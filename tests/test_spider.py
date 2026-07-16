import os
import sys
import scrapy
from scrapy.http import TextResponse

# Ensure Python can find your Scrapy project
sys.path.append(os.path.join(os.path.dirname(__file__), '../scrapers'))
from bot.spiders.devpost_spider import DevpostSpider

def test_spider_extraction_logic():
    # 1. Setup the Spider
    spider = DevpostSpider()
    
    # 2. Load our fake, static snapshot from Phase 2
    fixture_path = os.path.join(os.path.dirname(__file__), 'fixtures', 'sample.json')
    with open(fixture_path, 'r') as f:
        mock_body = f.read()

    # 3. Create a fake Scrapy response (No internet required!)
    request = scrapy.Request(url="https://dummyjson.com/posts")
    response = TextResponse(
        url="https://dummyjson.com/posts", 
        request=request, 
        body=mock_body, 
        encoding='utf-8'
    )

    # 4. Push the fake response into your spider
    # spider.parse() yields a generator, so we convert it to a list to check the results
    extracted_items = list(spider.parse(response))

    # 5. THE ASSERTIONS (If any of these fail, the test fails)
    assert len(extracted_items) == 1, "Spider should have extracted exactly 1 item."
    assert extracted_items[0]['title'] == "Hackathon Winning Project", "Spider failed to find the title!"
    assert extracted_items[0]['url'] == "https://dummyjson.com/posts/999", "Spider built the wrong URL!"