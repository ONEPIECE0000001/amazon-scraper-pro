import re
import logging
from datetime import datetime
from typing import Any, Optional, Set

import pymysql
import scrapy
from scrapy.settings import Settings
from scrapy.crawler import Crawler
from scrapy.exceptions import DropItem


logger = logging.getLogger(__name__)


class DataCleaningPipeline:
    """清洗字段：价格转 float、评分/评论数转数字、ASIN 校验、字符串 strip、时间默认值"""

    ASIN_PATTERN = re.compile(r'^[A-Z0-9]{10}$')
    NUMBER_PATTERN = re.compile(r'[\d.]+')

    def process_item(self, item: scrapy.Item, spider: scrapy.Spider) -> scrapy.Item:
        # --- price / original_price ---
        for field in ('price', 'original_price'):
            val = item.get(field)
            if val:
                cleaned = re.sub(r'[$,\s]', '', str(val))
                # detect negative prices
                if cleaned.strip().startswith('-'):
                    item[field] = None
                else:
                    m = self.NUMBER_PATTERN.search(cleaned)
                    if m:
                        try:
                            item[field] = float(m.group())
                        except ValueError:
                            item[field] = None
                    else:
                        item[field] = None
            elif val is not None and val != '':
                pass  # keep non-empty falsy values as-is
            else:
                item[field] = None  # empty string or None → None

        # --- rating ---
        raw_rating = item.get('rating')
        if raw_rating:
            raw_str = str(raw_rating)
            # detect negative ratings before number extraction
            if raw_str.strip().startswith('-'):
                item['rating'] = None
            else:
                m = self.NUMBER_PATTERN.search(raw_str)
                if m:
                    try:
                        r = float(m.group())
                        item['rating'] = r if 0 <= r <= 5 else None
                    except ValueError:
                        item['rating'] = None
                else:
                    item['rating'] = None

        # --- review_count ---
        raw_reviews = item.get('review_count')
        if raw_reviews:
            cleaned = str(raw_reviews).replace(',', '')
            m = re.search(r'\d+', cleaned)
            if m:
                try:
                    item['review_count'] = int(m.group())
                except ValueError:
                    item['review_count'] = None
            else:
                item['review_count'] = None

        # --- asin 校验 ---
        asin = item.get('asin', '')
        if not self.ASIN_PATTERN.match(str(asin)):
            raise DropItem(f"Invalid ASIN: {asin}")

        # --- 字符串字段 strip ---
        for field in ('title', 'brand', 'category', 'description'):
            val = item.get(field)
            if isinstance(val, str):
                item[field] = val.strip()

        # --- scraped_at 默认值 ---
        if not item.get('scraped_at'):
            item['scraped_at'] = datetime.now()

        return item


class DeduplicationPipeline:
    """基于 ASIN 去重，重复的 item 直接 Drop"""

    def __init__(self) -> None:
        self.seen_asins: Set[str] = set()

    def process_item(self, item: scrapy.Item, spider: scrapy.Spider) -> scrapy.Item:
        asin = item.get('asin')
        if asin in self.seen_asins:
            logger.debug(f"Dropping duplicate ASIN: {asin}")
            raise DropItem(f"Duplicate ASIN: {asin}")
        self.seen_asins.add(asin)
        return item


class MySQLPipeline:
    """写入 MySQL，ASIN 为主键，重复则更新价格/评分/评论数/可用性/抓取时间"""

    def __init__(self, settings: Settings) -> None:
        self.enabled: bool = settings.getbool('MYSQL_ENABLED', True)
        self.host = settings.get('MYSQL_HOST', 'localhost')
        self.port = settings.getint('MYSQL_PORT', 3306)
        self.user = settings.get('MYSQL_USER', 'root')
        self.password = settings.get('MYSQL_PASSWORD', '')
        self.database = settings.get('MYSQL_DATABASE', 'amazon_scraper')
        self.conn = None
        self.cursor = None

    @classmethod
    def from_crawler(cls, crawler: Crawler) -> 'MySQLPipeline':
        return cls(crawler.settings)

    def open_spider(self, spider: scrapy.Spider) -> None:
        if not self.enabled:
            logger.info("MySQL pipeline disabled (MYSQL_ENABLED=False)")
            return

        try:
            self.conn = pymysql.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=self.database,
                charset='utf8mb4',
            )
            self.cursor = self.conn.cursor()
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS products (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    asin VARCHAR(10) NOT NULL UNIQUE,
                    title TEXT,
                    price FLOAT,
                    original_price FLOAT,
                    rating FLOAT,
                    review_count INT,
                    brand VARCHAR(255),
                    category VARCHAR(255),
                    seller_name VARCHAR(255),
                    availability VARCHAR(255),
                    is_prime VARCHAR(10),
                    url TEXT,
                    image_url TEXT,
                    description TEXT,
                    date_first_available VARCHAR(255),
                    scraped_at DATETIME,
                    KEY idx_asin (asin)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            self.conn.commit()
            logger.info(f"MySQL connected: {self.host}:{self.port}/{self.database}")
        except pymysql.Error as e:
            logger.warning(f"MySQL connection failed: {e}")
            self.conn = None
            self.cursor = None

    def process_item(self, item: scrapy.Item, spider: scrapy.Spider) -> scrapy.Item:
        if not self.conn or not self.cursor:
            return item

        try:
            self.cursor.execute("""
                INSERT INTO products
                    (asin, title, price, original_price, rating, review_count,
                     brand, category, seller_name, availability, is_prime,
                     url, image_url, description, date_first_available, scraped_at)
                VALUES
                    (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    price = VALUES(price),
                    rating = VALUES(rating),
                    review_count = VALUES(review_count),
                    availability = VALUES(availability),
                    scraped_at = VALUES(scraped_at)
            """, (
                item.get('asin'), item.get('title'), item.get('price'),
                item.get('original_price'), item.get('rating'), item.get('review_count'),
                item.get('brand'), item.get('category'), item.get('seller_name'),
                item.get('availability'), item.get('is_prime'),
                item.get('url'), item.get('image_url'), item.get('description'),
                item.get('date_first_available'), item.get('scraped_at'),
            ))
            self.conn.commit()
        except pymysql.Error as e:
            logger.warning(f"MySQL insert failed for {item.get('asin')}: {e}")

        return item

    def close_spider(self, spider: scrapy.Spider) -> None:
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
            logger.info("MySQL connection closed")
