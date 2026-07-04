"""
Unit tests for Amazon spider parsing logic.

Run with:  pytest tests/test_spider.py -v
"""

import sys
from unittest.mock import MagicMock, AsyncMock, patch

import pytest
from scrapy.http import HtmlResponse, Request

sys.path.insert(0, "..")

from amazon_spider.spiders.amazon_spider import AdvancedAmazonSpider
from amazon_spider.items import AmazonProductItem


# ---------------------------------------------------------------------------
# HTML fixtures
# ---------------------------------------------------------------------------

SEARCH_PAGE_HTML = """
<html>
<body>
<div data-component-type="s-search-result" data-asin="B09XYZ1234">
    <a class="a-link-normal s-faceout-link aok-block a-text-normal" href="/dp/B09XYZ1234">
        <span><span role="link">
            <h2 aria-label="Wireless Bluetooth Headphones"><span>Wireless Bluetooth Headphones</span></h2>
        </span></span>
    </a>
    <span class="a-price">
        <span class="a-price-whole">49</span>
        <span class="a-price-fraction">99</span>
    </span>
    <span aria-label="4.5 out of 5 stars"></span>
    <span aria-label="1,234 ratings">1,234</span>
</div>
<div data-component-type="s-search-result" data-asin="B08ABCD5678">
    <a class="a-link-normal s-faceout-link aok-block a-text-normal" href="/gp/product/B08ABCD5678">
        <span><span role="link">
            <h2 aria-label="USB-C Charging Cable 2-Pack"><span>USB-C Charging Cable 2-Pack</span></h2>
        </span></span>
    </a>
    <span class="a-offscreen">$12.99</span>
    <span class="a-icon-alt">4.2 out of 5 stars</span>
    <a role="link"><span>567</span></a>
</div>
<div data-component-type="s-search-result" data-asin="B07SPONSOR">
    <span class="s-sponsored-faceout-badge-wrapper"></span>
    <a class="a-link-normal s-faceout-link aok-block a-text-normal" href="/dp/B07SPONSOR">
        <span><span role="link">
            <h2 aria-label="Sponsored Product"><span>Sponsored Product</span></h2>
        </span></span>
    </a>
</div>
<a aria-label="Next page" href="/s?k=laptop&page=2"></a>
</body>
</html>
"""

SEARCH_PAGE_NO_NEXT = """
<html>
<body>
<div data-component-type="s-search-result" data-asin="B09XYZ1234">
    <a class="a-link-normal s-faceout-link aok-block a-text-normal" href="/dp/B09XYZ1234">
        <span><span role="link">
            <h2 aria-label="Test Product"><span>Test Product</span></h2>
        </span></span>
    </a>
    <span class="a-price">
        <span class="a-price-whole">10</span>
        <span class="a-price-fraction">00</span>
    </span>
</div>
</body>
</html>
"""

DETAIL_PAGE_HTML = """
<html>
<body>
<h1 id="productTitle">Wireless Bluetooth Headphones</h1>
<div id="bylineInfo">BrandName</div>
<div id="wayfinding-breadcrumbs_feature_div">
    <ul><li><span><a>Electronics</a></span></li><li><span><a>Headphones</a></span></li></ul>
</div>
<div id="productDetails_detailBullets_sections1">
    <table>
        <tr><td>Date First Available</td><td>January 15, 2024</td></tr>
    </table>
</div>
<span id="deliveryMessageMirId">FREE delivery: Jan 20-25</span>
<span class="a-icon-prime"></span>
</body>
</html>
"""

DETAIL_PAGE_MINIMAL = """
<html>
<body>
<h1 id="productTitle">Minimal Product</h1>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Spider creation
# ---------------------------------------------------------------------------

class TestSpiderCreation:
    def test_spider_instantiation(self):
        spider = AdvancedAmazonSpider()
        assert spider.name == "amazon"
        assert "amazon.com" in spider.allowed_domains

    def test_spider_default_params(self):
        spider = AdvancedAmazonSpider()
        assert spider.retry_times == 3

    def test_ua_fallback_list_loaded(self):
        spider = AdvancedAmazonSpider()
        # When fake_useragent is unavailable, the fallback list should be used
        spider.ua = None  # simulate fake_useragent failure
        ua = spider._random_ua()
        assert ua in spider.user_agents

    def test_custom_settings_configured(self):
        spider = AdvancedAmazonSpider()
        assert spider.custom_settings["CONCURRENT_REQUESTS"] == 1
        assert spider.custom_settings["DOWNLOAD_DELAY"] == 5


# ---------------------------------------------------------------------------
# Search page parsing
# ---------------------------------------------------------------------------

class TestSearchPageParsing:
    @pytest.fixture
    def spider(self):
        s = AdvancedAmazonSpider()
        s._crawl_detail = False  # fast mode: yield items directly
        return s

    @pytest.fixture
    def search_response(self):
        request = Request(url="https://www.amazon.com/s?k=laptop&page=1")
        response = HtmlResponse(
            url="https://www.amazon.com/s?k=laptop&page=1",
            body=SEARCH_PAGE_HTML.encode(),
            encoding="utf-8",
            request=request,
        )
        return response

    def make_response(self, html, url="https://www.amazon.com/s?k=laptop&page=1"):
        request = Request(url=url)
        return HtmlResponse(
            url=url, body=html.encode(), encoding="utf-8", request=request
        )

    
    def test_extracts_correct_number_of_products(self, spider, search_response):
        results = []
        for item in spider.parse(search_response):
            if isinstance(item, AmazonProductItem):
                results.append(item)

        # 3 products in HTML, 1 is sponsored → 2 organic products
        assert len(results) == 2

    
    def test_extracts_asin(self, spider, search_response):
        results = []
        for item in spider.parse(search_response):
            if isinstance(item, AmazonProductItem):
                results.append(item)

        asins = {r["asin"] for r in results}
        assert "B09XYZ1234" in asins
        assert "B08ABCD5678" in asins
        assert "B07SPONSOR" not in asins  # sponsored

    
    def test_extracts_title(self, spider, search_response):
        results = []
        for item in spider.parse(search_response):
            if isinstance(item, AmazonProductItem):
                results.append(item)

        titles = {r["title"] for r in results}
        assert "Wireless Bluetooth Headphones" in titles
        assert "USB-C Charging Cable 2-Pack" in titles

    
    def test_extracts_price_whole_fraction(self, spider, search_response):
        results = []
        for item in spider.parse(search_response):
            if isinstance(item, AmazonProductItem):
                results.append(item)

        # First product uses whole + fraction: $49.99
        item1 = [r for r in results if r["asin"] == "B09XYZ1234"][0]
        assert item1["price"] == "$49.99"

    
    def test_extracts_price_offscreen(self, spider):
        html = """
        <html><body>
        <div data-component-type="s-search-result" data-asin="B00TEST">
            <h2><a href="/dp/B00TEST"><span>Offscreen Price Item</span></a></h2>
            <span class="a-offscreen">$12.99</span>
        </div>
        </body></html>
        """
        response = self.make_response(html)
        results = []
        for item in spider.parse(response):
            if isinstance(item, AmazonProductItem):
                results.append(item)

        assert results[0]["price"] == "$12.99"

    
    def test_extracts_title_empty_becomes_none(self, spider):
        html = """
        <html><body>
        <div data-component-type="s-search-result" data-asin="B00NOTITLE">
            <h2><a href="/dp/B00NOTITLE"><span></span></a></h2>
        </div>
        </body></html>
        """
        response = self.make_response(html)
        results = []
        for item in spider.parse(response):
            if isinstance(item, AmazonProductItem):
                results.append(item)

        # Empty title → .strip() → "" → becomes None via `or None`
        # So this product is skipped because the condition `if product_id and name` fails
        assert len(results) == 0

    
    def test_rating_from_aria_label(self, spider, search_response):
        results = []
        for item in spider.parse(search_response):
            if isinstance(item, AmazonProductItem):
                results.append(item)

        item1 = [r for r in results if r["asin"] == "B09XYZ1234"][0]
        assert "4.5" in item1["rating"]

    
    def test_rating_from_icon_alt(self, spider):
        html = """
        <html><body>
        <div data-component-type="s-search-result" data-asin="B00RATING">
            <h2><a href="/dp/B00RATING"><span>Rating Test</span></a></h2>
            <span class="a-icon-alt">4.2 out of 5 stars</span>
        </div>
        </body></html>
        """
        response = self.make_response(html)
        results = []
        for item in spider.parse(response):
            if isinstance(item, AmazonProductItem):
                results.append(item)

        assert results[0]["rating"] == "4.2"

    
    def test_review_count_from_span(self, spider, search_response):
        results = []
        for item in spider.parse(search_response):
            if isinstance(item, AmazonProductItem):
                results.append(item)

        item1 = [r for r in results if r["asin"] == "B09XYZ1234"][0]
        assert item1["review_count"] == "1234"

    
    def test_review_count_from_link(self, spider):
        html = """
        <html><body>
        <div data-component-type="s-search-result" data-asin="B00REVIEW">
            <h2><a href="/dp/B00REVIEW"><span>Review Test</span></a></h2>
            <a role="link"><span>567</span></a>
        </div>
        </body></html>
        """
        response = self.make_response(html)
        results = []
        for item in spider.parse(response):
            if isinstance(item, AmazonProductItem):
                results.append(item)

        assert results[0]["review_count"] == "567"

    
    def test_ad_products_filtered(self, spider):
        # All 3 products in the main fixture, but the sponsored one is filtered
        html = """
        <html><body>
        <div data-component-type="s-search-result" data-asin="B00REAL1">
            <h2><a href="/dp/B00REAL1"><span>Real Product</span></a></h2>
        </div>
        <div data-component-type="s-search-result" data-asin="B00SPONS">
            <span class="s-sponsored-faceout-badge-wrapper"></span>
            <h2><a href="/dp/B00SPONS"><span>Ad</span></a></h2>
        </div>
        <div data-component-type="s-search-result" data-asin="B00REAL2">
            <h2><a href="/dp/B00REAL2"><span>Another Real Product</span></a></h2>
        </div>
        </body></html>
        """
        response = self.make_response(html)
        results = []
        for item in spider.parse(response):
            if isinstance(item, AmazonProductItem):
                results.append(item)

        assert len(results) == 2
        asins = {r["asin"] for r in results}
        assert "B00SPONS" not in asins


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------

class TestPagination:
    @pytest.fixture
    def spider(self):
        s = AdvancedAmazonSpider()
        s._crawl_detail = False
        return s

    def make_response(self, html, url="https://www.amazon.com/s?k=laptop&page=1"):
        request = Request(url=url)
        return HtmlResponse(
            url=url, body=html.encode(), encoding="utf-8", request=request
        )

    
    def test_next_page_link_followed(self, spider):
        response = self.make_response(SEARCH_PAGE_HTML)
        next_requests = []
        for result in spider.parse(response):
            if isinstance(result, Request):
                next_requests.append(result)

        # Filter to pagination requests only (exclude detail page requests)
        page_reqs = [r for r in next_requests if "/s?k=" in r.url]
        assert len(page_reqs) == 1
        assert "page=2" in page_reqs[0].url

    
    def test_no_next_page_when_missing(self, spider):
        response = self.make_response(SEARCH_PAGE_NO_NEXT)
        next_requests = []
        for result in spider.parse(response):
            if isinstance(result, Request):
                next_requests.append(result)

        # Filter to pagination requests only
        page_reqs = [r for r in next_requests if "/s?k=" in r.url]
        assert len(page_reqs) == 0

    
    def test_next_page_with_last_selector(self, spider):
        html = """
        <html><body>
        <div data-component-type="s-search-result" data-asin="B00TEST">
            <h2><a href="/dp/B00TEST"><span>Test</span></a></h2>
        </div>
        <li class="a-last"><a href="/s?k=laptop&page=2"></a></li>
        </body></html>
        """
        response = self.make_response(html)
        next_requests = []
        for result in spider.parse(response):
            if isinstance(result, Request):
                next_requests.append(result)

        # Filter to pagination requests only
        page_reqs = [r for r in next_requests if "/s?k=" in r.url]
        assert len(page_reqs) == 1


# ---------------------------------------------------------------------------
# Detail page parsing
# ---------------------------------------------------------------------------

class TestDetailPageParsing:
    @pytest.fixture
    def spider(self):
        return AdvancedAmazonSpider()

    def make_response(self, html, url="https://www.amazon.com/dp/B09XYZ1234", meta=None):
        request = Request(url=url, meta=meta or {})
        return HtmlResponse(
            url=url, body=html.encode(), encoding="utf-8", request=request
        )

    
    def test_extracts_brand_from_byline(self, spider):
        search_data = {
            "asin": "B09XYZ1234",
            "title": "Wireless Bluetooth Headphones",
            "price": "$49.99",
            "rating": "4.5",
            "review_count": "1234",
            "url": "https://www.amazon.com/dp/B09XYZ1234",
            "brand": None,
            "category": None,
            "seller_name": None,
            "availability": None,
            "is_prime": None,
            "description": None,
            "original_price": None,
            "image_url": None,
            "date_first_available": None,
            "scraped_at": "2024-01-01 00:00:00",
        }
        response = self.make_response(
            DETAIL_PAGE_HTML,
            meta={"product_id": "B09XYZ1234", "search_item": search_data},
        )
        results = []
        for item in spider.parse_product_detail(response):
            if isinstance(item, AmazonProductItem):
                results.append(item)

        assert len(results) == 1
        assert results[0]["brand"] == "BrandName"

    
    def test_extracts_category_breadcrumb(self, spider):
        search_data = {
            "asin": "B09XYZ1234", "title": "Test", "price": "$10.00",
            "rating": "4.0", "review_count": "100",
            "url": "https://www.amazon.com/dp/B09XYZ1234",
            "brand": None, "category": None, "seller_name": None,
            "availability": None, "is_prime": None, "description": None,
            "original_price": None, "image_url": None,
            "date_first_available": None, "scraped_at": "2024-01-01 00:00:00",
        }
        response = self.make_response(
            DETAIL_PAGE_HTML,
            meta={"product_id": "B09XYZ1234", "search_item": search_data},
        )
        results = []
        for item in spider.parse_product_detail(response):
            if isinstance(item, AmazonProductItem):
                results.append(item)

        assert results[0]["category"] == "Electronics > Headphones"

    
    def test_extracts_date_first_available(self, spider):
        search_data = {
            "asin": "B09XYZ1234", "title": "Test", "price": "$10.00",
            "rating": "4.0", "review_count": "100",
            "url": "https://www.amazon.com/dp/B09XYZ1234",
            "brand": None, "category": None, "seller_name": None,
            "availability": None, "is_prime": None, "description": None,
            "original_price": None, "image_url": None,
            "date_first_available": None, "scraped_at": "2024-01-01 00:00:00",
        }
        response = self.make_response(
            DETAIL_PAGE_HTML,
            meta={"product_id": "B09XYZ1234", "search_item": search_data},
        )
        results = []
        for item in spider.parse_product_detail(response):
            if isinstance(item, AmazonProductItem):
                results.append(item)

        assert results[0]["date_first_available"] == "January 15, 2024"

    
    def test_extracts_shipping_info(self, spider):
        search_data = {
            "asin": "B09XYZ1234", "title": "Test", "price": "$10.00",
            "rating": "4.0", "review_count": "100",
            "url": "https://www.amazon.com/dp/B09XYZ1234",
            "brand": None, "category": None, "seller_name": None,
            "availability": None, "is_prime": None, "description": None,
            "original_price": None, "image_url": None,
            "date_first_available": None, "scraped_at": "2024-01-01 00:00:00",
        }
        response = self.make_response(
            DETAIL_PAGE_HTML,
            meta={"product_id": "B09XYZ1234", "search_item": search_data},
        )
        results = []
        for item in spider.parse_product_detail(response):
            if isinstance(item, AmazonProductItem):
                results.append(item)

        assert "FREE delivery" in results[0]["availability"]

    
    def test_detects_prime_status(self, spider):
        search_data = {
            "asin": "B09XYZ1234", "title": "Test", "price": "$10.00",
            "rating": "4.0", "review_count": "100",
            "url": "https://www.amazon.com/dp/B09XYZ1234",
            "brand": None, "category": None, "seller_name": None,
            "availability": None, "is_prime": None, "description": None,
            "original_price": None, "image_url": None,
            "date_first_available": None, "scraped_at": "2024-01-01 00:00:00",
        }
        response = self.make_response(
            DETAIL_PAGE_HTML,
            meta={"product_id": "B09XYZ1234", "search_item": search_data},
        )
        results = []
        for item in spider.parse_product_detail(response):
            if isinstance(item, AmazonProductItem):
                results.append(item)

        assert results[0]["is_prime"] == "Yes"

    
    def test_handles_minimal_detail_page(self, spider):
        """Should not crash when detail page has minimal content."""
        search_data = {
            "asin": "B09XYZ1234", "title": "Test", "price": "$10.00",
            "rating": "4.0", "review_count": "100",
            "url": "https://www.amazon.com/dp/B09XYZ1234",
            "brand": None, "category": None, "seller_name": None,
            "availability": None, "is_prime": None, "description": None,
            "original_price": None, "image_url": None,
            "date_first_available": None, "scraped_at": "2024-01-01 00:00:00",
        }
        response = self.make_response(
            DETAIL_PAGE_MINIMAL,
            meta={"product_id": "B09XYZ1234", "search_item": search_data},
        )
        results = []
        for item in spider.parse_product_detail(response):
            if isinstance(item, AmazonProductItem):
                results.append(item)

        # Should still yield one item with search data preserved
        assert len(results) == 1
        assert results[0]["title"] == "Test"
        assert results[0]["brand"] is None
        assert results[0]["is_prime"] == "No"  # no prime icon

    
    def test_merges_search_and_detail_data(self, spider):
        search_data = {
            "asin": "B09XYZ1234",
            "title": "Original Search Title",
            "price": "$49.99",
            "rating": "4.5",
            "review_count": "1234",
            "url": "https://www.amazon.com/dp/B09XYZ1234",
            "brand": None,
            "category": None,
            "seller_name": "TestSeller",
            "availability": None,
            "is_prime": None,
            "description": None,
            "original_price": "$59.99",
            "image_url": "https://example.com/img.jpg",
            "date_first_available": None,
            "scraped_at": "2024-06-01 12:00:00",
        }
        response = self.make_response(
            DETAIL_PAGE_HTML,
            meta={"product_id": "B09XYZ1234", "search_item": search_data},
        )
        results = []
        for item in spider.parse_product_detail(response):
            if isinstance(item, AmazonProductItem):
                results.append(item)

        item = results[0]
        # Search page data preserved
        assert item["title"] == "Original Search Title"
        assert item["price"] == "$49.99"
        assert item["rating"] == "4.5"
        assert item["review_count"] == "1234"
        assert item["original_price"] == "$59.99"
        assert item["image_url"] == "https://example.com/img.jpg"
        # Detail page data added
        assert item["brand"] == "BrandName"
        assert item["category"] == "Electronics > Headphones"
        assert item["date_first_available"] == "January 15, 2024"


# ---------------------------------------------------------------------------
# Request creation
# ---------------------------------------------------------------------------

class TestRequestCreation:
    @pytest.fixture
    def spider(self):
        return AdvancedAmazonSpider()

    def test_build_request_has_referer_header(self, spider):
        req = spider._build_request(
            "https://www.amazon.com/s?k=laptop&page=1",
            callback=spider.parse,
        )
        assert req.headers["Referer"] == b"https://www.google.com/"

    def test_build_detail_request_dont_filter(self, spider):
        req = spider._build_detail_request(
            "https://www.amazon.com/dp/B09XYZ1234", "B09XYZ1234", {}
        )
        assert req.dont_filter is True
        assert req.meta["product_id"] == "B09XYZ1234"

    def test_start_requests_yields_pages(self, spider):
        spider.keyword = "laptop"
        spider.max_pages = 3
        requests = list(spider._build_start_requests())
        assert len(requests) == 3
        for i, req in enumerate(requests, 1):
            assert f"page={i}" in req.url
