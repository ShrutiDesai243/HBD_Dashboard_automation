from flask import Blueprint, request, jsonify
from extensions import db
from model.bank import Bank

bank_bp = Blueprint('bank_bp', __name__)

@bank_bp.route('/fetch-data', methods=['GET'])
def fetch_bank_data():
    try:
        # 1. Get Filters
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 10, type=int)
        search = request.args.get('search', '')
        city_filter = request.args.get('city', '')

        # 2. Build Query
        query = Bank.query

        if search:
            # Search by Bank Name OR Branch OR IFSC
            query = query.filter(
                (Bank.name.ilike(f"%{search}%")) | 
                (Bank.branch.ilike(f"%{search}%")) |
                (Bank.ifsc.ilike(f"%{search}%"))
            )
        
        if city_filter:
            query = query.filter(Bank.city.ilike(f"%{city_filter}%"))

        # 3. Paginate
        pagination = query.paginate(page=page, per_page=limit, error_out=False)
        
        return jsonify({
            "data": [item.to_dict() for item in pagination.items],
            "total_pages": pagination.pages,
            "total_count": pagination.total,
            "current_page": page
        }), 200

    except Exception as e:
        print(f"Error fetching bank data: {str(e)}")
        return jsonify({"error": str(e)}), 500