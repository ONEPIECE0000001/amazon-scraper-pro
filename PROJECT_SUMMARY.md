# 亚马逊电商平台商品数据智能采集系统 — 项目总结

## 项目概述

面向市场调研公司的自动化数据采集系统，用于监测亚马逊平台的商品价格波动、
用户评论趋势和促销活动。

## 技术架构

### 核心技术栈
- **核心框架**: Scrapy 2.11+ — 高效异步爬虫框架
- **浏览器引擎**: Playwright 1.40+ — JavaScript 动态渲染
- **任务调度**: Celery 5.3+ — 分布式任务队列
- **数据存储**: CSV + MySQL — Pipeline 多路输出
- **代理管理**: ProxyPool — 免费源自动获取 + 加权选择

### 系统特性
1. **智能反爬策略** — stealth.js 注入 + UA 轮换 + 随机延迟 + 行为模拟
2. **Item Pipeline 架构** — 清洗 → 去重 → MySQL，职责分离
3. **数据质量保障** — 7 字段自动验证、质量得分计算、中文报告
4. **自动化调度** — Celery Beat 定时任务，86400s 周期无人值守
5. **完整测试覆盖** — 151 单元测试，爬虫/中间件/验证器/代理池全覆盖

## 项目结构

```
python-amazon-spider/
├── amazon_spider/                     # Scrapy 核心包
│   ├── items.py                       #   AmazonProductItem (16 字段)
│   ├── pipelines.py                   #   清洗 → 去重 → MySQL
│   ├── spiders/amazon_spider.py       #   主爬虫 (搜索 + 详情)
│   └── middlewares/
│       ├── stealth_middleware.py      #   playwright-stealth 注入
│       ├── retry_middleware.py        #   指数退避 + UA/代理轮换
│       └── proxy_middleware.py        #   请求级代理注入 + 故障切换
│
├── main.py                            # CLI 入口 (argparse)
├── settings.py                        # Scrapy 全局配置
├── proxy_pool.py                      # 代理池 (免费源获取 + 验证)
├── data_validator.py                  # 数据验证 + 质量监控
├── celery_config.py                   # Celery Beat 调度配置
├── celery_tasks.py                    # Celery 任务定义
├── logging_config.py                  # 统一日志配置 (console + file)
│
├── tests/                             # 单元测试 (151 用例)
│   ├── test_pipelines.py              #   16 用例
│   ├── test_spider.py                 #   29 用例
│   ├── test_middlewares.py            #   17 用例
│   ├── test_data_validator.py         #   65 用例
│   └── test_proxy_pool.py            #   19 用例
│
├── docs/                              # 详细文档
├── .env.example                       # 环境变量模板
├── .pre-commit-config.yaml            # pre-commit 钩子
├── pyproject.toml                     # pytest + ruff + mypy
├── Dockerfile                         # Docker 化部署
└── .github/workflows/                 # CI/CD
```

## 反爬策略详解

- **playwright-stealth** — `add_init_script` 在页面加载前注入反检测 JS
- **UA 轮换** — `fake-useragent` + Chrome 130/Firefox 132/Safari 17 备用列表
- **随机 Viewport** — 1280-1920 × 720-1080
- **随机延迟** — 搜索页 3-8s，详情页 2-5s
- **分段滚动** — 模拟人类浏览的分段页面滚动
- **频率控制** — `CONCURRENT_REQUESTS=1`, `DOWNLOAD_DELAY=10s`
- **AutoThrottle** — 10-120s 动态延迟调整
- **代理池** — GitHub 免费源 → 多线程验证 → 按延迟加权选择 → 失败自动移除

## 数据质量保障

1. **DataCleaningPipeline** — 价格→float、评分 0-5 校验、ASIN `^[A-Z0-9]{10}$` 格式、评论数去逗号、负数检测
2. **DeduplicationPipeline** — 基于 ASIN 的 Set 内存去重
3. **MySQLPipeline** — ASIN 唯一主键，重复则更新价格/评分/时间
4. **DataValidator** — 7 字段独立验证 + 数据框批量校验 + 中文本地化报告
5. **DataQualityMonitor** — 质量得分（目标 95%+）、自动清洗去重

## 代理管理

- `proxy_pool.py` — 3 个 GitHub 免费源自动获取代理列表
- 20 线程并发验证 (httpbin.org/ip, 5s 超时)
- 按延迟倒数加权随机选择（低延迟代理更高权重）
- `mark_bad()` 失败自动移除
- `CUSTOM_PROXIES` 环境变量支持付费代理
- 代理池空时自动降级直连

## 快速开始

```bash
pip install -r requirements.txt
playwright install chromium
python main.py --keyword "laptop" --pages 2
```

输出：`output/amazon_laptop_<timestamp>.csv`

## 定时调度

```bash
# 启动 Redis (Docker)
docker run --name redis -p 6379:6379 -d redis:latest

# 启动 Celery (每天采集一次)
celery -A celery_tasks worker --loglevel=info --beat
```

修改采集关键词/频率：编辑 `celery_config.py` 第 16-21 行的 `beat_schedule`。

## 测试

```bash
pytest tests/ -v       # 151 用例全部通过
python test_system.py  # 5 场景集成冒烟测试
```

## 注意事项

1. 确保数据采集行为符合相关法律法规
2. 默认不遵守 Amazon robots.txt（采集功能必需），部署前请法务评估
3. 生产环境建议配置付费代理，免费代理可能不稳定
4. `ROBOTSTXT_OBEY` 和 `CUSTOM_PROXIES` 均可通过环境变量配置

## 许可证

MIT
