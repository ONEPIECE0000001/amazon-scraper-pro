# 使用说明

## 基本命令

```bash
# 单次采集
python main.py --keyword "laptop" --pages 2

# 显示浏览器窗口（调试用）
python main.py --keyword "laptop" --pages 2 --show-browser

# 不使用代理
python main.py --keyword "headphones" --pages 3 --no-proxy
```

### 参数说明

| 参数 | 简写 | 说明 | 默认值 |
|------|------|------|--------|
| `--keyword` | `-k` | 搜索关键词（必填） | — |
| `--pages` | `-p` | 爬取页数 | 2 |
| `--show-browser` | — | 显示浏览器窗口（非无头模式） | False |
| `--no-proxy` | — | 禁用代理池 | False |

### 输出说明

采集结果输出到 `output/` 目录，文件命名为 `amazon_<关键词>_<时间戳>.csv`。

启动时终端会显示代理池状态和 MySQL 连接状态。

## 定时调度

### 启动

```bash
celery -A celery_tasks worker --loglevel=info --beat
```

每天自动执行一次（86400 秒周期）。

### 修改调度参数

编辑 `celery_config.py`：

```python
'beat_schedule': {
    'daily-amazon-scraper': {
        'task': 'celery_tasks.run_amazon_scraping',
        'schedule': 86400.0,          # 周期（秒）
        'args': ('laptop', 5),         # (关键词, 页数)
    },
},
```

## 代理配置

### 使用免费代理（默认）

无需任何配置。系统自动从 GitHub 免费代理源获取并验证。

### 使用付费代理

在 `.env` 中配置（复制 `.env.example` → `.env`）：

```
CUSTOM_PROXIES=http://user:pass@proxy1.com:8080,socks5://10.0.0.1:1080
```

支持 `http://`、`https://`、`socks5://`、`socks4://` 格式，逗号分隔多个。

### 完全禁用代理

```bash
python main.py --keyword "laptop" --no-proxy
```

## 爬虫参数调整

编辑 `amazon_spider/spiders/amazon_spider.py` 中 `__init__` 的参数：

```python
self.min_wait_time = 3       # 搜索页最小等待 (秒)
self.max_wait_time = 8       # 搜索页最大等待 (秒)
self.retry_times = 3         # 最大重试次数
self.scroll_wait_time = 3000 # 滚动间隔 (毫秒)
```

## 数据输出格式

CSV 文件包含 16 个字段：

| 字段 | 说明 |
|------|------|
| `asin` | ASIN 码 |
| `title` | 商品标题 |
| `price` | 当前价格 (USD) |
| `original_price` | 原价 |
| `rating` | 评分 (0-5) |
| `review_count` | 评论数 |
| `brand` | 品牌 |
| `category` | 分类路径 |
| `availability` | 配送信息 |
| `is_prime` | Prime 状态 |
| `url` | 商品链接 |
| `image_url` | 主图链接 |
| `description` | 描述 |
| `date_first_available` | 上架日期 |
| `scraped_at` | 采集时间 |
| `seller_name` | 卖家名称 |

## 数据验证

```bash
# 通过脚本验证 CSV 数据质量
python -c "
from data_validator import validate_amazon_data_file
validate_amazon_data_file('output/amazon_laptop_20260101.csv')
"
```

## 日志

所有模块使用 `logging_config.py` 统一管理日志：

```bash
# 只显示 WARNING 及以上
set LOG_LEVEL=WARNING && python main.py --keyword "test" --pages 1

# 同时写入文件
set LOG_FILE=spider.log && python main.py --keyword "test" --pages 1
```

## 监控与调试

```bash
# 开启 Scrapy 详细日志
scrapy crawl amazon -a keyword=laptop -a max_pages=1 -L DEBUG

# 运行测试
pytest tests/ -v
python test_system.py
```

## 故障排除

| 症状 | 可能原因 | 解决 |
|------|----------|------|
| 503 / CAPTCHA 页面 | 触发反爬 | 增加延迟、换代理、启用 stealth |
| 代理池为空 | 免费源不可达 | 配置 `CUSTOM_PROXIES` 付费代理 |
| 数据不完整 | Amazon 页面结构变动 | 更新 CSS 选择器 |
| Celery 无法启动 | Redis 未运行 | `docker run -d -p 6379:6379 redis` |
| CSV 为空 | 请求被拦截 | 检查代理状态，尝试 `--show-browser` |
