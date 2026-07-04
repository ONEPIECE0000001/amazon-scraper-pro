# Scrapy settings for amazon_scraper project
#
# For simplicity, this file contains only settings considered important or
# commonly used. You can find more settings consulting the documentation:
#
#     https://docs.scrapy.org/en/latest/topics/settings.html
#     https://docs.scrapy.org/en/latest/topics/downloader-middleware.html
#     https://docs.scrapy.org/en/latest/topics/spider-middleware.html

import os

BOT_NAME = 'amazon_scraper'

SPIDER_MODULES = ['amazon_spider.spiders']


# Crawl responsibly by identifying yourself (and your website) on the user-agent
#USER_AGENT = 'amazon_scraper (+http://www.yourdomain.com)'

# ---------------------------------------------------------------------------
# robots.txt compliance (IMPORTANT — read before enabling)
# ---------------------------------------------------------------------------
# Amazon's robots.txt blocks automated crawlers on most paths.  Setting this
# to True will make the spider respect those directives and likely collect
# no data at all.
#
# **Legal / compliance risk**: setting this to False means the spider WILL
# ignore robots.txt.  Depending on your jurisdiction and use case this may
# violate Amazon's ToS.  Consult your legal counsel before deploying.
#
# The default is False so the spider is functional out of the box, but you
# can override it via the ROBOTSTXT_OBEY environment variable.
# ---------------------------------------------------------------------------
ROBOTSTXT_OBEY = os.environ.get(
    'ROBOTSTXT_OBEY', 'False'
).strip().lower() in ('1', 'true', 'yes')

# Configure maximum concurrent requests performed by Scrapy (default: 16)
CONCURRENT_REQUESTS = 1

# Configure a delay for requests for the same website (default: 0)
# See https://docs.scrapy.org/en/latest/topics/settings.html#download-delay
# See also autothrottle settings and docs
DOWNLOAD_DELAY = 10
RANDOMIZE_DOWNLOAD_DELAY = 0.5
# The download delay setting will honor only one of:
#CONCURRENT_REQUESTS_PER_DOMAIN = 16
#CONCURRENT_REQUESTS_PER_IP = 16

# Disable cookies (enabled by default)
COOKIES_ENABLED = False

# Disable Telnet Console (enabled by default)
#TELNETCONSOLE_ENABLED = False

# Override the default request headers:
DEFAULT_REQUEST_HEADERS = {
   'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
   'Accept-Language': 'en-US,en;q=0.9',
   'Accept-Encoding': 'gzip, deflate, br',
   'Connection': 'keep-alive',
   'Upgrade-Insecure-Requests': '1',
   'Sec-Fetch-Dest': 'document',
   'Sec-Fetch-Mode': 'navigate',
   'Sec-Fetch-Site': 'none',
   'Cache-Control': 'max-age=0',
   'DNT': '1'
}

# Enable or disable spider middlewares
# See https://docs.scrapy.org/en/latest/topics/spider-middleware.html
#SPIDER_MIDDLEWARES = {
#    'amazon_scraper.middlewares.AmazonScraperSpiderMiddleware': 543,
#}

# Enable or disable downloader middlewares
# See https://docs.scrapy.org/en/latest/topics/downloader-middleware.html

# Proxy middleware — set PROXY_ENABLED = False to disable proxy injection
PROXY_ENABLED = True

DOWNLOADER_MIDDLEWARES = {
    'scrapy.downloadermiddlewares.useragent.UserAgentMiddleware': None,
    'scrapy.downloadermiddlewares.retry.RetryMiddleware': None,
    'scrapy_fake_useragent.middleware.RandomUserAgentMiddleware': 400,
    'scrapy_fake_useragent.middleware.RetryMiddleware': 401,
    'amazon_spider.middlewares.stealth_middleware.PlaywrightStealthMiddleware': 543,
    'amazon_spider.middlewares.retry_middleware.ExponentialRetryMiddleware': 550,
    'amazon_spider.middlewares.proxy_middleware.ProxyMiddleware': 750,
}

# Enable or disable extensions
# See https://docs.scrapy.org/en/latest/topics/extensions.html
#EXTENSIONS = {
#    'scrapy.extensions.telnet.TelnetConsole': None,
#}

# Configure item pipelines
# See https://docs.scrapy.org/en/latest/topics/item-pipeline.html
ITEM_PIPELINES = {
    'amazon_spider.pipelines.DataCleaningPipeline': 100,
    'amazon_spider.pipelines.DeduplicationPipeline': 200,
    'amazon_spider.pipelines.MySQLPipeline': 300,
}

# Enable and configure the AutoThrottle extension (disabled by default)
# See https://docs.scrapy.org/en/latest/topics/autothrottle.html
AUTOTHROTTLE_ENABLED = True
# The initial download delay
AUTOTHROTTLE_START_DELAY = 10
# The maximum download delay to be set in case of high latencies
AUTOTHROTTLE_MAX_DELAY = 120
# The average number of requests Scrapy should be sending in parallel to
# each remote server
AUTOTHROTTLE_TARGET_CONCURRENCY = 0.5
# Enable showing throttling stats for every response received:
#AUTOTHROTTLE_DEBUG = False

# Enable and configure HTTP caching (disabled by default)
# See https://docs.scrapy.org/en/latest/topics/downloader-middleware.html#httpcache-middleware-settings
#HTTPCACHE_ENABLED = True
#HTTPCACHE_EXPIRATION_SECS = 0
#HTTPCACHE_DIR = 'httpcache'
#HTTPCACHE_IGNORE_HTTP_CODES = []
#HTTPCACHE_STORAGE = 'scrapy.extensions.httpcache.FilesystemCacheStorage'

# Playwright settings
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
DOWNLOAD_HANDLERS = {
    "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
    "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
}

PLAYWRIGHT_BROWSER_TYPE = "chromium"
PLAYWRIGHT_LAUNCH_OPTIONS = {
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
}
PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT = 60000
PLAYWRIGHT_MAX_PAGES_PER_CONTEXT = 10

# Custom settings for anti-detection
USER_AGENT_CHOICES = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:132.0) Gecko/20100101 Firefox/132.0',
    'Mozilla/5.0 (X11; Linux i686; rv:132.0) Gecko/20100101 Firefox/132.0'
]

# Retry settings
RETRY_TIMES = 3
RETRY_HTTP_CODES = [500, 502, 503, 504, 408, 429, 403]

# Memory usage settings
MEMUSAGE_ENABLED = True
MEMUSAGE_LIMIT_MB = 2048
MEMUSAGE_NOTIFY_MAIL = ['admin@example.com']
MEMUSAGE_WARNING_MB = 1024

# ---------------------------------------------------------------------------
# MySQL pipeline — credentials are read from environment variables with
# sensible defaults for local development.
# ---------------------------------------------------------------------------
MYSQL_ENABLED = os.environ.get('MYSQL_ENABLED', 'True').lower() in ('1', 'true', 'yes')
MYSQL_HOST = os.environ.get('MYSQL_HOST', 'localhost')
MYSQL_PORT = int(os.environ.get('MYSQL_PORT', '3306'))
MYSQL_USER = os.environ.get('MYSQL_USER', 'root')
MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD', '')
MYSQL_DATABASE = os.environ.get('MYSQL_DATABASE', 'amazon_scraper')

# ---------------------------------------------------------------------------
# CSV export via Scrapy FEEDS — always active regardless of MySQL status
# ---------------------------------------------------------------------------
FEEDS = {
    'output/amazon_%(time)s.csv': {
        'format': 'csv',
        'encoding': 'utf-8',
    }
}
