from flask import Blueprint, request, jsonify
from extensions import db
from model.scraper_task import ScraperTask

jiomart_api_bp = Blueprint('jiomart_api_bp', __name__)

@jiomart_api_bp.route('/scrape_jiomart', methods=['POST'])
def scrape_jiomart():
    try:
        data = request.get_json() or {}
        resume = data.get('resume', False)
        max_categories = data.get('max_categories')

        # Create ScraperTask in MySQL DB to monitor progress
        search_query = "Resume Last Run" if resume else "Full Scrape"
        if max_categories:
            search_query += f" (Limit: {max_categories})"

        new_task = ScraperTask(
            platform="JioMart",
            search_query=search_query,
            location="Mumbai (400001)",
            status="starting",
            progress=0,
            total_found=0
        )
        db.session.add(new_task)
        db.session.commit()
            
        import sys
        import os
        import subprocess
        
        backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        
        cmd = [
            sys.executable,
            "-u",
            "-m", "services.scrapers.jiomart_engine.scraper",
            "--task_id", str(new_task.id)
        ]
        if resume:
            cmd.append("--resume")
        if max_categories is not None:
            cmd.extend(["--max_categories", str(max_categories)])

        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"
        env["PYTHONUNBUFFERED"] = "1"
        
        log_dir = os.path.join(backend_dir, "logs")
        os.makedirs(log_dir, exist_ok=True)
        log_file_path = os.path.join(log_dir, f"jiomart_task_{new_task.id}.log")
        log_file = open(log_file_path, "a", encoding="utf-8")
        
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
            "message": f"JioMart scraping job started successfully in background with Task ID {new_task.id}."
        }), 202

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@jiomart_api_bp.route('/jiomart/recent_products', methods=['GET'])
def get_jiomart_recent_products():
    try:
        from model.product_model.additional_products import JioMartProduct, JioMartCategory
        products = db.session.query(
            JioMartProduct, JioMartCategory.category_name
        ).outerjoin(
            JioMartCategory, JioMartProduct.category_id == JioMartCategory.category_id
        ).order_by(
            JioMartProduct.id.desc()
        ).limit(10).all()

        result = []
        for prod, cat_name in products:
            result.append({
                "id": prod.id,
                "sku_id": prod.sku_id,
                "product_name": prod.product_name,
                "brand": prod.brand,
                "price": float(prod.price) if prod.price else 0,
                "mrp": float(prod.mrp) if prod.mrp else 0,
                "quantity": prod.quantity,
                "size": prod.size,
                "category_id": prod.category_id,
                "category_name": cat_name,
                "product_url": prod.product_url,
                "image_url": prod.image_url
            })
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

