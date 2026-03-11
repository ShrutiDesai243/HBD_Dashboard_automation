from flask import Blueprint, request, jsonify
from extensions import db
from model.college_dunia import CollegeDunia

college_dunia_bp = Blueprint('college_dunia_bp', __name__)

@college_dunia_bp.route('/fetch-data', methods=['GET'])
def fetch_college_dunia_data():
    try:
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 10, type=int)
        search = request.args.get('search', '')

        query = CollegeDunia.query

        if search:
            query = query.filter(CollegeDunia.name.ilike(f"%{search}%"))
        
        pagination = query.paginate(page=page, per_page=limit, error_out=False)
        
        return jsonify({
            "data": [item.to_dict() for item in pagination.items],
            "total_pages": pagination.pages,
            "total_count": pagination.total,
            "current_page": page
        }), 200

    except Exception as e:
        print(f"❌ Error in CollegeDunia fetch: {str(e)}")
        return jsonify({"error": str(e)}), 500