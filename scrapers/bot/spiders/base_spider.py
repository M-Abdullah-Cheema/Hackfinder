import scrapy
import urllib.parse
from abc import ABC, abstractmethod

class BaseDynamicSpider(scrapy.Spider, ABC):
    """
    Abstract Base Spider designed to intercept social media requests 
    and route them through upstream anti-bot bypass APIs.
    """
    name = "base_dynamic_spider"

    def __init__(self, source_id: int, target_url: str, config_jsonb: dict, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.source_id = source_id
        self.target_url = target_url
        self.config_jsonb = config_jsonb
        
        # Extract configurations with fallback options
        self.platform_type = config_jsonb.get("platform_type", "static_web")
        self.proxy_required = config_jsonb.get("proxy_required", True)
        
        # Upstream API configurations (Set these in your environment variables)
        self.scraper_api_key = "YOUR_SCRAPING_API_KEY" 
        self.scraper_api_url = "https://api.scraperapi.com/"

    def start_requests(self):
        """Routes targets dynamically based on platform type."""
        if self.platform_type in ["linkedin", "instagram"]:
            self.logger.info(f"🚀 Routing social feed via upstream bypass API: {self.target_url}")
            
            # Construct the upstream API proxy gateway payload
            payload = {
                "api_key": self.scraper_api_key,
                "url": self.target_url,
                "render": "true",           # Force JavaScript rendering for heavy SPAs
                "country_code": "us"        # Geotarget high-reputation nodes
            }
            proxy_gateway_url = f"{self.scraper_api_url}?{urllib.parse.urlencode(payload)}"
            
            yield scrapy.Request(
                url=proxy_gateway_url, 
                callback=self.parse,
                meta={"original_target_url": self.target_url}
            )
        else:
            self.logger.info(f"🌐 Initiating direct connection to institutional portal: {self.target_url}")
            yield scrapy.Request(url=self.target_url, callback=self.parse)

    @abstractmethod
    def parse(self, response):
        """Must be implemented by concrete university or platform subclasses."""
        pass