# 安装指南

## 环境要求

- **操作系统**: Windows 10+, macOS 10.14+, Linux (Ubuntu 18.04+, CentOS 7+)
- **Python版本**: 3.8 - 3.12
- **内存**: ≥ 4GB RAM
- **存储**: ≥ 2GB 可用空间
- **网络**: 稳定的互联网连接

## 依赖软件

### 必需依赖
- [Python](https://www.python.org/downloads/) 3.8+
- [Node.js](https://nodejs.org/) (用于Playwright)
- [Redis](https://redis.io/download) (用于Celery)

### 可选依赖（推荐）
- Git (用于版本控制)
- Docker (用于容器化部署)

## 安装步骤

### 1. 克隆项目

```bash
# 使用HTTPS
git clone https://github.com/yourusername/amazon-data-collector.git

# 或使用SSH
git clone git@github.com:yourusername/amazon-data-collector.git

cd amazon-data-collector
```

### 2. 创建虚拟环境

```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

### 3. 安装Python依赖

```bash
# 升级pip
python -m pip install --upgrade pip

# 安装项目依赖
pip install -r requirements.txt
```

### 4. 安装Playwright浏览器

```bash
# 安装Playwright
playwright install chromium

# 验证安装
playwright install-deps
```

### 5. 配置Redis（用于任务调度）

#### Windows
```bash
# 下载并安装Redis
# 或使用Docker
docker run --name redis -p 6379:6379 -d redis:latest
```

#### macOS
```bash
# 使用Homebrew
brew install redis
brew services start redis
```

#### Linux (Ubuntu)
```bash
# 使用APT
sudo apt update
sudo apt install redis-server
sudo systemctl start redis-server
sudo systemctl enable redis-server
```

### 6. 验证安装

```bash
# 检查依赖是否正确安装
python -c "import scrapy; import playwright; import celery; print('All dependencies installed successfully')"
```

## 配置文件

### 1. 代理配置

编辑 `advanced_amazon_spider.py` 文件中的代理配置：

```python
# 代理池配置
self.proxies = [
    'http://username:password@proxy_host:proxy_port',
    'http://username2:password2@proxy_host2:proxy_port2',
    # 添加更多代理
]
```

### 2. Celery配置

编辑 `celery_config.py` 文件中的Redis连接配置：

```python
app.config_from_object({
    'broker_url': 'redis://localhost:6379/0',
    'result_backend': 'redis://localhost:6379/0',
    # 其他配置...
})
```

## 常见问题

### 1. Playwright安装失败

**问题**: Playwright浏览器安装失败
**解决方案**:
```bash
# 重新安装
playwright install chromium --with-deps

# 或使用代理
playwright install chromium --proxy=http://proxy-server:port
```

### 2. 权限错误

**问题**: 安装过程中出现权限错误
**解决方案**:
```bash
# 使用用户安装
pip install --user -r requirements.txt
```

### 3. Redis连接失败

**问题**: Celery无法连接Redis
**解决方案**:
- 检查Redis服务是否启动
- 确认配置文件中的连接地址正确
- 检查防火墙设置

## 验证安装

运行以下命令验证所有组件正常工作：

```bash
# 验证Python环境
python --version

# 验证Scrapy
scrapy version

# 验证Playwright
python -c "from playwright.sync_api import sync_playwright; print('Playwright OK')"

# 验证Celery
python -c "import celery; print('Celery OK')"
```

## 下一步

安装完成后，您可以参考 [使用说明](usage.md) 开始使用系统。