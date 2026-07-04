"""
Proxy pool with auto-refresh from free proxy sources and validation.
"""
import logging
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Set, Tuple, Union

import requests

logger = logging.getLogger(__name__)

PROXY_SOURCES = [
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
    "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt",
    "https://raw.githubusercontent.com/hookzof/socks5_list/master/proxy.txt",
]

TEST_URL = "http://httpbin.org/ip"

# Session that ignores system HTTP_PROXY / HTTPS_PROXY env vars —
# otherwise the proxy-source fetches get routed through a (likely dead) proxy.
_SOURCE_SESSION = requests.Session()
_SOURCE_SESSION.trust_env = False


class ProxyPool:
    """Auto-refreshing proxy pool backed by free public sources.

    The pool is a process-wide singleton — multiple places (ProxyMiddleware,
    ExponentialRetryMiddleware, main.py) share a single instance so proxy
    lists are fetched and validated only once.
    """

    _instance: Optional["ProxyPool"] = None

    def __new__(cls, min_proxies: int = 5) -> "ProxyPool":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, min_proxies: int = 5) -> None:
        if hasattr(self, "_initialized"):
            return
        self._initialized = True
        self.min_proxies = min_proxies
        self.proxies: List[Dict[str, Union[str, float]]] = []
        self.refresh()

    def _fetch_raw_proxies(self) -> List[str]:
        """Pull proxy lists from free sources, deduplicate and format them."""
        seen: Set[str] = set()
        for source in PROXY_SOURCES:
            try:
                resp = _SOURCE_SESSION.get(source, timeout=10)
                resp.raise_for_status()
                for line in resp.text.splitlines():
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if not any(line.startswith(scheme) for scheme in ("http://", "https://", "socks5://", "socks4://")):
                        line = f"http://{line}"
                    if line not in seen:
                        seen.add(line)
                logger.debug("Fetched proxies from %s", source)
            except Exception:
                logger.debug("Failed to fetch from %s", source, exc_info=True)
        logger.info("Fetched %d raw proxies total", len(seen))
        return list(seen)

    def validate_proxies(self) -> int:
        """Validate raw proxies against httpbin and keep the working ones."""
        raw = self._fetch_raw_proxies()
        if not raw:
            logger.warning("No raw proxies to validate")
            return 0

        valid: List[Dict[str, Union[str, float]]] = []

        def _check(proxy_url: str) -> Optional[Tuple[str, float]]:
            try:
                start = time.perf_counter()
                resp = requests.get(
                    TEST_URL,
                    proxies={"http": proxy_url, "https": proxy_url},
                    timeout=5,
                )
                elapsed = time.perf_counter() - start
                if resp.status_code == 200:
                    return (proxy_url, elapsed)
            except Exception:
                pass
            return None

        with ThreadPoolExecutor(max_workers=20) as pool:
            futures = {pool.submit(_check, p): p for p in raw}
            for future in as_completed(futures):
                result = future.result()
                if result is not None:
                    url, elapsed = result
                    valid.append({"url": url, "latency": elapsed, "score": 1.0})

        self.proxies = valid
        logger.info(f"Validated {len(valid)}/{len(raw)} proxies")
        return len(valid)

    def get_proxy(self) -> Optional[str]:
        """Return a random proxy weighted by inverse latency.

        Auto-refreshes the pool when empty.
        """
        if not self.proxies:
            logger.info("Proxy pool empty, refreshing …")
            self.refresh()
        if not self.proxies:
            logger.warning("Proxy pool still empty after refresh, going direct")
            return None

        # Weighted random: lower latency → higher weight
        weights = [1.0 / max(p["latency"], 0.01) for p in self.proxies]
        chosen = random.choices(self.proxies, weights=weights, k=1)[0]
        return str(chosen["url"])

    def mark_bad(self, proxy: str) -> None:
        """Remove a specific proxy from the pool."""
        before = len(self.proxies)
        self.proxies = [p for p in self.proxies if p["url"] != proxy]
        if len(self.proxies) < before:
            logger.debug(f"Marked bad proxy: {proxy}")

    def refresh(self) -> None:
        """Fetch and validate proxies, replacing the current pool."""
        self.validate_proxies()
        logger.info(f"Proxy pool refreshed: {len(self.proxies)} available")

    def stats(self) -> Dict[str, Union[int, float]]:
        """Return pool statistics."""
        if not self.proxies:
            return {"total_fetched": 0, "available": 0, "avg_latency": 0.0}
        latencies = [float(p["latency"]) for p in self.proxies]
        return {
            "total_fetched": len(self.proxies),
            "available": len(self.proxies),
            "avg_latency": sum(latencies) / len(latencies),
        }
