#!/usr/bin/env python
"""Amazon scraper entry point — builds and runs the scrapy command via subprocess."""

import argparse
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Load .env file if present
_ENV_PATH = Path(__file__).resolve().parent / ".env"
if _ENV_PATH.exists():
    with open(_ENV_PATH, encoding="utf-8") as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _key, _, _val = _line.partition("=")
                os.environ.setdefault(_key.strip(), _val.strip())


def main() -> None:
    parser = argparse.ArgumentParser(description="Amazon product scraper")
    parser.add_argument("--keyword", "-k", default=None, help="search keyword")
    parser.add_argument("--asin", default=None,
                        help="single ASIN or comma-separated list (B0XXX,B0YYY)")
    parser.add_argument("--asin-list", default=None,
                        help="path to a text file with one ASIN per line")
    parser.add_argument("--label", default=None,
                        help="label for keyword column when using --asin (default: asin_direct)")
    parser.add_argument("--pages", "-p", type=int, default=2, help="pages to crawl")
    parser.add_argument("--start-page", type=int, default=1,
                        help="first page number (for batch resume, e.g. --start-page 6 --pages 5)")
    parser.add_argument(
        "--show-browser", action="store_true", help="run browser in headed mode"
    )
    parser.add_argument(
        "--no-proxy", action="store_true", help="disable proxy pool"
    )
    parser.add_argument(
        "--no-detail", action="store_true",
        help="fast mode: skip detail pages, only grab search result fields"
    )
    args = parser.parse_args()

    # ── validate: keyword or ASIN required ─────────────────────────────
    if not args.keyword and not args.asin and not args.asin_list:
        parser.error("either --keyword or --asin/--asin-list is required")

    # ── resolve ASINs ──────────────────────────────────────────────────
    asins = []
    if args.asin:
        asins.extend(a.strip() for a in args.asin.split(",") if a.strip())
    if args.asin_list:
        p = Path(args.asin_list)
        if not p.exists():
            print(f"Error: ASIN list file not found: {args.asin_list}")
            sys.exit(1)
        with open(p, encoding="utf-8") as f_:
            for line in f_:
                a = line.strip()
                if a and not a.startswith("#"):
                    asins.append(a)

    if asins:
        # Validate ASIN format
        asin_pat = re.compile(r"^[A-Z0-9]{10}$")
        bad = [a for a in asins if not asin_pat.match(a)]
        if bad:
            print(f"Warning: {len(bad)} invalid ASIN(s) skipped: {bad[:5]}")
            asins = [a for a in asins if asin_pat.match(a)]
        if not asins:
            print("Error: no valid ASINs found")
            sys.exit(1)
        print(f"ASIN mode: {len(asins)} product(s)")
        args.keyword = args.label or "asin_direct"
        args.pages = 1        # ASIN mode: no pagination
        args.no_detail = False  # always fetch detail for ASIN mode
        args.crawl_detail = 1

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
    safe_keyword = re.sub(r"[^\w\-]", "_", args.keyword)
    start_p = args.start_page
    end_p = start_p + args.pages - 1
    page_range = f"p{start_p}-{end_p}" if args.pages > 1 else f"p{start_p}"
    mode = "fast" if args.no_detail else "full"
    output_file = f"output/amazon_{safe_keyword}_{page_range}_{mode}_{ts}.csv"
    print(f"Output: {output_file}")

    # --- build scrapy command ---
    cmd = [
        sys.executable, "-m", "scrapy", "crawl", "amazon",
        "-a", f"keyword={args.keyword}",
        "-a", f"max_pages={args.pages}",
        "-a", f"start_page={args.start_page}",
        "-a", f"crawl_detail={1 if not args.no_detail else 0}",
        "-a", f"headless={not args.show_browser}",
        "-s", f"PROXY_ENABLED={use_proxy}",
        "-s", "FEEDS=",           # clear default feed to avoid duplicate CSV
        "-o", output_file,
    ]
    if asins:
        cmd.insert(-2, "-a")
        cmd.insert(-2, f"asins={','.join(asins)}")

    print(f"\nRunning: {' '.join(cmd)}\n")
    try:
        subprocess.run(cmd, check=False)
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        sys.exit(130)

    print("Done. Check output/ for CSV results.")


if __name__ == "__main__":
    main()
