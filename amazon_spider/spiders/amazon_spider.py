import re
import random
import asyncio
from datetime import datetime

import scrapy
from scrapy_playwright.page import PageMethod
from fake_useragent import UserAgent

from amazon_spider.items import AmazonProductItem


class AdvancedAmazonSpider(scrapy.Spider):
    name = "amazon"
    allowed_domains = ["amazon.com"]

    custom_settings = {
        "PLAYWRIGHT_BROWSER_TYPE": "chromium",
        "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 60000,
        "PLAYWRIGHT_LAUNCH_OPTIONS": {
            "headless": True,
            "timeout": 30000,
            "args": [
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--disable-web-security",
                "--disable-features=VizDisplayCompositor",
                "--disable-setuid-sandbox",
                "--disable-accelerated-2d-canvas",
                "--no-first-run",
                "--no-zygote",
                "--disable-gpu",
                "--disable-extensions",
                "--disable-extensions-except=",
                "--disable-plugins-discovery",
                "--start-maximized",
                "--disable-background-tasks",
                "--disable-backgrounding-occluded-windows",
                "--disable-renderer-backgrounding",
                "--no-default-browser-check",
                "--disable-default-apps",
                "--disable-ipc-flooding-protection",
                "--disable-background-networking"
            ]
        },
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 10,
        "RANDOMIZE_DOWNLOAD_DELAY": 0.5
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # 配置参数
        self.min_wait_time = 3
        self.max_wait_time = 8
        self.scroll_wait_time = 3000
        self.retry_times = 3

        # 初始化User-Agent生成器
        try:
            self.ua = UserAgent()
        except:
            self.user_agents = [
                # Chrome 130 — Windows / Mac / Linux
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
                'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
                # Edge 130
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0',
                # Firefox 132
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:132.0) Gecko/20100101 Firefox/132.0',
                # Safari 17
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15',
            ]

        # 请求计数器（用于控制请求频率）
        self.request_count = 0
        self.max_requests_per_minute = 10

    def get_random_user_agent(self):
        """获取随机User-Agent"""
        try:
            return self.ua.random
        except:
            return random.choice(self.user_agents)

    def start_requests(self):
        search_terms = getattr(self, 'keyword', 'laptop')
        pages = int(getattr(self, 'max_pages', 2))

        for page in range(1, pages + 1):
            url = f"https://www.amazon.com/s?k={search_terms}&page={page}"
            yield self.create_request(url)

    def create_request(self, url):
        """创建带反爬策略的请求"""
        self.request_count += 1

        headless = getattr(self, 'headless', True)
        # 请求元数据
        meta = {
            "playwright": True,
            "playwright_page_coroutines": [
                PageMethod("wait_for_load_state", "networkidle"),
                PageMethod("wait_for_selector", "[data-component-type='s-search-result']"),
            ],
            "playwright_context_kwargs": {
                "user_agent": self.get_random_user_agent(),
                "java_script_enabled": True,
                "viewport": {
                    "width": random.randint(1280, 1920),
                    "height": random.randint(720, 1080)
                }
            },
            "playwright_launch_options": {
                "headless": headless,
            },
        }

        req = scrapy.Request(
            url,
            meta=meta,
            callback=self.parse,
            errback=self.errback_close_page,
            dont_filter=False
        )
        req.headers['Referer'] = 'https://www.google.com/'
        return req

    async def parse(self, response):
        self.logger.info(f"Parsing page: {response.url}")

        try:
            # 模拟随机停留时间，模拟人类行为
            await asyncio.sleep(random.uniform(self.min_wait_time, self.max_wait_time))

            # 模拟页面滚动行为
            if response.meta.get("playwright_page"):
                page = response.meta["playwright_page"]
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight/3);")
                await asyncio.sleep(random.uniform(1, 3))
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight*2/3);")
                await asyncio.sleep(random.uniform(1, 3))
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
                await asyncio.sleep(random.uniform(2, 4))

            # 获取所有商品项
            products = response.css("[data-component-type='s-search-result']")

            self.logger.info(f"Found {len(products)} products on page {response.url}")

            for product in products:
                try:
                    # 提取商品信息
                    product_id = product.css("::attr(data-asin)").get()
                    if not product_id:
                        continue

                    # 跳过广告产品
                    if product.css(".s-sponsored-faceout-badge-wrapper").get():
                        continue

                    # 商品名称
                    name = (product.css("h2 a span::text").get() or "").strip() or None

                    # 价格：优先 whole+fraction 拼接，fallback .a-offscreen
                    price_whole = (product.css(".a-price-whole::text").get() or "").strip()
                    price_fraction = (product.css(".a-price-fraction::text").get() or "").strip()
                    if price_whole:
                        whole_clean = re.sub(r'[^\d]', '', price_whole)
                        frac_clean = re.sub(r'[^\d]', '', price_fraction)
                        # Normalise to 2 decimal places — fraction may be truncated
                        frac_clean = frac_clean[:2].ljust(2, '0')
                        price = f"${whole_clean}.{frac_clean}"
                    else:
                        price_off = product.css(".a-offscreen::text").get()
                        price = price_off.strip() if price_off else None

                    # 评分 — 优先 aria-label，fallback 到 .a-icon-alt
                    rating = None
                    rating_aria = product.css("span[aria-label*='out of']::attr(aria-label)").get()
                    if rating_aria:
                        rating = rating_aria.strip()
                    else:
                        rating_alt = product.css(".a-icon-alt::text").get()
                        if rating_alt:
                            m = re.search(r'[\d.]+', rating_alt)
                            if m:
                                rating = m.group()

                    # 评论数
                    review_count_text = product.css("span[aria-label*='ratings']::text").get()
                    if review_count_text:
                        review_count = ''.join(filter(str.isdigit, review_count_text)) or None
                    else:
                        review_count_match = product.css("a[role='link'] span::text").re(r'\d+,\d+|\d+')
                        review_count = ''.join(filter(str.isdigit, review_count_match[0])) if review_count_match else None

                    # 构建商品详情页URL
                    product_url = product.css("h2 a::attr(href)").get()
                    if product_url:
                        product_url = response.urljoin(product_url)
                    else:
                        product_url = None

                    if product_id and name:
                        item = AmazonProductItem()
                        item['asin'] = product_id
                        item['title'] = name
                        item['price'] = price
                        item['rating'] = rating
                        item['review_count'] = review_count
                        item['url'] = product_url
                        item['brand'] = None
                        item['category'] = None
                        item['seller_name'] = None
                        item['availability'] = None
                        item['is_prime'] = None
                        item['description'] = None
                        item['original_price'] = None
                        item['image_url'] = None
                        item['date_first_available'] = None
                        item['scraped_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                        self.logger.info(f"Yielded partial item: {name[:50]}... (ASIN: {product_id})")

                        # yield 搜索页部分数据，标记为 partial
                        yield item

                        # 请求商品详情页以获取更多信息
                        yield self.create_product_detail_request(product_url, product_id, item)

                except Exception as e:
                    self.logger.error(f"Error parsing product on {response.url}: {str(e)}")
                    continue

            # 处理分页 - 尝试获取下一页链接
            next_page = response.css('a[aria-label="Next page"]::attr(href)').get()
            if not next_page:
                next_page = response.css('li.a-last a::attr(href)').get()

            if next_page:
                next_page_url = response.urljoin(next_page)
                yield self.create_request(next_page_url)

        except Exception as e:
            self.logger.error(f"Error parsing page {response.url}: {str(e)}")

    def create_product_detail_request(self, url, product_id, search_item):
        """创建商品详情页请求"""
        self.request_count += 1
        headless = getattr(self, 'headless', True)

        meta = {
            "playwright": True,
            "playwright_page_coroutines": [
                PageMethod("wait_for_load_state", "networkidle"),
                PageMethod("wait_for_selector", "#productTitle"),
            ],
            "playwright_context_kwargs": {
                "user_agent": self.get_random_user_agent(),
                "java_script_enabled": True,
                "viewport": {
                    "width": random.randint(1280, 1920),
                    "height": random.randint(720, 1080)
                }
            },
            "playwright_launch_options": {
                "headless": headless,
            },
            "product_id": product_id,
            "search_item": dict(search_item),
        }

        req = scrapy.Request(
            url=url,
            meta=meta,
            callback=self.parse_product_detail,
            errback=self.errback_close_page,
            dont_filter=True
        )
        req.headers['Referer'] = 'https://www.amazon.com/'
        return req

    async def parse_product_detail(self, response):
        """解析商品详情页"""
        product_id = response.meta.get("product_id")
        search_data = response.meta.get("search_item", {})
        self.logger.info(f"Parsing product detail: {response.url}")

        try:
            # 模拟人类行为 - 随机等待和页面交互
            await asyncio.sleep(random.uniform(2, 5))

            # 模拟页面滚动
            if response.meta.get("playwright_page"):
                page = response.meta["playwright_page"]
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight/4);")
                await asyncio.sleep(random.uniform(1, 2))
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight/2);")
                await asyncio.sleep(random.uniform(1, 2))
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
                await asyncio.sleep(random.uniform(2, 3))

            # 提取品牌
            brand = None
            brand_text = response.css("#bylineInfo::text").get()
            if brand_text:
                brand = brand_text.strip()
            if not brand:
                brand_text = response.css("#brand ::text").get()
                if brand_text:
                    brand = brand_text.strip()
            if not brand:
                brand_elements = response.css("#bylineInfo-container a, #bylineInfo a")
                if brand_elements:
                    brand = (brand_elements[0].css("::text").get() or "").strip() or None

            # 提取分类
            category = None
            breadcrumb_items = response.css("#wayfinding-breadcrumbs_feature_div ul li span a::text").getall()
            if breadcrumb_items:
                category = " > ".join([item.strip() for item in breadcrumb_items if item.strip()]) or None

            # 提取上架时间
            date_info = None
            date_text = response.css("#productDetails_detailBullets_sections1 td:contains('Date First Available') + td::text").get()
            if date_text:
                date_info = date_text.strip()
            if not date_info:
                date_labels = response.css("div.content ul li span::text").getall()
                for i, label in enumerate(date_labels):
                    if label and 'Date First Available' in label:
                        date_info = response.css(f"div.content ul li span::text")[i+1].get()
                        if date_info:
                            date_info = date_info.strip()
                        break
            if not date_info:
                date_match = response.css("#detailBullets_feature_div ul li span[dir='auto']::text").re(r'Date First Available.*?(\w+ \d+, \d{4}|\w+ \d{4})')
                if date_match:
                    date_info = date_match[0]

            # 提取配送信息
            shipping_info = response.css("#deliveryMessageMirId::text").get()
            if not shipping_info:
                shipping_info = response.css("#exportsBuyBox_feature_div span::text").get()
            if shipping_info:
                shipping_info = shipping_info.strip()
            if not shipping_info:
                shipping_info = None

            # 检查是否Prime商品
            is_prime = "Yes" if response.css(".a-icon-prime").get() else "No"

            # 合并搜索页数据 + 详情页数据，yield 完整 Item
            item = AmazonProductItem()
            item['asin'] = search_data.get('asin')
            item['title'] = search_data.get('title')
            item['price'] = search_data.get('price')
            item['rating'] = search_data.get('rating')
            item['review_count'] = search_data.get('review_count')
            item['url'] = search_data.get('url')
            item['original_price'] = search_data.get('original_price')
            item['image_url'] = search_data.get('image_url')
            item['scraped_at'] = search_data.get('scraped_at')
            item['brand'] = brand
            item['category'] = category
            item['seller_name'] = search_data.get('seller_name')
            item['availability'] = shipping_info
            item['is_prime'] = is_prime
            item['description'] = None
            item['date_first_available'] = date_info

            self.logger.info(f"Yielded complete item for ASIN: {product_id}")
            yield item

            # 滚动页面以加载更多评论（如果需要）
            if response.meta.get("playwright_page"):
                await response.meta["playwright_page"].evaluate("window.scrollTo(0, document.body.scrollHeight);")
                await asyncio.sleep(2)

        except Exception as e:
            self.logger.error(f"Error parsing product detail {response.url}: {str(e)}")

    async def errback_close_page(self, failure):
        try:
            page = failure.request.meta.get("playwright_page")
            if page:
                await page.close()
            self.logger.error(f"Request failed: {failure.request.url} - {failure.value}")
        except Exception as e:
            self.logger.error(f"Error in errback: {str(e)}")
