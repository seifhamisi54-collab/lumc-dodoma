"""Mwaka wa fedha (Tanzania: Julai 1 → Juni 30) — shared across modules."""
from __future__ import annotations

import re
from datetime import date

DEFAULT_FINANCIAL_YEAR = '2026/2027'
FY_START_YEAR = 2020
FY_YEARS_AHEAD = 15
FY_SESSION_KEY = 'lumc_financial_year'
FY_MAX_LENGTH = 32

_FY_PAIR_RE = re.compile(r'^(\d{4})\s*[/\-–—]\s*(\d{4})$')
_FY_YEAR_RE = re.compile(r'^(\d{4})$')


def financial_year_from_date(value=None) -> str:
    """Rudisha FY kama 2026/2027 kutoka tarehe (Jul–Jun)."""
    d = value or date.today()
    if hasattr(d, 'year'):
        year, month = d.year, d.month
    else:
        try:
            parsed = date.fromisoformat(str(d)[:10])
            year, month = parsed.year, parsed.month
        except ValueError:
            return DEFAULT_FINANCIAL_YEAR
    if month >= 7:
        return f'{year}/{year + 1}'
    return f'{year - 1}/{year}'


def normalize_financial_year(value, default=None) -> str:
    """
    Kubali maandishi ya kujaza: 2026/2027, 2026-2027, 2026, au maandishi mengine mafupi.
    """
    fy = (value or '').strip()
    if not fy:
        return default or DEFAULT_FINANCIAL_YEAR

    pair = _FY_PAIR_RE.match(fy)
    if pair:
        return f'{pair.group(1)}/{pair.group(2)}'

    year_only = _FY_YEAR_RE.match(fy)
    if year_only:
        y = int(year_only.group(1))
        return f'{y}/{y + 1}'

    # Hifadhi kama mtumiaji alivyoandika (mf. maelezo mafupi)
    return fy[:FY_MAX_LENGTH]


def suggested_financial_years(extra=None) -> list[str]:
    """Orodha ya mapendekezo (datalist) — hesabu + extra kutoka DB."""
    years: set[str] = set()
    current = financial_year_from_date()
    try:
        current_start = int(current.split('/')[0])
    except (ValueError, IndexError):
        current_start = date.today().year
    end_start = max(
        current_start + FY_YEARS_AHEAD,
        int(DEFAULT_FINANCIAL_YEAR.split('/')[0]) + FY_YEARS_AHEAD,
    )
    for y in range(FY_START_YEAR, end_start + 1):
        years.add(f'{y}/{y + 1}')
    if extra:
        for item in extra:
            cleaned = (item or '').strip()
            if cleaned:
                years.add(cleaned[:FY_MAX_LENGTH])
    years.add(DEFAULT_FINANCIAL_YEAR)
    years.add(current)
    return sorted(years, reverse=True)


def session_financial_year(request, fallback=None) -> str:
    raw = ''
    if request is not None and hasattr(request, 'session'):
        raw = (request.session.get(FY_SESSION_KEY) or '').strip()
    return normalize_financial_year(raw, default=fallback or DEFAULT_FINANCIAL_YEAR)


def set_session_financial_year(request, value) -> str:
    fy = normalize_financial_year(value)
    if request is not None and hasattr(request, 'session'):
        request.session[FY_SESSION_KEY] = fy
    return fy
