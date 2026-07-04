"""
curl_cffi downloader middleware for Scrapy.

Replaces the default HTTP download handler with curl_cffi, which impersonates
real browser TLS fingerprints (JA3/JA4).  Amazon's WAF inspects TLS handshake
characteristics *before* headers are parsed — a vanilla Python requests/Scrapy
fingerprint is a dead giveaway.

This middleware intercepts every request, fetches it via curl_cffi with a
Chrome 130 impersonation profile, and returns a standard Scrapy HtmlResponse.
"""

import logging
from typing import Optional

from curl_cffi import requests as curl_requests
from scrapy import signals
from scrapy.http import HtmlResponse

logger = logging.getLogger(__name__)


class CurlCffiDownloaderMiddleware:
    """Use curl_cffi to fetch pages with TLS fingerprint impersonation."""

    # Browser profile to impersonate — matches the User-Agent we send
    IMPERSONATE = "chrome131"

    # curl_cffi session (lazy-init per spider)
    _session: Optional[curl_requests.Session] = None

    @classmethod
    def from_crawler(cls, crawler):
        mw = cls()
        crawler.signals.connect(mw.spider_opened, signals.spider_opened)
        crawler.signals.connect(mw.spider_closed, signals.spider_closed)
        return mw

    def spider_opened(self, spider):
        self._session = curl_requests.Session()
        logger.info("curl_cffi session created (impersonate=%s)", self.IMPERSONATE)

    def spider_closed(self, spider):
        if self._session:
            self._session.close()
            self._session = None

    def _extract_proxy(self, request) -> Optional[dict]:
        """Extract proxy URL from request meta (set by ProxyMiddleware)."""
        proxy = request.meta.get("proxy")
        if proxy:
            # Scrapy sets proxy as URL string; curl_cffi wants a dict
            return {"http": proxy, "https": proxy}
        return None

    def process_request(self, request, spider):
        """
        Intercept Amazon requests and fetch via curl_cffi.

        Non-Amazon URLs pass through to the default download handler.
        Returns a Scrapy Response for Amazon requests.
        """
        # Only handle Amazon requests — let everything else pass through
        if "amazon.com" not in request.url and "amazon." not in request.url:
            return None  # let default download handler process it

        url = request.url
        method = request.method

        # ---- build headers (bytes → str) ----
        headers = {}
        for k, v in (request.headers or {}).items():
            key = k.decode() if isinstance(k, bytes) else k
            val = v[0].decode() if isinstance(v, (list, tuple)) else v
            if isinstance(val, bytes):
                val = val.decode()
            headers[key] = val

        # Ensure Accept-Encoding is set so curl_cffi can handle decompression
        headers.setdefault("Accept-Encoding", "gzip, deflate, br")

        # ---- proxy extraction ----
        proxies = self._extract_proxy(request)

        # ---- make the request ----
        try:
            resp = self._session.request(
                method=method,
                url=url,
                headers=headers,
                proxies=proxies,
                impersonate=self.IMPERSONATE,
                timeout=30,
                allow_redirects=True,
                verify=True,  # SSL verification
            )
        except Exception as exc:
            logger.error("curl_cffi request failed: %s — %s", url, exc)
            # Let Scrapy's retry middleware handle it
            from twisted.internet.error import ConnectionRefusedError
            raise ConnectionRefusedError from exc

        # ---- convert to Scrapy Response ----
        # curl_cffi already decompressed — strip Content-Encoding to prevent
        # Scrapy's HttpCompressionMiddleware from double-decompressing
        resp_headers = {
            k: v for k, v in (resp.headers or {}).items()
            if k.lower() != "content-encoding"
        }

        return HtmlResponse(
            url=str(resp.url),  # final URL after redirects
            status=resp.status_code,
            headers={
                k.encode(): [str(v[0] if isinstance(v, list) else v).encode()]
                for k, v in resp_headers.items()
            },
            body=resp.content,
            request=request,
            encoding=resp.encoding or "utf-8",
        )
