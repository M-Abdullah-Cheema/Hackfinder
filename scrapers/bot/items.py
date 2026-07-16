# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy
from datetime import datetime, timezone

class TargetScrapedItem(scrapy.Item):
    """The immutable data contract for all downstream scraped data."""
    
    # Traceability: Which database target did this come from?
    source_id = scrapy.Field()
    
    # Location and Raw Data
    url = scrapy.Field()
    raw_html = scrapy.Field()
    extracted_text = scrapy.Field()
    
    # Timestamping
    scraped_at = scrapy.Field()