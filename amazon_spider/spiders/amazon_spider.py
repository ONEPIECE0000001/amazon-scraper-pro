"""Amazon product spider — pure HTTP + curl_cffi TLS fingerprint impersonation."""

import random
import re
from datetime import datetime

import scrapy
from fake_useragent import UserAgent

from amazon_spider.items import AmazonProductItem

# Unicode control characters to strip from text fields
_UNICODE_CONTROL = re.compile(
    "[‎‏‪‫‬‭‮﻿ ]"
)


def _clean_text(value):
    """Strip Unicode control chars, excessive whitespace, and nil values."""
    if not value:
        return None
    value = _UNICODE_CONTROL.sub("", str(value)).strip()
    return value or None


def _clean_brand(value):
    """Clean brand name: strip control chars, remove 'Visit the X Store' wrapper."""
    value = _clean_text(value)
    if not value:
        return None
    # "Visit the Apple Store" → "Apple"
    m = re.match(r"^Visit the (.+?)(?:\s*Store)?$", value, re.I)
    if m:
        value = m.group(1).strip()
    return value or None


def _extract_best_image(product_sel):
    """
    Extract the highest-resolution product image URL.

    Amazon lazy-loads thumbnails — ``src`` may be a grey-pixel placeholder.
    The ``srcset`` attribute carries real image URLs at multiple resolutions;
    we pick the last (highest-resolution) entry.
    """
    srcset = (product_sel.css(".s-image::attr(srcset)").get() or "").strip()
    if srcset:
        # Format: "url1 1x, url2 1.5x, url3 2x"
        parts = [p.strip() for p in srcset.split(",") if p.strip()]
        if parts:
            # Last entry = highest resolution, take the URL part (before space)
            best = parts[-1].split()[0]
            if best.startswith("http"):
                return best

    # Fallback: src attribute
    src = (product_sel.css(".s-image::attr(src)").get() or "").strip()
    if src and "grey-pixel" not in src:
        return src

    # Last resort: data-src
    data_src = (product_sel.css(".s-image::attr(data-src)").get() or "").strip()
    if data_src:
        return data_src

    return src or None  # may still be grey-pixel, but better than nothing


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
        self.keyword = getattr(self, 'keyword', None) or kwargs.get('keyword', '')
        self._pending = {}
        self._crawl_detail = bool(int(getattr(self, "crawl_detail", 1)))
        self._max_pages = int(getattr(self, "max_pages", 2))
        self._pages_crawled = 0

        # User-Agent rotation — fallback list must match TLS impersonation (chrome131)
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) "
            "Gecko/20100101 Firefox/133.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:133.0) "
            "Gecko/20100101 Firefox/133.0",
        ]
        try:
            self.ua = UserAgent()
        except Exception:
            pass

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
        start = int(getattr(self, "start_page", 1))
        for page in range(start, start + pages):
            yield self._build_request(
                f"https://www.amazon.com/s?k={keyword}&page={page}",
                callback=self.parse,
            )

    # ── Search page ─────────────────────────────────────────────────────

    def parse(self, response):
        self.logger.info("Parsing search: %s", response.url)

        self._pages_crawled += 1
        products = response.css("[data-component-type='s-search-result']")
        self.logger.info(
            "Found %d products on page %d/%d",
            len(products), self._pages_crawled, self._max_pages,
        )

        for product in products:
            try:
                asin = product.css("::attr(data-asin)").get()
                if not asin:
                    continue

                # Skip sponsored
                if product.css(".s-sponsored-faceout-badge-wrapper").get():
                    continue

                # Title
                title = (
                    product.css("h2::attr(aria-label)").get()
                    or product.css("h2 > span::text").get()
                    or "".join(product.css("h2 ::text").getall())
                )
                title = _clean_text(title)
                if not title:
                    continue

                # Price — try multiple selectors (Amazon varies by product type)
                price = None
                pw = (product.css(".a-price-whole::text").get() or "").strip()
                pf = (product.css(".a-price-fraction::text").get() or "").strip()
                if pw:
                    w = re.sub(r"[^\d]", "", pw)
                    f = re.sub(r"[^\d]", "", pf)[:2].ljust(2, "0")
                    price = f"${w}.{f}"
                else:
                    # Fallback 1: .a-offscreen (screen-reader price text)
                    off = product.css(".a-offscreen::text").get()
                    if off:
                        price = off.strip()
                if not price:
                    # Fallback 2: data-a-color="price" (more stable attribute)
                    dp = product.css("[data-a-color='price'] .a-offscreen::text").get()
                    if dp:
                        price = dp.strip()
                if not price:
                    # Fallback 3: typographic price
                    tp = product.css(".a-price[data-a-size] .a-offscreen::text").get()
                    if tp:
                        price = tp.strip()

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
                href = product.css("a[href*='/dp/']::attr(href)").get()
                product_url = response.urljoin(href) if href else None

                if not asin:
                    continue

                # Image — extract best available URL
                image_url = _extract_best_image(product)

                # Build search-item payload for detail page merge
                search_item = {
                    "keyword": getattr(self, "keyword", ""),
                    "asin": asin,
                    "title": title,
                    "price": price,
                    "rating": rating,
                    "review_count": review_count,
                    "url": product_url,
                    "image_url": image_url,
                    "brand": None,
                    "category": None,
                    "seller_name": None,
                    "availability": None,
                    "is_prime": None,
                    "description": None,
                    "original_price": None,
                    "date_first_available": None,
                    "scraped_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }

                if self._crawl_detail and product_url:
                    self._pending[asin] = search_item
                    yield self._build_detail_request(
                        product_url, asin, search_item
                    )
                else:
                    item = AmazonProductItem()
                    for f in item.fields:
                        item[f] = search_item.get(f)
                    yield item

            except Exception:
                self.logger.error("Error parsing product", exc_info=True)

        # Pagination — respect max_pages limit
        if self._pages_crawled < self._max_pages:
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

        # Brand — prefer product details table over byline
        brand = None
        for entry in response.css("tr"):
            label = entry.css("th.prodDetSectionEntry::text").get()
            if label and label.strip() in ("Brand", "Manufacturer"):
                value = entry.css("td.prodDetAttrValue::text").get()
                if value:
                    brand = _clean_brand(value)
                    break

        # Fallback: old byline selectors
        if not brand:
            for sel in ("#bylineInfo::text", "#brand::text"):
                t = response.css(sel).get()
                if t and t.strip():
                    brand = _clean_brand(t)
                    break
        if not brand:
            el = response.css("#bylineInfo-container a, #bylineInfo a")
            if el:
                brand = _clean_brand((el[0].css("::text").get() or "").strip())

        # Category breadcrumb
        category = None
        crumbs = response.css(
            "#wayfinding-breadcrumbs_feature_div ul li span a::text"
        ).getall()
        if not crumbs:
            crumbs = response.css(
                "#breadcrumbs_feature_div ul li span a::text"
            ).getall()
        if crumbs:
            category = " > ".join(
                _clean_text(c) for c in crumbs if _clean_text(c)
            ) or None

        # Date first available
        date_info = None
        for entry in response.css("tr"):
            label = entry.css("th.prodDetSectionEntry::text").get()
            if label and "Date" in label:
                value = entry.css("td.prodDetAttrValue::text").get()
                if value:
                    date_info = _clean_text(value)
                    break
        if not date_info:
            d = response.css(
                "#productDetails_detailBullets_sections1 "
                "td:contains('Date') + td::text"
            ).get()
            if d:
                date_info = d.strip()

        # Shipping / availability
        shipping = None
        delivery_el = response.css(
            "#deliveryBlockMessage [data-csa-c-delivery-price]"
        )
        if delivery_el:
            price_ = delivery_el.attrib.get("data-csa-c-delivery-price", "")
            time_ = delivery_el.attrib.get("data-csa-c-delivery-time", "")
            parts = [p for p in [price_, time_] if p]
            shipping = " — ".join(parts) if parts else None
        if not shipping:
            shipping = response.css("#deliveryMessageMirId::text").get()
        if shipping:
            shipping = shipping.strip()

        # Prime
        is_prime = "Yes" if response.css(".a-icon-prime").get() else "No"

        # Merge search + detail data → item
        item = self._pending.pop(product_id, None)
        if item is None:
            item = AmazonProductItem()
            for f in item.fields:
                item[f] = search_data.get(f)
            item["keyword"] = getattr(self, "keyword", "")

        item["brand"] = brand
        item["category"] = category
        item["date_first_available"] = date_info
        item["availability"] = shipping
        item["is_prime"] = is_prime

        yield item

    # ── Error handler ───────────────────────────────────────────────────

    def _errback(self, failure):
        self.logger.error(
            "Request failed: %s — %s", failure.request.url, failure.value
        )
