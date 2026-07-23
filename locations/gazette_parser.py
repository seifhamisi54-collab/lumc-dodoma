"""Parse gazeti PDF (Mgawanyo wa Maeneo) → rows (region, district, ward, village)."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from locations.gazette_quality import (
    clean_place,
    is_clean_row,
    is_impurity,
    normalize_dup_words,
    title_place,
)

try:
    import pdfplumber
except ImportError:  # pragma: no cover
    pdfplumber = None


HEADER_RE = re.compile(r'(?i)mkoa\s+wa\s+(.+)')
NUMBER_RE = re.compile(r'^\d+$')


@dataclass
class VillageRow:
    region_name: str
    district_name: str
    ward_name: str
    village_name: str
    unit_type: str  # village | mtaa
    source_file: str


# Backwards-compatible aliases for older imports
_clean_name = clean_place
_title_place = title_place
_is_noise = is_impurity


def _column_bands(page_width: float) -> dict[str, tuple[float, float]]:
    w = page_width or 595.0
    return {
        'district': (0.10 * w, 0.28 * w),
        'ward': (0.27 * w, 0.44 * w),
        'village': (0.43 * w, 0.60 * w),
        'kitongoji': (0.59 * w, 0.98 * w),
    }


def _assign_column(x0: float, bands: dict[str, tuple[float, float]]) -> str | None:
    for key, (lo, hi) in bands.items():
        if lo <= x0 < hi:
            return key
    return None


def _cluster_rows(words: list[dict], y_tol: float = 3.5) -> list[list[dict]]:
    if not words:
        return []
    ordered = sorted(words, key=lambda w: (round(w['top'] / y_tol), w['x0']))
    rows: list[list[dict]] = []
    current: list[dict] = []
    current_top = None
    for w in ordered:
        if current_top is None or abs(w['top'] - current_top) <= y_tol:
            current.append(w)
            if current_top is None:
                current_top = w['top']
        else:
            rows.append(current)
            current = [w]
            current_top = w['top']
    if current:
        rows.append(current)
    return rows


def _split_num_name(words: list[dict]) -> tuple[bool, str]:
    """Return (has_number, name_without_numbers)."""
    has_num = False
    parts = []
    for w in sorted(words, key=lambda x: x['x0']):
        t = (w.get('text') or '').strip()
        if NUMBER_RE.match(t):
            has_num = True
            continue
        parts.append(t)
    return has_num, clean_place(' '.join(parts))


def parse_gazette_pdf(path: Path) -> list[VillageRow]:
    if pdfplumber is None:
        raise RuntimeError('pdfplumber haijasakinishwa. Endesha: pip install pdfplumber')

    rows_out: list[VillageRow] = []
    seen: set[tuple[str, str, str, str]] = set()
    region = ''
    district = ''
    ward = ''
    village = ''
    unit_type = 'village'

    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ''
            for line in text.splitlines():
                m = HEADER_RE.search(line.strip())
                if m:
                    region = title_place(re.sub(r'\s+\d+\s*$', '', clean_place(m.group(1))))
            if re.search(r'(?i)na\.?\s*mtaa', text) and not re.search(r'(?i)na\.?\s*kijiji', text):
                unit_type = 'mtaa'
            elif re.search(r'(?i)na\.?\s*kijiji', text):
                unit_type = 'village'

            # Skip summary/index pages
            if re.search(r'(?i)\bmuhtasari\b|\bjumla\s+kuu\b', text) and not re.search(
                r'(?i)na\.?\s*kijiji|na\.?\s*kitongoji|na\.?\s*mtaa', text
            ):
                continue

            words = page.extract_words(use_text_flow=False, keep_blank_chars=False) or []
            if not words or not region or is_impurity(region, kind='region'):
                continue

            bands = _column_bands(float(page.width or 595))
            for word_row in _cluster_rows(words):
                buckets: dict[str, list[dict]] = {
                    'district': [], 'ward': [], 'village': [], 'kitongoji': []
                }
                for w in word_row:
                    col = _assign_column(float(w['x0']), bands)
                    if col:
                        buckets[col].append(w)

                d_num, d_name = _split_num_name(buckets['district'])
                w_num, w_name = _split_num_name(buckets['ward'])
                v_num, v_name = _split_num_name(buckets['village'])

                joined = ' '.join(x for x in (d_name, w_name, v_name) if x).lower()
                if any(k in joined for k in ('halmashauri', 'muhtasari', 'jumla', 'kitongoji na')):
                    continue
                if 'kijiji' in joined and 'kata' in joined:
                    continue

                # Update parents ONLY when column has serial number + clean name
                # (avoids kitongoji / header fragments polluting state)
                village_updated = False
                if d_num and d_name and not is_impurity(d_name, kind='district'):
                    district = title_place(normalize_dup_words(d_name))
                if w_num and w_name and not is_impurity(w_name, kind='ward'):
                    ward = title_place(normalize_dup_words(w_name))
                if v_num and v_name and not is_impurity(v_name, kind='village'):
                    village = title_place(normalize_dup_words(v_name))
                    village_updated = True

                # Emit only when a NEW kijiji/mtaa appears (not every kitongoji line)
                if not village_updated:
                    continue
                if not is_clean_row(region, district, ward, village):
                    continue

                key = (region.lower(), district.lower(), ward.lower(), village.lower())
                if key in seen:
                    continue
                seen.add(key)
                rows_out.append(
                    VillageRow(
                        region_name=region,
                        district_name=district,
                        ward_name=ward,
                        village_name=village,
                        unit_type=unit_type,
                        source_file=path.name,
                    )
                )
    return rows_out


def iter_gazette_pdfs(root: Path) -> list[Path]:
    root = Path(root)
    pdfs = sorted(root.rglob('*.pdf'))
    return [
        p for p in pdfs
        if not (p.name.upper().startswith('797') and 'MAMLAKA ZA MIJI' in p.name.upper())
    ]


def parse_gazette_folder(root: Path) -> list[VillageRow]:
    all_rows: list[VillageRow] = []
    seen: set[tuple[str, str, str, str]] = set()
    for pdf in iter_gazette_pdfs(root):
        try:
            part = parse_gazette_pdf(pdf)
        except Exception:
            continue
        for row in part:
            if not is_clean_row(row.region_name, row.district_name, row.ward_name, row.village_name):
                continue
            key = (
                row.region_name.lower(),
                row.district_name.lower(),
                row.ward_name.lower(),
                row.village_name.lower(),
            )
            if key in seen:
                continue
            seen.add(key)
            all_rows.append(row)
    return all_rows
