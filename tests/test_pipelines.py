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
        "seller_name": None,
        "availability": "In Stock",
        "is_prime": "Yes",
        "url": "https://www.amazon.com/dp/B09XYZ1234",
        "image_url": None,
        "description": "A great product",
        "date_first_available": None,
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

    # -- scraped_at default ---------------------------------------------

    def test_scraped_at_set_when_missing(self):
        item = _item(scraped_at=None)
        result = self.pipeline.process_item(item, MagicMock())
        assert isinstance(result["scraped_at"], datetime)


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
            "asin", "title", "price", "original_price", "rating",
            "review_count", "brand", "category", "seller_name",
            "availability", "is_prime", "url", "image_url",
            "description", "date_first_available", "scraped_at",
        }
        assert set(item.fields.keys()) == expected
