"""Second-pass audit: header fragments missed by first heuristics."""
from __future__ import annotations
import os, re, sys
from collections import Counter, defaultdict

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tanzania_gis.settings")
sys.path.insert(0, r"D:\MFUMO LUMC\LUMC\tanzania_gis")
import django
django.setup()

from locations.gazette_models import GazetteVillage
from locations.gazette_quality import is_impurity, clean_place

EXTRA_EXACT = {
    "sura ya", "sura", "la serikali na", "la dar es", "la dar", "mtaa wa",
    "of tanzania no.32 vol", "of tanzania no.32 vol. dated",
    "namba", "namba one", "kijiji cha miaka", "trm (kijiji",
    "nhc", "jiji", "ya chini", "ya utemini", "ya mawenzi",
    "ya picha ya ndege", "a matale", "a kimamba a",
    "no.5", "no.5 oljoro", "oljoro no.5",
}

# Broader patterns
PATTERNS = [
    ("sura_fragment", re.compile(r"(?i)^sura\b")),
    ("of_tanzania", re.compile(r"(?i)\bof tanzania\b|\bno\.\s*\d+\s*vol")),
    ("la_fragment", re.compile(r"(?i)^la\s+(serikali|dar|jiji|manispaa|mkoa|wilaya)")),
    ("ya_fragment", re.compile(r"(?i)^ya\s+\w")),
    ("wa_fragment", re.compile(r"(?i)^wa\s+\w")),
    ("mtaa_kijiji_prefix", re.compile(r"(?i)^(mtaa|kijiji|kata|kitongoji)\b")),
    ("paren_trunc", re.compile(r"\($|\($|\(\w+$")),
    ("quote_letter", re.compile(r"(?i)^['\"]?[ab]['\"]?$|\s+'[ab]'$")),
    ("ocr_digit_suffix", re.compile(r"[A-Za-z]{3,}\d+$")),
    ("no_dot_num", re.compile(r"(?i)\bno\.\s*\d")),
    ("nhc_acronym", re.compile(r"(?i)^nhc$")),
    ("dated_gazette", re.compile(r"(?i)\bdated\b|\bvol\.?\b|\bsupplement\b")),
    ("serikali", re.compile(r"(?i)serikali")),
    ("truncated_district_suspect", re.compile(r"(?i)^(ngorongor|mpwapw|chamwin)$")),
]

by = defaultdict(lambda: {"rows": set(), "strings": Counter(), "samples": []})

# Also collect truncated-looking districts (len<=7 and missing vowels end?) 
district_counter = Counter()
districts_by_region = defaultdict(set)

all_flagged_ids = set()
string_field_rows = Counter()  # (field, val) -> count of rows where that field equals val AND row flagged

qs = list(GazetteVillage.objects.all().values(
    "id", "region_name", "district_name", "ward_name", "village_name"
))
print(f"TOTAL={len(qs)}")

for g in qs:
    rid = g["id"]
    districts_by_region[g["region_name"]].add(g["district_name"])
    district_counter[(g["region_name"], g["district_name"])] += 1
    for field in ("village_name", "ward_name", "district_name"):
        val = g[field] or ""
        low = val.lower().strip()
        hit = []
        if low in EXTRA_EXACT:
            hit.append("extra_exact_bad")
        for pname, cre in PATTERNS:
            if cre.search(val):
                hit.append(pname)
        for h in hit:
            by[h]["rows"].add(rid)
            by[h]["strings"][f"{field}={val}"] += 1
            if len(by[h]["samples"]) < 12:
                by[h]["samples"].append(
                    f"{g['village_name']} | {g['ward_name']} | {g['district_name']} | {g['region_name']}"
                )
            all_flagged_ids.add(rid)
            string_field_rows[(field, val)] += 1

# Sura ya specifically
print("\n=== 'Sura ya' as village_name ===")
sura = [g for g in qs if (g["village_name"] or "").lower() == "sura ya"]
print(f"rows={len(sura)}")
regs = Counter(g["region_name"] for g in sura)
print("by region:", dict(regs))
for g in sura[:8]:
    print(f"  {g}")

print("\n=== PATTERN HITS ===")
for pname in [p[0] for p in PATTERNS] + ["extra_exact_bad"]:
    info = by[pname]
    print(f"\n## {pname}: rows={len(info['rows'])} distinct={len(info['strings'])}")
    for s, c in info["strings"].most_common(25):
        print(f"  [{c:4d}] {s}")
    for s in info["samples"][:6]:
        print(f"  sample: {s}")

# Delete-ready: rows where village OR ward matches known bad
KNOWN_BAD_VILLAGE = {
    "sura ya", "of tanzania no.32 vol", "of tanzania no.32 vol. dated",
    "mtaa wa", "namba", "namba one", "kijiji cha miaka", "trm (kijiji",
    "gunene1", "gwaam4", "qalieda8", "mahongol37", "kakola na.9",
    "no.5", "oljoro no.5", "block c1", "ya chini", "a matale", "a kimamba a",
    "ya picha ya ndege", "iyela namba",
}
KNOWN_BAD_WARD = {
    "la serikali na", "la dar es", "ya utemini", "ya mawenzi",
    "no.5 oljoro", "mambwekeny85",
}
KNOWN_BAD_DISTRICT = {
    # incomplete admin labels
    "jiji",
}

del_ids = set()
for g in qs:
    v = (g["village_name"] or "").lower()
    w = (g["ward_name"] or "").lower()
    d = (g["district_name"] or "").lower()
    if v in KNOWN_BAD_VILLAGE or w in KNOWN_BAD_WARD or d in KNOWN_BAD_DISTRICT:
        del_ids.add(g["id"])
    # also pattern-based strong deletes
    if re.search(r"(?i)^sura\b", g["village_name"] or ""):
        del_ids.add(g["id"])
    if re.search(r"(?i)\bof tanzania\b", g["village_name"] or ""):
        del_ids.add(g["id"])
    if re.search(r"(?i)^la\s+(serikali|dar)\b", g["ward_name"] or ""):
        del_ids.add(g["id"])
    if re.search(r"(?i)^(mtaa|kijiji)\b", g["village_name"] or ""):
        del_ids.add(g["id"])
    if re.search(r"(?i)\bno\.\s*\d", (g["village_name"] or "") + " " + (g["ward_name"] or "")):
        del_ids.add(g["id"])
    if re.search(r"[A-Za-z]{4,}\d+$", g["village_name"] or ""):
        del_ids.add(g["id"])
    if re.search(r"[A-Za-z]{4,}\d+$", g["ward_name"] or ""):
        del_ids.add(g["id"])

print("\n=== DELETE-READY UNION ===")
print(f"rows_to_delete (strong rules): {len(del_ids)}")

# Breakdown by which field triggered
trig = Counter()
for g in qs:
    if g["id"] not in del_ids:
        continue
    v, w, d = g["village_name"] or "", g["ward_name"] or "", g["district_name"] or ""
    reasons = []
    if v.lower() in KNOWN_BAD_VILLAGE or re.search(r"(?i)^sura\b|\bof tanzania\b|^(mtaa|kijiji)\b|[A-Za-z]{4,}\d+$|\bno\.\s*\d", v):
        reasons.append(f"village={v}")
    if w.lower() in KNOWN_BAD_WARD or re.search(r"(?i)^la\s+(serikali|dar)\b|[A-Za-z]{4,}\d+$|\bno\.\s*\d", w):
        reasons.append(f"ward={w}")
    if d.lower() in KNOWN_BAD_DISTRICT:
        reasons.append(f"district={d}")
    for r in reasons:
        trig[r] += 1

print("trigger string counts (rows):")
for s, c in trig.most_common(40):
    print(f"  [{c:4d}] {s}")

# Ambiguous / maybe-real — report separately
print("\n=== AMBIGUOUS (review, maybe real places) ===")
ambig = {
    "ya chini": "could be '... Ya Chini' fragment OR real",
    "ya utemini": "Singida? Utemini is a real ward — 'Ya' may be OCR prefix",
    "ya mawenzi": "Mawenzi real; 'Ya' prefix suspicious",
    "ya picha ya ndege": "real street/place name in DSM possible",
    "a matale": "likely 'Matale A' OCR reorder",
    "a kimamba a": "Kimamba A fragment",
    "block c1": "urban block id, not village",
    "nhc": "acronym estate name — often real neighbourhood label",
    "jiji": "district should be Ilala/Kinondoni/Temeke/Kigamboni/Ubungo — 'Jiji' is incomplete",
    "iyela namba": "maybe 'Iyela' + 'Namba' OCR",
    "namba one": "possibly real local name",
}
for name, note in ambig.items():
    rows_v = sum(1 for g in qs if (g["village_name"] or "").lower() == name)
    rows_w = sum(1 for g in qs if (g["ward_name"] or "").lower() == name)
    rows_d = sum(1 for g in qs if (g["district_name"] or "").lower() == name)
    if rows_v or rows_w or rows_d:
        print(f"  {name!r}: v={rows_v} w={rows_w} d={rows_d} — {note}")
        for g in qs:
            if name in {(g["village_name"] or "").lower(), (g["ward_name"] or "").lower(), (g["district_name"] or "").lower()}:
                print(f"    {g['village_name']} | {g['ward_name']} | {g['district_name']} | {g['region_name']}")

# Truncated districts across all regions
print("\n=== ALL REGIONS: DISTINCT DISTRICTS (flag truncations) ===")
# known truncated
TRUNC_HINT = re.compile(r"(?i)(ngorongor|mpwapw|chamwin|^jiji$)")
for reg in sorted(districts_by_region.keys()):
    dists = sorted(districts_by_region[reg], key=str.lower)
    flags = [d for d in dists if TRUNC_HINT.search(d) or (len(d) <= 4 and d.lower() not in {"meru", "bahi", "geita", "chato", "nyasa", "same", "romo"})]
    print(f"\n{reg}: {dists}")
    if flags:
        print(f"  ** look wrong: {flags}")

# NHC rows
print("\n=== NHC rows ===")
for g in qs:
    if (g["village_name"] or "").lower() == "nhc" or (g["ward_name"] or "").lower() == "nhc":
        print(f"  {g['village_name']} | {g['ward_name']} | {g['district_name']} | {g['region_name']}")

# High-freq bogus confirmed
print("\n=== CONFIRMED BOGUS HIGH-FREQ ===")
for name in ["la serikali na", "la dar es", "sura ya", "of tanzania no.32 vol", "of tanzania no.32 vol. dated", "mtaa wa"]:
    for field in ("village_name", "ward_name", "district_name"):
        n = sum(1 for g in qs if (g[field] or "").lower() == name)
        if n:
            regs = sorted({g["region_name"] for g in qs if (g[field] or "").lower() == name})
            print(f"  {field}={name!r} rows={n} regions={len(regs)}: {regs}")

print(f"\nALL_FLAGGED_PATTERN_ROWS={len(all_flagged_ids)}")
print(f"STRONG_DELETE_ROWS={len(del_ids)}")
print("DONE2")
