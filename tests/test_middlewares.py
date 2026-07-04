"""
Unit tests for Spider middlewares.

Run with:  pytest tests/test_middlewares.py -v
"""

import sys
from unittest.mock import MagicMock, patch

import pytest
from scrapy.http import HtmlResponse, Request

sys.path.insert(0, "..")

from amazon_spider.middlewares.retry_middleware import ExponentialRetryMiddleware
from amazon_spider.middlewares.proxy_middleware import ProxyMiddleware


# ---------------------------------------------------------------------------
# ProxyMiddleware
# ---------------------------------------------------------------------------

class TestProxyMiddleware:
    @pytest.fixture
    def spider(self):
        return MagicMock()

    def test_skips_when_pool_disabled(self, spider):
        mw = ProxyMiddleware()
        mw.proxy_pool = None
        request = Request(url="https://www.amazon.com/s?k=laptop")
        mw.process_request(request, spider)
        assert "proxy" not in request.meta

    def test_injects_proxy_when_available(self, spider):
        mock_pool = MagicMock()
        mock_pool.get_proxy.return_value = "http://proxy1:8080"
        mw = ProxyMiddleware()
        mw.proxy_pool = mock_pool
        request = Request(url="https://www.amazon.com/s?k=laptop")
        mw.process_request(request, spider)
        assert request.meta["proxy"] == "http://proxy1:8080"
        assert mw.current_proxy == "http://proxy1:8080"

    def test_uses_direct_when_no_proxy_available(self, spider):
        mock_pool = MagicMock()
        mock_pool.get_proxy.return_value = None
        mw = ProxyMiddleware()
        mw.proxy_pool = mock_pool
        request = Request(url="https://www.amazon.com/s?k=laptop")
        mw.process_request(request, spider)
        assert "proxy" not in request.meta

    def test_process_exception_marks_bad_and_switches(self, spider):
        mock_pool = MagicMock()
        mock_pool.get_proxy.return_value = "http://new-proxy:8080"
        mw = ProxyMiddleware()
        mw.proxy_pool = mock_pool
        request = Request(
            url="https://www.amazon.com/s?k=laptop",
            meta={"proxy": "http://bad-proxy:8080"},
        )
        result = mw.process_exception(request, Exception("timeout"), spider)
        mock_pool.mark_bad.assert_called_once_with("http://bad-proxy:8080")
        assert result is not None
        assert result.meta["proxy"] == "http://new-proxy:8080"

    def test_process_exception_skips_when_no_pool(self, spider):
        mw = ProxyMiddleware()
        mw.proxy_pool = None
        request = Request(url="https://www.amazon.com/s?k=laptop")
        result = mw.process_exception(request, Exception("timeout"), spider)
        assert result is None

    def test_process_exception_no_fallback_proxy(self, spider):
        mock_pool = MagicMock()
        mock_pool.get_proxy.return_value = None
        mw = ProxyMiddleware()
        mw.proxy_pool = mock_pool
        request = Request(
            url="https://www.amazon.com/s?k=laptop",
            meta={"proxy": "http://bad-proxy:8080"},
        )
        result = mw.process_exception(request, Exception("timeout"), spider)
        mock_pool.mark_bad.assert_called_once()
        assert result is None


# ---------------------------------------------------------------------------
# ExponentialRetryMiddleware
# ---------------------------------------------------------------------------

class TestExponentialRetryMiddleware:
    @pytest.fixture
    def middleware(self):
        return ExponentialRetryMiddleware(proxy_enabled=False)

    @pytest.fixture
    def spider(self):
        return MagicMock()

    def test_passes_clean_response_through(self, middleware, spider):
        request = Request(url="https://www.amazon.com/s?k=laptop")
        response = HtmlResponse(
            url="https://www.amazon.com/s?k=laptop",
            status=200,
            body=b"<html>Normal page content</html>",
            request=request,
        )
        result = middleware.process_response(request, response, spider)
        assert result is response

    def test_retries_on_503(self, middleware, spider):
        request = Request(
            url="https://www.amazon.com/s?k=laptop",
            meta={"retry_times": 0},
        )
        response = HtmlResponse(
            url="https://www.amazon.com/s?k=laptop",
            status=503,
            body=b"Service Unavailable",
            request=request,
        )
        with patch("twisted.internet.reactor.callLater") as mock_call:
            result = middleware.process_response(request, response, spider)
            from twisted.internet.defer import Deferred
            assert isinstance(result, Deferred)
            assert mock_call.called

    def test_detects_captcha_body(self, middleware, spider):
        request = Request(
            url="https://www.amazon.com/s?k=laptop",
            meta={"retry_times": 0},
        )
        response = HtmlResponse(
            url="https://www.amazon.com/s?k=laptop",
            status=200,
            body=b"<html>Enter the characters you see below</html>",
            request=request,
        )
        with patch("twisted.internet.reactor.callLater") as mock_call:
            result = middleware.process_response(request, response, spider)
            from twisted.internet.defer import Deferred
            assert isinstance(result, Deferred)

    def test_detects_robot_check_body(self, middleware, spider):
        request = Request(
            url="https://www.amazon.com/s?k=laptop",
            meta={"retry_times": 0},
        )
        response = HtmlResponse(
            url="https://www.amazon.com/s?k=laptop",
            status=200,
            body=b"<html>Robot Check</html>",
            request=request,
        )
        with patch("twisted.internet.reactor.callLater") as mock_call:
            result = middleware.process_response(request, response, spider)
            from twisted.internet.defer import Deferred
            assert isinstance(result, Deferred)

    def test_detects_unusual_traffic_body(self, middleware, spider):
        request = Request(
            url="https://www.amazon.com/s?k=laptop",
            meta={"retry_times": 0},
        )
        response = HtmlResponse(
            url="https://www.amazon.com/s?k=laptop",
            status=200,
            body=b"<html>Unusual Traffic detected</html>",
            request=request,
        )
        with patch("twisted.internet.reactor.callLater") as mock_call:
            result = middleware.process_response(request, response, spider)
            from twisted.internet.defer import Deferred
            assert isinstance(result, Deferred)

    def test_creates_fresh_request_on_max_retries(self, middleware, spider):
        request = Request(
            url="https://www.amazon.com/s?k=laptop",
            callback=lambda x: x,
            errback=lambda x: x,
            meta={"retry_count": 3},
        )
        response = HtmlResponse(
            url="https://www.amazon.com/s?k=laptop",
            status=503,
            body=b"Service Unavailable",
            request=request,
        )
        result = middleware.process_response(request, response, spider)
        from scrapy.http import Request as ScrapyRequest
        assert isinstance(result, ScrapyRequest)
        assert result.meta["retry_count"] == 0

    def test_does_not_retry_passed_max_but_request_same_url(self, middleware, spider):
        request = Request(
            url="https://www.amazon.com/dp/B09XYZ1234",
            callback=lambda x: x,
            meta={"retry_count": 3},
        )
        response = HtmlResponse(
            url="https://www.amazon.com/dp/B09XYZ1234",
            status=503,
            body=b"Service Unavailable",
            request=request,
        )
        result = middleware.process_response(request, response, spider)
        from scrapy.http import Request as ScrapyRequest
        assert isinstance(result, ScrapyRequest)
        assert result.url == "https://www.amazon.com/dp/B09XYZ1234"

    def test_exponential_backoff_delay_increases(self, middleware, spider):
        delays = []
        for retry_count in [0, 1, 2]:
            request = Request(
                url="https://www.amazon.com/s?k=laptop",
                meta={"retry_count": retry_count},
            )
            response = HtmlResponse(
                url="https://www.amazon.com/s?k=laptop",
                status=503,
                body=b"Service Unavailable",
                request=request,
            )
            with patch("twisted.internet.reactor.callLater") as mock_call:
                middleware.process_response(request, response, spider)
                if mock_call.called:
                    delays.append(mock_call.call_args[0][0])
        assert delays == [1, 2, 4]

    def test_anti_bot_keywords_coverage(self):
        from amazon_spider.middlewares.retry_middleware import ANTI_BOT_KEYWORDS
        expected = [
            "captcha",
            "robot check",
            "unusual traffic",
            "automated access",
            "enter the characters",
        ]
        assert ANTI_BOT_KEYWORDS == expected

    def test_handles_empty_response_body(self, middleware, spider):
        request = Request(
            url="https://www.amazon.com/s?k=laptop",
            meta={"retry_count": 0},
        )
        response = HtmlResponse(
            url="https://www.amazon.com/s?k=laptop",
            status=200,
            body=b"",
            request=request,
        )
        result = middleware.process_response(request, response, spider)
        assert result is response
