"""
BigBasket Scraper Routes
========================
Endpoints:
  POST   /api/scrape_bigbasket          - Start a new BB scrape job
  GET    /api/scrape_bigbasket/csv/<id> - Download the generated CSV
  GET    /api/scrape_bigbasket/preview/<id> - Full CSV preview (all rows)
  POST   /api/scrape_bigbasket/merge/<id>  - Approve & merge CSV into DB
  GET    /api/scrape_bigbasket/tasks        - Task history for BB scrapes
  GET    /api/scrape_bigbasket/unmapped-categories - Get new BigBasket categories needing mapping
  GET    /api/scrape_bigbasket/unmapped-subcategories?category=<name> - Get new BigBasket subcategories needing mapping
  GET    /api/scrape_bigbasket/mapping - List existing BigBasket mappings
  POST   /api/scrape_bigbasket/mapping - Add a new BigBasket DB mapping
"""

import os
import sys
import csv
import json
import shutil
import subprocess
import datetime
import tempfile

from flask import Blueprint, request, jsonify, send_file
from extensions import db
from model.scraper_task import ScraperTask
from model.product_model.bigbasket_product_model import BigBasket

bigbasket_api_bp = Blueprint('bigbasket_api_bp', __name__)


# ─── Output directories ───────────────────────────────────────────────────────

TMP_CSV_OUTPUT_DIR = os.path.abspath(
    os.path.join(tempfile.gettempdir(), 'HBD_Dashboard_automation', 'bigbasket')
)
OLD_CSV_OUTPUT_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', 'csv_output', 'bigbasket')
)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _task_metadata_path(task_id, base_dir):
    return os.path.join(base_dir, f'task_{task_id}.json')


def _load_task_metadata(task_id, base_dir):
    meta_path = _task_metadata_path(task_id, base_dir)
    if not os.path.exists(meta_path):
        return None
    try:
        with open(meta_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None


def _migrate_task_csv(task_id, old_base_dir, new_base_dir):
    """Copy legacy task CSV and metadata into the temp output directory."""
    payload = _load_task_metadata(task_id, old_base_dir)
    if not payload:
        return None

    old_csv_path = payload.get('csv_path')
    if not old_csv_path or not os.path.exists(old_csv_path):
        return None

    os.makedirs(new_base_dir, exist_ok=True)
    csv_name = os.path.basename(old_csv_path)
    new_csv_path = os.path.join(new_base_dir, csv_name)

    try:
        if os.path.abspath(old_csv_path) != os.path.abspath(new_csv_path):
            shutil.copy2(old_csv_path, new_csv_path)

        new_payload = dict(payload, csv_path=new_csv_path)
        with open(_task_metadata_path(task_id, new_base_dir), 'w', encoding='utf-8') as f:
            json.dump(new_payload, f)
        return new_csv_path
    except Exception:
        return None


def _find_bigbasket_csv(task_id):
    """Locate the CSV file associated with a task ID."""
    # Search the temp directory first
    temp_meta = _load_task_metadata(task_id, TMP_CSV_OUTPUT_DIR)
    if temp_meta:
        csv_path = temp_meta.get('csv_path')
        if csv_path and os.path.exists(csv_path):
            return csv_path

    if os.path.isdir(TMP_CSV_OUTPUT_DIR):
        for filename in sorted(os.listdir(TMP_CSV_OUTPUT_DIR), reverse=True):
            if filename.endswith('.csv') and str(task_id) in filename:
                return os.path.join(TMP_CSV_OUTPUT_DIR, filename)

    # Preserve compatibility with legacy repo storage and migrate files if found
    legacy_csv = None
    legacy_meta = _load_task_metadata(task_id, OLD_CSV_OUTPUT_DIR)
    if legacy_meta:
        legacy_csv = legacy_meta.get('csv_path')
        if legacy_csv and os.path.exists(legacy_csv):
            return _migrate_task_csv(task_id, OLD_CSV_OUTPUT_DIR, TMP_CSV_OUTPUT_DIR)

    if os.path.isdir(OLD_CSV_OUTPUT_DIR):
        for filename in sorted(os.listdir(OLD_CSV_OUTPUT_DIR), reverse=True):
            if filename.endswith('.csv') and str(task_id) in filename:
                legacy_csv = os.path.join(OLD_CSV_OUTPUT_DIR, filename)
                if os.path.exists(legacy_csv):
                    return _migrate_task_csv(task_id, OLD_CSV_OUTPUT_DIR, TMP_CSV_OUTPUT_DIR)

    return None


# ─── Routes ──────────────────────────────────────────────────────────────────

@bigbasket_api_bp.route('/scrape_bigbasket', methods=['POST'])
def scrape_bigbasket():
    """
    Start a BigBasket category scrape job.

    Body (JSON):
        category      (str, required)  — e.g. "Fruits & Vegetables"
        subcategories (str, optional)  — comma-sep e.g. "Fruits,Vegetables"
        pages         (int, optional)  — max scroll rounds per page (default 10)
    """
    try:
        data = request.get_json() or {}
        category = (data.get('category') or '').strip()
        subcategories = (data.get('subcategories') or '').strip()
        pages = int(data.get('pages', 10))

        if not category:
            return jsonify({'error': 'category is required'}), 400

        if pages < 1 or pages > 200:
            return jsonify({'error': 'pages must be between 1 and 200'}), 400

        # Create DB task record
        query_label = category
        if subcategories:
            query_label += f' | {subcategories}'

        new_task = ScraperTask(
            platform='BigBasket',
            search_query=query_label,
            status='starting',
            progress=0,
            total_found=0
        )
        db.session.add(new_task)
        db.session.commit()

        backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        log_dir = os.path.join(backend_dir, 'logs')
        os.makedirs(log_dir, exist_ok=True)
        log_file_path = os.path.join(log_dir, f'bigbasket_task_{new_task.id}.log')

        cmd = [
            sys.executable,
            '-m', 'services.scrapers.bigbasket_service',
            '--category', category,
            '--pages', str(pages),
            '--task-id', str(new_task.id),
        ]
        if subcategories:
            cmd.extend(['--subcategories', subcategories])

        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        env['PYTHONUTF8'] = '1'

        log_file = open(log_file_path, 'a', encoding='utf-8')
        subprocess.Popen(cmd, cwd=backend_dir, env=env, stdout=log_file, stderr=log_file)

        return jsonify({
            'status': 'started',
            'task_id': new_task.id,
            'message': f'BigBasket scraping started. Category: "{category}". Task ID: {new_task.id}.',
            'download_url': f'/api/scrape_bigbasket/csv/{new_task.id}',
            'preview_url': f'/api/scrape_bigbasket/preview/{new_task.id}',
            'merge_url': f'/api/scrape_bigbasket/merge/{new_task.id}',
        }), 202

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@bigbasket_api_bp.route('/scrape_bigbasket/csv/<int:task_id>', methods=['GET'])
def download_bigbasket_csv(task_id):
    """Download the generated CSV file for a task."""
    csv_file = _find_bigbasket_csv(task_id)
    if not csv_file:
        return jsonify({'error': 'CSV file not found for this task. Scraping may still be in progress.'}), 404
    return send_file(csv_file, as_attachment=True, download_name=os.path.basename(csv_file))


@bigbasket_api_bp.route('/scrape_bigbasket/preview/<int:task_id>', methods=['GET'])
def preview_bigbasket_csv(task_id):
    """
    Return the full CSV content for preview.
    Query params:
        limit (int) — optional max rows (default: all)
    """
    csv_file = _find_bigbasket_csv(task_id)
    if not csv_file:
        return jsonify({'headers': [], 'rows': [], 'total': 0}), 200

    limit = request.args.get('limit', None)
    rows = []
    headers = []

    try:
        with open(csv_file, 'r', encoding='utf-8', errors='ignore') as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames or []
            for idx, row in enumerate(reader):
                if limit and idx >= int(limit):
                    break
                rows.append(dict(row))
    except Exception as e:
        return jsonify({'error': str(e)}), 500

    return jsonify({
        'headers': headers,
        'rows': rows,
        'total': len(rows),
        'filename': os.path.basename(csv_file)
    })


@bigbasket_api_bp.route('/scrape_bigbasket/merge/<int:task_id>', methods=['POST'])
def merge_bigbasket_csv(task_id):
    """
    Approve and merge the scraped CSV into the BigBasket products DB table.
    Deduplicates by product name + category. Marks task status as MERGED.
    """
    try:
        task = db.session.get(ScraperTask, task_id)
        if not task:
            return jsonify({'error': f'Task {task_id} not found'}), 404

        if task.status == 'MERGED':
            return jsonify({'error': 'This task has already been merged into the database.'}), 409

        if task.status not in ('COMPLETED', 'FAILED'):
            return jsonify({'error': f'Task is not ready for merge. Current status: {task.status}'}), 400

        csv_file = _find_bigbasket_csv(task_id)
        if not csv_file:
            return jsonify({'error': 'CSV file not found. Cannot merge.'}), 404

        inserted = 0
        skipped = 0
        errors = 0
        now_str = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        
        new_cats_found = set()
        new_subcats_found = set()

        # Load existing products to deduplicate quickly
        existing_products = set()
        try:
            from sqlalchemy import text
            res = db.session.execute(text("SELECT product FROM bigbasket"))
            for r in res:
                if r[0]:
                    existing_products.add(r[0].strip().lower())
        except Exception as e:
            print(f"Failed to load existing products for deduplication: {e}")

        with open(csv_file, 'r', encoding='utf-8', errors='ignore') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    product_name = (row.get('product_name') or '').strip()
                    category = (row.get('main_category') or '').strip()
                    subcategory = (row.get('subcategory') or '').strip()
                    mrp = (row.get('mrp') or '0').strip()
                    selling_price = (row.get('selling_price') or '0').strip()
                    rating = (row.get('rating') or '0').strip()
                    product_url = (row.get('product_url') or '').strip()

                    if not product_name:
                        skipped += 1
                        continue

                    if category:
                        new_cats_found.add(category)
                        if subcategory:
                            new_subcats_found.add((category, subcategory))

                    if product_name.lower() in existing_products:
                        skipped += 1
                        continue
                        
                    existing_products.add(product_name.lower())

                    entry = BigBasket(
                        product=product_name,
                        category=category,
                        sub_category=subcategory,
                        brand='',
                        sale_price=selling_price,
                        market_price=mrp,
                        type='scraped',
                        rating=rating,
                        description=product_url,
                        created_at=now_str
                    )
                    db.session.add(entry)
                    inserted += 1

                    # Commit in batches of 200 for performance
                    if inserted % 200 == 0:
                        db.session.commit()

                except Exception:
                    errors += 1
                    continue

        db.session.commit()

        # Update bigbasket_dbmapping table mapping
        try:
            from sqlalchemy import text
            res = db.session.execute(text("SELECT category_id, category_name, parent_id, category_level, full_category_path FROM bigbasket_dbmapping"))
            existing_cats = {}
            existing_subcats = set()
            max_id = 0
            
            for r in res:
                cid = r[0] if r[0] is not None else 0
                if cid > max_id: max_id = cid
                
                cname = (r[1] or '').strip().lower()
                clevel = r[3] if r[3] is not None else 1
                cpath = (r[4] or '').strip().lower()
                
                if clevel == 1:
                    existing_cats[cname] = cid
                elif clevel == 2:
                    existing_subcats.add(cpath)
            
            rows_to_insert = []
            
            for c in new_cats_found:
                clower = c.strip().lower()
                if clower not in existing_cats:
                    max_id += 1
                    existing_cats[clower] = max_id
                    rows_to_insert.append({
                        "category_id": max_id,
                        "category_name": c,
                        "parent_id": 0,
                        "category_level": 1,
                        "full_category_path": c
                    })
            
            for c, sc in new_subcats_found:
                clower = c.strip().lower()
                sclower = sc.strip().lower()
                path = f"{clower} > {sclower}"
                if path not in existing_subcats:
                    parent_id = existing_cats.get(clower, 0)
                    max_id += 1
                    existing_subcats.add(path)
                    rows_to_insert.append({
                        "category_id": max_id,
                        "category_name": sc,
                        "parent_id": parent_id,
                        "category_level": 2,
                        "full_category_path": f"{c} > {sc}"
                    })
            
            if rows_to_insert:
                stmt = text("""
                    INSERT INTO bigbasket_dbmapping (category_id, category_name, parent_id, category_level, full_category_path) 
                    VALUES (:category_id, :category_name, :parent_id, :category_level, :full_category_path)
                """)
                db.session.execute(stmt, rows_to_insert)
                db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"Error updating bigbasket_dbmapping table: {e}")

        # Update task status
        task.status = 'MERGED'
        db.session.commit()

        return jsonify({
            'success': True,
            'task_id': task_id,
            'inserted': inserted,
            'skipped': skipped,
            'errors': errors,
            'message': f'Successfully merged {inserted} new products into the database. ({skipped} duplicates skipped)'
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@bigbasket_api_bp.route('/scrape_bigbasket/unmapped-categories', methods=['GET'])
def get_unmapped_bigbasket_categories():
    """Return BigBasket main categories that are not mapped yet."""
    try:
        from sqlalchemy import text
        rows = db.session.execute(text("""
            SELECT DISTINCT main_category
            FROM bigbasket
            WHERE main_category IS NOT NULL
              AND main_category != ''
              AND main_category NOT IN (
                  SELECT category_name FROM bigbasket_dbmapping WHERE category_level = 1 AND category_name IS NOT NULL
              )
            ORDER BY main_category ASC
        """)).fetchall()
        data = [{'category_name': r[0]} for r in rows]
        return jsonify({'status': 'success', 'data': data, 'total': len(data)}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@bigbasket_api_bp.route('/scrape_bigbasket/unmapped-subcategories', methods=['GET'])
def get_unmapped_bigbasket_subcategories():
    """Return BigBasket subcategories for a given main category that are not mapped yet."""
    category = (request.args.get('category') or '').strip()
    if not category:
        return jsonify({'status': 'error', 'message': 'category query parameter is required'}), 400

    try:
        from sqlalchemy import text
        rows = db.session.execute(text("""
            SELECT DISTINCT subcategory
            FROM bigbasket
            WHERE main_category = :category
              AND subcategory IS NOT NULL
              AND subcategory != ''
              AND CONCAT(main_category, ' > ', subcategory) NOT IN (
                  SELECT full_category_path FROM bigbasket_dbmapping WHERE category_level = 2 AND full_category_path IS NOT NULL
              )
            ORDER BY subcategory ASC
        """), {'category': category}).fetchall()
        data = [{'subcategory_name': r[0]} for r in rows]
        return jsonify({'status': 'success', 'category': category, 'data': data, 'total': len(data)}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@bigbasket_api_bp.route('/scrape_bigbasket/mapping', methods=['GET'])
def get_bigbasket_dbmapping():
    """Return existing BigBasket DB mappings."""
    try:
        from sqlalchemy import text
        rows = db.session.execute(text("""
            SELECT category_id, category_name, parent_id, category_level, full_category_path
            FROM bigbasket_dbmapping
            ORDER BY category_level ASC, category_name ASC, full_category_path ASC
        """)).fetchall()
        data = [
            {
                'category_id': r[0],
                'category_name': r[1],
                'parent_id': r[2],
                'category_level': r[3],
                'full_category_path': r[4],
            }
            for r in rows
        ]
        return jsonify({'status': 'success', 'data': data, 'total': len(data)}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@bigbasket_api_bp.route('/scrape_bigbasket/mapping', methods=['POST'])
def add_bigbasket_mapping():
    """Insert a new mapping row into bigbasket_dbmapping."""
    try:
        data = request.get_json() or {}
        category_name = (data.get('category_name') or '').strip()
        subcategory_name = (data.get('subcategory_name') or '').strip()
        full_category_path = (data.get('full_category_path') or '').strip()

        if not category_name:
            return jsonify({'status': 'error', 'message': 'category_name is required'}), 400

        if not full_category_path:
            full_category_path = category_name if not subcategory_name else f"{category_name} > {subcategory_name}"

        from sqlalchemy import text
        existing = db.session.execute(text("SELECT category_id FROM bigbasket_dbmapping WHERE LOWER(full_category_path) = LOWER(:path)"), {'path': full_category_path}).fetchone()
        if existing:
            return jsonify({'status': 'error', 'message': 'Mapping already exists for this category path'}), 409

        if subcategory_name:
            parent = db.session.execute(text("SELECT category_id FROM bigbasket_dbmapping WHERE category_level = 1 AND LOWER(category_name) = LOWER(:category_name)"), {'category_name': category_name}).fetchone()
            if not parent:
                return jsonify({'status': 'error', 'message': 'Parent main category must exist before adding a subcategory mapping.'}), 400
            parent_id = parent[0]
            category_level = 2
        else:
            parent_id = 0
            category_level = 1

        max_id = db.session.execute(text("SELECT COALESCE(MAX(category_id), 0) FROM bigbasket_dbmapping")).scalar() or 0
        new_id = max_id + 1

        insert_stmt = text("""
            INSERT INTO bigbasket_dbmapping (category_id, category_name, parent_id, category_level, full_category_path)
            VALUES (:category_id, :category_name, :parent_id, :category_level, :full_category_path)
        """)
        db.session.execute(insert_stmt, {
            'category_id': new_id,
            'category_name': subcategory_name if category_level == 2 else category_name,
            'parent_id': parent_id,
            'category_level': category_level,
            'full_category_path': full_category_path,
        })
        db.session.commit()

        return jsonify({'status': 'success', 'category_id': new_id, 'category_name': category_name, 'subcategory_name': subcategory_name, 'full_category_path': full_category_path}), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500


@bigbasket_api_bp.route('/scrape_bigbasket/tasks', methods=['GET'])
def get_bigbasket_tasks():
    """Return the history of all BigBasket scraping tasks."""
    try:
        tasks = (
            ScraperTask.query
            .filter_by(platform='BigBasket')
            .order_by(ScraperTask.id.desc())
            .limit(50)
            .all()
        )
        return jsonify([
            {
                'id': t.id,
                'platform': t.platform,
                'query': t.search_query,
                'status': t.status,
                'progress': t.progress,
                'total_found': t.total_found,
                'error_message': t.error_message,
                'created_at': t.created_at.isoformat() if t.created_at else None,
                'download_url': f'/api/scrape_bigbasket/csv/{t.id}',
                'preview_url': f'/api/scrape_bigbasket/preview/{t.id}',
                'merge_url': f'/api/scrape_bigbasket/merge/{t.id}',
            }
            for t in tasks
        ])
    except Exception as e:
        return jsonify({'error': str(e)}), 500
