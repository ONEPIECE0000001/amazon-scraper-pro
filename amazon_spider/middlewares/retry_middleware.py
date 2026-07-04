"""
Enhanced retry middleware — exponential backoff with real Twisted deferred delay,
anti-bot detection, proxy rotation, and User-Agent cycling.
"""
import logging
import random

from twisted.internet import reactor
from twisted.internet.defer import Deferred

import scrapy

logger = logging.getLogger(__name__)

ANTI_BOT_KEYWORDS = [
    'captcha',
    'robot check',
    'unusual traffic',
    'automated access',
    'enter the characters',
]


class ExponentialRetryMiddleware:

    USER_AGENTS = [
        # Chrome 120-130, Windows
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36',
        # Chrome 120-130, Mac
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
        # Edge
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36 Edg/129.0.0.0',
        # Firefox
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:132.0) Gecko/20100101 Firefox/132.0',
    ]

    def __init__(self, proxy_enabled: bool = True):
        self.proxy_enabled = proxy_enabled
        self.proxy_pool = None
        if proxy_enabled:
            from core.proxy_pool import ProxyPool
            self.proxy_pool = ProxyPool()

    @classmethod
    def from_crawler(cls, crawler):
        proxy_enabled = crawler.settings.getbool('PROXY_ENABLED', False)
        return cls(proxy_enabled=proxy_enabled)

    def process_response(self, request, response, spider):
        if response.status == 503:
            return self._retry(request, response, spider)

        body = response.text
        if body:
            body_lower = body.lower()
            for kw in ANTI_BOT_KEYWORDS:
                if kw in body_lower:
                    return self._retry(request, response, spider)

        return response

    def _retry(self, request, response, spider):
        retry_count = request.meta.get('retry_count', 0)

        if retry_count >= 3:
            spider.logger.error(
                "Max retries (%d) reached for %s — creating fresh request",
                retry_count, request.url,
            )
            # Create a brand-new request instead of returning the anti-bot page.
            # This prevents captcha/503 HTML from flowing into the item pipeline.
            new_req = scrapy.Request(
                url=request.url,
                callback=request.callback,
                errback=request.errback,
                meta=dict(request.meta),
                headers=dict(request.headers) if request.headers else {},
                dont_filter=True,
            )
            new_req.meta['retry_count'] = 0
            return new_req

        delay = 2 ** retry_count

        spider.logger.info(
            "Retry %s/3 for %s, waiting %ss",
            retry_count + 1, request.url, delay,
        )

        if self.proxy_pool is not None:
            current_proxy = request.meta.get('proxy')
            if current_proxy:
                self.proxy_pool.mark_bad(current_proxy)
            new_proxy = self.proxy_pool.get_proxy()
            if new_proxy:
                request.meta['proxy'] = new_proxy

        request.headers['User-Agent'] = random.choice(self.USER_AGENTS)
        request.meta['retry_count'] = retry_count + 1

        # Real exponential backoff via Twisted deferred — Scrapy's downloader
        # middleware natively supports returning a Deferred from process_response.
        deferred = Deferred()
        reactor.callLater(delay, deferred.callback, request.copy())
        return deferred
