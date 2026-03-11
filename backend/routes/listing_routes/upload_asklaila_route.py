from flask import Blueprint, request, jsonify
from extensions import db
from model.asklaila import Asklaila  # Importing the model we created

# Define the Blueprint
asklaila_bp = Blueprint('asklaila_bp', __name__)

# --- FETCH DATA ROUTE (For the Table) ---
@asklaila_bp.route('/fetch-data', methods=['GET'])
def fetch_asklaila_data():
    try:
        # Get query parameters from the frontend
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 10, type=int)
        search = request.args.get('search', '')
        city_filter = request.args.get('city', '')

        # Start the query
        query = Asklaila.query

        # Apply Search Filter (Business Name)
        if search:
            query = query.filter(Asklaila.name.ilike(f"%{search}%"))
        
        # Apply City Filter
        if city_filter:
            query = query.filter(Asklaila.city.ilike(f"%{city_filter}%"))

        # Apply Sorting (Newest first) and Pagination
        pagination = query.order_by(Asklaila.id.desc()).paginate(
            page=page, 
            per_page=limit, 
            error_out=False
        )
        
        # Return JSON response
        return jsonify({
            "data": [item.to_dict() for item in pagination.items],
            "total_pages": pagination.pages,
            "total_count": pagination.total,
            "current_page": page
        }), 200

    except Exception as e:
        # Log the error and return 500
        print(f"Error fetching Asklaila data: {str(e)}")
        return jsonify({"error": str(e)}), 500


# --- (OPTIONAL) EXISTING UPLOAD ROUTE ---
# If you had an upload route here before, you can paste it below this line.
# Example:
# @asklaila_bp.route('/upload', methods=['POST'])
# def upload_csv():
#     ...