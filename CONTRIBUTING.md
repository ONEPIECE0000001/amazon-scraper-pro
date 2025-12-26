# 贡献指南

欢迎为亚马逊电商平台商品数据智能采集系统做出贡献！本文档提供了贡献代码、报告问题和改进建议的指南。

## 📋 目录

- [开发环境设置](#开发环境设置)
- [项目结构](#项目结构)
- [代码规范](#代码规范)
- [提交规范](#提交规范)
- [测试要求](#测试要求)
- [报告问题](#报告问题)
- [功能请求](#功能请求)

## 开发环境设置

### 环境要求
- Python 3.8+
- Git
- Node.js (用于Playwright)

### 设置步骤

1. **Fork 仓库**
   ```bash
   git clone https://github.com/YOUR_USERNAME/amazon-data-collector.git
   cd amazon-data-collector
   ```

2. **创建虚拟环境**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   # 或
   venv\Scripts\activate  # Windows
   ```

3. **安装依赖**
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```

4. **运行测试**
   ```bash
   python -m pytest test_system.py
   ```

## 项目结构

```
amazon-data-collector/
├── advanced_amazon_spider.py    # 高级爬虫实现
├── data_validator.py           # 数据验证模块
├── proxy_manager.py            # 代理管理模块
├── celery_tasks.py             # 任务调度模块
├── main.py                    # 主程序入口
├── tests/                     # 测试文件
├── docs/                      # 文档
└── requirements.txt           # 依赖列表
```

## 代码规范

### Python 代码规范
- 遵循 [PEP 8](https://pep8.org/) 代码风格
- 使用 [Google 风格](https://google.github.io/styleguide/pyguide.html) 的文档字符串
- 变量和函数名使用 snake_case
- 类名使用 PascalCase
- 常量使用 UPPER_CASE

### 代码示例

```python
def get_random_proxy(self):
    """
    获取随机代理
    
    Returns:
        dict: 代理配置字典，如果无可用代理则返回 None
    """
    if not self.proxy_list:
        return None
        
    available_proxies = [
        p for i, p in enumerate(self.proxy_list) 
        if self.proxy_status.get(i, True)
    ]
    
    if not available_proxies:
        return None
        
    self.current_proxy = random.choice(available_proxies)
    return self.current_proxy
```

## 提交规范

### 提交消息格式
```
<type>(<scope>): <subject>
<BLANK LINE>
<body>
<BLANK LINE>
<footer>
```

### 类型说明
- `feat`: 新功能
- `fix`: 修复bug
- `docs`: 文档更新
- `style`: 代码格式调整
- `refactor`: 代码重构
- `test`: 测试相关
- `chore`: 构建工具或辅助工具变动

### 提交示例
```
feat(crawler): 添加用户代理轮换功能

- 实现随机User-Agent生成器
- 添加User-Agent池管理
- 集成到请求头中

Closes #123
```

## 测试要求

### 单元测试
- 为新功能编写单元测试
- 确保现有测试仍然通过
- 测试覆盖率应保持在80%以上

### 测试文件结构
```python
def test_proxy_manager():
    """测试代理管理器功能"""
    pm = ProxyManager()
    assert pm is not None
    
def test_data_validator():
    """测试数据验证器功能"""
    validator = DataValidator()
    result = validator.validate_product_id("B08N5WRWNW")
    assert result is True
```

### 运行测试
```bash
# 运行所有测试
python -m pytest

# 运行特定测试文件
python -m pytest test_system.py

# 运行测试并生成覆盖率报告
python -m pytest --cov=.
```

## 报告问题

### 问题模板
当报告问题时，请包含以下信息：

1. **环境信息**
   - Python 版本
   - 操作系统
   - 依赖包版本

2. **重现步骤**
   - 详细的操作步骤
   - 相关的代码片段

3. **期望行为**
   - 期望发生什么

4. **实际行为**
   - 实际发生了什么

5. **错误信息**
   - 完整的错误消息和堆栈跟踪

### 问题示例
```
标题: 爬虫在处理特定商品页面时崩溃

环境:
- Python: 3.11.0
- OS: Ubuntu 22.04
- Scrapy: 2.13.0

重现步骤:
1. 运行命令: python main.py --search "laptop" --pages 1
2. 爬虫在处理第3个商品时崩溃

期望行为: 爬虫应该成功处理所有商品

实际行为: 爬虫崩溃并抛出异常

错误信息:
Traceback (most recent call last):
  ...
```

## 功能请求

当提出新功能请求时，请说明：

1. **功能描述**
2. **使用场景**
3. **实现建议**
4. **相关问题**

## 分支管理

- `main`: 生产就绪代码
- `develop`: 开发中功能
- `feature/*`: 新功能分支
- `bugfix/*`: 修复分支
- `hotfix/*`: 紧急修复分支

### 分支命名约定
```
feature/user-agent-rotation
bugfix/proxy-authentication
hotfix/critical-security-fix
```

## 审查流程

1. 提交 Pull Request
2. 自动测试运行
3. 代码审查
4. 修改（如果需要）
5. 合并

## 联系方式

如有疑问，请通过 GitHub Issues 联系项目维护者。

---

感谢您为项目做出贡献！ 🎉