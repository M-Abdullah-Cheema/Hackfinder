import asyncio
import sys
import os
from sqlalchemy import select

# Ensure Python can find your core modules from inside the scripts folder
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import AsyncSessionLocal
from core.models import Source

# ==========================================
# 1. THE STANDARDIZED SEED DATA
# ==========================================
SEED_TARGETS = [
    # ---------------------------------------------------------
    # TIER 1: Highly Active Tech Hubs (Robust Servers)
    # Fast download_delay (1s), broader depth to find events
    # ---------------------------------------------------------
    {
        "name": "Google Developer Groups Pakistan",
        "is_active": True,
        "tier": 1,
        "config_jsonb": {
            "allowed_domains": ["gdg.community.dev"],
            "max_depth": 3,
            "download_delay": 1, 
            "use_proxies": False,
            "title_selector": "h1.event-title::text",
            "content_selector": "div.event-description::text"
        }
    },
    {
        "name": "Devsinc Community Board",
        "is_active": True,
        "tier": 1,
        "config_jsonb": {
            "allowed_domains": ["devsinc.com"],
            "max_depth": 3,
            "download_delay": 1,
            "use_proxies": False,
            "title_selector": "h2.post-title::text",
            "content_selector": "div.post-content::text"
        }
    },

    # ---------------------------------------------------------
    # TIER 2: Primary Research Universities (Fragile Servers)
    # Slow download_delay (3-5s), shallow depth to avoid DDoS flags
    # ---------------------------------------------------------
    {
        "name": "NUST Events & Notices",
        "is_active": True,
        "tier": 2,
        "config_jsonb": {
            "allowed_domains": ["nust.edu.pk"],
            "max_depth": 2,
            "download_delay": 4, # Be polite to university servers
            "use_proxies": True, # Route through proxies to prevent IP bans
            "title_selector": "h3.notice-title::text",
            "content_selector": "div.notice-body p::text"
        }
    },
    {
        "name": "FAST-NUCES Islamabad Campus",
        "is_active": True,
        "tier": 2,
        "config_jsonb": {
            "allowed_domains": ["isb.nu.edu.pk"],
            "max_depth": 2,
            "download_delay": 5,
            "use_proxies": True,
            "title_selector": "h2.event-heading::text",
            "content_selector": "div.event-details::text"
        }
    },
    {
        "name": "LUMS Hackathon Portal",
        "is_active": True,
        "tier": 2,
        "config_jsonb": {
            "allowed_domains": ["lums.edu.pk"],
            "max_depth": 2,
            "download_delay": 3,
            "use_proxies": True,
            "title_selector": "h1.page-title::text",
            "content_selector": "div.content-area::text"
        }
    },

    # ---------------------------------------------------------
    # TIER 3: Static Informational Portals (Infrequent Updates)
    # Checked rarely, very precise targeting
    # ---------------------------------------------------------
    {
        "name": "Ignite Tech Fund Announcements",
        "is_active": True,
        "tier": 3,
        "config_jsonb": {
            "allowed_domains": ["ignite.org.pk"],
            "max_depth": 1,
            "download_delay": 2,
            "use_proxies": False,
            "title_selector": "h4.news-title::text",
            "content_selector": "p.news-excerpt::text"
        }
    }
    # Note: You can expand this list up to the full 15 universities and 10 tech hubs easily.
]

# ==========================================
# 2. THE INSERTION ENGINE
# ==========================================
async def seed_database():
    print("\n🌱 Starting Database Seeding Process...")
    
    async with AsyncSessionLocal() as session:
        added_count = 0
        skipped_count = 0
        
        for target in SEED_TARGETS:
            # Check if this specific target already exists in the registry
            query = select(Source).where(Source.name == target["name"])
            result = await session.execute(query)
            existing_source = result.scalar_one_or_none()
            
            if existing_source:
                skipped_count += 1
                print(f"⏩ Skipped: '{target['name']}' (Already exists)")
                continue
                
            # If it doesn't exist, build the ORM object and stage it
            new_source = Source(**target)
            session.add(new_source)
            added_count += 1
            print(f"✅ Added: '{target['name']}' (Tier {target['tier']})")
            
        # Commit all staged inserts to the database at once
        if added_count > 0:
            await session.commit()
            print(f"\n🎉 Seeding Complete! Inserted {added_count} new targets. (Skipped {skipped_count})")
        else:
            print(f"\n👍 Seeding Complete! Database is already up to date. (Skipped {skipped_count})")
        print("="*50 + "\n")

if __name__ == "__main__":
    asyncio.run(seed_database())