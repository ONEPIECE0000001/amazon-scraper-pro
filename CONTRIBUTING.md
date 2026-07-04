# 贡献指南

感谢你对亚马逊爬虫项目的关注！

## 项目结构

```
python-amazon-spider/
├── amazon_spider/
│   ├── items.py                       # AmazonProductItem (16 字段)
│   ├── pipelines.py                   # 清洗 → 去重 → MySQL
│   ├── spiders/amazon_spider.py       # 主爬虫
│   └── middlewares/
│       ├── stealth_middleware.py      # playwright-stealth 注入
│       ├── retry_middleware.py        # 指数退避重试
│       └── proxy_middleware.py        # 代理注入 + 故障切换
│
├── proxy_pool.py                      # 代理池
├── data_validator.py                  # 数据验证
├── celery_config.py                   # Celery 调度
├── celery_tasks.py                    # Celery 任务
├── logging_config.py                  # 日志配置
├── main.py                            # CLI 入口
├── settings.py                        # Scrapy 配置
│
└── tests/
    ├── test_pipelines.py
    ├── test_spider.py
    ├── test_middlewares.py
    ├── test_data_validator.py
    └── test_proxy_pool.py
```

## 开发环境设置

```bash
pip install -r requirements.txt
playwright install chromium

# 安装开发工具（可选）
pip install pre-commit ruff mypy
pre-commit install
```

## 代码风格

- Python 3.9+，类型注解推荐但不强制
- 使用 ruff 进行 linting 和格式化：`ruff check . && ruff format .`
- 双引号字符串，100 字符行宽
- 日志使用 `logging.getLogger(__name__)`，禁止裸 `print()`

## 提交前检查

```bash
# 运行所有测试
pytest tests/ -v

# 运行 lint
ruff check .

# 运行类型检查
mypy amazon_spider/ --ignore-missing-imports
```

## Pull Request 流程

1. Fork 项目
2. 创建功能分支：`git checkout -b feature/your-feature`
3. 编写代码 + 测试
4. 确保 `pytest tests/ -v` 全部通过
5. 提交 PR

## 测试指南

- 所有新功能需有对应测试
- 测试文件放在 `tests/` 目录
- 使用 pytest fixture 管理测试状态
- 网络相关测试需 mock 外部请求

## 添加新中间件

1. 在 `amazon_spider/middlewares/` 创建新文件
2. 在 `settings.py` 的 `DOWNLOADER_MIDDLEWARES` 中注册
3. 在 `tests/` 中添加对应测试

## 添加新 Pipeline

1. 在 `amazon_spider/pipelines.py` 添加新类
2. 在 `settings.py` 的 `ITEM_PIPELINES` 中注册（分配合理优先级）
3. 在 `tests/test_pipelines.py` 添加测试
