"""Full duplicate audit for JioMart SQLite database."""
import sys, io
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import db

db.init_db()
conn = db.get_connection()

print("=" * 60)
print("  DUPLICATE AUDIT REPORT")
print("=" * 60)

# 1. Duplicate SKUs in products
print("\n[1] PRODUCTS — Duplicate sku_id check")
dupes = conn.execute(
    "SELECT sku_id, COUNT(*) as cnt FROM products GROUP BY sku_id HAVING cnt > 1"
).fetchall()
if dupes:
    print(f"  FAIL: {len(dupes)} duplicate SKUs found!")
    for d in dupes[:10]:
        print(f"    sku_id={d['sku_id']} appears {d['cnt']} times")
else:
    print(f"  PASS: 0 duplicate SKUs")

# 2. Empty/null SKUs
print("\n[2] PRODUCTS — Empty/null sku_id check")
empty = conn.execute(
    "SELECT COUNT(*) as cnt FROM products WHERE sku_id IS NULL OR TRIM(sku_id) = ''"
).fetchone()
print(f"  {'FAIL' if empty['cnt'] > 0 else 'PASS'}: {empty['cnt']} empty/null SKUs")

# 3. Total products
total = conn.execute("SELECT COUNT(*) as cnt FROM products").fetchone()
unique = conn.execute("SELECT COUNT(DISTINCT sku_id) as cnt FROM products").fetchone()
print(f"\n[3] PRODUCTS — Totals")
print(f"  Total rows:      {total['cnt']:,}")
print(f"  Unique sku_ids:  {unique['cnt']:,}")
print(f"  Difference:      {total['cnt'] - unique['cnt']}")

# 4. Duplicate categories (same name + level + parent)
print("\n[4] CATEGORIES — Duplicate check (name + level + parent)")
cat_dupes = conn.execute("""
    SELECT name, level, parent_id, COUNT(*) as cnt 
    FROM categories 
    GROUP BY name, level, parent_id 
    HAVING cnt > 1
""").fetchall()
if cat_dupes:
    print(f"  FAIL: {len(cat_dupes)} duplicate categories!")
    for d in cat_dupes[:10]:
        lvl = {0:'Main', 1:'L1', 2:'L2', 3:'L3'}.get(d['level'], d['level'])
        print(f"    '{d['name']}' (level={lvl}, parent={d['parent_id']}) x{d['cnt']}")
else:
    print(f"  PASS: 0 duplicate categories")

# 5. Duplicate product_categories links
print("\n[5] PRODUCT_CATEGORIES — Duplicate link check")
pc_dupes = conn.execute("""
    SELECT product_id, category_id, COUNT(*) as cnt 
    FROM product_categories 
    GROUP BY product_id, category_id 
    HAVING cnt > 1
""").fetchall()
if pc_dupes:
    print(f"  FAIL: {len(pc_dupes)} duplicate product-category links!")
else:
    print(f"  PASS: 0 duplicate links")

# 6. Category stats
print("\n[6] CATEGORY STATS")
for level, label in [(0,'Main'), (1,'L1'), (2,'L2'), (3,'L3')]:
    cnt = conn.execute("SELECT COUNT(*) as cnt FROM categories WHERE level=?", (level,)).fetchone()
    slug_cnt = conn.execute(
        "SELECT COUNT(*) as cnt FROM categories WHERE level=? AND url_slug IS NOT NULL", (level,)
    ).fetchone()
    print(f"  {label:>4}: {cnt['cnt']:>4} total, {slug_cnt['cnt']:>4} with URL slugs")

# 7. Orphan check
print("\n[7] ORPHAN CHECKS")
orphan_cats = conn.execute("""
    SELECT COUNT(*) as cnt FROM categories c 
    WHERE c.parent_id IS NOT NULL 
    AND c.parent_id NOT IN (SELECT id FROM categories)
""").fetchone()
print(f"  Categories with missing parent: {orphan_cats['cnt']}")

orphan_pc = conn.execute("""
    SELECT COUNT(*) as cnt FROM product_categories pc
    WHERE pc.product_id NOT IN (SELECT id FROM products)
    OR pc.category_id NOT IN (SELECT id FROM categories)
""").fetchone()
print(f"  Product-category links with missing ref: {orphan_pc['cnt']}")

# Summary
print(f"\n{'=' * 60}")
all_pass = (
    len(dupes) == 0 and empty['cnt'] == 0 and 
    len(cat_dupes) == 0 and len(pc_dupes) == 0 and
    orphan_cats['cnt'] == 0 and orphan_pc['cnt'] == 0
)
if all_pass:
    print("  ALL CHECKS PASSED — ZERO DUPLICATES")
else:
    print("  SOME CHECKS FAILED — SEE ABOVE")
print(f"{'=' * 60}")

conn.close()
