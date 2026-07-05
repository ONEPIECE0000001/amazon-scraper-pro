"""Amazon Spider Web UI — browse scraped product data from SQLite."""

import sqlite3
import os
from urllib.parse import urlencode
from flask import Flask, render_template_string, request, g, jsonify

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

<!-- page title -->
<div class="page-title-row">
  <h2>商品数据</h2>
  <span class="meta">共 {{ total }} 条记录</span>
</div>

<!-- stats -->
<div class="statbar">
  <div class="statcard">
    <div class="icon blue">🛒</div>
    <div><div class="val blue">{{ total }}</div><div class="lbl">总商品</div></div>
  </div>
  <div class="statcard">
    <div class="icon green">💲</div>
    <div><div class="val green">{{ with_price }}</div><div class="lbl">有价格</div></div>
  </div>
  <div class="statcard">
    <div class="icon yellow">⭐</div>
    <div><div class="val yellow">{{ with_rating }}</div><div class="lbl">有评分</div></div>
  </div>
  <div class="statcard">
    <div class="icon purple">📊</div>
    <div><div class="val purple">{{ avg_price }}</div><div class="lbl">均价 (USD)</div></div>
  </div>
  <div class="statcard">
    <div class="icon red">🔑</div>
    <div><div class="val red">{{ keywords|length }}</div><div class="lbl">关键词数</div></div>
  </div>
</div>

<div class="main">

  <!-- filter bar -->
  <form class="filter-bar" method="get">
    <div class="search-wrap">
      <span class="search-icon">🔍</span>
      <input name="q" value="{{ query }}" placeholder="搜索标题 / ASIN / 品牌 …">
    </div>
    <input type="number" name="min_price" value="{{ min_price }}" placeholder="最低价">
    <input type="number" name="max_price" value="{{ max_price }}" placeholder="最高价">
    <input type="number" name="min_rating" value="{{ min_rating }}" placeholder="最低评分" step="0.5">
    <button type="submit">筛选</button>
    {% if query or min_price or max_price or min_rating or cur_kw %}
    <a href="/"><button type="button" class="ghost">清除</button></a>
    {% endif %}

    {% if keywords %}
    <div class="kw-bar">
      <span class="kw-label">关键词:</span>
      {% for kw in keywords %}
      <a href="?kw={{ kw }}" class="{% if cur_kw == kw %}active{% endif %}">{{ kw }}</a>
      {% endfor %}
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
    return g.db


@app.teardown_appcontext
def close_db(error):
    db = g.pop('db', None)
    if db:
        db.close()


# ── Routes ──────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    db = get_db()

    # Filters
    q = request.args.get('q', '').strip()
    min_price = request.args.get('min_price', '').strip()
    max_price = request.args.get('max_price', '').strip()
    min_rating = request.args.get('min_rating', '').strip()
    cur_kw = request.args.get('kw', '').strip()
    page = int(request.args.get('p', 1))

    where = []
    params = []

    if cur_kw:
        where.append("keyword = ?")
        params.append(cur_kw)

    if q:
        where.append("(title LIKE ? OR asin LIKE ? OR brand LIKE ? OR category LIKE ?)")
        like = f"%{q}%"
        params.extend([like, like, like, like])

    if min_price:
        where.append("price >= ?")
        params.append(float(min_price))
    if max_price:
        where.append("price <= ?")
        params.append(float(max_price))
    if min_rating:
        where.append("rating >= ?")
        params.append(float(min_rating))

    where_clause = ("WHERE " + " AND ".join(where)) if where else ""

    # Count
    count = db.execute(
        f"SELECT COUNT(*) FROM products {where_clause}", params
    ).fetchone()[0]

    # Global stats
    stats = db.execute("""
        SELECT COUNT(*) as total,
               SUM(CASE WHEN price IS NOT NULL THEN 1 ELSE 0 END) as with_price,
               SUM(CASE WHEN rating IS NOT NULL THEN 1 ELSE 0 END) as with_rating,
               ROUND(AVG(price), 2) as avg_price
        FROM products
    """).fetchone()

    # Keyword list
    kws = db.execute(
        "SELECT DISTINCT keyword FROM products WHERE keyword != '' ORDER BY keyword"
    ).fetchall()
    keywords = [row['keyword'] for row in kws]

    total_pages = max(1, (count + PER_PAGE - 1) // PER_PAGE)
    offset = (page - 1) * PER_PAGE

    rows = db.execute(
        f"""SELECT keyword, asin, title, price, rating, review_count,
                   brand, category, is_prime, availability,
                   date_first_available, scraped_at, image_url,
                   bsr, coupon_text, answered_questions, variation_count,
                   fulfillment_type, sold_by
            FROM products {where_clause}
            ORDER BY scraped_at DESC
            LIMIT ? OFFSET ?""",
        params + [PER_PAGE, offset]
    ).fetchall()

    # Convert rows to dicts for easy template access
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

    # Page range for pagination
    page_range = _build_page_range(page, total_pages)

    return render_template_string(
        TEMPLATE,
        rows=product_rows,
        total=stats['total'],
        with_price=stats['with_price'],
        with_rating=stats['with_rating'],
        avg_price=f"${stats['avg_price']:,.0f}" if stats['avg_price'] else '-',
        keywords=keywords,
        cur_kw=cur_kw,
        query=q, min_price=min_price, max_price=max_price, min_rating=min_rating,
        page=page, total_pages=total_pages,
        page_range=page_range,
        page_qs=_page_qs,
        dbfile=DATABASE,
    )


# ── Helpers ─────────────────────────────────────────────────────────────────

def _page_qs(p):
    args = {}
    for key in ('q', 'min_price', 'max_price', 'min_rating', 'kw'):
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
  <select id="kw-select" onchange="loadAll()">
    <option value="">全部</option>
  </select>
  <label>商品:</label>
  <select id="asin-select" onchange="loadPriceHistory()">
    <option value="">选择商品看价格走势…</option>
  </select>
  <button onclick="loadAll()">刷新</button>
</div>

<!-- 价格走势 -->
<div class="panel">
  <h2>📈 价格走势</h2>
  <div class="sub" id="price-sub">选择一个商品查看价格历史</div>
  <canvas id="priceChart" height="200"></canvas>
</div>

<div class="grid-2">
  <!-- BSR 排行 -->
  <div class="panel">
    <h2>🏆 BSR 排行</h2>
    <div class="sub" id="bsr-sub"></div>
    <table><thead><tr><th>#</th><th>商品</th><th>BSR</th><th>价格</th><th>评分</th></tr></thead>
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
let priceChart = null, radarChart = null;
let keywordList = [];
let currentKw = '';

// ── load keyword dropdown ──
async function init() {
  const r = await fetch('/api/keywords');
  const data = await r.json();
  keywordList = data.keywords || [];
  const sel = document.getElementById('kw-select');
  keywordList.forEach(kw => {
    const o = document.createElement('option');
    o.value = kw; o.textContent = kw;
    sel.appendChild(o);
  });
  // Also populate asin dropdown
  await loadAsins();
  loadAll();
}

async function loadAsins() {
  const kw = document.getElementById('kw-select').value;
  const url = kw ? '/api/products?kw=' + encodeURIComponent(kw) : '/api/products';
  const r = await fetch(url);
  const data = await r.json();
  const sel = document.getElementById('asin-select');
  sel.innerHTML = '<option value="">选择商品看价格走势…</option>';
  (data.products || []).forEach(p => {
    const o = document.createElement('option');
    o.value = p.asin;
    o.textContent = (p.brand ? '['+p.brand+'] ' : '') + p.title.slice(0, 60);
    sel.appendChild(o);
  });
}

async function loadAll() {
  currentKw = document.getElementById('kw-select').value;
  await Promise.all([loadAsins(), loadKPIs(), loadBSR(), loadCompetitors(), loadOpportunities()]);
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
async function loadBSR() {
  const kw = currentKw ? '?kw=' + encodeURIComponent(currentKw) : '';
  const r = await fetch('/api/bsr-top' + kw);
  const data = await r.json();
  const rows = data.ranking || [];
  document.getElementById('bsr-sub').textContent =
    (currentKw || '全部关键词') + ' · 共 ' + rows.length + ' 个有BSR商品';
  const tbody = document.getElementById('bsr-tbody');
  tbody.innerHTML = rows.map((r, i) =>
    '<tr><td>' + (i+1) + '</td><td title="' + r.title + '">' +
    r.title.slice(0, 35) + '</td><td>' + r.bsr + '</td><td>$' +
    (r.price||'-') + '</td><td>' + (r.rating ? '★'+r.rating : '-') + '</td></tr>'
  ).join('') || '<tr><td colspan="5">暂无BSR数据</td></tr>';
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
    '<div class="t" title="' + o.title + '">' + o.title.slice(0, 50) + '</div>' +
    '<div style="font-size:.78rem;color:var(--muted);">' +
    '★ ' + (o.rating||'-') + ' · ' + (o.review_count||0) + '评论 · $' +
    (o.price||'-') + '</div>' +
    '<div class="tags">' +
    '<span class="tag gold">' + (o.reason || '机会品') + '</span>' +
    (o.keyword ? '<span class="tag blue">' + o.keyword + '</span>' : '') +
    (o.brand ? '<span class="tag green">' + o.brand + '</span>' : '') +
    '</div></div>'
  ).join('') || '<div style="color:var(--muted);">暂无机会发现</div>';
}

// ── init ──
init();
</script>
</body>
</html>'''


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
            "SELECT asin, title, brand, price FROM products WHERE keyword=? ORDER BY scraped_at DESC",
            (kw,)
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT asin, title, brand, price FROM products ORDER BY scraped_at DESC LIMIT 100"
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
    return jsonify({'total': total, 'with_bsr': with_bsr, 'opportunities': opps})


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
    return jsonify({'ranking': [dict(r) for r in rows]})


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
    return jsonify({'opportunities': [dict(r) for r in rows]})


# ── Entry point ─────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print(f" Database: {DATABASE}")
    print(f" Open:    http://127.0.0.1:5000")
    app.run(debug=True, host='127.0.0.1', port=5000)
