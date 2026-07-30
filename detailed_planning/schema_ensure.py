"""Ensure detailed_planning schema columns exist (Neon / partial migrate)."""
from __future__ import annotations

import logging

from django.db import connections

logger = logging.getLogger(__name__)

_ENSURED = False


def ensure_village_plans_schema(*, force: bool = False) -> bool:
    """
    Hakikisha column financial_year ipo kwenye detailed_planning.village_plans.
    Inaitwa kutoka API za stats/village-plans ili kuepuka HTML 500 baada ya deploy.
    """
    global _ENSURED
    if _ENSURED and not force:
        return True

    conn = connections['detailed_planning']
    try:
        with conn.cursor() as cur:
            cur.execute('CREATE SCHEMA IF NOT EXISTS detailed_planning')
            cur.execute(
                """
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'detailed_planning'
                  AND table_name = 'village_plans'
                  AND column_name = 'financial_year'
                """
            )
            if cur.fetchone():
                _ENSURED = True
                return True

            # Table might live without schema qualification in some dumps
            cur.execute(
                """
                SELECT table_schema
                FROM information_schema.tables
                WHERE table_name = 'village_plans'
                  AND table_schema IN ('detailed_planning', 'public')
                LIMIT 1
                """
            )
            row = cur.fetchone()
            if not row:
                logger.warning('village_plans table not found; skip financial_year ensure')
                return False
            schema = row[0]
            cur.execute(
                f"""
                ALTER TABLE "{schema}"."village_plans"
                ADD COLUMN IF NOT EXISTS financial_year VARCHAR(32) NOT NULL DEFAULT '2026/2027'
                """
            )
            cur.execute(
                f"""
                CREATE INDEX IF NOT EXISTS village_plans_financial_year_idx
                ON "{schema}"."village_plans" (financial_year)
                """
            )
        _ENSURED = True
        logger.info('Ensured financial_year on %s.village_plans', schema)
        return True
    except Exception:
        logger.exception('ensure_village_plans_schema failed')
        return False
