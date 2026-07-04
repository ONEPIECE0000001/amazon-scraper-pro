"""Simple Flask web UI for browsing scraped Amazon product data."""
import sqlite3
import os
from flask import Flask, render_template_string, request, g

DATABASE = os.environ.get('SQLITE_PATH', 'amazon_data.db')

app = Flask(__name__)

# ── HTML template (single-file, no external deps) ─────────────────────────

TEMPLATE = r'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Amazon Spider — 商品数据</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         background: #f5f6fa; color: #2d3436; padding: 20px; }
  h1 { font-size: 1.5rem; margin-bottom: 16px; }
  .stats { display: flex; gap: 16px; margin-bottom: 16px; flex-wrap: wrap; }
  .stat { background: #fff; padding: 12px 20px; border-radius: 8px;
           box-shadow: 0 1px 3px rgba(0,0,0,.08); }
  .stat .num { font-size: 1.4rem; font-weight: 700; color: #0984e3; }
  .stat .lbl { font-size: .75rem; color: #636e72; }
  form { display: flex; gap: 8px; margin-bottom: 16px; flex-wrap: wrap; }
  input, button { padding: 8px 14px; border: 1px solid #dfe6e9; border-radius: 6px;
                  font-size: .85rem; }
  button { background: #0984e3; color: #fff; border: none; cursor: pointer; }
  button:hover { background: #0767b2; }
  table { width: 100%; border-collapse: collapse; background: #fff;
          border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,.08); }
  th, td { padding: 10px 12px; text-align: left; font-size: .82rem;
           border-bottom: 1px solid #f0f0f0; }
  th { background: #f8f9fd; font-weight: 600; color: #636e72; }
  tr:hover { background: #f8f9fd; }
  .price { font-weight: 600; color: #0984e3; }
  .star { color: #f9ca24; }
  .prime { color: #00b894; font-weight: 600; }
  img { width: 60px; height: 60px; object-fit: contain; border-radius: 4px;
        background: #f0f0f0; }
  .empty { text-align: center; padding: 40px; color: #b2bec3; }
  .pager { display: flex; gap: 8px; margin-top: 16px; justify-content: center; }
  .pager a { padding: 6px 12px; background: #fff; border: 1px solid #dfe6e9;
             border-radius: 4px; text-decoration: none; color: #2d3436; font-size: .8rem; }
  .pager a.active { background: #0984e3; color: #fff; border-color: #0984e3; }
  .pager a:hover { border-color: #0984e3; }
</style>
</head>
<body>
<h1>📦 Amazon Spider — 商品数据</h1>

<div class="stats">
  <div class="stat"><div class="num">{{ total }}</div><div class="lbl">总商品数</div></div>
  <div class="stat"><div class="num">{{ with_price }}</div><div class="lbl">有价格</div></div>
  <div class="stat"><div class="num">{{ with_rating }}</div><div class="lbl">有评分</div></div>
  <div class="stat"><div class="num">{{ avg_price }}</div><div class="lbl">均价(USD)</div></div>
</div>

<form method="get">
  <input name="q" value="{{ query }}" placeholder="搜索标题 / ASIN / 品牌 …">
  <input name="min_price" value="{{ min_price }}" placeholder="最低价" style="width:90px">
  <input name="max_price" value="{{ max_price }}" placeholder="最高价" style="width:90px">
  <input name="min_rating" value="{{ min_rating }}" placeholder="最低评分" style="width:90px">
  <button type="submit">筛 选</button>
  <a href="/" style="font-size:.8rem;color:#636e72;align-self:center;margin-left:8px;">清除</a>
</form>

{% if rows %}
<table>
<thead><tr>
  <th></th><th>ASIN</th><th>标题</th><th>价格</th><th>评分</th>
  <th>评论</th><th>品牌</th><th>类目</th><th>Prime</th>
</tr></thead>
<tbody>
{% for r in rows %}
<tr>
  <td>{% if r[13] %}<img src="{{ r[13] }}" loading="lazy">{% endif %}</td>
  <td><a href="{{ r[10] or '#' }}" target="_blank" title="{{ r[0] }}">{{ r[0] }}</a></td>
  <td>{{ r[1][:80] }}{% if r[1]|length > 80 %}…{% endif %}</td>
  <td class="price">{% if r[2] is not none %}${{ '{:,.2f}'.format(r[2]) }}{% endif %}</td>
  <td>{% if r[3] is not none %}<span class="star">★</span> {{ r[3] }}{% endif %}</td>
  <td>{% if r[4] is not none %}{{ r[4] }}{% endif %}</td>
  <td>{{ r[5] or '' }}</td>
  <td>{{ r[6] or '' }}</td>
  <td>{% if r[7] == 'Yes' %}<span class="prime">✓ Prime</span>{% endif %}</td>
</tr>
{% endfor %}
</tbody>
</table>

<div class="pager">
  {% for p in range(1, total_pages + 1) %}
    <a href="?{{ page_qs(p) }}" {% if p == page %}class="active"{% endif %}>{{ p }}</a>
  {% endfor %}
</div>
{% else %}
<div class="empty">没有匹配的商品，换个关键词试试</div>
{% endif %}

</body>
</html>'''


# ── Database helpers ───────────────────────────────────────────────────────

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


def page_qs(p):
    """Build query string for page p preserving all filters."""
    from urllib.parse import urlencode
    args = {}
    for key in ('q', 'min_price', 'max_price', 'min_rating'):
        val = request.args.get(key, '')
        if val:
            args[key] = val
    args['p'] = p
    return urlencode(args)


# ── Routes ─────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    db = get_db()

    # Filters
    q = request.args.get('q', '').strip()
    min_price = request.args.get('min_price', '')
    max_price = request.args.get('max_price', '')
    min_rating = request.args.get('min_rating', '')
    page = int(request.args.get('p', 1))
    per_page = 50

    where = []
    params = []

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

    # Stats (unfiltered, from full table)
    stats = db.execute("""
        SELECT COUNT(*) as total,
               SUM(CASE WHEN price IS NOT NULL THEN 1 ELSE 0 END) as with_price,
               SUM(CASE WHEN rating IS NOT NULL THEN 1 ELSE 0 END) as with_rating,
               ROUND(AVG(price), 2) as avg_price
        FROM products
    """).fetchone()

    total_pages = max(1, (count + per_page - 1) // per_page)
    offset = (page - 1) * per_page

    rows = db.execute(
        f"""SELECT asin, title, price, rating, review_count,
                   brand, category, is_prime, availability,
                   date_first_available, url, description, scraped_at, image_url
            FROM products {where_clause}
            ORDER BY scraped_at DESC
            LIMIT ? OFFSET ?""",
        params + [per_page, offset]
    ).fetchall()

    return render_template_string(
        TEMPLATE,
        rows=rows,
        total=stats['total'],
        with_price=stats['with_price'],
        with_rating=stats['with_rating'],
        avg_price=f"${stats['avg_price']:,.0f}" if stats['avg_price'] else '-',
        query=q,
        min_price=min_price,
        max_price=max_price,
        min_rating=min_rating,
        page=page,
        total_pages=total_pages,
        page_qs=page_qs,
    )


# ── Entry point ────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print(f"Database: {DATABASE}")
    app.run(debug=True, host='127.0.0.1', port=5000)
