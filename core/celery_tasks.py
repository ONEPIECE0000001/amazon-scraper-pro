from celery import Celery
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings
from amazon_spider.spiders.amazon_spider import AdvancedAmazonSpider
from core.logging_config import configure_logging
import os
import sys

logger = configure_logging("celery_tasks")

# 从配置文件加载Celery配置
app = Celery('amazon_scraper')
app.config_from_object('core.celery_config')

@app.task
def run_amazon_scraping(search_term="laptop", pages=5):
    """
    Celery任务：运行亚马逊数据采集
    """
    logger.info("开始执行定时采集任务, 关键词=%s, 页数=%d", search_term, pages)
    
    try:
        # 获取Scrapy项目设置
        settings = get_project_settings()
        
        # 创建CrawlerProcess
        process = CrawlerProcess(settings)
        
        # 启动爬虫
        process.crawl(AdvancedAmazonSpider, keyword=search_term, max_pages=pages)
        process.start()  # blocks reactor
        
        logger.info("定时采集任务完成")
        return {"status": "success", "message": "采集任务完成"}

    except Exception as e:
        logger.error("采集任务失败: %s", str(e))
        return {"status": "error", "message": str(e)}


def start_scheduler():
    """
    启动定时任务调度器
    """
    app.start(argv=['worker', '--loglevel=info', '--beat'])


if __name__ == '__main__':
    start_scheduler()