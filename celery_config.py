from celery import Celery
import os

# 创建Celery实例
app = Celery('amazon_scraper')

# 配置Celery
app.config_from_object({
    'broker_url': 'redis://localhost:6379/0',
    'result_backend': 'redis://localhost:6379/0',
    'task_serializer': 'json',
    'accept_content': ['json'],
    'result_serializer': 'json',
    'timezone': 'UTC',
    'enable_utc': True,
    'beat_schedule': {
        'daily-amazon-scraper': {
            'task': 'celery_tasks.run_amazon_scraping',
            'schedule': 86400.0,  # 每天运行一次 (24*60*60 秒)
        },
    },
})

if __name__ == '__main__':
    app.start()