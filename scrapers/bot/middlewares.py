import random
import sys
import os
import base64
import logging
from scrapy.exceptions import NotConfigured
from scrapy.downloadermiddlewares.retry import RetryMiddleware
from scrapy.utils.response import response_status_message

# Ensure we can read our .env file from the core folder
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from core.config import settings

class RotateUserAgentMiddleware:
    """Randomly selects a modern browser User-Agent for every single request."""
    
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/119.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15"
    ]

    def process_request(self, request, spider):
        agent = random.choice(self.USER_AGENTS)
        request.headers["User-Agent"] = agent



class SocialProxyRotatorMiddleware:
    """
    Middleware that blocks cheap datacenter proxy servers 
    and forces premium Residential/Mobile proxy nodes for social targets.
    """

    def __init__(self):
        # Configure endpoints for your premium residential provider (e.g., Bright Data, Oxylabs, Smartproxy)
        self.residential_proxy = "http://pr.oxylabs.io:7777"
        self.proxy_username = "your_residential_username"
        self.proxy_password = "your_residential_password"

    def process_request(self, request, spider):
        """
        Intercepts incoming network requests. If the target matches a social platform, 
        strips legacy routing and hooks up premium credentials.
        """
        # Determine target profile based on the running spider config parameters
        platform_type = getattr(spider, "platform_type", "static_web")
        
        if platform_type in ["linkedin", "instagram"] or "linkedin.com" in request.url or "instagram.com" in request.url:
            spider.logger.info(f"🛡️ Social target detected ({request.url}). Routing through Premium Residential Proxy Gateway.")
            
            # Inject the high-tier residential proxy server string into request metadata
            request.meta["proxy"] = self.residential_proxy
            
            # Formulate proxy HTTP Basic Authentication headers
            auth_bytes = f"{self.proxy_username}:{self.proxy_password}".encode("utf-8")
            auth_header = b"Basic " + base64.b64encode(auth_bytes)
            request.headers["Proxy-Authorization"] = auth_header

class SmartRetryMiddleware(RetryMiddleware):
    """Catches bans and forces an IP swap before retrying."""

    def process_response(self, request, response, spider):
        if request.meta.get('dont_retry', False):
            return response

        if response.status in [403, 429]:
            spider.logger.warning(f"🚨 Caught a {response.status} ban! Stripping proxy and retrying...")
            if 'proxy' in request.meta:
                del request.meta['proxy']
                
            reason = response_status_message(response.status)
            # Removed the 'spider' argument for Scrapy 2.16 compatibility
            return self._retry(request, reason) or response

        if response.status in self.retry_http_codes:
            reason = response_status_message(response.status)
            return self._retry(request, reason) or response

        return response
        
    def process_exception(self, request, exception, spider):
        spider.logger.warning(f"🔌 Connection error: {exception}. Swapping proxy...")
        if 'proxy' in request.meta:
            del request.meta['proxy']
            
        # Removed the 'spider' argument for Scrapy 2.16 compatibility
        return self._retry(request, exception)