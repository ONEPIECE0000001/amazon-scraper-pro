# Amazon Scraper Pro 亚马逊商品数据采集

<div align="center">

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue)](https://www.python.org/)
[![Scrapy](https://img.shields.io/badge/Scrapy-2.13%2B-green)](https://scrapy.org/)
[![Playwright](https://img.shields.io/badge/Playwright-1.40%2B-brightgreen)](https://playwright.dev/)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)
[![Maintenance](https://img.shields.io/badge/Maintenance-Active-green)]()

**专业的亚马逊商品数据采集解决方案 | 智能反爬 | Pipeline 架构 | 自动化调度**

</div>

## 项目概述

本项目是基于原始项目独立优化的版本，面向市场调研公司的自动化数据采集系统，用于监测亚马逊平台的商品价格波动、用户评论趋势和促销活动。基于 Scrapy Item Pipeline 架构，支持 Playwright 动态渲染、多层反爬策略、数据质量保障和 Celery 定时调度。

**🔧 独立优化特色**

- 全面升级至 Scrapy 2.13+，采用新的 `async def start()` 入口
- 增强反爬策略，优化页面交互模拟
- 改进数据清洗 Pipeline，提升数据质量
- 优化用户代理管理，提高稳定性

**⚠️ 声明**

本项目为完全独立的开源项目，所有代码和优化均为原创开发。

## 核心功能

- **智能数据采集** — Playwright 渲染 + 搜索页/详情页两级采集
- **高级反爬策略** — stealth.js 注入、UA 轮换、随机延迟、模拟滚动
- **数据质量保障** — 清洗 → 去重 → MySQL 三阶段 Pipeline
- **代理管理** — GitHub 免费源自动获取 + 多线程验证 + 加权选择
- **自动化调度** — Celery Beat 86400s 周期，无人值守
- **151 单元测试** — 爬虫/中间件/验证器/代理池全覆盖

## 快速开始

### 安装

```bash
pip install -r requirements.txt
playwright install chromium
```

### 单次采集

```bash
# 搜索 "laptop"，爬 2 页
python main.py --keyword "laptop" --pages 2

# 显示浏览器窗口
python main.py --keyword "iPhone 15" --pages 5 --show-browser

# 不用代理
python main.py --keyword "headphones" --pages 3 --no-proxy
```

输出文件：`output/amazon_<关键词>_<时间戳>.csv`

### 定时调度（需 Redis）

```bash
# 启动 Redis
docker run --name redis -p 6379:6379 -d redis:latest

# 启动 Celery 定时任务（每天采集一次）
celery -A celery_tasks worker --loglevel=info --beat
```

### 运行测试

```bash
pytest tests/ -v       # 151 单元测试
python test_system.py  # 集成冒烟测试
```

## 项目结构

```
python-amazon-spider/
├── amazon_spider/                     # Scrapy 核心包
│   ├── items.py                       #   AmazonProductItem (16 字段)
│   ├── pipelines.py                   #   清洗 → 去重 → MySQL
│   ├── spiders/amazon_spider.py       #   主爬虫 (搜索 + 详情)
│   └── middlewares/
│       ├── stealth_middleware.py      #   playwright-stealth 注入
│       ├── retry_middleware.py        #   指数退避 + 反爬关键词检测
│       └── proxy_middleware.py        #   代理注入 + 故障切换
│
├── main.py                            # CLI 入口
├── settings.py                        # Scrapy 全局配置
├── proxy_pool.py                      # 代理池 (免费源获取 + 验证)
├── data_validator.py                  # 数据验证 + 质量监控
├── celery_config.py                   # Celery 调度配置
├── celery_tasks.py                    # Celery 任务定义
├── logging_config.py                  # 统一日志配置
│
├── tests/                             # 单元测试 (151 用例)
│   ├── test_pipelines.py              #   16 — Pipeline 清洗/去重
│   ├── test_spider.py                 #   29 — 爬虫解析逻辑
│   ├── test_middlewares.py            #   17 — 中间件
│   ├── test_data_validator.py         #   65 — 数据验证
│   └── test_proxy_pool.py            #   19 — 代理池
│
├── docs/                              # 文档
├── .env.example                       # 环境变量模板
├── .pre-commit-config.yaml            # pre-commit 钩子
├── pyproject.toml                     # pytest + ruff + mypy
├── Dockerfile                         # Docker 化部署
└── .github/workflows/                 # CI/CD
```

## 代理配置

系统默认从 GitHub 免费源自动获取代理。如需付费代理，在 `.env` 中配置：

```
CUSTOM_PROXIES=http://user:pass@proxy1.com:8080,socks5://proxy2.com:1080
```

支持 `http://`、`https://`、`socks5://`、`socks4://` 协议。

## 数据库（可选）

复制 `.env.example` → `.env`，填入 MySQL 连接信息：

```
MYSQL_ENABLED=True
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=amazon_scraper
```

表自动创建，ASIN 主键重复时自动更新价格和评分。

## 反爬策略

1. **playwright-stealth** — 页面加载前注入反检测脚本，隐藏 `navigator.webdriver`
2. **UA 轮换** — `fake-useragent` + Chrome 130 / Firefox 132 / Safari 17 fallback
3. **随机延迟** — 搜索页 3-8s，详情页 2-5s
4. **分段滚动** — 1/3 → 2/3 → 全页，模拟人类行为
5. **频率控制** — `CONCURRENT_REQUESTS=1`, `DOWNLOAD_DELAY=10s`
6. **AutoThrottle** — 10-120s 动态延迟
7. **代理轮换** — 自动获取 + 验证 + 加权选择 + 失败自动切换

## 数据采集字段

| 字段 | 说明 |
|------|------|
| `asin` | 亚马逊 ASIN 码 (10 位字母数字) |
| `title` | 商品标题 |
| `price` | 当前价格 (USD) |
| `original_price` | 原价 / 划线价 |
| `rating` | 用户评分 (0-5) |
| `review_count` | 评论总数 |
| `brand` | 品牌 |
| `category` | 面包屑分类路径 |
| `seller_name` | 卖家名称 |
| `availability` | 配送信息 |
| `is_prime` | 是否 Prime 商品 |
| `url` | 商品详情页 URL |
| `image_url` | 主图 URL |
| `description` | 商品描述 |
| `date_first_available` | 首次上架日期 |
| `scraped_at` | 采集时间戳 |

## 注意事项

1. **合规使用** — 请确保数据采集行为符合相关法律法规和目标网站的服务条款
2. **robots.txt** — 默认不遵守 Amazon robots.txt（采集功能所必需），可通过 `ROBOTSTXT_OBEY=True` 环境变量切换
3. **请求频率** — 内置 AutoThrottle 扩展自动调节延迟，不建议大幅降低 `DOWNLOAD_DELAY`
4. **代理质量** — 免费代理可能不稳定，生产环境建议配置付费住宅代理

## 文档

- [系统架构](docs/architecture.md)
- [安装指南](docs/installation.md)
- [使用说明](docs/usage.md)
- [配置说明](docs/configuration.md)

## 许可证

MIT — 详见 [LICENSE](LICENSE) 文件。
