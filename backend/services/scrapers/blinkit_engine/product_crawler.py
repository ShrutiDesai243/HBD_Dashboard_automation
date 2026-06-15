"""
Blinkit Product Crawler — Fetches and parses all products for a given category.
Handles pagination, field extraction, and data normalization.
"""
import logging
import time
from decimal import Decimal, InvalidOperation
from typing import List, Dict, Optional, Callable

from services.scrapers.blinkit_engine.api_client import BlinkitAPIClient

logger = logging.getLogger(__name__)

# Maximum pages per category to prevent infinite loops
MAX_PAGES_PER_CATEGORY = 200


class BlinkitProductCrawler:
    """
    Scrapes all products for a list of categories using Blinkit's paginated API.

    Product data maps to blinkit table:
    (product_id, product_name, brand, category, sub_category, price, mrp,
     discount, quantity, availability, image_url, product_url)
    """

    def __init__(self, client: BlinkitAPIClient, category_name_map: Optional[Dict[int, str]] = None):
        self.client = client
        # Map: category_id → category_name (for enriching products)
        self.category_name_map = category_name_map or {}

    def crawl_category(
        self,
        category_id: int,
        category_name: str,
        parent_category_name: Optional[str] = None,
        start_page: int = 1,
        on_product_batch: Optional[Callable] = None,
        max_pages: Optional[int] = None,
    ) -> List[Dict]:
        """
        Crawl all products for a single category across all pages.

        Args:
            category_id: Blinkit category ID
            category_name: Category display name
            parent_category_name: Parent category (used as 'category' field if subcategory)
            start_page: Page to resume from (for crash recovery)
            on_product_batch: Callback when a batch of products is scraped
            max_pages: Hard cap on pages (for testing)

        Returns:
            List of normalized product dicts
        """
        all_products = []
        page = start_page
        limit = max_pages or MAX_PAGES_PER_CATEGORY
        empty_pages = 0

        logger.info(f"[ProductCrawler] Crawling category '{category_name}' (id={category_id}) from page {page}")

        while page <= limit:
            raw_data = self.client.fetch_products_by_category(category_id, page)

            if not raw_data:
                empty_pages += 1
                if empty_pages >= 2:
                    logger.info(f"[ProductCrawler] Category '{category_name}' — no data on page {page}, stopping")
                    break
                page += 1
                continue

            products = self._parse_products(raw_data, category_id, category_name, parent_category_name)

            if not products:
                empty_pages += 1
                if empty_pages >= 2:
                    logger.info(f"[ProductCrawler] Category '{category_name}' — empty page {page}, stopping")
                    break
            else:
                empty_pages = 0
                all_products.extend(products)
                logger.info(f"[ProductCrawler]   page={page} → {len(products)} products (total={len(all_products)})")

                if on_product_batch:
                    try:
                        on_product_batch(products, category_id=category_id)
                    except Exception as cb_err:
                        logger.error(f"[ProductCrawler] Batch callback error: {cb_err}")

            page += 1
            # Small pace-limiting between pages
            time.sleep(0.2)

        logger.info(f"[ProductCrawler] Category '{category_name}' complete: {len(all_products)} total products")
        return all_products

    def _parse_products(
        self,
        raw_data: Dict,
        category_id: int,
        category_name: str,
        parent_category_name: Optional[str],
    ) -> List[Dict]:
        """
        Parse raw API response into normalized product dicts.
        Handles multiple Blinkit API response formats.
        """
        products = []

        try:
            # Extract product list from various possible response structures
            product_list = self._extract_product_list(raw_data)

            for item in product_list:
                product = self._parse_single_product(item, category_id, category_name, parent_category_name)
                if product:
                    products.append(product)

        except Exception as e:
            logger.error(f"[ProductCrawler] Parse error for category {category_id}: {e}", exc_info=True)

        return products

    def _extract_product_list(self, raw_data: Dict) -> List[Dict]:
        """Extract product list from various Blinkit API response structures."""
        # Try response.objects.products (common structure)
        objects = raw_data.get("response", {}).get("objects", [])
        if objects:
            for obj in objects:
                products = obj.get("products", [])
                if products:
                    return products

        # Try direct products list
        products = raw_data.get("products", [])
        if products:
            return products

        # Try snippets → widgets structure
        snippets = raw_data.get("snippets", []) or raw_data.get("data", {}).get("snippets", [])
        for snippet in snippets:
            if isinstance(snippet, dict):
                widgets = snippet.get("data", {}).get("widgets", [])
                for widget in widgets:
                    widget_products = widget.get("data", {}).get("products", [])
                    if widget_products:
                        return widget_products

        # Try catalog.products
        catalog = raw_data.get("catalog", {})
        if catalog:
            return catalog.get("products", [])

        return []

    def _parse_single_product(
        self,
        item: Dict,
        category_id: int,
        category_name: str,
        parent_category_name: Optional[str],
    ) -> Optional[Dict]:
        """Parse a single product item into normalized dict."""
        try:
            # Product ID — CRITICAL (primary key)
            product_id = (
                item.get("id") or
                item.get("product_id") or
                item.get("prid")
            )
            if not product_id:
                return None

            # Safely convert to int
            try:
                product_id = int(product_id)
            except (TypeError, ValueError):
                return None

            # Product name
            product_name = (
                item.get("name") or
                item.get("product_name") or
                item.get("display_name") or
                item.get("title", "")
            ).strip()

            if not product_name:
                return None

            # Brand
            brand = (
                item.get("brand") or
                item.get("brand_name") or
                item.get("merchant_info", {}).get("name", "") or
                ""
            ).strip()

            # Category & subcategory
            # If this is a level-2 category, parent is the main category
            if parent_category_name:
                category_field = parent_category_name
                sub_category_field = category_name
            else:
                category_field = category_name
                sub_category_field = (
                    item.get("sub_category") or
                    item.get("subcategory") or
                    item.get("category", {}).get("name", "") or
                    ""
                )

            # Pricing
            price      = self._safe_decimal(item.get("price") or item.get("mrp") or item.get("discounted_price"))
            mrp        = self._safe_decimal(item.get("mrp") or item.get("market_price") or item.get("price"))
            discount   = self._calc_discount(price, mrp)

            # Quantity / Pack size
            quantity = (
                item.get("quantity") or
                item.get("pack_size") or
                item.get("unit") or
                item.get("weight") or
                ""
            )
            if isinstance(quantity, (int, float)):
                quantity = str(quantity)

            # Availability
            availability = bool(
                item.get("available", True) or
                item.get("availability", True) or
                item.get("in_stock", True)
            )

            # Images
            image_url = ""
            images = item.get("images", []) or item.get("image_urls", [])
            if images and isinstance(images, list):
                image_url = images[0] if isinstance(images[0], str) else images[0].get("url", "")
            if not image_url:
                image_url = item.get("image_url") or item.get("img_url") or item.get("image", "")

            # Product URL
            product_url = (
                item.get("product_url") or
                item.get("url") or
                f"https://blinkit.com/prn/item/prid/{product_id}"
            )

            return {
                "product_id":   product_id,
                "product_name": product_name[:500] if product_name else "",
                "brand":        brand[:255] if brand else None,
                "category":     category_field[:255] if category_field else None,
                "sub_category": sub_category_field[:255] if sub_category_field else None,
                "price":        price,
                "mrp":          mrp,
                "discount":     discount,
                "quantity":     str(quantity)[:100] if quantity else None,
                "availability": availability,
                "image_url":    image_url[:2048] if image_url else None,
                "product_url":  product_url[:2048] if product_url else None,
            }

        except Exception as e:
            logger.debug(f"[ProductCrawler] Failed to parse product: {e} | item={str(item)[:200]}")
            return None

    @staticmethod
    def _safe_decimal(value) -> Optional[Decimal]:
        if value is None:
            return None
        try:
            if isinstance(value, str):
                value = value.replace("₹", "").replace(",", "").strip()
            return Decimal(str(value)).quantize(Decimal("0.01"))
        except (InvalidOperation, ValueError, TypeError):
            return None

    @staticmethod
    def _calc_discount(price: Optional[Decimal], mrp: Optional[Decimal]) -> Optional[Decimal]:
        if price is not None and mrp is not None and mrp > 0:
            discount = mrp - price
            return max(Decimal("0.00"), discount.quantize(Decimal("0.01")))
        return None
