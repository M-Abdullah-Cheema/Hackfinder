import scrapy
from abc import ABC, abstractmethod

from core.proxy_rotation import wrap_url_via_scraperapi


class BaseDynamicSpider(scrapy.Spider, ABC):
    """
    Abstract Base Spider designed to intercept social media requests
    and route them through upstream anti-bot bypass APIs when configured.
    """

    name = "base_dynamic_spider"

    def __init__(self, source_id: int, target_url: str, config_jsonb: dict, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.source_id = source_id
        self.target_url = target_url
        self.config_jsonb = config_jsonb

        self.platform_type = config_jsonb.get("platform_type", "static_web")
        self.proxy_required = config_jsonb.get("proxy_required", True)

    def start_requests(self):
        """Routes targets dynamically based on platform type."""
        if self.platform_type in ["linkedin", "instagram"]:
            gateway = wrap_url_via_scraperapi(self.target_url, render=True)
            if gateway:
                self.logger.info(
                    "Routing social feed via ScraperAPI gateway: %s", self.target_url
                )
                yield scrapy.Request(
                    url=gateway,
                    callback=self.parse,
                    meta={"original_target_url": self.target_url},
                )
                return

            self.logger.warning(
                "No PROXY_API_KEY set — scraping social URL directly: %s",
                self.target_url,
            )

        self.logger.info("Initiating connection to: %s", self.target_url)
        yield scrapy.Request(url=self.target_url, callback=self.parse)

    @abstractmethod
    def parse(self, response):
        """Must be implemented by concrete university or platform subclasses."""
        pass
