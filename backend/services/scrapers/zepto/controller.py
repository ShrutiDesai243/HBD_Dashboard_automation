from flask import Blueprint, jsonify, request
from . import runner
from . import state

zepto_scraper_bp = Blueprint("zepto_scraper_bp", __name__)

@zepto_scraper_bp.route("/scraper/zepto/start", methods=["POST"])
def start_zepto():
    data = request.json or {}
    category = data.get("category", "").strip()
    pincodes = data.get("pincodes", "").strip()
    
    success, message = runner.start_scraper(category, pincodes)
    if success:
        return jsonify({"status": "success", "message": message}), 200
    else:
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
