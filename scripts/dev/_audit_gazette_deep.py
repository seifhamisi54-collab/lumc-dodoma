"""Deep audit: GazetteVillage names that are NOT real places (beyond is_impurity)."""
from __future__ import annotations

import os
import re
import sys
from collections import Counter, defaultdict

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tanzania_gis.settings")
sys.path.insert(0, r"D:\MFUMO LUMC\LUMC\tanzania_gis")

import django
django.setup()

from locations.gazette_models import GazetteVillage
from locations.gazette_quality import is_impurity, clean_place

# Official-ish Tanzania region names (for cross-region district checks)
REGIONS = {
    "arusha", "dar es salaam", "dodoma", "geita", "iringa", "kagera", "katavi",
    "kigoma", "kilimanjaro", "lindi", "manyara", "mara", "mbeya", "mjini magharibi",
    "morogoro", "mtwara", "mwanza", "njombe", "pwani", "rukwa", "ruvuma",
    "shinyanga", "simiyu", "singida", "songwe", "tabora", "tanga", "unguja",
    "kusini pemba", "kaskazini pemba", "kusini unuja", "kaskazini unuja",
    "kusini ungua", "kaskazini ungua",
}

MONTHS_SW = {
    "januari", "februari", "machi", "aprili", "mei", "juni", "julai",
    "agosti", "septemba", "oktoba", "novemba", "desemba",
    "january", "february", "march", "april", "may", "june", "july",
    "august", "september", "october", "november", "december",
}

LEGAL_EN = {
    "shall", "under", "section", "thereof", "hereby", "whereas", "pursuant",
    "schedule", "supplement", "gazette", "notice", "order", "regulation",
    "cap", "act", "law", "laws", "part", "chapter", "subsection", "paragraph",
}

CONTAINS_RE = re.compile(
    r"(?i)\b("
    r"kijiji|kata|mtaa|kitongoji|wilaya|mkoa|halmasha|mamlaka|serikali|"
    r"orodha|ofisi|gazeti|notisi|mwaka|jumla|muhtasari|"
    r"na\.|namba|page|schedule|gazette"
    r")\b"
    r"|\bgn\b|\bgp\b|\bschedule\b"
)

STARTS_RE = re.compile(r"^(Ya|Wa|La|Na|N|A)\s+", re.I)
# Also bare starts with those as whole first token patterns user asked
STARTS_BARE = re.compile(r"^(Ya|Wa|La|Na)\b", re.I)
STARTS_SINGLE = re.compile(r"^(N|A)\s+")

ALL_CAPS_LONG = re.compile(r"^[A-Z][A-Z\s\.\-]{12,}$")
DIGITS_ODD = re.compile(r"(?=\D*\d)(?=.*[A-Za-z]).*")  # mixed letters+digits
DIGIT_PATTERNS = [
    re.compile(r"^\d"),           # starts with digit
    re.compile(r"\d{3,}"),        # long number run
    re.compile(r"[A-Za-z]+\d+\d"),  # letters then multi digits oddly
    re.compile(r"\d+[A-Za-z]+\d+"),
]

HEADER_FRAG = re.compile(
    r"(?i)^(ya|wa|la|na|n|a|of|the|and|or|for|to|in|on|by)$"
    r"|^(ya|wa|la)\s+\w{1,3}$"
    r"|halmasha|orodha|muhtasari|jumla|notisi|gazeti"
)

FIELDS = ("village_name", "ward_name", "district_name", "region_name")


def flag_reasons(name: str, kind: str) -> list[str]:
    """Extra heuristics beyond is_impurity. Returns list of reason codes."""
    n = clean_place(name)
    if not n:
        return ["empty"]
    reasons = []
    low = n.lower()

    # Skip if already caught by is_impurity — we still track separately
    if is_impurity(n, kind=kind if kind != "region" else "region"):
        reasons.append("is_impurity")

    if CONTAINS_RE.search(n):
        reasons.append("contains_admin_token")
    if STARTS_RE.match(n) or STARTS_BARE.match(n):
        # avoid flagging legitimate "Na..." place names that are one word like "Nachingwea"
        # User asked: Starts with Ya , Wa , La , Na , N , A (with space implied for N/A)
        if STARTS_RE.match(n) or (STARTS_BARE.match(n) and " " in n):
            reasons.append("starts_preposition")
        elif re.match(r"^[NA]\s", n):
            reasons.append("starts_preposition")
    if len(n) <= 2:
        reasons.append("very_short")
    if ALL_CAPS_LONG.match(n) and len(n.split()) >= 2:
        reasons.append("all_caps_bureaucratic")
    if low in MONTHS_SW:
        reasons.append("month_name")
    if low in LEGAL_EN or any(w in LEGAL_EN for w in low.split()):
        reasons.append("legal_english")
    if re.search(r"\d", n) and re.search(r"[A-Za-z]", n):
        reasons.append("digits_mixed")
    elif re.fullmatch(r"\d+", n):
        reasons.append("digits_only")

    return reasons


def looks_header_fragment(name: str) -> bool:
    n = clean_place(name)
    if not n:
        return True
    if HEADER_FRAG.search(n):
        return True
    if len(n) <= 3 and n.lower() in {"ya", "wa", "la", "na", "n", "a", "of", "gp", "gn"}:
        return True
    if CONTAINS_RE.search(n):
        return True
    return False


def main():
    total = GazetteVillage.objects.count()
    print(f"TOTAL_ROWS={total}")
    print()

    # Collect all rows
    by_reason_samples = defaultdict(list)  # reason -> list of (field, value, region, full)
    by_reason_rows = defaultdict(set)      # reason -> set of row ids
    bad_string_counts = Counter()          # (field, value) -> rows
    bad_strings_by_type = defaultdict(Counter)  # reason -> Counter of strings
    village_eq_ward_header = []
    cross_region = []  # district is another region name
    still_impure = []

    # Frequency of name across regions (for high-freq weird)
    name_regions = defaultdict(lambda: defaultdict(set))  # field -> name_low -> regions
    name_row_ids = defaultdict(lambda: defaultdict(set))

    # District sets per region
    districts_by_region = defaultdict(set)
    all_district_region_pairs = defaultdict(set)  # district_low -> regions

    sample_limit = 25

    qs = GazetteVillage.objects.all().values(
        "id", "region_name", "district_name", "ward_name", "village_name"
    )
    row_count = 0
    any_extra_flag_ids = set()

    for g in qs.iterator(chunk_size=2000):
        row_count += 1
        rid = g["id"]
        region = g["region_name"] or ""
        district = g["district_name"] or ""
        ward = g["ward_name"] or ""
        village = g["village_name"] or ""

        districts_by_region[region].add(district)
        all_district_region_pairs[district.lower()].add(region)

        for field, val, kind in (
            ("village_name", village, "village"),
            ("ward_name", ward, "ward"),
            ("district_name", district, "district"),
            ("region_name", region, "region"),
        ):
            name_regions[field][val.lower()].add(region)
            name_row_ids[field][val.lower()].add(rid)
            reasons = flag_reasons(val, kind)
            # Only care about EXTRA beyond is_impurity for "slipped past",
            # but also report is_impurity still in DB
            for r in reasons:
                by_reason_rows[r].add(rid)
                bad_strings_by_type[r][val] += 1
                if len(by_reason_samples[r]) < sample_limit:
                    by_reason_samples[r].append(
                        (field, val, region, f"{village} | {ward} | {district} | {region}")
                    )
                if r != "is_impurity":
                    any_extra_flag_ids.add(rid)
                    bad_string_counts[(field, val)] += 1
            if "is_impurity" in reasons and len(still_impure) < 40:
                still_impure.append((field, val, region, rid))

        # village == ward and looks like header
        if village and ward and village.lower() == ward.lower() and looks_header_fragment(village):
            village_eq_ward_header.append((rid, village, district, region))
            by_reason_rows["village_eq_ward_header"].add(rid)
            bad_strings_by_type["village_eq_ward_header"][village] += 1
            any_extra_flag_ids.add(rid)

        # district_name equals another region's name (not current)
        dlow = district.lower().strip()
        rlow = region.lower().strip()
        if dlow in REGIONS and dlow != rlow and dlow not in {
            # some places share names legitimately? still flag
        }:
            # Also flag if district is literally a region name different from parent
            cross_region.append((rid, district, region, village, ward))
            by_reason_rows["cross_region_district"].add(rid)
            bad_strings_by_type["cross_region_district"][f"{district} under {region}"] += 1
            any_extra_flag_ids.add(rid)

    print("=" * 72)
    print("STILL MATCHING is_impurity (should have been cleaned)")
    print(f"  rows: {len(by_reason_rows['is_impurity'])}")
    print("  samples:")
    for item in still_impure[:20]:
        print(f"    {item}")
    print()

    EXTRA_REASONS = [
        "contains_admin_token",
        "starts_preposition",
        "very_short",
        "all_caps_bureaucratic",
        "month_name",
        "legal_english",
        "digits_mixed",
        "digits_only",
        "village_eq_ward_header",
        "cross_region_district",
    ]

    print("=" * 72)
    print("EXTRA HEURISTICS (beyond / in addition to is_impurity)")
    print(f"  rows with ANY extra flag: {len(any_extra_flag_ids)}")
    print()

    for reason in EXTRA_REASONS:
        rows = by_reason_rows.get(reason, set())
        print("-" * 72)
        print(f"TYPE: {reason}")
        print(f"  affected_rows: {len(rows)}")
        top = bad_strings_by_type[reason].most_common(40)
        print(f"  distinct_bad_strings: {len(bad_strings_by_type[reason])}")
        print("  top strings (count):")
        for s, c in top:
            print(f"    [{c:5d}] {s!r}")
        print("  samples (field, value, region, full path):")
        for s in by_reason_samples.get(reason, [])[:15]:
            print(f"    {s}")
        print()

    # High-frequency weird names across many regions
    print("=" * 72)
    print("HIGH-FREQUENCY NAMES ACROSS MANY REGIONS (potential bogus)")
    # Candidate pool: names that hit any suspicious reason OR appear in >= 8 regions
    weird_tokens = set()
    for reason in EXTRA_REASONS + ["is_impurity"]:
        for s in bad_strings_by_type[reason]:
            weird_tokens.add(s.lower())

    hf_candidates = []
    for field in ("village_name", "ward_name", "district_name"):
        for name_low, regions in name_regions[field].items():
            nreg = len(regions)
            nrows = len(name_row_ids[field][name_low])
            if nreg >= 5:
                # score weirdness
                sample_name = None
                # get original casing from a sample in bad strings or reconstruct
                sample_name = name_low
                is_weird = name_low in weird_tokens or looks_header_fragment(name_low)
                # also flag if very common AND short/admin-like
                reasons = flag_reasons(name_low, field.replace("_name", ""))
                extra = [r for r in reasons if r != "is_impurity"]
                if is_weird or extra or (nreg >= 10 and looks_header_fragment(name_low)):
                    hf_candidates.append((nreg, nrows, field, name_low, sorted(regions)[:8], extra or reasons))

    hf_candidates.sort(reverse=True)
    print(f"  candidates: {len(hf_candidates)}")
    for item in hf_candidates[:60]:
        nreg, nrows, field, name_low, regs, reasons = item
        print(f"  regions={nreg:2d} rows={nrows:5d} {field}={name_low!r} reasons={reasons} e.g.regs={regs}")

    # Also: same string high freq even if not already flagged — top multi-region villages that look odd
    print()
    print("TOP multi-region village_name (nreg>=6) for manual scan:")
    multi_v = []
    for name_low, regions in name_regions["village_name"].items():
        if len(regions) >= 6:
            multi_v.append((len(regions), len(name_row_ids["village_name"][name_low]), name_low, sorted(regions)))
    multi_v.sort(reverse=True)
    for nreg, nrows, name_low, regs in multi_v[:40]:
        frag = looks_header_fragment(name_low) or bool(flag_reasons(name_low, "village"))
        mark = " **SUS**" if frag else ""
        print(f"  r={nreg:2d} n={nrows:5d} {name_low!r}{mark} regs={regs[:6]}...")

    # Cross-region oddities detail
    print()
    print("=" * 72)
    print("CROSS-REGION DISTRICT ODDITIES (district_name is a region name)")
    cr_counter = Counter((d, r) for _, d, r, _, _ in cross_region)
    print(f"  rows: {len(cross_region)}")
    for (d, r), c in cr_counter.most_common(50):
        print(f"  [{c:5d}] district={d!r} under region={r!r}")
    print("  samples:")
    for item in cross_region[:30]:
        print(f"    id={item[0]} district={item[1]!r} region={item[2]!r} v={item[3]!r} w={item[4]!r}")

    # District that appears under many regions (mis-assigned)
    print()
    print("Districts appearing under MANY regions (>=3):")
    multi_d = [(len(regs), d, sorted(regs)) for d, regs in all_district_region_pairs.items() if len(regs) >= 3]
    multi_d.sort(reverse=True)
    for nreg, d, regs in multi_d[:40]:
        print(f"  regions={nreg} district={d!r} -> {regs}")

    # Full distinct district lists for a few regions
    print()
    print("=" * 72)
    print("FULL DISTINCT DISTRICT LISTS (sample regions)")
    # Prefer regions that showed cross-region issues, else alphabetical sample
    prefer = []
    for (d, r), c in cr_counter.most_common():
        if r not in prefer:
            prefer.append(r)
    all_regs = sorted(districts_by_region.keys())
    sample_regs = (prefer + [r for r in all_regs if r not in prefer])[:6]
    if "Ruvuma" in districts_by_region or "ruvuma" in {x.lower() for x in districts_by_region}:
        for r in districts_by_region:
            if r.lower() == "ruvuma" and r not in sample_regs:
                sample_regs.insert(0, r)
    sample_regs = sample_regs[:6]

    for reg in sample_regs:
        dists = sorted(districts_by_region[reg], key=lambda x: x.lower())
        print(f"\nREGION: {reg!r}  ({len(dists)} distinct districts)")
        for d in dists:
            dlow = d.lower()
            mark = ""
            if dlow in REGIONS and dlow != reg.lower():
                mark = "  << REGION_NAME_AS_DISTRICT"
            elif is_impurity(d, kind="district"):
                mark = "  << is_impurity"
            else:
                rs = [r for r in flag_reasons(d, "district") if r != "is_impurity"]
                if rs:
                    mark = f"  << {','.join(rs)}"
            print(f"  - {d!r}{mark}")

        # suspicious wards/villages in this region
        print(f"  Suspicious ward/village in {reg!r}:")
        sus = []
        for g in GazetteVillage.objects.filter(region_name=reg).values(
            "id", "district_name", "ward_name", "village_name"
        ).iterator(chunk_size=1000):
            for field, val, kind in (
                ("ward", g["ward_name"], "ward"),
                ("village", g["village_name"], "village"),
            ):
                rs = flag_reasons(val, kind)
                extra = [r for r in rs if r != "is_impurity"]
                if extra or "is_impurity" in rs:
                    sus.append((g["id"], field, val, g["district_name"], rs))
        # unique by (field,val)
        seen = set()
        shown = 0
        for item in sus:
            key = (item[1], item[2].lower())
            if key in seen:
                continue
            seen.add(key)
            print(f"    id={item[0]} {item[1]}={item[2]!r} district={item[3]!r} reasons={item[4]}")
            shown += 1
            if shown >= 40:
                print(f"    ... truncated ({len(seen)} distinct suspicious names in region)")
                break
        print(f"  distinct suspicious ward/village names shown/capped; total distinct flagged: {len(seen)}")

    # Concrete delete lists: unique bad strings with row counts
    print()
    print("=" * 72)
    print("CONCRETE BAD STRINGS FOR DELETION (aggregated)")
    # Union of all extra-flagged field values with counts
    delete_candidates = Counter()
    for g in GazetteVillage.objects.all().values(
        "id", "region_name", "district_name", "ward_name", "village_name"
    ).iterator(chunk_size=2000):
        rid = g["id"]
        flagged = False
        tags = []
        for field, val, kind in (
            ("village_name", g["village_name"], "village"),
            ("ward_name", g["ward_name"], "ward"),
            ("district_name", g["district_name"], "district"),
        ):
            rs = flag_reasons(val, kind)
            extra = [r for r in rs if r != "is_impurity"]
            if "is_impurity" in rs or extra:
                flagged = True
                tags.extend([(field, val, r) for r in rs])
            if field == "village_name" and g["village_name"] and g["ward_name"]:
                if g["village_name"].lower() == g["ward_name"].lower() and looks_header_fragment(g["village_name"]):
                    flagged = True
                    tags.append((field, val, "village_eq_ward_header"))
            if field == "district_name":
                dlow = (val or "").lower().strip()
                rlow = (g["region_name"] or "").lower().strip()
                if dlow in REGIONS and dlow != rlow:
                    flagged = True
                    tags.append((field, val, "cross_region_district"))
        if flagged:
            for field, val, r in tags:
                delete_candidates[(r, field, val)] += 1

    # Print grouped
    by_type = defaultdict(list)
    for (r, field, val), c in delete_candidates.items():
        by_type[r].append((c, field, val))

    grand_ids = set()
    # recount unique row ids properly
    print(f"\nSummary row counts by type:")
    for reason in ["is_impurity"] + EXTRA_REASONS:
        print(f"  {reason}: {len(by_reason_rows.get(reason, set()))} rows")

    print(f"\nUNION any-flag rows (is_impurity OR extra): ", end="")
    union = set(by_reason_rows.get("is_impurity", set())) | any_extra_flag_ids
    print(len(union))

    print("\nBAD STRING LIST (reason | field | count | string):")
    for reason in ["is_impurity"] + EXTRA_REASONS:
        items = sorted(by_type.get(reason, []), reverse=True)
        if not items:
            continue
        print(f"\n## {reason} ({len(items)} distinct field-values)")
        for c, field, val in items[:80]:
            print(f"  {c:5d}  {field:15s}  {val!r}")
        if len(items) > 80:
            print(f"  ... +{len(items)-80} more distinct")

    print("\nDONE")


if __name__ == "__main__":
    main()
