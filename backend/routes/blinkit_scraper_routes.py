"""
Blinkit Scraper API Routes — Blueprint for /api/scrape_blinkit endpoints
All scraping runs as a background subprocess so the user can continue
working in the dashboard without any blocking.
"""
import os
import json
import sys
import subprocess
from flask import Blueprint, request, jsonify
from extensions import db
from model.scraper_task import ScraperTask

blinkit_scraper_bp = Blueprint("blinkit_scraper_bp", __name__)

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
STATE_FILE = os.path.join(BACKEND_DIR, "output", "blinkit_scrape_state.json")


# ── Helper ────────────────────────────────────────────────────────────────────

def _load_state() -> dict:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _get_engine():
    from sqlalchemy import create_engine
    from config import config
    return create_engine(config.SQLALCHEMY_DATABASE_URI, pool_pre_ping=True)


# ── Start Scraper ─────────────────────────────────────────────────────────────

@blinkit_scraper_bp.route("/scrape_blinkit", methods=["POST"])
def start_blinkit_scrape():
    """
    POST /api/scrape_blinkit
    Trigger Blinkit automation scraper as a background subprocess.
    Returns immediately (202) — user can continue working while scraper runs.

    Body (JSON):
        pincode         str   — delivery pincode (default: "110001")
        mode            str   — "full" | "categories" | "incremental"
        max_categories  int   — limit categories (for testing, null = all)
        resume          bool  — resume from saved state (default: false)
        selected_categories list[str] — optional: limit to specific L1 category names
    """
    try:
        data = request.get_json(silent=True) or {}
        pincode             = str(data.get("pincode", "110001")).strip()
        mode                = str(data.get("mode", "full")).strip()
        max_categories      = data.get("max_categories")
        resume              = bool(data.get("resume", False))
        selected_categories = data.get("selected_categories") or []  # List[str]

        # Validate mode
        valid_modes = ("full", "categories", "incremental")
        if mode not in valid_modes:
            return jsonify({"error": f"Invalid mode '{mode}'. Choose from: {valid_modes}"}), 400

        # Validate max_categories
        if max_categories is not None:
            try:
                max_categories = int(max_categories)
                if max_categories <= 0:
                    max_categories = None
            except (TypeError, ValueError):
                max_categories = None

        # Create ScraperTask record
        task = ScraperTask(
            platform="Blinkit",
            search_query=f"mode={mode} | pincode={pincode}",
            location=pincode,
            status="PENDING",
            progress=0,
            total_found=0,
        )
        db.session.add(task)
        db.session.commit()
        task_id = task.id

        # Build subprocess command
        cmd = [
            sys.executable,
            "-m", "services.scrapers.blinkit_service",
            "--pincode", str(pincode),
            "--mode",    str(mode),
            "--task_id", str(task_id),
        ]
        if max_categories:
            cmd.extend(["--max_categories", str(max_categories)])
        if resume:
            cmd.append("--resume")
        if selected_categories:
            # Pass as JSON string
            cmd.extend(["--selected_categories", json.dumps(selected_categories)])

        # Windows-compatible UTF-8 environment
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"

        # Log file
        log_dir = os.path.join(BACKEND_DIR, "logs")
        os.makedirs(log_dir, exist_ok=True)
        log_file_path = os.path.join(log_dir, f"blinkit_task_{task_id}.log")
        log_file = open(log_file_path, "a", encoding="utf-8")

        # Launch background subprocess (non-blocking — user can do other work)
        subprocess.Popen(
            cmd,
            cwd=BACKEND_DIR,
            env=env,
            stdout=log_file,
            stderr=log_file,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )

        # Update task status to RUNNING
        task.status = "RUNNING"
        db.session.commit()

        return jsonify({
            "status":              "started",
            "task_id":             task_id,
            "message":             f"Blinkit scraper running in background (mode={mode}, pincode={pincode}). You can continue using the dashboard.",
            "pincode":             pincode,
            "mode":                mode,
            "max_categories":      max_categories,
            "resume":              resume,
            "selected_categories": selected_categories,
            "log_file":            log_file_path,
        }), 202

    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "trace": traceback.format_exc()[-500:]}), 500


# ── Status ────────────────────────────────────────────────────────────────────

@blinkit_scraper_bp.route("/scrape_blinkit/status", methods=["GET"])
def get_blinkit_scrape_status():
    """GET /api/scrape_blinkit/status — latest task + scrape state."""
    try:
        task = (
            ScraperTask.query
            .filter_by(platform="Blinkit")
            .order_by(ScraperTask.id.desc())
            .first()
        )
        task_data  = task.to_dict() if task else None
        state_data = _load_state()

        return jsonify({"task": task_data, "state": state_data}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── History ───────────────────────────────────────────────────────────────────

@blinkit_scraper_bp.route("/scrape_blinkit/history", methods=["GET"])
def get_blinkit_scrape_history():
    """GET /api/scrape_blinkit/history — all blinkit scrape tasks."""
    try:
        limit = request.args.get("limit", 20, type=int)
        tasks = (
            ScraperTask.query
            .filter_by(platform="Blinkit")
            .order_by(ScraperTask.id.desc())
            .limit(limit)
            .all()
        )
        return jsonify([t.to_dict() for t in tasks]), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Stop ──────────────────────────────────────────────────────────────────────

@blinkit_scraper_bp.route("/scrape_blinkit/stop", methods=["POST"])
def stop_blinkit_scrape():
    """POST /api/scrape_blinkit/stop — signal stop to running scrape."""
    try:
        data    = request.get_json(silent=True) or {}
        task_id = data.get("task_id")

        if task_id:
            task = ScraperTask.query.get(task_id)
        else:
            task = (
                ScraperTask.query
                .filter_by(platform="Blinkit")
                .filter(ScraperTask.status.in_(["PENDING", "RUNNING"]))
                .order_by(ScraperTask.id.desc())
                .first()
            )

        if not task:
            return jsonify({"error": "No active Blinkit task found"}), 404

        task.should_stop = True
        task.status      = "STOPPED"
        db.session.commit()

        return jsonify({"message": f"Stop signal sent to task #{task.id}", "task_id": task.id}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Task Logs ─────────────────────────────────────────────────────────────────

@blinkit_scraper_bp.route("/tasks/<int:task_id>/blinkit-logs", methods=["GET"])
def get_blinkit_task_logs(task_id: int):
    """GET /api/tasks/{id}/blinkit-logs — stream log file for a Blinkit task."""
    try:
        log_file = os.path.join(BACKEND_DIR, "logs", f"blinkit_task_{task_id}.log")
        if not os.path.exists(log_file):
            return jsonify({"logs": [], "exists": False}), 200

        with open(log_file, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        cleaned = [line.rstrip("\n\r") for line in lines if line.strip()]
        return jsonify({"logs": cleaned[-500:], "total_lines": len(cleaned), "exists": True}), 200

    except Exception as e:
        return jsonify({"error": str(e), "logs": []}), 500


# ── DB Stats ──────────────────────────────────────────────────────────────────

@blinkit_scraper_bp.route("/scrape_blinkit/db-stats", methods=["GET"])
def get_blinkit_db_stats():
    """
    GET /api/scrape_blinkit/db-stats
    Live stats from blinkit and blinkit_mapping tables.
    """
    try:
        from sqlalchemy import text
        engine = _get_engine()

        with engine.connect() as conn:
            product_count = conn.execute(text("SELECT COUNT(*) FROM blinkit")).scalar()
            cat_count     = conn.execute(text("SELECT COUNT(*) FROM blinkit_mapping")).scalar()
            brand_count   = conn.execute(text(
                "SELECT COUNT(DISTINCT brand) FROM blinkit WHERE brand IS NOT NULL AND brand != ''"
            )).scalar()
            avail_count   = conn.execute(text(
                "SELECT COUNT(*) FROM blinkit WHERE availability = 1"
            )).scalar()
            null_cat_ids  = conn.execute(text(
                "SELECT COUNT(*) FROM blinkit WHERE category_id IS NULL"
            )).scalar()

            # Top categories by product count (joined with blinkit_mapping for proper category name)
            cat_breakdown = conn.execute(text("""
                SELECT b.category, COUNT(*) as cnt
                FROM blinkit b
                WHERE b.category IS NOT NULL
                GROUP BY b.category
                ORDER BY cnt DESC
                LIMIT 20
            """)).mappings().fetchall()

            # Duplicate check in mapping
            mapping_dupes = conn.execute(text("""
                SELECT COUNT(*) FROM (
                    SELECT category_id, COUNT(*) c
                    FROM blinkit_mapping
                    WHERE category_id IS NOT NULL
                    GROUP BY category_id HAVING c > 1
                ) x
            """)).scalar()

        state_data = _load_state()

        return jsonify({
            "total_products":           int(product_count or 0),
            "total_categories":         int(cat_count or 0),
            "distinct_brands":          int(brand_count or 0),
            "available_products":       int(avail_count or 0),
            "mapping_duplicates":       int(mapping_dupes or 0),
            "products_null_category_id": int(null_cat_ids or 0),
            "top_categories":           [
                {"category": r["category"], "count": int(r["cnt"])}
                for r in cat_breakdown
            ],
            "last_scrape_state": {
                "products_scraped":     state_data.get("products_scraped", 0),
                "products_inserted":    state_data.get("products_inserted", 0),
                "products_updated":     state_data.get("products_updated", 0),
                "duplicates_prevented": state_data.get("duplicates_prevented", 0),
                "categories_synced":    state_data.get("categories_synced", 0),
                "is_complete":          state_data.get("is_complete", False),
                "started_at":           state_data.get("started_at", ""),
                "last_updated":         state_data.get("last_updated", ""),
                "pincode":              state_data.get("pincode", ""),
                "mode":                 state_data.get("mode", ""),
            }
        }), 200

    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "trace": traceback.format_exc()[-800:]}), 500


# ── Categories for Filter ─────────────────────────────────────────────────────

@blinkit_scraper_bp.route("/scrape_blinkit/categories", methods=["GET"])
def get_blinkit_categories():
    """
    GET /api/scrape_blinkit/categories
    Returns L1 categories for the scraper category filter UI.
    """
    try:
        from sqlalchemy import text
        engine = _get_engine()

        with engine.connect() as conn:
            # L1 categories with their product counts
            rows = conn.execute(text("""
                SELECT
                    m.category_id,
                    m.category_name,
                    COUNT(DISTINCT b.product_id) as product_count,
                    COUNT(DISTINCT sub.category_id) as subcategory_count
                FROM blinkit_mapping m
                LEFT JOIN blinkit b ON b.category = m.category_name
                LEFT JOIN blinkit_mapping sub ON sub.parent_id = m.category_id
                WHERE m.parent_id = 0 OR m.category_level = 1
                GROUP BY m.category_id, m.category_name
                ORDER BY m.category_name
            """)).mappings().fetchall()

        return jsonify({
            "categories": [
                {
                    "id":                r["category_id"],
                    "name":              r["category_name"],
                    "product_count":     int(r["product_count"] or 0),
                    "subcategory_count": int(r["subcategory_count"] or 0),
                }
                for r in rows
            ],
            "total": len(rows),
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Mapping (blinkit_mapping) ─────────────────────────────────────────────────

@blinkit_scraper_bp.route("/scrape_blinkit/mapping", methods=["GET"])
def get_blinkit_mapping():
    """
    GET /api/scrape_blinkit/mapping
    Returns full blinkit_mapping hierarchy for the Data Report page.
    """
    try:
        from sqlalchemy import text
        engine = _get_engine()

        with engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT
                    m.category_id,
                    m.category_name,
                    m.parent_id,
                    m.category_level,
                    m.full_category_path,
                    p.category_name as parent_name,
                    COUNT(DISTINCT b.product_id) as product_count
                FROM blinkit_mapping m
                LEFT JOIN blinkit_mapping p ON p.category_id = m.parent_id
                LEFT JOIN blinkit b ON b.category_id = m.category_id
                GROUP BY m.category_id, m.category_name, m.parent_id, m.category_level,
                         m.full_category_path, p.category_name
                ORDER BY m.category_level, m.category_name
            """)).mappings().fetchall()

        return jsonify({
            "mapping": [
                {
                    "category_id":         r["category_id"],
                    "category_name":       r["category_name"],
                    "parent_id":           r["parent_id"],
                    "parent_name":         r["parent_name"],
                    "category_level":      r["category_level"],
                    "full_category_path":  r["full_category_path"],
                    "product_count":       int(r["product_count"] or 0),
                }
                for r in rows
            ],
            "total": len(rows),
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
