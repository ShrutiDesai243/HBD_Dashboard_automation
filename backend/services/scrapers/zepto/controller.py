from flask import Blueprint, jsonify, request
from extensions import db
from model.scraper_task import ScraperTask
from . import runner
from . import state
from datetime import datetime, timedelta
import time

zepto_scraper_bp = Blueprint("zepto_scraper_bp", __name__)

@zepto_scraper_bp.route("/scraper/zepto/start", methods=["POST"])
def start_zepto():
    data = request.json or {}
    category = data.get("category", "").strip()
    pincodes = data.get("pincodes", "").strip()
    resume = bool(data.get("resume", False))
    
    if not pincodes:
        try:
            from .zepto_scraper import load_default_pincodes
            pincodes = load_default_pincodes()
        except Exception:
            pincodes = "400053,560034,110016,122002,500081"
            
    # Create the ScraperTask record
    try:
        new_task = ScraperTask(
            platform="Zepto",
            search_query=f"{category or 'all'} (resume)" if resume else (category or "all"),
            location=pincodes,
            status="starting",
            progress=0,
            total_found=0,
        )
        db.session.add(new_task)
        db.session.commit()
        task_id = new_task.id
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": f"Failed to create database task record: {e}"}), 500
        
    success, message = runner.start_scraper(category, pincodes, task_id, resume=resume)
    if success:
        return jsonify({"status": "success", "message": message, "task_id": task_id}), 200
    else:
        # Delete task if starting failed
        try:
            db.session.delete(new_task)
            db.session.commit()
        except Exception:
            pass
        return jsonify({"status": "error", "message": message}), 400

@zepto_scraper_bp.route("/scraper/zepto/stop", methods=["POST"])
def stop_zepto():
    success, message = runner.stop_scraper()
    if success:
        return jsonify({"status": "success", "message": message}), 200
    else:
        return jsonify({"status": "error", "message": message}), 400

@zepto_scraper_bp.route("/scraper/zepto/status", methods=["GET"])
def get_zepto_status():
    current_state = state.get_state()
    return jsonify({
        "status": "success",
        "data": current_state
    }), 200

@zepto_scraper_bp.route("/scraper/zepto/logs", methods=["GET"])
def get_zepto_logs():
    try:
        limit = request.args.get("limit", 100, type=int)
    except Exception:
        limit = 100
        
    logs = state.get_logs(limit)
    return jsonify({
        "status": "success",
        "logs": logs
    }), 200

@zepto_scraper_bp.route("/scraper/zepto/history", methods=["GET"])
def get_zepto_history():
    try:
        # Get the 3 most recent tasks for platform="Zepto"
        tasks = (
            ScraperTask.query
            .filter_by(platform="Zepto")
            .order_by(ScraperTask.id.desc())
            .limit(3)
            .all()
        )
        
        # Calculate timezone offset to convert UTC database timestamps to local time
        tz_offset_seconds = -time.timezone if time.daylight == 0 else -time.altzone
        tz_offset = timedelta(seconds=tz_offset_seconds)
        
        history_list = []
        for t in tasks:
            # Parse stop time
            stopped_at = "N/A"
            duration = "N/A"
            
            if t.error_message and t.error_message.startswith("Stopped: "):
                parts = t.error_message.split(" | ")
                stopped_at = parts[0].replace("Stopped: ", "").strip()
            elif t.status == "RUNNING" or t.status.startswith("Pincode") or t.status == "starting":
                stopped_at = "Running..."
                
            # Localize start time from database UTC
            started_at_local = "N/A"
            if t.created_at:
                local_dt = t.created_at + tz_offset
                started_at_local = local_dt.strftime("%Y-%m-%d %H:%M:%S")
                
                # Calculate duration
                if stopped_at == "Running...":
                    # Dynamic active duration
                    diff = datetime.now() - local_dt
                    diff_seconds = max(0, int(diff.total_seconds()))
                    if diff_seconds < 60:
                        duration = f"{diff_seconds}s (active)"
                    else:
                        duration = f"{diff_seconds // 60}m {diff_seconds % 60}s (active)"
                elif stopped_at != "N/A":
                    try:
                        stopped_dt = datetime.strptime(stopped_at, "%Y-%m-%d %H:%M:%S")
                        diff = stopped_dt - local_dt
                        diff_seconds = max(0, int(diff.total_seconds()))
                        if diff_seconds < 60:
                            duration = f"{diff_seconds}s"
                        else:
                            duration = f"{diff_seconds // 60}m {diff_seconds % 60}s"
                    except Exception:
                        pass
                
            history_list.append({
                "id": t.id,
                "query": t.search_query,
                "pincodes": t.location or "default",
                "started_at": started_at_local,
                "stopped_at": stopped_at,
                "duration": duration,
                "total_leads": t.total_found,
                "status": t.status
            })
            
        return jsonify({
            "status": "success",
            "history": history_list
        }), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@zepto_scraper_bp.route("/scraper/zepto/db-stats", methods=["GET"])
def get_zepto_db_stats():
    try:
        from sqlalchemy import text
        product_count = db.session.execute(text("SELECT COUNT(*) FROM zepto")).scalar()
        category_count = db.session.execute(text("SELECT COUNT(*) FROM zepto_db_mapping")).scalar()
        return jsonify({
            "status": "success",
            "total_products": int(product_count or 0),
            "total_categories": int(category_count or 0)
        }), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

