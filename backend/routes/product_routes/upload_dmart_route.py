from flask import request, jsonify, Blueprint
from werkzeug.utils import secure_filename
import os
from utils.storage import get_upload_base_dir
from extensions import db
from model.product_model.additional_products import DMart

dmart_bp = Blueprint("dmart_bp", __name__)


@dmart_bp.route('/fetch-data', methods=['GET'])
def fetch_dmart_data():
    try:
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 10, type=int)
        search = request.args.get('search', '')
        category = request.args.get('category', '')

        query = DMart.query

        if search:
            query = query.filter(
                db.or_(
                    DMart.Product_name.ilike(f"%{search}%"),
                    DMart.ASIN.ilike(f"%{search}%"),
                    DMart.Brand.ilike(f"%{search}%"),
                )
            )
        if category:
            query = query.filter(DMart.category.ilike(f"%{category}%"))

        pagination = query.paginate(page=page, per_page=limit, error_out=False)
        return jsonify({
            "status": "success",
            "data": [item.to_dict() for item in pagination.items],
            "total_pages": pagination.pages,
            "total_count": pagination.total,
            "current_page": page
        }), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@dmart_bp.route("/upload/dmart-data", methods=["POST"])
def upload_dmart_route():
    files = request.files.getlist("files")
    if not files:
        return jsonify({"error": "No files provided"}), 400
    UPLOAD_DIR = get_upload_base_dir() / "dmart"
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    paths = []
    for f in files:
        filename = secure_filename(f.filename)
        filepath = UPLOAD_DIR / filename
        f.save(filepath)
        paths.append(str(filepath))
    try:
        from tasks.products_task.upload_dmart_task import process_dmart_task
        task = process_dmart_task.delay(paths)
        return jsonify({"status": "files_accepted", "task_id": task.id}), 202
    except Exception as e:
        return jsonify({"error": str(e)}), 500