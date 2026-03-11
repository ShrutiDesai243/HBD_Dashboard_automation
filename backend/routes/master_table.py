import os
from pathlib import Path
from flask import Blueprint, jsonify, request
from sqlalchemy import func, or_, text
from werkzeug.utils import secure_filename

# Model and Session imports
from model.master_table_model import MasterTable
from model.upload_master_reports_model import UploadReport
from database.session import get_db_session

# --- INITIALIZE BLUEPRINT FIRST ---
master_table_bp = Blueprint("master_table", __name__)

# Define upload directory helper
def get_upload_base_dir():
    return Path(os.getenv("UPLOAD_DIR", "./uploads"))

# Import Celery task safely
try:
    from tasks.upload_master_task import process_master_upload_task
except ImportError:
    process_master_upload_task = None

# --- ROUTES ---

@master_table_bp.route("/upload/master", methods=["POST"])
def upload_master():
    files = request.files.getlist("file")
    if not files:
        return jsonify({"error": "No files provided"}), 400

    UPLOAD_DIR = get_upload_base_dir() / "master"
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    paths = []
    for f in files:
        filename = secure_filename(f.filename)
        path = UPLOAD_DIR / filename
        f.save(path)
        paths.append(str(path))

    if process_master_upload_task:
        task = process_master_upload_task.delay(paths)
        return jsonify({
            "status": "files_accepted",
            "task_id": task.id
        }), 202
    return jsonify({"error": "Upload task not configured"}), 500

@master_table_bp.route("/master_table/list", methods=["GET"])
def get_master_table_list():
    session = get_db_session()
    try:
        page = request.args.get("page", 1, type=int)
        # Default to 10 for resource safety
        limit = request.args.get("limit", 10, type=int)
        search = request.args.get("search", "", type=str)

        # Hard cap to prevent frontend from accidentally crashing the DB
        limit = max(1, min(limit, 50))

        query = session.query(MasterTable)

        if search:
            query = query.filter(
                or_(
                    MasterTable.business_name.ilike(f"%{search}%"),
                    MasterTable.city.ilike(f"%{search}%"),
                    MasterTable.business_category.ilike(f"%{search}%"),
                    MasterTable.global_business_id.ilike(f"%{search}%")
                )
            )

        total_count = query.count()
        total_pages = (total_count + limit - 1) // limit

        rows = query.order_by(MasterTable.id.desc()).offset((page - 1) * limit).limit(limit).all()

        return jsonify({
            "total_count": total_count,
            "total_pages": total_pages,
            "current_page": page,
            "data": [row.to_dict() for row in rows]
        })
    except Exception as e:
        print(f"❌ Error fetching master list: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()

@master_table_bp.route("/master-dashboard-stats", methods=["GET"])
def get_master_dashboard_stats():
    session = get_db_session()
    task_id = request.args.get('task_id')
    
    where_clause = "WHERE 1=1"
    params = {}
    
    if task_id:
        where_clause += " AND task_id = :task_id"
        params['task_id'] = task_id

    try:
        state_query = text(f"SELECT state, COUNT(*) as count FROM master_table {where_clause} AND state != '' GROUP BY state ORDER BY count DESC LIMIT 5")
        states = [dict(row._mapping) for row in session.execute(state_query, params)]

        phone_query = text(f"""
            SELECT 
                SUM(CASE WHEN 
                    (primary_phone IS NOT NULL AND primary_phone != '') OR 
                    (secondary_phone IS NOT NULL AND secondary_phone != '') OR 
                    (other_phones IS NOT NULL AND other_phones != '') OR 
                    (virtual_phone IS NOT NULL AND virtual_phone != '') OR 
                    (whatsapp_phone IS NOT NULL AND whatsapp_phone != '') 
                THEN 1 ELSE 0 END) as has_any_phone,
                COUNT(*) as total_count
            FROM master_table {where_clause}
        """)
        phone_res = session.execute(phone_query, params).fetchone()
        
        has_phone = int(phone_res.has_any_phone or 0)
        missing_phone = int(phone_res.total_count or 0) - has_phone

        phone_distribution = [
            {"name": "With Contact No.", "value": has_phone, "fill": "#10b981"},
            {"name": "No Contact No.", "value": missing_phone, "fill": "#ef4444"}
        ]

        city_query = text(f"SELECT city as name, COUNT(*) as count FROM master_table {where_clause} GROUP BY city ORDER BY count DESC LIMIT 10")
        top_cities = [dict(row._mapping) for row in session.execute(city_query, params)]
        
        sub_query = text(f"SELECT COALESCE(business_subcategory, business_category, 'Other') as name, COUNT(*) as count FROM master_table {where_clause} GROUP BY name ORDER BY count DESC LIMIT 5")
        top_subs = [dict(row._mapping) for row in session.execute(sub_query, params)]

        total_records = session.execute(text(f"SELECT COUNT(*) FROM master_table {where_clause}"), params).scalar() or 0
        avg_rating = session.execute(text(f"SELECT ROUND(AVG(ratings), 1) FROM master_table {where_clause} AND ratings IS NOT NULL"), params).scalar() or 0.0
        
        top_rated_query = text(f"""
            SELECT id, business_name as name, city, ratings as stars, business_category as category
            FROM master_table {where_clause} 
            AND ratings IS NOT NULL 
            AND business_name IS NOT NULL
            ORDER BY ratings DESC LIMIT 5
        """)
        top_rated = [dict(row._mapping) for row in session.execute(top_rated_query, params)]

        return jsonify({
            "status": "COMPLETED",
            "stats": {
                "total_records": total_records,
                "avg_system_rating": float(avg_rating),
                "state_summary": states,
                "phone_distribution": phone_distribution,
                "top_cities": top_cities,
                "top_subcategories": top_subs,
                "top_rated_businesses": top_rated
            }
        })
    except Exception as e:
        print(f"❌ Dashboard Error: {str(e)}")
        return jsonify({"status": "ERROR", "message": str(e)}), 500
    finally:
        session.close()

@master_table_bp.route("/upload/report/<task_id>", methods=["GET"])
def get_upload_report(task_id):
    session = get_db_session()
    try:
        report = session.query(UploadReport).filter_by(task_id=task_id).first()
        if not report:
            return jsonify({"status": "not_found", "task_id": task_id}), 404

        return jsonify({
            "task_id": report.task_id,
            "status": report.status,
            "stats": {
                "total_records": report.total_processed or 0,
                "missing_values": {
                    "missing_phone": report.missing_primary_phone or 0,
                    "missing_email": report.missing_email or 0,
                    "missing_address": report.missing_address or 0
                }
            }
        })
    finally:
        session.close()