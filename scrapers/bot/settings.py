# Scrapy settings for bot project
#
# For simplicity, this file contains only settings considered important or
# commonly used. You can find more settings consulting the documentation:
#
#     https://docs.scrapy.org/en/latest/topics/settings.html
#     https://docs.scrapy.org/en/latest/topics/downloader-middleware.html
#     https://docs.scrapy.org/en/latest/topics/spider-middleware.html

BOT_NAME = "bot"

SPIDER_MODULES = ["bot.spiders"]
NEWSPIDER_MODULE = "bot.spiders"

ADDONS = {}

# Obey robots.txt rules
ROBOTSTXT_OBEY = True

# Set settings whose default value is deprecated to a future-proof value
FEED_EXPORT_ENCODING = "utf-8"

# ==========================================
# ASYNC & DATABASE CONFIGURATION
# ==========================================
# Enable Asyncio capabilities for our Database and Playwright wrappers
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"

ITEM_PIPELINES = {
   "bot.pipelines.DatabasePipeline": 300,
}

# ==========================================
# NETWORK RESILIENCE & POLITENESS SETTINGS
# ==========================================
# 1. Be Polite: Wait 2 seconds between every request to the same website
DOWNLOAD_DELAY = 2.0

# 2. Concurrency: Don't hammer the server with simultaneous requests
CONCURRENT_REQUESTS_PER_DOMAIN = 2

# 3. Tell Scrapy which error codes mean we got caught or the server is dying
RETRY_HTTP_CODES = [403, 429, 500, 502, 503, 504]
RETRY_TIMES = 5 # Try 5 different proxies before completely giving up on a page

# 4. Turn off Scrapy's default, outdated User-Agent
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# ==========================================
# CUSTOM MIDDLEWARE STACK
# ==========================================
# 5. Activate our custom defensive middlewares
DOWNLOADER_MIDDLEWARES = {
    'scrapy.downloadermiddlewares.useragent.UserAgentMiddleware': None, # Disable built-in UA middleware
    'scrapy.downloadermiddlewares.retry.RetryMiddleware': None,        # Disable built-in retry middleware
    
    # Randomizes the browser fingerprint
    'bot.middlewares.RotateUserAgentMiddleware': 400,
    
    # 🚨 THE SOCIAL GATEWAY: Intercepts social media requests and forces premium residential proxies
    'bot.middlewares.SocialProxyRotatorMiddleware': 405,
    
    # Standard proxy rotator for your institutional/university scraping tasks
    'bot.middlewares.ProxyRotatorMiddleware': 410,                      
    
    # Re-routes traffic and drops burned proxies on 403/429 bans
    'bot.middlewares.SmartRetryMiddleware': 550,
}