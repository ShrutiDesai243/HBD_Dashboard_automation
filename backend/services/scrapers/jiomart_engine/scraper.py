"""
JioMart Product Scraper — SQLite-Backed, Automation-Ready
==========================================================
Scrapes products from JioMart's Vertex API, stores in SQLite with
zero-duplicate guarantee (UNIQUE constraint on sku_id).

Features:
- Dynamic category loading from SQLite (no hardcoded JSON dependency)
- Upsert semantics: new products INSERT, existing ones UPDATE price + last_seen
- Run tracking with per-category progress (supports resume)
- Thread-safe writes with DB-level locking
- Configurable concurrency and throttling

Usage:
    python scraper.py              # Scrape all categories
    python scraper.py 5            # Scrape first 5 categories (testing)
    python scraper.py --resume     # Resume last incomplete run
"""

import os
import sys
import time
import random
import requests
import json
import re
import threading
from urllib.parse import urlparse, parse_qs
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

# Fix Windows console encoding issues
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Ensure all prints are flushed immediately
import builtins
def print(*args, **kwargs):
    kwargs.setdefault('flush', True)
    builtins.print(*args, **kwargs)


# Ensure the scraper can import its local db module when run as a sub-module
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import db

# ---------------------------------------------------------------------------
# API Configuration
# ---------------------------------------------------------------------------
API_URL = "https://www.jiomart.com/ext/vertex/application/api/v1.0/products"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "authorization": "Bearer Njg1OTQ1ZjQ2YzhjN2FlZTNmM2FmNjA1OlRwS3c3d0Q5aA==",
    "x-location-detail": '{"country":"INDIA","country_iso_code":"IN","city":"MUMBAI","pincode":"400001","state":"MAHARASHTRA"}',
    "x-geolocation": '{"latitude":"18.9385352","longitude":"72.836334","polygon_ids":["T6HZ_QC_5475bdd9"]}',
    "x-currency-code": "INR",
    "accept": "application/json, text/plain, */*"
}

COOKIES = {
    "app_location_details": "%7B%22country%22%3A%22INDIA%22%2C%22country_iso_code%22%3A%22IN%22%2C%22city%22%3A%22MUMBAI%22%2C%22pincode%22%3A%22400001%22%2C%22state%22%3A%22MAHARASHTRA%22%7D",
    "app_geolocation": "%7B%22latitude%22%3A%2218.9385352%22%2C%22longitude%22%3A%2272.836334%22%2C%22polygon_ids%22%3A%5B%22T6HZ_QC_5475bdd9%22%5D%7D"
}

# ---------------------------------------------------------------------------
# Concurrency Settings
# ---------------------------------------------------------------------------
MAX_WORKERS = 8
PAGE_SIZE = 100
MAX_PAGES_PER_CATEGORY = 500
MAX_RETRIES = 3

# ---------------------------------------------------------------------------
# Thread-safe counters
# ---------------------------------------------------------------------------
progress_lock = threading.Lock()
completed_categories = 0
success_categories = 0
total_new = 0
total_updated = 0
task_id = None


def fetch_api_page(filter_val, page_no):
    """Fetch a single page of products from the Vertex API."""
    params = {
        "f": filter_val,
        "page_id": "*",
        "page_no": str(page_no),
        "page_type": "number",
        "page_size": str(PAGE_SIZE),
        "sort_on": "popular"
    }

    for attempt in range(MAX_RETRIES):
        try:
            r = requests.get(API_URL, params=params, headers=HEADERS, cookies=COOKIES, timeout=15)
            if r.status_code == 200:
                return r.json()
            elif r.status_code == 500:
                return None  # End of pages
            else:
                time.sleep(random.uniform(1.0, 2.0))
        except Exception:
            time.sleep(random.uniform(1.0, 2.0))

    return None


def parse_quantity_and_size(name):
    """
    Extract quantity (pack size) and size (weight/volume/dimensions) from product name.
    """
    if not name:
        return "1", None
    name_lower = name.lower()
    
    # 1. Quantity / Pack Size
    # e.g., "4 x 100 g" or "4x100g"
    mult_match = re.search(r'\b(\d+)\s*x\s*\d+(?:\.\d+)?\s*(?:g|gm|gram|ml|l|kg)\b', name_lower)
    if mult_match:
        qty = mult_match.group(1)
    else:
        # e.g., "pack of 3", "combo pack of 4", "box of 5"
        qty_match = re.search(r'\b(?:pack|pk|pkg|box|set|combo|bag)\s*(?:of)?\s*(\d+)\b', name_lower)
        if qty_match:
            qty = qty_match.group(1)
        else:
            # e.g., "3 pack", "4 pcs", "14 pcs"
            qty_match2 = re.search(r'\b(\d+)\s*(?:pcs|pieces|pack|pk|balls|items)\b', name_lower)
            if qty_match2:
                qty = qty_match2.group(1)
            else:
                qty = "1"

    # 2. Size (weight/volume/dimensions)
    size_pattern = r'\b(\d+(?:\.\d+)?\s*(?:kg|g|gm|gram|grams|ml|l|ltr|litre|litres|inch|inches|cm|mm|oz|mtr|meters|mtrs))\b'
    size_matches = re.findall(size_pattern, name_lower)
    
    if size_matches:
        unique_sizes = []
        for m in size_matches:
            idx = name_lower.find(m)
            if idx != -1:
                orig = name[idx:idx+len(m)].strip()
                if orig not in unique_sizes:
                    unique_sizes.append(orig)
            else:
                unique_sizes.append(m.strip())
        size = ", ".join(unique_sizes)
    else:
        size = None
        
    return qty, size


def build_filter_string(target):
    """
    Build the API 'f' filter parameter from a scrape target dict.
    target has: main_slug, l1_slug, l2_slug
    """
    parts = []
    # For Vertex API queries, the department parameter must always be 'groceries'
    if target.get("main_slug"):
        parts.append("department:groceries")
    if target.get("l1_slug"):
        parts.append(f"l1_category:{target['l1_slug']}")
    if target.get("l2_slug"):
        parts.append(f"l2_category:{target['l2_slug']}")
    parts.append("journey:standard")
    return ":::".join(parts)


def load_targets_from_json():
    """Load target categories dynamically from all_jiomart_categories.json."""
    filepath = os.path.join(os.path.dirname(os.path.abspath(__file__)), "all_jiomart_categories.json")
    if not os.path.exists(filepath):
        print(f"[ERROR] Category JSON file not found: {filepath}")
        return []

    with open(filepath, "r", encoding="utf-8") as f:
        categories = json.load(f)

    targets = []
    for cat in categories:
        url = cat.get("url", "")
        # Parse query parameters from URL
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        dept_slug = qs.get("department", [""])[0]
        l1_slug = qs.get("l1_category", [""])[0]
        l2_slug = qs.get("l2_category", [""])[0]

        if not l2_slug:
            continue

        targets.append({
            "main_slug": dept_slug,
            "l1_slug": l1_slug,
            "l2_slug": l2_slug,
            "main_name": cat.get("department_name", "Groceries"),
            "l1_name": l1_slug.replace("-l1", "").replace("-", " ").title(),
            "l2_name": cat.get("category_name", "")
        })
    return targets


def worker_task(args):
    """Worker function to scrape a single category."""
    global completed_categories, success_categories, total_new, total_updated, task_id

    try:
        target, run_id, total_categories_count = args

        dept_display = target["main_name"]
        l1_display = target["l1_name"]
        cat_display = target["l2_name"]
        cat_id = target["l2_id"]

        if db.is_db_unreachable():
            print(f"[HALT] Database is unreachable. Skipping category: {cat_display}", flush=True)
            with progress_lock:
                completed_categories += 1
            return

        if task_id and db.check_should_stop(task_id):
            print(f"[HALT] Stop signal active. Skipping category: {cat_display}", flush=True)
            with progress_lock:
                completed_categories += 1
            return

        # Update task progress when starting category
        with progress_lock:
            if task_id:
                progress_pct = min(99, int((completed_categories / total_categories_count) * 100))
                db.update_task_progress(
                    task_id,
                    progress_pct,
                    f"Scraping '{cat_display}' ({completed_categories + 1}/{total_categories_count})",
                    total_new + total_updated
                )

        try:
            # Mark category as in_progress
            with db.transaction() as conn:
                db.update_category_scrape_status(conn, run_id, cat_id, "in_progress")
        except Exception as e:
            print(f"[DB ERROR] Failed to initialize category status: {e}", flush=True)
            with progress_lock:
                completed_categories += 1
            return

        # Build filter string from DB slugs
        filter_val = build_filter_string(target)

        if not filter_val or filter_val == "journey:standard":
            print(f"[SKIP] No URL slugs for: {dept_display} > {l1_display} > {cat_display}")
            with db.transaction() as conn:
                db.update_category_scrape_status(conn, run_id, cat_id, "failed")
            with progress_lock:
                completed_categories += 1
            return

        # Crawl page by page
        page_no = 1
        category_new = 0
        category_updated = 0

        while True:
            if db.is_db_unreachable():
                print(f"[HALT] Database is unreachable. Aborting crawl for category: {cat_display}", flush=True)
                break

            if task_id and db.check_should_stop(task_id):
                print(f"[HALT] Stop signal detected during crawl for category: {cat_display}", flush=True)
                break

            time.sleep(random.uniform(0.1, 0.3))

            data = fetch_api_page(filter_val, page_no)
            if not data:
                break

            items = data.get("items", [])
            if not items:
                break

            # Build product batch
            products = []
            for item in items:
                sku_id = str(item.get("item_code") or item.get("sku_code") or "").strip()
                if not sku_id:
                    continue

                slug = item.get("slug")
                product_url = f"https://www.jiomart.com/product/{slug}" if slug else ""

                price_obj = item.get("price", {}) or {}
                mrp = price_obj.get("marked", {}).get("max")
                selling_price = price_obj.get("effective", {}).get("max")

                brand = (item.get("brand", {}) or {}).get("name")

                product_name = item.get("name") or ""
                
                # Resolve variant details (like color/packsize) from API to distinguish same-name items
                variant_details = []
                variants = item.get("variants") or []
                for var_group in variants:
                    var_items = var_group.get("items") or []
                    for v_item in var_items:
                        v_uid = v_item.get("uid")
                        v_identifiers = [str(x.get("identifier")) for x in v_item.get("sizes_with_identifer", [])]
                        if (v_uid and str(v_uid) == str(item.get("uid"))) or (sku_id in v_identifiers):
                            v_val = v_item.get("value")
                            if v_val and v_val.lower() not in product_name.lower():
                                if v_val not in variant_details:
                                    variant_details.append(v_val)
                                    break
                if variant_details:
                    product_name = f"{product_name} ({', '.join(variant_details)})"

                qty, size = parse_quantity_and_size(product_name)

                medias = item.get("medias") or []
                image_url = None
                if medias and isinstance(medias, list):
                    for media in medias:
                        if media.get("type") == "image" and media.get("url"):
                            image_url = media.get("url")
                            break

                products.append({
                    "sku_id": sku_id,
                    "product_name": product_name,
                    "product_url": product_url,
                    "mrp": mrp,
                    "selling_price": selling_price,
                    "brand": brand,
                    "hierarchy": item.get("hierarchy"),
                    "fallback_l2_id": cat_id,
                    "quantity": qty,
                    "size": size,
                    "image_url": image_url,
                })

            # Upsert batch to DB
            if products:
                try:
                    with db.transaction() as conn:
                        new, updated = db.upsert_products(conn, products, run_id)
                        category_new += new
                        category_updated += updated
                    print(f"[DB] Category '{cat_display}' Page {page_no} synced | +{new} New, +{updated} Updated", flush=True)
                except Exception as e:
                    print(f"[DB ERROR] Failed to upsert products for {cat_display}: {e}", flush=True)
                    break

            # Check pagination
            page_obj = data.get("page", {})
            if not page_obj.get("has_next") or page_no >= MAX_PAGES_PER_CATEGORY:
                break

            page_no += 1

        if db.is_db_unreachable():
            return

        # Mark category as completed
        try:
            with db.transaction() as conn:
                db.update_category_scrape_status(
                    conn, run_id, cat_id, "completed",
                    pages=page_no, products=category_new + category_updated
                )
        except Exception as e:
            print(f"[DB ERROR] Failed to finalize category status: {e}", flush=True)
            return

        with progress_lock:
            completed_categories += 1
            success_categories += 1
            total_new += category_new
            total_updated += category_updated
            print(
                f"[{completed_categories}/{total_categories_count}] [OK] "
                f"{dept_display} > {l1_display} > {cat_display} | "
                f"Pages: {page_no} | New: {category_new} | Updated: {category_updated} | "
                f"(Total New: {total_new}, Updated: {total_updated})"
            )
            if task_id:
                progress_pct = min(99, int((completed_categories / total_categories_count) * 100))
                db.update_task_progress(
                    task_id,
                    progress_pct,
                    f"Processed {completed_categories}/{total_categories_count} categories",
                    total_new + total_updated
                )
    except Exception as thread_ex:
        import traceback
        print(f"[THREAD ERROR] Exception in worker thread: {thread_ex}", flush=True)
        traceback.print_exc()
        with progress_lock:
            completed_categories += 1





def main():
    global completed_categories, success_categories, total_new, total_updated, task_id

    import argparse
    parser = argparse.ArgumentParser(description="JioMart Product Scraper — MySQL-Backed")
    parser.add_argument("--task_id", type=int, default=None)
    parser.add_argument("--resume", action="store_true", default=False)
    parser.add_argument("--max_categories", type=int, default=None)
    parser.add_argument("limit", type=int, nargs="?", default=None)
    args = parser.parse_args()

    task_id = args.task_id

    print("=" * 70)
    print("  JioMart Product Scraper — MySQL-Backed")
    print("=" * 70)

    try:
        # Initialize DB
        db.init_db()

        if task_id:
            db.update_task_progress(task_id, 0, "RUNNING", 0)

        # Check for resume mode
        resume_mode = args.resume
        run_id = None
        targets = None

        if resume_mode:
            last_run = db.get_last_incomplete_run()
            if last_run:
                run_id = last_run["id"]
                pending_cat_ids = db.get_pending_categories(run_id)
                print(f"\n[RESUME] Resuming run #{run_id} with {len(pending_cat_ids)} pending categories")

                # Get full target info for pending categories
                all_targets = db.get_scrape_target_categories()
                targets = [t for t in all_targets if t["l2_id"] in pending_cat_ids]
            else:
                print("[RESUME] No incomplete run found. Starting fresh.")
                resume_mode = False

        if not resume_mode:
            # Load targets dynamically from JSON
            targets = load_targets_from_json()

            if not targets:
                print("\n[ERROR] No scrapeable categories found in JSON.")
                if task_id:
                    db.update_task_progress(task_id, 100, "FAILED: No categories found in JSON.", 0)
                return

            # Apply run limit if specified
            run_limit = len(targets)
            if args.max_categories is not None:
                run_limit = min(args.max_categories, len(targets))
            elif args.limit is not None:
                run_limit = min(args.limit, len(targets))

            if run_limit < len(targets):
                print(f"\n[TEST] Limiting to first {run_limit} categories")
                targets = targets[:run_limit]

            # Seed/resolve target categories in DB dynamically to get L2 database IDs
            for t in targets:
                with db.transaction() as conn:
                    dept_name, dept_slug = db.get_logical_department(t["l1_slug"], t["main_name"], t["main_slug"])
                    dept_id = db.upsert_category(conn, dept_name, 0, None, dept_slug)
                    l1_id = db.upsert_category(conn, t["l1_name"], 1, dept_id, t["l1_slug"])
                    l2_id = db.upsert_category(conn, t["l2_name"], 2, l1_id, t["l2_slug"])
                    t["l2_id"] = l2_id

            # Create scrape run
            with db.transaction() as conn:
                run_id = db.create_scrape_run(conn, len(targets))
                db.init_category_scrape_status(conn, run_id, [t["l2_id"] for t in targets])

        total_count = len(targets)
        print(f"\n  Run ID: #{run_id}")
        print(f"  Target categories: {total_count}")
        print(f"  Workers: {MAX_WORKERS}")
        print(f"  Products in MySQL DB before: {db.get_product_count():,}")
        print()

        if total_count == 0:
            print("[INFO] No pending categories to scrape.")
            if task_id:
                db.update_task_progress(task_id, 100, "COMPLETED", 0)
            return

        # Execute
        start_time = time.time()
        worker_args = [(t, run_id, total_count) for t in targets]

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            # Consume the map generator to raise and handle worker thread exceptions in the main thread
            list(executor.map(worker_task, worker_args))

        duration = time.time() - start_time

        # Finalize run
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        status = "completed"
        if task_id and db.check_should_stop(task_id):
            status = "stopped"
            print("\n[SYSTEM] Scraper run aborted by stop signal.", flush=True)

        with db.transaction() as conn:
            db.update_scrape_run(
                conn, run_id,
                finished_at=now,
                status=status,
                completed_categories=success_categories,
                new_products=total_new,
                updated_products=total_updated
            )

        # Summary
        print(f"\n{'=' * 70}")
        if status == "stopped":
            print(f"  Scrape Run #{run_id} Aborted!")
        else:
            print(f"  Scrape Run #{run_id} Complete!")
        print(f"{'=' * 70}")
        print(f"  Categories processed: {success_categories}/{completed_categories}")
        print(f"  New products:         {total_new:,}")
        print(f"  Updated products:     {total_updated:,}")
        print(f"  Total in MySQL now:   {db.get_product_count():,}")
        print(f"  Duration:             {duration:.1f}s ({duration/60:.1f}m)")

        if task_id:
            final_status = "STOPPED" if status == "stopped" else "COMPLETED"
            db.update_task_progress(task_id, 100, final_status, total_new + total_updated)

    except Exception as e:
        import traceback
        traceback.print_exc()
        if task_id and not db.is_db_unreachable():
            try:
                db.update_task_progress(task_id, 100, f"FAILED: {e}", total_new + total_updated)
            except Exception:
                pass
        sys.exit(1)


if __name__ == "__main__":
    main()
