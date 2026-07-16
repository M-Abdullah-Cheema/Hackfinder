"""
Quick seed script — inserts sample FinalOpportunity rows directly into Supabase
so the frontend has data to display immediately, without needing the full
Playwright → OCR → AI → Celery pipeline to run first.

Run with:
    python scripts/seed_opportunities.py
"""
import asyncio
import os
import sys

# Ensure the project root is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import select
from core.database import AsyncSessionLocal
from core.models import FinalOpportunity

SAMPLE_OPPORTUNITIES = [
    {
        "title": "GDG Cloud Islamabad DevFest 2025",
        "organization_name": "GDG Cloud Islamabad",
        "category": "Workshop",
        "registration_url": "https://gdg.community.dev/gdg-cloud-islamabad/",
        "platform_post_id": "ig_seed_gdg_devfest_2025",
    },
    {
        "title": "Google Solution Challenge 2025",
        "organization_name": "Google Developers ISB",
        "category": "Hackathon",
        "registration_url": "https://developers.google.com/community/gdsc-solution-challenge",
        "platform_post_id": "ig_seed_gdsc_solution_challenge",
    },
    {
        "title": "AWS Cloud Practitioner Bootcamp",
        "organization_name": "AWS SBG NUST",
        "category": "Workshop",
        "registration_url": None,
        "platform_post_id": "ig_seed_aws_bootcamp_nust",
    },
    {
        "title": "UI/UX Design Sprint — Creative Thinking Workshop",
        "organization_name": "Inside Imagine Art",
        "category": "Workshop",
        "registration_url": "https://www.instagram.com/insideimagineart/",
        "platform_post_id": "ig_seed_imagine_art_uiux",
    },
    {
        "title": "Change Mechanics Social Innovation Fellowship",
        "organization_name": "Change Mechanics",
        "category": "Internship",
        "registration_url": "https://www.changemechanics.org/",
        "platform_post_id": "ig_seed_change_mechanics_fellowship",
    },
    {
        "title": "NUST Entrepreneurship Summit Hackathon",
        "organization_name": "GDG Cloud Islamabad",
        "category": "Hackathon",
        "registration_url": None,
        "platform_post_id": "ig_seed_nust_summit_hackathon",
    },
    {
        "title": "Google Cloud GenAI Hackathon 2025",
        "organization_name": "Google Developers ISB",
        "category": "Hackathon",
        "registration_url": "https://cloud.google.com/",
        "platform_post_id": "ig_seed_genai_hackathon",
    },
    {
        "title": "AWS Machine Learning Community Day",
        "organization_name": "AWS SBG NUST",
        "category": "Workshop",
        "registration_url": None,
        "platform_post_id": "ig_seed_aws_ml_day",
    },
    {
        "title": "Digital Art & Motion Graphics Masterclass",
        "organization_name": "Inside Imagine Art",
        "category": "Workshop",
        "registration_url": "https://www.instagram.com/insideimagineart/",
        "platform_post_id": "ig_seed_imagine_art_motion",
    },
    {
        "title": "Full Stack Web Development Internship — Summer 2025",
        "organization_name": "Google Developers ISB",
        "category": "Internship",
        "registration_url": "https://developers.google.com/",
        "platform_post_id": "ig_seed_fullstack_intern",
    },
    {
        "title": "FAST NUCES Coding Competition",
        "organization_name": "GDG Cloud Islamabad",
        "category": "Hackathon",
        "registration_url": None,
        "platform_post_id": "ig_seed_fast_coding_comp",
    },
    {
        "title": "HEC Need-Based Scholarship 2025",
        "organization_name": "Change Mechanics",
        "category": "Scholarship",
        "registration_url": "https://hec.gov.pk/",
        "platform_post_id": "ig_seed_hec_scholarship",
    },
]


async def seed():
    print("[*] Seeding FinalOpportunity table...\n")
    inserted = 0
    skipped = 0

    async with AsyncSessionLocal() as session:
        for item in SAMPLE_OPPORTUNITIES:
            existing = await session.execute(
                select(FinalOpportunity).where(
                    FinalOpportunity.platform_post_id == item["platform_post_id"]
                )
            )
            if existing.scalars().first():
                print(f"  [skip] Already exists: {item['title']}")
                skipped += 1
                continue

            opp = FinalOpportunity(
                title=item["title"],
                organization_name=item["organization_name"],
                category=item["category"],
                registration_url=item.get("registration_url"),
                platform_post_id=item["platform_post_id"],
                embedding=None,  # No vector needed for display
            )
            session.add(opp)
            print(f"  [+] [{item['category']}] {item['title']}")
            inserted += 1

        await session.commit()

    print(f"\n[DONE] Inserted {inserted} records, skipped {skipped} duplicates.")
    print("   Open http://localhost:3000 to see your website populated with data.")


if __name__ == "__main__":
    asyncio.run(seed())
