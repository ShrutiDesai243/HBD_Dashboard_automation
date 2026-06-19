"""
csv_manager.py — Thread-safe read/write utility for categories.csv.
Handles URL discovery writes, verification status, and scrape tracking.
"""

import csv
import os
import threading
from datetime import datetime

CATEGORIES_FILE = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "categories.csv"
)

# Must match your actual categories.csv header exactly
FIELDNAMES = [
    "main_category", "subcategory", "leaf_category", "url",
    "scrape_status", "last_scraped", "items_found", "pages_scraped",
    "errors", "notes"
]

_lock = threading.Lock()


# ── Core read/write ────────────────────────────────────────────────────────────

def load_categories(csv_path=None) -> list[dict]:
    """Read all rows. Returns list of dicts."""
    path = csv_path or CATEGORIES_FILE
    with _lock:
        with open(path, newline="", encoding="utf-8-sig") as f:
            return list(csv.DictReader(f))


def save_categories(rows: list[dict], csv_path=None):
    """Overwrite categories.csv with updated rows."""
    path = csv_path or CATEGORIES_FILE
    with _lock:
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)


def _update_by_url(url: str, updates: dict, csv_path=None):
    """
    Internal: find row by URL and apply updates. Thread-safe.
    """
    path = csv_path or CATEGORIES_FILE
    with _lock:
        with open(path, newline="", encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))

        matched = False
        for row in rows:
            if row.get("url", "").strip() == url.strip():
                row.update(updates)
                matched = True
                break

        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)

    return matched


def _update_by_leaf(main_category: str, subcategory: str,
                    leaf_category: str, updates: dict, csv_path=None):
    """
    Internal: find row by the three name columns and apply updates.
    Used by write_url() — matches even when URL column is still blank.
    Thread-safe.
    """
    path = csv_path or CATEGORIES_FILE
    with _lock:
        with open(path, newline="", encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))

        matched = False
        for row in rows:
            if (row.get("main_category", "").strip().lower() == main_category.strip().lower()
                    and row.get("subcategory", "").strip().lower() == subcategory.strip().lower()
                    and row.get("leaf_category", "").strip().lower() == leaf_category.strip().lower()):
                row.update(updates)
                matched = True
                break

        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)

    return matched


# ── URL discovery functions (NEW) ─────────────────────────────────────────────

def write_url(main_category: str, subcategory: str,
              leaf_category: str, url: str, csv_path=None) -> bool:
    """
    Write a discovered URL into the matching row (found by name columns).
    Sets scrape_status to 'url_found'.
    Returns True if a matching row was found and updated, False otherwise.

    Called by discover_categories spider after nav crawl finds a match.
    """
    return _update_by_leaf(
        main_category, subcategory, leaf_category,
        {
            "url": url,
            "scrape_status": "url_found",
            "notes": f"URL found by discover_categories on {datetime.now().strftime('%Y-%m-%d')}",
        },
        csv_path,
    )


def get_url_pending(csv_path=None) -> list[dict]:
    """
    Return rows where URL is blank — these need discovery.
    Called at the start of discover_categories to know what to search for.
    """
    rows = load_categories(csv_path)
    return [
        r for r in rows
        if not r.get("url", "").strip()
        and r.get("leaf_category", "").strip()   # must have a leaf to search for
    ]


def get_verify_pending(csv_path=None) -> list[dict]:
    """
    Return rows that have a URL but haven't been verified yet.
    Status: url_found, pending, failed.
    """
    rows = load_categories(csv_path)
    return [
        r for r in rows
        if r.get("url", "").strip()
        and r.get("scrape_status", "").strip() in ("url_found", "pending", "failed", "")
    ]


# ── Scrape status functions (existing, updated for new column names) ──────────

def mark_verified(url: str, csv_path=None):
    """URL confirmed reachable with product cards."""
    _update_by_url(url, {"scrape_status": "verified"}, csv_path)


def mark_failed(url: str, error_msg: str = "", csv_path=None):
    """URL failed — network error, 404, or no product cards found."""
    _update_by_url(url, {
        "scrape_status": "failed",
        "last_scraped": datetime.now().isoformat(timespec="seconds"),
        "errors": error_msg[:200],
    }, csv_path)


def mark_in_progress(url: str, csv_path=None):
    _update_by_url(url, {"scrape_status": "in_progress"}, csv_path)


def mark_done(url: str, items_found: int, pages_scraped: int, csv_path=None):
    _update_by_url(url, {
        "scrape_status": "done",
        "last_scraped": datetime.now().isoformat(timespec="seconds"),
        "items_found": items_found,
        "pages_scraped": pages_scraped,
    }, csv_path)


def get_pending_urls(csv_path=None) -> list[dict]:
    """
    Return rows ready to scrape.
    Includes both 'verified' (confirmed working) and 'url_found' (has URL,
    not yet verified but worth trying directly — skipping the verify step).
    This ensures the 100+ url_found rows are not permanently ignored.
    """
    rows = load_categories(csv_path)
    return [
        r for r in rows
        if r.get("scrape_status", "").strip() in ("verified", "url_found")
        and r.get("url", "").strip()   # must have a URL
    ]


# ── Summary ────────────────────────────────────────────────────────────────────

def get_summary(csv_path=None) -> dict:
    rows = load_categories(csv_path)
    summary = {
        "total": len(rows),
        "no_url": 0,
        "url_found": 0,
        "verified": 0,
        "failed": 0,
        "in_progress": 0,
        "done": 0,
        "pending": 0,
    }
    for r in rows:
        status = r.get("scrape_status", "").strip() or "no_url"
        if not r.get("url", "").strip():
            summary["no_url"] += 1
        elif status in summary:
            summary[status] += 1
        else:
            summary["pending"] += 1
    return summary


def print_summary(csv_path=None):
    s = get_summary(csv_path)
    print(f"\n{'='*42}")
    print(f"  Categories CSV Summary")
    print(f"{'='*42}")
    print(f"  Total        : {s['total']}")
    print(f"  No URL yet   : {s['no_url']}")
    print(f"  URL Found    : {s['url_found']}")
    print(f"  Verified     : {s['verified']}")
    print(f"  Failed       : {s['failed']}")
    print(f"  In Progress  : {s['in_progress']}")
    print(f"  Done         : {s['done']}")
    print(f"{'='*42}\n")