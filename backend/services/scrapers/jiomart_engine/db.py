"""
JioMart MySQL Database Module (SQLite dependencies removed)
===========================================================
Single-file module for all database CRUD operations on MySQL.
Uses direct pymysql connections and stores scraper run states locally in JSON.
"""

import os
import json
import pymysql
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from dotenv import load_dotenv

# Load environment variables from backend/.env
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
_env_path = os.path.join(backend_dir, '.env')
load_dotenv(_env_path, override=True)

DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD', '')
DB_HOST = os.getenv('DB_HOST')
DB_PORT = int(os.getenv('DB_PORT', '3306'))
DB_NAME = os.getenv('DB_NAME')

STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jiomart_state.json")

# Module-level lock for thread-safe writes/access to shared state
_db_lock = threading.Lock()


# In-memory cache for resolved categories to avoid redundant queries
_category_cache = {}

def clear_category_cache():
    global _category_cache
    _category_cache.clear()


db_unreachable = False

def is_db_unreachable():
    global db_unreachable
    return db_unreachable

def get_connection():
    """Create a new MySQL connection with optimal settings and automatic retries on transient connection issues."""
    global db_unreachable
    if db_unreachable:
        raise pymysql.err.OperationalError(2003, "Database is flagged as unreachable due to prior connection failures.")

    max_retries = 3
    delay = 1.0
    import time
    for attempt in range(1, max_retries + 1):
        try:
            return pymysql.connect(
                host=DB_HOST,
                user=DB_USER,
                password=DB_PASSWORD,
                database=DB_NAME,
                port=DB_PORT,
                cursorclass=pymysql.cursors.DictCursor,
                connect_timeout=5
            )
        except (pymysql.err.OperationalError, pymysql.err.InterfaceError) as e:
            if attempt == max_retries:
                db_unreachable = True
                print(f"[DB ERROR] MySQL connection failed after {max_retries} attempts. Flagging database as unreachable: {e}", flush=True)
                raise
            print(f"[DB WARNING] Connection attempt {attempt} failed: {e}. Retrying in {delay}s...", flush=True)
            time.sleep(delay)
            delay *= 2


@contextmanager
def transaction():
    """Context manager for thread-safe write transactions."""
    with _db_lock:
        conn = None
        try:
            conn = get_connection()
            yield conn
            conn.commit()
        except Exception:
            if conn:
                try:
                    conn.rollback()
                except Exception as rollback_err:
                    print(f"[DB WARNING] Rollback failed: {rollback_err}", flush=True)
            raise
        finally:
            if conn:
                try:
                    conn.close()
                except Exception as close_err:
                    print(f"[DB WARNING] Connection close failed: {close_err}", flush=True)


@contextmanager
def read_connection():
    """Context manager for read-only queries."""
    conn = None
    try:
        conn = get_connection()
        yield conn
    finally:
        if conn:
            try:
                conn.close()
            except Exception as close_err:
                print(f"[DB WARNING] Read connection close failed: {close_err}", flush=True)


def init_db():
    """No-op for MySQL as tables are managed by Flask migrations, but we check/log connection."""
    conn = None
    try:
        clear_category_cache()
        conn = get_connection()
        print("[DB] MySQL connection verified successfully.")
    except Exception as e:
        print(f"[DB ERROR] MySQL connection failed: {e}", flush=True)
        raise
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Local JSON State Tracking Helpers (Replaces scrape_runs / status SQL tables)
# ---------------------------------------------------------------------------

def _load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"run_id": 0, "status": "completed", "completed_categories": [], "target_categories": []}


def _save_state(state):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        print(f"[ERROR] Failed to save state file: {e}")


def get_last_incomplete_run():
    state = _load_state()
    if state.get("status") in ("running", "failed"):
        return {"id": state["run_id"]}
    return None


def get_pending_categories(run_id):
    state = _load_state()
    if state.get("run_id") == run_id:
        targets = state.get("target_categories", [])
        completed = set(state.get("completed_categories", []))
        return [cat_id for cat_id in targets if cat_id not in completed]
    return []


def create_scrape_run(conn, total_categories):
    state = _load_state()
    new_run_id = state.get("run_id", 0) + 1
    state = {
        "run_id": new_run_id,
        "status": "running",
        "total_categories": total_categories,
        "completed_categories": [],
        "target_categories": []
    }
    _save_state(state)
    return new_run_id


def init_category_scrape_status(conn, run_id, category_ids):
    state = _load_state()
    if state.get("run_id") == run_id:
        state["target_categories"] = list(category_ids)
        state["completed_categories"] = []
        _save_state(state)


def update_category_scrape_status(conn, run_id, category_id, status, pages=0, products=0):
    if status == "completed":
        state = _load_state()
        if state.get("run_id") == run_id:
            completed = state.get("completed_categories", [])
            if category_id not in completed:
                completed.append(category_id)
                state["completed_categories"] = completed
                _save_state(state)


def update_scrape_run(conn, run_id, **kwargs):
    state = _load_state()
    if state.get("run_id") == run_id:
        if "status" in kwargs:
            state["status"] = kwargs["status"]
        _save_state(state)


# ---------------------------------------------------------------------------
# Category CRUD
# ---------------------------------------------------------------------------

def insert_category(conn, cat_id, name, level, parent_id=None, url_slug=None):
    """Insert a category. Uses INSERT IGNORE for idempotency in MySQL."""
    with conn.cursor() as cursor:
        cursor.execute(
            "INSERT IGNORE INTO jiomart_categories (category_id, category_name, category_level, parent_id, slug) VALUES (%s, %s, %s, %s, %s)",
            (cat_id, name, level, parent_id, url_slug)
        )


def get_logical_department(l1_slug, original_name, original_slug):
    """
    Get the logical department name and slug based on L1 category slug.
    This prevents non-grocery categories from falling under 'Groceries'.
    """
    if not l1_slug:
        return original_name, original_slug
    
    l1_slug = l1_slug.lower().strip()
    if l1_slug in ("personal-care", "beauty"):
        return "Beauty & Personal Care", "beauty-personal-care"
    elif l1_slug in ("kitchenware-l1", "tableware-l1"):
        return "Home & Kitchen", "home-kitchen"
    elif l1_slug == "home":
        return "Home Care", "home-care"
    elif l1_slug == "school-office-stationery":
        return "Books & Stationery", "books-stationery"
    
    return original_name, original_slug


def upsert_category(conn, name, level, parent_id=None, url_slug=None):
    """
    Upsert a category dynamically with in-memory caching.
    Guarantees exactly one entry for a given (name, level, parent_id)
    or url_slug, and returns its category ID.
    """
    if not name:
        return None
    name = name.strip()

    # Check in-memory cache first
    cache_key = (name.lower(), level, parent_id, (url_slug or "").lower())
    if cache_key in _category_cache:
        return _category_cache[cache_key]

    with conn.cursor() as cursor:
        # Prevent parent-child same-name redundancy (e.g., Rice -> Rice)
        if parent_id is not None:
            cursor.execute("SELECT category_name FROM jiomart_categories WHERE category_id = %s", (parent_id,))
            parent_row = cursor.fetchone()
            if parent_row and parent_row["category_name"].strip().lower() == name.lower():
                _category_cache[cache_key] = parent_id
                return parent_id

        # Compute category path
        category_path = name
        if parent_id is not None:
            cursor.execute("SELECT category_path FROM jiomart_categories WHERE category_id = %s", (parent_id,))
            parent_row = cursor.fetchone()
            if parent_row and parent_row["category_path"]:
                category_path = parent_row["category_path"] + " > " + name

        row = None
        # 1. First try lookup by slug if available to merge placeholders and API names
        if url_slug:
            if parent_id is not None:
                cursor.execute(
                    "SELECT category_id FROM jiomart_categories WHERE slug = %s AND category_level = %s AND parent_id = %s",
                    (url_slug, level, parent_id)
                )
            else:
                cursor.execute(
                    "SELECT category_id FROM jiomart_categories WHERE slug = %s AND category_level = %s AND parent_id IS NULL",
                    (url_slug, level)
                )
            row = cursor.fetchone()
            if row:
                # Update name and path to match the latest/official name
                cursor.execute(
                    "UPDATE jiomart_categories SET category_name = %s, category_path = %s WHERE category_id = %s",
                    (name, category_path, row["category_id"])
                )

        # 2. Fall back to name-based lookup
        if not row:
            if parent_id is not None:
                cursor.execute(
                    "SELECT category_id FROM jiomart_categories WHERE LOWER(category_name) = LOWER(%s) AND category_level = %s AND parent_id = %s",
                    (name, level, parent_id)
                )
            else:
                cursor.execute(
                    "SELECT category_id FROM jiomart_categories WHERE LOWER(category_name) = LOWER(%s) AND category_level = %s AND parent_id IS NULL",
                    (name, level)
                )
            row = cursor.fetchone()
            if row:
                cursor.execute(
                    "UPDATE jiomart_categories SET slug = COALESCE(slug, %s), category_path = %s WHERE category_id = %s",
                    (url_slug, category_path, row["category_id"])
                )

        if row:
            cat_id = row["category_id"]
        else:
            cursor.execute(
                "INSERT INTO jiomart_categories (category_name, category_level, parent_id, slug, category_path) VALUES (%s, %s, %s, %s, %s)",
                (name, level, parent_id, url_slug, category_path)
            )
            cat_id = cursor.lastrowid

        # Cache the resolved ID
        _category_cache[cache_key] = cat_id
        return cat_id


def get_all_categories(level=None):
    """Get categories, optionally filtered by level."""
    with read_connection() as conn:
        with conn.cursor() as cursor:
            if level is not None:
                cursor.execute(
                    "SELECT * FROM jiomart_categories WHERE category_level = %s ORDER BY category_id", (level,)
                )
            else:
                cursor.execute("SELECT * FROM jiomart_categories ORDER BY category_level, category_id")
            rows = cursor.fetchall()
    return rows


def get_scrape_target_categories():
    """
    Get L2-level categories that have URL slugs for scraping.
    Returns list of dicts with full hierarchy info.
    """
    with read_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT
                    l2.category_id      AS l2_id,
                    l2.category_name    AS l2_name,
                    l2.slug             AS l2_slug,
                    l1.category_id      AS l1_id,
                    l1.category_name    AS l1_name,
                    l1.slug             AS l1_slug,
                    main.category_id    AS main_id,
                    main.category_name  AS main_name,
                    main.slug           AS main_slug
                FROM jiomart_categories l2
                JOIN jiomart_categories l1   ON l2.parent_id = l1.category_id AND l1.category_level = 1
                JOIN jiomart_categories main ON l1.parent_id = main.category_id AND main.category_level = 0
                WHERE l2.category_level = 2 AND l2.slug IS NOT NULL
                ORDER BY main.category_id, l1.category_id, l2.category_id
            """)
            rows = cursor.fetchall()
    return rows


# ---------------------------------------------------------------------------
# Product CRUD
# ---------------------------------------------------------------------------

def upsert_products(conn, products, run_id=None):
    """
    Batch upsert products in MySQL. Returns (new_count, updated_count).
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    new_count = 0
    updated_count = 0

    with conn.cursor() as cursor:
        for p in products:
            sku_id = str(p.get("sku_id", "")).strip()
            if not sku_id:
                continue

            category_ids = p.get("category_ids") or []
            deepest_id = None

            if p.get("hierarchy"):
                hierarchy = p["hierarchy"] or {}
                
                l1_slug = hierarchy.get("l1_category", {}).get("slug")
                dept_name = hierarchy.get("department", {}).get("name")
                dept_slug = hierarchy.get("department", {}).get("slug")
                dept_name, dept_slug = get_logical_department(l1_slug, dept_name, dept_slug)
                d_id = upsert_category(conn, dept_name, 0, None, dept_slug) if dept_name else None
                
                l1_name = hierarchy.get("l1_category", {}).get("name")
                l1_id = upsert_category(conn, l1_name, 1, d_id, l1_slug) if l1_name and d_id else None
                
                l2_name = hierarchy.get("l2_category", {}).get("name")
                l2_slug = hierarchy.get("l2_category", {}).get("slug")
                l2_id = upsert_category(conn, l2_name, 2, l1_id, l2_slug) if l2_name and l1_id else None
                
                l3_name = hierarchy.get("l3_category", {}).get("name")
                l3_slug = hierarchy.get("l3_category", {}).get("slug")
                l3_id = upsert_category(conn, l3_name, 3, l2_id, l3_slug) if l3_name and l2_id else None
                
                deepest_id = l3_id or l2_id or l1_id or d_id or p.get("fallback_l2_id")
            elif p.get("fallback_l2_id"):
                deepest_id = p["fallback_l2_id"]

            # Query existing product by sku_id
            cursor.execute("SELECT id FROM jiomart_products WHERE sku_id = %s", (sku_id,))
            row = cursor.fetchone()

            if row:
                prod_id = row["id"]
                # Update product details
                cursor.execute(
                    """UPDATE jiomart_products 
                       SET product_name = %s,
                           product_url = COALESCE(%s, product_url),
                           mrp = %s, price = %s, 
                           brand = COALESCE(%s, brand),
                           category_id = COALESCE(%s, category_id),
                           quantity = COALESCE(%s, quantity),
                           size = COALESCE(%s, size),
                           image_url = COALESCE(%s, image_url),
                           last_seen_at = %s
                       WHERE id = %s""",
                    (
                        p.get("product_name"),
                        p.get("product_url"),
                        p.get("mrp"),
                        p.get("selling_price"),
                        p.get("brand"),
                        deepest_id,
                        p.get("quantity"),
                        p.get("size"),
                        p.get("image_url"),
                        now,
                        prod_id
                    )
                )
                updated_count += 1
            else:
                # Insert new product
                cursor.execute(
                    """INSERT INTO jiomart_products 
                       (sku_id, product_name, product_url, mrp, price, brand, category_id, quantity, size, image_url, first_seen_at, last_seen_at)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (
                        sku_id,
                        p.get("product_name"),
                        p.get("product_url"),
                        p.get("mrp"),
                        p.get("selling_price"),
                        p.get("brand"),
                        deepest_id,
                        p.get("quantity"),
                        p.get("size"),
                        p.get("image_url"),
                        now, now
                    )
                )
                new_count += 1

    return new_count, updated_count


def get_product_count():
    """Get total unique product count."""
    with read_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) as cnt FROM jiomart_products")
            row = cursor.fetchone()
    return row["cnt"] if row else 0


# ---------------------------------------------------------------------------
# Scraper Task Status Direct Updater
# ---------------------------------------------------------------------------

def update_task_progress(task_id, progress, status, total_leads):
    """Update progress and status directly in the MySQL scraper_tasks table."""
    global db_unreachable
    if db_unreachable:
        return
    conn = None
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                "UPDATE scraper_tasks SET progress = %s, status = %s, total_leads = %s WHERE id = %s",
                (progress, status, total_leads, task_id)
            )
        conn.commit()
        print(f"[TASK STATUS] Task ID {task_id}: {progress}% | {status} | Leads: {total_leads}", flush=True)
    except Exception as e:
        print(f"[DB ERROR] Failed to update task status in MySQL: {e}", flush=True)
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass

def check_should_stop(task_id):
    """Check if the stop signal has been sent for this task."""
    global db_unreachable
    if db_unreachable:
        return False
    if not task_id:
        return False
    conn = None
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT should_stop FROM scraper_tasks WHERE id = %s", (task_id,))
            row = cursor.fetchone()
        return bool(row and row.get("should_stop"))
    except Exception as e:
        print(f"[DB ERROR] Failed to check stop signal for task {task_id}: {e}", flush=True)
        return False
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass

