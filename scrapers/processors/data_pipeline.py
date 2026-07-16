import asyncio
import logging
from sqlalchemy import select
from core.database import AsyncSessionLocal
from core.models import ScrapedOpportunity
from core.llm_router import AIRouter

logger = logging.getLogger(__name__)

async def run_ai_extraction_loop():
    ai_router = AIRouter()
    
    async with AsyncSessionLocal() as session:
        # 1. Fetch records that have been OCR'd but not yet structured by the AI
        # (Assuming you add an 'ai_processed' boolean to your ScrapedOpportunity model)
        query = select(ScrapedOpportunity).where(
            ScrapedOpportunity.ocr_processed == True
            # ScrapedOpportunity.ai_processed == False  <-- Add this to your model!
        )
        result = await session.execute(query)
        ready_records = result.scalars().all()

        for record in ready_records:
            if not record.extracted_text:
                continue
                
            # 2. Pass the text to the patched LLM router
            structured_data = await ai_router.extract_structured_data(record.extracted_text)
            
            if structured_data:
                logger.info(f"✅ Successfully structured: {structured_data.title} ({structured_data.category})")
                
                # 3. Here is where you will INSERT the structured_data into your FINAL production table!
                # e.g., insert_into_final_table(structured_data)
                
                # 4. Mark the staging record as complete
                # record.ai_processed = True
            else:
                logger.warning(f"⚠️ Flagging record {record.platform_post_id} for MANUAL REVIEW.")
                # record.requires_manual_review = True
                
        await session.commit()

if __name__ == "__main__":
    asyncio.run(run_ai_extraction_loop())