"""
BigBasket Scraper Service
=========================
All scraping logic is ported from BB_Scraper/ (scraper.py, parser.py, cleaner.py).
No subprocess calls to the BB_Scraper folder — everything runs natively here.

Usage (CLI):
    python -m services.scrapers.bigbasket_service \
        --category "Fruits & Vegetables" \
        --subcategories "Fruits,Vegetables" \
        --pages 5 \
        --task-id 42
"""

import os
import sys
import re
import time
import random
import csv
import json
import argparse
import datetime
import tempfile
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from app import app
from extensions import db
from model.scraper_task import ScraperTask

# ─── Output directory ────────────────────────────────────────────────────────

OUTPUT_DIR = os.path.abspath(
    os.path.join(tempfile.gettempdir(), 'HBD_Dashboard_automation', 'bigbasket')
)

# ─── Helpers ─────────────────────────────────────────────────────────────────

def make_slug(name: str) -> str:
    """Convert a category/subcategory name to a BigBasket URL slug."""
    s = name.lower()
    s = s.replace('&', ' ')
    s = re.sub(r'[^a-z0-9\s-]', '', s)
    s = re.sub(r'\s+', '-', s)
    s = re.sub(r'-+', '-', s)
    return s.strip('-')


def metadata_path(task_id):
    return os.path.join(OUTPUT_DIR, f'task_{task_id}.json')


def save_task_metadata(task_id, csv_path):
    try:
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        with open(metadata_path(task_id), 'w', encoding='utf-8') as f:
            json.dump({
                'task_id': task_id,
                'csv_path': csv_path,
                'created_at': datetime.datetime.utcnow().isoformat() + 'Z'
            }, f)
    except Exception as exc:
        print(f"[WARN] Failed to write metadata for task {task_id}: {exc}")


# ─── Ported from BB_Scraper/parser.py ────────────────────────────────────────

def _parse_rating_and_review(card_text: str):
    """Parse rating and review count from BigBasket product card text."""
    rating = 0.0
    review = 0

    review_match = re.search(
        r"([0-9][0-9,]*)\s*(?:Ratings?|Rating)", card_text, flags=re.IGNORECASE
    )
    if review_match:
        try:
            review = int(review_match.group(1).replace(',', ''))
        except Exception:
            review = 0

    rating_match = re.search(
        r"([1-5](?:\.[0-9])?)\s*(?:/\s*)?\s*(?:out of\s*5\s*)?(?:Ratings?|Rating)",
        card_text,
        flags=re.IGNORECASE,
    )
    if not rating_match:
        rating_match = re.search(r"\b([1-5](?:\.[0-9])?)\b", card_text)

    if rating_match:
        try:
            rating = float(rating_match.group(1))
        except Exception:
            rating = 0.0

    return rating, review


def parse_raw_html(html: str, main_cat: str, subcat: str) -> list:
    """
    Parse BigBasket category page HTML and return a list of product dicts.
    Ported from BB_Scraper/parser.py::parse_raw_html().
    """
    soup = BeautifulSoup(html, "html.parser")
    products = []
    seen_skus = set()

    for link in soup.find_all("a", href=re.compile(r"/pd/\d+")):
        try:
            href = link.get('href')
            if not href:
                continue

            sku_match = re.search(r"/pd/(\d+)/", href)
            sku = sku_match.group(1) if sku_match else ""
            if not sku or sku in seen_skus:
                continue

            product_url = href
            if product_url.startswith('/'):
                product_url = 'https://www.bigbasket.com' + product_url

            # Find parent card
            card = (
                link.find_parent("div", class_=lambda x: x and ('SKU' in x or 'ProductTemplate' in x))
                or link.find_parent("li")
            )
            if not card:
                parent = link.parent
                for _ in range(5):
                    if parent and (
                        parent.name == "li"
                        or (
                            parent.name == "div"
                            and any(k in str(parent.get('class', [])) for k in ['SKU', 'Product', 'Card', 'Item', 'Template'])
                        )
                    ):
                        card = parent
                        break
                    if parent:
                        parent = parent.parent
            if not card:
                continue

            # Product name
            name_el = card.select_one("h3, h4, [class*='Title'], [class*='name']")
            name = name_el.text.strip() if name_el else ""
            if not name:
                name = link.text.strip()
            if not name:
                continue

            # Prices
            price_text = card.get_text(" ", strip=True)
            prices = re.findall(r"₹\s*([\d,.]+)", price_text)
            clean_prices = [float(p.replace(",", "")) for p in prices if len(p) > 1]

            mrp = max(clean_prices) if clean_prices else 0
            selling_price = min(clean_prices) if clean_prices else 0

            if mrp <= 0 or selling_price <= 0:
                continue
            if not any(p > 0 for p in clean_prices):
                continue

            rating, review = _parse_rating_and_review(price_text)

            seen_skus.add(sku)
            products.append({
                "sku_id": sku,
                "product_name": name,
                "product_url": product_url,
                "rating": rating,
                "review": review,
                "mrp": mrp,
                "selling_price": selling_price,
                "main_category": main_cat,
                "subcategory": subcat,
            })
        except Exception:
            continue

    return products


# ─── Ported from BB_Scraper/scraper.py ───────────────────────────────────────

def scroll_to_bottom(page, max_scrolls=60):
    """Scroll to trigger BigBasket infinite/lazy loading. Stops when stable."""
    def get_product_link_count():
        try:
            return page.eval_on_selector_all("a[href*='/pd/']", "els => els.length")
        except Exception:
            return 0

    last_count = get_product_link_count()
    last_height = page.evaluate("() => document.body.scrollHeight")
    stable_rounds = 0

    for i in range(max_scrolls):
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(random.uniform(2.5, 4.0))

        current_count = get_product_link_count()
        current_height = page.evaluate("() => document.body.scrollHeight")
        print(f"      [Scroll] Step {i+1}: links={current_count}, height={current_height}")

        if current_count == last_count and current_height == last_height:
            stable_rounds += 1
            if stable_rounds >= 6:
                print(f"      [Scroll] Settled at {current_count} product links.")
                break
        else:
            stable_rounds = 0
            last_count = current_count
            last_height = current_height

        if i % 10 == 9:
            page.evaluate("window.scrollBy(0, -800)")
            time.sleep(1)


def _normalize_bb_url(href: str) -> str:
    """Normalize BigBasket category URLs to relative /pc/.../ paths."""
    if not href:
        return ""
    clean = href.split("?", 1)[0]
    if not clean.startswith("/"):
        m = re.search(r"https?://www\.bigbasket\.com(\/.*)", clean)
        if m:
            clean = m.group(1)
    clean = clean.rstrip("/") + "/"
    return clean


def _extract_category_links(page, slug: str) -> list:
    """Extract nested BigBasket category links from the current page."""
    def collect(selector: str):
        locator = page.locator(selector)
        links = locator.all()
        out = []
        for link in links:
            href = link.get_attribute("href")
            norm = _normalize_bb_url(href or "")
            if not norm:
                continue
            if norm not in out:
                out.append(norm)
        return out

    primary = collect(f"a[href*='/pc/{slug}/']")
    if primary:
        return primary
    print(f"    [Discover] No /pc/{slug}/ links found. Falling back to broad /pc/ link discovery...")
    return collect("a[href*='/pc/']")


def _safe_goto(page, url: str, *, timeout_ms: int = 30000) -> bool:
    """Navigate without crashing on slow pages."""
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        return True
    except Exception as e:
        print(f"        [NavWarn] goto timeout/failed for {url}: {e}")
        return False


# ─── Ported from BB_Scraper/cleaner.py ───────────────────────────────────────

def _process_and_deduplicate(all_rows: list) -> list:
    """Deduplicate rows by sku_id. Returns a cleaned list."""
    seen = set()
    result = []
    for row in all_rows:
        sku = str(row.get('sku_id', '')).strip()
        if not sku or not re.match(r'^\d+$', sku):
            continue
        if sku not in seen:
            seen.add(sku)
            result.append(row)
    return result


def save_csv(rows: list, output_path: str):
    """Save rows to CSV file."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    fieldnames = [
        'sku_id', 'product_name', 'product_url',
        'rating', 'review', 'mrp', 'selling_price',
        'main_category', 'subcategory'
    ]
    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)


# ─── Main scraper function ────────────────────────────────────────────────────

def scrape_bigbasket_category(
    category: str,
    subcategories: str = '',
    pages: int = 10,
    task_id: int = None
):
    """
    Full BigBasket category scraper — uses the complete BB_Scraper algorithm.

    Args:
        category:      Main category name e.g. "Fruits & Vegetables"
        subcategories: Optional comma-separated subcategory names e.g. "Fruits,Vegetables"
                       If empty, scraper auto-discovers all subcategories.
        pages:         Max scroll rounds per subcategory page (default 10)
        task_id:       DB task ID to update progress in
    """
    with app.app_context():
        task = None
        if task_id:
            task = db.session.get(ScraperTask, task_id)
            if task:
                task.status = 'RUNNING'
                task.progress = 0
                task.total_found = 0
                db.session.commit()

        os.makedirs(OUTPUT_DIR, exist_ok=True)
        slug = make_slug(category)
        ts = datetime.datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        output_name = f"bigbasket_{slug}_{ts}.csv"
        output_path = os.path.join(OUTPUT_DIR, output_name)

        all_results = []

        try:
            print(f"[TASK] BigBasket task {task_id or 'local'} starting.")
            print(f"[CONFIG] Category: '{category}' | Subcategories: '{subcategories or 'auto-discover'}' | Pages: {pages}")

            # Parse user-supplied subcategories
            user_subcats = []
            if subcategories and subcategories.strip():
                user_subcats = [s.strip() for s in re.split(r'[,\n]+', subcategories) if s.strip()]
                print(f"[CONFIG] User-specified subcategories: {user_subcats}")

            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=False,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--disable-dev-shm-usage",
                        "--no-sandbox",
                    ],
                )
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
                    locale="en-IN",
                    java_script_enabled=True,
                    viewport={"width": 1920, "height": 1080},
                )
                context.add_init_script(
                    "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
                )
                page = context.new_page()

                # ── Phase 1: Establish session & cookies ────────────────────
                print("[INIT] Visiting BigBasket homepage to establish session...")
                page.goto("https://www.bigbasket.com/", wait_until='domcontentloaded', timeout=90000)
                page.wait_for_timeout(5000)

                # Try to dismiss cookie/consent banners
                for sel in [
                    "#onetrust-accept-btn-handler",
                    "button:has-text('Accept')",
                    "button:has-text('I agree')",
                    "button:has-text('GOT IT')",
                    "button:has-text('ALLOW ALL')",
                ]:
                    try:
                        loc = page.locator(sel)
                        if loc.count() > 0:
                            loc.first.click()
                            page.wait_for_timeout(2000)
                            print(f"[INIT] Clicked banner: {sel}")
                            break
                    except Exception:
                        continue

                landing_url = f"https://www.bigbasket.com/cl/{slug}/"
                print(f"[3] Navigating to category landing: {landing_url}")

                if not _safe_goto(page, landing_url, timeout_ms=90000):
                    raise RuntimeError(f"Could not navigate to category landing {landing_url}")

                time.sleep(4)

                # ── Phase 2: Discover subcategory URLs ──────────────────────
                if user_subcats:
                    # Build URLs from user-specified subcategories
                    subcategory_urls = []
                    for sc in user_subcats:
                        sc_slug = make_slug(sc)
                        subcategory_urls.append(f"/pc/{slug}/{sc_slug}/")
                    print(f"[Discover] Using {len(subcategory_urls)} user-specified subcategory URLs.")
                else:
                    # Auto-discover via BFS crawl (same as BB_Scraper)
                    visited = set()
                    to_visit = []

                    seeds = _extract_category_links(page, slug)
                    to_visit.extend(seeds)

                    max_nodes = 250
                    while to_visit and len(visited) < max_nodes:
                        current = to_visit.pop(0)
                        if current in visited:
                            continue
                        visited.add(current)

                        full_current_url = (
                            "https://www.bigbasket.com" + current if current.startswith("/") else current
                        )
                        print(f"    [Discover] ({len(visited)}/{max_nodes}) {current}")

                        if not _safe_goto(page, full_current_url, timeout_ms=30000):
                            continue

                        time.sleep(random.uniform(2.5, 4.5))
                        scroll_to_bottom(page, max_scrolls=20)

                        nested = _extract_category_links(page, slug)
                        for u in nested:
                            if u not in visited and u not in to_visit:
                                to_visit.append(u)

                    subcategory_urls = sorted(visited)
                    print(f"[4] Discovered {len(subcategory_urls)} subcategory pages to scrape.")

                if not subcategory_urls:
                    # Fallback: scrape the landing page itself
                    print(f"[!] No subcategories found, scraping the category landing page directly.")
                    subcategory_urls = [f"/cl/{slug}/"]

                # ── Phase 3: Scrape each subcategory page ───────────────────
                total_pages = len(subcategory_urls)
                for idx, url_path in enumerate(subcategory_urls, 1):
                    full_url = (
                        "https://www.bigbasket.com" + url_path
                        if url_path.startswith("/")
                        else url_path
                    )
                    subcat_name = url_path.strip('/').split('/')[-1]

                    print(f"    ({idx}/{total_pages}) Crawling: {subcat_name} -> {full_url}")

                    if not _safe_goto(page, full_url, timeout_ms=30000):
                        continue

                    time.sleep(random.uniform(3.0, 5.0))
                    scroll_to_bottom(page, max_scrolls=pages)

                    data = parse_raw_html(page.content(), category, subcat_name)
                    if data:
                        all_results.extend(data)
                        print(f"        [+] Scraped {len(data)} items for '{subcat_name}'. Total so far: {len(all_results)}")
                    else:
                        print(f"        [!] No items parsed on '{subcat_name}'.")

                    # Update DB progress
                    if task:
                        task.total_found = len(all_results)
                        task.progress = min(99, int((idx / total_pages) * 100))
                        task.status = f"Scraped {len(all_results)} items [{idx}/{total_pages} pages]"
                        db.session.commit()

                browser.close()

            # ── Phase 4: Deduplicate and save CSV ───────────────────────────
            deduped = _process_and_deduplicate(all_results)
            print(f"[+] Deduplication: {len(all_results)} raw -> {len(deduped)} unique by sku_id")

            save_csv(deduped, output_path)
            save_task_metadata(task_id, output_path)

            if task:
                task.status = 'COMPLETED'
                task.progress = 100
                task.total_found = len(deduped)
                db.session.commit()

            print(f"[COMPLETED] Finished with {len(deduped)} unique records. CSV: {output_path}")

        except Exception as e:
            if task:
                task.status = 'FAILED'
                task.error_message = str(e)
                db.session.commit()
            print(f"[ERROR] BigBasket scraping failed: {e}")
            raise

        return {'scraped': len(all_results), 'unique': len(deduped) if 'deduped' in dir() else 0, 'csv_path': output_path}


# Keep legacy search function for backward compat (routes still reference it)
def scrape_bigbasket_search(search_term: str = '', pages: int = 1, task_id=None, category=None):
    """Legacy wrapper — delegates to category scraper."""
    return scrape_bigbasket_category(
        category=category or search_term or 'bigbasket',
        subcategories='',
        pages=pages,
        task_id=task_id
    )


# ─── CLI entrypoint ───────────────────────────────────────────────────────────

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='BigBasket Category Scraper Service')
    parser.add_argument('--category', required=True, help='Main category name e.g. "Fruits & Vegetables"')
    parser.add_argument('--subcategories', default='', help='Optional comma-separated subcategory names')
    parser.add_argument('--pages', type=int, default=10, help='Max scroll rounds per subcategory page')
    parser.add_argument('--task-id', type=int, default=None, help='ScraperTask DB ID')
    # Legacy args for backward compat
    parser.add_argument('--search-term', default='', help='(legacy) search term')
    args = parser.parse_args()

    scrape_bigbasket_category(
        category=args.category or args.search_term,
        subcategories=args.subcategories,
        pages=args.pages,
        task_id=args.task_id
    )
