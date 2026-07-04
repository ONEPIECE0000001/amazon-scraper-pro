"""
Unit tests for DataValidator and DataQualityMonitor.

Run with:  pytest tests/test_data_validator.py -v
"""

import sys
from unittest.mock import patch

import pandas as pd
import pytest

sys.path.insert(0, "..")

from core.data_validator import DataValidator, DataQualityMonitor, validate_amazon_data_file


# ---------------------------------------------------------------------------
# DataValidator — field validators
# ---------------------------------------------------------------------------

class TestDataValidatorFields:
    @pytest.fixture
    def validator(self):
        return DataValidator()

    # -- product_id / ASIN ------------------------------------------------

    @pytest.mark.parametrize("asin", [
        "B08N5WRWNW",
        "B07ZPC9Q4K",
        "0123456789",
        "ABCDEFGHIJ",
    ])
    def test_valid_asins(self, validator, asin):
        assert validator.validate_product_id(asin) is True

    @pytest.mark.parametrize("asin", [
        "",
        None,
        123,
        "TOO_SHORT",
        "TOO_LONG_WITH_LOWERCASE",
        "b08n5wrwnw",  # lowercase
        "B08N5W",       # too short
    ])
    def test_invalid_asins(self, validator, asin):
        assert validator.validate_product_id(asin) is False

    # -- name -------------------------------------------------------------

    @pytest.mark.parametrize("name", [
        "Wireless Bluetooth Headphones",
        "USB Cable",
        "A" * 500,
    ])
    def test_valid_names(self, validator, name):
        assert validator.validate_name(name) is True

    @pytest.mark.parametrize("name", [
        "",
        None,
        123,
        "AB",       # too short (< 3)
        "A" * 501,  # too long (> 500)
    ])
    def test_invalid_names(self, validator, name):
        assert validator.validate_name(name) is False

    # -- price ------------------------------------------------------------

    @pytest.mark.parametrize("price", [
        "$19.99",
        "$1,299.99",
        "N/A",
    ])
    def test_valid_prices(self, validator, price):
        assert validator.validate_price(price) is True

    @pytest.mark.parametrize("price", [
        "$1000000",
        "not a price at all",
        123,
    ])
    def test_invalid_prices(self, validator, price):
        assert validator.validate_price(price) is False

    # -- rating -----------------------------------------------------------

    @pytest.mark.parametrize("rating", [
        "4.5 out of 5 stars",
        "3.2",
        "5.0",
        "0",
        "N/A",
    ])
    def test_valid_ratings(self, validator, rating):
        assert validator.validate_rating(rating) is True

    @pytest.mark.parametrize("rating", [
        "6.0 out of 5 stars",  # > 5
        "not a rating",
        123,
    ])
    def test_invalid_ratings(self, validator, rating):
        assert validator.validate_rating(rating) is False

    # -- review_count -----------------------------------------------------

    @pytest.mark.parametrize("count", [
        "1,234",
        "42",
        "0",
        "N/A",
    ])
    def test_valid_review_counts(self, validator, count):
        assert validator.validate_review_count(count) is True

    @pytest.mark.parametrize("count", [
        "no reviews",
        123,
    ])
    def test_invalid_review_counts(self, validator, count):
        assert validator.validate_review_count(count) is False

    # -- brand ------------------------------------------------------------

    @pytest.mark.parametrize("brand", [
        "Sony",
        "Samsung Electronics",
        "N/A",
    ])
    def test_valid_brands(self, validator, brand):
        assert validator.validate_brand(brand) is True

    @pytest.mark.parametrize("brand", [
        123,
        "A" * 101,
    ])
    def test_invalid_brands(self, validator, brand):
        assert validator.validate_brand(brand) is False

    # -- category ---------------------------------------------------------

    @pytest.mark.parametrize("category", [
        "Electronics",
        "Home & Kitchen",
        "N/A",
    ])
    def test_valid_categories(self, validator, category):
        assert validator.validate_category(category) is True

    @pytest.mark.parametrize("category", [
        123,
        "A" * 201,
    ])
    def test_invalid_categories(self, validator, category):
        assert validator.validate_category(category) is False


# ---------------------------------------------------------------------------
# DataValidator — row and dataframe validation
# ---------------------------------------------------------------------------

class TestDataValidatorDataFrame:
    @pytest.fixture
    def validator(self):
        return DataValidator()

    @pytest.fixture
    def valid_row(self):
        return {
            "product_id": "B08N5WRWNW",
            "name": "Wireless Bluetooth Headphones",
            "price": "$99.99",
            "rating": "4.5 out of 5 stars",
            "review_count": "1,234",
            "brand": "Sony",
            "category": "Electronics",
        }

    def test_validate_row_all_valid(self, validator, valid_row):
        results = validator.validate_row(valid_row)
        assert all(results.values()) is True

    def test_validate_row_detects_invalid_asin(self, validator, valid_row):
        valid_row["product_id"] = "bad"
        results = validator.validate_row(valid_row)
        assert results["product_id"] is False

    def test_validate_dataframe_counts_correctly(self, validator, valid_row):
        df = pd.DataFrame([valid_row, valid_row, valid_row])
        results = validator.validate_dataframe(df)
        assert results["total_rows"] == 3
        assert results["valid_rows"] == 3
        assert results["data_quality_score"] == 100.0

    def test_validate_dataframe_handles_invalid_rows(self, validator, valid_row):
        invalid_row = dict(valid_row)
        invalid_row["product_id"] = "bad"
        df = pd.DataFrame([valid_row, invalid_row, valid_row])
        results = validator.validate_dataframe(df)
        assert results["total_rows"] == 3
        assert results["valid_rows"] == 2
        assert len(results["invalid_rows"]) == 1

    def test_validate_dataframe_quality_score_partial(self, validator, valid_row):
        invalid_row = dict(valid_row)
        invalid_row["product_id"] = "bad"
        invalid_row["name"] = "AB"
        df = pd.DataFrame([valid_row, invalid_row])
        results = validator.validate_dataframe(df)
        assert results["data_quality_score"] == 50.0

    def test_validate_dataframe_empty(self, validator):
        df = pd.DataFrame({
            "product_id": [], "name": [], "price": [],
            "rating": [], "review_count": [], "brand": [], "category": [],
        })
        results = validator.validate_dataframe(df)
        assert results["total_rows"] == 0
        assert results["data_quality_score"] == 0.0

    def test_field_validation_counts(self, validator, valid_row):
        df = pd.DataFrame([valid_row])
        results = validator.validate_dataframe(df)
        for field in ["product_id", "name", "price", "rating", "review_count", "brand", "category"]:
            assert results["field_validation"][field]["valid"] == 1
            assert results["field_validation"][field]["invalid"] == 0


# ---------------------------------------------------------------------------
# DataValidator — report generation
# ---------------------------------------------------------------------------

class TestValidationReport:
    @pytest.fixture
    def validator(self):
        return DataValidator()

    def test_report_contains_key_sections(self, validator):
        results = {
            "total_rows": 10,
            "valid_rows": 8,
            "invalid_rows": [
                {"index": 0, "data": {}, "errors": {"product_id": False}},
                {"index": 1, "data": {}, "errors": {"name": False}},
            ],
            "data_quality_score": 80.0,
            "field_validation": {
                "product_id": {"valid": 9, "invalid": 1},
                "name": {"valid": 8, "invalid": 2},
                "price": {"valid": 10, "invalid": 0},
                "rating": {"valid": 10, "invalid": 0},
                "review_count": {"valid": 10, "invalid": 0},
                "brand": {"valid": 10, "invalid": 0},
                "category": {"valid": 10, "invalid": 0},
            },
        }
        report = validator.get_validation_report(results)
        assert "总行数: 10" in report
        assert "有效行数: 8" in report
        assert "数据质量得分: 80.00%" in report
        assert "product_id" in report

    def test_report_with_no_invalid_rows(self, validator):
        results = {
            "total_rows": 5,
            "valid_rows": 5,
            "invalid_rows": [],
            "data_quality_score": 100.0,
            "field_validation": {
                "product_id": {"valid": 5, "invalid": 0},
                "name": {"valid": 5, "invalid": 0},
                "price": {"valid": 5, "invalid": 0},
                "rating": {"valid": 5, "invalid": 0},
                "review_count": {"valid": 5, "invalid": 0},
                "brand": {"valid": 5, "invalid": 0},
                "category": {"valid": 5, "invalid": 0},
            },
        }
        report = validator.get_validation_report(results)
        assert "无效行数: 0" in report


# ---------------------------------------------------------------------------
# DataQualityMonitor
# ---------------------------------------------------------------------------

class TestDataQualityMonitor:
    @pytest.fixture
    def sample_df(self):
        return pd.DataFrame({
            "product_id": ["B08N5WRWNW", "B07ZPC9Q4K", "B00TEST000"],
            "name": ["Product 1", "Product 2", "Product 3"],
            "price": ["$99.99", "$120.50", "$75.00"],
            "rating": ["4.5 out of 5 stars", "4.2 out of 5 stars", "3.8 out of 5 stars"],
            "review_count": ["1,234", "567", "2,345"],
            "brand": ["Sony", "Samsung", "Apple"],
            "category": ["Electronics", "Electronics", "Electronics"],
        })

    def test_monitor_passes_with_quality_data(self, sample_df):
        monitor = DataQualityMonitor(min_quality_score=90.0)
        assert monitor.monitor_data_quality(sample_df) is True

    def test_monitor_fails_with_low_quality(self, sample_df):
        # Corrupt all rows
        sample_df["product_id"] = ["bad", "also_bad", "invalid"]
        monitor = DataQualityMonitor(min_quality_score=50.0)
        assert monitor.monitor_data_quality(sample_df) is False

    def test_clean_data_removes_invalid_rows(self, sample_df):
        # Corrupt one row
        sample_df.loc[0, "product_id"] = "bad"
        monitor = DataQualityMonitor()
        cleaned = monitor.clean_data(sample_df)
        assert len(cleaned) == 2  # 1 row removed

    def test_clean_data_removes_duplicates(self, sample_df):
        # Add a duplicate
        df = pd.concat([sample_df, sample_df.iloc[[0]]], ignore_index=True)
        assert len(df) == 4
        monitor = DataQualityMonitor()
        cleaned = monitor.clean_data(df)
        assert len(cleaned) == 3  # duplicate removed

    def test_clean_data_requires_product_id_and_name(self, sample_df):
        sample_df.loc[0, "name"] = "AB"  # invalid name
        monitor = DataQualityMonitor()
        cleaned = monitor.clean_data(sample_df)
        assert len(cleaned) == 2

    def test_clean_data_price_is_optional(self, sample_df):
        sample_df["price"] = "N/A"  # N/A is valid per validator
        monitor = DataQualityMonitor()
        cleaned = monitor.clean_data(sample_df)
        assert len(cleaned) == 3


# ---------------------------------------------------------------------------
# validate_amazon_data_file (integration helper)
# ---------------------------------------------------------------------------

class TestValidateAmazonDataFile:
    def test_handles_missing_file(self):
        result = validate_amazon_data_file("/nonexistent/path.csv")
        assert result == {}
