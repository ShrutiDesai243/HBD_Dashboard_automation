from flask import Blueprint, request, jsonify
import sys
import os
import subprocess
from extensions import db
from model.scraper_task import ScraperTask

indiamart_scraper_bp = Blueprint('indiamart_scraper_bp', __name__)

@indiamart_scraper_bp.route('/scrape_indiamart', methods=['POST'])
def scrape_indiamart():
    try:
        data = request.get_json() or {}
        search_term = data.get('search_term')
        pages = data.get('pages', 1)

        if not search_term:
            return jsonify({'error': 'search_term is required'}), 400
            
        try:
            pages = int(pages)
            if pages <= 0:
                pages = 1
        except (TypeError, ValueError):
            pages = 1

        # Check if another IndiaMART scrape task is currently running
        running_task = ScraperTask.query.filter_by(
            platform="IndiaMart", 
            status="RUNNING"
        ).first()
        if running_task:
            return jsonify({
                "error": f"A scrape job is already active for IndiaMART (Task ID: {running_task.id}). Please wait for it to complete."
            }), 409

        # Create ScraperTask in MySQL DB to track progress
        new_task = ScraperTask(
            platform="IndiaMart",
            search_query=search_term,
            location="All India",
            status="starting",
            progress=0,
            total_found=0
        )
        db.session.add(new_task)
        db.session.commit()
            
        # Launch scraper inside a background subprocess directly to bypass Celery congestion
        backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        
        cmd = [
            sys.executable,
            "-u",
            "-m", "services.scrapers.indiamart_service",
            "--search_term", str(search_term),
            "--pages", str(pages),
            "--task_id", str(new_task.id)
        ]
            
        # Configure unbuffered UTF-8 environment for subprocess logs
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"
        env["PYTHONUNBUFFERED"] = "1"
        
        # Open log file
        log_dir = os.path.join(backend_dir, "logs")
        os.makedirs(log_dir, exist_ok=True)
        log_file_path = os.path.join(log_dir, f"indiamart_task_{new_task.id}.log")
        log_file = open(log_file_path, "a", encoding="utf-8")
        
        # Popen runs the process in the background and returns immediately
        subprocess.Popen(
            cmd,
            cwd=backend_dir,
            env=env,
            stdout=log_file,
            stderr=log_file,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        )
        
        # Update task status to RUNNING
        new_task.status = "RUNNING"
        db.session.commit()
        
        return jsonify({
            "status": "started", 
            "task_id": new_task.id,
            "message": f"IndiaMART scraping job started successfully in background with Task ID {new_task.id}."
        }), 202

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@indiamart_scraper_bp.route('/scrape_indiamart/db-stats', methods=['GET'])
def get_indiamart_db_stats():
    """
    GET /api/scrape_indiamart/db-stats
    Calculates live stats for IndiaMART tables and mappings.
    """
    try:
        from sqlalchemy import text
        
        # Product counts
        product_count = db.session.execute(text("SELECT COUNT(*) FROM indiamart_products")).scalar() or 0
        cat_count = db.session.execute(text("SELECT COUNT(DISTINCT category_name) FROM indiamart_mappings WHERE category_level IS NULL")).scalar() or 0
        brand_count = db.session.execute(text(
            "SELECT COUNT(DISTINCT manufacturer) FROM indiamart_products WHERE manufacturer IS NOT NULL AND manufacturer != ''"
        )).scalar() or 0
        avail_count = db.session.execute(text(
            "SELECT COUNT(*) FROM indiamart_products WHERE Price IS NOT NULL AND Price != ''"
        )).scalar() or 0
        
        # Category mapping breakdown
        cat_breakdown = db.session.execute(text("""
            SELECT category_name, COUNT(*) as cnt
            FROM indiamart_products
            WHERE category_name IS NOT NULL
            GROUP BY category_name
            ORDER BY cnt DESC
            LIMIT 20
        """)).mappings().fetchall()
        
        # Mapping duplicates check (mapping status and active mappings)
        mapping_dupes = db.session.execute(text("""
            SELECT COUNT(*) FROM (
                SELECT platform_category_raw, COUNT(*) c
                FROM platform_category_mapping
                WHERE platform_name = 'IndiaMart' AND is_active = 1
                GROUP BY platform_category_raw HAVING c > 1
            ) x
        """)).scalar() or 0
        
        # Tasks backfill
        last_task = ScraperTask.query.filter_by(
            platform="IndiaMart"
        ).order_by(ScraperTask.id.desc()).first()
        
        last_scrape = {
            "products_scraped": last_task.total_found if last_task else 0,
            "products_inserted": last_task.total_found if (last_task and last_task.status == "COMPLETED") else 0,
            "products_updated": 0,
            "duplicates_prevented": 0,
            "categories_synced": 0
        }

        return jsonify({
            "total_products": int(product_count),
            "total_categories": int(cat_count),
            "distinct_brands": int(brand_count),
            "available_products": int(avail_count),
            "mapping_duplicates": int(mapping_dupes),
            "products_null_category_id": 0,
            "top_categories": [
                {"category": r["category_name"], "count": int(r["cnt"])}
                for r in cat_breakdown
            ],
            "last_scrape_state": last_scrape
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
