import sys
import os
import asyncio

# --- THE FIX ---
# This forces Python to look in your current folder for the 'core' module
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
# ---------------

from core.database import engine
from core.models import Base

async def create_tables():
    print("Connecting to database...")
    try:
        async with engine.begin() as conn:
            print("Dropping old tables (if any)...")
            await conn.run_sync(Base.metadata.drop_all)

            print("Creating new tables...")
            await conn.run_sync(Base.metadata.create_all)
    except Exception as exc:
        print(f"[FAIL] Could not connect to Supabase: {type(exc).__name__}: {exc}")
        print("Checklist:")
        print("  1. Supabase dashboard -> Project Settings -> resume project if paused")
        print("  2. Copy a fresh 'Transaction pooler' URI (port 6543) into .env")
        print("  3. Reset DB password if needed, then update DATABASE_URL")
        print("  4. On campus networks, try mobile hotspot/VPN if SSL keeps failing")
        raise SystemExit(1) from exc

    print("[OK] Database initialization complete! Tables are ready.")

if __name__ == "__main__":
    asyncio.run(create_tables())