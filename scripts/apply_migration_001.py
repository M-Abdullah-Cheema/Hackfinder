"""
Apply scripts/migrations/001_enable_postgis_and_global_fields.sql to Supabase.

Usage:
    python scripts/apply_migration_001.py
"""
from __future__ import annotations

import asyncio
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from sqlalchemy import text

load_dotenv()

from core.database import engine


def _statements(sql: str) -> list[str]:
    """Split SQL on semicolons, ignoring comment-only chunks."""
    parts: list[str] = []
    for raw in sql.split(";"):
        lines = []
        for line in raw.splitlines():
            stripped = line.strip()
            if stripped.startswith("--"):
                continue
            lines.append(line)
        chunk = "\n".join(lines).strip()
        if chunk:
            parts.append(chunk)
    return parts


async def main() -> None:
    sql_path = os.path.join(
        os.path.dirname(__file__),
        "migrations",
        "001_enable_postgis_and_global_fields.sql",
    )
    with open(sql_path, encoding="utf-8") as fh:
        sql = fh.read()

    async with engine.begin() as conn:
        for statement in _statements(sql):
            preview = re.sub(r"\s+", " ", statement)[:90]
            print(f"-> {preview}...")
            await conn.execute(text(statement))

    await engine.dispose()
    print("[OK] Migration 001 applied (PostGIS + global opportunity fields).")


if __name__ == "__main__":
    asyncio.run(main())
