"""
Pre-flight check before running the live scraping pipeline.

Usage:
    python scripts/check_live_pipeline.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.pipeline_config import AUTH_STATE_PATH, INSTAGRAM_TARGETS, instagram_auth_ready


def check_redis() -> bool:
    try:
        import redis

        url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        client = redis.from_url(url, socket_connect_timeout=3)
        client.ping()
        print("[OK] Redis reachable")
        return True
    except Exception as exc:
        print(f"[FAIL] Redis: {exc}")
        print("       Start with: docker run -p 6379:6379 redis")
        return False


def check_instagram_auth() -> bool:
    if instagram_auth_ready():
        print(f"[OK] Instagram session: {AUTH_STATE_PATH}")
        return True
    print(f"[FAIL] Instagram session missing: {AUTH_STATE_PATH}")
    print("       Run: python scrapers/auth_states/login.py")
    return False


def check_env() -> bool:
    ok = True
    for key in ("DATABASE_URL", "GEMINI_API_KEY"):
        if os.getenv(key):
            print(f"[OK] {key} is set")
        else:
            print(f"[FAIL] {key} is not set in .env")
            ok = False
    return ok


def main() -> int:
    from dotenv import load_dotenv

    load_dotenv()
    print("[*] Live pipeline pre-flight check\n")

    results = [
        check_env(),
        check_redis(),
        check_instagram_auth(),
    ]

    print(f"\n[*] Configured Instagram targets: {len(INSTAGRAM_TARGETS)}")
    for url in INSTAGRAM_TARGETS:
        print(f"    - {url}")

    print("\n[*] Required running processes:")
    print("    1. python -m celery -A core.celery_app worker -Q scrapers,ocr_tasks,ai_extraction,deliveries --loglevel=info --concurrency=2")
    print("    2. python -m celery -A core.celery_app beat --loglevel=info   (optional, for auto-refresh)")
    print("    3. python scripts/trigger_pipeline.py   (manual first run)")

    if all(results):
        print("\n[OK] Ready to scrape live data.")
        return 0

    print("\n[FAIL] Fix the items above before triggering the pipeline.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
