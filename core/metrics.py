"""
Derived operational metrics — computed at query time, not stored in DB.

Formulas can be adjusted without schema migration. All functions are pure
(no side effects, no I/O) except compute_competition_score which takes a
sqlite3.Connection for the count query.
"""

import re
from datetime import date, datetime
from typing import Optional

# BSR → est_monthly_sales: Amazon seller heuristic formula
# est_monthly_sales ≈ CONSTANT / (bsr_rank + OFFSET)
# Higher BSR rank (worse) → proportionally lower estimated sales
BSR_SALES_CONSTANT = 480_000
BSR_OFFSET = 50

# Pattern: "#1,234 in Electronics" or "#42 in Home & Kitchen"
_BSR_RANK_PATTERN = re.compile(r"#([\d,]+)")


def parse_bsr_rank(bsr_text: Optional[str]) -> Optional[int]:
    """Extract the numeric BSR rank from text like '#1,234 in Electronics'.

    Returns the first rank found, or None if unparseable.
    """
    if not bsr_text:
        return None
    m = _BSR_RANK_PATTERN.search(str(bsr_text))
    if not m:
        return None
    try:
        return int(m.group(1).replace(",", ""))
    except (ValueError, TypeError):
        return None


def compute_est_monthly_sales(bsr_text: Optional[str]) -> Optional[int]:
    """Estimate monthly unit sales from BSR text.

    Uses the Amazon seller heuristic:
        est_monthly_sales = max(1, int(480000 / (bsr_rank + 50)))
    """
    rank = parse_bsr_rank(bsr_text)
    if rank is None:
        return None
    return max(1, int(BSR_SALES_CONSTANT / (rank + BSR_OFFSET)))


def parse_date_first_available(date_str: Optional[str]) -> Optional[date]:
    """Parse date_first_available into a date object.

    Supports multiple formats commonly seen on Amazon:
      - "June 15, 2023"
      - "2023-06-15"
      - "06/15/2023"
      - "Jan 5, 2024"
    """
    if not date_str:
        return None

    s = str(date_str).strip()

    # Try dateutil first (handles most formats automatically)
    try:
        from dateutil.parser import parse as dt_parse  # type: ignore[import-untyped]
        return dt_parse(s).date()
    except (ImportError, ValueError, TypeError):
        pass

    # Fallback: manual format list
    formats = [
        "%B %d, %Y",   # "June 15, 2023"
        "%b %d, %Y",   # "Jun 15, 2023"
        "%Y-%m-%d",    # "2023-06-15"
        "%m/%d/%Y",    # "06/15/2023"
        "%d/%m/%Y",    # "15/06/2023"
    ]
    for fmt in formats:
        try:
            return datetime.strptime(s, fmt).date()
        except (ValueError, TypeError):
            continue
    return None


def compute_review_velocity(
    review_count: Optional[int],
    date_first_available: Optional[str],
) -> Optional[float]:
    """Daily review growth rate = review_count / days_since_listed.

    Returns reviews/day as a float rounded to 2 decimal places,
    or None if inputs are insufficient.
    """
    if review_count is None or not date_first_available:
        return None

    d = parse_date_first_available(date_first_available)
    if d is None:
        return None

    days = max(1, (date.today() - d).days)
    return round(review_count / days, 2)


def compute_competition_score(db, keyword: str) -> int:
    """Count products in the same keyword as a competition proxy."""
    import sqlite3
    try:
        row = db.execute(
            "SELECT COUNT(*) FROM products WHERE keyword = ?", (keyword,)
        ).fetchone()
        return row[0] if row else 0
    except sqlite3.Error:
        return 0


def price_bucket_label(price: Optional[float]) -> Optional[str]:
    """Map a price to its distribution bucket label."""
    if price is None:
        return None
    if price <= 10:
        return "$0-10"
    if price <= 25:
        return "$10-25"
    if price <= 50:
        return "$25-50"
    if price <= 100:
        return "$50-100"
    if price <= 200:
        return "$100-200"
    return "$200+"
