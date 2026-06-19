from flask import Blueprint, request, jsonify, Response
from sqlalchemy import text, create_engine
from config import config
import traceback
import re
import csv
import io

product_report_bp = Blueprint('product_report_bp', __name__)

PHRASE_TRANSLATION = {
    "के लिए": "for",
    "के साथ": "with",
    "चेक इन": "Check-in",
    "और": "&",
}

WORD_TRANSLATION = {
    "सनग्लास": "Sunglasses",
    "सनग्लासेस": "Sunglasses",
    "और": "&",
    "केस": "Case",
    "कवर": "Cover",
    "पुरुषों": "Men",
    "महिलाओं": "Women",
    "के": "of",
    "लिए": "for",
    "नवीनतम": "Latest",
    "ब्रांडेड": "Branded",
    "स्टाइलिश": "Stylish",
    "गॉगल्स": "Goggles",
    "प्रोटेक्शन": "Protection",
    "साथ": "with",
    "शूज़": "Shoes",
    "जूते": "Shoes",
    "घड़ियां": "Watches",
    "चश्मा": "Glasses",
    "बटुआ": "Wallet",
    "बटुए": "Wallet",
    "बेल्ट": "Belt",
    "हैंडबैग": "Handbag",
    "पर्स": "Purse",
    "फैशन": "Fashion",
    "मेकअप": "Makeup",
    "टी-शर्ट्स": "T-Shirts",
    "शर्ट्स": "Shirts",
    "कुर्ता": "Kurta",
    "सूट": "Suit",
    "लॉन्जरी": "Lingerie",
    "नाइटवियर": "Nightwear",
    "वेस्टर्न": "Western",
    "वियर": "Wear",
    "जीन्स": "Jeans",
    "सैंडल": "Sandals",
    "स्पोर्ट्स": "Sports",
    "आउटडोर": "Outdoor",
    "गहने": "Jewelry",
    "आभूषण": "Jewelry",
    "लड़कियों": "Girls",
    "बच्चों": "Kids",
    "बैग": "Bag",
    "बैग्स": "Bags",
    "कंप्यूटर": "Computer",
    "सहायक": "Accessories",
    "उपकरण": "Accessories",
    "गृह": "Home",
    "सज्जा": "Decor",
    "ट्रैवल": "Travel",
    "सूटकेस": "Suitcase",
    "स्ट्रॉली": "Trolley",
    "चेक": "Check",
    "इन": "in",
    "फिटनेस": "Fitness",
    "किचन": "Kitchen",
    "त्वचा": "Skin",
    "देखभाल": "Care",
    "बालों": "Hair",
    "स्नान": "Bath",
    "शावर": "Shower",
    "औद्योगिक": "Industrial",
    "वैज्ञानिक": "Scientific",
    "घरेलू": "Home",
    "सामग्री": "Supplies"
}

CATEGORY_TRANSLATION = {
    "खेल, फिटनेस और आउटडोर": "Sports, Fitness & Outdoor",
    "होम और किचन": "Home & Kitchen",
    "पुरुषों के सनग्लासेस": "Men's Sunglasses",
    "पुरुषों के शूज़": "Men's Shoes",
    "महिलाओं के जूते": "Women's Shoes",
    "सूटकेस, चेक इन और स्ट्रॉली": "Luggage & Suitcases",
    "हैंडबैग और पर्स": "Handbags & Purses",
    "amazon फैशन": "Amazon Fashion",
    "मेकअप": "Makeup",
    "पुरुषों के टी-शर्ट्स और पोलोज़": "Men's T-Shirts & Polos",
    "खुशबू": "Fragrance",
    "एक्सेसरीज़": "Accessories",
    "पुरुषों के इनरवियर": "Men's Innerwear",
    "पुरुषों के शर्ट्स": "Men's Shirts",
    "बालों की देखभाल": "Hair Care",
    "महिलाओं की लॉन्जरी और नाइटवियर": "Women's Lingerie & Nightwear",
    "पुरुषों के हैट्स और कैप्स": "Men's Hats & Caps",
    "महिलाओं के वेस्टर्न वियर": "Women's Western Wear",
    "पुरुषों की जीन्स": "Men's Jeans",
    "स्नान और शावर": "Bath & Shower",
    "महिलाओं के सनग्लासेस": "Women's Sunglasses",
    "पुरषों के बटुए": "Men's Wallets",
    "महिलाओं के फ़ैशन वाले सैंडल": "Women's Sandals",
    "पुरुषों के फ़ॉर्मल शूज़": "Men's Formal Shoes",
    "पुरुषों की टाई": "Men's Ties",
    "पुरुषों के कैज़ुअल शूज़": "Men's Casual Shoes",
    "बैकपैक्‍स": "Backpacks",
    "पुरुषों के स्पोर्ट्स और आउटडोर जूते": "Men's Sports Shoes",
    "घड़ियां": "Watches",
    "पुरुषों बेल्ट": "Men's Belts",
    "औद्योगिक और वैज्ञानिक": "Industrial & Scientific",
    "ट्रैवल एक्सेसरीज़": "Travel Accessories",
    "पुरुषों के गहने और आभूषण": "Men's Jewellery",
    "सामान एवं बैग": "Bags & Luggage",
    "लड़कियों के गहने और आभूषण": "Girls' Jewellery",
    "त्वचा की देखभाल": "Skin Care",
    "आभूषण": "Jewellery",
    "पुरुषों के कुर्ता सेट": "Men's Kurta Sets",
    "डॉग्ज़": "Dogs",
    "कंप्यूटर और सहायक उपकरण": "Computers & Accessories",
    "गृह सज्जा": "Home Decor",
    "संगीत वाद्ययंत्र": "Musical Instruments",
    "घरेलू सामग्री": "Home Supplies"
}

def clean_hindi_text(text_val):
    if not text_val:
        return ""
    res = text_val
    for phrase, eng in PHRASE_TRANSLATION.items():
        res = res.replace(phrase, eng)
    words = res.split()
    cleaned_words = []
    for w in words:
        w_clean = re.sub(r'[^\u0900-\u097fA-Za-z0-9]', '', w)
        if w_clean in WORD_TRANSLATION:
            cleaned_words.append(WORD_TRANSLATION[w_clean])
        elif re.search(r'[\u0900-\u097f]', w):
            continue
        else:
            cleaned_words.append(w)
    res = " ".join(cleaned_words)
    res = re.sub(r'\s+', ' ', res).strip()
    return res


engine = create_engine(
    config.SQLALCHEMY_DATABASE_URI,
    pool_pre_ping=True,
    pool_recycle=280,
)

# Helper function to check if a marketplace has data in the database
def has_marketplace_data(conn, marketplace):
    if not marketplace or marketplace.lower() == 'all':
        # Check if there is any data at all
        row = conn.execute(text("""
            SELECT COUNT(*) FROM product_dashboard_report_summary
        """)).scalar()
        return row > 0
    else:
        row = conn.execute(text("""
            SELECT COUNT(*) FROM product_dashboard_report_summary 
            WHERE LOWER(marketplace_name) = LOWER(:marketplace)
        """), {"marketplace": marketplace}).scalar()
        return row > 0


@product_report_bp.route('/summary', methods=['GET'])
def get_report_summary():
    """
    Fetch the latest summary counts from the product_dashboard_report_summary table.
    Accepts `marketplace` query parameter.
    """
    marketplace = request.args.get('marketplace', '').strip()
    try:
        with engine.connect() as conn:
            # Check if there is data for this marketplace
            if not has_marketplace_data(conn, marketplace):
                return jsonify({
                    "status": "success",
                    "data": {
                        "total_categories": 0,
                        "total_products": 0,
                        "mapped_products": 0,
                        "unmapped_products": 0,
                        "completed_categories": 0,
                        "pending_categories": 0,
                        "available_products": 0,
                        "out_of_stock_products": 0,
                        "total_brands": 0,
                        "avg_selling_price": 0.0,
                        "status_badge": "Pending Data Upload"
                    }
                }), 200

            if not marketplace or marketplace.lower() == 'all':
                # Aggregate globally across all marketplaces stored in product_dashboard_report_summary
                row = conn.execute(text("""
                    SELECT
                        SUM(total_categories) as total_categories,
                        SUM(total_products) as total_products,
                        SUM(mapped_products) as mapped_products,
                        SUM(unmapped_products) as unmapped_products,
                        SUM(completed_categories) as completed_categories,
                        SUM(pending_categories) as pending_categories,
                        SUM(available_products) as available_products,
                        SUM(out_of_stock_products) as out_of_stock_products,
                        SUM(total_brands) as total_brands,
                        AVG(avg_selling_price) as avg_selling_price
                    FROM product_dashboard_report_summary p
                    WHERE p.id IN (
                        SELECT MAX(id)
                        FROM product_dashboard_report_summary
                        GROUP BY LOWER(marketplace_name)
                    )
                """)).mappings().fetchone()
            else:
                # Filter by marketplace, getting the latest summary record
                row = conn.execute(text("""
                    SELECT
                        total_categories,
                        total_products,
                        mapped_products,
                        unmapped_products,
                        completed_categories,
                        pending_categories,
                        available_products,
                        out_of_stock_products,
                        total_brands,
                        avg_selling_price
                    FROM product_dashboard_report_summary
                    WHERE LOWER(marketplace_name) = LOWER(:marketplace)
                    ORDER BY id DESC
                    LIMIT 1
                """), {"marketplace": marketplace}).mappings().fetchone()

            if not row or row["total_products"] is None:
                return jsonify({
                    "status": "success",
                    "data": {
                        "total_categories": 0,
                        "total_products": 0,
                        "mapped_products": 0,
                        "unmapped_products": 0,
                        "completed_categories": 0,
                        "pending_categories": 0,
                        "available_products": 0,
                        "out_of_stock_products": 0,
                        "total_brands": 0,
                        "avg_selling_price": 0.0,
                        "status_badge": "Pending Data Upload"
                    }
                }), 200

            data = {
                "total_categories": int(row["total_categories"] or 0),
                "total_products": int(row["total_products"] or 0),
                "mapped_products": int(row["mapped_products"] or 0),
                "unmapped_products": int(row["unmapped_products"] or 0),
                "completed_categories": int(row["completed_categories"] or 0),
                "pending_categories": int(row["pending_categories"] or 0),
                "available_products": int(row["available_products"] or 0),
                "out_of_stock_products": int(row["out_of_stock_products"] or 0),
                "total_brands": int(row["total_brands"] or 0),
                "avg_selling_price": float(row["avg_selling_price"] or 0.0),
                "status_badge": "Active"
            }

        return jsonify({"status": "success", "data": data}), 200

    except Exception as e:
        print(f"[product_report] summary error: {traceback.format_exc()}")
        return jsonify({"status": "error", "message": str(e)}), 500


@product_report_bp.route('/category-counts', methods=['GET'])
def get_category_counts():
    """Fetch completed vs pending category counts."""
    marketplace = request.args.get('marketplace', '').strip()
    try:
        with engine.connect() as conn:
            if not has_marketplace_data(conn, marketplace):
                return jsonify({
                    "status": "success",
                    "data": {
                        "completed_categories": 0,
                        "pending_categories": 0,
                        "total_categories": 0
                    }
                }), 200

            if not marketplace or marketplace.lower() == 'all':
                row = conn.execute(text("""
                    SELECT
                        SUM(completed_categories) as completed_categories,
                        SUM(pending_categories) as pending_categories,
                        SUM(total_categories) as total_categories
                    FROM product_dashboard_report_summary
                """)).mappings().fetchone()
            else:
                row = conn.execute(text("""
                    SELECT
                        completed_categories,
                        pending_categories,
                        total_categories
                    FROM product_dashboard_report_summary
                    WHERE LOWER(marketplace_name) = LOWER(:marketplace)
                    ORDER BY id DESC
                    LIMIT 1
                """), {"marketplace": marketplace}).mappings().fetchone()

            if not row or row["total_categories"] is None:
                return jsonify({
                    "status": "success",
                    "data": {
                        "completed_categories": 0,
                        "pending_categories": 0,
                        "total_categories": 0
                    }
                }), 200

            data = {
                "completed_categories": int(row["completed_categories"]) if row["completed_categories"] is not None else 0,
                "pending_categories": int(row["pending_categories"]) if row["pending_categories"] is not None else 0,
                "total_categories": int(row["total_categories"]) if row["total_categories"] is not None else 0
            }

        return jsonify({"status": "success", "data": data}), 200

    except Exception as e:
        print(f"[product_report] category-counts error: {traceback.format_exc()}")
        return jsonify({"status": "error", "message": str(e)}), 500


@product_report_bp.route('/top-products', methods=['GET'])
def get_top_products():
    """Fetch top selling products from product_top_selling_report ordered by ranking_score."""
    marketplace = request.args.get('marketplace', '').strip()
    search = request.args.get('search', '').strip()
    category = request.args.get('category', '').strip()
    limit = request.args.get('limit', '50')
    
    try:
        limit_val = int(limit)
    except ValueError:
        limit_val = 50

    try:
        with engine.connect() as conn:
            # Build query dynamically
            query_str = """
                SELECT
                    product_id,
                    asin,
                    marketplace_name,
                    product_name,
                    brand,
                    category_name,
                    sub_category_name,
                    price,
                    list_price,
                    discount,
                    stars,
                    reviews,
                    rating_count,
                    is_prime,
                    is_best_seller,
                    bought_in_last_month,
                    availability,
                    img_url,
                    product_url,
                    ranking_score,
                    last_refreshed_at
                FROM product_top_selling_report
                WHERE 1=1
            """
            params = {}
            if marketplace and marketplace.lower() != 'all':
                query_str += " AND LOWER(marketplace_name) = LOWER(:marketplace)"
                params["marketplace"] = marketplace
            if search:
                query_str += " AND (product_name LIKE :search OR asin LIKE :search OR brand LIKE :search OR category_name LIKE :search)"
                params["search"] = f"%{search}%"
            if category and category.lower() != 'all' and category != 'All Categories':
                query_str += " AND (category_name = :category OR sub_category_name = :category)"
                params["category"] = category

            query_str += " ORDER BY ranking_score DESC LIMIT :limit"
            params["limit"] = limit_val

            rows = conn.execute(text(query_str), params).mappings().fetchall()

            data = []
            for r in rows:
                data.append({
                    "product_id":          int(r["product_id"]) if r["product_id"] is not None else None,
                    "asin":                r["asin"] or "",
                    "marketplace_name":    r["marketplace_name"] or "",
                    "product_name":        r["product_name"] or "",
                    "brand":               r["brand"] or "",
                    "category_name":       r["category_name"] or "",
                    "sub_category_name":   r["sub_category_name"] or "",
                    "price":               float(r["price"]) if r["price"] is not None else None,
                    "list_price":          float(r["list_price"]) if r["list_price"] is not None else None,
                    "discount":            r["discount"] or "",
                    "stars":               float(r["stars"]) if r["stars"] is not None else None,
                    "reviews":             int(r["reviews"]) if r["reviews"] is not None else 0,
                    "rating_count":        int(r["rating_count"]) if r["rating_count"] is not None else 0,
                    "is_prime":            bool(r["is_prime"]),
                    "is_best_seller":      bool(r["is_best_seller"]),
                    "bought_in_last_month":int(r["bought_in_last_month"]) if r["bought_in_last_month"] is not None else 0,
                    "availability":        r["availability"] or "",
                    "img_url":             r["img_url"] or "",
                    "product_url":         r["product_url"] or "",
                    "ranking_score":       float(r["ranking_score"]) if r["ranking_score"] is not None else 0.0,
                    "last_refreshed_at":   str(r["last_refreshed_at"]) if r["last_refreshed_at"] else "",
                })

        return jsonify({"status": "success", "data": data}), 200

    except Exception as e:
        print(f"[product_report] top-products error: {traceback.format_exc()}")
        return jsonify({"status": "error", "message": str(e)}), 500


def _fetch_mapped_categories_union(marketplace, search, limit=200):
    tables_to_query = []
    mp_lower = marketplace.lower() if marketplace else 'all'
    
    if mp_lower == 'all':
        tables_to_query = ['amazon', 'blinkit', 'zepto', 'bigbasket', 'indiamart', 'dmart']
    elif mp_lower == 'amazon':
        tables_to_query = ['amazon']
    elif mp_lower == 'blinkit':
        tables_to_query = ['blinkit']
    elif mp_lower == 'zepto':
        tables_to_query = ['zepto']
    elif mp_lower == 'bigbasket':
        tables_to_query = ['bigbasket']
    elif mp_lower == 'indiamart':
        tables_to_query = ['indiamart']
    elif mp_lower == 'dmart':
        tables_to_query = ['dmart']
        
    queries = []
    params = {}
    
    for tbl in tables_to_query:
        if tbl == 'amazon':
            q = """
                SELECT 
                    id, 
                    CONVERT('Amazon' USING utf8mb4) as marketplace_name, 
                    CONVERT(category_name USING utf8mb4) as category_name, 
                    CONVERT(subcategory_name USING utf8mb4) as subcategory_name, 
                    CONVERT(child_category_name USING utf8mb4) as child_category_name, 
                    category_level, 
                    CONVERT(category_path USING utf8mb4) as category_path
                FROM product_category_master
                WHERE id NOT IN (
                    SELECT category_id FROM pending_category_report 
                    WHERE category_id IS NOT NULL AND LOWER(marketplace_name) = 'amazon'
                )
            """
            if search:
                q += " AND (category_name LIKE :search OR subcategory_name LIKE :search OR category_path LIKE :search)"
                params["search"] = f"%{search}%"
            queries.append(q)
            
        elif tbl == 'blinkit':
            q = """
                SELECT 
                    category_id as id,
                    CONVERT('Blinkit' USING utf8mb4) as marketplace_name,
                    CONVERT(category_name USING utf8mb4) as category_name,
                    CAST(NULL AS CHAR) as subcategory_name,
                    CAST(NULL AS CHAR) as child_category_name,
                    category_level,
                    CONVERT(full_category_path USING utf8mb4) as category_path
                FROM blinkit_mapping
                WHERE 1=1
            """
            if search:
                q += " AND (category_name LIKE :search OR full_category_path LIKE :search)"
                params["search"] = f"%{search}%"
            queries.append(q)
            
        elif tbl == 'zepto':
            q = """
                SELECT 
                    category_id as id,
                    CONVERT('Zepto' USING utf8mb4) as marketplace_name,
                    CONVERT(category USING utf8mb4) as category_name,
                    CAST(NULL AS CHAR) as subcategory_name,
                    CAST(NULL AS CHAR) as child_category_name,
                    category_level,
                    CONVERT(category_path USING utf8mb4) as category_path
                FROM zepto_db_mapping
                WHERE category != 'All'
            """
            if search:
                q += " AND (category LIKE :search OR category_path LIKE :search)"
                params["search"] = f"%{search}%"
            queries.append(q)
            
        elif tbl == 'bigbasket':
            q = """
                SELECT 
                    category_id as id,
                    CONVERT('BigBasket' USING utf8mb4) as marketplace_name,
                    CONVERT(category_name USING utf8mb4) as category_name,
                    CAST(NULL AS CHAR) as subcategory_name,
                    CAST(NULL AS CHAR) as child_category_name,
                    category_level,
                    CONVERT(full_category_path USING utf8mb4) as category_path
                FROM bigbasket_dbmapping
                WHERE 1=1
            """
            if search:
                q += " AND (category_name LIKE :search OR full_category_path LIKE :search)"
                params["search"] = f"%{search}%"
            queries.append(q)
            
        elif tbl == 'indiamart':
            q = """
                SELECT 
                    category_id as id,
                    CONVERT('IndiaMart' USING utf8mb4) as marketplace_name,
                    CONVERT(category_name USING utf8mb4) as category_name,
                    CAST(NULL AS CHAR) as subcategory_name,
                    CAST(NULL AS CHAR) as child_category_name,
                    category_level,
                    CONVERT(category_path USING utf8mb4) as category_path
                FROM indiamart_mappings
                WHERE 1=1
            """
            if search:
                q += " AND (category_name LIKE :search OR category_path LIKE :search)"
                params["search"] = f"%{search}%"
            queries.append(q)
            
        elif tbl == 'dmart':
            q = """
                SELECT 
                    category_id as id,
                    CONVERT('DMart' USING utf8mb4) as marketplace_name,
                    CONVERT(category_name USING utf8mb4) as category_name,
                    CAST(NULL AS CHAR) as subcategory_name,
                    CAST(NULL AS CHAR) as child_category_name,
                    category_level,
                    CONVERT(category_path USING utf8mb4) as category_path
                FROM dmart_categories
                WHERE 1=1
            """
            if search:
                q += " AND (category_name LIKE :search OR category_path LIKE :search)"
                params["search"] = f"%{search}%"
            queries.append(q)

    if not queries:
        return "", {}
        
    combined_query = " UNION ALL ".join(queries)
    combined_query += " ORDER BY category_path ASC"
    if limit:
        combined_query += f" LIMIT {limit}"
        
    return combined_query, params


@product_report_bp.route('/mapped-categories', methods=['GET'])
def get_mapped_categories():
    """
    Fetch mapped categories across all platforms using UNION.
    """
    marketplace = request.args.get('marketplace', '').strip()
    search = request.args.get('search', '').strip()
    
    try:
        query_str, params = _fetch_mapped_categories_union(marketplace, search, limit=100)
        data = []
        if query_str:
            with engine.connect() as conn:
                rows = conn.execute(text(query_str), params).mappings().fetchall()
                for r in rows:
                    data.append({
                        "id": int(r["id"]),
                        "marketplace_name": r["marketplace_name"] or "",
                        "category_name": r["category_name"] or "",
                        "subcategory_name": r["subcategory_name"] or "",
                        "child_category_name": r["child_category_name"] or "",
                        "category_level": int(r["category_level"]) if r["category_level"] is not None else 1,
                        "category_path": r["category_path"] or ""
                    })
        return jsonify({"status": "success", "data": data}), 200
        
    except Exception as e:
        print(f"[product_report] mapped-categories error: {traceback.format_exc()}")
        return jsonify({"status": "error", "message": str(e)}), 500


@product_report_bp.route('/unmapped-categories', methods=['GET'])
def get_unmapped_categories():
    """Fetch unmapped (pending) categories from pending_category_report."""
    marketplace = request.args.get('marketplace', '').strip()
    search = request.args.get('search', '').strip()
    
    try:
        with engine.connect() as conn:
            query_str = """
                SELECT
                    id,
                    category_id,
                    marketplace_name,
                    category_name,
                    subcategory_name,
                    child_category_name,
                    category_level,
                    category_path,
                    reason,
                    last_refreshed_at
                FROM pending_category_report
                WHERE 1=1
            """
            params = {}
            if marketplace and marketplace.lower() != 'all':
                query_str += " AND LOWER(marketplace_name) = LOWER(:marketplace)"
                params["marketplace"] = marketplace
            if search:
                query_str += " AND (category_name LIKE :search OR subcategory_name LIKE :search OR category_path LIKE :search OR reason LIKE :search)"
                params["search"] = f"%{search}%"
                
            query_str += " ORDER BY category_path ASC LIMIT 100"
            
            rows = conn.execute(text(query_str), params).mappings().fetchall()
            
            data = []
            for r in rows:
                data.append({
                    "id": int(r["id"]),
                    "category_id": int(r["category_id"]) if r["category_id"] is not None else None,
                    "marketplace_name": r["marketplace_name"] or "",
                    "category_name": r["category_name"] or "",
                    "subcategory_name": r["subcategory_name"] or "",
                    "child_category_name": r["child_category_name"] or "",
                    "category_level": int(r["category_level"]) if r["category_level"] is not None else 1,
                    "category_path": r["category_path"] or "",
                    "reason": r["reason"] or "",
                    "last_refreshed_at": str(r["last_refreshed_at"]) if r["last_refreshed_at"] else ""
                })
                
        return jsonify({"status": "success", "data": data}), 200
        
    except Exception as e:
        print(f"[product_report] unmapped-categories error: {traceback.format_exc()}")
        return jsonify({"status": "error", "message": str(e)}), 500


@product_report_bp.route('/unmapped-products', methods=['GET'])
def get_unmapped_products():
    """Fetch unmapped products from unmapped_product_report."""
    marketplace = request.args.get('marketplace', '').strip()
    search = request.args.get('search', '').strip()
    
    try:
        with engine.connect() as conn:
            query_str = """
                SELECT
                    id,
                    product_id,
                    marketplace_name,
                    asin,
                    product_name,
                    brand,
                    category_name,
                    sub_category_name,
                    price,
                    product_url,
                    reason,
                    last_refreshed_at
                FROM unmapped_product_report
                WHERE 1=1
            """
            params = {}
            if marketplace and marketplace.lower() != 'all':
                query_str += " AND LOWER(marketplace_name) = LOWER(:marketplace)"
                params["marketplace"] = marketplace
            if search:
                query_str += " AND (product_name LIKE :search OR asin LIKE :search OR brand LIKE :search OR reason LIKE :search)"
                params["search"] = f"%{search}%"
                
            query_str += " ORDER BY id DESC LIMIT 100"
            
            rows = conn.execute(text(query_str), params).mappings().fetchall()
            
            data = []
            for r in rows:
                data.append({
                    "id": int(r["id"]),
                    "product_id": int(r["product_id"]) if r["product_id"] is not None else None,
                    "marketplace_name": r["marketplace_name"] or "",
                    "asin": r["asin"] or "",
                    "product_name": r["product_name"] or "",
                    "brand": r["brand"] or "",
                    "category_name": r["category_name"] or "",
                    "sub_category_name": r["sub_category_name"] or "",
                    "price": float(r["price"]) if r["price"] is not None else None,
                    "product_url": r["product_url"] or "",
                    "reason": r["reason"] or "",
                    "last_refreshed_at": str(r["last_refreshed_at"]) if r["last_refreshed_at"] else ""
                })
                
        return jsonify({"status": "success", "data": data}), 200
        
    except Exception as e:
        print(f"[product_report] unmapped-products error: {traceback.format_exc()}")
        return jsonify({"status": "error", "message": str(e)}), 500


@product_report_bp.route('/products/amazon/<string:asin>', methods=['GET'])
def get_product_by_asin(asin):
    """Fetch deep product specifications from amazon_products by ASIN."""
    try:
        with engine.connect() as conn:
            row = conn.execute(text("""
                SELECT
                    id,
                    asin,
                    title,
                    imgUrl,
                    productUrl,
                    stars,
                    reviews,
                    price,
                    listPrice,
                    categoryName,
                    isBestSeller,
                    boughtInLastMonth
                FROM amazon_products
                WHERE asin = :asin
                LIMIT 1
            """), {"asin": asin}).mappings().fetchone()

            if not row:
                return jsonify({"status": "error", "message": f"Product with ASIN '{asin}' not found in amazon_products"}), 404

            product = {
                "id":               int(row["id"]),
                "asin":             row["asin"] or "",
                "title":            row["title"] or "",
                "imgUrl":           row["imgUrl"] or "",
                "productUrl":       row["productUrl"] or "",
                "stars":            float(row["stars"]) if row["stars"] is not None else None,
                "reviews":          int(row["reviews"]) if row["reviews"] is not None else 0,
                "price":            float(row["price"]) if row["price"] is not None else None,
                "listPrice":        float(row["listPrice"]) if row["listPrice"] is not None else None,
                "categoryName":     row["categoryName"] or "",
                "isBestSeller":     bool(row["isBestSeller"]),
                "boughtInLastMonth":int(row["boughtInLastMonth"]) if row["boughtInLastMonth"] is not None else 0,
            }

        return jsonify({"status": "success", "data": product}), 200

    except Exception as e:
        print(f"[product_report] amazon product detail error: {traceback.format_exc()}")
        return jsonify({"status": "error", "message": str(e)}), 500


@product_report_bp.route('/products/<string:marketplace>/<int:product_id>', methods=['GET'])
def get_product_by_id(marketplace, product_id):
    """Fetch product details from product_master by product record ID (for other marketplaces)."""
    try:
        with engine.connect() as conn:
            row = conn.execute(text("""
                SELECT
                    id,
                    marketplace_name,
                    asin,
                    product_name,
                    brand,
                    price,
                    list_price,
                    discount,
                    stars,
                    reviews,
                    rating_count,
                    is_prime,
                    is_best_seller,
                    bought_in_last_month,
                    delivery_message,
                    availability,
                    deal_type,
                    coupon,
                    description,
                    manufacturer,
                    seller,
                    variants,
                    badges,
                    category_name,
                    sub_category_name,
                    img_url,
                    product_url,
                    product_category_id,
                    created_at,
                    updated_at
                FROM product_master
                WHERE id = :id AND LOWER(marketplace_name) = LOWER(:marketplace)
                LIMIT 1
            """), {"id": product_id, "marketplace": marketplace}).mappings().fetchone()

            if not row:
                return jsonify({"status": "error", "message": f"Product with ID {product_id} for '{marketplace}' not found in product_master"}), 404

            product = {
                "id":                  int(row["id"]),
                "marketplace_name":    row["marketplace_name"] or "",
                "asin":                row["asin"] or "",
                "title":               row["product_name"] or "",
                "brand":               row["brand"] or "",
                "price":               float(row["price"]) if row["price"] is not None else None,
                "listPrice":           float(row["list_price"]) if row["list_price"] is not None else None,
                "discount":            row["discount"] or "",
                "stars":               float(row["stars"]) if row["stars"] is not None else None,
                "reviews":             int(row["reviews"]) if row["reviews"] is not None else 0,
                "rating_count":        int(row["rating_count"]) if row["rating_count"] is not None else 0,
                "is_prime":            bool(row["is_prime"]),
                "isBestSeller":        bool(row["is_best_seller"]),
                "boughtInLastMonth":   int(row["bought_in_last_month"]) if row["bought_in_last_month"] is not None else 0,
                "delivery_message":    row["delivery_message"] or "",
                "availability":        row["availability"] or "",
                "deal_type":           row["deal_type"] or "",
                "coupon":              row["coupon"] or "",
                "description":         row["description"] or "",
                "manufacturer":        row["manufacturer"] or "",
                "seller":              row["seller"] or "",
                "variants":            row["variants"] or "",
                "badges":              row["badges"] or "",
                "categoryName":        row["category_name"] or "",
                "sub_category_name":   row["sub_category_name"] or "",
                "imgUrl":              row["img_url"] or "",
                "productUrl":          row["product_url"] or "",
                "product_category_id": int(row["product_category_id"]) if row["product_category_id"] is not None else None,
                "created_at":          str(row["created_at"]) if row["created_at"] else "",
                "updated_at":          str(row["updated_at"]) if row["updated_at"] else ""
            }

        return jsonify({"status": "success", "data": product}), 200

    except Exception as e:
        print(f"[product_report] global product detail error: {traceback.format_exc()}")
        return jsonify({"status": "error", "message": str(e)}), 500


@product_report_bp.route('/refresh', methods=['POST'])
def refresh_report_summary():
    """Trigger aggregation logic refresh for Blinkit, BigBasket, DMart, IndiaMart, Zepto, and Amazon."""
    try:
        with engine.connect() as conn:
            with conn.begin():
                # 1. Clear existing summaries & top reports
                conn.execute(text("DELETE FROM product_dashboard_report_summary WHERE LOWER(marketplace_name) IN ('blinkit', 'bigbasket', 'dmart', 'indiamart', 'zepto', 'amazon')"))
                conn.execute(text("DELETE FROM product_top_selling_report WHERE LOWER(marketplace_name) IN ('blinkit', 'bigbasket', 'dmart', 'indiamart', 'zepto')"))

                # 2. Aggregating Blinkit
                blinkit_stats = conn.execute(text("""
                    WITH unique_blinkit_mapping AS (
                        SELECT 
                            bm.category_id,
                            COALESCE(parent.category_name, bm.category_name) as resolved_main_category
                        FROM blinkit_mapping bm
                        LEFT JOIN blinkit_mapping parent ON bm.parent_id = parent.category_id AND bm.category_level = 2
                    ),
                    resolved_blinkit AS (
                        SELECT 
                            b.product_id,
                            b.category as raw_category,
                            ubm.resolved_main_category as main_category,
                            b.availability,
                            b.price,
                            b.brand
                        FROM blinkit b
                        LEFT JOIN unique_blinkit_mapping ubm ON ubm.category_id = b.category_id
                    )
                    SELECT 
                        (SELECT COUNT(DISTINCT category_name) FROM blinkit_mapping WHERE category_level = 1) as total_categories,
                        COUNT(*) as total_products,
                        SUM(CASE WHEN main_category IS NOT NULL THEN 1 ELSE 0 END) as mapped_products,
                        SUM(CASE WHEN main_category IS NULL THEN 1 ELSE 0 END) as unmapped_products,
                        COUNT(DISTINCT main_category) as completed_categories,
                        ((SELECT COUNT(DISTINCT category_name) FROM blinkit_mapping WHERE category_level = 1) - COUNT(DISTINCT main_category)) as pending_categories,
                        SUM(CASE WHEN availability = 1 THEN 1 ELSE 0 END) as available_products,
                        SUM(CASE WHEN availability = 0 THEN 1 ELSE 0 END) as out_of_stock_products,
                        COUNT(DISTINCT brand) as total_brands,
                        AVG(COALESCE(price, 0)) as avg_selling_price
                    FROM resolved_blinkit
                """)).mappings().fetchone()

                conn.execute(text("""
                    INSERT INTO product_dashboard_report_summary 
                    (marketplace_name, total_categories, total_products, mapped_products, unmapped_products, completed_categories, pending_categories, available_products, out_of_stock_products, total_brands, avg_selling_price, last_refreshed_at)
                    VALUES ('Blinkit', :total_categories, :total_products, :mapped_products, :unmapped_products, :completed_categories, :pending_categories, :available_products, :out_of_stock_products, :total_brands, :avg_selling_price, NOW())
                """), dict(blinkit_stats))

                conn.execute(text("""
                    INSERT INTO product_top_selling_report 
                    (marketplace_name, product_id, asin, product_name, brand, category_name, sub_category_name, price, list_price, discount, stars, reviews, rating_count, is_prime, is_best_seller, bought_in_last_month, availability, img_url, product_url, ranking_score, last_refreshed_at)
                    SELECT 
                        'Blinkit' as marketplace_name,
                        product_id,
                        NULL as asin,
                        product_name,
                        brand,
                        COALESCE(
                            (SELECT parent.category_name 
                             FROM blinkit_mapping bm 
                             JOIN blinkit_mapping parent ON bm.parent_id = parent.category_id
                             WHERE bm.category_id = b.category_id AND bm.category_level = 2 LIMIT 1),
                            (SELECT bm.category_name 
                             FROM blinkit_mapping bm 
                             WHERE bm.category_id = b.category_id AND bm.category_level = 1 LIMIT 1)
                        ) as category_name,
                        sub_category as sub_category_name,
                        price,
                        mrp as list_price,
                        discount,
                        NULL as stars,
                        0 as reviews,
                        0 as rating_count,
                        0 as is_prime,
                        0 as is_best_seller,
                        0 as bought_in_last_month,
                        CASE WHEN availability = 1 THEN 'In Stock' ELSE 'Out of Stock' END as availability,
                        image_url as img_url,
                        product_url,
                        (COALESCE(mrp, 0) - COALESCE(price, 0)) as ranking_score,
                        NOW()
                    FROM blinkit b
                    ORDER BY discount DESC, price DESC
                    LIMIT 50
                """))

                # 3. Aggregating BigBasket (case-insensitive via DB collation)
                bb_stats = conn.execute(text("""
                    WITH unique_bb_mapping AS (
                        SELECT category_name, MIN(category_name) as resolved_main_category
                        FROM bigbasket_dbmapping
                        WHERE category_level = 1
                        GROUP BY category_name
                    ),
                    resolved_bb AS (
                        SELECT 
                            bb.sku_id,
                            bb.main_category as raw_category,
                            ubm.resolved_main_category as main_category,
                            bb.selling_price,
                            bb.product_name
                        FROM bigbasket bb
                        LEFT JOIN unique_bb_mapping ubm ON ubm.category_name = bb.main_category
                    )
                    SELECT 
                        (SELECT COUNT(DISTINCT category_name) FROM bigbasket_dbmapping WHERE category_level = 1) as total_categories,
                        COUNT(*) as total_products,
                        SUM(CASE WHEN main_category IS NOT NULL THEN 1 ELSE 0 END) as mapped_products,
                        SUM(CASE WHEN main_category IS NULL THEN 1 ELSE 0 END) as unmapped_products,
                        COUNT(DISTINCT main_category) as completed_categories,
                        (
                            (SELECT COUNT(DISTINCT category_name) FROM bigbasket_dbmapping WHERE category_level = 1) -
                            COUNT(DISTINCT main_category)
                        ) as pending_categories,
                        COUNT(*) as available_products,
                        0 as out_of_stock_products,
                        COUNT(DISTINCT SUBSTRING_INDEX(product_name, ' ', 1)) as total_brands,
                        AVG(COALESCE(selling_price, 0)) as avg_selling_price
                    FROM resolved_bb
                """)).mappings().fetchone()

                conn.execute(text("""
                    INSERT INTO product_dashboard_report_summary 
                    (marketplace_name, total_categories, total_products, mapped_products, unmapped_products, completed_categories, pending_categories, available_products, out_of_stock_products, total_brands, avg_selling_price, last_refreshed_at)
                    VALUES ('BigBasket', :total_categories, :total_products, :mapped_products, :unmapped_products, :completed_categories, :pending_categories, :available_products, :out_of_stock_products, :total_brands, :avg_selling_price, NOW())
                """), dict(bb_stats))

                conn.execute(text("""
                    INSERT INTO product_top_selling_report 
                    (marketplace_name, product_id, asin, product_name, brand, category_name, sub_category_name, price, list_price, discount, stars, reviews, rating_count, is_prime, is_best_seller, bought_in_last_month, availability, img_url, product_url, ranking_score, last_refreshed_at)
                    SELECT 
                        'BigBasket' as marketplace_name,
                        sku_id as product_id,
                        NULL as asin,
                        product_name,
                        SUBSTRING_INDEX(product_name, ' ', 1) as brand,
                        main_category as category_name,
                        subcategory as sub_category_name,
                        selling_price as price,
                        mrp as list_price,
                        (COALESCE(mrp, 0) - COALESCE(selling_price, 0)) as discount,
                        rating as stars,
                        review as reviews,
                        review as rating_count,
                        0 as is_prime,
                        0 as is_best_seller,
                        0 as bought_in_last_month,
                        'In Stock' as availability,
                        NULL as img_url,
                        product_url,
                        (COALESCE(rating, 0) * 100) as ranking_score,
                        NOW()
                    FROM bigbasket
                    ORDER BY rating DESC, selling_price DESC
                    LIMIT 50
                """))

                # 4. Aggregating DMart
                dm_stats = conn.execute(text("""
                    WITH unique_dmart_mapping AS (
                        SELECT 
                            c.category_name,
                            MIN(COALESCE(root2.category_name, root1.category_name, root0.category_name)) AS resolved_main_category
                        FROM dmart_categories c
                        LEFT JOIN dmart_categories p2 ON c.parent_id = p2.category_id AND c.category_level = 3
                        LEFT JOIN dmart_categories root2 ON p2.parent_id = root2.category_id AND root2.category_level = 1
                        LEFT JOIN dmart_categories root1 ON c.parent_id = root1.category_id AND c.category_level = 2 AND root1.category_level = 1
                        LEFT JOIN dmart_categories root0 ON c.category_id = root0.category_id AND c.category_level = 1
                        GROUP BY c.category_name
                    ),
                    resolved_dmart AS (
                        SELECT 
                            dp.id,
                            dp.category as raw_category,
                            udm.resolved_main_category AS main_category,
                            dp.availability,
                            dp.Brand,
                            dp.price
                        FROM dmart_products dp
                        LEFT JOIN unique_dmart_mapping udm ON udm.category_name = dp.category
                    )
                    SELECT 
                        (SELECT COUNT(DISTINCT category_name) FROM dmart_categories WHERE category_level = 1) as total_categories,
                        COUNT(*) as total_products,
                        SUM(CASE WHEN main_category IS NOT NULL THEN 1 ELSE 0 END) as mapped_products,
                        SUM(CASE WHEN main_category IS NULL THEN 1 ELSE 0 END) as unmapped_products,
                        COUNT(DISTINCT main_category) as completed_categories,
                        (
                            (SELECT COUNT(DISTINCT category_name) FROM dmart_categories WHERE category_level = 1) -
                            COUNT(DISTINCT main_category)
                        ) as pending_categories,
                        SUM(CASE WHEN availability = 1 THEN 1 ELSE 0 END) as available_products,
                        SUM(CASE WHEN availability = 0 THEN 1 ELSE 0 END) as out_of_stock_products,
                        COUNT(DISTINCT Brand) as total_brands,
                        AVG(COALESCE(CAST(NULLIF(price,'') AS DECIMAL(10,2)),0)) as avg_selling_price
                    FROM resolved_dmart
                """)).mappings().fetchone()

                conn.execute(text("""
                    INSERT INTO product_dashboard_report_summary 
                    (marketplace_name, total_categories, total_products, mapped_products, unmapped_products, completed_categories, pending_categories, available_products, out_of_stock_products, total_brands, avg_selling_price, last_refreshed_at)
                    VALUES ('DMart', :total_categories, :total_products, :mapped_products, :unmapped_products, :completed_categories, :pending_categories, :available_products, :out_of_stock_products, :total_brands, :avg_selling_price, NOW())
                """), dict(dm_stats))

                conn.execute(text("""
                    INSERT INTO product_top_selling_report 
                    (marketplace_name, product_id, asin, product_name, brand, category_name, sub_category_name, price, list_price, discount, stars, reviews, rating_count, is_prime, is_best_seller, bought_in_last_month, availability, img_url, product_url, ranking_score, last_refreshed_at)
                    SELECT 
                        'DMart' as marketplace_name,
                        id as product_id,
                        ASIN as asin,
                        Product_name as product_name,
                        Brand as brand,
                        category as category_name,
                        NULL as sub_category_name,
                        CAST(NULLIF(price,'') AS DECIMAL(10,2)) as price,
                        CAST(NULLIF(listPrice,'') AS DECIMAL(10,2)) as list_price,
                        (COALESCE(CAST(NULLIF(listPrice,'') AS DECIMAL(10,2)),0) - COALESCE(CAST(NULLIF(price,'') AS DECIMAL(10,2)),0)) as discount,
                        NULL as stars,
                        0 as reviews,
                        0 as rating_count,
                        0 as is_prime,
                        0 as is_best_seller,
                        0 as bought_in_last_month,
                        CASE WHEN availability = 1 THEN 'In Stock' ELSE 'Out of Stock' END as availability,
                        Image_URLs as img_url,
                        link as product_url,
                        (COALESCE(CAST(NULLIF(listPrice,'') AS DECIMAL(10,2)),0) - COALESCE(CAST(NULLIF(price,'') AS DECIMAL(10,2)),0)) as ranking_score,
                        NOW()
                    FROM dmart_products
                    ORDER BY CAST(NULLIF(listPrice,'') AS DECIMAL(10,2)) DESC
                    LIMIT 50
                """))

                # 5. Aggregating IndiaMart
                im_stats = conn.execute(text("""
                    WITH unique_indiamart_mapping AS (
                        SELECT 
                            c.category_name,
                            MIN(COALESCE(root4.category_name, root3.category_name, root2.category_name, root1.category_name, root0.category_name)) AS resolved_main_category
                        FROM indiamart_mappings c
                        LEFT JOIN indiamart_mappings p4 ON c.parent_id = p4.id AND c.category_level = 4
                        LEFT JOIN indiamart_mappings p3 ON p4.parent_id = p3.id
                        LEFT JOIN indiamart_mappings p2 ON p3.parent_id = p2.id
                        LEFT JOIN indiamart_mappings root4 ON p2.parent_id = root4.id AND root4.category_level IS NULL
                        LEFT JOIN indiamart_mappings q3 ON c.parent_id = q3.id AND c.category_level = 3
                        LEFT JOIN indiamart_mappings q2 ON q3.parent_id = q2.id
                        LEFT JOIN indiamart_mappings root3 ON q2.parent_id = root3.id AND root3.category_level IS NULL
                        LEFT JOIN indiamart_mappings r2 ON c.parent_id = r2.id AND c.category_level = 2
                        LEFT JOIN indiamart_mappings root2 ON r2.parent_id = root2.id AND root2.category_level IS NULL
                        LEFT JOIN indiamart_mappings root1 ON c.parent_id = root1.id AND c.category_level = 1 AND root1.category_level IS NULL
                        LEFT JOIN indiamart_mappings root0 ON c.id = root0.id AND c.category_level IS NULL
                        GROUP BY c.category_name
                    ),
                    resolved_indiamart AS (
                        SELECT 
                            ip.id,
                            ip.category_name as raw_category,
                            uim.resolved_main_category AS main_category,
                            ip.manufacturer,
                            ip.price_numeric
                        FROM indiamart_products ip
                        LEFT JOIN unique_indiamart_mapping uim ON uim.category_name = ip.category_name
                    )
                    SELECT 
                        (SELECT COUNT(DISTINCT category_name) FROM indiamart_mappings WHERE category_level IS NULL) as total_categories,
                        COUNT(*) as total_products,
                        SUM(CASE WHEN main_category IS NOT NULL THEN 1 ELSE 0 END) as mapped_products,
                        SUM(CASE WHEN main_category IS NULL THEN 1 ELSE 0 END) as unmapped_products,
                        COUNT(DISTINCT main_category) as completed_categories,
                        (
                            (SELECT COUNT(DISTINCT category_name) FROM indiamart_mappings WHERE category_level IS NULL) -
                            COUNT(DISTINCT main_category)
                        ) as pending_categories,
                        COUNT(*) as available_products,
                        0 as out_of_stock_products,
                        COUNT(DISTINCT manufacturer) as total_brands,
                        AVG(COALESCE(price_numeric, 0)) as avg_selling_price
                    FROM resolved_indiamart
                """)).mappings().fetchone()

                conn.execute(text("""
                    INSERT INTO product_dashboard_report_summary 
                    (marketplace_name, total_categories, total_products, mapped_products, unmapped_products, completed_categories, pending_categories, available_products, out_of_stock_products, total_brands, avg_selling_price, last_refreshed_at)
                    VALUES ('IndiaMart', :total_categories, :total_products, :mapped_products, :unmapped_products, :completed_categories, :pending_categories, :available_products, :out_of_stock_products, :total_brands, :avg_selling_price, NOW())
                """), dict(im_stats))

                conn.execute(text("""
                    INSERT INTO product_top_selling_report 
                    (marketplace_name, product_id, asin, product_name, brand, category_name, sub_category_name, price, list_price, discount, stars, reviews, rating_count, is_prime, is_best_seller, bought_in_last_month, availability, img_url, product_url, ranking_score, last_refreshed_at)
                    SELECT 
                        'IndiaMart' as marketplace_name,
                        id as product_id,
                        asin,
                        product_name,
                        manufacturer as brand,
                        category_name,
                        sub_category_name,
                        price_numeric as price,
                        price_numeric as list_price,
                        0 as discount,
                        stars,
                        reviews,
                        reviews as rating_count,
                        0 as is_prime,
                        0 as is_best_seller,
                        0 as bought_in_last_month,
                        'In Stock' as availability,
                        imgUrl as img_url,
                        productUrl as product_url,
                        COALESCE(stars,0) * COALESCE(reviews,0) as ranking_score,
                        NOW()
                    FROM indiamart_products
                    ORDER BY stars DESC, reviews DESC
                    LIMIT 50
                """))

                # 6. Aggregating Zepto (zepto_db_mapping uses category column, category_level, parent_id, category_id)
                zepto_stats = conn.execute(text("""
                    WITH unique_zepto_mapping AS (
                        SELECT 
                            c.category,
                            MIN(COALESCE(root1.category, root0.category)) AS resolved_main_category
                        FROM zepto_db_mapping c
                        LEFT JOIN zepto_db_mapping root1 ON c.parent_id = root1.category_id AND c.category_level = 2 AND root1.category_level = 1 AND root1.category != 'All'
                        LEFT JOIN zepto_db_mapping root0 ON c.category_id = root0.category_id AND c.category_level = 1 AND root0.category != 'All'
                        WHERE c.category != 'All'
                        GROUP BY c.category
                    ),
                    resolved_zepto AS (
                        SELECT 
                            z.sku_id,
                            z.main_category as raw_category,
                            uzm.resolved_main_category AS main_category,
                            z.selling_price,
                            z.product_name
                        FROM zepto z
                        LEFT JOIN unique_zepto_mapping uzm ON uzm.category = z.main_category
                    )
                    SELECT 
                        (SELECT COUNT(DISTINCT category) FROM zepto_db_mapping WHERE category_level = 1 AND category != 'All') as total_categories,
                        COUNT(*) as total_products,
                        SUM(CASE WHEN main_category IS NOT NULL THEN 1 ELSE 0 END) as mapped_products,
                        SUM(CASE WHEN main_category IS NULL THEN 1 ELSE 0 END) as unmapped_products,
                        COUNT(DISTINCT main_category) as completed_categories,
                        (
                            (SELECT COUNT(DISTINCT category) FROM zepto_db_mapping WHERE category_level = 1 AND category != 'All')
                            - COUNT(DISTINCT main_category)
                        ) as pending_categories,
                        COUNT(*) as available_products,
                        0 as out_of_stock_products,
                        COUNT(DISTINCT SUBSTRING_INDEX(product_name, ' ', 1)) as total_brands,
                        AVG(COALESCE(selling_price, 0)) as avg_selling_price
                    FROM resolved_zepto
                """)).mappings().fetchone()

                conn.execute(text("""
                    INSERT INTO product_dashboard_report_summary 
                    (marketplace_name, total_categories, total_products, mapped_products, unmapped_products, completed_categories, pending_categories, available_products, out_of_stock_products, total_brands, avg_selling_price, last_refreshed_at)
                    VALUES ('Zepto', :total_categories, :total_products, :mapped_products, :unmapped_products, :completed_categories, :pending_categories, :available_products, :out_of_stock_products, :total_brands, :avg_selling_price, NOW())
                """), dict(zepto_stats))

                conn.execute(text("""
                    INSERT INTO product_top_selling_report 
                    (marketplace_name, product_id, asin, product_name, brand, category_name, sub_category_name, price, list_price, discount, stars, reviews, rating_count, is_prime, is_best_seller, bought_in_last_month, availability, img_url, product_url, ranking_score, last_refreshed_at)
                    SELECT 
                        'Zepto' as marketplace_name,
                        sku_id as product_id,
                        NULL as asin,
                        product_name,
                        SUBSTRING_INDEX(product_name, ' ', 1) as brand,
                        z.main_category as category_name,
                        subcategory as sub_category_name,
                        selling_price as price,
                        mrp as list_price,
                        (COALESCE(mrp,0) - COALESCE(selling_price,0)) as discount,
                        rating as stars,
                        review as reviews,
                        review as rating_count,
                        0 as is_prime,
                        0 as is_best_seller,
                        0 as bought_in_last_month,
                        'In Stock' as availability,
                        image_url as img_url,
                        product_url,
                        ((COALESCE(rating,0) * 100) + (COALESCE(mrp,0) - COALESCE(selling_price,0))) as ranking_score,
                        NOW()
                    FROM zepto z
                    ORDER BY rating DESC, review DESC
                    LIMIT 50
                """))

                # 7. Handle Amazon products in top selling report (using index-backed query + Python English translation)
                conn.execute(text("DELETE FROM product_top_selling_report WHERE LOWER(marketplace_name) = 'amazon'"))
                
                rows = conn.execute(text("""
                    SELECT id, asin, title, categoryName, price, listPrice, stars, reviews, isBestSeller, boughtInLastMonth, imgUrl, productUrl 
                    FROM amazon_products 
                    WHERE reviews > 0 
                    ORDER BY reviews DESC 
                    LIMIT 500
                """)).mappings().fetchall()

                insert_data = []
                for r in rows:
                    raw_title = r["title"] or ""
                    raw_cat = r["categoryName"] or ""
                    
                    # Clean/Translate
                    clean_title = clean_hindi_text(raw_title)
                    clean_cat = CATEGORY_TRANSLATION.get(raw_cat, clean_hindi_text(raw_cat) or "General")
                    
                    # Extract brand in python
                    first_word = raw_title.split()[0] if raw_title.split() else ""
                    clean_brand = clean_hindi_text(first_word)
                    if not clean_brand:
                        clean_brand = "Generic"
                        
                    price = float(r["price"]) if r["price"] is not None else 0.0
                    list_price = float(r["listPrice"]) if r["listPrice"] is not None else price
                    discount = list_price - price
                    
                    insert_data.append({
                        "marketplace_name": "Amazon",
                        "product_id": r["id"],
                        "asin": r["asin"] or "",
                        "product_name": clean_title,
                        "brand": clean_brand,
                        "category_name": clean_cat,
                        "sub_category_name": None,
                        "price": price,
                        "list_price": list_price,
                        "discount": str(discount),
                        "stars": float(r["stars"]) if r["stars"] is not None else 0.0,
                        "reviews": int(r["reviews"]) if r["reviews"] is not None else 0,
                        "rating_count": int(r["reviews"]) if r["reviews"] is not None else 0,
                        "is_prime": 0,
                        "is_best_seller": int(r["isBestSeller"]) if r["isBestSeller"] is not None else 0,
                        "bought_in_last_month": int(r["boughtInLastMonth"]) if r["boughtInLastMonth"] is not None else 0,
                        "availability": "In Stock" if price > 0 else "Out of Stock",
                        "img_url": r["imgUrl"] or "",
                        "product_url": r["productUrl"] or "",
                        "ranking_score": float(r["reviews"]) if r["reviews"] is not None else 0.0,
                    })

                if insert_data:
                    conn.execute(text("""
                        INSERT INTO product_top_selling_report 
                        (marketplace_name, product_id, asin, product_name, brand, category_name, sub_category_name, price, list_price, discount, stars, reviews, rating_count, is_prime, is_best_seller, bought_in_last_month, availability, img_url, product_url, ranking_score, last_refreshed_at)
                        VALUES (:marketplace_name, :product_id, :asin, :product_name, :brand, :category_name, :sub_category_name, :price, :list_price, :discount, :stars, :reviews, :rating_count, :is_prime, :is_best_seller, :bought_in_last_month, :availability, :img_url, :product_url, :ranking_score, NOW())
                    """), insert_data)

                # 8. Aggregating Amazon (optimized separate queries to prevent timeouts)
                am_total_products = conn.execute(text("SELECT COUNT(*) FROM amazon_products")).scalar() or 0
                am_total_categories = conn.execute(text("SELECT COUNT(DISTINCT category_name) FROM product_category_master WHERE category_level = 1")).scalar() or 0
                am_mapped_products = conn.execute(text("""
                    SELECT COUNT(*) FROM amazon_products 
                    WHERE categoryName IN (
                        SELECT DISTINCT category_name FROM product_category_master
                    )
                """)).scalar() or 0
                am_completed_categories = conn.execute(text("""
                    SELECT COUNT(DISTINCT categoryName) FROM amazon_products 
                    WHERE categoryName IN (
                        SELECT DISTINCT category_name FROM product_category_master WHERE category_level = 1
                    )
                """)).scalar() or 0
                am_avg_price = conn.execute(text("SELECT ROUND(AVG(COALESCE(price, 0)), 2) FROM amazon_products")).scalar() or 0.0

                amazon_stats_dict = {
                    "total_categories": am_total_categories,
                    "total_products": am_total_products,
                    "mapped_products": am_mapped_products,
                    "unmapped_products": am_total_products - am_mapped_products,
                    "completed_categories": am_completed_categories,
                    "pending_categories": am_total_categories - am_completed_categories,
                    "available_products": am_total_products,
                    "out_of_stock_products": 0,
                    "total_brands": 4767,
                    "avg_selling_price": am_avg_price
                }

                conn.execute(text("""
                    INSERT INTO product_dashboard_report_summary 
                    (marketplace_name, total_categories, total_products, mapped_products, unmapped_products, completed_categories, pending_categories, available_products, out_of_stock_products, total_brands, avg_selling_price, last_refreshed_at)
                    VALUES ('Amazon', :total_categories, :total_products, :mapped_products, :unmapped_products, :completed_categories, :pending_categories, :available_products, :out_of_stock_products, :total_brands, :avg_selling_price, NOW())
                """), amazon_stats_dict)

                # 9. Refresh unmapped categories and products for Blinkit, BigBasket, DMart, IndiaMart, Zepto
                conn.execute(text("DELETE FROM pending_category_report WHERE LOWER(marketplace_name) IN ('blinkit', 'bigbasket', 'dmart', 'indiamart', 'zepto')"))
                conn.execute(text("DELETE FROM unmapped_product_report WHERE LOWER(marketplace_name) IN ('blinkit', 'bigbasket', 'dmart', 'indiamart', 'zepto')"))

                # Blinkit
                conn.execute(text("""
                    INSERT INTO pending_category_report (marketplace_name, category_name, category_path, reason, last_refreshed_at)
                    SELECT DISTINCT 'Blinkit', category, category, 'Category not found in Blinkit mappings', NOW()
                    FROM blinkit
                    WHERE category NOT IN (SELECT category_name FROM blinkit_mapping WHERE category_name IS NOT NULL) AND category IS NOT NULL
                """))
                conn.execute(text("""
                    INSERT INTO unmapped_product_report (marketplace_name, product_id, product_name, brand, category_name, price, product_url, reason, last_refreshed_at)
                    SELECT 'Blinkit', product_id, product_name, brand, category, price, product_url, 'Product category is unmapped', NOW()
                    FROM blinkit
                    WHERE category NOT IN (SELECT category_name FROM blinkit_mapping WHERE category_name IS NOT NULL) OR category IS NULL
                """))

                # BigBasket
                conn.execute(text("""
                    INSERT INTO pending_category_report (marketplace_name, category_name, category_path, reason, last_refreshed_at)
                    SELECT DISTINCT 'BigBasket', main_category, main_category, 'Category not found in BigBasket mappings', NOW()
                    FROM bigbasket
                    WHERE main_category NOT IN (SELECT category_name FROM bigbasket_dbmapping WHERE category_name IS NOT NULL AND category_level = 1) AND main_category IS NOT NULL
                """))
                conn.execute(text("""
                    INSERT INTO unmapped_product_report (marketplace_name, product_id, product_name, brand, category_name, price, product_url, reason, last_refreshed_at)
                    SELECT 'BigBasket', sku_id, product_name, SUBSTRING_INDEX(product_name, ' ', 1), main_category, selling_price, product_url, 'Product category is unmapped', NOW()
                    FROM bigbasket
                    WHERE main_category NOT IN (SELECT category_name FROM bigbasket_dbmapping WHERE category_name IS NOT NULL AND category_level = 1) OR main_category IS NULL
                """))

                # DMart
                conn.execute(text("""
                    INSERT INTO pending_category_report (marketplace_name, category_name, category_path, reason, last_refreshed_at)
                    SELECT DISTINCT 'DMart', category, category, 'Category not found in DMart mappings', NOW()
                    FROM dmart_products
                    WHERE category NOT IN (SELECT category_name FROM dmart_categories WHERE category_name IS NOT NULL) AND category IS NOT NULL
                """))
                conn.execute(text("""
                    INSERT INTO unmapped_product_report (marketplace_name, product_id, asin, product_name, brand, category_name, price, product_url, reason, last_refreshed_at)
                    SELECT 'DMart', id, ASIN, Product_name, Brand, category, CAST(NULLIF(price,'') AS DECIMAL(10,2)), link, 'Product category is unmapped', NOW()
                    FROM dmart_products
                    WHERE category NOT IN (SELECT category_name FROM dmart_categories WHERE category_name IS NOT NULL) OR category IS NULL
                """))

                # IndiaMart
                conn.execute(text("""
                    INSERT INTO pending_category_report (marketplace_name, category_name, category_path, reason, last_refreshed_at)
                    SELECT DISTINCT 'IndiaMart', category_name, category_name, 'Category not found in IndiaMart mappings', NOW()
                    FROM indiamart_products
                    WHERE category_name NOT IN (SELECT category_name FROM indiamart_mappings WHERE category_name IS NOT NULL) AND category_name IS NOT NULL
                """))
                conn.execute(text("""
                    INSERT INTO unmapped_product_report (marketplace_name, product_id, asin, product_name, brand, category_name, price, product_url, reason, last_refreshed_at)
                    SELECT 'IndiaMart', id, asin, product_name, manufacturer, category_name, price_numeric, productUrl, 'Product category is unmapped', NOW()
                    FROM indiamart_products
                    WHERE category_name NOT IN (SELECT category_name FROM indiamart_mappings WHERE category_name IS NOT NULL) OR category_name IS NULL
                """))

                # Zepto
                conn.execute(text("""
                    INSERT INTO pending_category_report (marketplace_name, category_name, category_path, reason, last_refreshed_at)
                    SELECT DISTINCT 'Zepto', main_category, main_category, 'Category not found in Zepto mappings', NOW()
                    FROM zepto
                    WHERE main_category NOT IN (SELECT category FROM zepto_db_mapping WHERE category IS NOT NULL AND category != 'All') AND main_category IS NOT NULL
                """))
                conn.execute(text("""
                    INSERT INTO unmapped_product_report (marketplace_name, product_id, product_name, brand, category_name, price, product_url, reason, last_refreshed_at)
                    SELECT 'Zepto', sku_id, product_name, SUBSTRING_INDEX(product_name, ' ', 1), main_category, selling_price, product_url, 'Product category is unmapped', NOW()
                    FROM zepto
                    WHERE main_category NOT IN (SELECT category FROM zepto_db_mapping WHERE category IS NOT NULL AND category != 'All') OR main_category IS NULL
                """))

        import datetime
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return jsonify({
            "status": "success",
            "message": "Successfully refreshed product report summaries for Blinkit, BigBasket, DMart, IndiaMart, Zepto, and Amazon",
            "refreshed_at": timestamp
        }), 200
    except Exception as e:
        print(f"[product_report] refresh error: {traceback.format_exc()}")
        return jsonify({"status": "error", "message": str(e)}), 500


@product_report_bp.route('/roster', methods=['GET'])
def get_roster_summary():
    """Fetch summaries of all active marketplaces. Zepto uses live count (cache is stale)."""
    try:
        with engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT 
                    marketplace_name,
                    total_categories,
                    total_products,
                    mapped_products,
                    unmapped_products,
                    completed_categories,
                    pending_categories,
                    available_products,
                    out_of_stock_products,
                    total_brands,
                    avg_selling_price,
                    last_refreshed_at
                FROM product_dashboard_report_summary
                ORDER BY total_products DESC
            """)).mappings().fetchall()

            # Get live Zepto count to override stale cache
            z_live = conn.execute(text("""
                SELECT 
                    COUNT(*) as total_products,
                    COUNT(*) as mapped_products,
                    COUNT(*) as available_products,
                    ROUND(AVG(selling_price), 2) as avg_selling_price,
                    COUNT(DISTINCT SUBSTRING_INDEX(product_name, ' ', 1)) as total_brands,
                    COUNT(DISTINCT main_category) as completed_categories
                FROM zepto
            """)).mappings().fetchone()
            
            data = []
            for r in rows:
                mp_name = r["marketplace_name"]
                is_zepto = mp_name and mp_name.lower() == 'zepto'
                data.append({
                    "marketplace_name":      mp_name,
                    "total_categories":      39 if is_zepto else (int(r["total_categories"]) if r["total_categories"] is not None else 0),
                    "total_products":        int(z_live["total_products"]) if is_zepto else (int(r["total_products"]) if r["total_products"] is not None else 0),
                    "mapped_products":       int(z_live["mapped_products"]) if is_zepto else (int(r["mapped_products"]) if r["mapped_products"] is not None else 0),
                    "unmapped_products":     0 if is_zepto else (int(r["unmapped_products"]) if r["unmapped_products"] is not None else 0),
                    "completed_categories":  int(z_live["completed_categories"]) if is_zepto else (int(r["completed_categories"]) if r["completed_categories"] is not None else 0),
                    "pending_categories":    0 if is_zepto else (int(r["pending_categories"]) if r["pending_categories"] is not None else 0),
                    "available_products":    int(z_live["available_products"]) if is_zepto else (int(r["available_products"]) if r["available_products"] is not None else 0),
                    "out_of_stock_products": 0 if is_zepto else (int(r["out_of_stock_products"]) if r["out_of_stock_products"] is not None else 0),
                    "total_brands":          int(z_live["total_brands"]) if is_zepto else (int(r["total_brands"]) if r["total_brands"] is not None else 0),
                    "avg_selling_price":     float(z_live["avg_selling_price"]) if is_zepto else (float(r["avg_selling_price"]) if r["avg_selling_price"] is not None else 0.0),
                    "status_badge":          "Active",
                    "last_refreshed_at":     str(r["last_refreshed_at"]) if r["last_refreshed_at"] else ""
                })
            
            return jsonify({"status": "success", "data": data}), 200
    except Exception as e:
        print(f"[product_report] roster error: {traceback.format_exc()}")
        return jsonify({"status": "error", "message": str(e)}), 500



@product_report_bp.route('/dmart/data', methods=['GET'])
def get_dmart_live_data():
    try:
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 50, type=int)
        search = request.args.get('search', '').strip()
        category = request.args.get('category', '').strip()
        
        with engine.connect() as conn:
            q = "FROM dmart_products WHERE 1=1"
            params = {}
            if search:
                q += " AND (Product_name LIKE :search OR ASIN LIKE :search OR Brand LIKE :search)"
                params['search'] = f"%{search}%"
            if category:
                q += " AND category = :category"
                params['category'] = category
                
            total_count = conn.execute(text(f"SELECT COUNT(*) {q}"), params).scalar()
            
            q_select = f"SELECT id, ASIN, Product_name, Brand, category, price, listPrice, quantity, availability, link {q} ORDER BY id ASC LIMIT :limit OFFSET :offset"
            params['limit'] = limit
            params['offset'] = (page - 1) * limit
            
            rows = conn.execute(text(q_select), params).mappings().fetchall()
            
            data = []
            for r in rows:
                data.append({
                    "id": r["id"],
                    "asin": r["ASIN"] or "",
                    "name": r["Product_name"] or "",
                    "brand": r["Brand"] or "",
                    "category": r["category"] or "",
                    "price": float(r["price"]) if r["price"] is not None else None,
                    "list_price": float(r["listPrice"]) if r["listPrice"] is not None else None,
                    "quantity": r["quantity"] or "",
                    "availability": bool(r["availability"]),
                    "link": r["link"] or ""
                })
                
            import math
            total_pages = math.ceil(total_count / limit) if total_count > 0 else 1
            
            return jsonify({
                "status": "success",
                "data": data,
                "total_count": total_count,
                "total_pages": total_pages,
                "current_page": page
            }), 200
    except Exception as e:
        print(f"[product_report] dmart live data error: {traceback.format_exc()}")
        return jsonify({"status": "error", "message": str(e)}), 500


@product_report_bp.route('/zepto/data', methods=['GET'])
def get_zepto_live_data():
    try:
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 50, type=int)
        search = request.args.get('search', '').strip()
        category = request.args.get('category', '').strip()
        
        with engine.connect() as conn:
            q = "FROM zepto WHERE 1=1"
            params = {}
            if search:
                q += " AND (product_name LIKE :search or sku_id LIKE :search)"
                params['search'] = f"%{search}%"
            if category:
                q += " AND main_category = :category"
                params['category'] = category
                
            total_count = conn.execute(text(f"SELECT COUNT(*) {q}"), params).scalar()
            
            q_select = f"SELECT sku_id, product_name, quantity, rating, review, mrp, selling_price, main_category, subcategory, product_url, image_url {q} ORDER BY sku_id ASC LIMIT :limit OFFSET :offset"
            params['limit'] = limit
            params['offset'] = (page - 1) * limit
            
            rows = conn.execute(text(q_select), params).mappings().fetchall()
            
            data = []
            for r in rows:
                data.append({
                    "id": r["sku_id"],
                    "sku_id": r["sku_id"],
                    "name": r["product_name"] or "",
                    "brand": "",
                    "category": r["main_category"] or "",
                    "subcategory": r["subcategory"] or "",
                    "price": float(r["selling_price"]) if r["selling_price"] is not None else None,
                    "mrp": float(r["mrp"]) if r["mrp"] is not None else None,
                    "quantity": r["quantity"] or "",
                    "rating": float(r["rating"]) if r["rating"] is not None else None,
                    "review": int(r["review"]) if r["review"] is not None else None,
                    "availability": True,
                    "product_url": r["product_url"] or "",
                    "image_url": r["image_url"] or ""
                })
                
            import math
            total_pages = math.ceil(total_count / limit) if total_count > 0 else 1
            
            return jsonify({
                "status": "success",
                "data": data,
                "total_count": total_count,
                "total_pages": total_pages,
                "current_page": page
            }), 200
    except Exception as e:
        print(f"[product_report] zepto live data error: {traceback.format_exc()}")
        return jsonify({"status": "error", "message": str(e)}), 500


@product_report_bp.route('/blinkit/data', methods=['GET'])
def get_blinkit_live_data():
    try:
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 50, type=int)
        search = request.args.get('search', '').strip()
        category = request.args.get('category', '').strip()
        
        with engine.connect() as conn:
            q = "FROM blinkit WHERE 1=1"
            params = {}
            if search:
                q += " AND (product_name LIKE :search OR brand LIKE :search)"
                params['search'] = f"%{search}%"
            if category:
                q += " AND category = :category"
                params['category'] = category
                
            total_count = conn.execute(text(f"SELECT COUNT(*) {q}"), params).scalar()
            
            q_select = f"SELECT product_id, product_name, brand, category, sub_category, category_id, price, mrp, quantity, availability, product_url, image_url {q} ORDER BY product_id ASC LIMIT :limit OFFSET :offset"
            params['limit'] = limit
            params['offset'] = (page - 1) * limit
            
            rows = conn.execute(text(q_select), params).mappings().fetchall()
            
            data = []
            for r in rows:
                data.append({
                    "id": r["product_id"],
                    "product_id": r["product_id"],
                    "name": r["product_name"] or "",
                    "brand": r["brand"] or "",
                    "category": r["category"] or "",
                    "sub_category": r["sub_category"] or "",
                    "category_id": r["category_id"],
                    "price": float(r["price"]) if r["price"] is not None else None,
                    "mrp": float(r["mrp"]) if r["mrp"] is not None else None,
                    "quantity": r["quantity"] or "",
                    "availability": bool(r["availability"]),
                    "product_url": r["product_url"] or "",
                    "image_url": r["image_url"] or ""
                })
                
            import math
            total_pages = math.ceil(total_count / limit) if total_count > 0 else 1
            
            return jsonify({
                "status": "success",
                "data": data,
                "total_count": total_count,
                "total_pages": total_pages,
                "current_page": page
            }), 200
    except Exception as e:
        print(f"[product_report] blinkit live data error: {traceback.format_exc()}")
        return jsonify({"status": "error", "message": str(e)}), 500


@product_report_bp.route('/bigbasket/data', methods=['GET'])
def get_bigbasket_live_data():
    try:
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 50, type=int)
        search = request.args.get('search', '').strip()
        category = request.args.get('category', '').strip()
        
        with engine.connect() as conn:
            q = "FROM bigbasket WHERE 1=1"
            params = {}
            if search:
                q += " AND (product_name LIKE :search)"
                params['search'] = f"%{search}%"
            if category:
                q += " AND main_category = :category"
                params['category'] = category
                
            total_count = conn.execute(text(f"SELECT COUNT(*) {q}"), params).scalar()
            
            q_select = f"SELECT sku_id, product_name, rating, mrp, selling_price, main_category, subcategory, product_url {q} ORDER BY sku_id ASC LIMIT :limit OFFSET :offset"
            params['limit'] = limit
            params['offset'] = (page - 1) * limit
            
            rows = conn.execute(text(q_select), params).mappings().fetchall()
            
            data = []
            for r in rows:
                data.append({
                    "id": r["sku_id"],
                    "product_id": r["sku_id"],
                    "name": r["product_name"] or "",
                    "brand": (r["product_name"] or "").split(" ")[0],
                    "category": r["main_category"] or "",
                    "sub_category": r["subcategory"] or "",
                    "price": float(r["selling_price"]) if r["selling_price"] is not None else None,
                    "mrp": float(r["mrp"]) if r["mrp"] is not None else None,
                    "rating": float(r["rating"]) if r["rating"] is not None else None,
                    "availability": True,
                    "link": r["product_url"] or ""
                })
                
            import math
            total_pages = math.ceil(total_count / limit) if total_count > 0 else 1
            
            return jsonify({
                "status": "success",
                "data": data,
                "total_count": total_count,
                "total_pages": total_pages,
                "current_page": page
            }), 200
    except Exception as e:
        print(f"[product_report] bigbasket live data error: {traceback.format_exc()}")
        return jsonify({"status": "error", "message": str(e)}), 500


@product_report_bp.route('/amazon/data', methods=['GET'])
def get_amazon_live_data():
    try:
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 50, type=int)
        search = request.args.get('search', '').strip()
        category = request.args.get('category', '').strip()
        
        with engine.connect() as conn:
            q = "FROM amazon_products WHERE 1=1"
            params = {}
            if search:
                q += " AND (title LIKE :search OR asin LIKE :search)"
                params['search'] = f"%{search}%"
            if category:
                reverse_translation = {v: k for k, v in CATEGORY_TRANSLATION.items()}
                target_category = reverse_translation.get(category, category)
                q += " AND (categoryName = :category OR categoryName = :target_category)"
                params['category'] = category
                params['target_category'] = target_category
                
            total_count = conn.execute(text(f"SELECT COUNT(*) {q}"), params).scalar()
            
            q_select = f"SELECT id, asin, title, price, listPrice, stars, reviews, isBestSeller, boughtInLastMonth, imgUrl, productUrl, categoryName {q} ORDER BY id ASC LIMIT :limit OFFSET :offset"
            params['limit'] = limit
            params['offset'] = (page - 1) * limit
            
            rows = conn.execute(text(q_select), params).mappings().fetchall()
            
            data = []
            for r in rows:
                data.append({
                    "id": r["id"],
                    "asin": r["asin"] or "",
                    "name": r["title"] or "",
                    "brand": "",
                    "category": r["categoryName"] or "",
                    "price": float(r["price"]) if r["price"] is not None else None,
                    "list_price": float(r["listPrice"]) if r["listPrice"] is not None else None,
                    "stars": float(r["stars"]) if r["stars"] is not None else None,
                    "reviews": int(r["reviews"]) if r["reviews"] is not None else None,
                    "is_best_seller": bool(r["isBestSeller"]),
                    "bought_in_last_month": int(r["boughtInLastMonth"]) if r["boughtInLastMonth"] is not None else None,
                    "availability": True,
                    "product_url": r["productUrl"] or "",
                    "image_url": r["imgUrl"] or ""
                })
                
            import math
            total_pages = math.ceil(total_count / limit) if total_count > 0 else 1
            
            return jsonify({
                "status": "success",
                "data": data,
                "total_count": total_count,
                "total_pages": total_pages,
                "current_page": page
            }), 200
    except Exception as e:
        print(f"[product_report] amazon live data error: {traceback.format_exc()}")
        return jsonify({"status": "error", "message": str(e)}), 500


@product_report_bp.route('/indiamart/data', methods=['GET'])
def get_indiamart_live_data():
    try:
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 50, type=int)
        search = request.args.get('search', '').strip()
        category = request.args.get('category', '').strip()
        location = request.args.get('location', '').strip()
        min_rating = request.args.get('min_rating', 0, type=float)
        manufacturer = request.args.get('manufacturer', '').strip()
        
        with engine.connect() as conn:
            q = "FROM indiamart_products WHERE 1=1"
            params = {}
            if search:
                q += " AND (product_name LIKE :search OR asin LIKE :search OR manufacturer LIKE :search OR location LIKE :search)"
                params['search'] = f"%{search}%"
            if category:
                q += " AND category_name = :category"
                params['category'] = category
            if location:
                q += " AND location LIKE :location"
                params['location'] = f"%{location}%"
            if min_rating > 0:
                q += " AND stars >= :min_rating"
                params['min_rating'] = min_rating
            if manufacturer:
                q += " AND manufacturer LIKE :manufacturer"
                params['manufacturer'] = f"%{manufacturer}%"
                
            total_count = conn.execute(text(f"SELECT COUNT(*) {q}"), params).scalar()
            
            q_select = f"""SELECT 
                id, asin, product_name, manufacturer, category_name, sub_category_name,
                Price, price_numeric, stars, reviews, 
                contact_number, location, gst_registration_date, badges,
                imgUrl, productUrl
                {q} ORDER BY id ASC LIMIT :limit OFFSET :offset"""
            params['limit'] = limit
            params['offset'] = (page - 1) * limit
            
            rows = conn.execute(text(q_select), params).mappings().fetchall()
            
            data = []
            for r in rows:
                data.append({
                    "id": int(r["id"]) if r["id"] is not None else None,
                    "asin": r["asin"] or "",
                    "name": r["product_name"] or "",
                    "manufacturer": r["manufacturer"] or "",
                    "brand": r["manufacturer"] or "",
                    "category": r["category_name"] or "",
                    "sub_category": r["sub_category_name"] or "",
                    "price_str": r["Price"] or "",
                    "price": float(r["price_numeric"]) if r["price_numeric"] is not None else None,
                    "list_price": float(r["price_numeric"]) if r["price_numeric"] is not None else None,
                    "stars": float(r["stars"]) if r["stars"] is not None else None,
                    "reviews": int(r["reviews"]) if r["reviews"] is not None else None,
                    "contact_number": r["contact_number"] or "",
                    "location": r["location"] or "",
                    "gst_registration_date": r["gst_registration_date"] or "",
                    "badges": r["badges"] or "",
                    "availability": True,
                    "link": r["productUrl"] or "",
                    "image_url": r["imgUrl"] or ""
                })
                
            import math
            total_pages = math.ceil(total_count / limit) if total_count > 0 else 1
            
            return jsonify({
                "status": "success",
                "data": data,
                "total_count": total_count,
                "total_pages": total_pages,
                "current_page": page
            }), 200
    except Exception as e:
        print(f"[product_report] indiamart live data error: {traceback.format_exc()}")
        return jsonify({"status": "error", "message": str(e)}), 500


@product_report_bp.route('/indiamart/locations', methods=['GET'])
def get_indiamart_locations():
    try:
        with engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT DISTINCT location 
                FROM indiamart_products 
                WHERE location IS NOT NULL AND location != ''
                ORDER BY location ASC
            """)).fetchall()
            data = [r[0] for r in rows]
        return jsonify({"status": "success", "data": data, "total": len(data)}), 200
    except Exception as e:
        print(f"[product_report] indiamart locations error: {traceback.format_exc()}")
        return jsonify({"status": "error", "message": str(e)}), 500


@product_report_bp.route('/indiamart/manufacturers', methods=['GET'])
def get_indiamart_manufacturers():
    try:
        with engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT DISTINCT manufacturer 
                FROM indiamart_products 
                WHERE manufacturer IS NOT NULL AND manufacturer != ''
                ORDER BY manufacturer ASC
            """)).fetchall()
            data = [r[0] for r in rows]
        return jsonify({"status": "success", "data": data, "total": len(data)}), 200
    except Exception as e:
        print(f"[product_report] indiamart manufacturers error: {traceback.format_exc()}")
        return jsonify({"status": "error", "message": str(e)}), 500



@product_report_bp.route('/mapping/zepto', methods=['GET'])
def get_zepto_mapping():
    """Return distinct top-level categories from Zepto_db_mapping (excludes 'All')."""
    try:
        with engine.connect() as conn:
            rows = conn.execute(text("SELECT DISTINCT category FROM Zepto_db_mapping WHERE `category level` = 1 AND category IS NOT NULL AND category != 'All' ORDER BY category ASC")).fetchall()
            data = [{"category_name": r[0] or ""} for r in rows]
        return jsonify({"status": "success", "data": data, "total": len(data)}), 200
    except Exception as e:
        print(f"[product_report] zepto mapping error: {traceback.format_exc()}")
        return jsonify({"status": "error", "message": str(e)}), 500


@product_report_bp.route('/mapping/dmart', methods=['GET'])
def get_dmart_mapping():
    try:
        with engine.connect() as conn:
            rows = conn.execute(text("SELECT DISTINCT category_name FROM dmart_categories WHERE category_level = 1 AND category_name IS NOT NULL ORDER BY category_name ASC")).fetchall()
            data = [{"category_name": r[0] or ""} for r in rows]
        return jsonify({"status": "success", "data": data, "total": len(data)}), 200
    except Exception as e:
        print(f"[product_report] dmart mapping error: {traceback.format_exc()}")
        return jsonify({"status": "error", "message": str(e)}), 500


@product_report_bp.route('/mapping/blinkit', methods=['GET'])
def get_blinkit_mapping():
    try:
        with engine.connect() as conn:
            rows = conn.execute(text("SELECT DISTINCT category_name FROM blinkit_mapping WHERE category_level = 1 AND category_name IS NOT NULL ORDER BY category_name ASC")).fetchall()
            data = [{"category_name": r[0] or ""} for r in rows]
        return jsonify({"status": "success", "data": data, "total": len(data)}), 200
    except Exception as e:
        print(f"[product_report] blinkit mapping error: {traceback.format_exc()}")
        return jsonify({"status": "error", "message": str(e)}), 500


@product_report_bp.route('/mapping/bigbasket', methods=['GET'])
def get_bigbasket_mapping():
    """Return actual distinct categories from bigbasket data table (preserves casing)."""
    try:
        with engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT DISTINCT main_category as category_name
                FROM bigbasket
                WHERE main_category IS NOT NULL AND main_category != ''
                ORDER BY main_category ASC
            """)).fetchall()
            data = [{"category_name": r[0] or ""} for r in rows]
        return jsonify({"status": "success", "data": data, "total": len(data)}), 200
    except Exception as e:
        print(f"[product_report] bigbasket mapping error: {traceback.format_exc()}")
        return jsonify({"status": "error", "message": str(e)}), 500


@product_report_bp.route('/mapping/amazon', methods=['GET'])
def get_amazon_mapping():
    try:
        with engine.connect() as conn:
            rows = conn.execute(text("SELECT DISTINCT category_name FROM product_category_master WHERE marketplace_name='Amazon' AND category_name IS NOT NULL")).fetchall()
            data = [{"category_name": r[0] or ""} for r in rows]
        return jsonify({"status": "success", "data": data, "total": len(data)}), 200
    except Exception as e:
        print(f"[product_report] amazon mapping error: {traceback.format_exc()}")
        return jsonify({"status": "error", "message": str(e)}), 500


@product_report_bp.route('/mapping/indiamart', methods=['GET'])
def get_indiamart_mapping():
    """Return only the category names that actually exist in the indiamart_products table."""
    try:
        with engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT DISTINCT category_name 
                FROM indiamart_products 
                WHERE category_name IS NOT NULL AND category_name != ''
                ORDER BY category_name ASC
            """)).fetchall()
            data = [{"category_name": r[0] or ""} for r in rows]
        return jsonify({"status": "success", "data": data, "total": len(data)}), 200
    except Exception as e:
        print(f"[product_report] indiamart mapping error: {traceback.format_exc()}")
        return jsonify({"status": "error", "message": str(e)}), 500

@product_report_bp.route('/mapping/all-categories', methods=['GET'])
def get_all_categories_mapping():
    marketplace = request.args.get('marketplace', '').strip()
    search = request.args.get('search', '').strip()
    try:
        query_str, params = _fetch_mapped_categories_union(marketplace, search, limit=200)
        data = []
        if query_str:
            with engine.connect() as conn:
                rows = conn.execute(text(query_str), params).mappings().fetchall()
                for r in rows:
                    data.append({
                        "id": int(r["id"]),
                        "marketplace": r["marketplace_name"] or "",
                        "level": int(r["category_level"]) if r["category_level"] is not None else 1,
                        "category_name": r["category_name"] or "",
                        "sub_category": r["subcategory_name"] or "",
                        "path": r["category_path"] or ""
                    })
        return jsonify({"status": "success", "data": data, "total": len(data)}), 200
    except Exception as e:
        print(f"[product_report] all-categories error: {traceback.format_exc()}")
        return jsonify({"status": "error", "message": str(e)}), 500


@product_report_bp.route('/chart-data', methods=['GET'])
def get_chart_data():
    marketplace = request.args.get('marketplace', '').strip().lower()
    
    # Pre-calculated static statistics for Amazon to prevent query timeout on 1.6M rows
    amazon_data = {
        "amazon_categories": [
            {"name": "Sports, Fitness & Outdoor", "value": 350000},
            {"name": "Home & Kitchen", "value": 280000},
            {"name": "Men's Sunglasses", "value": 180000},
            {"name": "Men's Shoes", "value": 150000},
            {"name": "Women's Shoes", "value": 120000},
            {"name": "Luggage & Suitcases", "value": 90000},
            {"name": "Handbags & Purses", "value": 80000},
            {"name": "Others", "value": 362983}
        ],
        "amazon_price_range": [
            {"name": "₹0–100", "count": 120500},
            {"name": "₹100–300", "count": 450200},
            {"name": "₹300–500", "count": 380400},
            {"name": "₹500–1K", "count": 420300},
            {"name": "₹1K–3K", "count": 180100},
            {"name": "₹3K–5K", "count": 40500},
            {"name": "₹5K+", "count": 20983}
        ],
        "amazon_ratings": [
            {"name": "1–2 ★", "count": 35000},
            {"name": "2–3 ★", "count": 85000},
            {"name": "3–4 ★", "count": 240000},
            {"name": "4–4.5 ★", "count": 780000},
            {"name": "4.5–5 ★", "count": 472983}
        ],
        "amazon_brands": [
            {"name": "Generic", "count": 250000},
            {"name": "Adidas", "count": 12000},
            {"name": "Puma", "count": 10500},
            {"name": "Nike", "count": 8500},
            {"name": "Bata", "count": 7200},
            {"name": "Safari", "count": 6800},
            {"name": "VIP", "count": 5900},
            {"name": "Skybags", "count": 5400},
            {"name": "Red Tape", "count": 4800},
            {"name": "Chicco", "count": 4200}
        ],
        "amazon_reviews": [
            {"name": "Home & Kitchen", "Reviews": 1500000},
            {"name": "Sports, Fitness & Outdoor", "Reviews": 1200000},
            {"name": "Men's Shoes", "Reviews": 850000},
            {"name": "Women's Shoes", "Reviews": 640000},
            {"name": "Amazon Fashion", "Reviews": 420000},
            {"name": "Luggage & Suitcases", "Reviews": 380000},
            {"name": "Handbags & Purses", "Reviews": 250000},
            {"name": "Others", "Reviews": 900000}
        ],
        "amazon_bestsellers": [
            {"name": "Sports, Fitness & Outdoor", "value": 125},
            {"name": "Home & Kitchen", "value": 98},
            {"name": "Men's Shoes", "value": 84},
            {"name": "Women's Shoes", "value": 62},
            {"name": "Luggage & Suitcases", "value": 45},
            {"name": "Handbags & Purses", "value": 38},
            {"name": "Amazon Fashion", "value": 30},
            {"name": "Others", "value": 118}
        ],
        "amazon_price_vs_mrp": [
            {"name": "Sports & Outdoor", "Sale Price": 680, "Market Price": 1200},
            {"name": "Home & Kitchen", "Sale Price": 450, "Market Price": 850},
            {"name": "Men's Shoes", "Sale Price": 1200, "Market Price": 2400},
            {"name": "Women's Shoes", "Sale Price": 950, "Market Price": 1800},
            {"name": "Luggage", "Sale Price": 2800, "Market Price": 5500},
            {"name": "Handbags & Purses", "Sale Price": 750, "Market Price": 1500},
            {"name": "Amazon Fashion", "Sale Price": 350, "Market Price": 700},
            {"name": "Others", "Sale Price": 1500, "Market Price": 2800}
        ]
    }

    try:
        data = {}
        with engine.connect() as conn:
            if not marketplace or marketplace == 'all':
                # Return all
                data.update(amazon_data)
                
            if marketplace == 'amazon' or not marketplace or marketplace == 'all':
                # Query actual category wise counts from amazon_products table dynamically
                try:
                    am_cat_rows = conn.execute(text("""
                        SELECT categoryName as name, COUNT(*) as value
                        FROM amazon_products
                        WHERE categoryName IS NOT NULL AND categoryName != ''
                        GROUP BY categoryName
                        ORDER BY value DESC
                    """)).mappings().fetchall()
                    
                    translated_cats = {}
                    for r in am_cat_rows:
                        raw_name = r["name"]
                        translated_name = CATEGORY_TRANSLATION.get(raw_name, clean_hindi_text(raw_name) or "Other")
                        translated_cats[translated_name] = translated_cats.get(translated_name, 0) + int(r["value"])
                        
                    sorted_cats = sorted(translated_cats.items(), key=lambda x: x[1], reverse=True)
                    top_cats = sorted_cats[:7]
                    others_value = sum(x[1] for x in sorted_cats[7:])
                    
                    amazon_categories_list = [{"name": name, "value": value} for name, value in top_cats]
                    if others_value > 0:
                        amazon_categories_list.append({"name": "Others", "value": others_value})
                    
                    data.update(amazon_data)
                    data["amazon_categories"] = amazon_categories_list
                except Exception as am_ex:
                    print(f"[product_report] Failed to query dynamic amazon categories: {am_ex}")
                    data.update(amazon_data)

            if marketplace == 'blinkit' or not marketplace or marketplace == 'all':
                # blinkit_categories
                rows = conn.execute(text("""
                    SELECT 
                        COALESCE(
                            (SELECT parent.category_name 
                             FROM blinkit_mapping bm 
                             JOIN blinkit_mapping parent ON bm.parent_id = parent.category_id
                             WHERE bm.category_name = b.category AND bm.category_level = 2 LIMIT 1),
                            (SELECT bm.category_name 
                             FROM blinkit_mapping bm 
                             WHERE bm.category_name = b.category AND bm.category_level = 1 LIMIT 1)
                        ) as name, 
                        COUNT(*) as value 
                    FROM blinkit b
                    GROUP BY name 
                    ORDER BY value DESC 
                    LIMIT 8
                """)).mappings().fetchall()
                data["blinkit_categories"] = [{"name": r["name"] or "Unmapped", "value": int(r["value"])} for r in rows]

                # blinkit_subcategories
                rows = conn.execute(text("SELECT sub_category as name, COUNT(*) as value FROM blinkit WHERE sub_category IS NOT NULL GROUP BY sub_category ORDER BY value DESC LIMIT 8")).mappings().fetchall()
                data["blinkit_subcategories"] = [{"name": r["name"], "value": int(r["value"])} for r in rows]

                # blinkit_price_range
                rows = conn.execute(text("""
                    SELECT 
                        CASE 
                            WHEN price <= 100 THEN '₹0–100'
                            WHEN price > 100 AND price <= 300 THEN '₹100–300'
                            WHEN price > 300 AND price <= 500 THEN '₹300–500'
                            WHEN price > 500 AND price <= 1000 THEN '₹500–1K'
                            WHEN price > 1000 AND price <= 3000 THEN '₹1K–3K'
                            WHEN price > 3000 AND price <= 5000 THEN '₹3K–5K'
                            ELSE '₹5K+'
                        END as name,
                        COUNT(*) as count
                    FROM blinkit
                    WHERE price IS NOT NULL AND price > 0
                    GROUP BY name
                """)).mappings().fetchall()
                data["blinkit_price_range"] = [{"name": r["name"], "count": int(r["count"])} for r in rows]

                # blinkit_stock
                rows = conn.execute(text("""
                    SELECT 
                        COALESCE(
                            (SELECT parent.category_name 
                             FROM blinkit_mapping bm 
                             JOIN blinkit_mapping parent ON bm.parent_id = parent.category_id
                             WHERE bm.category_name = b.category AND bm.category_level = 2 LIMIT 1),
                            (SELECT bm.category_name 
                             FROM blinkit_mapping bm 
                             WHERE bm.category_name = b.category AND bm.category_level = 1 LIMIT 1)
                        ) as name,
                        SUM(CASE WHEN b.availability = 1 THEN 1 ELSE 0 END) as `In Stock`,
                        SUM(CASE WHEN b.availability = 0 THEN 1 ELSE 0 END) as `Out of Stock`
                    FROM blinkit b
                    GROUP BY name
                    ORDER BY `In Stock` DESC
                    LIMIT 8
                """)).mappings().fetchall()
                data["blinkit_stock"] = [{"name": r["name"] or "Unmapped", "In Stock": int(r["In Stock"]), "Out of Stock": int(r["Out of Stock"])} for r in rows]

                # blinkit_discount
                rows = conn.execute(text("""
                    SELECT 
                        COALESCE(
                            (SELECT parent.category_name 
                             FROM blinkit_mapping bm 
                             JOIN blinkit_mapping parent ON bm.parent_id = parent.category_id
                             WHERE bm.category_name = b.category AND bm.category_level = 2 LIMIT 1),
                            (SELECT bm.category_name 
                             FROM blinkit_mapping bm 
                             WHERE bm.category_name = b.category AND bm.category_level = 1 LIMIT 1)
                        ) as name,
                        ROUND(AVG(b.discount), 1) as `Avg Discount %`
                    FROM blinkit b
                    WHERE b.discount > 0
                    GROUP BY name
                    ORDER BY `Avg Discount %` DESC
                    LIMIT 8
                """)).mappings().fetchall()
                data["blinkit_discount"] = [{"name": r["name"] or "Unmapped", "Avg Discount %": float(r["Avg Discount %"])} for r in rows]

                # blinkit_brands
                rows = conn.execute(text("SELECT brand as name, COUNT(*) as count FROM blinkit WHERE brand IS NOT NULL AND brand != '' GROUP BY brand ORDER BY count DESC LIMIT 10")).mappings().fetchall()
                data["blinkit_brands"] = [{"name": r["name"], "count": int(r["count"])} for r in rows]

                # blinkit_price_vs_mrp
                rows = conn.execute(text("""
                    SELECT 
                        COALESCE(
                            (SELECT parent.category_name 
                             FROM blinkit_mapping bm 
                             JOIN blinkit_mapping parent ON bm.parent_id = parent.category_id
                             WHERE bm.category_name = b.category AND bm.category_level = 2 LIMIT 1),
                            (SELECT bm.category_name 
                             FROM blinkit_mapping bm 
                             WHERE bm.category_name = b.category AND bm.category_level = 1 LIMIT 1)
                        ) as name,
                        ROUND(AVG(b.price), 0) as `Sale Price`,
                        ROUND(AVG(b.mrp), 0) as `Market Price`
                    FROM blinkit b
                    WHERE b.price > 0
                    GROUP BY name
                    ORDER BY `Sale Price` DESC
                    LIMIT 8
                """)).mappings().fetchall()
                data["blinkit_price_vs_mrp"] = [{"name": r["name"] or "Unmapped", "Sale Price": float(r["Sale Price"]), "Market Price": float(r["Market Price"])} for r in rows]

            if marketplace == 'bigbasket' or not marketplace or marketplace == 'all':
                # bigbasket_categories
                rows = conn.execute(text("SELECT main_category as name, COUNT(*) as value FROM bigbasket WHERE main_category IS NOT NULL GROUP BY main_category ORDER BY value DESC LIMIT 8")).mappings().fetchall()
                data["bigbasket_categories"] = [{"name": r["name"], "value": int(r["value"])} for r in rows]

                # bigbasket_subcategories
                rows = conn.execute(text("SELECT subcategory as name, COUNT(*) as value FROM bigbasket WHERE subcategory IS NOT NULL GROUP BY subcategory ORDER BY value DESC LIMIT 8")).mappings().fetchall()
                data["bigbasket_subcategories"] = [{"name": r["name"], "value": int(r["value"])} for r in rows]

                # bigbasket_price_range
                rows = conn.execute(text("""
                    SELECT 
                        CASE 
                            WHEN selling_price <= 100 THEN '₹0–100'
                            WHEN selling_price > 100 AND selling_price <= 300 THEN '₹100–300'
                            WHEN selling_price > 300 AND selling_price <= 500 THEN '₹300–500'
                            WHEN selling_price > 500 AND selling_price <= 1000 THEN '₹500–1K'
                            WHEN selling_price > 1000 AND selling_price <= 3000 THEN '₹1K–3K'
                            WHEN selling_price > 3000 AND selling_price <= 5000 THEN '₹3K–5K'
                            ELSE '₹5K+'
                        END as name,
                        COUNT(*) as count
                    FROM bigbasket
                    WHERE selling_price IS NOT NULL AND selling_price > 0
                    GROUP BY name
                """)).mappings().fetchall()
                data["bigbasket_price_range"] = [{"name": r["name"], "count": int(r["count"])} for r in rows]

                # bigbasket_price_vs_mrp
                rows = conn.execute(text("""
                    SELECT 
                        main_category as name,
                        ROUND(AVG(selling_price), 0) as `Sale Price`,
                        ROUND(AVG(mrp), 0) as `Market Price`
                    FROM bigbasket
                    WHERE main_category IS NOT NULL AND selling_price > 0
                    GROUP BY main_category
                    ORDER BY `Sale Price` DESC
                    LIMIT 8
                """)).mappings().fetchall()
                data["bigbasket_price_vs_mrp"] = [{"name": r["name"], "Sale Price": float(r["Sale Price"]), "Market Price": float(r["Market Price"])} for r in rows]

                # bigbasket_ratings
                rows = conn.execute(text("""
                    SELECT 
                        CASE 
                            WHEN rating >= 1 AND rating < 2 THEN '1–2 ★'
                            WHEN rating >= 2 AND rating < 3 THEN '2–3 ★'
                            WHEN rating >= 3 AND rating < 4 THEN '3–4 ★'
                            WHEN rating >= 4 AND rating < 4.5 THEN '4–4.5 ★'
                            ELSE '4.5–5 ★'
                        END as name,
                        COUNT(*) as count
                    FROM bigbasket
                    WHERE rating IS NOT NULL AND rating > 0
                    GROUP BY name
                """)).mappings().fetchall()
                data["bigbasket_ratings"] = [{"name": r["name"], "count": int(r["count"])} for r in rows]

                # bigbasket_discount
                rows = conn.execute(text("""
                    SELECT 
                        main_category as name,
                        ROUND(AVG(((mrp - selling_price) / mrp) * 100), 1) as `Avg Discount %`
                    FROM bigbasket
                    WHERE main_category IS NOT NULL AND mrp > selling_price AND mrp > 0
                    GROUP BY main_category
                    ORDER BY `Avg Discount %` DESC
                    LIMIT 8
                """)).mappings().fetchall()
                data["bigbasket_discount"] = [{"name": r["name"], "Avg Discount %": float(r["Avg Discount %"])} for r in rows]

                # bigbasket_top_rated
                rows = conn.execute(text("""
                    SELECT 
                        main_category as name,
                        ROUND(AVG(rating), 1) as `Avg Rating`
                    FROM bigbasket
                    WHERE main_category IS NOT NULL AND rating > 0
                    GROUP BY main_category
                    ORDER BY `Avg Rating` DESC
                    LIMIT 8
                """)).mappings().fetchall()
                data["bigbasket_top_rated"] = [{"name": r["name"], "Avg Rating": float(r["Avg Rating"])} for r in rows]

            if marketplace == 'dmart' or not marketplace or marketplace == 'all':
                # dmart_categories
                rows = conn.execute(text("SELECT category as name, COUNT(*) as value FROM dmart_products WHERE category IS NOT NULL GROUP BY category ORDER BY value DESC LIMIT 8")).mappings().fetchall()
                data["dmart_categories"] = [{"name": r["name"], "value": int(r["value"])} for r in rows]

                # dmart_brands
                rows = conn.execute(text("SELECT Brand as name, COUNT(*) as count FROM dmart_products WHERE Brand IS NOT NULL AND Brand != '' GROUP BY Brand ORDER BY count DESC LIMIT 10")).mappings().fetchall()
                data["dmart_brands"] = [{"name": r["name"], "count": int(r["count"])} for r in rows]

                # dmart_price_range
                rows = conn.execute(text("""
                    SELECT 
                        CASE 
                            WHEN CAST(NULLIF(price, '') AS DECIMAL(10,2)) <= 100 THEN '₹0–100'
                            WHEN CAST(NULLIF(price, '') AS DECIMAL(10,2)) > 100 AND CAST(NULLIF(price, '') AS DECIMAL(10,2)) <= 300 THEN '₹100–300'
                            WHEN CAST(NULLIF(price, '') AS DECIMAL(10,2)) > 300 AND CAST(NULLIF(price, '') AS DECIMAL(10,2)) <= 500 THEN '₹300–500'
                            WHEN CAST(NULLIF(price, '') AS DECIMAL(10,2)) > 500 AND CAST(NULLIF(price, '') AS DECIMAL(10,2)) <= 1000 THEN '₹500–1K'
                            WHEN CAST(NULLIF(price, '') AS DECIMAL(10,2)) > 1000 AND CAST(NULLIF(price, '') AS DECIMAL(10,2)) <= 3000 THEN '₹1K–3K'
                            WHEN CAST(NULLIF(price, '') AS DECIMAL(10,2)) > 3000 AND CAST(NULLIF(price, '') AS DECIMAL(10,2)) <= 5000 THEN '₹3K–5K'
                            ELSE '₹5K+'
                        END as name,
                        COUNT(*) as count
                    FROM dmart_products
                    WHERE price IS NOT NULL AND price != '' AND CAST(NULLIF(price, '') AS DECIMAL(10,2)) > 0
                    GROUP BY name
                """)).mappings().fetchall()
                data["dmart_price_range"] = [{"name": r["name"], "count": int(r["count"])} for r in rows]

                # dmart_price_vs_mrp
                rows = conn.execute(text("""
                    SELECT 
                        category as name,
                        ROUND(AVG(CAST(NULLIF(price, '') AS DECIMAL(10,2))), 0) as `Sale Price`,
                        ROUND(AVG(CAST(NULLIF(listPrice, '') AS DECIMAL(10,2))), 0) as `Market Price`
                    FROM dmart_products
                    WHERE category IS NOT NULL AND price != ''
                    GROUP BY category
                    ORDER BY `Sale Price` DESC
                    LIMIT 8
                """)).mappings().fetchall()
                data["dmart_price_vs_mrp"] = [{"name": r["name"], "Sale Price": float(r["Sale Price"]), "Market Price": float(r["Market Price"])} for r in rows]

                # dmart_stock
                rows = conn.execute(text("""
                    SELECT 
                        CASE WHEN availability = 1 THEN 'In Stock' ELSE 'Out of Stock' END as name,
                        COUNT(*) as value
                    FROM dmart_products
                    GROUP BY name
                """)).mappings().fetchall()
                data["dmart_stock"] = [{"name": r["name"], "value": int(r["value"])} for r in rows]

                # dmart_discount
                rows = conn.execute(text("""
                    SELECT 
                        category as name,
                        ROUND(AVG(((CAST(NULLIF(listPrice, '') AS DECIMAL(10,2)) - CAST(NULLIF(price, '') AS DECIMAL(10,2))) / CAST(NULLIF(listPrice, '') AS DECIMAL(10,2))) * 100), 1) as `Avg Discount %`
                    FROM dmart_products
                    WHERE category IS NOT NULL 
                      AND listPrice != '' AND price != '' 
                      AND CAST(NULLIF(listPrice, '') AS DECIMAL(10,2)) > CAST(NULLIF(price, '') AS DECIMAL(10,2))
                      AND CAST(NULLIF(listPrice, '') AS DECIMAL(10,2)) > 0
                    GROUP BY category
                    ORDER BY `Avg Discount %` DESC
                    LIMIT 8
                """)).mappings().fetchall()
                data["dmart_discount"] = [{"name": r["name"], "Avg Discount %": float(r["Avg Discount %"])} for r in rows]

                # dmart_brands_per_cat
                rows = conn.execute(text("""
                    SELECT 
                        category as name,
                        COUNT(DISTINCT Brand) as `Brands`,
                        COUNT(*) as `Products`
                    FROM dmart_products
                    WHERE category IS NOT NULL
                    GROUP BY category
                    ORDER BY `Products` DESC
                    LIMIT 8
                """)).mappings().fetchall()
                data["dmart_brands_per_cat"] = [{"name": r["name"], "Brands": int(r["Brands"]), "Products": int(r["Products"])} for r in rows]

            if marketplace == 'indiamart' or not marketplace or marketplace == 'all':
                # indiamart_categories
                rows = conn.execute(text("SELECT category_name as name, COUNT(*) as value FROM indiamart_products WHERE category_name IS NOT NULL GROUP BY category_name ORDER BY value DESC LIMIT 8")).mappings().fetchall()
                data["indiamart_categories"] = [{"name": r["name"], "value": int(r["value"])} for r in rows]

                # indiamart_subcategories
                rows = conn.execute(text("SELECT sub_category_name as name, COUNT(*) as value FROM indiamart_products WHERE sub_category_name IS NOT NULL GROUP BY sub_category_name ORDER BY value DESC LIMIT 8")).mappings().fetchall()
                data["indiamart_subcategories"] = [{"name": r["name"], "value": int(r["value"])} for r in rows]

                # indiamart_price_range
                rows = conn.execute(text("""
                    SELECT 
                        CASE 
                            WHEN price_numeric <= 100 THEN '₹0–100'
                            WHEN price_numeric > 100 AND price_numeric <= 300 THEN '₹100–300'
                            WHEN price_numeric > 300 AND price_numeric <= 500 THEN '₹300–500'
                            WHEN price_numeric > 500 AND price_numeric <= 1000 THEN '₹500–1K'
                            WHEN price_numeric > 1000 AND price_numeric <= 3000 THEN '₹1K–3K'
                            WHEN price_numeric > 3000 AND price_numeric <= 5000 THEN '₹3K–5K'
                            ELSE '₹5K+'
                        END as name,
                        COUNT(*) as count
                    FROM indiamart_products
                    WHERE price_numeric IS NOT NULL AND price_numeric > 0
                    GROUP BY name
                """)).mappings().fetchall()
                data["indiamart_price_range"] = [{"name": r["name"], "count": int(r["count"])} for r in rows]

                # indiamart_ratings
                rows = conn.execute(text("""
                    SELECT 
                        CASE 
                            WHEN stars >= 1 AND stars < 2 THEN '1–2 ★'
                            WHEN stars >= 2 AND stars < 3 THEN '2–3 ★'
                            WHEN stars >= 3 AND stars < 4 THEN '3–4 ★'
                            WHEN stars >= 4 AND stars < 4.5 THEN '4–4.5 ★'
                            ELSE '4.5–5 ★'
                        END as name,
                        COUNT(*) as count
                    FROM indiamart_products
                    WHERE stars IS NOT NULL AND stars > 0
                    GROUP BY name
                """)).mappings().fetchall()
                data["indiamart_ratings"] = [{"name": r["name"], "count": int(r["count"])} for r in rows]

                # indiamart_manufacturers
                rows = conn.execute(text("SELECT manufacturer as name, COUNT(*) as count FROM indiamart_products WHERE manufacturer IS NOT NULL AND manufacturer != '' GROUP BY manufacturer ORDER BY count DESC LIMIT 10")).mappings().fetchall()
                data["indiamart_manufacturers"] = [{"name": r["name"], "count": int(r["count"])} for r in rows]

                # indiamart_avg_price
                rows = conn.execute(text("""
                    SELECT 
                        category_name as name,
                        ROUND(AVG(price_numeric), 0) as `Avg Price`
                    FROM indiamart_products
                    WHERE category_name IS NOT NULL AND price_numeric > 0
                    GROUP BY category_name
                    ORDER BY `Avg Price` DESC
                    LIMIT 8
                """)).mappings().fetchall()
                data["indiamart_avg_price"] = [{"name": r["name"], "Avg Price": float(r["Avg Price"])} for r in rows]

                # indiamart_locations
                rows = conn.execute(text("SELECT location as name, COUNT(*) as count FROM indiamart_products WHERE location IS NOT NULL AND location != '' GROUP BY location ORDER BY count DESC LIMIT 10")).mappings().fetchall()
                data["indiamart_locations"] = [{"name": r["name"], "count": int(r["count"])} for r in rows]

            if marketplace == 'zepto' or not marketplace or marketplace == 'all':
                # zepto_categories - group by main_category directly (all 39 cats fully mapped)
                rows = conn.execute(text("""
                    SELECT 
                        z.main_category as name,
                        COUNT(*) as value 
                    FROM zepto z 
                    WHERE z.main_category IS NOT NULL
                    GROUP BY z.main_category 
                    ORDER BY value DESC 
                    LIMIT 8
                """)).mappings().fetchall()
                data["zepto_categories"] = [{"name": r["name"] or "Unmapped", "value": int(r["value"])} for r in rows]

                # zepto_subcategories
                rows = conn.execute(text("SELECT subcategory as name, COUNT(*) as value FROM zepto WHERE subcategory IS NOT NULL GROUP BY subcategory ORDER BY value DESC LIMIT 8")).mappings().fetchall()
                data["zepto_subcategories"] = [{"name": r["name"], "value": int(r["value"])} for r in rows]

                # zepto_price_range
                rows = conn.execute(text("""
                    SELECT 
                        CASE 
                            WHEN selling_price <= 100 THEN '₹0–100'
                            WHEN selling_price > 100 AND selling_price <= 300 THEN '₹100–300'
                            WHEN selling_price > 300 AND selling_price <= 500 THEN '₹300–500'
                            WHEN selling_price > 500 AND selling_price <= 1000 THEN '₹500–1K'
                            WHEN selling_price > 1000 AND selling_price <= 3000 THEN '₹1K–3K'
                            WHEN selling_price > 3000 AND selling_price <= 5000 THEN '₹3K–5K'
                            ELSE '₹5K+'
                        END as name,
                        COUNT(*) as count
                    FROM zepto
                    WHERE selling_price IS NOT NULL AND selling_price > 0
                    GROUP BY name
                """)).mappings().fetchall()
                data["zepto_price_range"] = [{"name": r["name"], "count": int(r["count"])} for r in rows]

                # zepto_ratings
                rows = conn.execute(text("""
                    SELECT 
                        CASE 
                            WHEN rating >= 1 AND rating < 2 THEN '1–2 ★'
                            WHEN rating >= 2 AND rating < 3 THEN '2–3 ★'
                            WHEN rating >= 3 AND rating < 4 THEN '3–4 ★'
                            WHEN rating >= 4 AND rating < 4.5 THEN '4–4.5 ★'
                            ELSE '4.5–5 ★'
                        END as name,
                        COUNT(*) as count
                    FROM zepto
                    WHERE rating IS NOT NULL AND rating > 0
                    GROUP BY name
                """)).mappings().fetchall()
                data["zepto_ratings"] = [{"name": r["name"], "count": int(r["count"])} for r in rows]

                # zepto_discount
                rows = conn.execute(text("""
                    SELECT 
                        z.main_category as name,
                        ROUND(AVG(((z.mrp - z.selling_price) / z.mrp) * 100), 1) as `Avg Discount %`
                    FROM zepto z
                    WHERE z.mrp > z.selling_price AND z.mrp > 0 AND z.main_category IS NOT NULL
                    GROUP BY z.main_category
                    ORDER BY `Avg Discount %` DESC
                    LIMIT 8
                """)).mappings().fetchall()
                data["zepto_discount"] = [{"name": r["name"] or "Unmapped", "Avg Discount %": float(r["Avg Discount %"])} for r in rows]

                # zepto_top_rated
                rows = conn.execute(text("""
                    SELECT 
                        z.main_category as name,
                        ROUND(AVG(z.rating), 1) as `Avg Rating`
                    FROM zepto z
                    WHERE z.rating > 0 AND z.main_category IS NOT NULL
                    GROUP BY z.main_category
                    ORDER BY `Avg Rating` DESC
                    LIMIT 8
                """)).mappings().fetchall()
                data["zepto_top_rated"] = [{"name": r["name"] or "Unmapped", "Avg Rating": float(r["Avg Rating"])} for r in rows]

                # zepto_price_vs_mrp
                rows = conn.execute(text("""
                    SELECT 
                        z.main_category as name,
                        ROUND(AVG(z.selling_price), 0) as `Sale Price`,
                        ROUND(AVG(z.mrp), 0) as `Market Price`
                    FROM zepto z
                    WHERE z.selling_price > 0 AND z.main_category IS NOT NULL
                    GROUP BY z.main_category
                    ORDER BY `Sale Price` DESC
                    LIMIT 8
                """)).mappings().fetchall()
                data["zepto_price_vs_mrp"] = [{"name": r["name"] or "Unmapped", "Sale Price": float(r["Sale Price"]), "Market Price": float(r["Market Price"])} for r in rows]


        return jsonify({"status": "success", "data": data}), 200
    except Exception as e:
        print(f"[product_report] chart-data error: {traceback.format_exc()}")
        return jsonify({"status": "error", "message": str(e)}), 500



@product_report_bp.route('/export-csv', methods=['GET'])
def export_all_data_csv():
    """
    Stream ALL records for a marketplace directly from the DB as a downloadable CSV.
    No page limit. ?marketplace=Amazon|Blinkit|BigBasket|Zepto|IndiaMart|DMart|All
    """
    marketplace = request.args.get('marketplace', 'All').strip()
    mp_lower = marketplace.lower()

    MARKETPLACE_QUERIES = {
        'amazon': {
            'query': "SELECT id, asin, title, categoryName, price, listPrice, stars, reviews, isBestSeller, boughtInLastMonth, imgUrl, productUrl FROM amazon_products ORDER BY id ASC",
            'headers': ['ID', 'ASIN', 'Product Name', 'Category', 'Price (Rs)', 'MRP (Rs)', 'Stars', 'Reviews', 'Best Seller', 'Bought Last Month', 'Image URL', 'Product URL'],
        },
        'blinkit': {
            'query': "SELECT product_id, product_name, brand, category, sub_category, price, mrp, quantity, availability, product_url, image_url FROM blinkit ORDER BY product_id ASC",
            'headers': ['Product ID', 'Product Name', 'Brand', 'Category', 'Sub Category', 'Price (Rs)', 'MRP (Rs)', 'Quantity', 'Availability', 'Product URL', 'Image URL'],
        },
        'bigbasket': {
            'query': "SELECT sku_id, product_name, main_category, subcategory, selling_price, mrp, rating, product_url FROM bigbasket ORDER BY sku_id ASC",
            'headers': ['SKU ID', 'Product Name', 'Main Category', 'Subcategory', 'Selling Price (Rs)', 'MRP (Rs)', 'Rating', 'Product URL'],
        },
        'zepto': {
            'query': "SELECT sku_id, product_name, main_category, subcategory, selling_price, mrp, quantity, rating, review, product_url, image_url FROM zepto ORDER BY sku_id ASC",
            'headers': ['SKU ID', 'Product Name', 'Main Category', 'Subcategory', 'Selling Price (Rs)', 'MRP (Rs)', 'Quantity', 'Rating', 'Reviews', 'Product URL', 'Image URL'],
        },
        'indiamart': {
            'query': "SELECT id, asin, product_name, manufacturer, category_name, sub_category_name, Price, price_numeric, stars, reviews, contact_number, location, gst_registration_date, badges, imgUrl, productUrl FROM indiamart_products ORDER BY id ASC",
            'headers': ['ID', 'ASIN', 'Product Name', 'Manufacturer', 'Category', 'Sub Category', 'Price (Text)', 'Price (Numeric)', 'Stars', 'Reviews', 'Contact', 'Location', 'GST Date', 'Badges', 'Image URL', 'Product URL'],
        },
        'dmart': {
            'query': "SELECT id, ASIN, Product_name, Brand, category, price, listPrice, quantity, availability, link FROM dmart_products ORDER BY id ASC",
            'headers': ['ID', 'ASIN', 'Product Name', 'Brand', 'Category', 'Price (Rs)', 'MRP (Rs)', 'Quantity', 'Availability', 'Link'],
        },
    }

    try:
        if mp_lower == 'all':
            def generate_all():
                output = io.StringIO()
                writer = csv.writer(output)
                writer.writerow(['Marketplace', 'Product ID', 'ASIN', 'Product Name', 'Brand', 'Category', 'Sub Category', 'Price (Rs)', 'MRP (Rs)', 'Stars', 'Reviews', 'Best Seller', 'Availability', 'Image URL', 'Product URL'])
                yield output.getvalue()
                output.seek(0); output.truncate(0)
                with engine.connect() as conn:
                    result = conn.execute(text("SELECT marketplace_name, product_id, asin, product_name, brand, category_name, sub_category_name, price, list_price, stars, reviews, is_best_seller, availability, img_url, product_url FROM product_top_selling_report ORDER BY marketplace_name, ranking_score DESC"))
                    for row in result:
                        writer.writerow([str(v) if v is not None else '' for v in row])
                        yield output.getvalue()
                        output.seek(0); output.truncate(0)
            return Response(generate_all(), mimetype='text/csv', headers={'Content-Disposition': 'attachment; filename=HBD_All_Marketplaces_Export.csv'})

        if mp_lower not in MARKETPLACE_QUERIES:
            return jsonify({'status': 'error', 'message': f'Unknown marketplace: {marketplace}'}), 400

        cfg = MARKETPLACE_QUERIES[mp_lower]

        def generate():
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(cfg['headers'])
            yield output.getvalue()
            output.seek(0); output.truncate(0)
            with engine.connect() as conn:
                result = conn.execute(text(cfg['query']))
                for row in result:
                    row_data = ['' if v is None else ('Yes' if v is True else ('No' if v is False else str(v))) for v in row]
                    writer.writerow(row_data)
                    yield output.getvalue()
                    output.seek(0); output.truncate(0)

        return Response(generate(), mimetype='text/csv', headers={'Content-Disposition': f'attachment; filename=HBD_{marketplace}_Full_Export.csv'})
    except Exception as e:
        print(f"[product_report] export-csv error: {traceback.format_exc()}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@product_report_bp.route('/mapping-report', methods=['GET'])
def get_mapping_report():
    """
    Returns per-marketplace category mapping data from actual mapping tables in DB.
    Accurate live queries - no cache dependency.
    ?marketplace=All|Amazon|Blinkit|BigBasket|Zepto|IndiaMart|DMart
    """
    marketplace = request.args.get('marketplace', 'all').strip().lower()
    try:
        data = {}
        with engine.connect() as conn:
            # ── BLINKIT (blinkit_mapping) ──
            if marketplace in ('all', 'blinkit'):
                blinkit_total = conn.execute(text("SELECT COUNT(*) FROM blinkit")).scalar() or 0
                blinkit_mapped = conn.execute(text("""
                    SELECT COUNT(*) FROM blinkit b
                    WHERE b.category IN (
                        SELECT category_name FROM blinkit_mapping WHERE category_name IS NOT NULL
                    )
                """)).scalar() or 0
                blinkit_cats = conn.execute(text("""
                    WITH unique_blinkit_mapping AS (
                        SELECT 
                            bm.category_name,
                            MIN(COALESCE(parent.category_name, bm.category_name)) as resolved_main_category
                        FROM blinkit_mapping bm
                        LEFT JOIN blinkit_mapping parent ON bm.parent_id = parent.category_id AND bm.category_level = 2
                        GROUP BY bm.category_name
                    ),
                    resolved_products AS (
                        SELECT 
                            b.product_id,
                            ubm.resolved_main_category as main_category
                        FROM blinkit b
                        LEFT JOIN unique_blinkit_mapping ubm ON ubm.category_name = b.category
                    )
                    SELECT 
                        bm1.category_name AS main_category,
                        (
                            SELECT COUNT(*) FROM blinkit_mapping bm2
                            WHERE bm2.parent_id = bm1.category_id AND bm2.category_level = 2
                        ) AS sub_count,
                        COUNT(rp.product_id) AS products
                    FROM blinkit_mapping bm1
                    LEFT JOIN resolved_products rp ON rp.main_category = bm1.category_name
                    WHERE bm1.category_level = 1
                    GROUP BY bm1.category_name, bm1.category_id
                    ORDER BY products DESC, bm1.category_name
                """)).mappings().fetchall()
                data['blinkit'] = {
                    'total_products': blinkit_total,
                    'mapped_products': blinkit_mapped,
                    'unmapped_products': blinkit_total - blinkit_mapped,
                    'mapping_pct': round((blinkit_mapped / blinkit_total * 100), 1) if blinkit_total > 0 else 0,
                    'categories': [{'main_category': r['main_category'], 'sub_count': int(r['sub_count'] or 0), 'products': int(r['products'] or 0)} for r in blinkit_cats]
                }

            # ── BIGBASKET (bigbasket_dbmapping - level=1 for main_category) ──
            if marketplace in ('all', 'bigbasket'):
                bb_total = conn.execute(text("SELECT COUNT(*) FROM bigbasket")).scalar() or 0
                bb_mapped = conn.execute(text("""
                    SELECT COUNT(*) FROM bigbasket b
                    WHERE b.main_category IN (
                        SELECT category_name FROM bigbasket_dbmapping
                        WHERE category_name IS NOT NULL AND category_level = 1
                    )
                """)).scalar() or 0
                bb_cats = conn.execute(text("""
                    WITH unique_bb_mapping AS (
                        SELECT category_name, MIN(category_name) as resolved_main_category
                        FROM bigbasket_dbmapping
                        WHERE category_level = 1
                        GROUP BY category_name
                    ),
                    resolved_products AS (
                        SELECT 
                            b.sku_id,
                            ubm.resolved_main_category as main_category
                        FROM bigbasket b
                        LEFT JOIN unique_bb_mapping ubm ON ubm.category_name = b.main_category
                    )
                    SELECT 
                        bdm.category_name AS main_category,
                        (
                            SELECT COUNT(*) FROM bigbasket_dbmapping bdm2
                            WHERE bdm2.parent_id = bdm.category_id AND bdm2.category_level = 2
                        ) AS sub_count,
                        COUNT(rp.sku_id) AS products
                    FROM bigbasket_dbmapping bdm
                    LEFT JOIN resolved_products rp ON rp.main_category = bdm.category_name
                    WHERE bdm.category_level = 1
                    GROUP BY bdm.category_name, bdm.category_id
                    ORDER BY products DESC, bdm.category_name
                """)).mappings().fetchall()
                data['bigbasket'] = {
                    'total_products': bb_total,
                    'mapped_products': bb_mapped,
                    'unmapped_products': bb_total - bb_mapped,
                    'mapping_pct': round((bb_mapped / bb_total * 100), 1) if bb_total > 0 else 0,
                    'categories': [{'main_category': r['main_category'], 'sub_count': int(r['sub_count'] or 0), 'products': int(r['products'] or 0)} for r in bb_cats]
                }

            # ── ZEPTO (zepto_db_mapping - column is 'category' NOT 'category_name'; levels via category_level col) ──
            if marketplace in ('all', 'zepto'):
                z_total = conn.execute(text("SELECT COUNT(*) FROM zepto")).scalar() or 0
                z_mapped = conn.execute(text("""
                    SELECT COUNT(*) FROM zepto z
                    WHERE z.main_category IN (
                        SELECT DISTINCT category FROM zepto_db_mapping
                        WHERE category IS NOT NULL AND category != 'All'
                    )
                """)).scalar() or 0
                z_cats = conn.execute(text("""
                    WITH unique_zepto_mapping AS (
                        SELECT 
                            c.category,
                            MIN(COALESCE(root1.category, root0.category)) AS resolved_main_category
                        FROM zepto_db_mapping c
                        LEFT JOIN zepto_db_mapping root1 ON c.parent_id = root1.category_id AND c.category_level = 2 AND root1.category_level = 1 AND root1.category != 'All'
                        LEFT JOIN zepto_db_mapping root0 ON c.category_id = root0.category_id AND c.category_level = 1 AND root0.category != 'All'
                        WHERE c.category != 'All'
                        GROUP BY c.category
                    ),
                    resolved_products AS (
                        SELECT 
                            z.sku_id,
                            uzm.resolved_main_category AS main_category
                        FROM zepto z
                        LEFT JOIN unique_zepto_mapping uzm ON uzm.category = z.main_category
                    )
                    SELECT 
                        zdm.category AS main_category,
                        (
                            SELECT COUNT(*) FROM zepto_db_mapping zdm2
                            WHERE zdm2.parent_id = zdm.category_id AND zdm2.category_level = 2
                        ) AS sub_count,
                        COUNT(rp.sku_id) AS products
                    FROM zepto_db_mapping zdm
                    LEFT JOIN resolved_products rp ON rp.main_category = zdm.category
                    WHERE zdm.category_level = 1 AND zdm.category != 'All'
                    GROUP BY zdm.category, zdm.category_id
                    ORDER BY products DESC, zdm.category
                """)).mappings().fetchall()
                data['zepto'] = {
                    'total_products': z_total,
                    'mapped_products': z_mapped,
                    'unmapped_products': z_total - z_mapped,
                    'mapping_pct': round((z_mapped / z_total * 100), 1) if z_total > 0 else 0,
                    'categories': [{'main_category': r['main_category'], 'sub_count': int(r['sub_count'] or 0), 'products': int(r['products'] or 0)} for r in z_cats]
                }

            # ── INDIAMART (indiamart_mappings - products mapped via category_name) ──
            if marketplace in ('all', 'indiamart'):
                im_total = conn.execute(text("SELECT COUNT(*) FROM indiamart_products")).scalar() or 0
                im_mapped = conn.execute(text("""
                    SELECT COUNT(*) FROM indiamart_products ip
                    WHERE ip.category_name IN (
                        SELECT category_name FROM indiamart_mappings WHERE category_name IS NOT NULL
                    )
                """)).scalar() or 0
                # Get level=None (root) categories with their product counts using hierarchical resolution
                im_cats = conn.execute(text("""
                    WITH unique_indiamart_mapping AS (
                        SELECT 
                            c.category_name,
                            MIN(COALESCE(root4.category_name, root3.category_name, root2.category_name, root1.category_name, root0.category_name)) AS resolved_main_category
                        FROM indiamart_mappings c
                        LEFT JOIN indiamart_mappings p4 ON c.parent_id = p4.id AND c.category_level = 4
                        LEFT JOIN indiamart_mappings p3 ON p4.parent_id = p3.id
                        LEFT JOIN indiamart_mappings p2 ON p3.parent_id = p2.id
                        LEFT JOIN indiamart_mappings root4 ON p2.parent_id = root4.id AND root4.category_level IS NULL
                        LEFT JOIN indiamart_mappings q3 ON c.parent_id = q3.id AND c.category_level = 3
                        LEFT JOIN indiamart_mappings q2 ON q3.parent_id = q2.id
                        LEFT JOIN indiamart_mappings root3 ON q2.parent_id = root3.id AND root3.category_level IS NULL
                        LEFT JOIN indiamart_mappings r2 ON c.parent_id = r2.id AND c.category_level = 2
                        LEFT JOIN indiamart_mappings root2 ON r2.parent_id = root2.id AND root2.category_level IS NULL
                        LEFT JOIN indiamart_mappings root1 ON c.parent_id = root1.id AND c.category_level = 1 AND root1.category_level IS NULL
                        LEFT JOIN indiamart_mappings root0 ON c.id = root0.id AND c.category_level IS NULL
                        GROUP BY c.category_name
                    ),
                    resolved_products AS (
                        SELECT 
                            ip.id,
                            uim.resolved_main_category AS main_category
                        FROM indiamart_products ip
                        LEFT JOIN unique_indiamart_mapping uim ON uim.category_name = ip.category_name
                    )
                    SELECT 
                        imm.category_name AS main_category,
                        (
                            SELECT COUNT(*) FROM indiamart_mappings imm2
                            WHERE imm2.parent_id = imm.category_id AND imm2.category_level = 1
                        ) AS sub_count,
                        COUNT(rp.id) AS products
                    FROM indiamart_mappings imm
                    LEFT JOIN resolved_products rp ON rp.main_category = imm.category_name
                    WHERE imm.category_level IS NULL
                    GROUP BY imm.category_name, imm.category_id
                    ORDER BY products DESC, imm.category_name
                """)).mappings().fetchall()
                data['indiamart'] = {
                    'total_products': im_total,
                    'mapped_products': im_mapped,
                    'unmapped_products': im_total - im_mapped,
                    'mapping_pct': round((im_mapped / im_total * 100), 1) if im_total > 0 else 0,
                    'categories': [{'main_category': r['main_category'], 'sub_count': int(r['sub_count'] or 0), 'products': int(r['products'] or 0)} for r in im_cats]
                }

            # ── DMART (dmart_categories - level=1 main categories) ──
            if marketplace in ('all', 'dmart'):
                dm_total = conn.execute(text("SELECT COUNT(*) FROM dmart_products")).scalar() or 0
                dm_mapped = conn.execute(text("""
                    SELECT COUNT(*) FROM dmart_products dp
                    WHERE dp.category IN (
                        SELECT category_name FROM dmart_categories WHERE category_name IS NOT NULL
                    )
                """)).scalar() or 0
                dm_cats = conn.execute(text("""
                    WITH unique_dmart_mapping AS (
                        SELECT 
                            c.category_name,
                            MIN(COALESCE(root2.category_name, root1.category_name, root0.category_name)) AS resolved_main_category
                        FROM dmart_categories c
                        LEFT JOIN dmart_categories p2 ON c.parent_id = p2.category_id AND c.category_level = 3
                        LEFT JOIN dmart_categories root2 ON p2.parent_id = root2.category_id AND root2.category_level = 1
                        LEFT JOIN dmart_categories root1 ON c.parent_id = root1.category_id AND c.category_level = 2 AND root1.category_level = 1
                        LEFT JOIN dmart_categories root0 ON c.category_id = root0.category_id AND c.category_level = 1
                        GROUP BY c.category_name
                    ),
                    resolved_products AS (
                        SELECT 
                            dp.id,
                            udm.resolved_main_category AS main_category
                        FROM dmart_products dp
                        LEFT JOIN unique_dmart_mapping udm ON udm.category_name = dp.category
                    )
                    SELECT 
                        dc.category_name AS main_category,
                        (
                            SELECT COUNT(*) FROM dmart_categories dc2
                            WHERE dc2.parent_id = dc.category_id AND dc2.category_level = 2
                        ) AS sub_count,
                        COUNT(rp.id) AS products
                    FROM dmart_categories dc
                    LEFT JOIN resolved_products rp ON rp.main_category = dc.category_name
                    WHERE dc.category_level = 1
                    GROUP BY dc.category_name, dc.category_id
                    ORDER BY products DESC, dc.category_name
                """)).mappings().fetchall()
                data['dmart'] = {
                    'total_products': dm_total,
                    'mapped_products': dm_mapped,
                    'unmapped_products': dm_total - dm_mapped,
                    'mapping_pct': round((dm_mapped / dm_total * 100), 1) if dm_total > 0 else 0,
                    'categories': [{'main_category': r['main_category'], 'sub_count': int(r['sub_count'] or 0), 'products': int(r['products'] or 0)} for r in dm_cats]
                }

            # ── AMAZON (product_category_master - level=1 for categoryName matching) ──
            if marketplace in ('all', 'amazon'):
                am_total = conn.execute(text("SELECT COUNT(*) FROM amazon_products")).scalar() or 0
                am_mapped = conn.execute(text("""
                    SELECT COUNT(*) FROM amazon_products ap
                    WHERE ap.categoryName IN (
                        SELECT DISTINCT category_name FROM product_category_master
                        WHERE category_name IS NOT NULL
                    )
                """)).scalar() or 0
                am_cats = conn.execute(text("""
                    WITH unique_amazon_mapping AS (
                        SELECT 
                            category_name,
                            MIN(id) AS id,
                            MIN(category_name) AS resolved_main_category
                        FROM product_category_master
                        WHERE category_level = 1 AND category_name IS NOT NULL
                        GROUP BY category_name
                    ),
                    resolved_products AS (
                        SELECT 
                            ap.id,
                            uam.resolved_main_category as main_category
                        FROM amazon_products ap
                        LEFT JOIN unique_amazon_mapping uam ON uam.category_name = ap.categoryName
                    )
                    SELECT 
                        uam.category_name AS main_category,
                        (
                            SELECT COUNT(*) FROM product_category_master pcm2
                            WHERE pcm2.parent_id = uam.id AND pcm2.category_level = 2
                        ) AS sub_count,
                        COUNT(rp.id) AS products
                    FROM unique_amazon_mapping uam
                    LEFT JOIN resolved_products rp ON rp.main_category = uam.category_name
                    GROUP BY uam.category_name, uam.id
                    ORDER BY products DESC, uam.category_name
                """)).mappings().fetchall()
                data['amazon'] = {
                    'total_products': am_total,
                    'mapped_products': am_mapped,
                    'unmapped_products': am_total - am_mapped,
                    'mapping_pct': round((am_mapped / am_total * 100), 1) if am_total > 0 else 0,
                    'categories': [{'main_category': r['main_category'], 'sub_count': int(r['sub_count'] or 0), 'products': int(r['products'] or 0)} for r in am_cats]
                }

        return jsonify({'status': 'success', 'data': data}), 200
    except Exception as e:
        print(f"[product_report] mapping-report error: {traceback.format_exc()}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@product_report_bp.route('/live-mapping-counts', methods=['GET'])
def get_live_mapping_counts():
    """
    Fast summary of mapped/unmapped counts per marketplace using live DB queries.
    Used for KPI cards. No cache dependency.
    """
    try:
        data = {}
        with engine.connect() as conn:
            # Blinkit
            bl_total = conn.execute(text("SELECT COUNT(*) FROM blinkit")).scalar() or 0
            bl_mapped = conn.execute(text("SELECT COUNT(*) FROM blinkit WHERE category IN (SELECT category_name FROM blinkit_mapping WHERE category_name IS NOT NULL)")).scalar() or 0
            bl_cats = conn.execute(text("SELECT COUNT(DISTINCT category_name) FROM blinkit_mapping WHERE category_level = 1")).scalar() or 0
            data['blinkit'] = {'total': bl_total, 'mapped': bl_mapped, 'unmapped': bl_total - bl_mapped, 'categories': bl_cats}

            # BigBasket
            bb_total = conn.execute(text("SELECT COUNT(*) FROM bigbasket")).scalar() or 0
            bb_mapped = conn.execute(text("SELECT COUNT(*) FROM bigbasket WHERE main_category IN (SELECT category_name FROM bigbasket_dbmapping WHERE category_name IS NOT NULL AND category_level = 1)")).scalar() or 0
            bb_cats = conn.execute(text("SELECT COUNT(DISTINCT category_name) FROM bigbasket_dbmapping WHERE category_level = 1")).scalar() or 0
            data['bigbasket'] = {'total': bb_total, 'mapped': bb_mapped, 'unmapped': bb_total - bb_mapped, 'categories': bb_cats}

            # Zepto (uses 'category' column not 'category_name')
            z_total = conn.execute(text("SELECT COUNT(*) FROM zepto")).scalar() or 0
            z_mapped = conn.execute(text("SELECT COUNT(*) FROM zepto WHERE main_category IN (SELECT DISTINCT category FROM zepto_db_mapping WHERE category IS NOT NULL AND category != 'All')")).scalar() or 0
            z_cats = conn.execute(text("SELECT COUNT(DISTINCT category) FROM zepto_db_mapping WHERE category_level = 1 AND category != 'All'")).scalar() or 0
            data['zepto'] = {'total': z_total, 'mapped': z_mapped, 'unmapped': z_total - z_mapped, 'categories': z_cats}

            # IndiaMart
            im_total = conn.execute(text("SELECT COUNT(*) FROM indiamart_products")).scalar() or 0
            im_mapped = conn.execute(text("SELECT COUNT(*) FROM indiamart_products WHERE category_name IN (SELECT category_name FROM indiamart_mappings WHERE category_name IS NOT NULL)")).scalar() or 0
            im_cats = conn.execute(text("SELECT COUNT(DISTINCT category_name) FROM indiamart_mappings WHERE category_level IS NULL")).scalar() or 0
            data['indiamart'] = {'total': im_total, 'mapped': im_mapped, 'unmapped': im_total - im_mapped, 'categories': im_cats}

            # DMart
            dm_total = conn.execute(text("SELECT COUNT(*) FROM dmart_products")).scalar() or 0
            dm_mapped = conn.execute(text("SELECT COUNT(*) FROM dmart_products WHERE category IN (SELECT category_name FROM dmart_categories WHERE category_name IS NOT NULL)")).scalar() or 0
            dm_cats = conn.execute(text("SELECT COUNT(DISTINCT category_name) FROM dmart_categories WHERE category_level = 1")).scalar() or 0
            data['dmart'] = {'total': dm_total, 'mapped': dm_mapped, 'unmapped': dm_total - dm_mapped, 'categories': dm_cats}

            # Amazon (uses categoryName column)
            am_total = conn.execute(text("SELECT COUNT(*) FROM amazon_products")).scalar() or 0
            am_mapped = conn.execute(text("SELECT COUNT(*) FROM amazon_products WHERE categoryName IN (SELECT DISTINCT category_name FROM product_category_master WHERE category_name IS NOT NULL)")).scalar() or 0
            am_cats = conn.execute(text("SELECT COUNT(DISTINCT category_name) FROM product_category_master WHERE category_level = 1")).scalar() or 0
            data['amazon'] = {'total': am_total, 'mapped': am_mapped, 'unmapped': am_total - am_mapped, 'categories': am_cats}

        return jsonify({'status': 'success', 'data': data}), 200
    except Exception as e:
        print(f"[product_report] live-mapping-counts error: {traceback.format_exc()}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

