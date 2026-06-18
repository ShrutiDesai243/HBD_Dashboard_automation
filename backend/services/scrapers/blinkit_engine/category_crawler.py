"""
Blinkit Category Crawler — Discovers and parses all categories/subcategories.
Builds a full hierarchical category tree from Blinkit's API.
"""
import logging
import time
from typing import List, Dict, Optional, Callable

from services.scrapers.blinkit_engine.api_client import BlinkitAPIClient
from services.scrapers.blinkit_engine.config import DEFAULT_PINCODE

logger = logging.getLogger(__name__)


class BlinkitCategoryCrawler:
    """
    Discovers all categories and subcategories from Blinkit.

    Blinkit's category API returns a tree structure:
    - Level 1: Main categories (e.g. "Vegetables & Fruits")
    - Level 2: Subcategories (e.g. "Exotics & Premium")
    - Level 3+: Sub-subcategories if any

    Each category maps to: blinkit_mapping table columns:
    (category_id, category_name, slug, parent_id, category_level, full_category_path)
    """

    def __init__(self, client: BlinkitAPIClient):
        self.client = client
        self._all_categories: List[Dict] = []

    def crawl(self, on_category_found: Optional[Callable] = None) -> List[Dict]:
        """
        Crawl all categories and subcategories.
        Returns list of category dicts matching blinkit_mapping schema.
        """
        self._all_categories = []
        logger.info("[CategoryCrawler] Starting category discovery...")

        # Step 1: Fetch main categories
        main_cats = self._fetch_main_categories()
        if not main_cats:
            logger.error("[CategoryCrawler] No main categories found!")
            return []

        logger.info(f"[CategoryCrawler] Found {len(main_cats)} main categories")

        # Step 2: For each main category, fetch subcategories
        for idx, cat in enumerate(main_cats, 1):
            logger.info(f"[CategoryCrawler] [{idx}/{len(main_cats)}] Processing: {cat.get('name', 'Unknown')}")

            # Add main category (level 1)
            main_entry = {
                "category_id": cat.get("id") or cat.get("category_id"),
                "category_name": cat.get("name") or cat.get("category_name", ""),
                "slug": cat.get("slug", ""),
                "parent_id": 0,
                "category_level": 1,
                "full_category_path": cat.get("name") or cat.get("category_name", ""),
            }

            if not main_entry["category_id"]:
                logger.warning(f"[CategoryCrawler] Skipping category with no ID: {cat}")
                continue

            self._all_categories.append(main_entry)
            if on_category_found:
                on_category_found(main_entry)

            # Fetch subcategories for this main category
            sub_cats = self._fetch_subcategories(main_entry["category_id"])
            for sub in sub_cats:
                sub_entry = {
                    "category_id": sub.get("id") or sub.get("category_id"),
                    "category_name": sub.get("name") or sub.get("category_name", ""),
                    "slug": sub.get("slug", ""),
                    "parent_id": main_entry["category_id"],
                    "category_level": 2,
                    "full_category_path": f"{main_entry['full_category_path']} > {sub.get('name') or sub.get('category_name', '')}",
                }
                if not sub_entry["category_id"]:
                    continue
                self._all_categories.append(sub_entry)
                if on_category_found:
                    on_category_found(sub_entry)

                # Level 3 — sub-subcategories (if any)
                sub_sub_cats = self._fetch_subcategories(sub_entry["category_id"])
                for ssub in sub_sub_cats:
                    ssub_entry = {
                        "category_id": ssub.get("id") or ssub.get("category_id"),
                        "category_name": ssub.get("name") or ssub.get("category_name", ""),
                        "slug": ssub.get("slug", ""),
                        "parent_id": sub_entry["category_id"],
                        "category_level": 3,
                        "full_category_path": f"{sub_entry['full_category_path']} > {ssub.get('name') or ssub.get('category_name', '')}",
                    }
                    if not ssub_entry["category_id"]:
                        continue
                    self._all_categories.append(ssub_entry)
                    if on_category_found:
                        on_category_found(ssub_entry)

        # Deduplicate by category_id
        seen = set()
        deduped = []
        for cat in self._all_categories:
            cid = cat["category_id"]
            if cid not in seen:
                seen.add(cid)
                deduped.append(cat)

        logger.info(f"[CategoryCrawler] Discovery complete: {len(deduped)} unique categories found")
        return deduped

    def _fetch_main_categories(self) -> List[Dict]:
        """Parse main categories from Blinkit's slot API response."""
        data = self.client.fetch_main_categories()
        if not data:
            return []

        categories = []
        try:
            # Try multiple response structures Blinkit may return
            snippets = (
                data.get("snippets") or
                data.get("data", {}).get("snippets") or
                data.get("categories") or
                []
            )

            for snippet in snippets:
                # Each snippet may have widgets inside
                widgets = snippet.get("data", {}).get("widgets", []) if isinstance(snippet, dict) else []
                for widget in widgets:
                    widget_data = widget.get("data", {})
                    items = (
                        widget_data.get("items") or
                        widget_data.get("categories") or
                        [widget_data] if widget_data.get("id") or widget_data.get("category_id") else []
                    )
                    for item in items:
                        cat_id = item.get("id") or item.get("category_id") or item.get("category", {}).get("id")
                        cat_name = (
                            item.get("name") or
                            item.get("category_name") or
                            item.get("category", {}).get("name") or
                            item.get("display_name", "")
                        )
                        slug = item.get("slug", "") or item.get("category", {}).get("slug", "")
                        if cat_id and cat_name:
                            categories.append({"id": cat_id, "name": cat_name, "slug": slug})

            # Fallback: try direct category list
            if not categories:
                direct = data.get("categories") or data.get("data", [])
                if isinstance(direct, list):
                    for item in direct:
                        cat_id = item.get("id") or item.get("category_id")
                        cat_name = item.get("name") or item.get("category_name") or item.get("display_name", "")
                        slug = item.get("slug", "")
                        if cat_id and cat_name:
                            categories.append({"id": cat_id, "name": cat_name, "slug": slug})

        except Exception as e:
            logger.error(f"[CategoryCrawler] Error parsing main categories: {e}", exc_info=True)

        return categories

    def _fetch_subcategories(self, category_id: int) -> List[Dict]:
        """Fetch and parse subcategories for a given parent category."""
        time.sleep(0.3)  # brief pause between sub-requests
        data = self.client.fetch_subcategories(category_id)
        if not data:
            return []

        subcategories = []
        try:
            snippets = (
                data.get("snippets") or
                data.get("data", {}).get("snippets") or
                []
            )
            for snippet in snippets:
                widgets = snippet.get("data", {}).get("widgets", []) if isinstance(snippet, dict) else []
                for widget in widgets:
                    widget_data = widget.get("data", {})
                    items = widget_data.get("items") or widget_data.get("categories") or []
                    for item in items:
                        cat_id = item.get("id") or item.get("category_id") or item.get("category", {}).get("id")
                        cat_name = (
                            item.get("name") or
                            item.get("category_name") or
                            item.get("category", {}).get("name") or
                            item.get("display_name", "")
                        )
                        slug = item.get("slug", "") or item.get("category", {}).get("slug", "")
                        if cat_id and cat_name and cat_id != category_id:
                            subcategories.append({"id": cat_id, "name": cat_name, "slug": slug})

            # Fallback: direct list
            if not subcategories:
                direct = data.get("categories") or data.get("data", [])
                if isinstance(direct, list):
                    for item in direct:
                        cat_id = item.get("id") or item.get("category_id")
                        cat_name = item.get("name") or item.get("category_name") or item.get("display_name", "")
                        slug = item.get("slug", "")
                        if cat_id and cat_name and cat_id != category_id:
                            subcategories.append({"id": cat_id, "name": cat_name, "slug": slug})

        except Exception as e:
            logger.debug(f"[CategoryCrawler] Error parsing subcategories for {category_id}: {e}")

        return subcategories
