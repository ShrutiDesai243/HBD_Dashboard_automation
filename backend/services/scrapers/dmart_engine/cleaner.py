# ============================================================
# DMart Web Scraper — Data Cleaner Module
# ============================================================
# Static utility class for cleaning and normalizing raw data
# extracted from DMart's DOM or API responses. All methods
# are stateless and can be called without instantiation.
# ============================================================

import re
import logging
from typing import Optional, Union

logger = logging.getLogger(__name__)


class DataCleaner:
    """
    Static methods for cleaning, normalizing, and validating
    scraped product data before database insertion.
    
    Design: All methods are @staticmethod — no instance state needed.
    Each method handles its own error cases gracefully, returning
    None or a sensible default rather than raising exceptions.
    """

    # ── Regex patterns (compiled once for performance) ─────────
    _CURRENCY_PATTERN = re.compile(r'[₹$€,\s]')        # Currency symbols & separators
    _WHITESPACE_PATTERN = re.compile(r'\s+')            # Multiple whitespace
    _SKU_FROM_URL = re.compile(r'/(\d{6,15})(?:[/?#]|$)')  # Numeric SKU from URL
    _SKU_FROM_SLUG = re.compile(r'-(\d{6,15})$')        # SKU at end of slug
    _WEIGHT_NORMALIZE = re.compile(                     # Weight/volume patterns
        r'(\d+(?:\.\d+)?)\s*(kg|g|gm|gms|gram|grams|ml|l|ltr|litre|litres|liter|liters|pcs?|pieces?|units?|pack|sheets?)\b',
        re.IGNORECASE
    )

    @staticmethod
    def clean_text(text: Optional[str]) -> Optional[str]:
        """
        Strip whitespace, newlines, and normalize internal spacing.
        
        Args:
            text: Raw text string from DOM or API.
            
        Returns:
            Cleaned string or None if input is empty/None.
            
        Example:
            "  Tata Salt  \\n  Iodized  " → "Tata Salt Iodized"
        """
        if not text:
            return None
        cleaned = DataCleaner._WHITESPACE_PATTERN.sub(' ', text.strip())
        return cleaned if cleaned else None

    @staticmethod
    def clean_product_name(name: Optional[str]) -> Optional[str]:
        """
        Clean product name: strip whitespace, newlines, and extra spaces.
        
        Args:
            name: Raw product name.
            
        Returns:
            Cleaned product name string.
        """
        return DataCleaner.clean_text(name)

    @staticmethod
    def clean_brand(brand: Optional[str]) -> Optional[str]:
        """
        Clean brand name and normalize to Title Case.
        
        Args:
            brand: Raw brand text.
            
        Returns:
            Title-cased brand name.
            
        Example:
            "  FORTUNE  " → "Fortune"
            "parle-g" → "Parle-G"
        """
        cleaned = DataCleaner.clean_text(brand)
        if not cleaned or 'inclusive of all taxes' in cleaned.lower():
            return None
        return cleaned.title()

    @staticmethod
    def clean_price(price_str: Optional[Union[str, int, float]]) -> Optional[float]:
        """
        CRITICAL: Parse price string into a clean float value.
        Extracts the first valid floating-point number.
        
        Args:
            price_str: Raw price string, e.g., "₹ 1,299.00", "1299", "MRP ₹103 (MRP Inclusive of all taxes)"
            
        Returns:
            Float value or None if parsing fails.
        """
        if price_str is None:
            return None

        # Handle numeric types directly (from API responses)
        if isinstance(price_str, (int, float)):
            return float(price_str)

        try:
            # Remove commas first, then find the first valid number
            cleaned = str(price_str).replace(',', '')
            match = re.search(r"(\d+(?:\.\d+)?)", cleaned)
            if match:
                return round(float(match.group(1)), 2)
            return None

        except (ValueError, TypeError) as e:
            logger.warning(f"Failed to parse price '{price_str}': {e}")
            return None

    @staticmethod
    def calculate_discount(mrp: Optional[float], sale_price: Optional[float]) -> Optional[float]:
        """
        Calculate discount amount programmatically.
        
        Args:
            mrp: Maximum Retail Price.
            sale_price: DMart selling price.
            
        Returns:
            Discount amount (mrp - sale_price), or 0.0 if not calculable.
        """
        if mrp is not None and sale_price is not None:
            discount = round(mrp - sale_price, 2)
            return max(discount, 0.0)  # Discount can't be negative
        return 0.0

    @staticmethod
    def clean_pack_size(pack_str: Optional[str]) -> Optional[str]:
        """
        Standardize weight/volume/quantity strings.
        
        Args:
            pack_str: Raw pack size text.
            
        Returns:
            Standardized pack size string.
            
        Examples:
            "1 Kg"     → "1 kg"
            "500 Gms"  → "500 g"
            "1000ml"   → "1000 ml"
            "6 Pcs"    → "6 pcs"
        """
        if not pack_str:
            return None

        cleaned = DataCleaner.clean_text(str(pack_str))
        if not cleaned:
            return None

        # Standardize unit abbreviations
        unit_map = {
            'gm': 'g', 'gms': 'g', 'gram': 'g', 'grams': 'g',
            'ltr': 'l', 'litre': 'l', 'litres': 'l',
            'liter': 'l', 'liters': 'l',
            'pcs': 'pcs', 'pc': 'pcs', 'pieces': 'pcs', 'piece': 'pcs',
            'units': 'units', 'unit': 'units',
            'sheets': 'sheets', 'sheet': 'sheets',
        }

        match = DataCleaner._WEIGHT_NORMALIZE.search(cleaned)
        if match:
            value = match.group(1)
            unit = match.group(2).lower()
            std_unit = unit_map.get(unit, unit)
            return f"{value} {std_unit}"

        return cleaned

    @staticmethod
    def clean_availability(status: Optional[Union[str, bool, int]]) -> int:
        """
        Convert availability text/state to binary integer.
        
        Args:
            status: Raw availability indicator — text, bool, or int.
            
        Returns:
            1 for in-stock, 0 for out-of-stock.
            
        Examples:
            "In Stock"      → 1
            "Out of Stock"  → 0
            True            → 1
            False           → 0
            "ADD TO CART"   → 1  (implies available)
        """
        if status is None:
            return 1  # Default to available if not specified

        if isinstance(status, bool):
            return 1 if status else 0

        if isinstance(status, int):
            return 1 if status > 0 else 0

        text = str(status).lower().strip()

        # Out-of-stock indicators
        out_of_stock_keywords = [
            'out of stock', 'out-of-stock', 'sold out', 'sold-out',
            'unavailable', 'not available', 'currently unavailable',
            'notify me', 'coming soon', 'false', '0'
        ]

        for keyword in out_of_stock_keywords:
            if keyword in text:
                return 0

        # In-stock indicators (including implied availability)
        in_stock_keywords = [
            'in stock', 'in-stock', 'available', 'add to cart',
            'add to bag', 'buy now', 'true', '1'
        ]

        for keyword in in_stock_keywords:
            if keyword in text:
                return 1

        # Default: assume available if we can't determine
        return 1

    @staticmethod
    def extract_sku_from_url(url: Optional[str]) -> Optional[str]:
        """
        Extract SKU/product ID from a DMart product URL.
        
        Args:
            url: Full product URL.
            
        Returns:
            SKU string or None.
            
        Examples:
            "/product/tasty-treats-butter-cookies-200g/12345678" → "12345678"
            "https://www.dmart.in/p/some-product-9876543"       → "9876543"
        """
        if not url:
            return None

        # Try extracting numeric ID from URL path
        match = DataCleaner._SKU_FROM_URL.search(url)
        if match:
            return match.group(1)

        # Try extracting from query param selectedProd=12345
        match = re.search(r'selectedProd=(\d+)', url)
        if match:
            return match.group(1)

        # Try extracting from end of slug (e.g., "product-name-12345")
        match = DataCleaner._SKU_FROM_SLUG.search(url.rstrip('/'))
        if match:
            return match.group(1)

        # Fallback: find any sequence of 5+ digits at the end of the string
        match = re.search(r'(\d{5,})(?:[^0-9]*)$', url)
        if match:
            return match.group(1)

        return None

    @staticmethod
    def build_full_url(path: Optional[str], base_url: str = "https://www.dmart.in") -> Optional[str]:
        """
        Convert a relative URL path to full absolute URL.
        
        Args:
            path: Relative or absolute URL.
            base_url: Base website URL.
            
        Returns:
            Full absolute URL string.
        """
        if not path:
            return None

        if path.startswith('http'):
            return path

        # Ensure path starts with /
        if not path.startswith('/'):
            path = f'/{path}'

        return f"{base_url}{path}"

    @staticmethod
    def clean_product_data(raw: dict) -> dict:
        """
        Master cleaning function: takes a raw product dict and returns
        a fully cleaned, database-ready dict.
        
        This is the single entry point for the cleaning pipeline.
        
        Args:
            raw: Dictionary with raw scraped fields.
            
        Returns:
            Cleaned dictionary ready for database insertion.
        """
        product_url = DataCleaner.build_full_url(
            raw.get('product_url') or raw.get('url')
        )

        # Extract SKU from multiple possible sources
        sku = (
            raw.get('sku_id')
            or raw.get('sku')
            or raw.get('id')
            or DataCleaner.extract_sku_from_url(product_url)
        )

        mrp = DataCleaner.clean_price(
            raw.get('mrp') or raw.get('maximum_retail_price')
        )
        dmart_price = DataCleaner.clean_price(
            raw.get('dmart_price')
            or raw.get('selling_price')
            or raw.get('sale_price')
            or raw.get('price')
        )

        # If only one price is available, use it for both
        if mrp is None and dmart_price is not None:
            mrp = dmart_price
        elif dmart_price is None and mrp is not None:
            dmart_price = mrp

        # Handle DMart image base URL
        image_url = raw.get('image_url')
        if image_url and not image_url.startswith('http'):
            # DMart API usually returns an imageKey like "J/A/N/JAN110004154xx23JAN24". 
            # The actual CDN URL only uses the basename, e.g. "JAN110004154xx23JAN24_5_B.jpg"
            if not image_url.startswith('/'):
                # Extract basename if it contains slashes
                basename = image_url.split('/')[-1]
                image_url = f"https://cdn.dmart.in/images/products/{basename}_5_B.jpg"
            else:
                image_url = DataCleaner.build_full_url(image_url)

        raw_name = raw.get('product_name') or raw.get('name') or raw.get('title')
        
        # Self-healing extraction: if pack_size is missing, try to extract it from the product name
        extracted_pack_size = None
        if raw_name:
            match = re.search(
                r'\s*:\s*(\d+(?:\.\d+)?\s*(?:kg|g|gm|gms|gram|grams|ml|l|ltr|litre|litres|liter|liters|pcs?|pieces?|units?|pack|sheets?|capsules?))\s*$',
                raw_name,
                re.IGNORECASE
            )
            if match:
                extracted_pack_size = match.group(1)

        brand = DataCleaner.clean_brand(
            raw.get('brand') or raw.get('brand_name')
        )
        if not brand and raw_name:
            words = raw_name.split()
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

        return {
            'product_url': product_url,
            'sku_id': str(sku) if sku else None,
            'product_name': DataCleaner.clean_product_name(raw_name),
            'brand': brand,
            'mrp': mrp,
            'dmart_price': dmart_price,
            'discount_amount': DataCleaner.calculate_discount(mrp, dmart_price),
            'pack_size': DataCleaner.clean_pack_size(
                raw.get('pack_size') or raw.get('packSize')
                or raw.get('uom') or raw.get('variant')
                or extracted_pack_size
            ),
            'availability': DataCleaner.clean_availability(
                raw.get('availability')
                or raw.get('stock_status')
                or raw.get('is_available')
                or raw.get('in_stock')
            ),
            'description': DataCleaner.clean_text(
                raw.get('description') or raw.get('seo_meta_desc')
            ),
            'category_name': raw.get('category_name'),
            'image_url': image_url,
        }
