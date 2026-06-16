import uuid
import threading
from flask import Blueprint, jsonify, request, current_app
from flask_jwt_extended import jwt_required
from extensions import db
from model.data_cleaning_log import DataCleaningLog
from services.data_cleaning_service import (
    get_table_counts_and_metrics,
    run_cleaning_async,
    rollback_from_backup,
    active_tasks
)
from safe_db_cleaner import load_engine, get_tables, is_backup_table, run_cleaning

data_cleaning_bp = Blueprint("data_cleaning", __name__)

@data_cleaning_bp.route("/analyze", methods=["GET"])
@jwt_required()
def analyze_tables():
    """Retrieve fast count metrics of master_table and product_master"""
    try:
        metrics = get_table_counts_and_metrics()
        return jsonify({"status": "success", "data": metrics})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@data_cleaning_bp.route("/safe-clean/tables", methods=["GET"])
@jwt_required()
def list_safe_clean_tables():
    """List selectable non-backup tables for safe text cleanup."""
    try:
        engine, database = load_engine()
        with engine.connect() as conn:
            tables = [t for t in get_tables(conn, database) if not is_backup_table(t)]
        return jsonify({"status": "success", "data": tables})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@data_cleaning_bp.route("/safe-clean/run", methods=["POST"])
@jwt_required()
def run_safe_clean_table():
    """Dry-run or apply safe text cleanup for one selected table."""
    try:
        req_data = request.get_json() or {}
        table_name = req_data.get("table_name")
        dry_run = bool(req_data.get("dry_run", True))
        chunk_size = int(req_data.get("chunk_size", 10000))

        if not table_name:
            return jsonify({"status": "error", "message": "table_name is required"}), 400
        if table_name == "all":
            return jsonify({"status": "error", "message": "Please select one table for safe cleanup"}), 400

        engine, database = load_engine()
        with engine.connect() as conn:
            valid_tables = {t for t in get_tables(conn, database) if not is_backup_table(t)}
        if table_name not in valid_tables:
            return jsonify({"status": "error", "message": f"Invalid or backup table: {table_name}"}), 400

        report = run_cleaning(
            table_names=[table_name],
            chunk_size=chunk_size,
            dry_run=dry_run,
            force_large_no_pk=True,
        )
        table_result = report["tables"][0] if report.get("tables") else None
        return jsonify({
            "status": "success",
            "data": {
                "summary": report.get("summary", {}),
                "table": table_result,
                "dry_run": dry_run,
            }
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@data_cleaning_bp.route("/dry-run", methods=["POST"])
@jwt_required()
def trigger_dry_run():
    """Start asynchronous dry-run cleaning task"""
    try:
        req_data = request.get_json() or {}
        table_name = req_data.get("table_name", "all") # 'master_table', 'product_master', 'all'
        
        if table_name not in ("master_table", "product_master", "all"):
            return jsonify({"status": "error", "message": "Invalid table_name parameter"}), 400
            
        run_id = f"dry_{uuid.uuid4().hex[:8]}"
        
        # Log entry for tracking
        log_entry = DataCleaningLog(
            run_id=run_id,
            run_type="dry-run",
            status="running",
            table_name=table_name
        )
        db.session.add(log_entry)
        db.session.commit()
        
        # Start background thread
        app_context = current_app._get_current_object().app_context()
        thread = threading.Thread(
            target=run_cleaning_async,
            args=(run_id, table_name, "dry-run", app_context)
        )
        thread.start()
        active_tasks[run_id] = thread
        
        return jsonify({
            "status": "success",
            "run_id": run_id,
            "message": f"Asynchronous dry-run cleaning started for '{table_name}'."
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500

@data_cleaning_bp.route("/apply", methods=["POST"])
@jwt_required()
def trigger_apply_cleaning():
    """Start asynchronous cleaning execution (backups created first)"""
    try:
        req_data = request.get_json() or {}
        table_name = req_data.get("table_name", "all")
        
        if table_name not in ("master_table", "product_master", "all"):
            return jsonify({"status": "error", "message": "Invalid table_name parameter"}), 400
            
        run_id = f"clean_{uuid.uuid4().hex[:8]}"
        
        # Log entry for tracking
        log_entry = DataCleaningLog(
            run_id=run_id,
            run_type="apply",
            status="running",
            table_name=table_name
        )
        db.session.add(log_entry)
        db.session.commit()
        
        # Start background thread
        app_context = current_app._get_current_object().app_context()
        thread = threading.Thread(
            target=run_cleaning_async,
            args=(run_id, table_name, "apply", app_context)
        )
        thread.start()
        active_tasks[run_id] = thread
        
        return jsonify({
            "status": "success",
            "run_id": run_id,
            "message": f"Asynchronous active cleaning started for '{table_name}'. Backup table created."
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500

@data_cleaning_bp.route("/rollback", methods=["POST"])
@jwt_required()
def trigger_rollback():
    """Rollback original tables using backup tables created in target_run_id"""
    try:
        req_data = request.get_json() or {}
        target_run_id = req_data.get("target_run_id")
        
        if not target_run_id:
            return jsonify({"status": "error", "message": "target_run_id is required"}), 400
            
        # Verify target run has backups
        target_log = DataCleaningLog.query.filter_by(run_id=target_run_id).first()
        if not target_log or not target_log.backup_table_name:
            return jsonify({"status": "error", "message": f"No backup table found for target run_id '{target_run_id}'"}), 404
            
        run_id = f"roll_{uuid.uuid4().hex[:8]}"
        
        # Log entry
        log_entry = DataCleaningLog(
            run_id=run_id,
            run_type="rollback",
            status="running",
            table_name=target_log.table_name,
            backup_table_name=target_log.backup_table_name
        )
        db.session.add(log_entry)
        db.session.commit()
        
        # Start background rollback thread
        app_context = current_app._get_current_object().app_context()
        thread = threading.Thread(
            target=rollback_from_backup,
            args=(run_id, target_run_id, app_context)
        )
        thread.start()
        active_tasks[run_id] = thread
        
        return jsonify({
            "status": "success",
            "run_id": run_id,
            "message": f"Asynchronous rollback started for target run_id '{target_run_id}'."
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500

@data_cleaning_bp.route("/history", methods=["GET"])
@jwt_required()
def fetch_history():
    """Retrieve chronological list of past data cleaning log runs"""
    try:
        logs = DataCleaningLog.query.order_by(DataCleaningLog.created_at.desc()).all()
        return jsonify({
            "status": "success",
            "data": [l.to_dict() for l in logs]
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@data_cleaning_bp.route("/status/<run_id>", methods=["GET"])
@jwt_required()
def fetch_status(run_id):
    """Retrieve detailed state of an active cleaning run"""
    try:
        log_entry = DataCleaningLog.query.filter_by(run_id=run_id).first()
        if not log_entry:
            return jsonify({"status": "error", "message": "Cleaning log run not found"}), 404
            
        return jsonify({
            "status": "success",
            "data": log_entry.to_dict()
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@data_cleaning_bp.route("/errors", methods=["GET"])
@jwt_required()
def get_cleaning_errors():
    """Retrieve sample of rows that contain active errors for auditing"""
    try:
        table_name = request.args.get("table_name")
        error_type = request.args.get("error_type")
        
        if not table_name or not error_type:
            return jsonify({"status": "error", "message": "table_name and error_type are required"}), 400
            
        if table_name not in ("master_table", "product_master"):
            return jsonify({"status": "error", "message": "Invalid table_name"}), 400
            
        data = []
        from sqlalchemy import text
        if table_name == "master_table":
            if error_type == "duplicates":
                # Find rows belonging to a duplicate group based on name, phone, address
                q = text("""
                    SELECT m1.id, m1.business_name, m1.primary_phone, m1.address, m1.city, m1.state, m1.area
                    FROM master_table m1
                    INNER JOIN (
                        SELECT business_name, primary_phone, address
                        FROM master_table
                        WHERE business_name IS NOT NULL AND primary_phone IS NOT NULL AND address IS NOT NULL
                        GROUP BY business_name, primary_phone, address
                        HAVING COUNT(*) > 1
                    ) m2 ON m1.business_name = m2.business_name 
                        AND m1.primary_phone = m2.primary_phone 
                        AND m1.address = m2.address
                    ORDER BY m1.business_name
                    LIMIT 50
                """)
                rows = db.session.execute(q).fetchall()
                data = [
                    {
                        "id": r[0], "business_name": r[1], "primary_phone": r[2], 
                        "address": r[3], "city": r[4], "state": r[5], "area": r[6]
                    } for r in rows
                ]
            elif error_type == "missing_location":
                q = text("""
                    SELECT id, business_name, primary_phone, address, city, state, area
                    FROM master_table
                    WHERE city IS NULL OR city = '' OR state IS NULL OR state = '' OR area IS NULL OR area = ''
                    LIMIT 50
                """)
                rows = db.session.execute(q).fetchall()
                data = [
                    {
                        "id": r[0], "business_name": r[1], "primary_phone": r[2], 
                        "address": r[3], "city": r[4] or "[Missing]", "state": r[5] or "[Missing]", "area": r[6] or "[Missing]"
                    } for r in rows
                ]
            elif error_type == "invalid_phone_email":
                q = text("""
                    SELECT id, business_name, primary_phone, email, address
                    FROM master_table
                    WHERE (primary_phone IS NOT NULL AND primary_phone != '' AND NOT (primary_phone REGEXP '^[0-9+ -]{8,20}$'))
                       OR (email IS NOT NULL AND email != '' AND NOT (email REGEXP '^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$'))
                    LIMIT 50
                """)
                rows = db.session.execute(q).fetchall()
                data = [
                    {
                        "id": r[0], "business_name": r[1], "primary_phone": r[2], 
                        "email": r[3], "address": r[4]
                    } for r in rows
                ]
            elif error_type == "unmatched_location":
                q = text("""
                    SELECT id, business_name, primary_phone, address, city, state, area
                    FROM master_table
                    WHERE (state IS NOT NULL AND state != '' AND state NOT IN (SELECT DISTINCT state_full_name FROM Location_Master_India) AND state NOT IN (SELECT DISTINCT state_short_code FROM Location_Master_India))
                       OR (city IS NOT NULL AND city != '' AND city NOT IN (SELECT DISTINCT city_name FROM Location_Master_India))
                       OR (area IS NOT NULL AND area != '' AND area NOT IN (SELECT DISTINCT area_name FROM Location_Master_India))
                    LIMIT 50
                """)
                rows = db.session.execute(q).fetchall()
                data = [
                    {
                        "id": r[0], "business_name": r[1], "primary_phone": r[2], 
                        "address": r[3], "city": r[4], "state": r[5], "area": r[6]
                    } for r in rows
                ]
        elif table_name == "product_master":
            if error_type == "duplicates":
                q = text("""
                    SELECT p1.id, p1.marketplace_name, p1.asin, p1.product_name, p1.brand, p1.category_name
                    FROM product_master p1
                    INNER JOIN (
                        SELECT marketplace_name, asin
                        FROM product_master
                        WHERE asin IS NOT NULL AND asin != ''
                        GROUP BY marketplace_name, asin
                        HAVING COUNT(*) > 1
                    ) p2 ON p1.marketplace_name = p2.marketplace_name AND p1.asin = p2.asin
                    ORDER BY p1.asin
                    LIMIT 50
                """)
                rows = db.session.execute(q).fetchall()
                data = [
                    {
                        "id": r[0], "marketplace_name": r[1], "asin": r[2], 
                        "product_name": r[3], "brand": r[4], "category_name": r[5]
                    } for r in rows
                ]
            elif error_type == "wrong_category":
                q = text("""
                    SELECT id, marketplace_name, asin, product_name, brand, category_name
                    FROM product_master
                    WHERE category_name IS NOT NULL AND category_name != ''
                      AND category_name COLLATE utf8mb4_general_ci NOT IN (SELECT DISTINCT category_name COLLATE utf8mb4_general_ci FROM product_category_master)
                    LIMIT 50
                """)
                rows = db.session.execute(q).fetchall()
                data = [
                    {
                        "id": r[0], "marketplace_name": r[1], "asin": r[2], 
                        "product_name": r[3], "brand": r[4], "category_name": r[5]
                    } for r in rows
                ]
                
        return jsonify({"status": "success", "data": data})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
