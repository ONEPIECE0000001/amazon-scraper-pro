# Amazon Spider — 亚马逊商品数据采集

基于 Scrapy + curl_cffi 的纯 HTTP 爬虫，支持搜索关键词批量采集商品数据，SQLite 存储，Web 管理面板。

## 技术栈

| 层 | 技术 |
|---|---|
| 爬虫引擎 | Scrapy 2.13 |
| TLS 仿冒 | curl_cffi（Chrome 131 指纹） |
| 代理 | Clash / 自定义 HTTP 代理，需美国 IP |
| 数据库 | SQLite（零配置，Navicat 可直接打开） |
| Web 面板 | Flask + 内置 HTML 模板 |
| Python | 3.9+ |

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置代理（.env 文件）
# CUSTOM_PROXIES=http://127.0.0.1:7897

# 3. 爬取数据
python main.py --keyword "bluetooth earphones" --pages 3

# 4. 启动 Web 面板
python web_app.py
# → 浏览器打开 http://127.0.0.1:5000
```

## 使用方式

```bash
# 完整模式 — 搜索 + 进入每个商品详情页（16 字段）
python main.py --keyword "camera" --pages 3

# 快速模式 — 仅搜索列表页（7 字段，2 分钟）
python main.py --keyword "camera" --pages 5 --no-detail

# 分批爬取 — 断点续爬
python main.py --keyword "camera" --pages 5 --start-page 6
```

## 采集字段

| 字段 | 来源 | 说明 |
|------|------|------|
| keyword | 搜索词 | 本次搜索使用的关键词 |
| asin | 列表页 | Amazon 商品唯一 ID |
| title | 列表页 | 商品标题 |
| price | 列表页 | 当前价格（USD） |
| original_price | 详情页 | 原价/划线价 |
| rating | 列表页 | 评分（1-5） |
| review_count | 列表页 | 评论总数 |
| brand | 详情页 | 品牌 |
| category | 详情页 | 类目路径 |
| seller_name | 详情页 | 卖家名称 |
| availability | 详情页 | 库存/物流信息 |
| is_prime | 详情页 | 是否 Prime 商品 |
| url | 列表页 | 商品链接 |
| image_url | 列表页 | 商品图片（高分辨率） |
| description | 详情页 | 商品描述 |
| date_first_available | 详情页 | 上架日期 |
| scraped_at | Spider | 抓取时间 |

## 项目结构

```
├── main.py                    # 入口
├── web_app.py                 # Web 面板
├── .env                       # 配置文件（不入 git）
│
├── amazon_spider/             # Scrapy 爬虫
│   ├── settings.py            # 全局配置
│   ├── items.py               # 数据模型
│   ├── pipelines.py           # 管道：清洗 → 去重 → SQLite
│   ├── feedexport.py          # 中英双语 CSV 导出
│   ├── spiders/
│   │   └── amazon_spider.py   # 核心爬虫
│   └── middlewares/
│       ├── proxy_middleware.py
│       ├── retry_middleware.py
│       └── curl_cffi_middleware.py
│
├── core/                      # 工具
│   ├── proxy_pool.py
│   ├── data_validator.py
│   └── logging_config.py
│
├── tests/                     # 150 个测试
└── output/                    # CSV 输出
```

## 测试

```bash
python -m pytest tests/ -q
# 150 passed
```

## 数据查看

**Web 面板**：`python web_app.py` → `http://127.0.0.1:5000`

**Navicat / SQLite 工具**：
- 连接类型：SQLite
- 数据库文件：选择 `amazon_data.db`
- 无需用户名密码

**CSV**：`output/` 目录，Excel 可直接打开（UTF-8 BOM 编码）

## 重要配置

| 配置 | 位置 | 说明 |
|------|------|------|
| `CUSTOM_PROXIES` | `.env` | 代理地址，**必须用美国 IP** |
| `SQLITE_ENABLED` | `.env` | SQLite 存储开关 |
| `DOWNLOAD_DELAY` | `settings.py` | 请求间隔（默认 5 秒） |
| `LOG_LEVEL` | `settings.py` | 日志级别（INFO 静音调试信息） |

## 反爬策略

1. **TLS 指纹仿冒**：curl_cffi 伪装 Chrome 131
2. **UA 轮换**：匹配 TLS 指纹的 Chrome/Firefox UA 列表
3. **自动限速**：AutoThrottle + 5 秒请求间隔
4. **代理**：Clash 代理 + US 出口节点

## 已知限制

- 部分字段（类目、Prime、上架日期）由 JS 动态渲染，纯 HTTP 无法获取
- 必须使用美国 IP 代理，否则价格组件可能不加载
- Apple 部分高价产品的价格可能不显示在静态 HTML 中
