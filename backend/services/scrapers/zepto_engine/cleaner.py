import re
import logging
from typing import Optional, Union

logger = logging.getLogger(__name__)


class DataCleaner:
    """Zepto-specific cleaning/normalization.

    Output keys must match the Zepto MySQL target CSV schema:
      sku_id,product_name,quantity,rating,review,mrp,selling_price,
      main_category,subcategory,product_url,image_url,scraped_at,product_description
    """

    _WHITESPACE_PATTERN = re.compile(r"\s+")
    _NUM_PATTERN = re.compile(r"(\d+(?:\.\d+)?)")

    # weight/volume/pcs
    _PACK_PATTERN = re.compile(
        r"(\d+(?:\.\d+)?)\s*(kg|g|gm|gms|gram|grams|ml|l|ltr|litre|litres|liter|liters|pcs?|pieces?|units?|pack|sheets?)\b",
        re.IGNORECASE,
    )

    _RATING_PATTERN = re.compile(r"(\d+(?:\.\d+)?)")

    @staticmethod
    def clean_text(text: Optional[str]) -> Optional[str]:
        if text is None:
            return None
        cleaned = DataCleaner._WHITESPACE_PATTERN.sub(" ", str(text)).strip()
        return cleaned or None

    @staticmethod
    def clean_price(price: Optional[Union[str, int, float]]) -> Optional[float]:
        if price is None:
            return None
        if isinstance(price, (int, float)):
            return float(price)
        try:
            m = DataCleaner._NUM_PATTERN.search(str(price).replace(",", ""))
            return float(m.group(1)) if m else None
        except Exception:
            return None

    @staticmethod
    def clean_pack_size(pack: Optional[str]) -> Optional[str]:
        if not pack:
            return None
        m = DataCleaner._PACK_PATTERN.search(str(pack))
        if not m:
            # Fallback: return cleaned raw
            return DataCleaner.clean_text(pack)
        value = m.group(1)
        unit = m.group(2).lower()
        unit_map = {
            "gm": "g",
            "gms": "g",
            "gram": "g",
            "grams": "g",
            "ml": "ml",
            "l": "l",
            "ltr": "l",
            "litre": "l",
            "litres": "l",
            "liter": "l",
            "liters": "l",
            "pcs": "pcs",
            "pc": "pcs",
            "pieces": "pcs",
            "piece": "pcs",
            "units": "units",
            "unit": "units",
            "pack": "pack",
            "sheets": "sheets",
            "sheet": "sheets",
        }
        std_unit = unit_map.get(unit, unit)
        return f"{value} {std_unit}"

    @staticmethod
    def clean_availability(avail) -> int:
        if avail is None:
            return 1
        if isinstance(avail, bool):
            return 1 if avail else 0
        if isinstance(avail, (int, float)):
            return 1 if avail > 0 else 0
        text = str(avail).lower().strip()
        out_keywords = ["out of stock", "out-of-stock", "unavailable", "sold out", "not available", "0"]
        in_keywords = ["in stock", "available", "add to cart", "buy now", "1"]
        if any(k in text for k in out_keywords):
            return 0
        if any(k in text for k in in_keywords):
            return 1
        return 1

    @staticmethod
    def clean_rating(rating) -> Optional[float]:
        if rating is None:
            return None
        if isinstance(rating, (int, float)):
            return float(rating)
        m = DataCleaner._RATING_PATTERN.search(str(rating))
        return float(m.group(1)) if m else None

    @staticmethod
    def clean_review(review) -> Optional[int]:
        if review is None:
            return None
        if isinstance(review, int):
            return review
        m = DataCleaner._NUM_PATTERN.search(str(review).replace(",", ""))
        if not m:
            return None
        try:
            return int(float(m.group(1)))
        except Exception:
            return None

    @staticmethod
    def clean_product_url(url: Optional[str]) -> Optional[str]:
        if not url:
            return None
        url = str(url).strip()
        if url.startswith("http"):
            return url
        if url.startswith("/"):
            return f"https://www.zepto.com{url}"
        return f"https://www.zepto.com/{url}"

    @staticmethod
    def clean_image_url(url: Optional[str]) -> Optional[str]:
        if not url:
            return None
        url = str(url).strip()
        if url.startswith("http"):
            return url
        # Sometimes CDN paths are already absolute in payloads; else leave as-is.
        return url

    @staticmethod
    def extract_sku_id(raw: dict) -> Optional[str]:
        # Zepto usually has a stable SKU id in JSON payloads.
        for k in ["sku_id", "skuId", "skuUniqueID", "id", "productId", "asin"]:
            v = raw.get(k)
            if v:
                return str(v).strip()
        return None

    @staticmethod
    def clean_product_data(raw: dict) -> dict:
        sku_id = DataCleaner.extract_sku_id(raw)

        return {
            "sku_id": sku_id,
            "product_name": DataCleaner.clean_text(
                raw.get("product_name")
                or raw.get("name")
                or raw.get("title")
                or raw.get("displayName")
            ),
            "quantity": DataCleaner.clean_text(raw.get("quantity") or raw.get("pack_text") or raw.get("pack_size")),
            "rating": DataCleaner.clean_rating(raw.get("rating") or raw.get("stars")),
            "review": DataCleaner.clean_review(raw.get("review") or raw.get("reviews")),
            "mrp": DataCleaner.clean_price(raw.get("mrp") or raw.get("priceMRP") or raw.get("maximum_retail_price")),
            "selling_price": DataCleaner.clean_price(
                raw.get("selling_price")
                or raw.get("sale_price")
                or raw.get("priceSALE")
                or raw.get("offerPrice")
                or raw.get("price")
            ),
            "main_category": DataCleaner.clean_text(raw.get("main_category") or raw.get("categoryName") or raw.get("category")),
            "subcategory": DataCleaner.clean_text(raw.get("subcategory") or raw.get("sub_category") or raw.get("subcategoryName")),
            "product_url": DataCleaner.clean_product_url(raw.get("product_url") or raw.get("productUrl") or raw.get("url") or raw.get("pdpUrl")),
            "image_url": DataCleaner.clean_image_url(raw.get("image_url") or raw.get("imageUrl") or raw.get("image") or raw.get("productImage")),
            "scraped_at": raw.get("scraped_at"),
            "product_description": DataCleaner.clean_text(raw.get("product_description") or raw.get("description") or raw.get("seo_meta_desc")),
            "availability": DataCleaner.clean_availability(raw.get("availability") or raw.get("inStock") or raw.get("stock_status")),
            "pack_size": DataCleaner.clean_pack_size(raw.get("pack_size") or raw.get("packSize") or raw.get("uom") or raw.get("variant")),
        }

