from flask import Blueprint, request, jsonify
from sqlalchemy import or_

# Adjust this import path based on exactly where your model is saved
from model.product_master_table import ProductMaster 

# Initialize the Blueprint
product_master_bp = Blueprint("product_master_bp", __name__)

@product_master_bp.route("/fetch-data", methods=["GET"], strict_slashes=False)
def fetch_product_master_data():
    print("🚀 API Hit: /api/product-master/fetch-data")
    
    try:
        page = request.args.get("page", 1, type=int)
        limit = request.args.get("limit", 10, type=int)
        
        # Extract the new specific search parameters from React
        search_name = request.args.get("name", "", type=str)
        search_category = request.args.get("category", "", type=str)
        search_subcategory = request.args.get("sub_category", "", type=str)

        limit = max(1, min(limit, 100))
        query = ProductMaster.query

        # Apply specific filters dynamically
        if search_name:
            query = query.filter(ProductMaster.business_name.ilike(f"%{search_name}%"))
        
        if search_category:
            query = query.filter(ProductMaster.category.ilike(f"%{search_category}%"))
            
        if search_subcategory:
            query = query.filter(ProductMaster.sub_category.ilike(f"%{search_subcategory}%"))

        # Calculate Pagination Metrics
        pagination = query.order_by(ProductMaster.id.desc()).paginate(
            page=page, 
            per_page=limit, 
            error_out=False
        )

        return jsonify({
            "total_count": pagination.total,
            "total_pages": pagination.pages,
            "current_page": page,
            "data": [item.to_dict() for item in pagination.items]
        }), 200

    except Exception as e:
        print(f"❌ Product Master Fetch Error: {str(e)}")
        return jsonify({"error": str(e)}), 500
