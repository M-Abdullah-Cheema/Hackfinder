import random
import sys
import os
import logging
from scrapy.downloadermiddlewares.retry import RetryMiddleware
from scrapy.utils.response import response_status_message

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.proxy_rotation import pick_user_agent, scrapy_proxy_meta

logger = logging.getLogger(__name__)


class RotateUserAgentMiddleware:
    """Randomly selects a modern browser User-Agent for every single request."""

    def process_request(self, request, spider):
        request.headers["User-Agent"] = pick_user_agent()


class SocialProxyRotatorMiddleware:
    """
    Routes social targets through configured residential / ScraperAPI proxies.
    No-ops (direct connect) when PROXY_SERVER / PROXY_API_KEY are unset.
    """

    def process_request(self, request, spider):
        platform_type = getattr(spider, "platform_type", "static_web")
        is_social = (
            platform_type in ["linkedin", "instagram"]
            or "linkedin.com" in request.url
            or "instagram.com" in request.url
        )
        if not is_social and not getattr(spider, "proxy_required", False):
            return

        meta = scrapy_proxy_meta(force_social=is_social)
        if not meta:
            return

        if "proxy" in meta:
            request.meta["proxy"] = meta["proxy"]
            spider.logger.info(
                "Social/proxy target (%s) → proxy gateway enabled", request.url
            )
        auth = meta.get("proxy_auth_header")
        if auth:
            request.headers["Proxy-Authorization"] = auth


class SmartRetryMiddleware(RetryMiddleware):
    """Catches bans and forces an IP swap before retrying."""

    def process_response(self, request, response, spider):
        if request.meta.get("dont_retry", False):
            return response

        if response.status in [403, 429]:
            spider.logger.warning(
                "Caught a %s ban! Stripping proxy and retrying...", response.status
            )
            if "proxy" in request.meta:
                del request.meta["proxy"]

            reason = response_status_message(response.status)
            return self._retry(request, reason) or response

        if response.status in self.retry_http_codes:
            reason = response_status_message(response.status)
            return self._retry(request, reason) or response

        return response

    def process_exception(self, request, exception, spider):
        spider.logger.warning("Connection error: %s. Swapping proxy...", exception)
        if "proxy" in request.meta:
            del request.meta["proxy"]
        return self._retry(request, exception)
