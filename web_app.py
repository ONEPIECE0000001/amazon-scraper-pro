"""Amazon Spider Web UI — browse scraped product data from SQLite."""

import sqlite3
import os
from urllib.parse import urlencode
from flask import Flask, render_template_string, request, g

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
    --bg: #f0f2f5;
    --card: #fff;
    --text: #1a1a2e;
    --muted: #6b7280;
    --accent: #2563eb;
    --accent-hover: #1d4ed8;
    --green: #059669;
    --yellow: #d97706;
    --red: #dc2626;
    --border: #e5e7eb;
    --shadow: 0 1px 3px rgba(0,0,0,.06), 0 1px 2px rgba(0,0,0,.04);
    --radius: 10px;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
         background: var(--bg); color: var(--text); min-height: 100vh; }

  /* ── header ── */
  .header { background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
            color: #fff; padding: 24px 0; }
  .header-inner { max-width: 1400px; margin: 0 auto; padding: 0 24px;
                  display: flex; align-items: center; justify-content: space-between; }
  .header h1 { font-size: 1.3rem; font-weight: 600; }
  .header .sub { font-size: .78rem; color: #94a3b8; margin-top: 2px; }

  /* ── stats bar ── */
  .statbar { max-width: 1400px; margin: -16px auto 20px; padding: 0 24px;
             display: flex; gap: 12px; flex-wrap: wrap; }
  .statcard { background: var(--card); padding: 14px 20px; border-radius: var(--radius);
              box-shadow: var(--shadow); flex: 1; min-width: 140px; }
  .statcard .val { font-size: 1.5rem; font-weight: 700; }
  .statcard .lbl { font-size: .73rem; color: var(--muted); margin-top: 2px; }
  .val.blue { color: var(--accent); }
  .val.green { color: var(--green); }
  .val.yellow { color: var(--yellow); }

  /* ── main content ── */
  .main { max-width: 1400px; margin: 0 auto; padding: 0 24px 40px; }

  /* ── filters ── */
  .filter-bar { background: var(--card); padding: 16px 20px; border-radius: var(--radius);
                box-shadow: var(--shadow); margin-bottom: 16px;
                display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }
  .filter-bar input, .filter-bar select, .filter-bar button {
    padding: 8px 14px; border: 1px solid var(--border); border-radius: 6px;
    font-size: .83rem; outline: none; }
  .filter-bar input:focus, .filter-bar select:focus { border-color: var(--accent); }
  .filter-bar button { background: var(--accent); color: #fff; border: none;
                       cursor: pointer; font-weight: 500; white-space: nowrap; }
  .filter-bar button:hover { background: var(--accent-hover); }
  .filter-bar input[type=number] { width: 90px; }
  .filter-bar .spacer { flex: 1; }
  .filter-bar .keyword-tag { display: inline-block; background: #dbeafe; color: var(--accent);
    padding: 4px 10px; border-radius: 20px; font-size: .75rem; font-weight: 500;
    cursor: pointer; text-decoration: none; }
  .filter-bar .keyword-tag:hover { background: #bfdbfe; }
  .filter-bar .keyword-tag.active { background: var(--accent); color: #fff; }

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
  .card .meta { display: flex; gap: 16px; flex-wrap: wrap; font-size: .78rem;
                color: var(--muted); }
  .card .meta span { white-space: nowrap; }
  .card .price { font-size: 1.2rem; font-weight: 700; color: var(--red); }
  .card .price.free { color: var(--green); font-size: .9rem; }
  .card .stars { color: #f59e0b; font-weight: 600; }
  .card .prime { color: var(--green); font-weight: 600; font-size: .75rem; }
  .card .tags { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 2px; }
  .card .tag { font-size: .68rem; padding: 2px 8px; border-radius: 4px;
               background: #f1f5f9; color: #475569; white-space: nowrap; }
  .card .tag.brand { background: #fef3c7; color: #92400e; }
  .card .tag.keyword { background: #dbeafe; color: #1e40af; }

  /* ── table (alt view) ── */
  .view-toggle { font-size: .8rem; color: var(--muted); margin-left: auto; }
  .view-toggle a { color: var(--accent); text-decoration: none; margin: 0 4px; }
  .view-toggle a.active { font-weight: 600; color: var(--text); }
  table { width: 100%; border-collapse: collapse; background: var(--card);
          border-radius: var(--radius); overflow: hidden; box-shadow: var(--shadow); }
  th, td { padding: 10px 14px; text-align: left; font-size: .8rem;
           border-bottom: 1px solid var(--border); white-space: nowrap; }
  th { background: #f8fafc; font-weight: 600; color: var(--muted); position: sticky; top: 0; }
  td.title-col { max-width: 300px; overflow: hidden; text-overflow: ellipsis; }
  td.title-col a { color: var(--text); text-decoration: none; }
  td.title-col a:hover { color: var(--accent); }
  img.thumb { width: 40px; height: 40px; object-fit: contain; border-radius: 4px;
              background: #f0f0f0; }

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
</style>
</head>
<body>

<div class="header">
  <div class="header-inner">
    <div>
      <h1>📦 Amazon Spider</h1>
      <div class="sub">商品数据浏览 · 共 {{ total }} 条记录</div>
    </div>
    <div style="font-size:.8rem;color:#94a3b8;">
      DB: {{ dbfile }} &nbsp;|&nbsp;
      <a href="/" style="color:#94a3b8;">🔄 刷新</a>
    </div>
  </div>
</div>

<div class="statbar">
  <div class="statcard"><div class="val blue">{{ total }}</div><div class="lbl">总商品</div></div>
  <div class="statcard"><div class="val green">{{ with_price }}</div><div class="lbl">有价格</div></div>
  <div class="statcard"><div class="val yellow">{{ with_rating }}</div><div class="lbl">有评分</div></div>
  <div class="statcard"><div class="val blue">{{ avg_price }}</div><div class="lbl">均价(USD)</div></div>
  <div class="statcard"><div class="val green">{{ keywords|length }}</div><div class="lbl">关键词数</div></div>
</div>

<div class="main">

  <!-- filter bar -->
  <form class="filter-bar" method="get">
    <input name="q" value="{{ query }}" placeholder="🔍 搜索标题 / ASIN / 品牌 …" style="flex:1; min-width:200px;">
    <input type="number" name="min_price" value="{{ min_price }}" placeholder="最低价">
    <input type="number" name="max_price" value="{{ max_price }}" placeholder="最高价">
    <input type="number" name="min_rating" value="{{ min_rating }}" placeholder="最低评分" step="0.5">
    <button type="submit">筛 选</button>
    {% if query or min_price or max_price or min_rating or cur_kw %}
    <a href="/" style="font-size:.8rem;color:var(--muted);align-self:center;">清除筛选</a>
    {% endif %}

    {% if keywords %}
    <div style="width:100%;display:flex;gap:6px;flex-wrap:wrap;margin-top:4px;">
      <span style="font-size:.75rem;color:var(--muted);align-self:center;">关键词:</span>
      {% for kw in keywords %}
      <a href="?kw={{ kw }}" class="keyword-tag {% if cur_kw == kw %}active{% endif %}">{{ kw }}</a>
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
        <span class="tag" style="background:#fef2f2;color:#991b1b;" title="Best Sellers Rank">📊 BSR: {{ r.bsr[:60] }}</span>
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
    <p style="font-size:.8rem;">数据库路径: {{ dbfile }}</p>
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
                   date_first_available, url, scraped_at, image_url,
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
            'url': row['url'],
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


# ── Entry point ─────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print(f" Database: {DATABASE}")
    print(f" Open:    http://127.0.0.1:5000")
    app.run(debug=True, host='127.0.0.1', port=5000)
