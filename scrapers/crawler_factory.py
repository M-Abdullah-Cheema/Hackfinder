import subprocess
import os
import logging
from scrapers.base_playwright import HeadlessBrowserWrapper

logger = logging.getLogger(__name__)

class CrawlerFactory:
    """Dynamically routes jobs to the appropriate execution engine."""
    
    @staticmethod
    async def execute(source_id: int, config_jsonb: dict, start_url: str) -> str:
        crawler_type = config_jsonb.get("crawler_type", "scrapy")
        
        if crawler_type == "playwright":
            logger.info(f"🎭 Routing Source {source_id} to Playwright Engine")
            # Wait for specific JS element if defined, else just load DOM
            wait_selector = config_jsonb.get("content_selector")
            html_payload = await HeadlessBrowserWrapper.fetch_rendered_html(
                url=start_url, 
                wait_selector=wait_selector
            )
            if not html_payload:
                raise Exception("Playwright failed to return HTML payload.")
            return "Playwright Execution Successful"
            
        elif crawler_type == "scrapy":
            logger.info(f"🕷️ Routing Source {source_id} to Scrapy Engine")
            process = subprocess.run(
                ["poetry", "run", "scrapy", "crawl", "base_dynamic", "-a", f"source_id={source_id}"],
                cwd=os.path.dirname(os.path.abspath(__file__)),
                capture_output=True,
                text=True,
                check=True 
            )
            return "Scrapy Execution Successful"
            
        else:
            raise ValueError(f"Unknown crawler_type: {crawler_type}")