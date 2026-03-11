from flask import Blueprint, request, jsonify
from extensions import db
from model.atm import ATM 

atm_bp = Blueprint('atm_bp', __name__)

@atm_bp.route('/fetch-data', methods=['GET'])
def fetch_atm_data():
    try:
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 10, type=int)
        search = request.args.get('search', '')
        city_filter = request.args.get('city', '')

        # Use ATM (all caps) to match your import
        query = ATM.query

        if search:
            query = query.filter(ATM.name.ilike(f"%{search}%"))
        
        if city_filter:
            query = query.filter(ATM.city.ilike(f"%{city_filter}%"))

        pagination = query.paginate(page=page, per_page=limit, error_out=False)
        
        return jsonify({
            "data": [item.to_dict() for item in pagination.items],
            "total_pages": pagination.pages,
            "total_count": pagination.total,
            "current_page": page
        }), 200

    except Exception as e:
        print(f"❌ Error in ATM fetch: {str(e)}") # Log this to Docker
        return jsonify({"error": str(e)}), 500