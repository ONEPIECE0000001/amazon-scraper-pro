# 配置说明

## 项目结构

```
python-amazon-spider/
├── amazon_spider/
│   ├── items.py                       # Item 数据模型
│   ├── pipelines.py                   # 数据处理管道
│   ├── spiders/amazon_spider.py       # 主爬虫
│   └── middlewares/
│       ├── stealth_middleware.py      # 反检测注入
│       ├── retry_middleware.py        # 重试中间件
│       └── proxy_middleware.py        # 代理中间件
│
├── settings.py                        # Scrapy 全局配置
├── main.py                            # CLI 入口
├── proxy_pool.py                      # 代理池
├── celery_config.py                   # Celery 配置
├── celery_tasks.py                    # Celery 任务
├── logging_config.py                  # 日志配置
├── .env.example                       # 环境变量模板
│
├── tests/                             # 单元测试
├── docs/                              # 文档
│
├── Dockerfile                         # Docker
├── .pre-commit-config.yaml            # pre-commit
└── pyproject.toml                     # pytest + ruff + mypy
```

## settings.py — Scrapy 全局配置

### 请求控制

```python
CONCURRENT_REQUESTS = 1        # 单并发（反爬核心）
DOWNLOAD_DELAY = 10            # 请求间隔 10s
RANDOMIZE_DOWNLOAD_DELAY = 0.5 # ±50% 随机化
ROBOTSTXT_OBEY = False         # 不遵守 robots.txt（环境变量可控）
COOKIES_ENABLED = False        # 禁用 cookie
```

### 中间件注册

```python
DOWNLOADER_MIDDLEWARES = {
    'amazon_spider.middlewares.stealth_middleware.PlaywrightStealthMiddleware': 543,
    'amazon_spider.middlewares.retry_middleware.ExponentialRetryMiddleware': 550,
    'amazon_spider.middlewares.proxy_middleware.ProxyMiddleware': 750,
}
```

优先级：Stealth(543) → Retry(550) → Proxy(750)，数值越低越先执行。

### Pipeline 注册

```python
ITEM_PIPELINES = {
    'amazon_spider.pipelines.DataCleaningPipeline': 100,
    'amazon_spider.pipelines.DeduplicationPipeline': 200,
    'amazon_spider.pipelines.MySQLPipeline': 300,
}
```

数据流：清洗(100) → 去重(200) → MySQL(300)。

### MySQL 配置

```python
MYSQL_HOST = os.environ.get('MYSQL_HOST', 'localhost')
MYSQL_PORT = int(os.environ.get('MYSQL_PORT', '3306'))
MYSQL_USER = os.environ.get('MYSQL_USER', 'root')
MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD', '')
MYSQL_DATABASE = os.environ.get('MYSQL_DATABASE', 'amazon_scraper')
```

所有值均可通过 `.env` 环境变量覆盖。

### Playwright 配置

```python
PLAYWRIGHT_BROWSER_TYPE = "chromium"
PLAYWRIGHT_LAUNCH_OPTIONS = {
    "headless": True,
    "args": [
        "--no-sandbox",
        "--disable-blink-features=AutomationControlled",
        # ... 20 项反检测 flag
    ]
}
PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT = 60000
```

## amazon_spider/spiders/amazon_spider.py — 爬虫配置

### 类变量

```python
name = "amazon"
custom_settings = {
    "PLAYWRIGHT_BROWSER_TYPE": "chromium",
    "CONCURRENT_REQUESTS": 1,
    "DOWNLOAD_DELAY": 10,
}
```

### 实例参数（`__init__`）

```python
self.min_wait_time = 3      # 搜索页最小等待 (秒)
self.max_wait_time = 8      # 搜索页最大等待 (秒)
self.scroll_wait_time = 3000 # 滚动间隔 (毫秒)
self.retry_times = 3        # 最大重试次数
```

## proxy_pool.py — 代理池配置

### 代理来源

```python
PROXY_SOURCES = [
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
    "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt",
    "https://raw.githubusercontent.com/hookzof/socks5_list/master/proxy.txt",
]
```

### 验证配置

```python
TEST_URL = "http://httpbin.org/ip"  # 验证目标
# 验证超时: 5s
# 验证线程: 20
```

### 选择策略

按延迟倒数加权随机：`weight = 1.0 / latency`，低延迟代理更高概率被选中。

## celery_config.py — 调度配置

```python
app.config_from_object({
    'broker_url': 'redis://localhost:6379/0',
    'result_backend': 'redis://localhost:6379/0',
    'beat_schedule': {
        'daily-amazon-scraper': {
            'task': 'celery_tasks.run_amazon_scraping',
            'schedule': 86400.0,  # 24h
        },
    },
})
```

## 环境变量一览

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `MYSQL_ENABLED` | 启用 MySQL Pipeline | True |
| `MYSQL_HOST` | MySQL 主机 | localhost |
| `MYSQL_PORT` | MySQL 端口 | 3306 |
| `MYSQL_USER` | MySQL 用户 | root |
| `MYSQL_PASSWORD` | MySQL 密码 | (空) |
| `MYSQL_DATABASE` | MySQL 数据库 | amazon_scraper |
| `PROXY_ENABLED` | 启用代理池 | True |
| `ROBOTSTXT_OBEY` | 遵守 robots.txt | False |
| `CUSTOM_PROXIES` | 自定义代理列表 | (空) |
| `LOG_LEVEL` | 日志级别 | INFO |
| `LOG_FILE` | 日志文件路径 | (空, 仅控制台) |
