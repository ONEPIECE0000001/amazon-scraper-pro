"""
Unit tests for core.metrics — BSR parsing, sales estimation, review velocity.
"""

import sys
from datetime import date, datetime
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, "..")

from core.metrics import (
    parse_bsr_rank,
    compute_est_monthly_sales,
    parse_date_first_available,
    compute_review_velocity,
    price_bucket_label,
    compute_competition_score,
)


# ── parse_bsr_rank ───────────────────────────────────────────────────────

class TestParseBsrRank:
    def test_simple_rank(self):
        assert parse_bsr_rank("#1,234 in Electronics") == 1234

    def test_without_comma(self):
        assert parse_bsr_rank("#1 in Electronics") == 1

    def test_top_rank(self):
        assert parse_bsr_rank("#42 in Home & Kitchen") == 42

    def test_multiple_bsr_returns_first(self):
        # If multiple BSRs appear, pick the first
        assert parse_bsr_rank("#1 in Electronics, #250 in Headphones") == 1

    def test_none_input(self):
        assert parse_bsr_rank(None) is None

    def test_empty_string(self):
        assert parse_bsr_rank("") is None

    def test_unparseable(self):
        assert parse_bsr_rank("N/A") is None

    def test_large_number(self):
        assert parse_bsr_rank("#99,999 in Toys") == 99999

    def test_no_hash(self):
        assert parse_bsr_rank("1 in Electronics") is None


# ── compute_est_monthly_sales ────────────────────────────────────────────

class TestComputeEstMonthlySales:
    def test_typical_rank(self):
        # rank=100 → 480000/(100+50) = 3200
        assert compute_est_monthly_sales("#100 in Electronics") == 3200

    def test_top_rank(self):
        # rank=1 → 480000/(1+50) = 9411
        assert compute_est_monthly_sales("#1 in Electronics") == 9411

    def test_poor_rank(self):
        # rank=10000 → 480000/(10000+50) = 47
        assert compute_est_monthly_sales("#10,000 in Kitchen") == 47

    def test_minimum_sales_is_1(self):
        # Very high rank → formula bottoms out at 1
        result = compute_est_monthly_sales("#999,999 in Books")
        assert result == 1

    def test_none_input(self):
        assert compute_est_monthly_sales(None) is None

    def test_unparseable_input(self):
        assert compute_est_monthly_sales("N/A") is None


# ── parse_date_first_available ───────────────────────────────────────────

class TestParseDateFirstAvailable:
    def test_full_month_name(self):
        result = parse_date_first_available("June 15, 2023")
        assert result == date(2023, 6, 15)

    def test_abbreviated_month(self):
        result = parse_date_first_available("Jan 5, 2024")
        assert result == date(2024, 1, 5)

    def test_iso_format(self):
        result = parse_date_first_available("2023-06-15")
        assert result == date(2023, 6, 15)

    def test_slash_format(self):
        result = parse_date_first_available("06/15/2023")
        assert result == date(2023, 6, 15)

    def test_none_input(self):
        assert parse_date_first_available(None) is None

    def test_empty_string(self):
        assert parse_date_first_available("") is None

    def test_whitespace_string(self):
        assert parse_date_first_available("   ") is None


# ── compute_review_velocity ──────────────────────────────────────────────

class TestComputeReviewVelocity:
    def test_recent_product(self):
        # Product listed today → velocity = review_count / 1
        today = date.today().strftime("%Y-%m-%d")
        result = compute_review_velocity(10, today)
        assert result == 10.0

    def test_typical_velocity(self):
        # 500 reviews, listed 100 days ago
        from datetime import timedelta
        d100 = (date.today() - timedelta(days=100)).strftime("%Y-%m-%d")
        result = compute_review_velocity(500, d100)
        assert result == 5.0

    def test_no_review_count(self):
        assert compute_review_velocity(None, "June 15, 2023") is None

    def test_no_date(self):
        assert compute_review_velocity(100, None) is None

    def test_unparseable_date(self):
        assert compute_review_velocity(100, "not a date") is None

    def test_rounding(self):
        # 100 reviews in 3 days → 33.33
        from datetime import timedelta
        d3 = (date.today() - timedelta(days=3)).strftime("%Y-%m-%d")
        result = compute_review_velocity(100, d3)
        assert result == 33.33


# ── price_bucket_label ───────────────────────────────────────────────────

class TestPriceBucketLabel:
    def test_low(self):
        assert price_bucket_label(5.0) == "$0-10"

    def test_boundary_10(self):
        assert price_bucket_label(10.0) == "$0-10"

    def test_mid_low(self):
        assert price_bucket_label(15.0) == "$10-25"

    def test_boundary_25(self):
        assert price_bucket_label(25.0) == "$10-25"

    def test_mid(self):
        assert price_bucket_label(35.0) == "$25-50"

    def test_boundary_50(self):
        assert price_bucket_label(50.0) == "$25-50"

    def test_high(self):
        assert price_bucket_label(75.0) == "$50-100"

    def test_boundary_100(self):
        assert price_bucket_label(100.0) == "$50-100"

    def test_premium(self):
        assert price_bucket_label(150.0) == "$100-200"

    def test_ultra_premium(self):
        assert price_bucket_label(300.0) == "$200+"

    def test_none(self):
        assert price_bucket_label(None) is None


# ── compute_competition_score ────────────────────────────────────────────

class TestComputeCompetitionScore:
    def test_with_results(self):
        db = MagicMock()
        db.execute.return_value.fetchone.return_value = [42]
        result = compute_competition_score(db, "wireless earbuds")
        assert result == 42
        db.execute.assert_called_once()

    def test_empty_keyword(self):
        db = MagicMock()
        db.execute.return_value.fetchone.return_value = [0]
        result = compute_competition_score(db, "unknown_keyword")
        assert result == 0

    def test_db_error_returns_zero(self):
        import sqlite3
        db = MagicMock()
        db.execute.side_effect = sqlite3.Error("table missing")
        result = compute_competition_score(db, "test")
        assert result == 0
