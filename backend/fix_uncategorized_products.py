import os
import sys
import time
import re
import sqlite3
import requests
from sqlalchemy import create_engine, text

# Add backend to path
sys.stdout.reconfigure(encoding='utf-8')
backend_dir = os.path.abspath(os.path.dirname(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from config import config

# Connect to MySQL and SQLite
engine = create_engine(config.DATABASE_URI)
sqlite_db_path = os.path.join(backend_dir, "output", "dmart_master.db")

print(f"MySQL Database: {config.DATABASE_URI}")
print(f"SQLite Master DB Path: {sqlite_db_path}")

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
}

def clean_brand_name(brand, name):
    if not brand and name:
        words = name.split()
        if words:
            if len(words) > 1 and words[0].lower() == 'dmart' and words[1].lower() == 'premia':
                brand = "DMart Premia"
            elif len(words) > 1 and words[0].lower() == 'wagh' and words[1].lower() == 'bakri':
                brand = "Wagh Bakri"
            elif len(words) > 1 and words[0].lower() == 'thums' and words[1].lower() == 'up':
                brand = "Thums Up"
            elif len(words) > 1 and words[0].lower() == 'red' and words[1].lower() == 'bull':
                brand = "Red Bull"
            elif len(words) > 1 and words[0].lower() == 'tata' and words[1].lower() in ('tea', 'sampann', 'simply'):
                brand = "Tata"
            else:
                brand = words[0].strip().strip(':').strip('-').strip()
            if brand:
                brand = brand.title()
    return brand

def extract_from_html(html_text, sku):
    extracted = {}
    
    # 1. Image URL extraction from Next.js payload
    sku_pat = rf'\\"skuUniqueID\\"\s*:\s*\\"{sku}\\"'
    match = re.search(sku_pat, html_text)
    if not match:
        sku_pat = rf'"skuUniqueID"\s*:\s*"{sku}"'
        match = re.search(sku_pat, html_text)
        
    pos = match.start() if match else -1
    
    # Search in window if SKU found, otherwise search whole page
    search_area = html_text[max(0, pos - 2000):min(len(html_text), pos + 3000)] if pos != -1 else html_text
    
    img_match = re.search(r'\\"(?:productImageKey|imageKey)\\"\s*:\s*\\"(.*?)\\"', search_area)
    if not img_match:
        img_match = re.search(r'"(?:productImageKey|imageKey)"\s*:\s*"(.*?)"', search_area)
        
    if img_match:
        img_key = img_match.group(1)
        basename = img_key.split('/')[-1]
        extracted['image_url'] = f"https://cdn.dmart.in/images/products/{basename}_5_B.jpg"
    else:
        # Fallback to general search in whole page
        general_img_match = re.search(r'\\"(?:productImageKey|imageKey)\\"\s*:\s*\\"(.*?)\\"', html_text)
        if general_img_match:
            img_key = general_img_match.group(1)
            basename = img_key.split('/')[-1]
            extracted['image_url'] = f"https://cdn.dmart.in/images/products/{basename}_5_B.jpg"
            
    # 2. Category extraction from breadcrumbs list
    bc_match = re.search(r'\\"breadcrumb\\"\s*:\s*\[(.*?)\]', html_text)
    if bc_match:
        bc_content = bc_match.group(1)
        labels = re.findall(r'\\"label\\"\s*:\s*\\"(.*?)\\"', bc_content)
        labels = [l.encode().decode('unicode-escape', errors='ignore').replace('&amp;', '&') for l in labels]
        labels = [l.replace('\\u0026', '&').replace('\\u0027', "'") for l in labels]
        labels = [l for l in labels if l.lower() not in ('home', 'dmart', 'online shopping', 'online shopping at dmart')]
        if labels:
            extracted['category'] = " > ".join(labels)
            
    # 3. Brand/Manufacturer extraction
    brand_match = re.search(r'\\"manufacturer\\"\s*:\s*\\"(.*?)\\"', html_text)
    if brand_match:
        extracted['brand'] = brand_match.group(1).title()
        
    return extracted

def fix_records():
    # 1. Load SQLite cache
    sqlite_cache = {}
    if os.path.exists(sqlite_db_path):
        try:
            print("Loading product details from SQLite Cache...")
            conn = sqlite3.connect(sqlite_db_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT sku_id, category_name, brand, image_url 
                FROM dmart_product_master
            """)
            for r in cursor.fetchall():
                sku, cat, brand, img = r
                sqlite_cache[sku] = {
                    'category': cat,
                    'brand': brand,
                    'image_url': img
                }
            conn.close()
            print(f"Loaded {len(sqlite_cache)} products from SQLite cache.")
        except Exception as e:
            print(f"Failed to read SQLite database: {e}")
            
    # Open SQLite connection for writing updates
    sqlite_conn = None
    if os.path.exists(sqlite_db_path):
        try:
            sqlite_conn = sqlite3.connect(sqlite_db_path)
            print("Opened SQLite database for writing updates.")
        except Exception as e:
            print(f"Failed to open SQLite database for writing: {e}")

    # 2. Query MySQL problematic products
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT id, ASIN, Product_name, category, Brand, Image_URLs, link 
            FROM dmart_products 
            WHERE category = 'Uncategorized' 
               OR Image_URLs IS NULL 
               OR Image_URLs = '' 
               OR Brand IS NULL 
               OR Brand = ''
        """)).fetchall()
        
        print(f"Found {len(rows)} problematic products in MySQL.")
        
        fixed_count = 0
        for idx, r in enumerate(rows, 1):
            db_id, asin, name, cat, brand, img, link = r
            
            new_cat = cat if cat != 'Uncategorized' else None
            new_brand = brand
            new_img = img
            
            # ── Check SQLite Cache first ──
            if asin in sqlite_cache:
                cache = sqlite_cache[asin]
                if not new_cat and cache.get('category'):
                    new_cat = cache['category']
                if not new_brand and cache.get('brand'):
                    new_brand = cache['brand']
                if not new_img and cache.get('image_url'):
                    new_img = cache['image_url']
                    
            # ── Self-healing brand fallback ──
            if not new_brand:
                new_brand = clean_brand_name(new_brand, name)
                
            # ── Web Scraping Fallback for Category/Image ──
            if (not new_cat or not new_img) and link:
                print(f"[{idx}/{len(rows)}] Fetching PDP for ASIN={asin}: {name}")
                try:
                    time.sleep(0.5)  # Be polite to the server
                    resp = requests.get(link, headers=headers, timeout=10)
                    if resp.status_code == 200:
                        extracted = extract_from_html(resp.text, asin)
                        if not new_cat and extracted.get('category'):
                            new_cat = extracted['category']
                            print(f"  -> Extracted Category: {new_cat}")
                        if not new_img and extracted.get('image_url'):
                            new_img = extracted['image_url']
                            print(f"  -> Extracted Image: {new_img}")
                        if not new_brand and extracted.get('brand'):
                            new_brand = extracted['brand']
                            print(f"  -> Extracted Brand: {new_brand}")
                    else:
                        print(f"  -> Failed status code: {resp.status_code}")
                except Exception as scrap_err:
                    print(f"  -> Request error: {scrap_err}")
                    
            # Double safety default category
            if not new_cat:
                new_cat = 'Uncategorized'
            if not new_brand:
                new_brand = clean_brand_name(None, name) or "Generic"
                
            # ── Update in MySQL ──
            try:
                conn.execute(text("""
                    UPDATE dmart_products 
                    SET category = :cat, Brand = :brand, Image_URLs = :img 
                    WHERE id = :id
                """), {
                    "cat": new_cat,
                    "brand": new_brand,
                    "img": new_img,
                    "id": db_id
                })
                conn.commit()
                fixed_count += 1
            except Exception as update_err:
                print(f"Failed to update row ID={db_id} in MySQL: {update_err}")

            # ── Update in SQLite ──
            if sqlite_conn:
                try:
                    sqlite_conn.execute("""
                        UPDATE dmart_product_master 
                        SET category_name = ?, brand = ?, image_url = ? 
                        WHERE sku_id = ?
                    """, (new_cat if new_cat != 'Uncategorized' else None, new_brand, new_img, asin))
                    sqlite_conn.commit()
                except Exception as sqlite_err:
                    print(f"Failed to update SKU={asin} in SQLite: {sqlite_err}")
                
        print(f"\nRepair complete. Successfully fixed {fixed_count} records in MySQL.")

    if sqlite_conn:
        sqlite_conn.close()
        print("Closed SQLite database.")

if __name__ == "__main__":
    fix_records()
