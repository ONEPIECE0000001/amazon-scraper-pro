"""Amazon product spider — pure HTTP, no JavaScript rendering required."""
import os
import re
import random
from datetime import datetime

import scrapy
from fake_useragent import UserAgent

from amazon_spider.items import AmazonProductItem


class AdvancedAmazonSpider(scrapy.Spider):
    name = "amazon"
    allowed_domains = ["amazon.com"]

    custom_settings = {
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 5,
        "RANDOMIZE_DOWNLOAD_DELAY": 0.5,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.retry_times = 3
        self._pending = {}  # asin → search-item, held until detail merge

        # User-Agent rotation
        try:
            self.ua = UserAgent()
        except Exception:
            self.user_agents = [
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) "
                "Gecko/20100101 Firefox/132.0",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:132.0) "
                "Gecko/20100101 Firefox/132.0",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
                "(KHTML, like Gecko) Version/17.5 Safari/605.1.15",
            ]

    # ── UA helpers ──────────────────────────────────────────────────────

    def _random_ua(self):
        try:
            return self.ua.random
        except Exception:
            return random.choice(self.user_agents)

    @staticmethod
    def _default_headers():
        return {
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;"
                "q=0.9,image/webp,*/*;q=0.8"
            ),
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Upgrade-Insecure-Requests": "1",
        }

    # ── Request builders ────────────────────────────────────────────────

    def _build_request(self, url, callback, **meta):
        """Create a Scrapy request with rotating UA and common headers."""
        headers = self._default_headers()
        headers["User-Agent"] = self._random_ua()
        headers["Referer"] = "https://www.google.com/"
        return scrapy.Request(
            url,
            headers=headers,
            callback=callback,
            meta=meta,
            dont_filter=False,
            errback=self._errback,
        )

    def _build_detail_request(self, url, product_id, search_item):
        headers = self._default_headers()
        headers["User-Agent"] = self._random_ua()
        headers["Referer"] = "https://www.amazon.com/"
        return scrapy.Request(
            url,
            headers=headers,
            callback=self.parse_product_detail,
            meta={"product_id": product_id, "search_item": dict(search_item)},
            dont_filter=True,
            errback=self._errback,
        )

    # ── Spider entry points ─────────────────────────────────────────────

    def start_requests(self):
        for req in self._build_start_requests():
            yield req

    def _build_start_requests(self):
        keyword = getattr(self, "keyword", "laptop")
        pages = int(getattr(self, "max_pages", 2))
        for page in range(1, pages + 1):
            yield self._build_request(
                f"https://www.amazon.com/s?k={keyword}&page={page}",
                callback=self.parse,
            )

    # ── Search page ─────────────────────────────────────────────────────

    def parse(self, response):
        self.logger.info("Parsing search: %s", response.url)

        products = response.css("[data-component-type='s-search-result']")
        self.logger.info("Found %d products", len(products))

        for product in products:
            try:
                asin = product.css("::attr(data-asin)").get()
                if not asin:
                    continue

                # Skip sponsored
                if product.css(".s-sponsored-faceout-badge-wrapper").get():
                    continue

                # Title
                title = (product.css("h2 a span::text").get() or "").strip() or None

                # Price: whole + fraction
                price = None
                pw = (product.css(".a-price-whole::text").get() or "").strip()
                pf = (product.css(".a-price-fraction::text").get() or "").strip()
                if pw:
                    w = re.sub(r"[^\d]", "", pw)
                    f = re.sub(r"[^\d]", "", pf)[:2].ljust(2, "0")
                    price = f"${w}.{f}"
                else:
                    off = product.css(".a-offscreen::text").get()
                    if off:
                        price = off.strip()

                # Rating
                rating = None
                aria = product.css(
                    "span[aria-label*='out of']::attr(aria-label)"
                ).get()
                if aria:
                    rating = aria.strip()
                else:
                    alt = product.css(".a-icon-alt::text").get()
                    if alt:
                        m = re.search(r"[\d.]+", alt)
                        if m:
                            rating = m.group()

                # Review count
                review_count = None
                rc_text = product.css(
                    "span[aria-label*='ratings']::text"
                ).get()
                if rc_text:
                    review_count = "".join(filter(str.isdigit, rc_text)) or None
                else:
                    rc_match = product.css(
                        "a[role='link'] span::text"
                    ).re(r"\d+,\d+|\d+")
                    if rc_match:
                        review_count = "".join(filter(str.isdigit, rc_match[0]))

                # Product URL
                href = product.css("h2 a::attr(href)").get()
                product_url = response.urljoin(href) if href else None

                if not asin or not title:
                    continue

                item = AmazonProductItem()
                item["asin"] = asin
                item["title"] = title
                item["price"] = price
                item["rating"] = rating
                item["review_count"] = review_count
                item["url"] = product_url
                item["brand"] = None
                item["category"] = None
                item["seller_name"] = None
                item["availability"] = None
                item["is_prime"] = None
                item["description"] = None
                item["original_price"] = None
                item["image_url"] = None
                item["date_first_available"] = None
                item["scraped_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                # Yield search data directly (detail page requires more time)
                yield item

            except Exception:
                self.logger.error("Error parsing product", exc_info=True)

        # Pagination
        next_page = response.css(
            'a[aria-label="Next page"]::attr(href)'
        ).get()
        if not next_page:
            next_page = response.css("li.a-last a::attr(href)").get()
        if next_page:
            yield self._build_request(
                response.urljoin(next_page), callback=self.parse
            )

    # ── Detail page ─────────────────────────────────────────────────────

    def parse_product_detail(self, response):
        product_id = response.meta.get("product_id")
        search_data = response.meta.get("search_item", {})
        self.logger.info("Parsing detail: %s", response.url)

        # Brand
        brand = None
        for sel in (
            "#bylineInfo::text",
            "#brand::text",
        ):
            t = response.css(sel).get()
            if t and t.strip():
                brand = t.strip()
                break
        if not brand:
            el = response.css("#bylineInfo-container a, #bylineInfo a")
            if el:
                brand = (el[0].css("::text").get() or "").strip() or None

        # Category breadcrumb
        category = None
        crumbs = response.css(
            "#wayfinding-breadcrumbs_feature_div ul li span a::text"
        ).getall()
        if crumbs:
            category = " > ".join(c.strip() for c in crumbs if c.strip()) or None

        # Date first available
        date_info = None
        d = response.css(
            "#productDetails_detailBullets_sections1 "
            "td:contains('Date First Available') + td::text"
        ).get()
        if d:
            date_info = d.strip()
        if not date_info:
            labels = response.css("div.content ul li span::text").getall()
            for i, label in enumerate(labels):
                if label and "Date First Available" in label:
                    try:
                        date_info = response.css(
                            "div.content ul li span::text"
                        )[i + 1].get()
                        if date_info:
                            date_info = date_info.strip()
                    except IndexError:
                        pass
                    break
        if not date_info:
            m = response.css(
                "#detailBullets_feature_div ul li span[dir='auto']::text"
            ).re(r"Date First Available.*?(\w+ \d+, \d{4}|\w+ \d{4})")
            if m:
                date_info = m[0]

        # Shipping
        shipping = response.css("#deliveryMessageMirId::text").get()
        if not shipping:
            shipping = response.css("#exportsBuyBox_feature_div span::text").get()
        if shipping:
            shipping = shipping.strip()

        # Prime
        is_prime = "Yes" if response.css(".a-icon-prime").get() else "No"

        # Merge search + detail data, yield complete item
        item = self._pending.pop(product_id, None)
        if item is None:
            item = AmazonProductItem()
            for f in item.fields:
                item[f] = search_data.get(f)

        item["brand"] = brand
        item["category"] = category
        item["date_first_available"] = date_info
        item["availability"] = shipping
        item["is_prime"] = is_prime

        yield item

    # ── Error handler ───────────────────────────────────────────────────

    def _errback(self, failure):
        self.logger.error("Request failed: %s — %s", failure.request.url, failure.value)
