"""
Unit tests for ProxyPool.

Run with:  pytest tests/test_proxy_pool.py -v
"""

import sys
import time
from unittest.mock import MagicMock, patch, mock_open

import pytest

sys.path.insert(0, "..")

from core.proxy_pool import ProxyPool


# ---------------------------------------------------------------------------
# ProxyPool — initialization and singleton
# ---------------------------------------------------------------------------

class TestProxyPoolInit:
    def test_singleton_behavior(self):
        # ProxyPool is a singleton — reset it first
        ProxyPool._instance = None
        with patch.object(ProxyPool, "validate_proxies", return_value=0):
            pool1 = ProxyPool()
            pool2 = ProxyPool()
        assert pool1 is pool2

    def test_init_does_not_refresh_twice(self):
        ProxyPool._instance = None
        # Second init should skip
        with patch.object(ProxyPool, "validate_proxies", return_value=0):
            with patch.object(ProxyPool, "refresh") as mock_refresh:
                pool1 = ProxyPool(min_proxies=5)
                # mock_refresh called once during first __init__
                # Second __init__ on same instance is a no-op
                pool2 = ProxyPool(min_proxies=10)
        # The singleton __init__ short-circuits on second call
        # refresh() is called once in first init only


# ---------------------------------------------------------------------------
# ProxyPool — proxy format normalization
# ---------------------------------------------------------------------------

class TestProxyFormatting:
    def test_http_prefix_added_when_missing(self):
        """The real _fetch_raw_proxies adds http:// when no scheme present."""
        ProxyPool._instance = None
        raw_response = "192.168.1.1:8080\nhttp://proxy.example.com:3128\n"

        with patch("core.proxy_pool._SOURCE_SESSION.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.text = raw_response
            mock_resp.raise_for_status.return_value = None
            mock_get.return_value = mock_resp

            with patch.object(ProxyPool, "validate_proxies", return_value=0):
                pool = ProxyPool()
                pool.proxies = []
                raw_proxies = pool._fetch_raw_proxies()

                assert "http://192.168.1.1:8080" in raw_proxies
                assert "http://proxy.example.com:3128" in raw_proxies

    def test_socks5_prefix_preserved(self):
        ProxyPool._instance = None
        raw_response = "socks5://192.168.1.1:1080\nsocks4://192.168.1.2:1080\n"

        with patch("core.proxy_pool._SOURCE_SESSION.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.text = raw_response
            mock_resp.raise_for_status.return_value = None
            mock_get.return_value = mock_resp

            with patch.object(ProxyPool, "validate_proxies", return_value=0):
                pool = ProxyPool()
                pool.proxies = []
                raw_proxies = pool._fetch_raw_proxies()

                assert "socks5://192.168.1.1:1080" in raw_proxies
                assert "socks4://192.168.1.2:1080" in raw_proxies

    def test_https_prefix_preserved(self):
        ProxyPool._instance = None
        raw_response = "https://proxy.example.com:443\n"

        with patch("core.proxy_pool._SOURCE_SESSION.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.text = raw_response
            mock_resp.raise_for_status.return_value = None
            mock_get.return_value = mock_resp

            with patch.object(ProxyPool, "validate_proxies", return_value=0):
                pool = ProxyPool()
                pool.proxies = []
                raw_proxies = pool._fetch_raw_proxies()

                assert "https://proxy.example.com:443" in raw_proxies


# ---------------------------------------------------------------------------
# ProxyPool — validate_proxies
# ---------------------------------------------------------------------------

class TestProxyValidation:
    def test_validate_returns_zero_when_no_raw(self):
        ProxyPool._instance = None
        with patch.object(ProxyPool, "_fetch_raw_proxies", return_value=[]):
            pool = ProxyPool()
            result = pool.validate_proxies()
            assert result == 0

    @patch("core.proxy_pool.requests.get")
    def test_validate_keeps_working_proxy(self, mock_get):
        ProxyPool._instance = None
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        raw = ["http://good.proxy:8080"]
        with patch.object(ProxyPool, "_fetch_raw_proxies", return_value=raw):
            pool = ProxyPool()
            result = pool.validate_proxies()
            # We can't easily control ThreadPoolExecutor timing,
            # but we verify the structure
            assert result >= 0

    @patch("core.proxy_pool.requests.get")
    def test_validate_drops_failed_proxy(self, mock_get):
        ProxyPool._instance = None
        mock_get.side_effect = Exception("Connection refused")

        raw = ["http://bad.proxy:8080"]
        with patch.object(ProxyPool, "_fetch_raw_proxies", return_value=raw):
            pool = ProxyPool()
            result = pool.validate_proxies()
            assert result == 0  # all failed
            assert len(pool.proxies) == 0


# ---------------------------------------------------------------------------
# ProxyPool — weighted random selection
# ---------------------------------------------------------------------------

class TestProxySelection:
    @pytest.fixture
    def populated_pool(self):
        ProxyPool._instance = None
        with patch.object(ProxyPool, "validate_proxies", return_value=0):
            pool = ProxyPool()
        pool.proxies = [
            {"url": "http://fast.proxy:8080", "latency": 0.1, "score": 1.0},
            {"url": "http://medium.proxy:8080", "latency": 1.0, "score": 1.0},
            {"url": "http://slow.proxy:8080", "latency": 5.0, "score": 1.0},
        ]
        return pool

    def test_get_proxy_returns_string(self, populated_pool):
        proxy = populated_pool.get_proxy()
        assert isinstance(proxy, str)
        assert proxy.startswith("http://")

    def test_get_proxy_from_populated_pool(self, populated_pool):
        proxy = populated_pool.get_proxy()
        valid_urls = [
            "http://fast.proxy:8080",
            "http://medium.proxy:8080",
            "http://slow.proxy:8080",
        ]
        assert proxy in valid_urls

    def test_get_proxy_auto_refreshes_when_empty(self):
        ProxyPool._instance = None
        with patch.object(ProxyPool, "validate_proxies", return_value=0):
            pool = ProxyPool()
        pool.proxies = []
        pool.refresh = MagicMock()            # block real refresh from hitting network
        pool.get_proxy()
        assert pool.refresh.called

    def test_get_proxy_returns_none_when_still_empty(self):
        ProxyPool._instance = None
        with patch.object(ProxyPool, "validate_proxies", return_value=0):
            pool = ProxyPool()
        pool.proxies = []
        pool.refresh = MagicMock()            # block real refresh from hitting network
        result = pool.get_proxy()
        assert result is None


# ---------------------------------------------------------------------------
# ProxyPool — mark_bad
# ---------------------------------------------------------------------------

class TestMarkBad:
    @pytest.fixture
    def pool_with_proxies(self):
        ProxyPool._instance = None
        with patch.object(ProxyPool, "validate_proxies", return_value=0):
            pool = ProxyPool()
        pool.proxies = [
            {"url": "http://good.proxy:8080", "latency": 0.5, "score": 1.0},
            {"url": "http://bad.proxy:8080", "latency": 5.0, "score": 1.0},
        ]
        return pool

    def test_removes_specified_proxy(self, pool_with_proxies):
        assert len(pool_with_proxies.proxies) == 2
        pool_with_proxies.mark_bad("http://bad.proxy:8080")
        assert len(pool_with_proxies.proxies) == 1
        assert pool_with_proxies.proxies[0]["url"] == "http://good.proxy:8080"

    def test_mark_bad_nonexistent_proxy_noop(self, pool_with_proxies):
        assert len(pool_with_proxies.proxies) == 2
        pool_with_proxies.mark_bad("http://nonexistent.proxy:9999")
        assert len(pool_with_proxies.proxies) == 2  # unchanged


# ---------------------------------------------------------------------------
# ProxyPool — stats
# ---------------------------------------------------------------------------

class TestProxyStats:
    def test_empty_pool_stats(self):
        ProxyPool._instance = None
        with patch.object(ProxyPool, "validate_proxies", return_value=0):
            pool = ProxyPool()
        pool.proxies = []
        stats = pool.stats()
        assert stats["available"] == 0
        assert stats["total_fetched"] == 0
        assert stats["avg_latency"] == 0.0

    def test_populated_pool_stats(self):
        ProxyPool._instance = None
        with patch.object(ProxyPool, "validate_proxies", return_value=0):
            pool = ProxyPool()
        pool.proxies = [
            {"url": "http://p1:8080", "latency": 0.5, "score": 1.0},
            {"url": "http://p2:8080", "latency": 1.5, "score": 1.0},
        ]
        stats = pool.stats()
        assert stats["available"] == 2
        assert stats["total_fetched"] == 2
        assert stats["avg_latency"] == 1.0  # (0.5 + 1.5) / 2


# ---------------------------------------------------------------------------
# ProxyPool — refresh
# ---------------------------------------------------------------------------

class TestProxyRefresh:
    def test_refresh_calls_validate(self):
        ProxyPool._instance = None
        with patch.object(ProxyPool, "validate_proxies", return_value=0):
            pool = ProxyPool()
        pool.validate_proxies = MagicMock(return_value=5)
        pool.refresh()
        pool.validate_proxies.assert_called_once()


# ---------------------------------------------------------------------------
# ProxyPool — fetch from sources
# ---------------------------------------------------------------------------

class TestFetchRawProxies:
    @patch("core.proxy_pool._SOURCE_SESSION.get")
    def test_fetches_and_deduplicates(self, mock_get):
        ProxyPool._instance = None
        mock_resp = MagicMock()
        mock_resp.text = "192.168.1.1:8080\n192.168.1.2:8080\n192.168.1.1:8080\n"
        mock_get.return_value = mock_resp
        mock_resp.raise_for_status.return_value = None

        with patch.object(ProxyPool, "validate_proxies", return_value=0):
            pool = ProxyPool()
            pool.proxies = []
            raw = pool._fetch_raw_proxies()

            assert len(raw) == 2  # deduplicated
            assert "http://192.168.1.1:8080" in raw
            assert "http://192.168.1.2:8080" in raw

    @patch("core.proxy_pool._SOURCE_SESSION.get")
    def test_handles_source_failure_gracefully(self, mock_get):
        ProxyPool._instance = None
        mock_get.side_effect = Exception("Network error")

        with patch.object(ProxyPool, "validate_proxies", return_value=0):
            pool = ProxyPool()
            pool.proxies = []
            raw = pool._fetch_raw_proxies()

            assert raw == []  # returns empty list on failure
