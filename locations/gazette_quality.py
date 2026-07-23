"""Filters za kusafisha impurities kutoka orodha ya vijiji (gazeti PDF)."""
from __future__ import annotations

import re

NUMBER_RE = re.compile(r'^\d+$')
YEAR_RE = re.compile(r'(?i)\bmwaka\b|\b20\d{2}\b')

EXACT_BAD = frozenset({
    'na', 'na.', 'n', 'ri', 'gp', 'dom', 'page', 'of', 'jr', 'tk', 'uo', 'uu', 'udom',
    'ba', 'be', 'bi', 'da', 'do', 'ea', 'go', 'ka', 'ko', 'le', 'li', 'lu', 'ma', 'ni',
    'no', 'ra', 'ru', 'sa', 'ta', 'we', 'ya', 'wa', 'zi', 'a i', 'n i', 'b a', 'l.s',
    'mji', 'mjini', 'jiji', 'maeneo', 'manispaa', 'manispa', 'manisp', 'halmashauri',
    'kata', 'kijiji', 'kitongoji', 'mtaa', 'jumla', 'muhtasari', 'orodha', 'ofisi',
    'mkoa', 'tanzania', 'serikali', 'mamlaka', 'wilaya', 'jina', 'utawala', 'sheria',
    'sura', 'notisi', 'septemba', 'supplement', 'gazeti', 'tangazo', 'mgawanyo',
    'namba', 'schedule', 'vol', 'dated', 'block', 'nhc',
    'sura ya', 'mtaa wa', 'kijiji cha', 'of tanzania no.32 vol',
    'of tanzania no.32 vol. dated', 'la serikali na', 'la dar es',
})

BAD_CONTAINS = re.compile(
    r'(?i)('
    r'halmasha|halmashauri|mgawanyo|muhtasari|jumla(\s+kuu)?|'
    r'mamlaka(\s+za)?|serikali(\s+za|\s+na)?|orodha(\s+ya)?|ofisi(ni)?|'
    r'to the gazette|supplement|notisi|kufuta\s+amri|'
    r'\bof tanzania\b|\bno\.\s*\d+.*vol\b|\bvol\.?\s*dated\b|'
    r'\bn\s*kata\b|\bn\s*kijiji\b|\bn\s*mtaa\b|\bn\s*kitongoji\b|'
    r'kata\s+na\s+kijiji|mtaa\s+n\s+kijiji|kijiji\s+(cha|na)|'
    r'mkoa\s+wa|katika\s+mamlaka|'
    r'^jiji(\s+la)?$|^manispaa?\s+ya$|^mji\s+(mdogo|wa|mkuu|singe)$|'
    r'^sura\b|^mtaa\s+wa\b|^kijiji\s+cha\b|'
    r'^la\s+(serikali|dar)\b|^ya\s+\d|'
    r'n\s+halmash|a\s+shauri|^a\s+ri$|s\s*erikali|'
    r'\bnamba\b|\bschedule\b|\bgazette\b'
    r')'
)

BAD_DISTRICT = re.compile(
    r'(?i)^('
    r'jiji(\s+la)?|manispaa?\s+ya|manispa|manisp|'
    r'mji\s+(mdogo|singe|mkuu|wa)|'
    r'orodha\s+ya|serikali|maeneo|mkoa\s+wa|'
    r'ya\s+\w+|n\s+halmash|n\s+i$|b\s+a$|'
    r'la\s+'
    r')'
)

# Prefixi za chembe za lugha zisizo sehemu ya jina
PARTICLE_PREFIX_RE = re.compile(r'(?i)^(ya|wa|la|na)\s+(.+)$')

# OCR: herufi + tarakimu mwishoni isiyo ya kawaida kwa jina (Gunene1, Gwaam4)
OCR_TRAIL_DIGIT_RE = re.compile(r'(?i)^[a-z]{3,}\d+$')
OCR_EMBED_DIGIT_RE = re.compile(r'(?i)[a-z]{4,}\d{2,}')

DUP_WORD_RE = re.compile(r'^(\S+)(?:\s+\1)+$', re.I)

# Marekebisho ya majina ya wilaya yaliyokatwa
DISTRICT_FIXES = {
    'ngorongor': 'Ngorongoro',
    'chamwin': 'Chamwino',
    'mpwapw': 'Mpwapwa',
    "wanging'o": "Wanging'ombe",
    'wangingombe': "Wanging'ombe",
    'shinyan': 'Shinyanga',
    'misung': 'Misungwi',
    'sumbawang': 'Sumbawanga',
    'sengere': 'Sengerema',
    'tandahi': 'Tandahimba',
}


def clean_place(text: str) -> str:
    text = re.sub(r'\s+', ' ', (text or '').strip())
    text = text.strip(' .,-;:()[]"\'')
    return text


def title_place(text: str) -> str:
    text = clean_place(text)
    if not text:
        return text
    collapsed = re.sub(r'\s+', '', text.lower())
    if 'dares' in collapsed and 'salaam' in collapsed:
        return 'Dar es Salaam'
    text = re.sub(
        r'(?i)^(wilaya|halmashauri|jiji|manispaa|mji|mamlaka)\s+(ya|la|wa)\s+',
        '',
        text,
    ).strip()
    parts = []
    for i, p in enumerate(text.split(' ')):
        if not p:
            continue
        low = p.lower()
        if i > 0 and low in {'ya', 'la', 'wa', 'za', 'cha', 'na', 'es'}:
            parts.append(low)
        else:
            parts.append(p[:1].upper() + p[1:].lower() if len(p) > 1 else p.upper())
    return ' '.join(parts)


def strip_particle_prefix(name: str) -> str:
    """Ya Utemini → Utemini; La Serikali na inabaki (bado chafu)."""
    name = clean_place(name)
    m = PARTICLE_PREFIX_RE.match(name)
    if not m:
        return name
    rest = clean_place(m.group(2))
    if len(rest) < 3:
        return name
    # usiondoe ikiwa "rest" bado ni maneno ya kiserikali
    if BAD_CONTAINS.search(rest) or rest.lower() in EXACT_BAD:
        return name
    return rest


def fix_district_name(name: str) -> str:
    name = title_place(normalize_dup_words(strip_particle_prefix(name)))
    key = name.lower().replace(' ', '')
    # try exact then prefix-less
    if name.lower() in DISTRICT_FIXES:
        return DISTRICT_FIXES[name.lower()]
    compact = re.sub(r'[^a-z\']', '', name.lower())
    for bad, good in DISTRICT_FIXES.items():
        if compact == re.sub(r'[^a-z\']', '', bad):
            return good
    return name


def is_impurity(name: str, *, kind: str = 'any') -> bool:
    """True = jina si sahihi kwa dropdown (impurity)."""
    name = clean_place(name)
    if not name or len(name) < 3:
        return True
    if NUMBER_RE.match(name):
        return True
    if name.lower() in EXACT_BAD:
        return True
    if YEAR_RE.search(name):
        return True
    if BAD_CONTAINS.search(name):
        return True
    if kind in ('district', 'any') and BAD_DISTRICT.search(name):
        return True
    if re.fullmatch(r'[A-Za-z]{1,2}', name):
        return True
    if re.search(r'(?i)^na\.?\s', name):
        return True
    if name.count('.') >= 2 and len(name) < 20:
        return True
    # Truncated OCR with unmatched brackets: "Trm (kijiji"
    if '(' in name or ')' in name:
        return True
    if re.search(r'(?i)\bkijiji\b', name) and kind in ('village', 'ward', 'any'):
        return True
    if re.search(r'(?i)\b(kata|mtaa|wilaya|mkoa)\b', name) and kind in ('village', 'ward', 'any'):
        return True
    # "La …" / "Ya …" particle-only leftovers that failed strip
    if re.match(r'(?i)^(la|ya|wa|na)\s+\S{1,6}$', name) and BAD_CONTAINS.search(name):
        return True
    if re.match(r'(?i)^la\s+', name) and kind in ('ward', 'village', 'any'):
        # La Dar es / La Serikali — never valid ward/village
        return True
    if OCR_TRAIL_DIGIT_RE.match(name.replace(' ', '')):
        return True
    if OCR_EMBED_DIGIT_RE.search(name.replace(' ', '')) and 'no.' not in name.lower():
        # allow things like "Block C1" already caught; Mahongol37 etc.
        if re.search(r'\d', name) and not re.search(r'(?i)\b[ab]\b$', name):
            # only reject if digits glued to letters without space
            if re.search(r'(?i)[a-z]\d|\d[a-z]', name):
                return True
    return False


def normalize_dup_words(name: str) -> str:
    name = clean_place(name)
    m = DUP_WORD_RE.match(name)
    if m:
        return m.group(1)
    parts = name.split()
    if len(parts) == 2 and parts[0].lower() == parts[1].lower():
        return parts[0]
    return name


def normalize_name(name: str, *, kind: str = 'any') -> str:
    name = normalize_dup_words(strip_particle_prefix(name))
    if kind == 'district':
        return fix_district_name(name)
    return title_place(name)


def is_clean_row(region: str, district: str, ward: str, village: str) -> bool:
    region = normalize_name(region, kind='region')
    district = normalize_name(district, kind='district')
    ward = normalize_name(ward, kind='ward')
    village = normalize_name(village, kind='village')
    if is_impurity(region, kind='region'):
        return False
    if is_impurity(district, kind='district'):
        return False
    if is_impurity(ward, kind='ward'):
        return False
    if is_impurity(village, kind='village'):
        return False
    return True
