"""
Downloader middleware that injects proxies from ProxyPool into each request.
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class ProxyMiddleware:
    """Assigns a random working proxy to every request and handles retries."""

    def __init__(self) -> None:
        self.proxy_pool = None
        self.current_proxy: Optional[str] = None

    @classmethod
    def from_crawler(cls, crawler):
        instance = cls()
        enabled = crawler.settings.getbool("PROXY_ENABLED", True)
        if enabled:
            from core.proxy_pool import ProxyPool
            instance.proxy_pool = ProxyPool()
        else:
            logger.info("Proxy disabled (PROXY_ENABLED=False)")
        return instance

    def process_request(self, request, spider) -> None:
        if self.proxy_pool is None:
            return

        proxy_url = self.proxy_pool.get_proxy()
        if proxy_url:
            self.current_proxy = proxy_url
            request.meta["proxy"] = proxy_url
            logger.debug("Using proxy: %s", proxy_url)
        else:
            logger.warning("No proxy available, using direct connection")

    def process_exception(self, request, exception, spider):
        if self.proxy_pool is None:
            return None

        bad_proxy = request.meta.get("proxy")
        if bad_proxy:
            self.proxy_pool.mark_bad(bad_proxy)

        new_proxy = self.proxy_pool.get_proxy()
        if new_proxy:
            self.current_proxy = new_proxy
            logger.info("Switched proxy after failure: %s → %s", bad_proxy, new_proxy)
            # Preserve all existing meta and only overwrite the proxy key
            new_req = request.copy()
            new_req.meta["proxy"] = new_proxy
            return new_req

        logger.warning("No fallback proxy available after failure")
        return None
