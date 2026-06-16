import pymysql
import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

conn = pymysql.connect(
    host=os.getenv('DB_HOST'),
    user=os.getenv('DB_USER', '').strip(),
    password=os.getenv('DB_PASSWORD', '').strip(),
    database=os.getenv('DB_NAME'),
    port=int(os.getenv('DB_PORT', 3306)),
    charset='utf8mb4'
)
cur = conn.cursor()

# Check existing tables related to blinkit
cur.execute("SHOW TABLES LIKE '%blinkit%'")
tables = cur.fetchall()
print('=== BLINKIT TABLES ===')
for t in tables:
    print(t[0])

print()

# Get schema for each
for (tbl,) in tables:
    cur.execute(f'SHOW CREATE TABLE `{tbl}`')
    row = cur.fetchone()
    print(f'=== {tbl} SCHEMA ===')
    print(row[1])
    print()
    
    cur.execute(f'SELECT COUNT(*) FROM `{tbl}`')
    cnt = cur.fetchone()
    print(f'  ROW COUNT: {cnt[0]}')
    print()

# Also check indexes on blinkit tables
print('=== INDEXES ON BLINKIT TABLES ===')
for (tbl,) in tables:
    cur.execute(f'SHOW INDEX FROM `{tbl}`')
    idxs = cur.fetchall()
    print(f'--- {tbl} indexes ---')
    for idx in idxs:
        print(f"  Key: {idx[2]}, Column: {idx[4]}, Unique: {not bool(idx[1])}")
    print()

# Sample data from blinkit
cur.execute("SELECT COUNT(*) FROM blinkit")
cnt = cur.fetchone()
print(f"blinkit total rows: {cnt[0]}")

cur.execute("SELECT * FROM blinkit LIMIT 3")
rows = cur.fetchall()
cols = [d[0] for d in cur.description]
print(f"Columns: {cols}")
for r in rows:
    print(dict(zip(cols, r)))
print()

# Check blinkit_mapping if exists
try:
    cur.execute("SELECT COUNT(*) FROM blinkit_mapping")
    cnt = cur.fetchone()
    print(f"blinkit_mapping total rows: {cnt[0]}")
    
    cur.execute("SELECT * FROM blinkit_mapping LIMIT 3")
    rows = cur.fetchall()
    cols = [d[0] for d in cur.description]
    print(f"Columns: {cols}")
    for r in rows:
        print(dict(zip(cols, r)))
except Exception as e:
    print(f"blinkit_mapping error: {e}")

print()

# Check distinct categories/subcategories in blinkit
try:
    cur.execute("SELECT DISTINCT category, sub_category FROM blinkit LIMIT 30")
    rows = cur.fetchall()
    print("=== DISTINCT CATEGORIES/SUBCATEGORIES IN BLINKIT ===")
    for r in rows:
        print(f"  Category: {r[0]}, SubCategory: {r[1]}")
except Exception as e:
    print(f"Category query error: {e}")

conn.close()
print("\nDone.")
