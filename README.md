# Amazon Spider — 跨境电商商品数据采集系统

基于 Scrapy + curl_cffi 的纯 HTTP 爬虫，支持关键词搜索 和 ASIN 精准追踪双模式。SQLite 存储 + Flask Web 运营驾驶舱。

## 技术栈

| 层 | 技术 |
|---|---|
| 爬虫引擎 | Scrapy 2.13 |
| TLS 仿冒 | curl_cffi（Chrome 131 指纹） |
| 代理 | Clash / 自定义 HTTP 代理，**需美国 IP** |
| 数据库 | SQLite（零配置，Navicat 直接打开） |
| Web 面板 | Flask + Chart.js |
| Python | 3.9+ |

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置代理（.env 文件）
# CUSTOM_PROXIES=http://127.0.0.1:7897

# 3. 关键词爬取
python main.py --keyword "bluetooth earphones" --pages 2

# 4. 启动 Web 面板
python web_app.py
# → 商品浏览: http://127.0.0.1:5000
# → 运营驾驶舱: http://127.0.0.1:5000/dashboard
```

## 完整使用手册

### 一、关键词搜索模式（发现新品、市场调研）

```bash
# 基础用法
python main.py --keyword "wireless earbuds" --pages 3

# 快速模式 — 只搜列表页，不进详情（~2分钟/5页）
python main.py --keyword "camera" --pages 5 --no-detail

# 分批断点续爬
python main.py --keyword "laptop" --pages 5 --start-page 6
```

### 二、ASIN 精准追踪模式（每日监控、积累历史数据）

```bash
# 单个 ASIN
python main.py --asin B0FQF9ZX7P

# 多个 ASIN（逗号分隔）
python main.py --asin "B0FQF9ZX7P,B0FQFL8PZ5,B0FSKL8NH1"

# 从文件批量读取（一行一个 ASIN）
python main.py --asin-list track_earphones.txt

# 自定义关键词列标签
python main.py --asin B0FQF9ZX7P --label "daily_track_20260705"
```

### 三、每日追踪工作流（价格历史积累）

```bash
# 第 1 天：关键词发现新品，导出关注 ASIN 列表
python main.py --keyword "bluetooth earphones" --pages 2
sqlite3 amazon_data.db "SELECT asin FROM products WHERE keyword='bluetooth earphones'" > track.txt

# 第 2 天起：精准追踪（每个 ASIN ~5 秒）
python main.py --asin-list track.txt --label "bluetooth earphones"

# 多次爬取后，价格走势图自动生成
```

## 采集字段

| 字段 | 来源 | 运营价值 | 命中率 |
|------|------|----------|:--:|
| `keyword` | 搜索词 | 关键词分类 | ~100% |
| `asin` | 列表页 | 商品唯一标识 | ~100% |
| `title` | 列表页 | 标题分析 | ~100% |
| `price` | 列表页 | 价格监控 | ~93% |
| `rating` | 列表页 | 评分对比 | ~90% |
| `review_count` | 列表页 | 评论量分析 | ~90% |
| `brand` | 详情页 | 品牌聚类 | ~75% |
| `category` | 详情页 | 类目归属 | ~50% |
| `availability` | 详情页 | 配送时效 | ~60% |
| `date_first_available` | 详情页 | 新品判断 | ~40% |
| **BSR** | 详情页 | 销量估算核心指标 | ~40% |
| **coupon_text** | 详情页 | 促销监测 | ~30% |
| **answered_questions** | 详情页 | 品类热度 | ~20% |
| **variation_count** | 详情页 | 产品矩阵深度 | ~35% |
| **fulfillment_type** | 详情页 | FBA vs FBM | ~75% |
| **sold_by** | 详情页 | 卖家身份 | ~75% |
| `is_prime` | 详情页 | Prime 标识 | ~15% |
| `original_price` | 详情页 | 划线价 | ~5% |
| `image_url` | 列表页 | 商品图片 | ~100% |
| `scraped_at` | Spider | 时间戳 | 100% |

> 命中率为实际爬取统计数据，因产品品类和页面结构而异。

## 数据库

### products 表（最新快照，keyword + asin 唯一）

| 列 | 类型 | 说明 |
|---|---|---|
| keyword | TEXT | 搜索词 / ASIN 标签 |
| asin | TEXT | 商品 ID |
| price | REAL | 当前价格 (USD) |
| rating | REAL | 评分 (0-5) |
| review_count | INTEGER | 评论数 |
| brand | TEXT | 品牌 |
| bsr | TEXT | Best Sellers Rank |
| fulfillment_type | TEXT | FBA / FBM |
| sold_by | TEXT | 卖家名称 |
| ... | | 完整 20 字段 |

### price_history 表（追加时间序列）

| 列 | 说明 |
|---|---|
| keyword, asin | 关联商品 |
| price | 当时价格 |
| bsr | 当时 BSR |
| scraped_at | 采集时间 |

每次爬取双写：`products` 覆盖最新快照 + `price_history` 追加一行。多次爬取同一 ASIN 后自动形成价格走势数据。

### 外部工具连接

```bash
# Navicat / DB Browser: 直接打开 amazon_data.db（SQLite 类型）
# SQLite CLI
sqlite3 amazon_data.db "SELECT * FROM products LIMIT 10"
sqlite3 amazon_data.db "SELECT * FROM price_history WHERE asin='B0FQF9ZX7P'"
```

## Web 面板

| 页面 | 路由 | 功能 |
|------|------|------|
| 商品浏览 | `/` | 卡片/表格展示、搜索筛选、关键词标签、分页 |
| 运营驾驶舱 | `/dashboard` | 价格走势图、BSR 排行、竞品雷达、机会发现 |

驾驶舱模块：

| 模块 | 图表类型 | 说明 |
|------|----------|------|
| 📈 价格走势 | Chart.js 折线图 | 选中商品查看历史价格变化 |
| 🏆 BSR 排行 | 表格 | 按排名升序 TOP 30 |
| 🎯 竞品雷达 | 柱状图 | 各品牌均价对比（hover 看均分/评论数） |
| 💡 机会发现 | 卡片 | 新品黑马🐴 / 性价比标杆💰 / 潜力新品🌟 |

> ⚠️ 价格走势图需要至少 2 次爬取同一 ASIN 才有历史数据。

## API 接口

| 端点 | 参数 | 返回 |
|------|------|------|
| `/api/keywords` | — | 所有关键词列表 |
| `/api/products` | `?kw=` | 商品列表（ASIN/标题/品牌/价格） |
| `/api/stats` | `?kw=` | 统计（总数/有BSR数/机会品数） |
| `/api/price-history` | `?asin=` | 价格历史数据点 |
| `/api/bsr-top` | `?kw=` | BSR 排行 TOP 30 |
| `/api/competitors` | `?kw=` | 品牌统计（均价/均分/评论数） |
| `/api/opportunities` | — | 机会发现商品列表 |

## 项目结构

```
python-amazon-spider/
├── main.py                    # CLI 入口
├── web_app.py                 # Web 面板 + 驾驶舱 + API
├── .env                       # 代理/数据库配置（不入 git）
├── requirements.txt
├── scrapy.cfg
├── README.md
│
├── amazon_spider/             # Scrapy 爬虫包
│   ├── settings.py            # 全局配置
│   ├── items.py               # 数据模型 (AmazonProductItem, 20 字段)
│   ├── pipelines.py           # 管道: 清洗 → 去重 → SQLite(+price_history)
│   ├── feedexport.py          # 中英双语 CSV 导出
│   ├── spiders/
│   │   └── amazon_spider.py   # 核心爬虫 (关键词 + ASIN 双模式)
│   └── middlewares/
│       ├── proxy_middleware.py     # 代理注入
│       ├── retry_middleware.py     # 指数退避重试
│       └── curl_cffi_middleware.py # curl_cffi TLS 仿冒 (chrome131)
│
├── core/                      # 工具层
│   ├── proxy_pool.py          # 代理池
│   ├── data_validator.py      # 数据校验
│   └── logging_config.py      # 日志配置
│
├── tests/                     # 153 个测试
│   ├── test_spider.py
│   ├── test_pipelines.py
│   ├── test_middlewares.py
│   ├── test_data_validator.py
│   └── test_proxy_pool.py
│
└── output/                    # CSV 输出 (gitignore)
```

## 测试

```bash
python -m pytest tests/ -q
# 153 passed
```

## 配置参考

| 配置项 | 位置 | 默认值 | 说明 |
|------|------|------|------|
| `CUSTOM_PROXIES` | `.env` | — | 代理地址，**必须用美国 IP** |
| `SQLITE_ENABLED` | `.env` | `True` | SQLite 存储开关 |
| `SQLITE_PATH` | `.env` | `amazon_data.db` | 数据库文件路径 |
| `MYSQL_ENABLED` | `.env` | — | MySQL 存储（可选） |
| `DOWNLOAD_DELAY` | `settings.py` | 5s | 请求间隔 |

## 反爬策略

1. **TLS 指纹仿冒**：curl_cffi 伪装 Chrome 131（`impersonate="chrome131"`）
2. **UA 轮换**：匹配 TLS 指纹的 Chrome 131 / Firefox 133 UA 列表
3. **自动限速**：`DOWNLOAD_DELAY=5s` + `RANDOMIZE_DOWNLOAD_DELAY=0.5`
4. **代理**：需配置 Clash + US 出口节点

## 已知限制

| 限制 | 原因 | 影响 |
|------|------|------|
| 部分字段命中率偏低 | JS 动态渲染（BSR/Coupon/Q&A 等） | 不同品类差异大 |
| 代理必须 US IP | 非 US IP 价格组件不渲染 | 必须 |
| Apple 产品价格偶有缺失 | Apple 产品价格由 API 异步加载 | ~7% |
| SQLite 不支持并发写 | 单进程锁 | 不要同时开多个爬虫 |
