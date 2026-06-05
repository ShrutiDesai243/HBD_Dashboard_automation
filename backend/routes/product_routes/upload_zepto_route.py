from flask import request, jsonify, Blueprint
from werkzeug.utils import secure_filename
import os
from utils.storage import get_upload_base_dir
from extensions import db
from model.product_model.additional_products import Zepto

zepto_bp = Blueprint("zepto_bp", __name__)

@zepto_bp.route('/fetch-data', methods=['GET'])
def fetch_zepto_data():
    try:
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 10, type=int)
        search = request.args.get('search', '')
        category = request.args.get('category', '')

        query = Zepto.query

        if search:
            query = query.filter(
                db.or_(
                    Zepto.product_name.ilike(f"%{search}%"),
                    Zepto.sku_id.ilike(f"%{search}%")
                )
            )
        if category:
            query = query.filter(Zepto.main_category.ilike(f"%{category}%"))

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

@zepto_bp.route("/upload/zepto-data", methods=["POST"])
def upload_zepto_route():
    files = request.files.getlist("files")
    if not files:
        return jsonify({"error": "No files provided"}), 400
    UPLOAD_DIR = get_upload_base_dir() / "zepto"
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    paths = []
    for f in files:
        filename = secure_filename(f.filename)
        filepath = UPLOAD_DIR / filename
        f.save(filepath)
        paths.append(str(filepath))
    try:
        from tasks.products_task.upload_zepto_task import process_zepto_task
        task = process_zepto_task.delay(paths)
        return jsonify({"status": "files_accepted", "task_id": task.id}), 202
    except Exception as e:
        return jsonify({"error": str(e)}), 500
