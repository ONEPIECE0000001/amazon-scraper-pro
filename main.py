import os
import sys
import time
from datetime import datetime, timedelta
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings
import argparse
from advanced_amazon_spider import AdvancedAmazonSpider


def run_amazon_scraper(search_term="laptop", pages=3, output_file=None):
    """
    运行亚马逊数据采集任务
    
    :param search_term: 搜索关键词
    :param pages: 爬取页数
    :param output_file: 输出文件名
    """
    print(f"开始采集亚马逊商品数据...")
    print(f"搜索关键词: {search_term}")
    print(f"爬取页数: {pages}")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 获取Scrapy项目设置
    settings = get_project_settings()
    
    # 创建CrawlerProcess
    process = CrawlerProcess(settings)
    
    # 启动爬虫
    try:
        process.crawl(AdvancedAmazonSpider, search=search_term, pages=pages)
        process.start()  # blocks reactor
    except KeyboardInterrupt:
        print("采集任务被用户中断")
    except Exception as e:
        print(f"采集任务发生错误: {str(e)}")
    
    print(f"数据采集完成！")
    print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


def schedule_daily_collection():
    """
    定时任务：每天凌晨执行数据采集
    """
    print("启动定时数据采集任务...")
    
    while True:
        now = datetime.now()
        # 设置在每天凌晨2点执行
        next_run = now.replace(hour=2, minute=0, second=0, microsecond=0)
        
        if now > next_run:
            next_run += timedelta(days=1)
        
        wait_time = (next_run - now).total_seconds()
        print(f"下次执行时间: {next_run.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"等待时间: {wait_time / 3600:.2f} 小时")
        
        time.sleep(wait_time)
        
        # 执行数据采集
        run_amazon_scraper(search_term="laptop", pages=5)


def analyze_data(file_path):
    """
    分析已采集的数据
    """
    try:
        import pandas as pd
        
        df = pd.read_excel(file_path)
        print(f"数据分析报告 - 文件: {file_path}")
        print(f"总商品数: {len(df)}")
        print(f"数据列: {list(df.columns)}")
        
        # 价格分析
        if '价格' in df.columns:
            price_col = df['价格'].dropna()
            # 提取价格数字
            import re
            prices = []
            for price in price_col:
                if isinstance(price, str):
                    # 提取价格中的数字部分
                    match = re.search(r'[\d,]+\.?\d*', price.replace(',', ''))
                    if match:
                        prices.append(float(match.group()))
            if prices:
                print(f"平均价格: ${sum(prices)/len(prices):.2f}")
                print(f"价格范围: ${min(prices):.2f} - ${max(prices):.2f}")
        
        # 评分分析
        if '评分' in df.columns:
            rating_col = df['评分'].dropna()
            ratings = []
            for rating in rating_col:
                if isinstance(rating, str):
                    match = re.search(r'[\d.]+', rating)
                    if match:
                        ratings.append(float(match.group()))
            if ratings:
                print(f"平均评分: {sum(ratings)/len(ratings):.2f}")
        
        # 销量分析
        if '评论数' in df.columns:
            reviews_col = df['评论数'].dropna()
            reviews = []
            for review in reviews_col:
                if str(review).isdigit():
                    reviews.append(int(review))
                else:
                    # 尝试提取数字
                    import re
                    match = re.search(r'\d+', str(review))
                    if match:
                        reviews.append(int(match.group()))
            if reviews:
                print(f"平均评论数: {sum(reviews)/len(reviews):.0f}")
        
    except ImportError:
        print("请安装pandas: pip install pandas")
    except Exception as e:
        print(f"数据分析出错: {str(e)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='亚马逊商品数据采集系统')
    parser.add_argument('--search', type=str, default='laptop', help='搜索关键词')
    parser.add_argument('--pages', type=int, default=3, help='爬取页数')
    parser.add_argument('--mode', type=str, default='run', choices=['run', 'schedule', 'analyze'], 
                       help='运行模式: run(运行一次), schedule(定时运行), analyze(分析数据)')
    parser.add_argument('--file', type=str, help='分析的文件路径(用于analyze模式)')
    
    args = parser.parse_args()
    
    if args.mode == 'run':
        run_amazon_scraper(search_term=args.search, pages=args.pages)
    elif args.mode == 'schedule':
        schedule_daily_collection()
    elif args.mode == 'analyze':
        if args.file:
            analyze_data(args.file)
        else:
            print("请提供要分析的文件路径")