"""Amazon Spider Web UI — browse scraped product data from SQLite."""

import os
import re
import sys
import json
import uuid
import sqlite3
import threading
import subprocess
from datetime import datetime
from urllib.parse import urlencode
from flask import Flask, render_template_string, request, g, jsonify

from core.metrics import (
    compute_est_monthly_sales,
    compute_review_velocity,
    compute_competition_score,
)

DATABASE = os.environ.get('SQLITE_PATH', 'amazon_data.db')
PER_PAGE = 30

app = Flask(__name__)

# ── Template ───────────────────────────────────────────────────────────────

TEMPLATE = r'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Amazon Spider — 商品数据</title>
<style>
  :root {
    --bg: #f0f2f5; --card: #fff; --text: #1a1a2e; --muted: #6b7280;
    --accent: #2563eb; --accent-hover: #1d4ed8;
    --green: #059669; --yellow: #d97706; --red: #dc2626;
    --border: #e5e7eb; --shadow: 0 1px 3px rgba(0,0,0,.06);
    --radius: 10px;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
         background: var(--bg); color: var(--text); min-height: 100vh; }

  /* ── top navbar ── */
  .navbar { background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
            color: #fff; padding: 0 24px; position: sticky; top: 0; z-index: 100; }
  .navbar-inner { max-width: 1400px; margin: 0 auto; display: flex;
                  align-items: center; height: 52px; gap: 24px; }
  .navbar .logo { font-size: 1.05rem; font-weight: 700; white-space: nowrap;
                  display: flex; align-items: center; gap: 8px; }
  .navbar .logo .icon { font-size: 1.3rem; }
  .navbar nav { display: flex; gap: 4px; flex: 1; }
  .navbar nav a { color: #94a3b8; text-decoration: none; padding: 6px 14px;
                  border-radius: 6px; font-size: .82rem; font-weight: 500;
                  display: flex; align-items: center; gap: 6px;
                  transition: background .15s, color .15s; }
  .navbar nav a:hover { background: rgba(255,255,255,.08); color: #e2e8f0; }
  .navbar nav a.active { background: rgba(255,255,255,.12); color: #fff; }
  .navbar .db-badge { font-size: .72rem; color: #94a3b8; display: flex;
    align-items: center; gap: 6px; white-space: nowrap; }
  .navbar .db-badge .dot { width: 7px; height: 7px; border-radius: 50%;
    background: #22c55e; box-shadow: 0 0 6px rgba(34,197,94,.5); flex-shrink: 0; }
  .navbar .db-badge .db-path { max-width: 140px; overflow: hidden;
    text-overflow: ellipsis; }

  /* ── breadcrumb ── */
  .breadcrumb { max-width: 1400px; margin: 0 auto; padding: 12px 24px 0;
                font-size: .78rem; color: var(--muted); }
  .breadcrumb a { color: var(--accent); text-decoration: none; }
  .breadcrumb a:hover { text-decoration: underline; }
  .breadcrumb span { color: var(--muted); }

  /* ── page title ── */
  .page-title-row { max-width: 1400px; margin: 0 auto; padding: 14px 24px 0;
                    display: flex; align-items: baseline; justify-content: space-between; }
  .page-title-row h2 { font-size: 1.15rem; font-weight: 600; }
  .page-title-row .meta { font-size: .78rem; color: var(--muted); }

  /* ── stats bar ── */
  .statbar { max-width: 1400px; margin: 12px auto 16px; padding: 0 24px;
             display: flex; gap: 12px; flex-wrap: wrap; }
  .statcard { background: var(--card); padding: 12px 18px; border-radius: var(--radius);
              box-shadow: var(--shadow); flex: 1; min-width: 130px;
              display: flex; align-items: center; gap: 10px; }
  .statcard .icon { font-size: 1.4rem; width: 36px; height: 36px; border-radius: 8px;
                    display: flex; align-items: center; justify-content: center;
                    flex-shrink: 0; }
  .statcard .icon.blue   { background: #dbeafe; }
  .statcard .icon.green  { background: #d1fae5; }
  .statcard .icon.yellow { background: #fef3c7; }
  .statcard .icon.purple { background: #ede9fe; }
  .statcard .icon.red    { background: #fee2e2; }
  .statcard .val { font-size: 1.35rem; font-weight: 700; line-height: 1.2; }
  .statcard .lbl { font-size: .7rem; color: var(--muted); }
  .val.blue   { color: var(--accent); }
  .val.green  { color: var(--green); }
  .val.yellow { color: var(--yellow); }
  .val.red    { color: var(--red); }
  .val.purple { color: #7c3aed; }

  /* ── main content ── */
  .main { max-width: 1400px; margin: 0 auto; padding: 0 24px 40px; }

  /* ── filters ── */
  .filter-bar { background: var(--card); padding: 14px 18px; border-radius: var(--radius);
                box-shadow: var(--shadow); margin-bottom: 14px;
                display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
  .filter-bar .search-wrap { flex: 1; min-width: 200px; position: relative; }
  .filter-bar .search-wrap .search-icon { position: absolute; left: 10px; top: 50%;
    transform: translateY(-50%); color: var(--muted); font-size: .85rem; pointer-events: none; }
  .filter-bar .search-wrap input { width: 100%; padding: 8px 14px 8px 32px;
    border: 1px solid var(--border); border-radius: 6px; font-size: .83rem; outline: none; }
  .filter-bar input, .filter-bar button {
    padding: 8px 14px; border: 1px solid var(--border); border-radius: 6px;
    font-size: .83rem; outline: none; }
  .filter-bar input:focus, .filter-bar .search-wrap input:focus { border-color: var(--accent); }
  .filter-bar button { background: var(--accent); color: #fff; border: none;
                       cursor: pointer; font-weight: 500; white-space: nowrap; }
  .filter-bar button:hover { background: var(--accent-hover); }
  .filter-bar button.ghost { background: transparent; color: var(--muted);
                              border: 1px solid var(--border); }
  .filter-bar button.ghost:hover { background: #f1f5f9; color: var(--text); }
  .filter-bar input[type=number] { width: 95px; }

  /* ── keyword tags ── */
  .kw-bar { display: flex; gap: 6px; flex-wrap: wrap; align-items: center;
            width: 100%; margin-top: 2px; }
  .kw-bar .kw-label { font-size: .73rem; color: var(--muted); flex-shrink: 0; }
  .kw-bar a { text-decoration: none; font-size: .75rem; padding: 4px 12px;
              border-radius: 20px; font-weight: 500; transition: all .15s;
              background: #f1f5f9; color: #475569; }
  .kw-bar a:hover { background: #dbeafe; color: var(--accent); }
  .kw-bar a.active { background: var(--accent); color: #fff; }
  .kw-bar a.active::before { content: '\\25CF '; font-size: .5rem; vertical-align: middle; }

  /* ── product cards ── */
  .product-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(420px, 1fr));
                  gap: 14px; }
  .card { background: var(--card); border-radius: var(--radius); box-shadow: var(--shadow);
          padding: 18px; display: flex; gap: 16px; transition: box-shadow .15s; }
  .card:hover { box-shadow: 0 4px 12px rgba(0,0,0,.1); }
  .card .img-wrap { flex-shrink: 0; width: 100px; height: 100px; display: flex;
                    align-items: center; justify-content: center;
                    background: #f8f9fb; border-radius: 8px; overflow: hidden; }
  .card .img-wrap img { max-width: 100%; max-height: 100%; object-fit: contain; }
  .card .info { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 6px; }
  .card .title { font-weight: 600; font-size: .88rem; line-height: 1.4;
                 display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
                 overflow: hidden; }
  .card .title a { color: var(--text); text-decoration: none; }
  .card .title a:hover { color: var(--accent); }
  .card .meta { display: flex; gap: 14px; flex-wrap: wrap; font-size: .78rem;
                color: var(--muted); }
  .card .meta span { white-space: nowrap; }
  .card .price { font-size: 1.2rem; font-weight: 700; color: var(--red); }
  .card .stars { color: #f59e0b; font-weight: 600; }
  .card .prime { color: var(--green); font-weight: 600; font-size: .75rem; }
  .card .tags { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 2px; }
  .card .tag { font-size: .68rem; padding: 2px 8px; border-radius: 4px;
               background: #f1f5f9; color: #475569; white-space: nowrap; }
  .card .tag.brand { background: #fef3c7; color: #92400e; }
  .card .tag.keyword { background: #dbeafe; color: #1e40af; }

  /* ── pagination ── */
  .pager { display: flex; gap: 6px; margin-top: 20px; justify-content: center;
           flex-wrap: wrap; }
  .pager a, .pager span { padding: 7px 13px; border-radius: 6px; font-size: .8rem;
    text-decoration: none; border: 1px solid var(--border); color: var(--text);
    background: var(--card); }
  .pager a:hover { border-color: var(--accent); }
  .pager a.cur { background: var(--accent); color: #fff; border-color: var(--accent); }
  .pager span { color: var(--muted); }

  /* ── empty ── */
  .empty { text-align: center; padding: 60px 20px; color: var(--muted); }
  .empty .icon { font-size: 3rem; margin-bottom: 12px; }

  /* ── responsive ── */
  @media (max-width: 640px) {
    .navbar nav a { padding: 6px 10px; font-size: .76rem; }
    .navbar .db-badge .db-path { display: none; }
    .statcard { min-width: 100px; padding: 10px 14px; }
    .statcard .val { font-size: 1.1rem; }
    .product-grid { grid-template-columns: 1fr; }
  }
</style>
</head>
<body>

<!-- top navbar -->
<nav class="navbar">
  <div class="navbar-inner">
    <a href="/" class="logo" style="color:#fff;text-decoration:none;">
      <span class="icon">🕷</span> Amazon Spider
    </a>
    <nav>
      <a href="/" class="active">📦 商品浏览</a>
      <a href="/dashboard">📊 驾驶舱</a>
    </nav>
    <div class="db-badge" title="数据库: {{ dbfile }}">
      <span class="dot"></span>
      <span class="db-path">{{ dbfile }}</span>
      <span style="color:#94a3b8;">· {{ total }} 条</span>
    </div>
  </div>
</nav>

<!-- breadcrumb -->
<div class="breadcrumb">
  <a href="/">首页</a> <span>›</span> 商品浏览
  {% if cur_kw %}<span> › {{ cur_kw }}</span>{% endif %}
</div>

<!-- compact stats -->
<div style="max-width:1400px;margin:0 auto;padding:8px 24px 0;font-size:.75rem;color:var(--muted);">
  共 <strong style="color:var(--text);">{{ total }}</strong> 个商品
  · <strong style="color:var(--text);">{{ kw_count }}</strong> 个关键词
  · <strong style="color:var(--text);">{{ brand_count }}</strong> 个品牌
</div>

<div class="main">

  <!-- filter bar -->
  <form class="filter-bar" method="get" autocomplete="off">
    <div class="search-wrap">
      <select name="search_type" style="position:absolute;left:0;top:0;bottom:0;width:80px;
        border:none;border-right:1px solid var(--border);border-radius:6px 0 0 6px;
        background:#f8fafc;font-size:.75rem;padding:0 4px;outline:none;z-index:1;
        color:var(--muted);">
        <option value="all" {% if search_type == 'all' %}selected{% endif %}>全部</option>
        <option value="title" {% if search_type == 'title' %}selected{% endif %}>标题</option>
        <option value="asin" {% if search_type == 'asin' %}selected{% endif %}>ASIN</option>
        <option value="brand" {% if search_type == 'brand' %}selected{% endif %}>品牌</option>
      </select>
      <span class="search-icon" style="left:88px;">🔍</span>
      <input name="q" value="{{ query }}" placeholder="输入搜索内容…" autocomplete="off"
       style="padding-left:108px;">
    </div>
    <select name="brand" onchange="this.form.submit()" style="padding:7px 10px;border:1px solid var(--border);border-radius:6px;font-size:.82rem;background:var(--card);">
      <option value="">全部品牌</option>
      {% for b in brand_list %}
      <option value="{{ b }}" {% if brand == b %}selected{% endif %}>{{ b[:30] }}</option>
      {% endfor %}
    </select>
    <select name="fulfillment" onchange="this.form.submit()" style="padding:7px 10px;border:1px solid var(--border);border-radius:6px;font-size:.82rem;background:var(--card);">
      <option value="">全部配送</option>
      <option value="FBA" {% if fulfillment == 'FBA' %}selected{% endif %}>FBA</option>
      <option value="FBM" {% if fulfillment == 'FBM' %}selected{% endif %}>FBM</option>
    </select>
    <input type="number" name="min_price" value="{{ min_price }}" placeholder="最低价" style="width:80px;">
    <input type="number" name="max_price" value="{{ max_price }}" placeholder="最高价" style="width:80px;">
    <input type="number" name="min_rating" value="{{ min_rating }}" placeholder="评分≥" step="0.5" style="width:70px;">
    <label style="font-size:.78rem;display:flex;align-items:center;gap:4px;white-space:nowrap;cursor:pointer;">
      <input type="checkbox" name="prime" value="1" {% if prime_only == '1' %}checked{% endif %} onchange="this.form.submit()"> Prime
    </label>
    <select name="sort" onchange="this.form.submit()" style="padding:7px 10px;border:1px solid var(--border);border-radius:6px;font-size:.82rem;background:var(--card);">
      <option value="latest" {% if sort == 'latest' %}selected{% endif %}>最新 ↓</option>
      <option value="price_asc" {% if sort == 'price_asc' %}selected{% endif %}>价格 ↑</option>
      <option value="price_desc" {% if sort == 'price_desc' %}selected{% endif %}>价格 ↓</option>
      <option value="rating" {% if sort == 'rating' %}selected{% endif %}>评分 ↓</option>
      <option value="reviews" {% if sort == 'reviews' %}selected{% endif %}>评论 ↓</option>
    </select>
    <select name="per_page" onchange="this.form.submit()" style="padding:7px 10px;border:1px solid var(--border);border-radius:6px;font-size:.82rem;background:var(--card);">
      <option value="30" {% if per_page == 30 %}selected{% endif %}>30条</option>
      <option value="60" {% if per_page == 60 %}selected{% endif %}>60条</option>
      <option value="90" {% if per_page == 90 %}selected{% endif %}>90条</option>
    </select>
    <button type="submit">筛选</button>
    {% if query or min_price or max_price or min_rating or cur_kw or brand or fulfillment or prime_only or search_type != 'all' %}
    <a href="/"><button type="button" class="ghost">清除</button></a>
    {% endif %}

    <input type="hidden" name="kw" value="{{ cur_kw }}" id="kw-hidden">
    {% if keywords %}
    <div class="kw-bar">
      <span class="kw-label">关键词:</span>
      {% for kw in keywords %}
      <a href="#" onclick="document.getElementById('kw-hidden').value='{{ kw }}';this.closest('form').submit();return false;"
         class="{% if cur_kw == kw %}active{% endif %}">{{ kw }}</a>
      {% endfor %}
      {% if cur_kw %}
      <a href="#" onclick="document.getElementById('kw-hidden').value='';this.closest('form').submit();return false;"
         style="background:#fee2e2;color:#991b1b;">✕ 清除</a>
      {% endif %}
    </div>
    {% endif %}
  </form>

  <!-- product cards -->
  {% if rows %}
  <div class="product-grid">
  {% for r in rows %}
  <div class="card">
    <div class="img-wrap">
      {% if r.image %}
      <img src="{{ r.image }}" loading="lazy" alt="">
      {% else %}
      <span style="color:var(--border);font-size:2rem;">📷</span>
      {% endif %}
    </div>
    <div class="info">
      <div class="title">
        <a href="{{ r.url or '#' }}" target="_blank" title="{{ r.title }}">{{ r.title }}</a>
      </div>
      <div class="meta">
        {% if r.price is not none %}
        <span class="price">${{ '{:,.2f}'.format(r.price) }}</span>
        {% endif %}
        {% if r.rating is not none %}
        <span class="stars">★ {{ '{:.1f}'.format(r.rating) }}</span>
        {% endif %}
        {% if r.review_count is not none %}
        <span>{{ r.review_count }} 评论</span>
        {% endif %}
        {% if r.is_prime == 'Yes' %}
        <span class="prime">✓ Prime</span>
        {% endif %}
      </div>
      <div class="tags">
        <a href="/product/{{ r.asin }}" class="tag" style="background:#eff6ff;color:#1e40af;text-decoration:none;cursor:pointer;" title="查看单品分析">🆔 {{ r.asin }}</a>
        {% if r.keyword %}
        <span class="tag keyword">{{ r.keyword }}</span>
        {% endif %}
        {% if r.brand %}
        <span class="tag brand">{{ r.brand }}</span>
        {% endif %}
        {% if r.fulfillment_type %}
        <span class="tag" style="background:#d1fae5;color:#065f46;">{{ r.fulfillment_type }}</span>
        {% endif %}
        {% if r.sold_by %}
        <span class="tag">{{ r.sold_by[:30] }}</span>
        {% endif %}
        {% if r.category %}
        <span class="tag">{{ r.category[:40] }}</span>
        {% endif %}
      </div>
      <div class="tags" style="margin-top:2px;">
        {% if r.bsr %}
        <span class="tag" style="background:#fef2f2;color:#991b1b;" title="Best Sellers Rank">📊 {{ r.bsr[:60] }}</span>
        {% endif %}
        {% if r.coupon_text %}
        <span class="tag" style="background:#fef7ed;color:#b45309;">🏷 {{ r.coupon_text[:40] }}</span>
        {% endif %}
        {% if r.answered_questions is not none %}
        <span class="tag">❓ {{ r.answered_questions }} Q&A</span>
        {% endif %}
        {% if r.variation_count is not none %}
        <span class="tag">📐 {{ r.variation_count }} 变体</span>
        {% endif %}
        {% if r.availability %}
        <span class="tag">{{ r.availability[:30] }}</span>
        {% endif %}
      </div>
    </div>
  </div>
  {% endfor %}
  </div>
  {% else %}
  <div class="empty">
    <div class="icon">🔍</div>
    <p>没有匹配的商品，换个关键词试试</p>
  </div>
  {% endif %}

  <!-- pagination -->
  {% if total_pages > 1 %}
  <div class="pager">
    {% if page > 1 %}
    <a href="?{{ page_qs(page-1) }}">‹ 上一页</a>
    {% endif %}
    {% for p in page_range %}
      {% if p == page %}
      <a class="cur">{{ p }}</a>
      {% elif p == '…' %}
      <span>…</span>
      {% else %}
      <a href="?{{ page_qs(p) }}">{{ p }}</a>
      {% endif %}
    {% endfor %}
    {% if page < total_pages %}
    <a href="?{{ page_qs(page+1) }}">下一页 ›</a>
    {% endif %}
  </div>
  {% endif %}

</div>
</body>
</html>'''


# ── Database ────────────────────────────────────────────────────────────────

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        _ensure_schema(g.db)
    return g.db


def _ensure_schema(db):
    """Auto-migrate: add missing columns to existing tables (mirrors SQLitePipeline)."""
    try:
        # price_history: add review_count if missing
        ph_cols = {r[1] for r in db.execute("PRAGMA table_info(price_history)")}
        if ph_cols and 'review_count' not in ph_cols:
            db.execute("ALTER TABLE price_history ADD COLUMN review_count INTEGER")
            db.commit()
    except sqlite3.OperationalError:
        pass


@app.teardown_appcontext
def close_db(error):
    db = g.pop('db', None)
    if db:
        db.close()


# ── Routes ──────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    db = get_db()

    # ── Filters ──────────────────────────────────────────────────────────
    q = request.args.get('q', '').strip()
    search_type = request.args.get('search_type', 'all').strip()
    min_price = request.args.get('min_price', '').strip()
    max_price = request.args.get('max_price', '').strip()
    min_rating = request.args.get('min_rating', '').strip()
    cur_kw = request.args.get('kw', '').strip()
    brand = request.args.get('brand', '').strip()
    fulfillment = request.args.get('fulfillment', '').strip()
    prime_only = request.args.get('prime', '').strip()
    sort = request.args.get('sort', 'latest').strip()
    per_page = int(request.args.get('per_page', PER_PAGE))
    page = int(request.args.get('p', 1))

    where = []
    params = []

    if cur_kw:
        where.append("keyword = ?")
        params.append(cur_kw)

    if q:
        like = f"%{q}%"
        if search_type == 'title':
            where.append("title LIKE ?")
            params.append(like)
        elif search_type == 'asin':
            where.append("asin LIKE ?")
            params.append(like)
        elif search_type == 'brand':
            where.append("brand LIKE ?")
            params.append(like)
        else:
            where.append("(title LIKE ? OR asin LIKE ? OR brand LIKE ? OR category LIKE ?)")
            params.extend([like, like, like, like])

    if brand:
        where.append("brand = ?")
        params.append(brand)

    if min_price:
        where.append("price >= ?")
        params.append(float(min_price))
    if max_price:
        where.append("price <= ?")
        params.append(float(max_price))
    if min_rating:
        where.append("rating >= ?")
        params.append(float(min_rating))

    if fulfillment == 'FBA':
        where.append("fulfillment_type LIKE 'FBA%'")
    elif fulfillment == 'FBM':
        where.append("fulfillment_type LIKE 'FBM%'")

    if prime_only == '1':
        where.append("is_prime = 'Yes'")

    where_clause = ("WHERE " + " AND ".join(where)) if where else ""

    # ── Sort ─────────────────────────────────────────────────────────────
    sort_map = {
        'latest': 'scraped_at DESC',
        'price_asc': 'price ASC',
        'price_desc': 'price DESC',
        'rating': 'rating DESC',
        'reviews': 'review_count DESC',
    }
    order_by = sort_map.get(sort, 'scraped_at DESC')

    # ── Count ────────────────────────────────────────────────────────────
    count = db.execute(
        f"SELECT COUNT(*) FROM products {where_clause}", params
    ).fetchone()[0]

    # ── Global counts ────────────────────────────────────────────────────
    kw_count = db.execute(
        "SELECT COUNT(DISTINCT keyword) FROM products WHERE keyword != ''"
    ).fetchone()[0]
    brand_count = db.execute(
        "SELECT COUNT(DISTINCT brand) FROM products WHERE brand IS NOT NULL AND brand != ''"
    ).fetchone()[0]

    # ── Brand list for dropdown ──────────────────────────────────────────
    brands = db.execute(
        "SELECT DISTINCT brand FROM products WHERE brand IS NOT NULL AND brand != '' ORDER BY brand"
    ).fetchall()
    brand_list = [r['brand'] for r in brands]

    # ── Keyword list ─────────────────────────────────────────────────────
    kws = db.execute(
        "SELECT DISTINCT keyword FROM products WHERE keyword != '' ORDER BY keyword"
    ).fetchall()
    keywords = [row['keyword'] for row in kws]

    total_pages = max(1, (count + per_page - 1) // per_page)
    offset = (page - 1) * per_page

    rows = db.execute(
        f"""SELECT keyword, asin, title, price, rating, review_count,
                   brand, category, is_prime, availability,
                   date_first_available, scraped_at, image_url,
                   bsr, coupon_text, answered_questions, variation_count,
                   fulfillment_type, sold_by
            FROM products {where_clause}
            ORDER BY {order_by}
            LIMIT ? OFFSET ?""",
        params + [per_page, offset]
    ).fetchall()

    product_rows = []
    for row in rows:
        product_rows.append(type('R', (), {
            'keyword': row['keyword'],
            'asin': row['asin'],
            'title': row['title'],
            'price': row['price'],
            'rating': row['rating'],
            'review_count': row['review_count'],
            'brand': row['brand'],
            'category': row['category'],
            'is_prime': row['is_prime'],
            'availability': row['availability'],
            'url': f"https://www.amazon.com/dp/{row['asin']}",
            'image': row['image_url'],
            'bsr': row['bsr'],
            'coupon_text': row['coupon_text'],
            'answered_questions': row['answered_questions'],
            'variation_count': row['variation_count'],
            'fulfillment_type': row['fulfillment_type'],
            'sold_by': row['sold_by'],
        }))

    page_range = _build_page_range(page, total_pages)

    return render_template_string(
        TEMPLATE,
        rows=product_rows,
        total=count,
        kw_count=kw_count,
        brand_count=brand_count,
        brand_list=brand_list,
        keywords=keywords,
        cur_kw=cur_kw,
        query=q, search_type=search_type,
        brand=brand, fulfillment=fulfillment, prime_only=prime_only,
        min_price=min_price, max_price=max_price, min_rating=min_rating,
        sort=sort, per_page=per_page,
        page=page, total_pages=total_pages,
        page_range=page_range,
        page_qs=_page_qs,
        dbfile=DATABASE,
    )


# ── Helpers ─────────────────────────────────────────────────────────────────

def _page_qs(p):
    args = {}
    for key in ('q', 'search_type', 'brand', 'fulfillment', 'prime', 'min_price', 'max_price',
                'min_rating', 'kw', 'sort', 'per_page'):
        val = request.args.get(key, '')
        if val:
            args[key] = val
    args['p'] = p
    return urlencode(args)


def _build_page_range(page, total):
    """Build a compact page range like [1, …, 3, 4, 5, …, 10]."""
    if total <= 7:
        return list(range(1, total + 1))
    pages = [1]
    if page > 3:
        pages.append('…')
    for p in range(max(2, page - 1), min(total, page + 2)):
        pages.append(p)
    if page < total - 2:
        pages.append('…')
    pages.append(total)
    return pages


# ── Dashboard ────────────────────────────────────────────────────────────────

DASHBOARD_TEMPLATE = r'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>运营驾驶舱 — Amazon Spider</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"></script>
<style>
  :root {
    --bg: #f0f2f5; --card: #fff; --text: #1a1a2e; --muted: #6b7280;
    --accent: #2563eb; --green: #059669; --yellow: #d97706; --red: #dc2626;
    --border: #e5e7eb; --shadow: 0 1px 3px rgba(0,0,0,.06);
    --radius: 10px;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
         background: var(--bg); color: var(--text); min-height: 100vh; }

  /* ── shared navbar (same as 商品浏览) ── */
  .navbar { background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
            color: #fff; padding: 0 24px; position: sticky; top: 0; z-index: 100; }
  .navbar-inner { max-width: 1400px; margin: 0 auto; display: flex;
                  align-items: center; height: 52px; gap: 24px; }
  .navbar .logo { font-size: 1.05rem; font-weight: 700; white-space: nowrap;
                  display: flex; align-items: center; gap: 8px; }
  .navbar .logo .icon { font-size: 1.3rem; }
  .navbar nav { display: flex; gap: 4px; flex: 1; }
  .navbar nav a { color: #94a3b8; text-decoration: none; padding: 6px 14px;
                  border-radius: 6px; font-size: .82rem; font-weight: 500;
                  display: flex; align-items: center; gap: 6px;
                  transition: background .15s, color .15s; }
  .navbar nav a:hover { background: rgba(255,255,255,.08); color: #e2e8f0; }
  .navbar nav a.active { background: rgba(255,255,255,.12); color: #fff; }
  .navbar .db-badge { font-size: .72rem; color: #94a3b8; display: flex;
    align-items: center; gap: 6px; white-space: nowrap; }
  .navbar .db-badge .dot { width: 7px; height: 7px; border-radius: 50%;
    background: #22c55e; box-shadow: 0 0 6px rgba(34,197,94,.5); flex-shrink: 0; }
  .breadcrumb { max-width: 1400px; margin: 0 auto; padding: 12px 24px 0;
                font-size: .78rem; color: var(--muted); }
  .breadcrumb a { color: var(--accent); text-decoration: none; }
  .breadcrumb a:hover { text-decoration: underline; }
  .breadcrumb span { color: var(--muted); }

  .main { max-width: 1400px; margin: 0 auto; padding: 20px 24px 40px; }

  /* tabs */
  .tabs { display: flex; gap: 4px; margin-bottom: 20px; }
  .tabs a { padding: 8px 20px; border-radius: 6px 6px 0 0; font-size: .85rem;
            text-decoration: none; color: var(--muted); background: #e2e8f0; }
  .tabs a.active { background: var(--card); color: var(--text); font-weight: 600; }

  /* panels */
  .panel { background: var(--card); border-radius: var(--radius); box-shadow: var(--shadow);
           padding: 20px; margin-bottom: 16px; }
  .panel h2 { font-size: 1rem; margin-bottom: 12px; color: var(--text); }
  .panel .sub { font-size: .75rem; color: var(--muted); margin-bottom: 12px; }

  /* grid */
  .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
  .grid-3 { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
  @media (max-width: 900px) { .grid-2, .grid-3 { grid-template-columns: 1fr; } }

  /* stat cards */
  .kpi { text-align: center; }
  .kpi .num { font-size: 1.8rem; font-weight: 700; }
  .kpi .lbl { font-size: .75rem; color: var(--muted); margin-top: 4px; }
  .kpi .num.blue { color: var(--accent); }
  .kpi .num.green { color: var(--green); }
  .kpi .num.yellow { color: var(--yellow); }
  .kpi .num.red { color: var(--red); }

  /* table */
  table { width: 100%; border-collapse: collapse; font-size: .82rem; }
  th, td { padding: 8px 12px; text-align: left; border-bottom: 1px solid var(--border); }
  th { color: var(--muted); font-weight: 600; background: #f8fafc; }
  tr:hover { background: #f8fafc; }

  /* opportunity cards */
  .opp-card { border: 1px solid var(--border); border-radius: 8px; padding: 14px;
              transition: box-shadow .15s; }
  .opp-card:hover { box-shadow: 0 2px 8px rgba(0,0,0,.08); }
  .opp-card .t { font-weight: 600; font-size: .85rem; margin-bottom: 6px;
                 white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .opp-card .tags { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 6px; }
  .opp-card .tag { font-size: .7rem; padding: 2px 8px; border-radius: 4px; }
  .tag.gold { background: #fef3c7; color: #92400e; }
  .tag.blue { background: #dbeafe; color: #1e40af; }
  .tag.green { background: #d1fae5; color: #065f46; }

  /* selector */
  .sel-row { display: flex; gap: 10px; align-items: center; flex-wrap: wrap;
             margin-bottom: 12px; }
  .sel-row select, .sel-row input, .sel-row button { padding: 6px 12px; border: 1px solid
    var(--border); border-radius: 6px; font-size: .82rem; }
  .sel-row button { background: var(--accent); color: #fff; border: none; cursor: pointer; }

  /* ── autocomplete ── */
  .autocomplete-wrap { position: relative; flex: 1; min-width: 160px; }
  .autocomplete-wrap input { width: 100%; padding: 7px 12px; border: 1px solid var(--border);
    border-radius: 6px; font-size: .82rem; outline: none; background: var(--card); }
  .autocomplete-wrap input:focus { border-color: var(--accent); }
  .autocomplete-dropdown { position: absolute; top: 100%; left: 0; right: 0;
    max-height: 220px; overflow-y: auto; background: var(--card); border: 1px solid var(--border);
    border-radius: 0 0 6px 6px; z-index: 200; display: none; box-shadow: 0 4px 12px rgba(0,0,0,.1);
    margin-top: 2px; }
  .autocomplete-dropdown.show { display: block; }
  .autocomplete-item { padding: 8px 14px; cursor: pointer; font-size: .82rem;
    border-bottom: 1px solid #f1f5f9; transition: background .1s; }
  .autocomplete-item:last-child { border-bottom: none; }
  .autocomplete-item:hover, .autocomplete-item.active { background: #eff6ff; }
  .autocomplete-item .title { font-weight: 500; }
  .autocomplete-item .sub { font-size: .7rem; color: var(--muted); }
  .autocomplete-empty { padding: 10px 14px; font-size: .78rem; color: var(--muted);
    text-align: center; }

  /* ── crawl toast ── */
  .crawl-toast { position: fixed; top: 60px; left: 50%; transform: translateX(-50%);
    z-index: 999; padding: 10px 24px; border-radius: 8px; font-size: .82rem;
    font-weight: 500; box-shadow: 0 4px 16px rgba(0,0,0,.15);
    display: none; align-items: center; gap: 10px; white-space: nowrap; }
  .crawl-toast.running { background: #eff6ff; color: #1e40af; border: 1px solid #bfdbfe; }
  .crawl-toast.done { background: #d1fae5; color: #065f46; border: 1px solid #a7f3d0; }
  .crawl-toast.error { background: #fee2e2; color: #991b1b; border: 1px solid #fecaca; }
  .crawl-toast .spinner { width: 16px; height: 16px; border: 2px solid #bfdbfe;
    border-top-color: #2563eb; border-radius: 50%; animation: spin .6s linear infinite; }
  @keyframes spin { to { transform: rotate(360deg); } }

  canvas { max-height: 300px; }
</style>
</head>
<body>

<nav class="navbar">
  <div class="navbar-inner">
    <a href="/" class="logo" style="color:#fff;text-decoration:none;">
      <span class="icon">🕷</span> Amazon Spider
    </a>
    <nav>
      <a href="/">📦 商品浏览</a>
      <a href="/dashboard" class="active">📊 驾驶舱</a>
    </nav>
    <div class="db-badge">
      <span class="dot"></span>
      <span style="color:#94a3b8;">数据已连接</span>
    </div>
  </div>
</nav>

<div class="breadcrumb">
  <a href="/">首页</a> <span>›</span> <a href="/dashboard">运营驾驶舱</a>
</div>

<div class="main" style="margin-top:14px;">

<div class="grid-3">
  <div class="panel kpi"><div class="num blue" id="kpi-total">-</div><div class="lbl">商品总数</div></div>
  <div class="panel kpi"><div class="num green" id="kpi-bsr">-</div><div class="lbl">有 BSR 排名商品</div></div>
  <div class="panel kpi"><div class="num yellow" id="kpi-opps">-</div><div class="lbl">发现机会品</div></div>
</div>

<div class="sel-row">
  <label>关键词:</label>
  <div class="autocomplete-wrap" id="kw-ac-wrap">
    <input type="text" id="kw-input" placeholder="输入关键词搜索…" autocomplete="off">
    <div class="autocomplete-dropdown" id="kw-dropdown"></div>
  </div>
  <label>商品:</label>
  <div class="autocomplete-wrap" id="asin-ac-wrap" style="flex:2;">
    <input type="text" id="asin-input" placeholder="输入品牌/标题/ASIN 搜索商品…" autocomplete="off">
    <div class="autocomplete-dropdown" id="asin-dropdown"></div>
  </div>
  <button onclick="loadAll()">刷新</button>
  <button onclick="triggerDashboardCrawl()" id="dash-crawl-btn" style="background:var(--green);">🔄 采集</button>
</div>

<!-- crawl toast -->
<div class="crawl-toast" id="dash-toast">
  <span class="spinner" id="dash-toast-spinner"></span>
  <span id="dash-crawl-msg"></span>
</div>

<!-- 价格走势 -->
<div class="panel">
  <h2>📈 价格走势</h2>
  <div class="sub" id="price-sub">选择一个商品查看价格历史</div>
  <canvas id="priceChart" height="200"></canvas>
</div>

<!-- 价格分布 -->
<div class="panel">
  <h2>📊 价格分布</h2>
  <div class="sub" id="price-dist-sub">按关键词查看价格区间分布</div>
  <canvas id="priceDistChart" height="180"></canvas>
</div>

<div class="grid-2">
  <!-- BSR 排行 -->
  <div class="panel">
    <h2>🏆 BSR 排行</h2>
    <div class="sub" id="bsr-sub"></div>
    <table><thead><tr><th>#</th><th>商品</th><th>BSR</th><th>预估月销</th><th>价格</th><th>评分</th></tr></thead>
    <tbody id="bsr-tbody"></tbody></table>
  </div>

  <!-- 竞品雷达 -->
  <div class="panel">
    <h2>🎯 竞品雷达</h2>
    <div class="sub" id="radar-sub"></div>
    <canvas id="radarChart" height="250"></canvas>
  </div>
</div>

<!-- 机会发现 -->
<div class="panel">
  <h2>💡 机会发现</h2>
  <div class="sub">高评分低评论 = 新品黑马 · 高评分高评论低价格 = 性价比标杆</div>
  <div class="grid-3" id="opps-grid" style="margin-top:12px;"></div>
</div>

</div>

<script>
let priceChart = null, radarChart = null, priceDistChart = null;
let keywordList = [];
let productList = [];
let currentKw = '';
let currentAsin = '';

// ── Autocomplete builder ─────────────────────────────────────────────────
function buildAutocomplete(inputId, dropdownId, getItems, onSelect, placeholder) {
  const input = document.getElementById(inputId);
  const dropdown = document.getElementById(dropdownId);
  let activeIdx = -1;

  input.placeholder = placeholder || '输入搜索…';

  input.addEventListener('input', () => {
    const q = input.value.trim();
    activeIdx = -1;
    const items = getItems(q);
    renderDropdown(dropdown, items, input.value.trim(), onSelect);
  });

  input.addEventListener('keydown', (e) => {
    const items = dropdown.querySelectorAll('.autocomplete-item');
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      activeIdx = Math.min(activeIdx + 1, items.length - 1);
      updateActive(items, activeIdx);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      activeIdx = Math.max(activeIdx - 1, -1);
      updateActive(items, activeIdx);
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (activeIdx >= 0 && items[activeIdx]) {
        items[activeIdx].click();
      }
    } else if (e.key === 'Escape') {
      dropdown.classList.remove('show');
    }
  });

  input.addEventListener('focus', () => {
    const q = input.value.trim();
    const items = getItems(q);
    if (items.length > 0) renderDropdown(dropdown, items, q, onSelect);
  });

  document.addEventListener('click', (e) => {
    if (!input.parentElement.contains(e.target)) {
      dropdown.classList.remove('show');
    }
  });

  return input;
}

function renderDropdown(dropdown, items, query, onSelect) {
  if (items.length === 0) {
    dropdown.innerHTML = '<div class="autocomplete-empty">无匹配结果</div>';
    dropdown.classList.add('show');
    return;
  }
  dropdown.innerHTML = items.map((item, i) =>
    '<div class="autocomplete-item" data-idx="' + i + '" data-value="' + item.value + '">' +
    (item.html || item.label) + '</div>'
  ).join('');
  dropdown.classList.add('show');

  dropdown.querySelectorAll('.autocomplete-item').forEach(el => {
    el.addEventListener('click', () => {
      dropdown.classList.remove('show');
      onSelect(el.dataset.value, el.textContent);
    });
  });
}

function updateActive(items, idx) {
  items.forEach((el, i) => el.classList.toggle('active', i === idx));
  if (idx >= 0 && items[idx]) {
    items[idx].scrollIntoView({ block: 'nearest' });
  }
}

// ── Keyword autocomplete ────────────────────────────────────────────────
function keywordItems(query) {
  const q = query.toLowerCase();
  const filtered = keywordList.filter(kw => kw.toLowerCase().includes(q));
  if (!query && filtered.length === 0) return keywordList.map(k => ({value: k, label: k}));
  return filtered.map(k => ({value: k, label: k}));
}

function onKeywordSelect(value) {
  currentKw = value;
  document.getElementById('kw-input').value = value;
  loadAll();
}

// ── Product autocomplete ────────────────────────────────────────────────
function productItems(query) {
  const q = query.toLowerCase();
  let list = productList;
  if (currentKw) {
    list = productList.filter(p => p.keyword === currentKw);
  }
  if (!query) return list.slice(0, 30).map(p => formatProductItem(p));
  const filtered = list.filter(p =>
    (p.title || '').toLowerCase().includes(q) ||
    (p.brand || '').toLowerCase().includes(q) ||
    (p.asin || '').toLowerCase().includes(q)
  );
  return filtered.slice(0, 30).map(p => formatProductItem(p));
}

function formatProductItem(p) {
  return {
    value: p.asin,
    label: (p.brand ? '[' + p.brand + '] ' : '') + p.title,
    html: '<div class="title">' + ((p.brand ? '[' + p.brand + '] ' : '') + p.title.slice(0, 70)) + '</div>' +
          '<div class="sub">' + p.asin + (p.price ? ' · $' + p.price : '') + '</div>'
  };
}

function onProductSelect(value) {
  currentAsin = value;
  document.getElementById('asin-input').value = value;
  loadPriceHistory();
}

// ── Dashboard crawl ──────────────────────────────────────────────────
let dashCrawlTimer = null;
let dashBeforeStats = null;

function showDashToast(msg, type) {
  var t = document.getElementById('dash-toast');
  t.className = 'crawl-toast ' + type;
  document.getElementById('dash-crawl-msg').innerHTML = msg;
  document.getElementById('dash-toast-spinner').style.display = (type === 'running') ? '' : 'none';
  t.style.display = 'flex';
}

function hideDashToast() {
  document.getElementById('dash-toast').style.display = 'none';
  if (dashCrawlTimer) { clearInterval(dashCrawlTimer); dashCrawlTimer = null; }
}

async function triggerDashboardCrawl() {
  var btn = document.getElementById('dash-crawl-btn');
  btn.disabled = true;
  btn.textContent = '⏳ …';
  showDashToast('采集任务启动中…', 'running');

  // Snapshot stats before crawl for comparison
  try {
    var kwParam = currentKw ? '?kw=' + encodeURIComponent(currentKw) : '';
    var beforeR = await fetch('/api/stats' + kwParam);
    dashBeforeStats = await beforeR.json();
  } catch(e) {
    dashBeforeStats = null;
  }

  var body = {};
  if (currentKw) body.keyword = currentKw;

  try {
    var r = await fetch('/api/crawl', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body)
    });
    var d = await r.json();

    if (d.error) {
      showDashToast(d.error, 'error');
      btn.disabled = false;
      btn.textContent = '🔄 采集';
      setTimeout(hideDashToast, 5000);
      return;
    }

    showDashToast('正在采集' + (currentKw || '全部') + '数据…', 'running');
    btn.textContent = '⏳ …';

    dashCrawlTimer = setInterval(async () => {
      try {
        var sr = await fetch('/api/crawl-status/' + d.job_id);
        var sd = await sr.json();
        if (sd.status === 'done') {
          clearInterval(dashCrawlTimer);
          // Compare before/after stats
          var afterKwParam = currentKw ? '?kw=' + encodeURIComponent(currentKw) : '';
          var afterR = await fetch('/api/stats' + afterKwParam);
          var afterStats = await afterR.json();

          var msg = '✓ 采集完成！';
          if (dashBeforeStats && afterStats) {
            var diffs = [];
            var totalDiff = (afterStats.total || 0) - (dashBeforeStats.total || 0);
            var bsrDiff = (afterStats.with_bsr || 0) - (dashBeforeStats.with_bsr || 0);
            if (totalDiff !== 0) diffs.push('商品 ' + (totalDiff > 0 ? '+' : '') + totalDiff);
            if (bsrDiff !== 0) diffs.push('BSR ' + (bsrDiff > 0 ? '+' : '') + bsrDiff);
            if (diffs.length > 0) {
              msg += ' 变化: ' + diffs.join('，');
            } else {
              msg += ' 数据无变化';
            }
          }
          msg += ' · 正在刷新…';
          showDashToast(msg, 'done');
          btn.disabled = false;
          btn.textContent = '🔄 采集';
          setTimeout(() => { hideDashToast(); loadAll(); }, 2000);
        } else if (sd.status === 'error') {
          clearInterval(dashCrawlTimer);
          showDashToast('采集失败', 'error');
          btn.disabled = false;
          btn.textContent = '🔄 采集';
          setTimeout(hideDashToast, 5000);
        }
      } catch(e) {}
    }, 3000);
  } catch(e) {
    showDashToast('网络错误', 'error');
    btn.disabled = false;
    btn.textContent = '🔄 采集';
    setTimeout(hideDashToast, 4000);
  }
}

// ── Init ────────────────────────────────────────────────────────────────
async function init() {
  const r = await fetch('/api/keywords');
  const data = await r.json();
  keywordList = data.keywords || [];

  buildAutocomplete('kw-input', 'kw-dropdown', keywordItems, onKeywordSelect, '输入关键词搜索…');
  buildAutocomplete('asin-input', 'asin-dropdown', productItems, onProductSelect, '输入品牌/标题/ASIN 搜索商品…');

  // Load all products for autocomplete
  const pr = await fetch('/api/products');
  const pd = await pr.json();
  productList = pd.products || [];

  loadAll();
}

async function loadAll() {
  await Promise.all([loadKPIs(), loadBSR(), loadCompetitors(), loadOpportunities(), loadPriceDistribution()]);
}

// ── KPIs ──
async function loadKPIs() {
  const kw = currentKw ? '?kw=' + encodeURIComponent(currentKw) : '';
  const r = await fetch('/api/stats' + kw);
  const d = await r.json();
  document.getElementById('kpi-total').textContent = d.total || 0;
  document.getElementById('kpi-bsr').textContent = d.with_bsr || 0;
  document.getElementById('kpi-opps').textContent = d.opportunities || 0;
}

// ── Price history chart ──
async function loadPriceHistory() {
  const asin = document.getElementById('asin-select').value;
  if (!asin) {
    document.getElementById('price-sub').textContent = '选择一个商品查看价格历史';
    if (priceChart) { priceChart.destroy(); priceChart = null; }
    return;
  }
  const r = await fetch('/api/price-history?asin=' + asin);
  const data = await r.json();
  const pts = data.points || [];
  if (pts.length === 0) {
    document.getElementById('price-sub').textContent = '暂无历史数据（需要多次爬取同一商品）';
    return;
  }
  document.getElementById('price-sub').textContent =
    data.title + ' — ' + pts.length + ' 次采集记录';

  const ctx = document.getElementById('priceChart').getContext('2d');
  if (priceChart) priceChart.destroy();
  priceChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: pts.map(p => p.time),
      datasets: [{
        label: '价格 (USD)',
        data: pts.map(p => p.price),
        borderColor: '#2563eb',
        backgroundColor: 'rgba(37,99,235,0.08)',
        fill: true,
        tension: 0.3,
        pointRadius: 4,
      }]
    },
    options: {
      responsive: true,
      plugins: { legend: { display: false } },
      scales: {
        y: { beginAtZero: false, title: { display: true, text: 'USD' } },
        x: { title: { display: true, text: '采集时间' } }
      }
    }
  });
}

// ── BSR ranking ──
let bsrAllRows = [];
let bsrExpanded = false;
const BSR_SHOW_INITIAL = 10;

function renderBSRRow(r, i) {
  return '<tr><td>' + (i+1) + '</td><td title="' + r.title + '">' +
    '<a href="/product/' + r.asin + '" style="color:var(--text);text-decoration:none;" ' +
    'onmouseover="this.style.color=\'var(--accent)\'" onmouseout="this.style.color=\'var(--text)\'">' +
    r.title.slice(0, 35) + '</a></td><td>' + r.bsr + '</td><td>' +
    (r.est_monthly_sales ? r.est_monthly_sales.toLocaleString() : '-') + '</td><td>$' +
    (r.price||'-') + '</td><td>' + (r.rating ? '★'+r.rating : '-') + '</td></tr>';
}

async function loadBSR() {
  const kw = currentKw ? '?kw=' + encodeURIComponent(currentKw) : '';
  const r = await fetch('/api/bsr-top' + kw);
  const data = await r.json();
  bsrAllRows = data.ranking || [];
  bsrExpanded = false;
  document.getElementById('bsr-sub').textContent =
    (currentKw || '全部关键词') + ' · 共 ' + bsrAllRows.length + ' 个有BSR商品';
  renderBSRTable();
}

function renderBSRTable() {
  const tbody = document.getElementById('bsr-tbody');
  if (bsrAllRows.length === 0) {
    tbody.innerHTML = '<tr><td colspan="6">暂无BSR数据</td></tr>';
    return;
  }
  const collapsed = bsrAllRows.length > BSR_SHOW_INITIAL && !bsrExpanded;
  const visible = collapsed ? bsrAllRows.slice(0, BSR_SHOW_INITIAL) : bsrAllRows;
  let html = visible.map((r, i) => renderBSRRow(r, i)).join('');
  if (bsrAllRows.length > BSR_SHOW_INITIAL) {
    html += '<tr><td colspan="6" style="text-align:center;padding:8px;">' +
      '<button onclick="toggleBSR()" id="bsr-toggle-btn" ' +
      'style="padding:6px 20px;border:1px solid var(--border);border-radius:6px;' +
      'background:var(--card);color:var(--accent);cursor:pointer;font-size:.8rem;' +
      'transition:all .15s;">' +
      (bsrExpanded ? '收起 ▲' : '展开全部 (' + bsrAllRows.length + ' 条) ▼') +
      '</button></td></tr>';
  }
  tbody.innerHTML = html;
}

function toggleBSR() {
  bsrExpanded = !bsrExpanded;
  renderBSRTable();
}

// ── Competitor radar ──
async function loadCompetitors() {
  const kw = currentKw ? '?kw=' + encodeURIComponent(currentKw) : '';
  const r = await fetch('/api/competitors' + kw);
  const data = await r.json();
  const brands = data.brands || [];
  document.getElementById('radar-sub').textContent =
    (currentKw || '全部') + ' · ' + brands.length + ' 个品牌';

  const ctx = document.getElementById('radarChart').getContext('2d');
  if (radarChart) radarChart.destroy();
  if (brands.length === 0) return;

  const colors = ['#2563eb','#059669','#d97706','#dc2626','#7c3aed','#0891b2',
                  '#be123c','#4f46e5','#ea580c','#15803d'];
  radarChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: brands.map(b => b.brand),
      datasets: [{
        label: '均价 (USD)',
        data: brands.map(b => b.avg_price),
        backgroundColor: colors,
        yAxisID: 'y',
      }]
    },
    options: {
      responsive: true,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: ctx => [
              '均价: $' + (ctx.raw||0).toFixed(2),
              '均分: ' + (brands[ctx.dataIndex].avg_rating||'-'),
              '评论: ' + (brands[ctx.dataIndex].avg_reviews||'-'),
              '商品数: ' + brands[ctx.dataIndex].count,
            ].join(' | ')
          }
        }
      },
      scales: {
        y: { title: { display: true, text: 'USD' }, beginAtZero: false }
      }
    }
  });
}

// ── Opportunities ──
async function loadOpportunities() {
  const r = await fetch('/api/opportunities');
  const data = await r.json();
  const opps = data.opportunities || [];
  const grid = document.getElementById('opps-grid');
  grid.innerHTML = opps.map(o =>
    '<div class="opp-card">' +
    '<a href="/product/' + o.asin + '" style="text-decoration:none;color:inherit;"><div class="t" title="' + o.title + '">' + o.title.slice(0, 50) + '</div></a>' +
    '<div style="font-size:.78rem;color:var(--muted);">' +
    '★ ' + (o.rating||'-') + ' · ' + (o.review_count||0) + '评论 · $' +
    (o.price||'-') + '</div>' +
    (o.review_velocity != null ?
     '<div style="font-size:.72rem;color:#7c3aed;">日增 ' +
     o.review_velocity + ' 评论</div>' : '') +
    '<div class="tags">' +
    '<span class="tag gold">' + (o.reason || '机会品') + '</span>' +
    (o.keyword ? '<span class="tag blue">' + o.keyword + '</span>' : '') +
    (o.brand ? '<span class="tag green">' + o.brand + '</span>' : '') +
    '</div></div>'
  ).join('') || '<div style="color:var(--muted);">暂无机会发现</div>';
}

// ── Price distribution ──
async function loadPriceDistribution() {
  const kw = currentKw ? '?kw=' + encodeURIComponent(currentKw) : '';
  const r = await fetch('/api/price-distribution' + kw);
  const data = await r.json();
  const dist = data.distribution || [];
  const total = dist.reduce((a, d) => a + d.count, 0);
  document.getElementById('price-dist-sub').textContent =
    (currentKw || '全部关键词') + ' · ' + total + ' 个有价格商品';

  const ctx = document.getElementById('priceDistChart').getContext('2d');
  if (priceDistChart) priceDistChart.destroy();

  const colors = ['#3b82f6','#10b981','#f59e0b','#f97316','#ef4444','#8b5cf6'];

  priceDistChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: dist.map(d => d.range),
      datasets: [{
        label: '商品数',
        data: dist.map(d => d.count),
        backgroundColor: colors,
        borderRadius: 4,
      }]
    },
    options: {
      responsive: true,
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: ctx => '商品数: ' + ctx.raw } }
      },
      scales: {
        y: { beginAtZero: true, title: { display: true, text: '商品数' }, ticks: { stepSize: 1 } },
        x: { title: { display: true, text: '价格区间' } }
      }
    }
  });
}

// ── init ──
init();
</script>
</body>
</html>'''


# ── Product detail page ──────────────────────────────────────────────────────

PRODUCT_TEMPLATE = r'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ title or asin }} — Amazon Spider</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"></script>
<style>
  :root {
    --bg: #f0f2f5; --card: #fff; --text: #1a1a2e; --muted: #6b7280;
    --accent: #2563eb; --accent-hover: #1d4ed8;
    --green: #059669; --yellow: #d97706; --red: #dc2626;
    --border: #e5e7eb; --shadow: 0 1px 3px rgba(0,0,0,.06);
    --radius: 8px;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
         background: var(--bg); color: var(--text); min-height: 100vh; }

  .navbar { background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
            color: #fff; padding: 0 24px; position: sticky; top: 0; z-index: 100; }
  .navbar-inner { max-width: 1200px; margin: 0 auto; display: flex;
                  align-items: center; height: 52px; gap: 20px; }
  .navbar .logo { font-size: 1.05rem; font-weight: 700; white-space: nowrap;
                  display: flex; align-items: center; gap: 8px; }
  .navbar nav { display: flex; gap: 4px; flex: 1; }
  .navbar nav a { color: #94a3b8; text-decoration: none; padding: 6px 14px;
                  border-radius: 6px; font-size: .82rem; font-weight: 500;
                  transition: background .15s, color .15s; }
  .navbar nav a:hover { background: rgba(255,255,255,.08); color: #e2e8f0; }

  .breadcrumb { max-width: 1200px; margin: 0 auto; padding: 10px 24px 0;
                font-size: .78rem; color: var(--muted); }
  .breadcrumb a { color: var(--accent); text-decoration: none; }
  .breadcrumb a:hover { text-decoration: underline; }

  .main { max-width: 1200px; margin: 0 auto; padding: 12px 24px 40px; }

  /* ── freshness badge ── */
  .freshness-badge { display: flex; align-items: center; gap: 8px; padding: 8px 14px;
    border-radius: 6px; font-size: .78rem; margin-bottom: 10px; }
  .freshness-badge.fresh { background: #d1fae5; color: #065f46; }
  .freshness-badge.stale { background: #fef3c7; color: #92400e; }
  .freshness-badge.old { background: #fee2e2; color: #991b1b; }

  /* ── crawl result banner ── */
  .crawl-result-banner { border-radius: var(--radius); padding: 14px 18px;
    margin-bottom: 12px; font-size: .82rem; display: flex; align-items: flex-start;
    gap: 12px; box-shadow: var(--shadow); }
  .crawl-result-banner.changed { background: #eff6ff; border: 1px solid #bfdbfe; color: #1e40af; }
  .crawl-result-banner.nochange { background: #f8fafc; border: 1px solid #e5e7eb; color: #475569; }
  .crawl-result-banner .banner-icon { font-size: 1.4rem; flex-shrink: 0; }
  .crawl-result-banner .banner-body { flex: 1; }
  .crawl-result-banner .banner-title { font-weight: 600; margin-bottom: 4px; }
  .crawl-result-banner .banner-item { display: inline-flex; align-items: center; gap: 6px;
    padding: 3px 10px; border-radius: 4px; margin: 2px 4px 2px 0;
    font-size: .78rem; white-space: nowrap; }
  .crawl-result-banner .banner-item.up { background: #fee2e2; color: #991b1b; }
  .crawl-result-banner .banner-item.down { background: #d1fae5; color: #065f46; }
  .crawl-result-banner .banner-summary { font-size: .75rem; margin-top: 4px; }
  .crawl-result-banner .banner-stats { display: flex; gap: 12px; margin-top: 6px;
    font-size: .73rem; color: var(--muted); }

  /* ── header ── */
  .product-header { background: var(--card); border-radius: var(--radius);
    box-shadow: var(--shadow); padding: 16px 20px; margin-bottom: 10px;
    display: flex; gap: 18px; }
  .product-header .img-box { flex-shrink: 0; width: 160px; height: 160px;
    display: flex; align-items: center; justify-content: center;
    background: #f8f9fb; border-radius: 8px; overflow: hidden;
    border: 1px solid var(--border); }
  .product-header .img-box img { max-width: 100%; max-height: 100%;
    object-fit: contain; }
  .product-header .img-box .no-img { font-size: 3rem; color: #d1d5db; }
  .product-header .header-info { flex: 1; min-width: 0; }
  .product-header h1 { font-size: 1rem; line-height: 1.45; margin-bottom: 8px;
    display: flex; align-items: flex-start; gap: 8px; }
  .product-header h1 .title-text { flex: 1; }
  .copy-btn { flex-shrink: 0; padding: 4px 10px; border: 1px solid var(--border);
    border-radius: 4px; background: var(--card); color: var(--muted);
    cursor: pointer; font-size: .72rem; white-space: nowrap; transition: all .15s; }
  .copy-btn:hover { border-color: var(--accent); color: var(--accent); }
  .copy-btn.copied { border-color: var(--green); color: var(--green); background: #d1fae5; }
  .crawl-btn { flex-shrink: 0; padding: 4px 12px; border: 1px solid var(--green);
    border-radius: 4px; background: #d1fae5; color: #065f46;
    cursor: pointer; font-size: .72rem; white-space: nowrap; transition: all .15s;
    font-weight: 500; }
  .crawl-btn:hover { background: #a7f3d0; }
  .crawl-btn:disabled { opacity: .6; cursor: not-allowed; }

  /* ── toast ── */
  .crawl-toast { position: fixed; top: 60px; left: 50%; transform: translateX(-50%);
    z-index: 999; padding: 10px 24px; border-radius: 8px; font-size: .82rem;
    font-weight: 500; box-shadow: 0 4px 16px rgba(0,0,0,.15);
    display: none; align-items: center; gap: 10px; white-space: nowrap; }
  .crawl-toast.running { background: #eff6ff; color: #1e40af; border: 1px solid #bfdbfe; }
  .crawl-toast.done { background: #d1fae5; color: #065f46; border: 1px solid #a7f3d0; }
  .crawl-toast.error { background: #fee2e2; color: #991b1b; border: 1px solid #fecaca; }
  .crawl-toast .spinner { width: 16px; height: 16px; border: 2px solid #bfdbfe;
    border-top-color: #2563eb; border-radius: 50%; animation: spin .6s linear infinite; }
  @keyframes spin { to { transform: rotate(360deg); } }
  .amazon-link { font-size: .78rem; color: var(--accent); text-decoration: none;
    display: inline-flex; align-items: center; gap: 4px; }
  .amazon-link:hover { text-decoration: underline; }

  /* ── tags ── */
  .tag { font-size: .7rem; padding: 2px 8px; border-radius: 4px;
         background: #f1f5f9; color: #475569; white-space: nowrap;
         display: inline-block; margin: 2px; text-decoration: none;
         transition: background .15s; }
  .tag.clickable { cursor: pointer; }
  .tag.clickable:hover { background: #dbeafe; }
  .tag.bsr { background: #fef2f2; color: #991b1b; }
  .tag.prime { background: #d1fae5; color: #065f46; }
  .tag.fba  { background: #dbeafe; color: #1e40af; }

  /* ── section divider ── */
  .section-label { font-size: .68rem; color: var(--muted); text-transform: uppercase;
    letter-spacing: .8px; margin-bottom: 6px; padding-left: 2px; }

  /* ── info grid ── */
  .info-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(165px, 1fr));
               gap: 8px; margin-bottom: 12px; }
  .info-card { background: var(--card); border-radius: var(--radius);
    box-shadow: var(--shadow); padding: 12px; position: relative; }
  .info-card .label { font-size: .68rem; color: var(--muted); margin-bottom: 3px;
                      display: flex; align-items: center; gap: 4px; }
  .info-card .value { font-size: .95rem; font-weight: 600; color: var(--text); }
  .info-card .value.price { color: var(--red); }
  .info-card .value.rating { color: #f59e0b; }
  .info-card .value.green { color: var(--green); }
  .info-card .value.purple { color: #7c3aed; }
  .info-card .value.blue { color: var(--accent); }
  .info-card .delta { font-size: .7rem; margin-top: 2px; }
  .info-card .delta.up { color: var(--red); }
  .info-card .delta.down { color: var(--green); }
  .info-card .delta.flat { color: var(--muted); }
  .info-card .source-tag { font-size: .6rem; padding: 1px 5px; border-radius: 3px;
    position: absolute; top: 6px; right: 8px; }
  .info-card .source-tag.scraped { background: #dbeafe; color: #1e40af; }
  .info-card .source-tag.derived { background: #fef3c7; color: #92400e; }

  /* ── panels ── */
  .panel { background: var(--card); border-radius: var(--radius);
           box-shadow: var(--shadow); padding: 14px 18px; margin-bottom: 10px; }
  .panel h2 { font-size: .95rem; margin-bottom: 8px; }
  .panel .sub { font-size: .73rem; color: var(--muted); margin-bottom: 10px; }

  .price-table { width: 100%; border-collapse: collapse; font-size: .8rem; }
  .price-table th, .price-table td { padding: 7px 10px; text-align: left;
    border-bottom: 1px solid var(--border); }
  .price-table th { color: var(--muted); font-weight: 600; background: #f8fafc; }
  .price-table td.na { color: var(--muted); font-style: italic; }

  /* ── empty state ── */
  .empty-hint { text-align: center; padding: 30px 20px; color: var(--muted); }
  .empty-hint .icon { font-size: 2.2rem; margin-bottom: 8px; }
  .empty-hint p { font-size: .82rem; margin-bottom: 10px; }
  .empty-hint a { color: var(--accent); text-decoration: none; font-weight: 500; }

  /* ── bottom nav ── */
  .bottom-nav { display: flex; gap: 10px; justify-content: center; align-items: center;
    margin-top: 14px; flex-wrap: wrap; }
  .bottom-nav a, .bottom-nav button { padding: 7px 18px; border: 1px solid var(--border);
    border-radius: 6px; font-size: .8rem; text-decoration: none; color: var(--text);
    background: var(--card); cursor: pointer; transition: all .15s; white-space: nowrap; }
  .bottom-nav a:hover, .bottom-nav button:hover { border-color: var(--accent); color: var(--accent); }
  .bottom-nav a.disabled { color: #d1d5db; pointer-events: none; }

  canvas { max-height: 250px; }

  @media (max-width: 640px) {
    .info-grid { grid-template-columns: repeat(2, 1fr); }
    .product-header { flex-direction: column; }
    .product-header .img-box { width: 120px; height: 120px; margin: 0 auto; }
    .product-header h1 { font-size: .9rem; }
  }
</style>
</head>
<body>

<nav class="navbar">
  <div class="navbar-inner">
    <a href="/" class="logo" style="color:#fff;text-decoration:none;">
      <span class="icon">🕷</span> Amazon Spider
    </a>
    <nav>
      <a href="/">📦 商品浏览</a>
      <a href="/dashboard">📊 驾驶舱</a>
    </nav>
    {% if kw %}
    <a href="/?kw={{ kw }}" class="amazon-link" style="color:#94a3b8;">← 返回 {{ kw }}</a>
    {% else %}
    <a href="/" class="amazon-link" style="color:#94a3b8;">← 返回列表</a>
    {% endif %}
  </div>
</nav>

<div class="breadcrumb">
  <a href="/">首页</a> <span>›</span>
  {% if kw %}<a href="/?kw={{ kw }}">{{ kw }}</a> <span>›</span>{% endif %}
  <span>{{ brand or '单品分析' }}</span> <span>›</span>
  <span title="{{ asin }}">{{ title[:40] if title else asin }}</span>
</div>

<!-- crawl toast -->
<div class="crawl-toast" id="crawl-toast">
  <span class="spinner" id="toast-spinner"></span>
  <span id="crawl-msg"></span>
</div>

<div class="main">

  <!-- ── Data freshness banner ── -->
  {% if hours_ago is not none %}
  <div class="freshness-badge {{ 'fresh' if hours_ago is not none and hours_ago < 6 else ('stale' if hours_ago is not none and hours_ago < 24 else 'old') }}">
    {% if hours_ago is not none %}
      {% if hours_ago < 6 %}
      🟢 数据采集于 {{ scraped_at[:19] }}（{{ freshness_text }}），数据较新
      {% elif hours_ago < 24 %}
      🟡 数据采集于 {{ scraped_at[:19] }}（{{ freshness_text }}），建议更新
      {% else %}
      🔴 数据采集于 {{ scraped_at[:19] }}（{{ freshness_text }}），数据可能已过时
      {% endif %}
    {% else %}
    ⚪ 采集时间未知
    {% endif %}
  </div>
  {% endif %}

  <!-- ── Post-crawl result banner ── -->
  {% if crawl_result %}
  <div class="crawl-result-banner {{ 'changed' if crawl_result.has_change else 'nochange' }}">
    <div class="banner-icon">
      {% if crawl_result.has_change %}📊{% else %}ℹ️{% endif %}
    </div>
    <div class="banner-body">
      <div class="banner-title">
        🔄 重新采集完成
        {% if crawl_result.has_change %}
        — 数据有变化
        {% else %}
        — 数据无变化
        {% endif %}
      </div>
      {% if crawl_result.has_change %}
      <div>
        {% for ch in crawl_result.changes %}
        <span class="banner-item {{ ch.dir }}">
          {{ ch.label }}: {{ ch.text }}
          <strong>{{ ch.delta }}</strong>
        </span>
        {% endfor %}
      </div>
      {% else %}
      <div class="banner-summary">
        本次采集的价格、BSR 排名、评论数与上次完全一致，商品数据稳定。
      </div>
      {% endif %}
      <div class="banner-stats">
        <span>📈 历史记录: {{ crawl_result.record_count }} 条</span>
        <span>🕐 采集时间: {{ scraped_at[:19] if scraped_at else '-' }}</span>
      </div>
    </div>
  </div>
  {% endif %}

  <!-- ── Title + actions ── -->
  <div class="product-header">
    <div class="img-box">
      {% if image_url %}
      <img src="{{ image_url }}" alt="{{ title }}" loading="eager"
           onerror="this.parentElement.innerHTML='<span class=\\'no-img\\'>📷</span>'">
      {% else %}
      <span class="no-img">📷</span>
      {% endif %}
    </div>
    <div class="header-info">
      <h1>
        <span class="title-text">{{ title or asin }}</span>
        <button class="copy-btn" onclick="copyText('{{ title|replace("'", "\\'") }}', this)" title="复制标题">📋 标题</button>
        <button class="copy-btn" onclick="copyText('{{ asin }}', this)" title="复制 ASIN">🆔 ASIN</button>
        <button class="copy-btn" onclick="copySummary()" title="复制完整数据摘要" style="border-color:var(--accent);color:var(--accent);font-weight:500;">📋 复制数据</button>
        <button class="crawl-btn" id="crawl-btn" onclick="triggerCrawl('{{ asin }}')" title="重新采集此商品">🔄 重新采集</button>
      </h1>
      <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
        <a href="https://www.amazon.com/dp/{{ asin }}" target="_blank" class="amazon-link">🔗 Amazon</a>
        <a href="https://www.amazon.com/dp/{{ asin }}/#customerReviews" target="_blank"
           class="amazon-link" style="font-size:.75rem;">📝 评论</a>
        {% if brand %}
        <a href="https://www.amazon.com/s?me={{ brand }}" target="_blank"
           class="amazon-link" style="font-size:.75rem;">🏪 店铺</a>
        {% endif %}
        <!-- clickable tags -->
        {% if brand %}<a href="/?q={{ brand }}" class="tag clickable" style="background:#fef3c7;color:#92400e;">🏷 {{ brand }}</a>{% endif %}
        {% if keyword %}<a href="/?kw={{ keyword }}" class="tag clickable" style="background:#dbeafe;color:#1e40af;">🔑 {{ keyword }}</a>{% endif %}
        {% if bsr_short %}<span class="tag bsr">📊 {{ bsr_short }}</span>{% endif %}
        {% if is_prime == 'Yes' %}<span class="tag prime">✓ Prime</span>{% endif %}
        {% if fulfillment_type %}<span class="tag fba">{{ fulfillment_type[:20] }}</span>{% endif %}
        {% if variation_count is not none %}<span class="tag">📐 {{ variation_count }} 变体</span>{% endif %}
      </div>
    </div>
  </div>

  <!-- ═══════ Card Group 1: Scraped Data ═══════ -->
  <div class="section-label">📡 实时抓取数据</div>
  <div class="info-grid">
    {% if price is not none %}
    <div class="info-card">
      <span class="source-tag scraped">抓取</span>
      <div class="label">当前价格</div>
      <div class="value price">${{ '{:,.2f}'.format(price) }}</div>
      {% if deltas.get('price') %}
      <div class="delta {{ deltas.price[0] }}">{{ deltas.price[1] }}</div>
      {% elif price_delta is not none %}
      <div class="delta {{ 'up' if price_delta > 0 else ('down' if price_delta < 0 else '') }}">
        {% if price_delta > 0 %}↑ +${{ '{:,.2f}'.format(price_delta) }}{% elif price_delta < 0 %}↓ -${{ '{:,.2f}'.format(price_delta|abs) }}{% else %}持平{% endif %}
      </div>
      {% endif %}
    </div>
    {% endif %}
    {% if original_price is not none %}
    <div class="info-card">
      <span class="source-tag scraped">抓取</span>
      <div class="label">原价</div>
      <div class="value" style="text-decoration:line-through;color:var(--muted);font-size:.85rem;">${{ '{:,.2f}'.format(original_price) }}</div>
    </div>
    {% endif %}
    {% if rating is not none %}
    <div class="info-card">
      <span class="source-tag scraped">抓取</span>
      <div class="label">评分</div>
      <div class="value rating">★ {{ '{:.1f}'.format(rating) }}</div>
      {% if deltas.get('rating') %}
      <div class="delta {{ deltas.rating[0] }}">{{ deltas.rating[1] }}</div>
      {% endif %}
    </div>
    {% endif %}
    {% if review_count is not none %}
    <div class="info-card">
      <span class="source-tag scraped">抓取</span>
      <div class="label">评论数</div>
      <div class="value">{{ '{:,}'.format(review_count) }}</div>
      {% if deltas.get('reviews') %}
      <div class="delta {{ deltas.reviews[0] }}">{{ deltas.reviews[1] }}</div>
      {% endif %}
    </div>
    {% endif %}
    {% if answered_questions is not none %}
    <div class="info-card">
      <span class="source-tag scraped">抓取</span>
      <div class="label">Q&A 数量</div>
      <div class="value">{{ answered_questions }}</div>
    </div>
    {% endif %}
    {% if bsr_short %}
    <div class="info-card">
      <span class="source-tag scraped">抓取</span>
      <div class="label">BSR 排名</div>
      <div class="value blue">{{ bsr_short }}</div>
      {% if deltas.get('bsr') %}
      <div class="delta {{ deltas.bsr[0] }}">{{ deltas.bsr[1] }}</div>
      {% endif %}
    </div>
    {% endif %}
  </div>

  <div class="info-grid">
    {% if sold_by %}
    <div class="info-card">
      <span class="source-tag scraped">抓取</span>
      <div class="label">卖家</div>
      <div class="value" style="font-size:.85rem;">{{ sold_by[:40] }}</div>
    </div>
    {% endif %}
    {% if coupon_text %}
    <div class="info-card">
      <span class="source-tag scraped">抓取</span>
      <div class="label">优惠券</div>
      <div class="value" style="color:#b45309;">{{ coupon_text[:40] }}</div>
    </div>
    {% endif %}
    {% if availability %}
    <div class="info-card">
      <span class="source-tag scraped">抓取</span>
      <div class="label">可用性</div>
      <div class="value" style="font-size:.8rem;">{{ availability[:50] }}</div>
    </div>
    {% endif %}
    {% if date_first_available %}
    <div class="info-card">
      <span class="source-tag scraped">抓取</span>
      <div class="label">上架日期</div>
      <div class="value" style="font-size:.8rem;">{{ date_first_available }}</div>
    </div>
    {% endif %}
    {% if category %}
    <div class="info-card">
      <span class="source-tag scraped">抓取</span>
      <div class="label">类目</div>
      <div class="value" style="font-size:.72rem;">{{ category[:80] }}</div>
    </div>
    {% endif %}
  </div>

  <!-- ═══════ Card Group 2: Derived Metrics ═══════ -->
  <div class="section-label">🧮 衍生估算数据 <span style="font-weight:400;text-transform:none;letter-spacing:0;">（基于算法推算，非 Amazon 官方数据）</span></div>
  <div class="info-grid">
    {% if est_monthly_sales is not none %}
    <div class="info-card">
      <span class="source-tag derived">估算</span>
      <div class="label">预估月销 ⓘ <span style="font-weight:400;font-size:.6rem;">(BSR 换算)</span></div>
      <div class="value blue">{{ '{:,}'.format(est_monthly_sales) }}</div>
    </div>
    {% endif %}
    {% if review_velocity is not none %}
    <div class="info-card">
      <span class="source-tag derived">估算</span>
      <div class="label">日增评论 ⓘ <span style="font-weight:400;font-size:.6rem;">(评论/天数)</span></div>
      <div class="value purple">{{ review_velocity }}</div>
    </div>
    {% endif %}
  </div>

  <!-- ── Price chart ── -->
  <div class="panel">
    <h2>📈 价格走势</h2>
    <div class="sub">{{ history|length }} 次历史记录</div>
    {% if history|length >= 2 %}
    <canvas id="priceChart" height="200"></canvas>
    {% else %}
    <div class="empty-hint">
      <div class="icon">📊</div>
      <p>仅 {{ history|length }} 次采集记录，暂无法生成价格走势图</p>
      <p style="font-size:.75rem;">点击上方 <strong>🔄 重新采集</strong> 按钮再次采集，积累 2 次以上即可查看价格走势</p>
    </div>
    {% endif %}
  </div>

  <!-- ── History table ── -->
  {% if history %}
  <div class="panel">
    <h2>📋 历史记录</h2>
    <table class="price-table">
      <thead><tr><th>采集时间</th><th>价格</th><th>BSR</th><th>评论数</th><th>预估月销</th></tr></thead>
      <tbody>
      {% for h in history %}
      <tr>
        <td>{{ h.scraped_at[:16] }}</td>
        <td>{% if h.price is not none %}${{ '{:,.2f}'.format(h.price) }}{% else %}<span class="na">无数据</span>{% endif %}</td>
        <td>{{ h.bsr or '-' }}</td>
        <td>{% if h.review_count is not none %}{{ '{:,}'.format(h.review_count) }}{% else %}<span class="na">未采集</span>{% endif %}</td>
        <td>{% if h.est_sales is not none %}{{ '{:,}'.format(h.est_sales) }}{% else %}-{% endif %}</td>
      </tr>
      {% endfor %}
      </tbody>
    </table>
  </div>
  {% endif %}

  <!-- ── Bottom navigation ── -->
  <div class="bottom-nav">
    {% if prev_asin %}
    <a href="/product/{{ prev_asin }}?kw={{ kw }}">← 上一款</a>
    {% endif %}

    {% if next_asin %}
    <a href="/product/{{ next_asin }}?kw={{ kw }}">下一款 →</a>
    {% endif %}
  </div>

</div>

<script>
function copyText(text, btn) {
  navigator.clipboard.writeText(text).then(() => {
    btn.classList.add('copied');
    btn.textContent = '✓ 已复制';
    setTimeout(() => { btn.classList.remove('copied'); btn.textContent = btn.dataset.orig || btn.textContent; }, 1500);
  }).catch(() => {
    // fallback
    const ta = document.createElement('textarea');
    ta.value = text; ta.style.position = 'fixed'; ta.style.left = '-9999px';
    document.body.appendChild(ta); ta.select();
    document.execCommand('copy'); document.body.removeChild(ta);
    btn.classList.add('copied');
    btn.textContent = '✓ 已复制';
    setTimeout(() => { btn.classList.remove('copied'); btn.textContent = btn.dataset.orig || btn.textContent; }, 1500);
  });
}
// Store original button text for restore
document.querySelectorAll('.copy-btn').forEach(btn => {
  btn.dataset.orig = btn.textContent;
  btn.addEventListener('click', function() {
    // restore is handled in copyText via setTimeout
  });
});

function copySummary() {
  var lines = [
    'ASIN: {{ asin }}',
    '商品: {{ title|replace("'", "\\'") }}',
    {% if brand %}'品牌: {{ brand }}',{% endif %}
    {% if price is not none %}'价格: ${{ '{:,.2f}'.format(price) }}',{% endif %}
    {% if rating is not none %}'评分: {{ '{:.1f}'.format(rating) }} / 5',{% endif %}
    {% if review_count is not none %}'评论数: {{ '{:,}'.format(review_count) }}',{% endif %}
    {% if bsr_short %}'BSR: {{ bsr_short }}',{% endif %}
    {% if est_monthly_sales is not none %}'预估月销: {{ '{:,}'.format(est_monthly_sales) }}',{% endif %}
    {% if review_velocity is not none %}'日增评论: {{ review_velocity }}',{% endif %}
    {% if is_prime == 'Yes' %}'Prime: 支持',{% endif %}
    {% if fulfillment_type %}'配送: {{ fulfillment_type }}',{% endif %}
    '链接: https://www.amazon.com/dp/{{ asin }}'
  ];
  navigator.clipboard.writeText(lines.join('\\n')).then(() => {
    var btn = event.target;
    btn.textContent = '✓ 复制成功';
    btn.style.borderColor = 'var(--green)';
    btn.style.color = 'var(--green)';
    btn.style.background = '#d1fae5';
    setTimeout(() => {
      btn.textContent = '📋 复制数据';
      btn.style.borderColor = 'var(--accent)';
      btn.style.color = 'var(--accent)';
      btn.style.background = '';
    }, 1500);
  }).catch(() => {
    var ta = document.createElement('textarea');
    ta.value = lines.join('\\n'); ta.style.position = 'fixed'; ta.style.left = '-9999px';
    document.body.appendChild(ta); ta.select();
    document.execCommand('copy'); document.body.removeChild(ta);
    event.target.textContent = '✓ 复制成功';
    setTimeout(() => { event.target.textContent = '📋 复制数据'; }, 1500);
  });
}

// ── Crawl trigger ────────────────────────────────────────────────────
let crawlTimer = null;
// Snapshot current data before crawl for comparison
var _snap = {
  price: {{ price if price is not none else 'null' }},
  bsr: "{{ bsr_short }}",
  review_count: {{ review_count if review_count is not none else 'null' }},
  rating: {{ rating if rating is not none else 'null' }},
};

function showToast(msg, type) {
  var t = document.getElementById('crawl-toast');
  var spinner = document.getElementById('toast-spinner');
  t.className = 'crawl-toast ' + type;
  document.getElementById('crawl-msg').textContent = msg;
  spinner.style.display = (type === 'running') ? '' : 'none';
  t.style.display = 'flex';
}

function hideToast() {
  document.getElementById('crawl-toast').style.display = 'none';
  if (crawlTimer) { clearInterval(crawlTimer); crawlTimer = null; }
}

async function triggerCrawl(asin) {
  var btn = document.getElementById('crawl-btn');
  btn.disabled = true;
  btn.textContent = '⏳ 启动中…';
  showToast('采集任务启动中…', 'running');

  try {
    var r = await fetch('/api/crawl', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({asin: asin})
    });
    var d = await r.json();

    if (d.error) {
      showToast(d.error, 'error');
      btn.disabled = false;
      btn.textContent = '🔄 重新采集';
      setTimeout(hideToast, 5000);
      return;
    }

    showToast('正在采集商品数据（约30-60秒）…', 'running');
    btn.textContent = '⏳ 采集中…';
    pollCrawlStatus(d.job_id, btn);
  } catch(e) {
    showToast('网络错误，请重试', 'error');
    btn.disabled = false;
    btn.textContent = '🔄 重新采集';
    setTimeout(hideToast, 4000);
  }
}

function pollCrawlStatus(jobId, btn) {
  crawlTimer = setInterval(async () => {
    try {
      var r = await fetch('/api/crawl-status/' + jobId);
      var d = await r.json();
      if (d.status === 'done') {
        clearInterval(crawlTimer);
        showToast('✓ 采集完成！页面即将刷新…', 'done');
        setTimeout(() => {
          var url = new URL(location.href);
          url.searchParams.set('crawled', '1');
          location.href = url.toString();
        }, 1200);
      } else if (d.status === 'error') {
        clearInterval(crawlTimer);
        showToast('采集失败，请查看终端日志', 'error');
        btn.disabled = false;
        btn.textContent = '🔄 重新采集';
        setTimeout(hideToast, 5000);
      }
    } catch(e) {}
  }, 3000);
}

{% if history|length >= 2 %}
const ctx = document.getElementById('priceChart').getContext('2d');
new Chart(ctx, {
  type: 'line',
  data: {
    labels: {{ hist_labels|tojson }},
    datasets: [{
      label: '价格 (USD)',
      data: {{ hist_prices|tojson }},
      borderColor: '#2563eb',
      backgroundColor: 'rgba(37,99,235,0.08)',
      fill: true,
      tension: 0.3,
      pointRadius: 3,
    }]
  },
  options: {
    responsive: true,
    plugins: { legend: { display: false } },
    scales: {
      y: { beginAtZero: false, title: { display: true, text: 'USD' } },
      x: { title: { display: true, text: '采集时间' } }
    }
  }
});
{% endif %}
</script>
</body>
</html>'''


@app.route('/product/<asin>')
def product_detail(asin):
    from datetime import datetime
    from core.metrics import (
        compute_est_monthly_sales, compute_review_velocity, parse_bsr_rank,
    )

    db = get_db()
    kw = request.args.get('kw', '').strip()
    crawled = request.args.get('crawled', '').strip()

    row = db.execute(
        """SELECT * FROM products WHERE asin = ?""", (asin,)
    ).fetchone()

    if not row:
        return render_template_string(
            '''<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
            <title>404 — Amazon Spider</title></head>
            <body style="font-family:sans-serif;text-align:center;padding:80px;
            background:#f0f2f5;"><h1 style="color:#dc2626;">404</h1>
            <p>ASIN 未找到: {{ asin }}</p>
            <a href="/" style="color:#2563eb;">← 返回商品列表</a></body></html>''',
            asin=asin
        ), 404

    # ── Derived metrics ──────────────────────────────────────────────────
    est_sales = compute_est_monthly_sales(row['bsr'])
    review_vel = compute_review_velocity(row['review_count'], row['date_first_available'])
    bsr_rank = parse_bsr_rank(row['bsr'])
    bsr_short = f'BSR #{bsr_rank:,}' if bsr_rank else (row['bsr'] or '')

    # ── Price history ────────────────────────────────────────────────────
    hist = db.execute(
        """SELECT price, bsr, review_count, scraped_at FROM price_history
           WHERE asin = ? ORDER BY scraped_at ASC""", (asin,)
    ).fetchall()

    hist_labels = [h['scraped_at'][:16] for h in hist]
    hist_prices = [h['price'] for h in hist]

    # ── Price delta vs previous crawl ────────────────────────────────────
    price_delta = None
    if len(hist) >= 2:
        prev_p = hist[-2]['price']
        curr_p = hist[-1]['price']
        if prev_p is not None and curr_p is not None:
            price_delta = round(curr_p - prev_p, 2)

    # ── Data freshness ───────────────────────────────────────────────────
    scraped_at = row['scraped_at']
    hours_ago = None
    freshness_text = ''
    if scraped_at:
        try:
            s = str(scraped_at)[:19]
            scraped_dt = datetime.strptime(s, '%Y-%m-%d %H:%M:%S')
            delta = datetime.now() - scraped_dt
            total_secs = int(delta.total_seconds())
            h = total_secs // 3600
            m = (total_secs % 3600) // 60
            hours_ago = h
            if h > 0:
                freshness_text = f'{h}小时{m}分前' if m > 0 else f'{h}小时前'
            else:
                freshness_text = f'{m}分钟前' if m > 0 else '刚刚'
        except (ValueError, TypeError):
            pass

    # ── Per-field deltas vs previous crawl ───────────────────────────────
    deltas = {}
    if len(hist) >= 2:
        prev = hist[-2]
        curr = hist[-1]

        # price delta
        if prev['price'] is not None and curr['price'] is not None:
            d = round(curr['price'] - prev['price'], 2)
            if d > 0.01:
                deltas['price'] = ('up', f'+${d:,.2f}')
            elif d < -0.01:
                deltas['price'] = ('down', f'-${abs(d):,.2f}')
            else:
                deltas['price'] = ('flat', '持平')

        # BSR delta
        prev_bsr = parse_bsr_rank(prev['bsr'])
        curr_bsr = parse_bsr_rank(curr['bsr'])
        if prev_bsr is not None and curr_bsr is not None:
            d = prev_bsr - curr_bsr  # positive = improved (lower rank number)
            if d > 0:
                deltas['bsr'] = ('down', f'↑{d}位 (变好)')
            elif d < 0:
                deltas['bsr'] = ('up', f'↓{abs(d)}位 (变差)')
            else:
                deltas['bsr'] = ('flat', '排名未变')

        # review delta
        if prev['review_count'] is not None and curr['review_count'] is not None:
            d = curr['review_count'] - prev['review_count']
            if d > 0:
                deltas['reviews'] = ('up', f'+{d}')
            elif d < 0:
                deltas['reviews'] = ('down', str(d))
            else:
                deltas['reviews'] = ('flat', '未变')

    # ── Crawl result summary (shown after re-crawl) ─────────────────────
    crawl_result = None
    if crawled == '1' and len(hist) >= 2:
        prev = hist[-2]
        curr = hist[-1]
        changes = []
        has_change = False

        # price
        if prev['price'] is not None and curr['price'] is not None:
            d = round(curr['price'] - prev['price'], 2)
            if abs(d) > 0.01:
                has_change = True
                changes.append({
                    'label': '价格',
                    'text': f"${prev['price']:,.2f} → ${curr['price']:,.2f}",
                    'delta': f"{'+' if d > 0 else ''}${d:,.2f}",
                    'dir': 'up' if d > 0 else 'down',
                })
        # BSR
        prev_bsr_rank = parse_bsr_rank(prev['bsr'])
        curr_bsr_rank = parse_bsr_rank(curr['bsr'])
        if prev_bsr_rank is not None and curr_bsr_rank is not None:
            if prev_bsr_rank != curr_bsr_rank:
                has_change = True
                d = prev_bsr_rank - curr_bsr_rank
                changes.append({
                    'label': 'BSR',
                    'text': f"#{prev_bsr_rank:,} → #{curr_bsr_rank:,}",
                    'delta': f"{'↑' if d > 0 else '↓'}{abs(d)}位",
                    'dir': 'down' if d > 0 else 'up',  # lower rank num = better
                })
        # reviews
        if prev['review_count'] is not None and curr['review_count'] is not None:
            d = curr['review_count'] - prev['review_count']
            if d != 0:
                has_change = True
                changes.append({
                    'label': '评论数',
                    'text': f"{prev['review_count']:,} → {curr['review_count']:,}",
                    'delta': f"{'+' if d > 0 else ''}{d}",
                    'dir': 'up' if d > 0 else 'down',
                })

        crawl_result = {
            'has_change': has_change,
            'changes': changes,
            'record_count': len(hist),
        }

    # ── Prev / Next navigation ───────────────────────────────────────────
    prev_asin = next_asin = None
    if kw:
        siblings = db.execute(
            "SELECT asin FROM products WHERE keyword=? ORDER BY scraped_at DESC",
            (kw,)
        ).fetchall()
        asin_list = [s['asin'] for s in siblings]
        if asin in asin_list:
            idx = asin_list.index(asin)
            if idx > 0:
                prev_asin = asin_list[idx - 1]
            if idx < len(asin_list) - 1:
                next_asin = asin_list[idx + 1]

    # ── History rows with derived metrics ────────────────────────────────
    hist_rows = []
    for h in hist:
        hd = dict(h)
        hd['est_sales'] = compute_est_monthly_sales(h['bsr'])
        hist_rows.append(hd)

    return render_template_string(
        PRODUCT_TEMPLATE,
        asin=asin, kw=kw,
        title=row['title'], price=row['price'],
        image_url=row['image_url'],
        original_price=row['original_price'], rating=row['rating'],
        review_count=row['review_count'], brand=row['brand'],
        category=row['category'], availability=row['availability'],
        is_prime=row['is_prime'], date_first_available=row['date_first_available'],
        bsr=row['bsr'], bsr_short=bsr_short,
        coupon_text=row['coupon_text'], answered_questions=row['answered_questions'],
        variation_count=row['variation_count'], fulfillment_type=row['fulfillment_type'],
        sold_by=row['sold_by'], keyword=row['keyword'],
        est_monthly_sales=est_sales, review_velocity=review_vel,
        price_delta=price_delta,
        scraped_at=scraped_at, hours_ago=hours_ago, freshness_text=freshness_text,
        deltas=deltas,
        crawl_result=crawl_result,
        prev_asin=prev_asin, next_asin=next_asin,
        history=hist_rows, hist_labels=hist_labels, hist_prices=hist_prices,
        hist_rows_json=json.dumps([{
            'price': h['price'], 'review_count': h['review_count'],
            'bsr': h['bsr'],
        } for h in hist_rows]),
    )


@app.route('/dashboard')
def dashboard():
    return render_template_string(DASHBOARD_TEMPLATE)


# ── API routes ───────────────────────────────────────────────────────────────

@app.route('/api/keywords')
def api_keywords():
    db = get_db()
    rows = db.execute(
        "SELECT DISTINCT keyword FROM products WHERE keyword != '' ORDER BY keyword"
    ).fetchall()
    return jsonify({'keywords': [r['keyword'] for r in rows]})


@app.route('/api/products')
def api_products():
    db = get_db()
    kw = request.args.get('kw', '').strip()
    if kw:
        rows = db.execute(
            "SELECT asin, title, brand, price, keyword FROM products WHERE keyword=? ORDER BY scraped_at DESC",
            (kw,)
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT asin, title, brand, price, keyword FROM products ORDER BY scraped_at DESC LIMIT 200"
        ).fetchall()
    return jsonify({'products': [dict(r) for r in rows]})


@app.route('/api/stats')
def api_stats():
    db = get_db()
    kw = request.args.get('kw', '').strip()
    where = "WHERE keyword = ?" if kw else ""
    params = (kw,) if kw else ()
    total = db.execute(
        f"SELECT COUNT(*) FROM products {where}", params
    ).fetchone()[0]
    with_bsr = db.execute(
        f"SELECT COUNT(*) FROM products {where} AND bsr IS NOT NULL", params
    ).fetchone()[0]
    opps = db.execute(
        "SELECT COUNT(*) FROM products WHERE rating >= 4.3 AND review_count <= 50"
    ).fetchone()[0]
    result = {'total': total, 'with_bsr': with_bsr, 'opportunities': opps}
    if kw:
        result['competition_score'] = compute_competition_score(db, kw)
    return jsonify(result)


@app.route('/api/price-history')
def api_price_history():
    db = get_db()
    asin = request.args.get('asin', '').strip()
    if not asin:
        return jsonify({'points': []})
    title_row = db.execute(
        "SELECT title FROM products WHERE asin=?", (asin,)
    ).fetchone()
    rows = db.execute(
        "SELECT price, bsr, scraped_at FROM price_history WHERE asin=? ORDER BY scraped_at ASC",
        (asin,)
    ).fetchall()
    return jsonify({
        'title': title_row['title'] if title_row else asin,
        'points': [{'price': r['price'], 'bsr': r['bsr'], 'time': r['scraped_at'][:16]} for r in rows],
    })


@app.route('/api/bsr-top')
def api_bsr_top():
    db = get_db()
    kw = request.args.get('kw', '').strip()
    if kw:
        rows = db.execute(
            """SELECT asin, title, bsr, price, rating FROM products
               WHERE keyword=? AND bsr IS NOT NULL
               ORDER BY bsr ASC LIMIT 30""", (kw,)
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT asin, title, bsr, price, rating FROM products WHERE bsr IS NOT NULL ORDER BY bsr ASC LIMIT 30"
        ).fetchall()
    ranking = []
    for r in rows:
        d = dict(r)
        d['est_monthly_sales'] = compute_est_monthly_sales(r['bsr'])
        ranking.append(d)
    return jsonify({'ranking': ranking})


@app.route('/api/competitors')
def api_competitors():
    db = get_db()
    kw = request.args.get('kw', '').strip()
    if kw:
        rows = db.execute(
            """SELECT brand, COUNT(*) as count,
                      ROUND(AVG(price), 2) as avg_price,
                      ROUND(AVG(rating), 2) as avg_rating,
                      ROUND(AVG(review_count), 0) as avg_reviews
               FROM products WHERE keyword=? AND brand IS NOT NULL AND brand != ''
               GROUP BY brand HAVING count >= 2
               ORDER BY count DESC LIMIT 10""", (kw,)
        ).fetchall()
    else:
        rows = db.execute(
            """SELECT brand, COUNT(*) as count,
                      ROUND(AVG(price), 2) as avg_price,
                      ROUND(AVG(rating), 2) as avg_rating,
                      ROUND(AVG(review_count), 0) as avg_reviews
               FROM products WHERE brand IS NOT NULL AND brand != ''
               GROUP BY brand HAVING count >= 2
               ORDER BY count DESC LIMIT 10"""
        ).fetchall()
    return jsonify({'brands': [dict(r) for r in rows]})


@app.route('/api/opportunities')
def api_opportunities():
    db = get_db()
    # Pattern 1: 新品黑马 — high rating + low reviews (new product growing fast)
    # Pattern 2: 性价比标杆 — high rating + high reviews + low price
    rows = db.execute(
        """SELECT asin, title, keyword, brand, price, rating, review_count,
                  date_first_available,
                  CASE
                    WHEN rating >= 4.5 AND review_count <= 30 THEN '新品黑马🐴'
                    WHEN rating >= 4.3 AND review_count >= 100 AND price < 50 THEN '性价比标杆💰'
                    WHEN rating >= 4.3 AND review_count <= 80 THEN '潜力新品🌟'
                    ELSE '高评分⭐'
                  END as reason
           FROM products
           WHERE rating >= 4.3 AND price IS NOT NULL
           ORDER BY
             CASE
               WHEN rating >= 4.5 AND review_count <= 30 THEN 0
               WHEN rating >= 4.3 AND review_count >= 100 AND price < 50 THEN 1
               WHEN rating >= 4.3 AND review_count <= 80 THEN 2
               ELSE 3
             END, rating DESC
           LIMIT 15"""
    ).fetchall()
    opportunities = []
    for r in rows:
        d = dict(r)
        d['review_velocity'] = compute_review_velocity(
            r['review_count'], r['date_first_available']
        )
        opportunities.append(d)
    return jsonify({'opportunities': opportunities})


@app.route('/api/price-distribution')
def api_price_distribution():
    """Return product count grouped by price buckets."""
    db = get_db()
    kw = request.args.get('kw', '').strip()

    buckets = [
        (0, 10, '$0-10'),
        (10, 25, '$10-25'),
        (25, 50, '$25-50'),
        (50, 100, '$50-100'),
        (100, 200, '$100-200'),
        (200, None, '$200+'),
    ]

    if kw:
        base_where = "WHERE keyword = ? AND price IS NOT NULL"
        base_params = (kw,)
    else:
        base_where = "WHERE price IS NOT NULL"
        base_params = ()

    distribution = []
    for lo, hi, label in buckets:
        if hi is None:
            clause = "price >= ?"
            p = (lo,)
        else:
            clause = "price >= ? AND price < ?"
            p = (lo, hi)

        sql = f"SELECT COUNT(*) FROM products {base_where} AND {clause}"
        count = db.execute(sql, base_params + p).fetchone()[0]
        distribution.append({
            'range': label,
            'count': count,
            'min': lo,
            'max': hi,
        })

    return jsonify({'keyword': kw or None, 'distribution': distribution})


# ── Crawl trigger ──────────────────────────────────────────────────────────

_crawl_jobs: dict = {}          # job_id → {status, output, started_at}
_crawl_lock = threading.Lock()
_ASIN_COOLDOWN = 60             # single-ASIN: 1 min (only 1 detail page, low risk)
_KEYWORD_COOLDOWN = 180         # keyword: 3 min (search + multi detail, higher risk)
_last_crawl_time: float = 0.0


@app.route('/api/crawl', methods=['POST'])
def api_crawl():
    global _last_crawl_time

    data = request.get_json(silent=True) or {}
    asin = (data.get('asin') or '').strip()
    keyword = (data.get('keyword') or '').strip()

    if not asin and not keyword:
        return jsonify({'error': '请提供 asin 或 keyword'}), 400

    is_asin = bool(asin)
    cooldown = _ASIN_COOLDOWN if is_asin else _KEYWORD_COOLDOWN

    # ── anti-block: enforce cooldown ────────────────────────────────────
    now = datetime.now().timestamp()
    with _crawl_lock:
        elapsed = now - _last_crawl_time
        if elapsed < cooldown:
            wait = int(cooldown - elapsed)
            return jsonify({
                'error': f'防封保护：距上次采集仅 {int(elapsed)} 秒，请等待 {wait} 秒后再试',
                'retry_after': wait,
            }), 429

        # Check no running job
        for jid, j in list(_crawl_jobs.items()):
            if j.get('status') == 'running':
                return jsonify({
                    'error': '防封保护：上一个采集任务仍在运行中，请等待完成',
                }), 429

        _last_crawl_time = now

    job_id = uuid.uuid4().hex[:8]

    # Build scrapy command (respect existing DOWNLOAD_DELAY=5s, CONCURRENT=1)
    cmd = [
        sys.executable, '-m', 'scrapy', 'crawl', 'amazon',
        '-a', 'max_pages=1',
        '-a', 'crawl_detail=1',
        '-a', 'headless=True',
        '-s', 'PROXY_ENABLED=False',
        '-s', 'FEEDS=',
    ]

    if asin:
        cmd.extend(['-a', f'asins={asin}', '-a', 'keyword=web_crawl'])
    elif keyword:
        cmd.extend(['-a', f'keyword={keyword}'])

    def run_crawl() -> None:
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=os.path.dirname(os.path.abspath(__file__)) or '.',
            )
            _crawl_jobs[job_id]['pid'] = proc.pid
            output, _ = proc.communicate(timeout=300)
            _crawl_jobs[job_id]['status'] = 'done' if proc.returncode == 0 else 'error'
            _crawl_jobs[job_id]['output'] = output[-3000:]
        except subprocess.TimeoutExpired:
            _crawl_jobs[job_id]['status'] = 'error'
            _crawl_jobs[job_id]['output'] = '采集超时（>5分钟）'
        except Exception as e:
            _crawl_jobs[job_id]['status'] = 'error'
            _crawl_jobs[job_id]['output'] = str(e)

    _crawl_jobs[job_id] = {
        'status': 'running', 'output': '', 'started_at': datetime.now().isoformat(),
    }
    threading.Thread(target=run_crawl, daemon=True).start()

    return jsonify({'job_id': job_id, 'status': 'running'})


@app.route('/api/crawl-status/<job_id>')
def api_crawl_status(job_id):
    job = _crawl_jobs.get(job_id)
    if not job:
        return jsonify({'error': '任务不存在'}), 404
    return jsonify({
        'job_id': job_id,
        'status': job['status'],
        'output': job.get('output', '')[-1500:],
        'started_at': job.get('started_at'),
    })


# ── Entry point ─────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print(f" Database: {DATABASE}")
    print(f" Open:    http://127.0.0.1:5000")
    app.run(debug=True, host='127.0.0.1', port=5000)
