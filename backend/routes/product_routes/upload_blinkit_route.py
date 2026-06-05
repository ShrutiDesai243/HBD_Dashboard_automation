from flask import Flask,request,jsonify,Blueprint
from tasks.products_task.upload_blinkit_task import process_blinkit_task
from werkzeug.utils import secure_filename
import os 
from utils.storage import get_upload_base_dir

from model.product_model.additional_products import Blinkit

blinkit_bp = Blueprint("blinkit_bp",__name__)
@blinkit_bp.route('/fetch-data', methods=['GET'])
def fetch_blinkit_data():
    try:

        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 50, type=int)
        search = request.args.get('search', '').strip()
        category = request.args.get('category', '').strip()
        sub_category = request.args.get('subcategory', '').strip()

        query = Blinkit.query

        if search:
            query = query.filter(Blinkit.product_name.ilike(f"%{search}%"))
        if category:
            query = query.filter(Blinkit.category.ilike(f"%{category}%"))
        if sub_category:
            query = query.filter(Blinkit.sub_category.ilike(f"%{sub_category}%"))

        pagination = query.paginate(
            page=page,
            per_page=limit,
            error_out=False
        )

        products = [item.to_dict() for item in pagination.items]

        return jsonify({
            "success": True,
            "data": products,
            "pagination": {
                "current_page": page,
                "total_pages": pagination.pages,
                "total_records": pagination.total
            }
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

@blinkit_bp.route("/upload/blinkit-data",methods=["POST"])
def upload_blinkit_route():
    files = request.files.getlist("files")
    if not files:
        return jsonify({"error":"No files provided"}),400
    UPLOAD_DIR = get_upload_base_dir()/"blinkit"
    UPLOAD_DIR.mkdir(parents=True,exist_ok=True)
    paths = []
    for f in files:
        filename = secure_filename(f.filename)
        filepath = UPLOAD_DIR/filename
        f.save(filepath)
        paths.append(str(filepath))
    try:
        task = process_blinkit_task.delay(paths)
        return jsonify({
            "status":"files_accepted",
            "task_id":task.id
            }),202
    except Exception as e:
        return jsonify({
            "error":str(e)
        }),500