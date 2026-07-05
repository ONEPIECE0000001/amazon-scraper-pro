# Amazon Spider — 跨境电商商品数据采集与运营分析系统

基于 Scrapy + curl\_cffi TLS 指纹仿冒的纯 HTTP 爬虫。支持**关键词搜索**和 **ASIN 精准追踪**双模式，SQLite 存储 + Flask Web 运营驾驶舱，完整覆盖从数据采集 → 清洗入库 → 价格监控 → 竞品分析的全链路。

---

## 目录

- [技术栈](#技术栈)
- [快速开始](#快速开始)
- [项目架构](#项目架构)
- [CLI 命令行使用](#cli-命令行使用)
  - [关键词搜索模式](#关键词搜索模式)
  - [ASIN 精准追踪模式](#asin-精准追踪模式)
  - [每日追踪工作流](#每日追踪工作流)
- [Web 运营面板](#web-运营面板)
  - [商品浏览页 `/`](#商品浏览页)
  - [单品分析页 `/product/<asin>`](#单品分析页)
  - [运营驾驶舱 `/dashboard`](#运营驾驶舱)
  - [一键采集](#一键采集)
- [API 接口参考](#api-接口参考)
- [数据库设计](#数据库设计)
- [采集字段说明](#采集字段说明)
- [衍生指标算法](#衍生指标算法)
- [配置参考](#配置参考)
- [反爬与防封策略](#反爬与防封策略)
- [开发指南](#开发指南)
- [测试](#测试)
- [故障排查](#故障排查)
- [已知限制](#已知限制)

---

## 技术栈

| 层 | 技术 | 说明 |
|---|---|---|
| 爬虫引擎 | Scrapy 2.11+ | 请求调度、中间件管道、CSV 导出 |
| TLS 仿冒 | curl\_cffi | 模拟 Chrome 131 TLS 指纹，绕过 Amazon 反爬检测 |
| 代理 | 自定义 HTTP 代理 | **必须使用美国 IP**，否则价格组件不渲染 |
| 数据库 | SQLite (WAL 模式) | 零配置，Navicat / DB Browser 可直接打开 |
| 衍生指标 | 纯 Python 函数 | BSR → 月销估算、评论速率、竞争度评分 |
| Web 面板 | Flask + Chart.js 4.x | 商品浏览、单品分析、驾驶舱图表 |
| 测试 | pytest | 198 个测试，覆盖 pipeline / spider / metrics / middleware |
| Python | 3.9+ | 跨平台 (Windows / macOS / Linux) |

---

## 快速开始

### 1. 安装依赖

```bash
cd python-amazon-spider
pip install -r requirements.txt
```

### 2. 配置代理

编辑 `.env` 文件（项目根目录），设置美国代理：

```ini
PROXY_ENABLED=True
CUSTOM_PROXIES=http://127.0.0.1:7897    # Clash 默认端口
```

> **重要**：Amazon 非美国 IP 不渲染价格组件，必须使用美国出口节点。

### 3. 首次数据采集

```bash
# 关键词模式 — 搜索 + 详情页，采集 2 页商品
python main.py --keyword "bluetooth earphones" --pages 2

# ASIN 模式 — 直接采集详情页（更快）
python main.py --asin B0FQF9ZX7P
```

### 4. 启动 Web 面板

```bash
python web_app.py
# → 商品浏览:    http://127.0.0.1:5000
# → 运营驾驶舱:  http://127.0.0.1:5000/dashboard
# → 单品分析:    http://127.0.0.1:5000/product/B0FQF9ZX7P
```

---

## 项目架构

```
python-amazon-spider/
│
├── main.py                         # CLI 入口 — 解析参数，构造 scrapy 命令
├── web_app.py                      # Flask Web 面板 — 14 路由 + 9 API + 2 Crawl API
├── .env                            # 环境变量配置（代理/数据库/Redis）
├── requirements.txt                # Python 依赖清单
├── scrapy.cfg                      # Scrapy 项目配置文件
│
├── amazon_spider/                  # Scrapy 爬虫包
│   ├── __init__.py
│   ├── settings.py                 # 全局设置（并发/延迟/中间件/管道/CSV）
│   ├── items.py                    # 数据模型 — AmazonProductItem (21 字段)
│   ├── pipelines.py                # 管道链 (3 个):
│   │                               #   1. DataCleaningPipeline  — 字段清洗
│   │                               #   2. DeduplicationPipeline  — ASIN 去重
│   │                               #   3. SQLitePipeline         — SQLite 双写
│   │                               #   4. MySQLPipeline          — MySQL 写入（可选）
│   ├── feedexport.py               # 中英双语 CSV 导出器
│   │
│   ├── spiders/
│   │   ├── __init__.py
│   │   └── amazon_spider.py        # 核心爬虫 — 关键词搜索 + ASIN 详情双模式
│   │
│   └── middlewares/
│       ├── __init__.py
│       ├── proxy_middleware.py      # 代理注入中间件
│       ├── retry_middleware.py      # 指数退避重试（3/9/27s）
│       └── curl_cffi_middleware.py  # curl_cffi TLS 仿冒 (chrome131)
│
├── core/                           # 独立工具层（无 Scrapy 依赖）
│   ├── __init__.py
│   ├── metrics.py                  # 衍生指标算法（BSR→月销、评论速率、价格桶）
│   ├── proxy_pool.py               # 代理池（免费代理源 + 验证）
│   ├── data_validator.py           # 数据校验（价格/评分/ASIN 合法性）
│   └── logging_config.py           # 统一日志配置
│
├── tests/                          # 测试套件 (198 个测试)
│   ├── test_spider.py              # 爬虫逻辑测试
│   ├── test_pipelines.py           # 管道清洗/去重/入库测试
│   ├── test_metrics.py             # 衍生指标算法测试
│   ├── test_middlewares.py         # 中间件测试
│   ├── test_data_validator.py      # 数据校验测试
│   └── test_proxy_pool.py          # 代理池测试
│
├── output/                         # CSV 输出目录（gitignore）
│   └── amazon_*_*.csv
│
└── amazon_data.db                  # SQLite 数据库（gitignore）
```

---

## CLI 命令行使用

### 关键词搜索模式

用于**新品发现、市场调研、关键词监控**。爬虫会先抓取搜索结果列表页，然后逐一进入详情页抓取扩展字段。

```bash
# 基础用法 — 搜索 "wireless earbuds"，采集 3 页
python main.py --keyword "wireless earbuds" --pages 3

# 快速模式 — 只抓列表页（~2 分钟 / 5 页），不进入详情
# 适合快速扫关键词，牺牲 BSR/品牌/类目等详情专属字段
python main.py --keyword "camera" --pages 5 --no-detail

# 分批断点续爬 — 从第 6 页开始，采集 5 页
# 适合处理超多结果的关键词，分批次采集避免被封锁
python main.py --keyword "laptop" --pages 5 --start-page 6

# 启用浏览器窗口（调试用）
python main.py --keyword "test" --pages 1 --show-browser

# 跳过代理（直连测试）
python main.py --keyword "test" --pages 1 --no-proxy
```

**参数说明：**

| 参数 | 简写 | 默认值 | 说明 |
|------|------|--------|------|
| `--keyword` | `-k` | — | 搜索关键词 |
| `--pages` | `-p` | 2 | 搜索页数（每页约 50-60 个商品） |
| `--start-page` | — | 1 | 起始页（断点续爬用） |
| `--no-detail` | — | False | 快速模式：跳过详情页 |
| `--show-browser` | — | False | 可视化浏览器窗口（调试） |
| `--no-proxy` | — | False | 禁用代理 |

**CSV 输出命名规则：**
```
output/amazon_{keyword}_{page_range}_{mode}_{timestamp}.csv

示例:
output/amazon_wireless_earbuds_p1-3_full_20260705_164611.csv
output/amazon_camera_p1-5_fast_20260705_170000.csv
```

### ASIN 精准追踪模式

用于**价格监控、竞品追踪、历史数据积累**。跳过搜索页直接访问详情页，速度快，触发验证码风险低。

```bash
# 单个 ASIN
python main.py --asin B0FQF9ZX7P

# 多个 ASIN（逗号分隔，无空格）
python main.py --asin "B0FQF9ZX7P,B0FQFL8PZ5,B0FSKL8NH1"

# 从文件批量读取（一行一个 ASIN，# 开头为注释）
python main.py --asin-list track_earphones.txt

# 自定义关键词列标签（用于数据库筛选）
python main.py --asin B0FQF9ZX7P --label "daily_track_20260705"
```

**ASIN 列表文件示例 (`track.txt`):**
```
# 蓝牙耳机追踪列表
B0FQF9ZX7P
B0FQFL8PZ5
B0FSKL8NH1
# 下次再加
# B0XXXXXX
```

**参数说明：**

| 参数 | 说明 |
|------|------|
| `--asin` | 单个或多个 ASIN（逗号分隔，最多 50 个） |
| `--asin-list` | ASIN 列表文件路径 |
| `--label` | 数据库 keyword 列标签（默认 `asin_direct`） |

### 每日追踪工作流

这是典型的电商运营日常 — 先通过关键词搜索发现新品，再每日追踪重点 ASIN 的价格变化。

```bash
# ── 第 1 天：关键词发现 ──
# 搜索蓝牙耳机，采集 2 页
python main.py --keyword "bluetooth earphones" --pages 2

# 从数据库导出发现的 ASIN 列表
sqlite3 amazon_data.db \
  "SELECT asin FROM products WHERE keyword='bluetooth earphones'" \
  > track_earphones.txt

# ── 第 2 天起：精准追踪 ──
# 每个 ASIN 约 5 秒，自动积累 price_history
python main.py --asin-list track_earphones.txt --label "bluetooth earphones"

# 打开 Web 面板查看价格走势
python web_app.py
# → http://127.0.0.1:5000/dashboard
```

> **核心原则**：每次爬取 `price_history` 表都追加新记录（无论数据是否变化），多次爬取同一 ASIN 后自动形成价格走势数据。

---

## Web 运营面板

启动命令：

```bash
python web_app.py
```

面板在 `http://127.0.0.1:5000` 运行，包含三个主要页面。

### 商品浏览页 `/`

搜索、筛选、浏览所有采集到的商品数据。

**筛选条件（9 种）：**

| 筛选器 | 类型 | 说明 |
|--------|------|------|
| 搜索框 | 文本 + 类型选择 | 按全部 / 标题 / ASIN / 品牌搜索 |
| 品牌下拉 | 下拉选择 | 可选择特定品牌 |
| 配送方式 | 下拉选择 | FBA / FBM |
| 最低价 | 数字输入 | 价格下限 (USD) |
| 最高价 | 数字输入 | 价格上限 (USD) |
| 评分 ≥ | 数字输入 | 最低评分过滤 |
| Prime | 复选框 | 仅显示 Prime 商品 |
| 排序 | 下拉选择 | 最新 / 价格↑ / 价格↓ / 评分 / 评论数 |
| 每页条数 | 下拉选择 | 30 / 60 / 90 |

**关键词标签：** 页面上方显示所有已采集的关键词，点击可快速筛选。点击 "✕ 清除" 可取消筛选。

**商品卡片：** 每个卡片展示：
- 商品图片 (100×100)
- 标题（可点击跳转 Amazon）
- 价格 (USD)、评分 (★)、评论数
- Prime 标识
- ASIN（可点击进入单品分析页）
- 所属关键词、品牌标签
- 配送方式 (FBA/FBM)、卖家、类目
- BSR 排名、优惠券、变体数、Q&A 数

**分页导航：** 底部显示页码，支持 "上一页" / "下一页"。

### 单品分析页 `/product/<asin>`

点击任何商品卡片的 ASIN 标签即可进入。这是最详细的数据分析页面。

**页面结构：**

1. **数据时效徽章** — 顶部横幅，根据距上次采集时间自动变色：
   - 🟢 6 小时内 — 数据较新
   - 🟡 6-24 小时 — 建议更新
   - 🔴 超过 24 小时 — 数据可能过时

2. **商品头部** — 图片 + 标题 + 操作按钮：
   - 📋 复制标题 / 🆔 复制 ASIN
   - 📋 复制完整数据摘要（一键复制到剪贴板）
   - 🔄 重新采集（触发后台 Scrapy 爬虫）
   - 🔗 Amazon / 📝 评论 / 🏪 店铺外链
   - 品牌 / 关键词可点击标签

3. **📡 实时抓取数据** — 指标卡片（带来源标记 + 变化提示）：
   - 当前价格、原价、评分、评论数、Q&A 数量、BSR 排名
   - 每张卡片显示较上次采集的变化：涨 ↑、跌 ↓、持平、未变
   - 卖家、优惠券、可用性、上架日期、类目

4. **🧮 衍生估算数据** — 基于算法推算的运营指标：
   - 预估月销（BSR 换算）
   - 日增评论速率

5. **📈 价格走势图** — Chart.js 折线图，展示所有历史采集记录

6. **📋 历史记录表** — 每次采集的价格、BSR、评论数、预估月销

7. **底部导航** — ← 上一款 / 下一款 →（同关键词内切换）

**重新采集反馈：**

点击「🔄 重新采集」后：
- Toast 通知显示采集进度（启动 → 采集中 → 完成）
- 采集完成后**自动对比**上次数据，Toast 直接显示变化摘要：
  - 有变化：`💰 价格: $19.99 → $21.50 (↑+$1.51)；📝 评论: 856 → 862 (+6)`
  - 无变化：`数据无变化 — 价格、BSR、评论数与上次完全一致`
- 页面自动刷新后顶部显示持久化 Banner

**防封保护：**
- 单 ASIN 采集冷却 60 秒
- 同时只允许一个采集任务

### 运营驾驶舱 `/dashboard`

数据可视化分析面板，用于宏观运营决策。

**KPI 统计卡片：**
- 商品总数 / 有 BSR 排名商品 / 发现机会品

**搜索式下拉框：**
- 关键词选择器（支持模糊搜索）
- 商品选择器（支持品牌/标题/ASIN 搜索，点击查看价格走势）

**分析模块：**

| 模块 | 图表类型 | 说明 |
|------|----------|------|
| 📈 价格走势 | 折线图 | 选中商品查看历史价格变化 |
| 📊 价格分布 | 柱状图 | 按价格区间 ($0-10 / $10-25 / … / $200+) 统计商品数量 |
| 🏆 BSR 排行 | 表格 | 按排名升序 TOP 30，含预估月销（可折叠展开） |
| 🎯 竞品雷达 | 柱状图 | 各品牌均价对比（tooltip 看均分/评论数/商品数） |
| 💡 机会发现 | 卡片 | 新品黑马🐴 / 性价比标杆💰 / 潜力新品🌟 |

**一键采集：**
- Dashboard 也有「🔄 采集」按钮
- 按当前选中的关键词触发后台采集
- 完成后对比前后统计数据，显示变化摘要

### 一键采集

Web 面板提供后台采集能力，无需命令行。

**触发方式：**
- 单品页：「🔄 重新采集」按钮（采集当前 ASIN）
- Dashboard：「🔄 采集」按钮（采集当前关键词）

**流程：**
1. 前端 POST `/api/crawl`，后台启动 Scrapy 子进程
2. 前端每 3 秒轮询 `/api/crawl-status/<job_id>` 获取进度
3. 完成后 Toast 显示变化摘要，自动刷新数据

**防封保护：**

| 采集类型 | 冷却时间 | 并发限制 |
|----------|----------|----------|
| 单 ASIN | 60 秒 | 1 个任务 |
| 关键词 | 180 秒 | 1 个任务 |

---

## API 接口参考

所有 API 返回 JSON 格式。

### 数据查询

#### `GET /api/keywords`
返回所有已采集的关键词列表。

```json
{"keywords": ["bluetooth earphones", "desk lamp", "wireless earbuds"]}
```

#### `GET /api/products?kw=<keyword>`
返回商品列表。不传 `kw` 返回全部（限制 200 条）。

```json
{
  "products": [
    {
      "asin": "B0FQF9ZX7P",
      "title": "Wireless Earbuds Bluetooth 5.3...",
      "brand": "SoundPeats",
      "price": 29.99,
      "keyword": "wireless earbuds"
    }
  ]
}
```

#### `GET /api/stats?kw=<keyword>`
返回统计信息。

```json
{
  "total": 216,
  "with_bsr": 89,
  "opportunities": 12,
  "competition_score": 48
}
```

#### `GET /api/price-history?asin=<asin>`
返回指定 ASIN 的价格历史。

```json
{
  "title": "Wireless Earbuds...",
  "points": [
    {"price": 29.99, "bsr": "#1,234 in Electronics", "review_count": 856, "time": "2026-07-05 16:46"},
    {"price": 31.50, "bsr": "#1,189 in Electronics", "review_count": 862, "time": "2026-07-06 09:15"}
  ]
}
```

#### `GET /api/bsr-top?kw=<keyword>`
返回 BSR 排行榜 TOP 30，含预估月销。

#### `GET /api/competitors?kw=<keyword>`
返回品牌竞争统计（均价、均分、评论数、商品数），仅返回 ≥2 个商品的品牌。

#### `GET /api/opportunities`
返回机会发现商品列表（高评分低评论 / 性价比标杆），含评论速率。

#### `GET /api/price-distribution?kw=<keyword>`
返回价格区间分布。

```json
{
  "keyword": "wireless earbuds",
  "distribution": [
    {"range": "$0-10", "count": 5},
    {"range": "$10-25", "count": 42},
    {"range": "$25-50", "count": 78}
  ]
}
```

### 采集控制

#### `POST /api/crawl`
触发后台采集任务。

**请求体：**
```json
{"asin": "B0FQF9ZX7P"}
```
或
```json
{"keyword": "wireless earbuds"}
```

**成功响应：**
```json
{"job_id": "a1b2c3d4", "status": "running"}
```

**冷却期响应 (429)：**
```json
{"error": "防封保护：距上次采集仅 25 秒，请等待 35 秒后再试", "retry_after": 35}
```

#### `GET /api/crawl-status/<job_id>`
查询采集任务进度。

```json
{
  "job_id": "a1b2c3d4",
  "status": "done",
  "output": "...",
  "started_at": "2026-07-05T14:30:00"
}
```

状态值：`running` | `done` | `error`

---

## 数据库设计

数据库文件：`amazon_data.db`（SQLite，WAL 模式），启动时自动创建和迁移。

### products 表（最新快照）

每次爬取更新（`keyword + asin` 唯一），保存最新的 21 个字段。

```sql
CREATE TABLE products (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    keyword             TEXT    NOT NULL DEFAULT '',
    asin                TEXT    NOT NULL,
    title               TEXT,
    price               REAL,
    original_price      REAL,
    rating              REAL,
    review_count        INTEGER,
    brand               TEXT,
    category            TEXT,
    availability        TEXT,
    is_prime            TEXT,
    image_url           TEXT,
    date_first_available TEXT,
    bsr                 TEXT,           -- Best Sellers Rank 原始文本
    coupon_text         TEXT,           -- 优惠券/折扣信息
    answered_questions  INTEGER,        -- Q&A 数量
    variation_count     INTEGER,        -- 变体数量
    fulfillment_type    TEXT,           -- FBA / FBM
    sold_by             TEXT,           -- 卖家信息
    scraped_at          TEXT,           -- 采集时间 (YYYY-MM-DD HH:MM:SS.fff)
    created_at          TEXT DEFAULT (datetime('now')),
    UNIQUE(keyword, asin)
);

CREATE INDEX idx_asin    ON products(asin);
CREATE INDEX idx_keyword ON products(keyword);
```

**写入策略：** `INSERT ... ON CONFLICT(keyword, asin) DO UPDATE SET ...` — ASIN 已存在则更新价格/评分/评论等字段。

### price_history 表（追加时间序列）

**每次爬取必定新增一条记录**（无 UNIQUE 约束），记录采集当时的快照值。

```sql
CREATE TABLE price_history (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    keyword      TEXT    NOT NULL,
    asin         TEXT    NOT NULL,
    price        REAL,
    bsr          TEXT,
    review_count INTEGER,
    scraped_at   TEXT    NOT NULL
);

CREATE INDEX idx_ph_asin    ON price_history(asin);
CREATE INDEX idx_ph_keyword ON price_history(keyword);
```

**数据变化检测：** Web 面板比较 `price_history` 最后 2 条记录来判断价格/BSR/评论的变化方向和幅度。

### 外部工具连接

```bash
# Navicat / DB Browser for SQLite — 直接打开 amazon_data.db
# 连接类型选择 "SQLite"

# SQLite CLI
sqlite3 amazon_data.db
.tables                          # 列出所有表
.schema products                 # 查看表结构
SELECT * FROM products LIMIT 10;
SELECT * FROM price_history WHERE asin='B0FQF9ZX7P' ORDER BY scraped_at DESC;
```

---

## 采集字段说明

| # | 字段 | 类型 | 来源 | 运营价值 | 命中率 |
|---|------|------|------|----------|:--:|
| 1 | `keyword` | TEXT | 搜索词/标签 | 关键词分类筛选 | ~100% |
| 2 | `asin` | TEXT | 列表页 | 商品唯一标识 | ~100% |
| 3 | `title` | TEXT | 列表页 | 标题分析/搜索 | ~100% |
| 4 | `price` | REAL | 列表页 | 价格监控 | ~93% |
| 5 | `original_price` | REAL | 列表页 | 划线价/折扣力度 | ~5% |
| 6 | `rating` | REAL | 列表页 | 评分对比 | ~90% |
| 7 | `review_count` | INTEGER | 列表页 | 评论量/市场热度 | ~90% |
| 8 | `brand` | TEXT | 详情页 | 品牌聚类 | ~75% |
| 9 | `category` | TEXT | 详情页 | 类目归属 | ~50% |
| 10 | `availability` | TEXT | 详情页 | 配送时效 | ~60% |
| 11 | `is_prime` | TEXT | 详情页 | Prime 标识 | ~15% |
| 12 | `image_url` | TEXT | 列表页 | 商品图片 | ~100% |
| 13 | `date_first_available` | TEXT | 详情页 | 上架日期（新品判断） | ~40% |
| 14 | `bsr` | TEXT | 详情页 | **销量估算核心** | ~40% |
| 15 | `coupon_text` | TEXT | 详情页 | 促销/折扣监测 | ~30% |
| 16 | `answered_questions` | INTEGER | 详情页 | 品类热度指标 | ~20% |
| 17 | `variation_count` | INTEGER | 详情页 | 产品矩阵深度 | ~35% |
| 18 | `fulfillment_type` | TEXT | 详情页 | FBA vs FBM 策略 | ~75% |
| 19 | `sold_by` | TEXT | 详情页 | 卖家身份 | ~75% |
| 20 | `scraped_at` | TEXT | 系统 | 数据时效 | 100% |

> 命中率为实际爬取统计数据。部分字段（BSR / coupon / Q&A 等）依赖 Amazon 页面 JS 动态渲染的 HTML 片段，不同品类差异较大。

---

## 衍生指标算法

所有衍生指标在 `core/metrics.py` 中定义为纯函数，**查询时实时计算**，不存入数据库（调整公式无需数据迁移）。

### BSR → 预估月销

```
est_monthly_sales = max(1, int(480,000 / (bsr_rank + 50)))
```

- `BSR_SALES_CONSTANT = 480,000` — 经验常数，可调节
- `BSR_OFFSET = 50` — 避免除零，同时平滑低排名区间的估算曲线
- BSR 排名越小（越好）→ 估算销量越高
- 例：BSR #1,000 → `480000 / 1050 ≈ 457` 件/月

### 日增评论速率

```
review_velocity = review_count / max(1, days_since_listed)
```

- 评论数 ÷ 上架天数 = 每日新增评论
- 高评论速率 = 近期销售活跃 = 市场热度高
- 例：上架 90 天，累计 450 评论 → 5.0 评论/天

### 竞争度评分

```
competition_score = 同关键词下商品总数
```

- 直接使用 `COUNT(*) WHERE keyword = ?` 统计
- 数字越大，该关键词竞争越激烈

### 价格区间分桶

```
$0-10 / $10-25 / $25-50 / $50-100 / $100-200 / $200+
```

- 用于驾驶舱价格分布柱状图
- 函数 `price_bucket_label()` 判定位

---

## 配置参考

### 环境变量 (`.env`)

```ini
# ── SQLite（默认启用）──
SQLITE_ENABLED=True
SQLITE_PATH=amazon_data.db

# ── MySQL（可选）──
MYSQL_ENABLED=False
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=
MYSQL_DATABASE=amazon_scraper

# ── 代理 ──
PROXY_ENABLED=True
CUSTOM_PROXIES=http://127.0.0.1:7897

# ── 爬虫行为 ──
ROBOTSTXT_OBEY=False
# HEADLESS=True
# LOG_LEVEL=INFO
```

### Scrapy 设置 (`settings.py`)

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `CONCURRENT_REQUESTS` | 1 | 并发请求数（建议保持 1） |
| `DOWNLOAD_DELAY` | 10s | 请求间隔（全局） |
| `RANDOMIZE_DOWNLOAD_DELAY` | 0.5 | 随机抖动比例 |
| `AUTOTHROTTLE_ENABLED` | True | 自动限速 |
| `AUTOTHROTTLE_START_DELAY` | 10s | 自动限速起始延迟 |
| `AUTOTHROTTLE_MAX_DELAY` | 120s | 自动限速最大延迟 |
| `AUTOTHROTTLE_TARGET_CONCURRENCY` | 0.5 | 目标并发度 |
| `RETRY_TIMES` | 3 | 重试次数 |
| `MEMUSAGE_LIMIT_MB` | 2048 | 内存上限 |

### Spider 级别设置 (`amazon_spider.py`)

| 配置 | 值 | 说明 |
|------|-----|------|
| `custom_settings.CONCURRENT_REQUESTS` | 1 | Spider 级并发限制 |
| `custom_settings.DOWNLOAD_DELAY` | 5s | Spider 级延迟 |

---

## 反爬与防封策略

系统采用多层反检测策略，按优先级排列：

### 1. TLS 指纹仿冒（核心）

`curl_cffi` 库模拟 Chrome 131 的 TLS 握手特征（JA3/JA4 指纹），使请求看起来像真实 Chrome 浏览器发出的。Amazon 的反爬系统（AWS WAF）通过 TLS 指纹检测非浏览器客户端，此层是最关键的绕过手段。

中间件：`curl_cffi_middleware.py` → `impersonate="chrome131"`

### 2. User-Agent 轮换

从 `fake_useragent` 库获取与 TLS 指纹匹配的 UA 字符串，每次请求随机切换。

```python
# 内置 fallback 列表 (Chrome 131 / Firefox 133 / Edge 131)
Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0
Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/131.0.0.0
...
```

### 3. 请求限速

| 层级 | 配置 | 说明 |
|------|------|------|
| Spyder 级 | `DOWNLOAD_DELAY=5s` | 基础间隔 |
| AutoThrottle | 起始 10s，最大 120s | 根据响应延迟自动加长 |
| Web API 级 | ASIN 60s / 关键词 180s 冷却 | 防止频繁触发采集 |
| 并发 | 全局 1 + 任务 1 | 串行请求，模拟人类浏览 |

### 4. 代理 IP

**必须使用美国 IP。** 非美国 IP 访问 Amazon 时，价格组件 (`$X.XX`) 不会被服务器端渲染，导致价格字段永久缺失。

```ini
# .env 配置
CUSTOM_PROXIES=http://127.0.0.1:7897   # Clash 默认端口
```

### 5. 请求头伪装

```python
DEFAULT_REQUEST_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
}
```

### 6. 指数退避重试

遇到 403/429/5xx 错误时，以 3s → 9s → 27s 的间隔重试，避免触发更严厉的限流。

---

## 开发指南

### 添加新的采集字段

1. **`amazon_spider/items.py`** — 添加 `scrapy.Field()`
2. **`amazon_spider/spiders/amazon_spider.py`** — 在 `parse_product_detail()` 中提取数据
3. **`amazon_spider/pipelines.py`** — `DataCleaningPipeline` 添加清洗逻辑，`SQLitePipeline` 更新 `CREATE TABLE` / `INSERT`
4. **`web_app.py`** — `product_detail()` 读取新字段，模板中展示
5. **`tests/test_spider.py`** / **`tests/test_pipelines.py`** — 添加对应测试

### 添加新的衍生指标

1. **`core/metrics.py`** — 添加纯函数（输入：DB row 的值，输出：标量）
2. **`web_app.py`** — `product_detail()` / API 路由中调用
3. **`tests/test_metrics.py`** — 添加测试用例

### 添加新的 Web API

1. **`web_app.py`** — 新增 `@app.route()` 函数
2. 使用 `get_db()` 获取数据库连接
3. 返回 `jsonify(...)` 格式数据

### 添加新的 Web 页面

1. **`web_app.py`** — 新增路由 + `render_template_string(TEMPLATE_STR, ...)`
2. 新增 `TEMPLATE_STR` 变量，包含完整 HTML/CSS/JS
3. 在 navbar 中添加导航链接

### 代码风格

- 中文注释 + 英文变量名
- 函数式、纯函数优先（特别是 `core/metrics.py`）
- Pipeline 错误不抛异常，`logger.warning` + 继续处理
- 模板内 Jinja2 使用 `.get()` 语法访问 dict（兼容性最佳）

---

## 测试

```bash
# 运行全部测试
python -m pytest tests/ -q
# 198 passed

# 指定测试文件
python -m pytest tests/test_pipelines.py -q

# 显示详细输出
python -m pytest tests/ -v

# 带覆盖率
pip install pytest-cov
python -m pytest tests/ --cov=amazon_spider --cov=core --cov-report=term

# 运行单个测试
python -m pytest tests/test_metrics.py::test_parse_bsr_rank -v
```

**测试文件说明：**

| 文件 | 测试数 | 覆盖内容 |
|------|--------|----------|
| `test_spider.py` | ~30 | Spider 请求构造、UA 轮换、字段解析 |
| `test_pipelines.py` | ~30 | 数据清洗（价格/评分/ASIN）、去重、SQLite 写入 |
| `test_metrics.py` | ~40 | BSR 解析、月销估算、评论速率、价格分桶 |
| `test_middlewares.py` | ~40 | 代理注入、重试逻辑、TLS 中间件 |
| `test_data_validator.py` | ~30 | 价格/评分/ASIN/URL 合法性校验 |
| `test_proxy_pool.py` | ~28 | 代理池获取/验证/统计 |

---

## 故障排查

### 价格字段全部为空

**原因：** 代理 IP 不是美国节点。

**解决：**
1. 检查 Clash / 代理工具，确认出口节点是美国
2. 验证：浏览器通过代理访问 `https://www.amazon.com`，查看是否显示美元价格
3. 或在 `main.py` 中使用 `--no-proxy` 测试（如果你本就在美国）

### Web 面板数据为空

**原因：** 数据库文件路径不一致。

**解决：**
1. 检查 `.env` 中 `SQLITE_PATH` 配置
2. Web 面板启动时的终端输出会显示数据库路径：
   ```
   Database: amazon_data.db
   ```
3. 确认该路径下的 `.db` 文件存在且非空

### 采集频繁返回 503/403

**原因：** Amazon 检测到爬虫行为。

**解决：**
1. 增加 `DOWNLOAD_DELAY`（在 `amazon_spider/spiders/amazon_spider.py` 中）
2. 检查代理 IP 是否被 Amazon 标记（更换节点）
3. 等待 30 分钟后再试（Amazon 的临时封锁通常持续 30-60 分钟）
4. 减少 `CONCURRENT_REQUESTS`（已默认为 1）

### price_history 没有新记录

**原因（已修复）：** 旧版数据库的 UNIQUE 约束阻止了重复 INSERT。

**解决：** 系统启动时自动检测并迁移旧 schema。如果仍有问题，删除数据库重建：

```bash
rm amazon_data.db
python main.py --keyword "test" --pages 1
python web_app.py                # 启动时自动创建新 schema
```

### Web 面板白屏 / Jinja2 错误

**原因：** 模板语法错误或 Python 版本不兼容。

**解决：**
1. 确认 Python ≥ 3.9
2. 重新安装依赖：`pip install -r requirements.txt --force-reinstall`
3. 查看终端错误日志定位具体行

### curl_cffi 安装失败

**原因：** Windows 缺少 C++ 编译工具。

**解决：**
```bash
# Windows: 安装 Visual Studio Build Tools
# https://visualstudio.microsoft.com/downloads/#build-tools-for-visual-studio-2022

# macOS:
brew install curl

# Linux:
sudo apt install libcurl4-openssl-dev
```

---

## 已知限制

| 限制 | 原因 | 影响 | 缓解措施 |
|------|------|------|----------|
| 部分字段命中率低 | Amazon JS 动态渲染差异 | BSR/Coupon/Q&A 等约 20-40% | 多次爬取，部分字段在后续访问中可能被渲染 |
| 代理必须 US IP | 非 US IP 不渲染价格 | 价格≠None 为硬需求 | 配置 Clash US 出口节点 |
| Apple 产品价格偶有缺失 | Apple 价格 API 异步加载 | ~7% 商品无价格 | 不影响其他字段 |
| SQLite 不支持并发写 | 单进程锁 | 不能同时开多个爬虫 | Web API 层已限制并发任务数为 1 |
| curl\_cffi 无官方 Windows wheel | 需编译安装 | 安装较慢 | 使用 `pip` 自动编译，需 Visual Studio Build Tools |
| Amazon 反爬更新频繁 | HTML 结构/CSS 选择器可能变化 | 字段提取可能失效 | 定期检查命中率，更新 CSS 选择器 |
| robots.txt 被忽略 | `ROBOTSTXT_OBEY=False` | 法律合规风险 | 仅用于研究和数据分析，部署前咨询法务 |
