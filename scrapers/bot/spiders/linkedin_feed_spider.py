import scrapy
import re
from datetime import datetime, timezone
from scrapers.bot.spiders.base_spider import BaseDynamicSpider

class LinkedInFeedSpider(BaseDynamicSpider):
    """
    Master Platform Spider for LinkedIn Company Pages, Groups, and Feeds.
    Dynamically captures posts, unique URN identifiers, and attached images.
    """
    name = "linkedin_feed"

    def parse(self, response):
        self.logger.info(f"📊 Parsing LinkedIn Feed Architecture for Target URL: {self.target_url}")

        # LinkedIn feed post containers (Common classes for updates/feed components)
        posts = response.xpath('//div[contains(@class, "feed-shared-update-v2")] | //article[contains(@class, "v-card")] | //div[@data-urn]')

        if not posts:
            self.logger.warning(f"⚠️ No LinkedIn post blocks identified on rendered DOM. Checking fallback main containers.")
            posts = response.css('div.update-components-actor, div.feed-shared-update-v2__control-menu')

        for post in posts:
            # 1. Extract the Immutable Platform Post ID (URN)
            # Looks for data-urn="urn:li:activity:1234567890" or parses it out of links
            urn = post.xpath('./@data-urn').get()
            if not urn:
                # Fallback: search for any URN pattern inside the post element html
                urn_match = re.search(r'urn:li:activity:\d+', post.get())
                if urn_match:
                    urn = urn_match.group(0)
                else:
                    # Absolute fallback: construct a deterministic hash based on URL and timestamp if no URN found
                    continue 

            # 2. Extract Post Text Content
            text_pieces = post.xpath('.//span[contains(@class, "break-words")]//text() | .//div[contains(@class, "update-v2__commentary")]//text()').getall()
            extracted_text = " ".join([t.strip() for t in text_pieces if t.strip()]).strip()

            # 3. Extract Flyer Image URLs for Downstream OCR
            image_urls = post.xpath('.//div[contains(@class, "update-v2__content")]//img/@src | .//img[contains(@class, "feed-shared-image__image")]/@src').getall()
            clean_image_urls = [url for url in image_urls if url and not url.startswith("data:")]

            # Yield data structured perfectly for your updated ScrapedOpportunity schema
            yield {
                "source_id": self.source_id,
                "platform_post_id": urn,
                "extracted_text": extracted_text,
                "image_urls": clean_image_urls,
                "scraped_at": datetime.now(timezone.utc)
            }