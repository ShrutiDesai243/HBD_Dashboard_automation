from flask import Blueprint, request, jsonify
from extensions import db
from model.scraper_task import ScraperTask

dmart_api_bp = Blueprint('dmart_api_bp', __name__)

@dmart_api_bp.route('/scrape_dmart', methods=['POST'])
def scrape_dmart():
    try:
        data = request.get_json() or {}
        search_term = data.get('search_term', 'all')
        mode = data.get('mode', 'category')
        pincodes = data.get('pincodes', 'all')
        if not pincodes or str(pincodes).strip() == "":
            pincodes = 'all'
        max_categories = data.get('max_categories')
        categories = data.get('categories')

        if not search_term:
            return jsonify({'error': 'search_term is required'}), 400
            
        # Create ScraperTask in MySQL DB to monitor progress
        new_task = ScraperTask(
            platform="DMart",
            search_query=f"{search_term} ({mode})",
            location=pincodes,
            status="starting",
            progress=0,
            total_found=0
        )
        db.session.add(new_task)
        db.session.commit()
            
        # Launch scraper inside a clean background subprocess directly to bypass Celery queue congestion
        import sys
        import os
        import subprocess
        
        backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        
        cmd = [
            sys.executable,
            "-u",
            "-m", "services.scrapers.dmart_service",
            "--search_term", str(search_term),
            "--mode", str(mode),
            "--pincodes", str(pincodes),
            "--task_id", str(new_task.id)
        ]
        if max_categories is not None:
            cmd.extend(["--max_categories", str(max_categories)])
        if categories:
            cmd.extend(["--categories", str(categories)])

            
        # UTF-8 encoding environment for Windows logs compatibility and unbuffered output
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"
        env["PYTHONUNBUFFERED"] = "1"
        
        # Create logs directory and log file handle
        log_dir = os.path.join(backend_dir, "logs")
        os.makedirs(log_dir, exist_ok=True)
        log_file_path = os.path.join(log_dir, f"dmart_task_{new_task.id}.log")
        log_file = open(log_file_path, "a", encoding="utf-8")
        
        # Popen starts the process in the background and returns immediately
        subprocess.Popen(
            cmd,
            cwd=backend_dir,
            env=env,
            stdout=log_file,
            stderr=log_file
        )
        
        return jsonify({
            "status": "started", 
            "task_id": new_task.id,
            "message": f"D-Mart scraping job started successfully in background with Task ID {new_task.id}."
        }), 202

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500
