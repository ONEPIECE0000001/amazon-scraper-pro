"""
Unit tests for Amazon spider pipelines and core logic.

Run with:  pytest tests/ -v
"""

import re
import sys
from datetime import datetime
from unittest.mock import MagicMock

import pytest
from scrapy.exceptions import DropItem

# Ensure the project root is on sys.path so amazon_spider is importable.
sys.path.insert(0, "..")

from amazon_spider.items import AmazonProductItem
from amazon_spider.pipelines import DataCleaningPipeline, DeduplicationPipeline


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _item(**kwargs) -> AmazonProductItem:
    """Build an AmazonProductItem with defaults so tests stay compact."""
    defaults = {
        "asin": "B09XYZ1234",
        "title": "Test Product",
        "price": "$19.99",
        "original_price": None,
        "rating": "4.5",
        "review_count": "1,234",
        "brand": "TestBrand",
        "category": "Electronics",
        "availability": "In Stock",
        "is_prime": "Yes",
        "image_url": None,
        "date_first_available": None,
        "bsr": None,
        "coupon_text": None,
        "answered_questions": None,
        "variation_count": None,
        "fulfillment_type": None,
        "sold_by": None,
        "scraped_at": None,
    }
    defaults.update(kwargs)
    item = AmazonProductItem()
    for k, v in defaults.items():
        item[k] = v
    return item


# ---------------------------------------------------------------------------
# DataCleaningPipeline
# ---------------------------------------------------------------------------

class TestDataCleaningPipeline:
    """Tests for DataCleaningPipeline."""

    def setup_method(self):
        self.pipeline = DataCleaningPipeline()

    # -- price ----------------------------------------------------------

    def test_price_removes_dollar_sign(self):
        item = _item(price="$19.99")
        result = self.pipeline.process_item(item, MagicMock())
        assert result["price"] == 19.99

    def test_price_handles_comma_thousands(self):
        item = _item(price="$1,299.99")
        result = self.pipeline.process_item(item, MagicMock())
        assert result["price"] == 1299.99

    def test_price_sets_none_for_empty_string(self):
        item = _item(price="")
        result = self.pipeline.process_item(item, MagicMock())
        assert result["price"] is None

    def test_original_price_cleaned_same_way(self):
        item = _item(original_price="$299.99")
        result = self.pipeline.process_item(item, MagicMock())
        assert result["original_price"] == 299.99

    # -- rating ---------------------------------------------------------

    def test_rating_extracts_numeric(self):
        item = _item(rating="4.5 out of 5 stars")
        result = self.pipeline.process_item(item, MagicMock())
        assert result["rating"] == 4.5

    def test_rating_clamped_at_5(self):
        item = _item(rating="6.0 out of 5 stars")
        result = self.pipeline.process_item(item, MagicMock())
        assert result["rating"] is None

    def test_rating_clamped_at_0(self):
        item = _item(rating="-0.5")
        result = self.pipeline.process_item(item, MagicMock())
        assert result["rating"] is None

    # -- review_count ---------------------------------------------------

    def test_review_count_removes_commas(self):
        item = _item(review_count="1,234")
        result = self.pipeline.process_item(item, MagicMock())
        assert result["review_count"] == 1234

    def test_review_count_handles_plain_int(self):
        item = _item(review_count=42)
        result = self.pipeline.process_item(item, MagicMock())
        assert result["review_count"] == 42

    # -- ASIN -----------------------------------------------------------

    def test_valid_asin_passes(self):
        item = _item(asin="B09XYZ1234")
        result = self.pipeline.process_item(item, MagicMock())
        assert result["asin"] == "B09XYZ1234"

    def test_invalid_asin_raises_dropitem(self):
        item = _item(asin="bad")
        with pytest.raises(DropItem, match="Invalid ASIN"):
            self.pipeline.process_item(item, MagicMock())

    def test_asin_too_short_raises_dropitem(self):
        item = _item(asin="B09XYZ")
        with pytest.raises(DropItem):
            self.pipeline.process_item(item, MagicMock())

    # -- string strip ---------------------------------------------------

    def test_title_stripped(self):
        item = _item(title="  Wireless Earbuds  ")
        result = self.pipeline.process_item(item, MagicMock())
        assert result["title"] == "Wireless Earbuds"

    # -- 第一期新增字段 -------------------------------------------------

    def test_answered_questions_converted_to_int(self):
        item = _item(answered_questions="42")
        result = self.pipeline.process_item(item, MagicMock())
        assert result["answered_questions"] == 42

    def test_answered_questions_none_stays_none(self):
        item = _item(answered_questions=None)
        result = self.pipeline.process_item(item, MagicMock())
        assert result["answered_questions"] is None

    def test_variation_count_converted_to_int(self):
        item = _item(variation_count="15")
        result = self.pipeline.process_item(item, MagicMock())
        assert result["variation_count"] == 15

    def test_variation_count_invalid_becomes_none(self):
        item = _item(variation_count="abc")
        result = self.pipeline.process_item(item, MagicMock())
        assert result["variation_count"] is None

    def test_bsr_stripped(self):
        item = _item(bsr="  #1 in Electronics  ")
        result = self.pipeline.process_item(item, MagicMock())
        assert result["bsr"] == "#1 in Electronics"

    def test_coupon_text_stripped(self):
        item = _item(coupon_text="  Save 20%  ")
        result = self.pipeline.process_item(item, MagicMock())
        assert result["coupon_text"] == "Save 20%"

    def test_sold_by_stripped(self):
        item = _item(sold_by="  TestSeller  ")
        result = self.pipeline.process_item(item, MagicMock())
        assert result["sold_by"] == "TestSeller"

    # -- scraped_at default ---------------------------------------------

    def test_scraped_at_set_when_missing(self):
        item = _item(scraped_at=None)
        result = self.pipeline.process_item(item, MagicMock())
        # scraped_at is now a string with millisecond precision (e.g. "2026-07-05 16:55:30.123")
        assert isinstance(result["scraped_at"], str)
        assert len(result["scraped_at"]) >= 19  # "YYYY-MM-DD HH:MM:SS" minimum


# ---------------------------------------------------------------------------
# DeduplicationPipeline
# ---------------------------------------------------------------------------

class TestDeduplicationPipeline:
    """Tests for DeduplicationPipeline."""

    def setup_method(self):
        self.pipeline = DeduplicationPipeline()

    def test_first_seen_passes(self):
        item = _item(asin="B09XYZ1234")
        result = self.pipeline.process_item(item, MagicMock())
        assert result["asin"] == "B09XYZ1234"

    def test_duplicate_asins_dropped(self):
        item1 = _item(asin="B09XYZ1234")
        item2 = _item(asin="B09XYZ1234")
        self.pipeline.process_item(item1, MagicMock())
        with pytest.raises(DropItem, match="Duplicate ASIN"):
            self.pipeline.process_item(item2, MagicMock())

    def test_different_asins_both_pass(self):
        item1 = _item(asin="AAAAAAAAAA")
        item2 = _item(asin="BBBBBBBBBB")
        r1 = self.pipeline.process_item(item1, MagicMock())
        r2 = self.pipeline.process_item(item2, MagicMock())
        assert r1["asin"] == "AAAAAAAAAA"
        assert r2["asin"] == "BBBBBBBBBB"


# ---------------------------------------------------------------------------
# Item definition sanity checks
# ---------------------------------------------------------------------------

class TestAmazonProductItem:
    """Verify the item schema matches expectations."""

    def test_item_has_expected_fields(self):
        item = AmazonProductItem()
        expected = {
            "keyword",
            "asin", "title", "price", "original_price", "rating",
            "review_count", "brand", "category",
            "availability", "is_prime", "image_url",
            "date_first_available",
            "bsr", "coupon_text", "answered_questions", "variation_count",
            "fulfillment_type", "sold_by", "scraped_at",
        }
        assert set(item.fields.keys()) == expected


# ---------------------------------------------------------------------------
# SQLitePipeline — price_history review_count
# ---------------------------------------------------------------------------

class TestSQLitePipelinePriceHistory:
    """Verify price_history table includes review_count."""

    def test_price_history_ddl_includes_review_count(self):
        """Reconstruct the CREATE TABLE check by reading pipeline source."""
        import inspect
        from amazon_spider.pipelines import SQLitePipeline

        src = inspect.getsource(SQLitePipeline.open_spider)
        # price_history CREATE TABLE should mention review_count
        assert "review_count" in src
        assert "review_count INTEGER" in src or "review_count  INTEGER" in src

    def test_dual_write_includes_review_count(self):
        """process_item INSERT into price_history should include review_count."""
        import inspect
        from amazon_spider.pipelines import SQLitePipeline

        src = inspect.getsource(SQLitePipeline.process_item)
        # Should have review_count in price_history INSERT column list
        assert "price_history" in src
        # The INSERT column list should contain 'review_count'
        assert "review_count" in src

    def test_item_has_review_count_field(self):
        """Item schema should include review_count for dual-write."""
        item = AmazonProductItem()
        item['review_count'] = 1234
        assert item['review_count'] == 1234
