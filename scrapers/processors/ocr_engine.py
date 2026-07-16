import asyncio
import logging
import pytesseract
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

# Import your database session and models
from core.database import AsyncSessionLocal
from core.models import ScrapedOpportunity
from scrapers.processors.image_fetcher import ImageProcessor

logger = logging.getLogger(__name__)

# NOTE: If you are on Windows, you MUST tell pytesseract where the .exe is located.
# Uncomment and update the line below if you get a "tesseract is not installed" error:
# pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

class OCREngine:
    """Coordinates the retrieval of unprocessed staging rows, image extraction, and database updating."""

    @staticmethod
    async def process_pending_opportunities():
        logger.info("🔍 Scanning database for pending OCR tasks...")
        
        async with AsyncSessionLocal() as session:
            # 1. Fetch rows that have image URLs but haven't been processed yet
            query = select(ScrapedOpportunity).where(
                ScrapedOpportunity.ocr_processed == False,
                # PostgreSQL specific check to ensure the array is not empty
                ScrapedOpportunity.image_urls != [] 
            )
            result = await session.execute(query)
            pending_records = result.scalars().all()

            if not pending_records:
                logger.info("✅ No pending flyers to process. System is caught up.")
                return

            for record in pending_records:
                logger.info(f"⚙️ Running OCR for platform post: {record.platform_post_id}")
                
                extracted_text_blocks = []

                # 2. Loop through all flyer images attached to this single post
                for img_url in record.image_urls:
                    processed_image = await ImageProcessor.fetch_and_preprocess(img_url)
                    
                    if processed_image:
                        # 3. Execute text extraction on the sanitized in-memory image
                        # psm 3 is the default page segmentation mode (fully automated)
                        raw_text = pytesseract.image_to_string(processed_image, config='--psm 3')
                        
                        # Clean up erratic newlines and whitespace from the OCR engine
                        clean_text = " ".join(raw_text.split()).strip()
                        if clean_text:
                            extracted_text_blocks.append(clean_text)

                # 4. Aggregation & Commit
                if extracted_text_blocks:
                    combined_flyer_text = "\n".join(extracted_text_blocks)
                    
                    # Ensure we don't append to a NoneType caption
                    existing_caption = record.extracted_text or ""
                    
                    # Append using the strict separator
                    updated_text = f"{existing_caption}\n\n--- FLYER TEXT EXTRACT ---\n{combined_flyer_text}"
                    
                    record.extracted_text = updated_text

                # 5. Mark as processed regardless of whether text was found (so we don't infinitely retry blank images)
                record.ocr_processed = True
                
            # Commit all the updated rows to PostgreSQL
            await session.commit()
            logger.info(f"🎉 Successfully processed {len(pending_records)} staging records.")

# To run this script independently:
if __name__ == "__main__":
    asyncio.run(OCREngine.process_pending_opportunities())