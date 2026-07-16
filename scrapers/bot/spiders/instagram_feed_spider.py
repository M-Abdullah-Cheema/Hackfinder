import scrapy
import json
import re
from datetime import datetime, timezone
from scrapers.bot.spiders.base_spider import BaseDynamicSpider

class InstagramFeedSpider(BaseDynamicSpider):
    """
    Master Platform Spider for Instagram Profile Timelines.
    Handles extraction of text captions, shortcodes, and sidecar media assets.
    """
    name = "instagram_feed"

    def parse(self, response):
        self.logger.info(f"📸 Parsing Instagram Feed Architecture for Target URL: {self.target_url}")

        # Strategy A: Check if the response is a direct JSON graph API injection
        try:
            json_data = json.loads(response.text)
            if "graphql" in json_data or "data" in json_data:
                yield from self.parse_json_graph(json_data)
                return
        except ValueError:
            pass # Not a pure JSON response, fallback to DOM extraction

        # Strategy B: DOM Extraction of rendered items (Playwright/ScraperAPI rendering)
        # Instagram posts typically group inside individual article structures or link grids
        articles = response.xpath('//article//a[contains(@href, "/p/")]')
        
        for article in articles:
            href = article.xpath('./@href').get()
            # Extract shortcode unique identifier from URL path (e.g., /p/C12345xyz/)
            shortcode_match = re.search(r'/p/([^/]+)/', href)
            if not shortcode_match:
                continue
                
            shortcode = shortcode_match.group(1)
            
            # Extract accessible image content descriptions and source paths
            img_src = article.xpath('.//img/@src').get()
            caption = article.xpath('.//img/@alt').get() or ""

            yield {
                "source_id": self.source_id,
                "platform_post_id": f"ig_{shortcode}",
                "extracted_text": caption.strip(),
                "image_urls": [img_src] if img_src else [],
                "scraped_at": datetime.now(timezone.utc)
            }

    def parse_json_graph(self, data):
        """Helper method to iterate through native Instagram API user timelines."""
        try:
            user_edges = data["data"]["user"]["edge_owner_to_timeline_media"]["edges"]
        except KeyError:
            self.logger.warning("⚠️ Could not trace GraphQL edge patterns in JSON response data.")
            return

        for edge in user_edges:
            node = edge["node"]
            shortcode = node.get("shortcode")
            
            # Gather captions
            caption_edges = node.get("edge_media_to_caption", {}).get("edges", [])
            extracted_text = caption_edges[0]["node"]["text"] if caption_edges else ""
            
            # Handle multiple images (Carousel/Sidecar children) vs single images
            image_urls = []
            if "edge_sidecar_to_children" in node:
                child_edges = node["edge_sidecar_to_children"].get("edges", [])
                for child in child_edges:
                    display_url = child["node"].get("display_url")
                    if display_url:
                        image_urls.append(display_url)
            else:
                display_url = node.get("display_url")
                if display_url:
                    image_urls.append(display_url)

            yield {
                "source_id": self.source_id,
                "platform_post_id": f"ig_{shortcode}",
                "extracted_text": extracted_text.strip(),
                "image_urls": image_urls,
                "scraped_at": datetime.now(timezone.utc)
            }