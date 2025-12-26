# 配置说明

## 项目结构

```
amazon-data-collector/
├── advanced_amazon_spider.py    # 高级亚马逊爬虫（含反爬策略）
├── amazon_spider.py            # 基础亚马逊爬虫
├── data_validator.py           # 数据验证和质量监控
├── main.py                    # 主程序入口
├── proxy_manager.py            # 代理池管理
├── settings.py                 # Scrapy配置文件
├── celery_config.py            # Celery配置
├── celery_tasks.py             # Celery任务定义
├── test_system.py              # 系统测试
├── requirements.txt            # 依赖包列表
├── README.md                   # 项目说明
├── LICENSE                     # 许可证
├── setup.py                    # 安装配置
├── .gitignore                  # Git忽略文件
├── docs/                       # 文档目录
│   ├── README.md               # 文档目录
│   ├── architecture.md         # 系统架构
│   ├── installation.md         # 安装指南
│   ├── usage.md                # 使用说明
│   └── configuration.md        # 配置说明
└── example.png                 # 示例截图
```

## 核心配置文件详解

### 1. settings.py (Scrapy配置)

#### 基础设置
```python
BOT_NAME = 'amazon_scraper'  # 爬虫名称
SPIDER_MODULES = ['amazon_spider', 'advanced_amazon_spider']  # 爬虫模块
NEWSPIDER_MODULE = 'spiders'  # 新爬虫模块位置
ROBOTSTXT_OBEY = False  # 不遵守robots.txt
```

#### 并发与延迟设置
```python
CONCURRENT_REQUESTS = 1  # 并发请求数
DOWNLOAD_DELAY = 10  # 下载延迟（秒）
RANDOMIZE_DOWNLOAD_DELAY = 0.5  # 随机延迟比例
```

#### Playwright设置
```python
PLAYWRIGHT_BROWSER_TYPE = "chromium"  # 浏览器类型
PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT = 60000  # 导航超时（毫秒）
PLAYWRIGHT_LAUNCH_OPTIONS = {  # 启动参数
    "headless": True,  # 无头模式
    "timeout": 30000,  # 超时时间
    "args": [
        "--no-sandbox",
        "--disable-blink-features=AutomationControlled",
        # 更多反检测参数...
    ]
}
```

#### 重试设置
```python
RETRY_TIMES = 5  # 重试次数
RETRY_HTTP_CODES = [500, 502, 503, 504, 408, 429, 403]  # 重试HTTP状态码
```

### 2. advanced_amazon_spider.py (爬虫配置)

#### 初始化参数
```python
self.min_wait_time = 10  # 最小等待时间（秒）
self.max_wait_time = 15  # 最大等待时间（秒）
self.scroll_wait_time = 3000  # 滚动等待时间（毫秒）
self.retry_times = 5  # 重试次数
```

#### 代理池配置
```python
self.proxies = [
    # 配置代理服务器
    # 'http://username:password@proxy_host:proxy_port',
]
```

#### 输出字段配置
```python
self.worksheet.append([
    "商品ID", "商品名称", "价格", "销量", "评分", "评论数", 
    "品牌", "类别", "上架时间", "采集时间", "URL", "配送信息", "是否Prime"
])
```

### 3. proxy_manager.py (代理管理配置)

#### 代理管理器
```python
class ProxyManager:
    def __init__(self, proxy_list=None):
        # 初始化代理列表
        # 代理测试和轮换机制
```

#### 亚马逊专用代理管理器
```python
class AmazonProxyManager(ProxyManager):
    def test_proxy_for_amazon(self, proxy, timeout=10):
        # 专门测试亚马逊访问的代理
```

### 4. data_validator.py (数据验证配置)

#### 数据验证规则
```python
validation_rules = {
    'product_id': self.validate_product_id,      # 商品ID验证
    'name': self.validate_name,                  # 商品名称验证
    'price': self.validate_price,                # 价格验证
    'rating': self.validate_rating,              # 评分验证
    'review_count': self.validate_review_count,  # 评论数验证
    'brand': self.validate_brand,                # 品牌验证
    'category': self.validate_category           # 分类验证
}
```

#### 数据质量监控
```python
class DataQualityMonitor:
    def __init__(self, min_quality_score: float = 98.0):
        # 最小质量分数（98%）
```

### 5. celery_config.py (任务调度配置)

#### Celery配置
```python
app.config_from_object({
    'broker_url': 'redis://localhost:6379/0',      # Redis连接
    'result_backend': 'redis://localhost:6379/0',  # 结果存储
    'task_serializer': 'json',                      # 任务序列化
    'result_serializer': 'json',                    # 结果序列化
    'timezone': 'UTC',                             # 时区
    'beat_schedule': {                             # 定时任务
        'daily-amazon-scraper': {
            'task': 'celery_tasks.run_amazon_scraping',
            'schedule': 86400.0,  # 每天执行
        },
    },
})
```

## 环境变量配置

### 1. 系统环境变量

#### Windows
```cmd
set PYTHONPATH=%PYTHONPATH%;C:\path\to\project
set SCRAPY_SETTINGS_MODULE=your_project.settings
```

#### Linux/macOS
```bash
export PYTHONPATH="${PYTHONPATH}:/path/to/project"
export SCRAPY_SETTINGS_MODULE="your_project.settings"
```

### 2. 配置文件优先级

配置优先级（从高到低）：
1. 命令行参数
2. 爬虫内部设置 (custom_settings)
3. settings.py 文件
4. Scrapy默认设置

## 性能调优配置

### 1. 内存管理
```python
# settings.py
MEMUSAGE_ENABLED = True
MEMUSAGE_LIMIT_MB = 2048  # 内存限制（MB）
MEMUSAGE_WARNING_MB = 1024  # 内存警告（MB）
```

### 2. 自动限速
```python
# settings.py
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 10  # 初始延迟
AUTOTHROTTLE_MAX_DELAY = 120   # 最大延迟
AUTOTHROTTLE_TARGET_CONCURRENCY = 0.5  # 目标并发数
```

### 3. 下载器中间件
```python
DOWNLOADER_MIDDLEWARES = {
    'scrapy.downloadermiddlewares.useragent.UserAgentMiddleware': None,
    'scrapy.downloadermiddlewares.retry.RetryMiddleware': None,
    'scrapy_fake_useragent.middleware.RandomUserAgentMiddleware': 400,
    'scrapy_fake_useragent.middleware.RetryMiddleware': 401,
}
```

## 安全配置

### 1. 请求头配置
```python
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
   'DNT': '1'  # Do Not Track
}
```

### 2. 反爬策略配置
- User-Agent轮换
- 请求频率控制
- 浏览器指纹伪装
- 行为模拟

## 自定义配置

### 1. 扩展配置

可以创建自定义配置文件：
```python
# custom_settings.py
CUSTOM_DOWNLOAD_DELAY = 15
CUSTOM_CONCURRENT_REQUESTS = 1
CUSTOM_USER_AGENTS = [
    'Custom Browser 1.0',
    'Another Custom Browser 2.0'
]
```

### 2. 配置验证

系统包含配置验证机制：
- 参数类型检查
- 数值范围验证
- 依赖关系检查

## 配置最佳实践

1. **安全性**: 不在代码中硬编码敏感信息
2. **可维护性**: 配置参数化，便于修改
3. **性能**: 合理设置并发数和延迟时间
4. **可靠性**: 配置重试机制和错误处理
5. **可扩展性**: 模块化配置，便于扩展

## 故障排除

### 1. 配置错误检查
- 检查参数类型和格式
- 验证依赖项是否正确配置
- 确认文件路径和权限

### 2. 性能问题排查
- 检查并发设置是否过高
- 验证延迟时间是否合理
- 确认代理配置是否有效