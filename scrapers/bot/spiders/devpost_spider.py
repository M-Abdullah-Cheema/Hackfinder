import scrapy
import json

class DevpostSpider(scrapy.Spider):
    name = "devpost" 
    
    # For this test, we are hitting a public dummy API that returns perfect JSON data
    start_urls = ["https://dummyjson.com/posts"]

    def parse(self, response):
        self.logger.info("🎯 Successfully hit the JSON API!")

        # 1. Convert the raw JSON response into a Python dictionary
        data = json.loads(response.text)

        # 2. Loop through the list of items (this API stores them under the 'posts' key)
        for item in data.get('posts', []):
            
            # 3. Extract exactly what we need using standard Python dictionary lookups
            title = item.get('title')
            
            # We'll construct a fake URL just so our database 'url' column doesn't crash
            url = f"https://dummyjson.com/posts/{item.get('id')}"
            
            content = item.get('body')

            # 4. Yield it to the Database Pipeline!
            yield {
                "title": title,
                "url": url,
                "raw_content": content
            }