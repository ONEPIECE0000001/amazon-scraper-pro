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
        for field in ('title', 'brand', 'category',
                      'bsr', 'coupon_text', 'fulfillment_type', 'sold_by'):
            val = item.get(field)
            if isinstance(val, str):
                item[field] = val.strip()

        # --- answered_questions → int ---
        aq = item.get('answered_questions')
        if aq is not None:
            try:
                item['answered_questions'] = int(aq)
            except (ValueError, TypeError):
                item['answered_questions'] = None

        # --- variation_count → int ---
        vc = item.get('variation_count')
        if vc is not None:
            try:
                item['variation_count'] = int(vc)
            except (ValueError, TypeError):
                item['variation_count'] = None

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


class SQLitePipeline:
    """写入 SQLite，零依赖本地数据库，适合开发和小规模使用。

    ASIN 为主键，重复则更新价格/评分/评论数/可用性/抓取时间。
    """

    def __init__(self, settings: Settings) -> None:
        self.enabled = settings.getbool('SQLITE_ENABLED', True)
        self.db_path = settings.get('SQLITE_PATH', 'amazon_data.db')

    @classmethod
    def from_crawler(cls, crawler: Crawler) -> 'SQLitePipeline':
        return cls(crawler.settings)

    def open_spider(self, spider: scrapy.Spider) -> None:
        if not self.enabled:
            logger.info("SQLite pipeline disabled (SQLITE_ENABLED=False)")
            return

        import sqlite3
        self.conn = sqlite3.connect(self.db_path)
        self.conn.execute("PRAGMA journal_mode=WAL")

        # Auto-migrate: add missing columns for old databases
        try:
            cols = {r[1] for r in self.conn.execute("PRAGMA table_info(products)")}
            if cols:
                # Drop old table if pre-July-2025 schema (no keyword column)
                if 'keyword' not in cols:
                    logger.info("SQLite: pre-v2 schema detected, recreating table")
                    self.conn.execute("DROP TABLE IF EXISTS products")
                else:
                    # Add any missing columns (ALTER TABLE ADD COLUMN is safe in SQLite)
                    desired_cols = {
                        'keyword': 'TEXT NOT NULL DEFAULT \'\'',
                        'asin': 'TEXT NOT NULL',
                        'title': 'TEXT',
                        'price': 'REAL',
                        'original_price': 'REAL',
                        'rating': 'REAL',
                        'review_count': 'INTEGER',
                        'brand': 'TEXT',
                        'category': 'TEXT',
                        'availability': 'TEXT',
                        'is_prime': 'TEXT',
                        'image_url': 'TEXT',
                        'date_first_available': 'TEXT',
                        'bsr': 'TEXT',
                        'coupon_text': 'TEXT',
                        'answered_questions': 'INTEGER',
                        'variation_count': 'INTEGER',
                        'fulfillment_type': 'TEXT',
                        'sold_by': 'TEXT',
                        'scraped_at': 'TEXT',
                        'created_at': 'TEXT DEFAULT (datetime(\'now\'))',
                    }
                    for col, col_def in desired_cols.items():
                        if col not in cols:
                            try:
                                self.conn.execute(
                                    f"ALTER TABLE products ADD COLUMN {col} {col_def}"
                                )
                                logger.info(f"SQLite: added missing column '{col}'")
                            except sqlite3.OperationalError as e:
                                logger.warning(f"SQLite: failed to add column '{col}': {e}")
        except sqlite3.OperationalError:
            pass

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                keyword     TEXT    NOT NULL DEFAULT '',
                asin        TEXT    NOT NULL,
                title       TEXT,
                price       REAL,
                original_price REAL,
                rating      REAL,
                review_count INTEGER,
                brand       TEXT,
                category    TEXT,
                availability TEXT,
                is_prime    TEXT,
                image_url   TEXT,
                date_first_available TEXT,
                bsr                     TEXT,
                coupon_text             TEXT,
                answered_questions      INTEGER,
                variation_count         INTEGER,
                fulfillment_type        TEXT,
                sold_by                 TEXT,
                scraped_at  TEXT,
                created_at  TEXT DEFAULT (datetime('now')),
                UNIQUE(keyword, asin)
            )
        """)
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_asin ON products(asin)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_keyword ON products(keyword)")

        # ── price_history table — append-only time series ──────────────
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS price_history (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                keyword     TEXT    NOT NULL,
                asin        TEXT    NOT NULL,
                price       REAL,
                bsr         TEXT,
                review_count INTEGER,
                scraped_at  TEXT    NOT NULL,
                UNIQUE(keyword, asin, scraped_at)
            )
        """)
        # Auto-migrate: add review_count to existing price_history tables
        try:
            ph_cols = {r[1] for r in self.conn.execute("PRAGMA table_info(price_history)")}
            if 'review_count' not in ph_cols:
                self.conn.execute(
                    "ALTER TABLE price_history ADD COLUMN review_count INTEGER"
                )
                logger.info("SQLite: added missing column 'review_count' to price_history")
        except sqlite3.OperationalError:
            pass
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ph_asin ON price_history(asin)"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ph_keyword ON price_history(keyword)"
        )
        self.conn.commit()

    def process_item(self, item: scrapy.Item, spider: scrapy.Spider) -> scrapy.Item:
        if not self.enabled:
            return item

        import sqlite3
        try:
            self.conn.execute("""
                INSERT INTO products
                    (keyword, asin, title, price, original_price, rating, review_count,
                     brand, category, availability, is_prime,
                     image_url, date_first_available,
                     bsr, coupon_text, answered_questions, variation_count,
                     fulfillment_type, sold_by, scraped_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(keyword, asin) DO UPDATE SET
                    title       = excluded.title,
                    price       = excluded.price,
                    original_price = excluded.original_price,
                    rating      = excluded.rating,
                    review_count = excluded.review_count,
                    brand       = excluded.brand,
                    category    = excluded.category,
                    availability = excluded.availability,
                    is_prime    = excluded.is_prime,
                    image_url   = excluded.image_url,
                    bsr         = excluded.bsr,
                    coupon_text = excluded.coupon_text,
                    answered_questions = excluded.answered_questions,
                    variation_count    = excluded.variation_count,
                    fulfillment_type   = excluded.fulfillment_type,
                    sold_by     = excluded.sold_by,
                    scraped_at  = excluded.scraped_at
            """, (
                item.get('keyword', ''), item.get('asin'), item.get('title'), item.get('price'),
                item.get('original_price'), item.get('rating'), item.get('review_count'),
                item.get('brand'), item.get('category'),
                item.get('availability'), item.get('is_prime'),
                item.get('image_url'), item.get('date_first_available'),
                item.get('bsr'), item.get('coupon_text'), item.get('answered_questions'),
                item.get('variation_count'), item.get('fulfillment_type'), item.get('sold_by'),
                item.get('scraped_at'),
            ))
            # ── dual-write: append to price_history ────────────────────
            self.conn.execute("""
                INSERT OR IGNORE INTO price_history
                    (keyword, asin, price, bsr, review_count, scraped_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                item.get('keyword', ''),
                item.get('asin'),
                item.get('price'),
                item.get('bsr'),
                item.get('review_count'),
                item.get('scraped_at') or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ))
            self.conn.commit()
        except sqlite3.Error as e:
            logger.warning(f"SQLite insert failed for {item.get('asin')}: {e}")

        return item

    def close_spider(self, spider: scrapy.Spider) -> None:
        if hasattr(self, 'conn') and self.conn:
            self.conn.close()
            logger.info("SQLite connection closed")


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
                    availability VARCHAR(255),
                    is_prime VARCHAR(10),
                    image_url TEXT,
                    date_first_available VARCHAR(255),
                    bsr TEXT,
                    coupon_text TEXT,
                    answered_questions INT,
                    variation_count INT,
                    fulfillment_type VARCHAR(50),
                    sold_by VARCHAR(255),
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
                     brand, category, availability, is_prime,
                     image_url, date_first_available,
                     bsr, coupon_text, answered_questions, variation_count,
                     fulfillment_type, sold_by, scraped_at)
                VALUES
                    (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                     %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    price = VALUES(price),
                    rating = VALUES(rating),
                    review_count = VALUES(review_count),
                    availability = VALUES(availability),
                    bsr = VALUES(bsr),
                    coupon_text = VALUES(coupon_text),
                    answered_questions = VALUES(answered_questions),
                    variation_count = VALUES(variation_count),
                    fulfillment_type = VALUES(fulfillment_type),
                    sold_by = VALUES(sold_by),
                    scraped_at = VALUES(scraped_at)
            """, (
                item.get('asin'), item.get('title'), item.get('price'),
                item.get('original_price'), item.get('rating'), item.get('review_count'),
                item.get('brand'), item.get('category'),
                item.get('availability'), item.get('is_prime'),
                item.get('image_url'), item.get('date_first_available'),
                item.get('bsr'), item.get('coupon_text'), item.get('answered_questions'),
                item.get('variation_count'), item.get('fulfillment_type'), item.get('sold_by'),
                item.get('scraped_at'),
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
