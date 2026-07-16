import asyncio
import sys
import os
from sqlalchemy import select, func
from datetime import datetime, timedelta, timezone

# Ensure Python can find our core module
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from core.database import AsyncSessionLocal
from core.models import ScrapedItem

async def check_data_health():
    async with AsyncSessionLocal() as session:
        # Calculate the exact time 24 hours ago
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        
        # Query the database: "How many items were saved since yesterday?"
        query = select(func.count()).select_from(ScrapedItem).where(ScrapedItem.scraped_at >= yesterday)
        result = await session.execute(query)
        recent_count = result.scalar()

        print("-" * 50)
        if recent_count == 0:
            print("🚨 ALERT: 0 items scraped in the last 24 hours!")
            print("🚨 The target API structure likely changed. Investigate immediately!")
            # In a real production app, you would add an email or Slack webhook here
        else:
            print(f"✅ Health Check Passed: {recent_count} items successfully ingested recently.")
        print("-" * 50)

if __name__ == "__main__":
    asyncio.run(check_data_health())