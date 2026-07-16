import os
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.postgresql import insert
from core.database import engine_factory  # Replace with your actual project database connection engine
from core.models import ScrapedItem, ScrapedOpportunity, Source
from bot.text_cleaner import SocialMediaSanitizer

class DatabasePipeline:
    """
    Unified ingestion pipeline that sanitizes content and route payloads 
    to legacy web tables or new social opportunity tables.
    """

    def __init__(self):
        # Bind your database engine (ensure your project's engine configuration is imported here)
        self.Session = sessionmaker(bind=engine_factory)

    def process_item(self, item, spider):
        session = self.Session()
        try:
            # --- ROUTING CONDITION: If it contains a post ID, treat it as a social opportunity ---
            if "platform_post_id" in item:
                spider.logger.info(f"💾 Processing pipeline routing for social post: {item['platform_post_id']}")

                # 1. Sanitize the post text content
                cleaned_caption = SocialMediaSanitizer.clean_text(item.get("extracted_text", ""))

                # 2. OCR Dispatch Condition: If images exist, fetch the execution flags from the source target
                ocr_text = ""
                image_list = item.get("image_urls", [])
                
                if image_list:
                    # Look up runtime parameters configured in Phase 2
                    source_record = session.query(Source).filter(Source.id == item["source_id"]).first()
                    should_ocr = source_record.config_jsonb.get("extract_images_for_ocr", False) if source_record else False

                    if should_ocr:
                        spider.logger.info(f"📸 Images detected and OCR flag enabled. Running extraction loop...")
                        ocr_text = self.execute_vision_ocr(image_list, spider)

                # 3. Combine captions and extracted text blocks together
                final_text = cleaned_caption
                if ocr_text:
                    final_text += f"\n\n--- [EXTRACTED FROM ATTACHED IMAGE FLYER] ---\n{ocr_text}"

                # 4. Upsert operation to prevent duplicate keys if a feed post is scraped multiple times
                stmt = insert(ScrapedOpportunity).values(
                    source_id=item["source_id"],
                    platform_post_id=item["platform_post_id"],
                    extracted_text=final_text,
                    image_urls=image_list,
                    scraped_at=item["scraped_at"]
                )
                # If post ID already exists, overwrite the text content and updated image arrays
                stmt = stmt.on_conflict_do_update(
                    index_elements=["platform_post_id"],
                    set_={
                        "extracted_text": stmt.excluded.extracted_text,
                        "image_urls": stmt.excluded.image_urls,
                        "scraped_at": stmt.excluded.scraped_at
                    }
                )
                session.execute(stmt)
                session.commit()

            # --- LEGACY FALLBACK: Traditional University Website Scraping ---
            else:
                spider.logger.info(f"🌐 Processing legacy web crawling data pipeline for: {item.get('url')}")
                stmt = insert(ScrapedItem).values(
                    url=item["url"],
                    title=item.get("title"),
                    raw_content=item.get("raw_content"),
                    scraped_at=item["scraped_at"]
                ).on_conflict_do_nothing(index_elements=["url"])
                session.execute(stmt)
                session.commit()

        except Exception as e:
            session.rollback()
            spider.logger.error(f"❌ Pipeline database runtime failure: {str(e)}")
            raise e
        finally:
            session.close()

        return item

    def execute_vision_ocr(self, image_urls: list, spider) -> str:
        """
        Integration bridge connecting downloaded image pipelines with the Phase 2
        Vision/OCR fallback script.
        """
        extracted_text_blocks = []
        
        # This is where your existing engine or an external service (like Google Vision / EasyOCR) hooks in
        for url in image_urls:
            try:
                spider.logger.info(f"👁️ Sending image URL to Vision processor: {url}")
                # Mock or hook your existing pdf_extractor / image reader function here:
                # result = YourVisionEngine.extract_text_from_url(url)
                # extracted_text_blocks.append(result)
                pass 
            except Exception as ocr_err:
                spider.logger.error(f"⚠️ OCR engine skipped asset {url}: {str(ocr_err)}")
                
        return "\n".join(extracted_text_blocks)