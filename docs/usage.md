# 使用说明

## 基本使用

### 1. 单次数据采集

```bash
# 基本采集命令
python main.py --search "laptop" --pages 3 --mode run

# 参数说明
--search: 搜索关键词（默认为"laptop"）
--pages: 爬取页数（默认为3）
--mode: 运行模式（run/analyze/schedule，默认为run）
```

### 2. 数据分析

```bash
# 分析已采集的数据
python main.py --mode analyze --file "advanced_amazon_data_20231201120000.xlsx"
```

### 3. 定时任务

```bash
# 启动Celery worker和定时任务
celery -A celery_tasks worker --loglevel=info --beat

# 或分别启动
# 启动Celery worker
celery -A celery_tasks worker --loglevel=info

# 启动beat调度器
celery -A celery_tasks beat --loglevel=info
```

## 高级用法

### 1. 自定义搜索参数

```bash
# 搜索特定商品
python main.py --search "iPhone 15" --pages 5 --mode run

# 搜索多个关键词
python main.py --search "wireless headphones" --pages 10 --mode run
```

### 2. 代理配置

在 `advanced_amazon_spider.py` 中配置代理：

```python
# 示例代理配置
self.proxies = [
    'http://user:pass@proxy1.example.com:8080',
    'http://user:pass@proxy2.example.com:8080',
    # 添加更多代理
]
```

### 3. 自定义爬取参数

在 `advanced_amazon_spider.py` 中调整以下参数：

```python
# 请求间隔时间（秒）
self.min_wait_time = 10
self.max_wait_time = 15

# 重试次数
self.retry_times = 5

# 页面滚动等待时间（毫秒）
self.scroll_wait_time = 3000
```

## 任务调度

### 1. 配置定时任务

编辑 `celery_config.py` 中的 `beat_schedule`：

```python
'beat_schedule': {
    'daily-amazon-scraper': {
        'task': 'celery_tasks.run_amazon_scraping',
        'schedule': 86400.0,  # 每天运行一次 (24*60*60 秒)
        'args': ('laptop', 5)  # 传递参数
    },
},
```

### 2. 启动调度服务

```bash
# 后台启动（Linux/macOS）
nohup celery -A celery_tasks worker --loglevel=info --beat &

# Windows下可以使用任务计划程序
```

## 数据处理

### 1. 数据导出格式

采集的数据会自动保存为Excel文件，包含以下字段：

| 字段名 | 说明 |
|--------|------|
| 商品ID | 亚马逊ASIN码 |
| 商品名称 | 产品标题 |
| 价格 | 当前价格 |
| 销量 | 月销量或总销量 |
| 评分 | 用户评分 |
| 评论数 | 用户评论总数 |
| 品牌 | 商品品牌 |
| 类别 | 商品分类 |
| 上架时间 | 首次上架时间 |
| 采集时间 | 数据采集时间 |
| URL | 商品页面链接 |
| 配送信息 | 配送详情 |
| 是否Prime | Prime会员服务 |

### 2. 数据分析功能

使用分析模式查看数据统计：

```bash
python main.py --mode analyze --file "your_data_file.xlsx"
```

分析结果包括：
- 总商品数
- 平均价格
- 价格范围
- 平均评分
- 平均评论数

## 监控与日志

### 1. 日志查看

系统会生成详细的日志信息：

```bash
# Scrapy日志
# 通常在终端输出中查看

# 自定义日志
# 在爬虫中添加日志记录
self.logger.info("Custom log message")
```

### 2. 性能监控

监控采集性能：

- 采集速度（页面/分钟）
- 成功率（成功请求/总请求）
- 数据质量得分
- 系统资源使用情况

## 最佳实践

### 1. 反爬策略

- 配置多个代理IP
- 设置合理的请求间隔
- 使用随机User-Agent
- 模拟人类浏览行为

### 2. 数据质量

- 定期验证数据准确性
- 设置数据质量阈值
- 实施数据清洗流程

### 3. 性能优化

- 合理设置并发数
- 优化选择器性能
- 使用缓存机制

## 故障排除

### 1. 常见错误

**503错误**: 增加请求间隔或更换代理IP
**超时错误**: 检查网络连接或增加超时时间
**数据不完整**: 检查选择器是否需要更新

### 2. 调试技巧

```bash
# 开启详细日志
scrapy crawl advanced_amazon_spider -L DEBUG

# 测试单个URL
python -c "from scrapy.http import Request; print('Request created')"
```

## 扩展功能

### 1. 多平台支持

系统架构支持扩展到其他电商平台：

```python
# 创建新的爬虫类
class NewPlatformSpider(scrapy.Spider):
    name = "new_platform_spider"
    # 实现特定平台的逻辑
```

### 2. API接口

可扩展为API服务：

```python
# 使用Flask或FastAPI创建API接口
from flask import Flask
app = Flask(__name__)

@app.route('/scrape')
def scrape():
    # 启动爬虫任务
    pass
```

## 注意事项

1. 遵守目标网站的robots.txt和使用条款
2. 合理控制请求频率，避免对服务器造成压力
3. 确保数据使用符合法律法规
4. 定期更新选择器以适应网站变化