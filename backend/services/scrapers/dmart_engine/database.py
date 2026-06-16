# ============================================================
# DMart Web Scraper — Database Manager Module
# ============================================================
# Handles all SQLite operations: schema creation, category
# hierarchy management, and product UPSERT (duplicate prevention).
# Implements context manager protocol for safe teardown.
# ============================================================

import sqlite3
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime
import csv

logger = logging.getLogger(__name__)

STATIC_CATEGORY_MAPPING = {
    'packaged food > ready to cook': {'category_id': 1, 'category_name': 'Ready To Cook', 'slug': 'ready-to-cook-aesc-readytocook', 'parent_id': 32, 'category_level': 2},
    'dairy & beverages > beverages': {'category_id': 2, 'category_name': 'Beverages', 'slug': 'beverages-aesc-beverages', 'parent_id': 31, 'category_level': 2},
    'packaged food > biscuits & cookies': {'category_id': 3, 'category_name': 'Biscuits & Cookies', 'slug': 'biscuits---cookies-aesc-biscuitsandcookies', 'parent_id': 32, 'category_level': 2},
    'personal care & beauty > bath & body': {'category_id': 4, 'category_name': 'Bath & Body', 'slug': 'bath-body', 'parent_id': 36, 'category_level': 2},
    'home & kitchen > detergent & fabric care': {'category_id': 5, 'category_name': 'Detergent & Fabric Care', 'slug': 'detergent---fabric-care-aesc-detergentsandfabriccare', 'parent_id': 34, 'category_level': 2},
    'home & kitchen > cleaners': {'category_id': 6, 'category_name': 'Cleaners', 'slug': 'cleaners-aesc-cleaners', 'parent_id': 34, 'category_level': 2},
    'dairy & beverages > dairy > milk': {'category_id': 7, 'category_name': 'Milk', 'slug': 'milk-aesc-milksc2', 'parent_id': 55, 'category_level': 3},
    'dairy & beverages > dairy > cheese': {'category_id': 8, 'category_name': 'Cheese', 'slug': 'cheese-aesc-cheesesc2', 'parent_id': 55, 'category_level': 3},
    'packaged food > ketchup & sauce': {'category_id': 9, 'category_name': 'Ketchup & Sauce', 'slug': 'ketchup---sauce-aesc-ketchupandsauces', 'parent_id': 32, 'category_level': 2},
    'packaged food > pickles': {'category_id': 10, 'category_name': 'Pickles', 'slug': 'pickles-aesc-pickles', 'parent_id': 32, 'category_level': 2},
    'grocery > dmart grocery > atta': {'category_id': 11, 'category_name': 'Atta', 'slug': 'atta-aesc-attasc2', 'parent_id': 94, 'category_level': 3},
    'packaged food > chips & wafers': {'category_id': 12, 'category_name': 'Chips & Wafers', 'slug': 'chips---wafers-aesc-chips---waferssc2', 'parent_id': 32, 'category_level': 2},
    'packaged food > oats': {'category_id': 13, 'category_name': 'Oats', 'slug': 'oats-aesc-oatssc2', 'parent_id': 32, 'category_level': 2},
    'dairy & beverages > beverages > green tea': {'category_id': 14, 'category_name': 'Green Tea', 'slug': 'green-tea-aesc-green-teasc2', 'parent_id': 2, 'category_level': 3},
    'dairy & beverages > beverages > cold drinks': {'category_id': 15, 'category_name': 'Cold Drinks', 'slug': 'soft-drinks-aesc-soft-drinkssc2', 'parent_id': 2, 'category_level': 3},
    'personal care & beauty > skin care': {'category_id': 16, 'category_name': 'Skin Care', 'slug': 'skin-care-208510--1', 'parent_id': 36, 'category_level': 2},
    'personal care & beauty > skin care > body lotions': {'category_id': 17, 'category_name': 'Body Lotions', 'slug': 'body-lotions-scrubs', 'parent_id': 16, 'category_level': 3},
    'personal care & beauty > skin care > baby powder': {'category_id': 18, 'category_name': 'Baby Powder', 'slug': 'baby-powder-aesc-baby-powdersc2', 'parent_id': 16, 'category_level': 3},
    'personal care & beauty > bath & body > bath soaps': {'category_id': 19, 'category_name': 'Bath Soaps', 'slug': 'soaps-aesc-soapssc2', 'parent_id': 4, 'category_level': 3},
    'personal care & beauty > bath & body > hair shampoos': {'category_id': 20, 'category_name': 'Hair Shampoos', 'slug': 'hair-shampoos-aesc-hair-shampoossc2', 'parent_id': 4, 'category_level': 3},
    'personal care & beauty > toothpaste': {'category_id': 21, 'category_name': 'Toothpaste', 'slug': 'toothpaste-aesc-toothpastesc2', 'parent_id': 36, 'category_level': 2},
    'baby & kids > diapering > diapers': {'category_id': 22, 'category_name': 'Diapers', 'slug': 'diapers-aesc-diaperssc2', 'parent_id': 90, 'category_level': 3},
    'home & kitchen > crockery set': {'category_id': 23, 'category_name': 'Crockery Set', 'slug': 'crockery-sets-aesc-crockery-sets-sc2', 'parent_id': 34, 'category_level': 2},
    'home & kitchen > cookware > tawas & sauce pans': {'category_id': 24, 'category_name': 'Tawas & Sauce Pans', 'slug': 'tawas-sauce-pans', 'parent_id': 60, 'category_level': 3},
    'home utility & organisers > jar container': {'category_id': 25, 'category_name': 'Jar Container', 'slug': 'jars---containers', 'parent_id': 41, 'category_level': 2},
    'bags & more > trolley bags': {'category_id': 26, 'category_name': 'Trolley bags', 'slug': 'trolley-bags-201503--1', 'parent_id': 44, 'category_level': 2},
    'home & kitchen > cleaners > bathroom cleaners': {'category_id': 27, 'category_name': 'Bathroom Cleaners', 'slug': 'bathroom-cleaners', 'parent_id': 6, 'category_level': 3},
    'home & kitchen > detergent & fabric care > detergent powder': {'category_id': 28, 'category_name': 'Detergent Powder', 'slug': 'detergent-powder-aesc-detergent-powder-sc2', 'parent_id': 5, 'category_level': 3},
    'home & kitchen > detergent & fabric care > dishwash liquids': {'category_id': 29, 'category_name': 'Dishwash Liquids', 'slug': 'dishwash-liquids--1', 'parent_id': 5, 'category_level': 3},
    'stationery > stationery kits': {'category_id': 30, 'category_name': 'Stationery Kits', 'slug': 'stationery-kits', 'parent_id': 40, 'category_level': 2},
    'dairy & beverages': {'category_id': 31, 'category_name': 'Dairy & Beverages', 'slug': 'dairy---beverages-aesc-dairyandbeveragescore', 'parent_id': None, 'category_level': 1},
    'packaged food': {'category_id': 32, 'category_name': 'Packaged Food', 'slug': 'packaged-food-aesc-packagedfoodcore', 'parent_id': None, 'category_level': 1},
    'fruits & vegetables': {'category_id': 33, 'category_name': 'Fruits & Vegetables', 'slug': 'fruits---vegetables-aesc-fruitsandvegetablescore', 'parent_id': None, 'category_level': 1},
    'home & kitchen': {'category_id': 34, 'category_name': 'Home & Kitchen', 'slug': 'home---kitchen-aesc-homeandkitchencore', 'parent_id': None, 'category_level': 1},
    'kitchen & dining': {'category_id': 35, 'category_name': 'Kitchen & Dining', 'slug': 'kitchen-dining', 'parent_id': None, 'category_level': 1},
    'personal care & beauty': {'category_id': 36, 'category_name': 'Personal Care & Beauty', 'slug': 'personal-care-beauty', 'parent_id': None, 'category_level': 1},
    'sports & fitness': {'category_id': 37, 'category_name': 'Sports & Fitness', 'slug': 'sports-and-fitness', 'parent_id': None, 'category_level': 1},
    'baby & kids > baby care': {'category_id': 38, 'category_name': 'Baby Care', 'slug': 'baby-care', 'parent_id': 89, 'category_level': 2},
    'books': {'category_id': 39, 'category_name': 'Books', 'slug': 'books-204003--1', 'parent_id': None, 'category_level': 1},
    'stationery': {'category_id': 40, 'category_name': 'Stationery', 'slug': 'school-supplies', 'parent_id': None, 'category_level': 1},
    'home utility & organisers': {'category_id': 41, 'category_name': 'Home Utility & Organisers', 'slug': 'home-utility-organisers', 'parent_id': None, 'category_level': 1},
    'electronics & appliances': {'category_id': 42, 'category_name': 'Electronics & Appliances', 'slug': 'electronics-appliances', 'parent_id': None, 'category_level': 1},
    'footwear': {'category_id': 43, 'category_name': 'Footwear', 'slug': 'aesc--footwear', 'parent_id': None, 'category_level': 1},
    'bags & more': {'category_id': 44, 'category_name': 'Bags & More', 'slug': 'trolley-bags-handbags-more', 'parent_id': None, 'category_level': 1},
    'gifting': {'category_id': 45, 'category_name': 'Gifting', 'slug': 'gifting-229002--1', 'parent_id': None, 'category_level': 1},
    'seasonal & more': {'category_id': 46, 'category_name': 'Seasonal & More', 'slug': 'specials-seasonal', 'parent_id': None, 'category_level': 1},
    'grocery > dmart grocery > dals': {'category_id': 47, 'category_name': 'Dals', 'slug': 'dals-aesc-dals', 'parent_id': 94, 'category_level': 3},
    'grocery > dmart grocery > pulses': {'category_id': 48, 'category_name': 'Pulses', 'slug': 'pulses-aesc-pulses3', 'parent_id': 94, 'category_level': 3},
    'grocery > dmart grocery > dry fruits': {'category_id': 49, 'category_name': 'Dry Fruits', 'slug': 'dry-fruits-aesc-dryfruits2', 'parent_id': 94, 'category_level': 3},
    'grocery > dmart grocery > cooking oil': {'category_id': 50, 'category_name': 'Cooking Oil', 'slug': 'cooking-oil-aesc-cookingoil', 'parent_id': 94, 'category_level': 3},
    'grocery > dmart grocery > ghee & vanaspati': {'category_id': 51, 'category_name': 'Ghee & Vanaspati', 'slug': 'ghee---vanaspati-aesc-gheeandvanaspati', 'parent_id': 94, 'category_level': 3},
    'grocery > dmart grocery > flours & grains': {'category_id': 52, 'category_name': 'Flours & Grains', 'slug': 'flours---grains-aesc-floursandgrains4', 'parent_id': 94, 'category_level': 3},
    'grocery > dmart grocery > rice & rice products': {'category_id': 53, 'category_name': 'Rice & Rice Products', 'slug': 'rice---rice-products-aesc-riceandriceproducts4', 'parent_id': 94, 'category_level': 3},
    'grocery > dmart grocery > salt / sugar / jaggery': {'category_id': 54, 'category_name': 'Salt / Sugar / Jaggery', 'slug': 'salt---sugar---jaggery-aesc-saltsugarjaggery4', 'parent_id': 94, 'category_level': 3},
    'dairy & beverages > dairy': {'category_id': 55, 'category_name': 'Dairy', 'slug': 'dairy-aesc-dairy', 'parent_id': 31, 'category_level': 2},
    'fruits & vegetables > fresh fruits': {'category_id': 56, 'category_name': 'Fresh Fruits', 'slug': 'fresh-fruits-aesc-freshfruits', 'parent_id': 33, 'category_level': 2},
    'fruits & vegetables > vegetables': {'category_id': 57, 'category_name': 'Vegetables', 'slug': 'vegetables-aesc-vegetables', 'parent_id': 33, 'category_level': 2},
    'home & kitchen > cleaners > utensil cleaners': {'category_id': 58, 'category_name': 'Utensil Cleaners', 'slug': 'utensil-cleaners-aesc-utensilcleaners', 'parent_id': 6, 'category_level': 3},
    'furniture & decor': {'category_id': 59, 'category_name': 'Furniture & Decor', 'slug': 'home-decor-216014--1', 'parent_id': None, 'category_level': 1},
    'home & kitchen > cookware': {'category_id': 60, 'category_name': 'Cookware', 'slug': 'cookware-218510--1', 'parent_id': 34, 'category_level': 2},
    'pooja needs': {'category_id': 61, 'category_name': 'Pooja Needs', 'slug': 'pooja-needs-aesc-poojaneeds', 'parent_id': None, 'category_level': 1},
    'home & kitchen > cookware > cookware set': {'category_id': 62, 'category_name': 'Cookware Set', 'slug': 'serveware-218514--1', 'parent_id': 60, 'category_level': 3},
    'home & kitchen > drinkware': {'category_id': 63, 'category_name': 'Drinkware', 'slug': 'drinkware', 'parent_id': 34, 'category_level': 2},
    'shop by room': {'category_id': 64, 'category_name': 'Shop By Room', 'slug': 'shop-by-room', 'parent_id': None, 'category_level': 1},
    'packaged food > snacks & farsans': {'category_id': 65, 'category_name': 'Snacks & Farsans', 'slug': 'snacks---farsans-aesc-snacksandfarsans', 'parent_id': 32, 'category_level': 2},
    'packaged food > breakfast cereals': {'category_id': 66, 'category_name': 'Breakfast Cereals', 'slug': 'breakfast-cereals-aesc-breakfastcereals', 'parent_id': 32, 'category_level': 2},
    'packaged food > chocolates & candies': {'category_id': 67, 'category_name': 'Chocolates & Candies', 'slug': 'chocolates---candies', 'parent_id': 32, 'category_level': 2},
    'packaged food > pasta & noodles': {'category_id': 68, 'category_name': 'Pasta & Noodles', 'slug': 'pasta---noodles-aesc-pastaandnoodles', 'parent_id': 32, 'category_level': 2},
    'packaged food > heathy food': {'category_id': 69, 'category_name': 'Heathy Food', 'slug': 'health-food-aesc-healthfood', 'parent_id': 32, 'category_level': 2},
    'packaged food > bakery': {'category_id': 70, 'category_name': 'Bakery', 'slug': 'bakery-aesc-bakery', 'parent_id': 32, 'category_level': 2},
    'packaged food > frozen food': {'category_id': 71, 'category_name': 'Frozen Food', 'slug': 'frozen-foods-aesc-frozenfoods', 'parent_id': 32, 'category_level': 2},
    'packaged food > sweets': {'category_id': 72, 'category_name': 'Sweets', 'slug': 'sweets-aesc-sweets', 'parent_id': 32, 'category_level': 2},
    'festive specials': {'category_id': 73, 'category_name': 'Festive Specials', 'slug': 'festive-specials', 'parent_id': None, 'category_level': 1},
    'bed & bath': {'category_id': 74, 'category_name': 'Bed & Bath', 'slug': 'home-furnishing-decor', 'parent_id': None, 'category_level': 1},
    'bed & bath > bedding': {'category_id': 75, 'category_name': 'Bedding', 'slug': 'bedsheets-more', 'parent_id': 74, 'category_level': 2},
    'bed & bath > curtains': {'category_id': 76, 'category_name': 'Curtains', 'slug': 'curtains-216012--1', 'parent_id': 74, 'category_level': 2},
    'bed & bath > bedroom storage': {'category_id': 78, 'category_name': 'Bedroom Storage', 'slug': 'storage-organizers', 'parent_id': 74, 'category_level': 2},
    'bed & bath > bath accessories': {'category_id': 79, 'category_name': 'Bath Accessories', 'slug': 'bath-range', 'parent_id': 74, 'category_level': 2},
    'electronics & accessories': {'category_id': 80, 'category_name': 'Electronics & Accessories', 'slug': 'computer-mobile-accessories', 'parent_id': None, 'category_level': 1},
    'home appliances': {'category_id': 81, 'category_name': 'Home Appliances', 'slug': 'home-appliances-216003--1', 'parent_id': None, 'category_level': 1},
    'home appliances > kitchen appliances': {'category_id': 82, 'category_name': 'Kitchen Appliances', 'slug': 'kitchen-appliances-216005--1', 'parent_id': 80, 'category_level': 2},
    'electronics & appliances > personal care appliances': {'category_id': 83, 'category_name': 'Personal Care Appliances', 'slug': 'personal-care-appliances-216007--1', 'parent_id': 42, 'category_level': 2},
    'clothing & accessories': {'category_id': 84, 'category_name': 'Clothing & Accessories', 'slug': 'clothing-accessories-aesc-clothingaccessories', 'parent_id': None, 'category_level': 1},
    'clothing & accessories > men clothing': {'category_id': 85, 'category_name': 'Men Clothing', 'slug': 'mens-mens', 'parent_id': 83, 'category_level': 2},
    'clothing & accessories > women clothing': {'category_id': 86, 'category_name': 'Women Clothing', 'slug': 'womens-womens', 'parent_id': 83, 'category_level': 2},
    'clothing & accessories > accessories': {'category_id': 87, 'category_name': 'Accessories', 'slug': 'accessories--1', 'parent_id': 83, 'category_level': 2},
    "footwear > men's footwear": {'category_id': 88, 'category_name': "Men's Footwear", 'slug': 'mens-footwear', 'parent_id': 43, 'category_level': 2},
    "footwear > women's footwear": {'category_id': 89, 'category_name': "Women's Footwear", 'slug': 'womens-footwear', 'parent_id': 43, 'category_level': 2},
    'baby & kids': {'category_id': 90, 'category_name': 'Baby & Kids', 'slug': 'baby---kids-aesc-babyandkidscore', 'parent_id': None, 'category_level': 1},
    'baby & kids > diapering': {'category_id': 91, 'category_name': 'Diapering', 'slug': 'diapers---wipes-aesc-diapersandwipes', 'parent_id': 89, 'category_level': 2},
    'baby & kids > baby food': {'category_id': 92, 'category_name': 'Baby Food', 'slug': 'baby-food-aesc-babyfood', 'parent_id': 89, 'category_level': 2},
    'baby & kids > baby gear & furniture': {'category_id': 93, 'category_name': 'Baby Gear & Furniture', 'slug': 'baby-gear---furniture', 'parent_id': 89, 'category_level': 2},
    'grocery': {'category_id': 94, 'category_name': 'Grocery', 'slug': 'grocery-aesc-grocerycore', 'parent_id': None, 'category_level': 1},
    'grocery > dmart grocery': {'category_id': 95, 'category_name': 'DMart Grocery', 'slug': 'dmart-grocery-aesc-grocerycore2', 'parent_id': 93, 'category_level': 2},
    'grocery > dmart grocery > grocery/dmart grocery/ dry fruits': {'category_id': 96, 'category_name': 'Grocery/DMart Grocery/ Dry Fruits', 'slug': None, 'parent_id': 94, 'category_level': 3},
    'grocery > dmart grocery > masala & spices': {'category_id': 97, 'category_name': 'Masala & Spices', 'slug': 'masala---spices-aesc-masalaandspices4', 'parent_id': 94, 'category_level': 3},
    'grocery > dmart grocery > masala & spices > chilli powder': {'category_id': 98, 'category_name': 'Chilli Powder', 'slug': None, 'parent_id': 96, 'category_level': 4},
    'grocery > dmart grocery > masala & spices > spices': {'category_id': 99, 'category_name': 'Spices', 'slug': None, 'parent_id': 96, 'category_level': 4},
    'grocery > dmart grocery > dals & pulses': {'category_id': 100, 'category_name': 'Dals & Pulses', 'slug': None, 'parent_id': 94, 'category_level': 3},
    'grocery > dmart grocery > grocery/dmart grocery/ flours & grains': {'category_id': 101, 'category_name': 'Grocery/DMart Grocery/ Flours & Grains', 'slug': None, 'parent_id': 94, 'category_level': 3},
}


class DatabaseManager:
    """
    Enterprise-grade SQLite database manager for DMart product data.
    
    Features:
        - Schema creation from external .sql file
        - Category hierarchy (3-level tree with parent_id FK)
        - Product UPSERT: INSERT new / UPDATE existing by sku_id
        - Batch insert with transaction support
        - Context manager for safe connection teardown
    
    Usage:
        with DatabaseManager('dmart_master.db', 'schema.sql') as db:
            cat_id = db.upsert_category('Grocery', 'grocery', None, 1)
            db.upsert_product({...}, cat_id)
    """

    def __init__(self, db_path: str, schema_path: Optional[str] = None):
        """
        Initialize database connection and create schema if needed.
        
        Args:
            db_path: Path to SQLite database file.
            schema_path: Path to .sql schema file (optional).
        """
        self.db_path = Path(db_path)
        self.schema_path = Path(schema_path) if schema_path else None
        self.conn: Optional[sqlite3.Connection] = None
        self.cursor: Optional[sqlite3.Cursor] = None

        # Category cache: maps (name, parent_id) → category_id
        # Prevents repeated DB lookups for the same category
        self._category_cache: Dict[tuple, int] = {}
        self.on_category_saved = None
        self.on_product_saved = None

    def _get_deterministic_id(self, path_str: str) -> int:
        """Get pre-defined ID from static mapping or fallback to deterministic path hash."""
        import hashlib
        normalized = " > ".join([p.strip().lower() for p in path_str.split('>') if p.strip()])
        
        # Check embedded static category mapping first to keep IDs consistent with original DB mapping
        if normalized in STATIC_CATEGORY_MAPPING:
            return STATIC_CATEGORY_MAPPING[normalized]['category_id']
            
        hash_md5 = hashlib.md5(normalized.encode('utf-8')).hexdigest()
        val = int(hash_md5[:8], 16)
        return val & 0x7FFFFFFF

    def __enter__(self):
        """Context manager entry: open connection and init schema."""
        if not self.conn:
            self.connect()
            self._context_managed = True
        else:
            self._context_managed = False
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit: always close connection safely."""
        if getattr(self, '_context_managed', False):
            self.close()
        return False  # Don't suppress exceptions

    def connect(self):
        """
        Establish SQLite connection with optimized settings.
        Creates the database file if it doesn't exist.
        """
        try:
            # Ensure parent directory exists
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

            self.conn = sqlite3.connect(
                str(self.db_path),
                timeout=30,
                check_same_thread=False
            )
            self.cursor = self.conn.cursor()

            # ── SQLite Performance Optimizations ──
            self.cursor.execute("PRAGMA journal_mode=WAL")     # Write-Ahead Logging
            self.cursor.execute("PRAGMA synchronous=NORMAL")   # Balance safety/speed
            self.cursor.execute("PRAGMA cache_size=-64000")    # 64MB cache
            self.cursor.execute("PRAGMA foreign_keys=ON")      # Enforce FK constraints
            self.cursor.execute("PRAGMA temp_store=MEMORY")    # Temp tables in RAM

            # Initialize schema if provided
            if self.schema_path:
                if self.schema_path.exists():
                    self._init_schema()
                    self._migrate_sqlite_columns()
                else:
                    raise FileNotFoundError(f"SQLite schema file not found at: {self.schema_path.absolute()}")

            logger.info(f"Database connected: {self.db_path}")

        except sqlite3.Error as e:
            logger.error(f"Database connection failed: {e}")
            raise

    def _init_schema(self):
        """Execute the schema SQL file to create tables and indexes."""
        try:
            schema_sql = self.schema_path.read_text(encoding='utf-8')
            self.cursor.executescript(schema_sql)
            self.conn.commit()
            logger.info(f"Schema initialized from: {self.schema_path}")
        except (sqlite3.Error, FileNotFoundError) as e:
            logger.error(f"Schema initialization failed: {e}")
            raise

    def _migrate_sqlite_columns(self):
        """Idempotently add missing columns in SQLite tables."""
        try:
            # 1. Check dmart_category_master columns
            self.cursor.execute("PRAGMA table_info(dmart_category_master)")
            columns_cat = [col[1] for col in self.cursor.fetchall()]
            if columns_cat and "category_path" not in columns_cat:
                logger.info("⚠️ Column `category_path` missing in SQLite `dmart_category_master`. Migrating now...")
                self.cursor.execute("ALTER TABLE dmart_category_master ADD COLUMN category_path TEXT")
                self.conn.commit()
                logger.info("✅ Column `category_path` successfully added to SQLite.")

            # 2. Check dmart_product_master columns
            self.cursor.execute("PRAGMA table_info(dmart_product_master)")
            columns_prod = [col[1] for col in self.cursor.fetchall()]
            if columns_prod and "pincodes" not in columns_prod:
                logger.info("⚠️ Column `pincodes` missing in SQLite `dmart_product_master`. Migrating now...")
                self.cursor.execute("ALTER TABLE dmart_product_master ADD COLUMN pincodes TEXT")
                self.conn.commit()
                logger.info("✅ Column `pincodes` successfully added to SQLite.")
        except sqlite3.Error as e:
            logger.error(f"SQLite dynamic column migration failed: {e}")

    def resolve_category_path(self, path_str: str, slug_list: Optional[list] = None) -> int:
        """
        Dynamically resolves a category path of any length (e.g., L1 > L2 > L3)
        to the database using deterministic path hashing.
        """
        def clean_cat_name(name_str: str) -> str:
            if not name_str:
                return ""
            return name_str.strip().strip('|').strip('/').strip('\\').strip(':').strip(';').strip()

        parts = [clean_cat_name(p) for p in path_str.split('>') if p.strip()]
        if not parts:
            return self.upsert_category("Uncategorized", level=1, category_path="Uncategorized")
            
        # ── Defensive Clean: Skip Home/DMart Root Breadcrumbs if present ──
        if len(parts) > 1 and parts[0].lower() in ('home', 'dmart', 'online shopping', 'online shopping at dmart'):
            parts = parts[1:]

        parent_id = None
        current_id = None
        path_accum = []
        
        for idx, name in enumerate(parts):
            level = idx + 1
            path_accum.append(name)
            current_path_str = " > ".join(path_accum)
            
            slug = slug_list[idx] if (slug_list and idx < len(slug_list)) else None
            
            current_id = self.upsert_category(
                name=name,
                slug=slug,
                parent_id=parent_id,
                level=level,
                category_path=current_path_str
            )
            parent_id = current_id
            
        return current_id

    def close(self):
        """Safely close the database connection."""
        try:
            if self.conn:
                self.conn.commit()  # Flush any pending changes
                self.conn.close()
                logger.info("Database connection closed.")
        except sqlite3.Error as e:
            logger.warning(f"Error closing database: {e}")
        finally:
            self.conn = None
            self.cursor = None

    # ── Category Operations ────────────────────────────────────

    def upsert_category(
        self,
        name: str,
        slug: Optional[str] = None,
        parent_id: Optional[int] = None,
        level: Optional[int] = None,
        category_path: Optional[str] = None
    ) -> int:
        """
        Insert or update a category using standard SQLite AUTOINCREMENT.
        
        Uses (name, parent_id) as the composite cache lookup key.
        """
        # Clean trailing/leading pipes, slashes, backslashes, colons, semicolons
        if name:
            name = name.strip().strip('|').strip('/').strip('\\').strip(':').strip(';').strip()
        if slug:
            slug = slug.strip().strip('|').strip('/').strip('\\').strip(':').strip(';').strip()

        cache_key = (name, parent_id)

        # Check cache first to avoid DB round-trip
        if cache_key in self._category_cache:
            return self._category_cache[cache_key]

        try:
            category_id = None
            
            # Check if category already exists by path or name & parent
            if category_path:
                self.cursor.execute(
                    "SELECT category_id FROM dmart_category_master WHERE category_path = ?",
                    (category_path,)
                )
                row = self.cursor.fetchone()
                if row:
                    category_id = row[0]
            
            if not category_id:
                if parent_id is not None:
                    self.cursor.execute(
                        "SELECT category_id FROM dmart_category_master WHERE category_name = ? AND parent_id = ?",
                        (name, parent_id)
                    )
                else:
                    self.cursor.execute(
                        "SELECT category_id FROM dmart_category_master WHERE category_name = ? AND parent_id IS NULL",
                        (name,)
                    )
                row = self.cursor.fetchone()
                if row:
                    category_id = row[0]

            if category_id is not None:
                # Category exists — use existing ID and idempotently update details
                self.cursor.execute(
                    """UPDATE dmart_category_master 
                       SET category_name = ?, slug = ?, parent_id = ?, category_level = ?, category_path = ?
                       WHERE category_id = ?""",
                    (name, slug, parent_id, level, category_path, category_id)
                )
                self.conn.commit()
            else:
                # Insert new category (letting SQLite generate AUTOINCREMENT ID)
                self.cursor.execute(
                    """INSERT INTO dmart_category_master 
                       (category_name, slug, parent_id, category_level, category_path)
                       VALUES (?, ?, ?, ?, ?)""",
                    (name, slug, parent_id, level, category_path)
                )
                self.conn.commit()
                category_id = self.cursor.lastrowid
                logger.info(
                    f"New category inserted: '{name}' (ID={category_id}, "
                    f"parent={parent_id}, level={level}, path={category_path})"
                )

            # Trigger external sync hook (e.g. MySQL)
            if self.on_category_saved:
                try:
                    self.on_category_saved({
                        'category_id': category_id,
                        'category_name': name,
                        'slug': slug,
                        'parent_id': parent_id,
                        'category_level': level,
                        'category_path': category_path
                    })
                except Exception as cb_err:
                    logger.error(f"Category sync callback failed: {cb_err}")

            # Cache the result
            self._category_cache[cache_key] = category_id
            return category_id

        except sqlite3.Error as e:
            logger.error(f"Category upsert failed for '{name}': {e}")
            raise

    def resolve_category_hierarchy(
        self,
        main_cat: str,
        sub_cat: Optional[str] = None,
        leaf_cat: Optional[str] = None,
        main_slug: Optional[str] = None,
        sub_slug: Optional[str] = None,
        leaf_slug: Optional[str] = None,
    ) -> int:
        """
        Resolve a full 3-level category path, creating entries as needed.
        """
        # Level 1: Main category
        main_path = main_cat
        main_id = self.upsert_category(main_cat, main_slug, None, 1, category_path=main_path)

        if not sub_cat:
            return main_id

        # Level 2: Sub-category (child of main)
        sub_path = f"{main_path} > {sub_cat}"
        sub_id = self.upsert_category(sub_cat, sub_slug, main_id, 2, category_path=sub_path)

        if not leaf_cat:
            return sub_id

        # Level 3: Leaf category (child of sub)
        leaf_path = f"{sub_path} > {leaf_cat}"
        leaf_id = self.upsert_category(leaf_cat, leaf_slug, sub_id, 3, category_path=leaf_path)
        return leaf_id

    # ── Product Operations ─────────────────────────────────────

    def upsert_product(
        self,
        product: dict,
        category_id: Optional[int] = None,
        pincode: Optional[str] = None
    ) -> bool:
        """
        Insert or update a product in SQLite.
        
        If the same SKU with identical pricing exists:
            Update attributes and append the pincode to its pincodes JSON array.
        If the SKU exists but has a DIFFERENT price:
            Create a separate row in the database.
        If the SKU is brand new:
            Insert a new row with the pincode array.
        
        Args:
            product: Cleaned product dictionary.
            category_id: Foreign key to dmart_category_master.
            pincode: Current scraping pincode.
            
        Returns:
            True if operation succeeded, False otherwise.
        """
        import json
        sku_id = str(product.get('sku_id', '')).strip()

        # ── Secondary Deduplication (Name + Pack) ──
        # If DMart uses regional SKUs, this ensures we don't duplicate identical products
        p_name = product.get('product_name')
        p_size = product.get('pack_size')
        if p_name:
            if p_size:
                self.cursor.execute(
                    "SELECT sku_id FROM dmart_product_master WHERE product_name = ? AND pack_size = ?", 
                    (p_name, p_size)
                )
            else:
                self.cursor.execute(
                    "SELECT sku_id FROM dmart_product_master WHERE product_name = ? AND pack_size IS NULL", 
                    (p_name,)
                )
            
            row = self.cursor.fetchone()
            if row:
                # Override incoming SKU with the existing one to force a clean UPDATE
                sku_id = row[0]

        if not sku_id:
            logger.warning(f"Skipping product with no SKU: {product.get('product_name', 'unknown')}")
            return False

        # Parse incoming prices for comparison
        inc_price = product.get('dmart_price')
        inc_mrp = product.get('mrp')
        try:
            inc_price_float = float(inc_price) if inc_price is not None else 0.0
        except ValueError:
            inc_price_float = 0.0
        try:
            inc_mrp_float = float(inc_mrp) if inc_mrp is not None else 0.0
        except ValueError:
            inc_mrp_float = 0.0

        try:
            # Query all rows with this sku_id to check their pricing
            self.cursor.execute(
                "SELECT id, dmart_price, mrp, pincodes FROM dmart_product_master WHERE sku_id = ?",
                (sku_id,)
            )
            rows = self.cursor.fetchall()

            matched_id = None
            existing_pincodes_str = None

            for r in rows:
                row_id, r_price, r_mrp, r_pincodes = r
                try:
                    r_price_float = float(r_price) if r_price is not None else 0.0
                except ValueError:
                    r_price_float = 0.0
                try:
                    r_mrp_float = float(r_mrp) if r_mrp is not None else 0.0
                except ValueError:
                    r_mrp_float = 0.0

                # Check if price matches (float-safe comparison)
                if abs(r_price_float - inc_price_float) < 0.01 and abs(r_mrp_float - inc_mrp_float) < 0.01:
                    matched_id = row_id
                    existing_pincodes_str = r_pincodes
                    break

            if matched_id is not None:
                # ── UPDATE: Refresh pricing, availability, and pincodes list ──
                pincodes_list = []
                if existing_pincodes_str:
                    try:
                        pincodes_list = json.loads(existing_pincodes_str)
                        if not isinstance(pincodes_list, list):
                            pincodes_list = [str(pincodes_list)]
                    except Exception:
                        pincodes_list = [str(existing_pincodes_str)] if existing_pincodes_str else []

                if pincode:
                    pincode_str = str(pincode).strip()
                    if pincode_str not in pincodes_list:
                        pincodes_list.append(pincode_str)

                pincodes_json = json.dumps(pincodes_list)

                self.cursor.execute(
                    """UPDATE dmart_product_master SET
                        product_name = ?,
                        brand = ?,
                        pack_size = ?,
                        mrp = ?,
                        dmart_price = ?,
                        availability = ?,
                        category_id = COALESCE(?, category_id),
                        category_name = COALESCE(?, category_name),
                        product_url = COALESCE(?, product_url),
                        image_url = COALESCE(?, image_url),
                        description = COALESCE(?, description),
                        pincodes = ?,
                        scraped_at = CURRENT_TIMESTAMP
                    WHERE id = ?""",
                    (
                        product.get('product_name'),
                        product.get('brand'),
                        product.get('pack_size'),
                        product.get('mrp'),
                        product.get('dmart_price'),
                        product.get('availability', 1),
                        category_id,
                        product.get('category_name'),
                        product.get('product_url'),
                        product.get('image_url'),
                        product.get('description'),
                        pincodes_json,
                        matched_id,
                    )
                )
                logger.debug(f"Updated product (same price): {sku_id} (ID={matched_id}, pincodes={pincodes_json})")
            else:
                # ── INSERT: Create a new product row (new SKU or new price) ──
                pincodes_list = [str(pincode).strip()] if pincode else []
                pincodes_json = json.dumps(pincodes_list)

                self.cursor.execute(
                    """INSERT INTO dmart_product_master 
                       (sku_id, product_name, brand, pack_size, mrp,
                        dmart_price, availability, category_id, category_name, product_url, image_url, description, pincodes)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        sku_id,
                        product.get('product_name'),
                        product.get('brand'),
                        product.get('pack_size'),
                        product.get('mrp'),
                        product.get('dmart_price'),
                        product.get('availability', 1),
                        category_id,
                        product.get('category_name'),
                        product.get('product_url'),
                        product.get('image_url'),
                        product.get('description'),
                        pincodes_json,
                    )
                )
                logger.debug(f"Inserted product: {sku_id} (pincodes={pincodes_json})")

            self.conn.commit()
            if self.on_product_saved:
                try:
                    self.on_product_saved(product, category_id)
                except Exception as cb_err:
                    logger.error(f"Error in on_product_saved callback: {cb_err}")
            return True

        except sqlite3.Error as e:
            logger.error(f"Product upsert failed for SKU '{sku_id}': {e}")
            return False

    def bulk_upsert_products(
        self,
        products: List[dict],
        category_id: Optional[int] = None
    ) -> dict:
        """
        Batch upsert multiple products in a single transaction.
        
        Args:
            products: List of cleaned product dictionaries.
            category_id: FK to category table.
            
        Returns:
            Stats dict with 'inserted', 'updated', 'failed' counts.
        """
        stats = {'inserted': 0, 'updated': 0, 'failed': 0}

        try:
            self.cursor.execute("BEGIN TRANSACTION")

            for product in products:
                sku_id = product.get('sku_id')
                if not sku_id:
                    stats['failed'] += 1
                    continue

                # Check existence
                self.cursor.execute(
                    "SELECT id FROM dmart_product_master WHERE sku_id = ?",
                    (sku_id,)
                )
                existing = self.cursor.fetchone()

                if existing:
                    self.cursor.execute(
                        """UPDATE dmart_product_master SET
                            product_name = ?, brand = ?, pack_size = ?,
                            mrp = ?, dmart_price = ?, availability = ?,
                            category_id = COALESCE(?, category_id),
                            product_url = COALESCE(?, product_url),
                            description = COALESCE(?, description),
                            scraped_at = CURRENT_TIMESTAMP
                        WHERE sku_id = ?""",
                        (
                            product.get('product_name'),
                            product.get('brand'),
                            product.get('pack_size'),
                            product.get('mrp'),
                            product.get('dmart_price'),
                            product.get('availability', 1),
                            category_id,
                            product.get('product_url'),
                            product.get('description'),
                            sku_id,
                        )
                    )
                    stats['updated'] += 1
                else:
                    self.cursor.execute(
                        """INSERT INTO dmart_product_master
                           (sku_id, product_name, brand, pack_size, mrp,
                            dmart_price, availability, category_id, product_url, description)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            sku_id,
                            product.get('product_name'),
                            product.get('brand'),
                            product.get('pack_size'),
                            product.get('mrp'),
                            product.get('dmart_price'),
                            product.get('availability', 1),
                            category_id,
                            product.get('product_url'),
                            product.get('description'),
                        )
                    )
                    stats['inserted'] += 1

            self.conn.commit()

        except sqlite3.Error as e:
            logger.error(f"Bulk upsert transaction failed: {e}")
            self.conn.rollback()
            stats['failed'] = len(products)

        logger.info(
            f"Bulk upsert complete: {stats['inserted']} inserted, "
            f"{stats['updated']} updated, {stats['failed']} failed"
        )
        return stats

    # ── Query / Stats ──────────────────────────────────────────

    def get_product_count(self) -> int:
        """Return total product count in the database."""
        self.cursor.execute("SELECT COUNT(*) FROM dmart_product_master")
        return self.cursor.fetchone()[0]

    def get_category_count(self) -> int:
        """Return total category count in the database."""
        self.cursor.execute("SELECT COUNT(*) FROM dmart_category_master")
        return self.cursor.fetchone()[0]

    def get_products_missing_descriptions(self) -> List[str]:
        """
        Return a list of product_urls for products that have no description.
        Useful for hybrid scraping to selectively visit PDPs.
        """
        self.cursor.execute("""
            SELECT product_url 
            FROM dmart_product_master 
            WHERE description IS NULL OR description = '' 
              AND product_url IS NOT NULL
        """)
        rows = self.cursor.fetchall()
        return [row[0] for row in rows if row[0]]

    def get_existing_products_for_category(self, category_id: int) -> List[Dict[str, Any]]:
        """
        Return a list of products (sku_id, name, pack_size) already saved in SQLite for a category.
        """
        if category_id is None:
            return []
        try:
            self.cursor.execute(
                "SELECT sku_id, product_name, pack_size FROM dmart_product_master WHERE category_id = ?",
                (category_id,)
            )
            rows = self.cursor.fetchall()
            return [
                {
                    'sku_id': row[0],
                    'product_name': row[1],
                    'pack_size': row[2]
                }
                for row in rows
            ]
        except sqlite3.Error as e:
            logger.error(f"Failed to get existing products for category {category_id}: {e}")
            return []


    def export_master_csv(self, output_path: Path) -> int:
        """
        Export the entire dmart_product_master table to a master CSV file.
        
        Args:
            output_path: Path object where the CSV should be saved.
            
        Returns:
            Number of rows exported.
        """
        try:
            # Query all columns in order
            self.cursor.execute("""
                SELECT 
                    sku_id, product_name, brand, pack_size, mrp, 
                    dmart_price, availability, product_url, image_url, description, category_name 
                FROM dmart_product_master
            """)
            rows = self.cursor.fetchall()
            
            if not rows:
                logger.warning("No data in database to export to Master CSV.")
                return 0
                
            # Column headers matching the SELECT statement
            headers = [
                'sku_id', 'product_name', 'brand', 'pack_size', 'mrp', 
                'dmart_price', 'availability', 'product_url', 'image_url', 'description', 'category_name'
            ]
            
            with open(output_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(headers)
                writer.writerows(rows)
                
            logger.info(f"Master CSV successfully exported: {output_path} ({len(rows)} rows)")
            return len(rows)
            
        except Exception as e:
            logger.error(f"Failed to export master CSV: {e}")
            return 0

    def get_stats(self) -> dict:
        """Return a summary of database statistics."""
        return {
            'total_products': self.get_product_count(),
            'total_categories': self.get_category_count(),
            'db_size_mb': round(
                self.db_path.stat().st_size / (1024 * 1024), 2
            ) if self.db_path.exists() else 0,
        }
