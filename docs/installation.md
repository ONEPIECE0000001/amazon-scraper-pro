# 安装指南

## 环境要求

- Python 3.9+
- Redis（定时调度需要，可选）
- 稳定的互联网连接

## 安装步骤

### 1. 安装 Python 依赖

```bash
cd python-amazon-spider
pip install -r requirements.txt
```

### 2. 安装 Playwright 浏览器

```bash
playwright install chromium
```

### 3. （可选）安装 Redis

定时调度功能需要 Redis。推荐用 Docker：

```bash
docker run --name redis -p 6379:6379 -d redis:latest
```

Windows 用户也可直接下载：https://github.com/tporadowski/redis/releases

## 验证安装

```bash
# 依赖检查
python -c "import scrapy, playwright; print('OK')"

# Playwright 检查
python -c "from playwright.sync_api import sync_playwright; print('OK')"

# 运行测试
pytest tests/ -q
```

## 配置

复制环境变量模板并根据需要修改：

```bash
cp .env.example .env
```

主要配置项：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `MYSQL_ENABLED` | 是否启用 MySQL | True |
| `MYSQL_HOST` | MySQL 地址 | localhost |
| `MYSQL_PASSWORD` | MySQL 密码 | (空) |
| `PROXY_ENABLED` | 是否启用代理池 | True |
| `ROBOTSTXT_OBEY` | 是否遵守 robots.txt | False |
| `LOG_LEVEL` | 日志级别 | INFO |
| `CUSTOM_PROXIES` | 自定义付费代理 | (空) |

## 常见问题

### Playwright 安装失败

```bash
playwright install chromium --with-deps
# 或通过代理
playwright install chromium --proxy=http://proxy:port
```

### Scrapy 导入报错 (OpenSSL)

```bash
pip install "cryptography>=41.0,<44.0" "pyOpenSSL>=23.0,<25.0"
```

### Redis 连接失败

- 确认 Redis 服务已启动
- 检查 `celery_config.py` 中 `broker_url` 地址是否正确

## 下一步

参考 [使用说明](usage.md) 开始采集数据。
