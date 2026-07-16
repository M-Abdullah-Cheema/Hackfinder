"""Test Supabase connectivity with common connection modes (no secrets printed)."""
import asyncio
import os
import re
import sys
from urllib.parse import urlparse, urlunparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()


def _mask(url: str) -> str:
    return re.sub(r":([^:@/]+)@", ":****@", url)


def _build_variants(base_url: str) -> list[tuple[str, str]]:
    parsed = urlparse(base_url)
    user = parsed.username or ""
    password = parsed.password or ""
    ref = user.split(".")[-1] if "." in user else "unknown"

    return [
        (
            "pooler-6543 (transaction mode)",
            urlunparse(
                parsed._replace(
                    netloc=f"{user}:{password}@aws-0-ap-northeast-1.pooler.supabase.com:6543"
                )
            ),
        ),
        (
            "direct-5432 (bypass pooler)",
            urlunparse(
                parsed._replace(netloc=f"postgres:{password}@db.{ref}.supabase.co:5432")
            ),
        ),
        (
            "pooler-5432 (current .env)",
            base_url,
        ),
    ]


async def _test(label: str, sqlalchemy_url: str, *, loop_policy: str | None = None) -> bool:
    import asyncpg

    if loop_policy == "selector":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    dsn = sqlalchemy_url.replace("postgresql+asyncpg://", "postgresql://")
    try:
        conn = await asyncio.wait_for(asyncpg.connect(dsn, ssl="require"), timeout=20)
        await conn.fetchval("SELECT 1")
        await conn.close()
        print(f"[OK] {label}")
        return True
    except Exception as exc:
        print(f"[FAIL] {label}: {type(exc).__name__}: {exc}")
        return False


def _normalize_sqlalchemy_url(url: str) -> str:
    """Fix common .env mistakes like duplicated key prefixes."""
    cleaned = url.strip()
    if cleaned.upper().startswith("DATABASE_URL="):
        cleaned = cleaned.split("=", 1)[1].strip()
    return cleaned


def _validate_url(url: str) -> str | None:
    if not url.startswith(("postgresql://", "postgresql+asyncpg://", "postgres://")):
        return (
            "DATABASE_URL must start with postgresql+asyncpg:// "
            "(not DATABASE_URL=... and no spaces in the URL)"
        )
    if " @" in url or ":// " in url:
        return "DATABASE_URL contains spaces — remove spaces around @ and in the password"
    return None


async def main() -> int:
    base_url = _normalize_sqlalchemy_url(os.getenv("DATABASE_URL", ""))
    if not base_url:
        print("[FAIL] DATABASE_URL is not set in .env")
        return 1

    validation_error = _validate_url(base_url)
    if validation_error:
        print(f"[FAIL] {validation_error}")
        print("\nCorrect format:")
        print("DATABASE_URL=postgresql+asyncpg://postgres.PROJECT_REF:PASSWORD@aws-0-REGION.pooler.supabase.com:6543/postgres")
        return 1

    print(f"Testing connection modes for: {_mask(base_url)}\n")

    working: list[tuple[str, str]] = []
    variants = _build_variants(base_url)

    for label, url in variants:
        if await _test(label, url):
            working.append((label, url))

    if not working:
        print("\nRetrying with Windows selector event loop policy...")
        for label, url in variants:
            tagged = f"{label} + selector loop"
            if await _test(tagged, url, loop_policy="selector"):
                working.append((tagged, url))

    if not working:
        print("\nNo connection mode succeeded.")
        return 1

    print(f"\nWorking mode: {working[0][0]}")
    print("Update .env DATABASE_URL to the working host/port if different from current.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
