"""
Bilingual CSV exporter — replaces English headers with Chinese annotations.
"""

from scrapy.exporters import CsvItemExporter


# Mapping: English field name → Chinese header (with English in parentheses)
HEADER_MAP = {
    "keyword": "搜索关键词(keyword)",
    "asin": "商品ID(asin)",
    "title": "商品标题(title)",
    "price": "价格(price)",
    "original_price": "原价(original_price)",
    "rating": "评分(rating)",
    "review_count": "评论数(review_count)",
    "brand": "品牌(brand)",
    "category": "类目(category)",
    "seller_name": "卖家(seller_name)",
    "availability": "库存/物流(availability)",
    "is_prime": "是否Prime(is_prime)",
    "url": "商品链接(url)",
    "image_url": "图片链接(image_url)",
    "description": "描述(description)",
    "date_first_available": "上架日期(date_first_available)",
    "scraped_at": "抓取时间(scraped_at)",
}


# Fixed column order for CSV output (most important fields first)
FIELD_ORDER = [
    "keyword",
    "asin", "title", "price", "original_price", "rating", "review_count",
    "brand", "category", "seller_name", "availability", "is_prime",
    "description", "date_first_available",
    "url", "image_url", "scraped_at",
]


class BilingualCsvExporter(CsvItemExporter):
    """CsvItemExporter that writes Chinese-English bilingual headers."""

    def _write_headers_and_set_fields_to_export(self, item):
        if not self.include_headers_line:
            return
        if not self.fields_to_export:
            self.fields_to_export = list(FIELD_ORDER)
        bilingual_headers = [
            HEADER_MAP.get(f, f) for f in self.fields_to_export
        ]
        self.csv_writer.writerow(bilingual_headers)
        self.include_headers_line = False
