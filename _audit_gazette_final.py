"""Final concrete delete lists with safe vs fix-needed split."""
from __future__ import annotations
import os, re, sys
from collections import Counter, defaultdict
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tanzania_gis.settings")
sys.path.insert(0, r"D:\MFUMO LUMC\LUMC\tanzania_gis")
import django; django.setup()
from locations.gazette_models import GazetteVillage

qs = list(GazetteVillage.objects.all().values(
    "id", "region_name", "district_name", "ward_name", "village_name"
))

BAD_VILLAGE_EXACT = {
    "sura ya", "of tanzania no.32 vol", "of tanzania no.32 vol. dated",
    "mtaa wa", "namba", "kijiji cha miaka", "trm (kijiji",
    "gunene1", "gwaam4", "qalieda8", "mahongol37", "kakola na.9",
    "no.5", "oljoro no.5", "block c1", "a matale", "a kimamba a",
    "ismani (t", "nangowe (m", "nangowe(s",
}
BAD_VILLAGE_RE = re.compile(
    r"(?i)^(sura\b|mtaa\b|kijiji\b)|of tanzania|vol\.?\s*dated|[A-Za-z]{4,}\d+$"
)
BAD_WARD_EXACT = {
    "la serikali na", "la dar es", "ya utemini", "ya mawenzi",
    "no.5 oljoro", "mambwekeny85", '"b"',
}
BAD_WARD_RE = re.compile(r"(?i)^la\s+(serikali|dar)\b|^ya\s+|mambwekeny\d+|^no\.\s*\d")

safe_del = []  # village is garbage
ward_bad_village_ok = []  # ward garbage, village looks ok
both = []

for g in qs:
    v = (g["village_name"] or "").strip()
    w = (g["ward_name"] or "").strip()
    vl, wl = v.lower(), w.lower()
    v_bad = vl in BAD_VILLAGE_EXACT or bool(BAD_VILLAGE_RE.search(v))
    w_bad = wl in BAD_WARD_EXACT or bool(BAD_WARD_RE.search(w))
    if v_bad and w_bad:
        both.append(g)
    elif v_bad:
        safe_del.append(g)
    elif w_bad:
        ward_bad_village_ok.append(g)

print(f"TOTAL={len(qs)}")
print(f"SAFE_DELETE (village bogus): {len(safe_del) + len(both)}")
print(f"  village-only bad: {len(safe_del)}")
print(f"  village+ward bad: {len(both)}")
print(f"WARD_BAD_VILLAGE_OK (fix ward or delete-row policy): {len(ward_bad_village_ok)}")

print("\n## SAFE DELETE — village string counts")
vc = Counter((g["village_name"] for g in safe_del + both))
for s, c in vc.most_common():
    regs = sorted({g["region_name"] for g in safe_del + both if g["village_name"] == s})
    print(f"  [{c:4d}] village={s!r} regions={len(regs)}")

print("\n## WARD BAD — ward string counts (village may be real)")
wc = Counter((g["ward_name"] for g in ward_bad_village_ok))
for s, c in wc.most_common():
    regs = sorted({g["region_name"] for g in ward_bad_village_ok if g["ward_name"] == s})
    print(f"  [{c:4d}] ward={s!r} regions={len(regs)} e.g. villages: ", end="")
    vs = [g["village_name"] for g in ward_bad_village_ok if g["ward_name"] == s][:5]
    print(vs)

# Truncated districts — FIX not delete
print("\n## TRUNCATED / BAD DISTRICT STRINGS (fix, do not mass-delete)")
trunc = {
    "Ngorongor": "Ngorongoro",
    "Mpwapw": "Mpwapwa",
    "Chamwin": "Chamwino",
    "Jiji": "(Dar municipalities — needs re-parse)",
    "Ulo": "Ulowa? or incomplete",
    "Manisp": "Manispaa (Lindi)",
    "Manispa": "Manispaa",
    "Tandahi": "Tandahimba?",
    "Misung": "Misungwi",
    "Sengere": "Sengerema",
    "Sumbawang": "Sumbawanga",
    "Shinyan": "Shinyanga",
    "Wanging'o": "Wanging'ombe",
    "Ngarenar": "ward trunc?",
}
dc = Counter(g["district_name"] for g in qs)
for bad, hint in trunc.items():
    c = dc.get(bad, 0)
    if c:
        print(f"  [{c:4d}] district={bad!r} -> {hint}")

# also check truncated wards that look like district trunc
print("\n## Other truncated-looking district names (len issue / incomplete)")
for d, c in sorted(dc.items(), key=lambda x: -x[1]):
    if d in trunc:
        continue
    if re.search(r"(?i)manispa|sumbaw|shinyan|misung|sengere|tandahi|wanging", d):
        print(f"  [{c:4d}] {d!r}")

# Cross-region: village named after other regions
print("\n## village_name equals a REGION name (not necessarily delete)")
REGIONS = {"arusha","dodoma","geita","iringa","kagera","katavi","kigoma","kilimanjaro",
           "lindi","manyara","mara","mbeya","morogoro","mtwara","mwanza","njombe",
           "pwani","rukwa","ruvuma","shinyanga","simiyu","singida","songwe","tabora","tanga"}
for g in qs:
    if (g["village_name"] or "").lower() in REGIONS and (g["village_name"] or "").lower() != (g["region_name"] or "").lower():
        pass
cross = defaultdict(list)
for g in qs:
    vl = (g["village_name"] or "").lower()
    if vl in REGIONS and vl != (g["region_name"] or "").lower():
        cross[vl].append(g["region_name"])
for name, regs in sorted(cross.items(), key=lambda x: -len(x[1]))[:15]:
    print(f"  village={name!r} count={len(regs)} under regions={sorted(set(regs))}")

# Ambiguous keep?
print("\n## REVIEW / AMBIGUOUS (not in safe-delete)")
for name in ["Ya Chini", "Ya Picha ya Ndege", "Namba One", "Iyela Namba", "Nhc", "Namba"]:
    rows = [g for g in qs if g["village_name"] == name or g["ward_name"] == name]
    print(f"  {name!r}: {len(rows)} rows")
    for g in rows[:3]:
        print(f"    {g['village_name']} | {g['ward_name']} | {g['district_name']} | {g['region_name']}")

print("\n## UNION counts for deletion planning")
print(f"  Delete if village bogus: {len(safe_del)+len(both)}")
print(f"  Rows with ward La Serikali na (any village): {sum(1 for g in qs if g['ward_name']=='La Serikali na')}")
print(f"  Rows with ward La Dar es: {sum(1 for g in qs if g['ward_name']=='La Dar es')}")
print(f"  Among La Serikali na, village also bogus: {sum(1 for g in qs if g['ward_name']=='La Serikali na' and (g['village_name'] or '').lower() in BAD_VILLAGE_EXACT)}")
print(f"  Among La Serikali na, village looks real: {sum(1 for g in qs if g['ward_name']=='La Serikali na' and (g['village_name'] or '').lower() not in BAD_VILLAGE_EXACT and not BAD_VILLAGE_RE.search(g['village_name'] or ''))}")
