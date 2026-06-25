from flask import Blueprint, request, jsonify
from extensions import db
from model.scraper_task import ScraperTask
import sys
import os
import subprocess

flipkart_api_bp = Blueprint('flipkart_api_bp', __name__)

@flipkart_api_bp.route('/scrape_flipkart', methods=['POST'])
def scrape_flipkart():
    try:
        data = request.get_json() or {}
        search_term = data.get('search_term', 'all')
        mode = data.get('mode', 'products')  # 'products', 'discover_categories', or 'auto_discover'
        categories = data.get('categories')
        max_pages = data.get('max_pages')

        if not search_term and mode not in ('discover_categories', 'auto_discover'):
            return jsonify({'error': 'search_term is required'}), 400

        # Create ScraperTask in MySQL DB to monitor progress
        new_task = ScraperTask(
            platform="Flipkart",
            search_query=f"{search_term} ({mode})",
            status="starting",
            progress=0,
            total_found=0
        )
        db.session.add(new_task)
        db.session.commit()

        # Launch scraper inside a clean background subprocess
        backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

        service_script = os.path.join(backend_dir, "services", "scrapers", "flipkart_service.py")
        cmd = [
            sys.executable,
            service_script,
            "--search_term", str(search_term),
            "--mode", str(mode),
            "--task_id", str(new_task.id)
        ]
        if categories is not None:
            cmd.extend(["--categories", str(categories)])
        if max_pages is not None:
            cmd.extend(["--max_pages", str(max_pages)])

        # UTF-8 encoding environment for Windows logs compatibility and unbuffered output
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"
        env["PYTHONUNBUFFERED"] = "1"

        # Create logs directory and log file handle
        log_dir = os.path.join(backend_dir, "logs")
        os.makedirs(log_dir, exist_ok=True)
        log_file_path = os.path.join(log_dir, f"flipkart_task_{new_task.id}.log")
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
            "message": f"Flipkart scraping job started successfully in background with Task ID {new_task.id}."
        }), 202

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500
