from flask import Blueprint, request, jsonify
from sqlalchemy import text
from extensions import db
from flask_jwt_extended import jwt_required

# Initialize the Blueprint
product_master_bp = Blueprint("product_master_bp", __name__)

@product_master_bp.route("/fetch-data", methods=["GET"], strict_slashes=False)
@jwt_required()
def fetch_product_master_data():
    """Retrieve paginated product records directly from product_master database table"""
    try:
        page = request.args.get("page", 1, type=int)
        limit = request.args.get("limit", 20, type=int)
        
        # Search and filter inputs
        search_name = request.args.get("name", "", type=str).strip()
        search_category = request.args.get("category", "", type=str).strip()
        search_source = request.args.get("source", "", type=str).strip()

        # Hard cap to protect DB performance
        limit = max(1, min(limit, 100))

        conditions = []
        params = {}

        if search_name:
            conditions.append("product_name LIKE :search_name")
            params["search_name"] = f"%{search_name}%"

        if search_category:
            conditions.append("category_name LIKE :search_category")
            params["search_category"] = f"%{search_category}%"

        if search_source:
            conditions.append("LOWER(marketplace_name) = LOWER(:search_source)")
            params["search_source"] = search_source

        where_clause = ""
        if conditions:
            where_clause = " AND " + " AND ".join(conditions)

        # 1. Total records count
        count_query = f"SELECT COUNT(*) FROM product_master WHERE 1=1 {where_clause}"
        total_count = db.session.execute(text(count_query), params).scalar() or 0

        # Calculate pages
        total_pages = (total_count + limit - 1) // limit

        # 2. Fetch records
        offset = (page - 1) * limit
        select_query = f"""
            SELECT 
                id, marketplace_name, asin, product_name, brand, price, list_price, 
                stars, reviews, availability, category_name, product_url, img_url, 
                manufacturer, is_best_seller
            FROM product_master 
            WHERE 1=1 {where_clause}
            ORDER BY id DESC
            LIMIT :limit OFFSET :offset
        """
        
        # Add pagination params
        query_params = {**params, "limit": limit, "offset": offset}
        rows = db.session.execute(text(select_query), query_params).mappings().fetchall()

        data = []
        for r in rows:
            data.append({
                "id": int(r["id"]),
                "marketplace_name": r["marketplace_name"] or "",
                "asin": r["asin"] or "",
                "product_name": r["product_name"] or "",
                "brand": r["brand"] or "",
                "price": float(r["price"]) if r["price"] is not None else 0.0,
                "list_price": float(r["list_price"]) if r["list_price"] is not None else 0.0,
                "stars": float(r["stars"]) if r["stars"] is not None else 0.0,
                "reviews": int(r["reviews"]) if r["reviews"] is not None else 0,
                "availability": r["availability"] or "",
                "category_name": r["category_name"] or "",
                "product_url": r["product_url"] or "",
                "img_url": r["img_url"] or "",
                "manufacturer": r["manufacturer"] or "",
                "is_best_seller": bool(r["is_best_seller"])
            })

        return jsonify({
            "total_count": total_count,
            "total_pages": total_pages,
            "current_page": page,
            "data": data
        }), 200

    except Exception as e:
        print(f"❌ Product Master Fetch Error: {str(e)}")
        return jsonify({"error": str(e)}), 500
