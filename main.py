#!/usr/bin/env python
"""Amazon scraper entry point — builds and runs the scrapy command via subprocess."""

import argparse
import os
import subprocess
import sys
from datetime import datetime


def main() -> None:
    parser = argparse.ArgumentParser(description="Amazon product scraper")
    parser.add_argument("--keyword", "-k", required=True, help="search keyword")
    parser.add_argument("--pages", "-p", type=int, default=2, help="pages to crawl")
    parser.add_argument(
        "--show-browser", action="store_true", help="run browser in headed mode"
    )
    parser.add_argument(
        "--no-proxy", action="store_true", help="disable proxy pool"
    )
    args = parser.parse_args()

    use_proxy = not args.no_proxy

    # --- status ---
    if use_proxy:
        from core.proxy_pool import ProxyPool
        pool = ProxyPool()
        pool.refresh()
        s = pool.stats()
        print(
            f"Proxy pool: {{'available': {s['available']}, "
            f"'avg_latency': {s['avg_latency']:.2f}s}}"
        )
    else:
        print("Proxy pool: disabled (--no-proxy)")

    mysql_enabled = os.environ.get('MYSQL_ENABLED', 'True').lower() in ('1', 'true', 'yes')
    print(f"MySQL: {'enabled' if mysql_enabled else 'disabled'}")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    print(f"Output: output/amazon_{args.keyword}_{ts}.csv")

    # --- build scrapy command ---
    cmd = [
        sys.executable, "-m", "scrapy", "crawl", "amazon",
        "-a", f"keyword={args.keyword}",
        "-a", f"max_pages={args.pages}",
        "-a", f"headless={not args.show_browser}",
        "-s", f"PROXY_ENABLED={use_proxy}",
    ]

    print(f"\nRunning: {' '.join(cmd)}\n")
    try:
        subprocess.run(cmd, check=False)
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        sys.exit(130)

    print("Done. Check output/ for CSV results.")


if __name__ == "__main__":
    main()
