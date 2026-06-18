from flask import Blueprint, request, jsonify
from extensions import db
from model.scraper_task import ScraperTask

import os
import sys
import subprocess
import logging

logger = logging.getLogger(__name__)

zepto_api_bp = Blueprint('zepto_api_bp', __name__)


@zepto_api_bp.route('/scrape_zepto', methods=['POST'])
def scrape_zepto():
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

        # Create ScraperTask in MySQL DB
        new_task = ScraperTask(
            platform="Zepto",
            search_query=f"{search_term} ({mode})",
            location=pincodes,
            status="starting",
            progress=0,
            total_found=0,
        )
        db.session.add(new_task)
        db.session.commit()

        # Launch scraper in background subprocess (mirrors DMart route)
        backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

        cmd = [
            sys.executable,
            "-u",
            "-m",
            "services.scrapers.zepto_service",
            "--pincodes",
            str(pincodes),
            "--task_id",
            str(new_task.id),
        ]

        if max_categories is not None:
            cmd.extend(["--max_categories", str(max_categories)])
        if categories:
            cmd.extend(["--categories", str(categories)])

        # UTF-8 encoding for Windows log compatibility and unbuffered output
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"
        env["PYTHONUNBUFFERED"] = "1"

        log_dir = os.path.join(backend_dir, "logs")
        os.makedirs(log_dir, exist_ok=True)
        log_file_path = os.path.join(log_dir, f"zepto_task_{new_task.id}.log")
        log_file = open(log_file_path, "a", encoding="utf-8")

        subprocess.Popen(
            cmd,
            cwd=backend_dir,
            env=env,
            stdout=log_file,
            stderr=log_file,
        )

        return jsonify({
            "status": "started",
            "task_id": new_task.id,
            "message": f"Zepto scraping job started successfully in background with Task ID {new_task.id}.",
        }), 202

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

