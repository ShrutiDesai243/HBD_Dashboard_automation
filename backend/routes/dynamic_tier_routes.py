from flask import Blueprint, jsonify, request, Response
from extensions import db
from sqlalchemy import text
from services.dynamic_cleaning_service import clean_and_route_batch
import os
import sys
import subprocess
import csv
import io

dynamic_tier_bp = Blueprint('dynamic_tier_bp', __name__)

@dynamic_tier_bp.route('/api/tiers/stats', methods=['GET'])
def get_tier_stats():
    """Returns the total row count for each tier."""
    try:
        source_table = request.args.get('source_table', 'ALL')
        
        where_clause = ""
        params = {}
        if source_table and source_table != "ALL":
            where_clause = "WHERE raw_source_table = :src"
            params = {"src": source_table}
            
            # Exact count when filtered
            t1 = db.session.execute(text(f"SELECT COUNT(*) FROM tier1_master_clean {where_clause}"), params).fetchone()[0]
            t2 = db.session.execute(text(f"SELECT COUNT(*) FROM tier2_missing_contact {where_clause}"), params).fetchone()[0]
            t3 = db.session.execute(text(f"SELECT COUNT(*) FROM tier3_missing_location {where_clause}"), params).fetchone()[0]
            t4 = db.session.execute(text(f"SELECT COUNT(*) FROM tier4_partial_fragments {where_clause}"), params).fetchone()[0]
            t5 = db.session.execute(text(f"SELECT COUNT(*) FROM tier5_linked_duplicates {where_clause}"), params).fetchone()[0]
        else:
            # Fast approximate count from information_schema when checking ALL tables
            query = text("SELECT TABLE_ROWS FROM information_schema.tables WHERE table_name = :tname AND table_schema = DATABASE()")
            t1 = db.session.execute(query, {"tname": "tier1_master_clean"}).fetchone()[0] or 0
            t2 = db.session.execute(query, {"tname": "tier2_missing_contact"}).fetchone()[0] or 0
            t3 = db.session.execute(query, {"tname": "tier3_missing_location"}).fetchone()[0] or 0
            t4 = db.session.execute(query, {"tname": "tier4_partial_fragments"}).fetchone()[0] or 0
            t5 = db.session.execute(query, {"tname": "tier5_linked_duplicates"}).fetchone()[0] or 0

        return jsonify({
            "status": "success",
            "stats": [
                {"tier": "tier1", "name": "Master Clean", "count": t1, "color": "bg-green-500"},
                {"tier": "tier2", "name": "Missing Contact", "count": t2, "color": "bg-blue-500"},
                {"tier": "tier3", "name": "Missing Location", "count": t3, "color": "bg-yellow-500"},
                {"tier": "tier4", "name": "Partial Fragments", "count": t4, "color": "bg-orange-500"},
                {"tier": "tier5", "name": "Linked Duplicates", "count": t5, "color": "bg-red-500"}
            ]
        }), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@dynamic_tier_bp.route('/api/tiers/run-cleaner', methods=['POST'])
def run_dynamic_cleaner():
    """Starts the dynamic cleaner as a background process and returns immediately."""
    try:
        limit = request.json.get('limit', 100) if request.is_json else 100
        table = request.json.get('table', 'raw_clean_google_map_data') if request.is_json else 'raw_clean_google_map_data'
        
        # Make sure logs dir exists
        log_dir = os.path.join(os.path.dirname(__file__), "..", "logs")
        os.makedirs(log_dir, exist_ok=True)
        
        # Clear any previous stop signal
        stop_file = os.path.join(log_dir, "stop_dynamic_cleaner")
        if os.path.exists(stop_file):
            os.remove(stop_file)

        log_file_path = os.path.join(log_dir, "dynamic_cleaner.log")
        
        # Clear the old log file
        with open(log_file_path, "w", encoding="utf-8") as f:
            f.write(f"--- Starting new cleaner run (Limit: {limit}, Table: {table}) ---\n")

        cmd = [
            sys.executable,
            "test_dynamic_cleaner.py",
            "--limit", str(limit),
            "--table", str(table)
        ]

        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"

        backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

        # Launch non-blocking background task
        log_file = open(log_file_path, "a", encoding="utf-8")
        subprocess.Popen(
            cmd,
            cwd=backend_dir,
            env=env,
            stdout=log_file,
            stderr=log_file,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        
        return jsonify({
            "status": "success",
            "message": f"Background cleaner task started successfully (Limit: {limit}, Table: {table}). Check terminal for progress."
        }), 202
        
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@dynamic_tier_bp.route('/api/tiers/prepare-table', methods=['POST'])
def prepare_table():
    """Explicitly adds required tracking columns to the specified table so it's fit for cleaning."""
    try:
        table_name = request.json.get('table')
        if not table_name:
            return jsonify({"status": "error", "message": "Table name is required"}), 400

        # Fetch existing columns
        columns_query = db.session.execute(text(f"SHOW COLUMNS FROM {table_name}")).fetchall()
        col_names = [col[0].lower() for col in columns_query]

        added_cols = []
        if 'cleaning_status' not in col_names:
            db.session.execute(text(f"ALTER TABLE {table_name} ADD COLUMN cleaning_status VARCHAR(50) DEFAULT 'PENDING'"))
            added_cols.append('cleaning_status')
        if 'assigned_tier' not in col_names:
            db.session.execute(text(f"ALTER TABLE {table_name} ADD COLUMN assigned_tier VARCHAR(100) DEFAULT NULL"))
            added_cols.append('assigned_tier')
        if 'quality_score' not in col_names:
            db.session.execute(text(f"ALTER TABLE {table_name} ADD COLUMN quality_score INT DEFAULT NULL"))
            added_cols.append('quality_score')

        db.session.commit()
        return jsonify({
            "status": "success", 
            "message": f"Table '{table_name}' prepared successfully. Added columns: {added_cols if added_cols else 'None (Already fit)'}"
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500

@dynamic_tier_bp.route('/api/tiers/tables', methods=['GET'])
def get_tables():
    """Returns a list of all tables in the database so the user can select one."""
    try:
        rows = db.session.execute(text("SHOW TABLES")).fetchall()
        tables = []
        for r in rows:
            val = r[0]
            if isinstance(val, bytes):
                tables.append(val.decode('utf-8'))
            else:
                tables.append(str(val))
                
        return jsonify({"status": "success", "tables": tables}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@dynamic_tier_bp.route('/api/tiers/cleaner-status', methods=['GET'])
def cleaner_status():
    """Checks if the cleaner is currently running by checking for the running lockfile."""
    try:
        running_file = os.path.join(os.path.dirname(__file__), "..", "logs", "cleaner.running")
        is_running = os.path.exists(running_file)
        
        table = None
        if is_running:
            with open(running_file, "r") as f:
                table = f.read().strip()
                
        return jsonify({"is_running": is_running, "table": table}), 200
    except Exception as e:
        return jsonify({"is_running": False, "error": str(e)}), 500

@dynamic_tier_bp.route('/api/tiers/cleaner-logs', methods=['GET'])
def get_cleaner_logs():
    """Streams the last 100 lines of the cleaner log file."""
    try:
        log_file = os.path.join(os.path.dirname(__file__), "..", "logs", "dynamic_cleaner.log")
        if not os.path.exists(log_file):
            return jsonify({"logs": ["Waiting for logs..."], "exists": False}), 200

        with open(log_file, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        cleaned = [line.rstrip("\n\r") for line in lines]
        return jsonify({"logs": cleaned[-100:], "exists": True}), 200

    except Exception as e:
        return jsonify({"error": str(e), "logs": []}), 500

@dynamic_tier_bp.route('/api/tiers/stop-cleaner', methods=['POST'])
def stop_cleaner():
    """Sends a stop signal to the background cleaner."""
    try:
        log_dir = os.path.join(os.path.dirname(__file__), "..", "logs")
        os.makedirs(log_dir, exist_ok=True)
        stop_file = os.path.join(log_dir, "stop_dynamic_cleaner")
        
        with open(stop_file, "w") as f:
            f.write("stop")

        # Also remove the running lockfile instantly to update UI
        running_file = os.path.join(log_dir, "cleaner.running")
        if os.path.exists(running_file):
            try:
                os.remove(running_file)
            except Exception:
                pass

        return jsonify({"status": "success", "message": "Stop signal sent to cleaner."}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@dynamic_tier_bp.route('/api/tiers/<tier_name>', methods=['GET'])
def get_tier_data(tier_name):
    """Returns the top 100 records for the requested tier."""
    valid_tiers = {
        "tier1": "tier1_master_clean",
        "tier2": "tier2_missing_contact",
        "tier3": "tier3_missing_location",
        "tier4": "tier4_partial_fragments",
        "tier5": "tier5_linked_duplicates"
    }

    if tier_name not in valid_tiers:
        return jsonify({"status": "error", "message": "Invalid tier name"}), 400

    table_name = valid_tiers[tier_name]
    
    try:
        source_table = request.args.get('source_table', 'ALL')
        where_clause = ""
        params = {}
        order_clause = "ORDER BY id DESC"
        
        if source_table and source_table != "ALL":
            where_clause = "WHERE raw_source_table = :src"
            params = {"src": source_table}
            # Use raw_source_id for sorting when filtering by source table to utilize the composite index perfectly
            order_clause = "ORDER BY raw_source_id DESC"

        # Fetching top 100
        rows = db.session.execute(text(f"SELECT * FROM {table_name} {where_clause} {order_clause} LIMIT 100"), params).fetchall()
        columns = db.session.execute(text(f"SHOW COLUMNS FROM {table_name}")).fetchall()
        col_names = [col[0] for col in columns]

        data = []
        for row in rows:
            record = {}
            for idx, col in enumerate(col_names):
                record[col] = row[idx]
            data.append(record)

        return jsonify({
            "status": "success",
            "tier": tier_name,
            "data": data
        }), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@dynamic_tier_bp.route('/api/tiers/<tier_name>/export', methods=['GET'])
def export_tier_data(tier_name):
    """Exports all records for a specific tier as a CSV file."""
    valid_tiers = {
        "tier1": "tier1_master_clean",
        "tier2": "tier2_missing_contact",
        "tier3": "tier3_missing_location",
        "tier4": "tier4_partial_fragments",
        "tier5": "tier5_linked_duplicates"
    }

    if tier_name not in valid_tiers:
        return jsonify({"status": "error", "message": "Invalid tier name"}), 400

    table_name = valid_tiers[tier_name]
    
    try:
        source_table = request.args.get('source_table', 'ALL')
        where_clause = ""
        params = {}
        if source_table and source_table != "ALL":
            where_clause = "WHERE raw_source_table = :src"
            params = {"src": source_table}

        # Fetch all data (no limit)
        rows = db.session.execute(text(f"SELECT * FROM {table_name} {where_clause} ORDER BY id DESC"), params).fetchall()
        columns = db.session.execute(text(f"SHOW COLUMNS FROM {table_name}")).fetchall()
        col_names = [col[0] for col in columns]

        # Generate CSV in memory
        si = io.StringIO()
        cw = csv.writer(si)
        cw.writerow(col_names)  # Write header
        
        for row in rows:
            cw.writerow(row)
            
        output = si.getvalue()
        
        filename = f"{table_name}_{source_table}.csv" if source_table != "ALL" else f"{table_name}_all.csv"
        
        return Response(
            output,
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment;filename={filename}"}
        )
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

