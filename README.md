# 亚马逊电商平台商品数据智能采集系统

<div align="center">

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue)](https://www.python.org/)
[![Scrapy](https://img.shields.io/badge/Scrapy-2.13%2B-green)](https://scrapy.org/)
[![Playwright](https://img.shields.io/badge/Playwright-1.40%2B-brightgreen)](https://playwright.dev/)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Production%20Ready-brightgreen)](README.md)

**🚀 专业的亚马逊商品数据采集解决方案 | 智能反爬 | 分布式架构 | 高效稳定**

</div>

## 📋 项目概述

为市场调研公司开发的自动化数据采集系统，用于监测多个主流电商平台的商品价格波动、用户评论趋势和促销活动。系统帮助客户实时掌握市场动态，优化定价策略，提升市场竞争力。

## 🎯 核心功能

- **智能数据采集** - 支持动态页面渲染，获取完整商品信息
- **高级反爬策略** - 多层反制机制，有效绕过网站防护
- **数据质量保障** - 自动验证和清洗，确保数据准确性
- **分布式架构** - 支持多节点并发采集
- **自动化调度** - 定时任务执行，无人值守运行
- **实时监控** - 采集进度和数据质量实时跟踪

## 🛠 技术架构

### 技术栈
- **核心框架**: Scrapy 2.13+ - 高效异步爬虫框架
- **浏览器引擎**: Playwright 1.40+ - 处理JavaScript动态渲染
- **任务调度**: Celery 5.3+ - 分布式任务队列
- **数据存储**: Excel/Pandas - 结构化数据处理
- **代理管理**: 自定义代理池 - IP轮换防封禁

### 系统架构图
```mermaid
graph TB
    A[数据采集入口] --> B[Scrapy爬虫框架]
    B --> C[Playwright渲染引擎]
    C --> D[反爬策略模块]
    D --> E[数据提取器]
    E --> F[数据验证器]
    F --> G[数据存储模块]
    G --> H[结果导出]
    
    I[代理池管理] --> D
    J[任务调度器] --> B
    K[监控系统] --> G
```

## 🚀 快速开始

### 环境要求
- Python 3.8+
- Redis (用于Celery)
- Node.js (用于Playwright)

### 安装依赖

```bash
# 克隆项目
git clone <repository-url>
cd PythonProject_pachong

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt

# 安装Playwright浏览器驱动
playwright install chromium
```

### 基本使用

```bash
# 1. 基本数据采集
python main.py --search "laptop" --pages 3 --mode run

# 2. 数据分析
python main.py --mode analyze --file "advanced_amazon_data_20231201120000.xlsx"

# 3. 启动定时任务
celery -A celery_tasks worker --loglevel=info --beat
```

### 参数说明
- `--search`: 搜索关键词（默认为"laptop"）
- `--pages`: 爬取页数（默认为3）
- `--mode`: 运行模式（run/analyze/schedule）

## ⚙️ 配置说明

### 代理配置
在 `advanced_amazon_spider.py` 中配置代理池：

```python
self.proxies = [
    'http://username:password@proxy_host:proxy_port',
    'http://username:password@proxy_host2:proxy_port2',
    # 添加更多代理
]
```

### 爬虫参数调整
在 `advanced_amazon_spider.py` 中可以调整以下参数：
- `min_wait_time` / `max_wait_time`: 请求间隔时间
- `retry_times`: 重试次数
- `scroll_wait_time`: 页面滚动等待时间

## 🔐 反爬策略

### 多层防护机制
1. **User-Agent轮换** - 模拟真实用户访问
2. **请求频率控制** - 随机延迟，避免频率检测
3. **浏览器指纹伪装** - 绕过自动化检测
4. **IP代理池** - 多IP轮换，防封禁
5. **行为模拟** - 模拟人类浏览行为

### 智能调度
- 随机下载延迟（10-15秒）
- 控制并发请求数量（1-2个）
- 智能重试机制

## 📊 数据质量保障

### 验证机制
- 商品ID格式验证
- 价格格式验证
- 评分范围验证（0-5分）
- 数据完整性检查
- 重复数据过滤

### 质量监控
- 实时监控数据质量得分
- 自动识别异常数据
- 数据清洗和标准化

## 📈 数据采集字段

| 字段名 | 说明 | 备注 |
|--------|------|------|
| 商品ID | 亚马逊ASIN码 | 唯一标识 |
| 商品名称 | 产品标题 | 完整名称 |
| 价格 | 当前价格 | 格式化价格 |
| 销量 | 月销量或总销量 | 估算值 |
| 评分 | 用户评分 | 0-5分 |
| 评论数 | 用户评论总数 | 数字格式 |
| 品牌 | 商品品牌 | 提取品牌 |
| 类别 | 商品分类 | 分类路径 |
| 上架时间 | 首次上架时间 | 日期格式 |
| 采集时间 | 数据采集时间 | 时间戳 |
| URL | 商品页面链接 | 完整URL |
| 配送信息 | 配送详情 | 配送方式 |
| 是否Prime | Prime会员服务 | 是/否 |

## 📁 项目结构

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

## 🚨 注意事项

1. **合规使用** - 请确保数据采集行为符合相关法律法规
2. **请求频率** - 合理设置请求频率，避免对目标网站造成过大压力
3. **代理配置** - 建议使用高质量代理以提高采集成功率
4. **错误处理** - 系统包含完善的异常处理机制
5. **性能监控** - 建议部署监控系统跟踪采集性能

## 📚 文档

完整的文档可在以下位置找到：
- [系统架构](docs/architecture.md) - 详细的技术架构说明
- [安装指南](docs/installation.md) - 详细的环境配置和依赖安装
- [使用说明](docs/usage.md) - 各种使用场景的操作指南
- [配置说明](docs/configuration.md) - 各种配置参数详解

## 🤝 贡献指南

欢迎提交 Issue 和 Pull Request 来帮助改进这个项目！

1. Fork 项目
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

## 📄 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件。

## 📞 联系方式

如有问题或建议，请通过 GitHub Issues 联系我们。

---

<div align="center">

**⭐ 如果这个项目对您有帮助，请给个Star支持我们！**

</div>