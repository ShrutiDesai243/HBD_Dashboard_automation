"""
Master Category Routes
======================
CRUD API for the master_categories tree.
All endpoints are under /api/master-categories.

Endpoints:
  GET    /                      List all (flat or tree)
  GET    /tree                  Full hierarchical tree
  GET    /search?q=…            Search by name
  POST   /                      Add a new category
  PUT    /<id>                   Update name or parent
  PUT    /<id>/deactivate        Soft-delete
  PUT    /<id>/reactivate        Restore
"""

from flask import Blueprint, request, jsonify
import traceback

from model.master_category import MasterCategory
from services.category_sync_service import (
    add_master_category,
    update_master_category,
    deactivate_master_category,
)
from extensions import db

master_category_bp = Blueprint('master_category_bp', __name__)


# ─── LIST (FLAT) ─────────────────────────────────────────────────────
@master_category_bp.route('/', methods=['GET'], strict_slashes=False)
def list_master_categories():
    """
    List master categories.
    Query params:
      - level (int): filter by hierarchy level
      - active_only (bool, default true): exclude deactivated
      - parent_id (int): filter by parent
      - page / limit: pagination
    """
    try:
        level = request.args.get('level', type=int)
        parent_id = request.args.get('parent_id', type=int)
        active_only = request.args.get('active_only', 'true').lower() != 'false'
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 100, type=int)
        limit = max(1, min(limit, 500))

        query = MasterCategory.query
        if active_only:
            query = query.filter_by(is_active=True)
        if level is not None:
            query = query.filter_by(level=level)
        if parent_id is not None:
            query = query.filter_by(parent_id=parent_id)

        query = query.order_by(MasterCategory.path.asc())
        pagination = query.paginate(page=page, per_page=limit, error_out=False)

        return jsonify({
            'status': 'success',
            'data': [c.to_dict() for c in pagination.items],
            'total_count': pagination.total,
            'total_pages': pagination.pages,
            'current_page': page,
        }), 200

    except Exception as e:
        print(f'[master_categories] list error: {traceback.format_exc()}')
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ─── TREE VIEW ───────────────────────────────────────────────────────
@master_category_bp.route('/tree', methods=['GET'])
def get_category_tree():
    """Return the full category hierarchy as a nested JSON tree."""
    try:
        active_only = request.args.get('active_only', 'true').lower() != 'false'

        # Fetch all categories in a single query to prevent N+1 query performance bottleneck
        query = MasterCategory.query
        if active_only:
            query = query.filter_by(is_active=True)

        categories = query.all()

        # Build tree in-memory: map each ID to its dictionary representation
        cat_dicts = {}
        for c in categories:
            cat_dicts[c.id] = {
                'id': c.id,
                'name': c.name,
                'parent_id': c.parent_id,
                'level': c.level,
                'path': c.path,
                'is_active': c.is_active,
                'created_at': c.created_at.isoformat() if c.created_at else None,
                'updated_at': c.updated_at.isoformat() if c.updated_at else None,
                'children': []
            }

        # Link children to their parent, and track root nodes
        roots = []
        for c in categories:
            c_dict = cat_dicts[c.id]
            if c.parent_id is None:
                roots.append(c_dict)
            else:
                parent_dict = cat_dicts.get(c.parent_id)
                if parent_dict is not None:
                    parent_dict['children'].append(c_dict)
                else:
                    # Parent not found in set (e.g. parent is inactive, child active), treat as root
                    roots.append(c_dict)

        # Recursively sort children alphabetically
        def sort_children(node):
            if node['children']:
                node['children'].sort(key=lambda x: x['name'].lower())
                for child in node['children']:
                    sort_children(child)

        roots.sort(key=lambda x: x['name'].lower())
        for root in roots:
            sort_children(root)

        return jsonify({'status': 'success', 'data': roots}), 200

    except Exception as e:
        print(f'[master_categories] tree error: {traceback.format_exc()}')
        return jsonify({'status': 'error', 'message': str(e)}), 500



# ─── SEARCH ──────────────────────────────────────────────────────────
@master_category_bp.route('/search', methods=['GET'])
def search_master_categories():
    """Search categories by name substring."""
    try:
        q = request.args.get('q', '').strip()
        if not q:
            return jsonify({'status': 'success', 'data': []}), 200

        results = MasterCategory.query.filter(
            MasterCategory.is_active == True,
            MasterCategory.name.ilike(f'%{q}%'),
        ).order_by(MasterCategory.path.asc()).limit(50).all()

        return jsonify({
            'status': 'success',
            'data': [c.to_dict() for c in results],
        }), 200

    except Exception as e:
        print(f'[master_categories] search error: {traceback.format_exc()}')
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ─── CREATE ──────────────────────────────────────────────────────────
@master_category_bp.route('/', methods=['POST'], strict_slashes=False)
def create_master_category():
    """
    Add a new master category.
    Body JSON: { "name": "Dairy & Bakery", "parent_id": 5 }
    parent_id is optional (null = root-level category).
    """
    try:
        data = request.get_json(force=True)
        name = data.get('name', '').strip()
        parent_id = data.get('parent_id')

        if not name:
            return jsonify({'status': 'error', 'message': 'name is required'}), 400

        cat, error = add_master_category(
            name=name,
            parent_id=parent_id,
            changed_by=data.get('changed_by', 'admin'),
        )
        if error:
            return jsonify({'status': 'error', 'message': error}), 400

        return jsonify({'status': 'success', 'data': cat.to_dict()}), 201

    except Exception as e:
        print(f'[master_categories] create error: {traceback.format_exc()}')
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ─── UPDATE ──────────────────────────────────────────────────────────
@master_category_bp.route('/<int:category_id>', methods=['PUT'])
def update_category(category_id):
    """
    Update a master category's name and/or parent.
    Body JSON: { "name": "New Name", "parent_id": 10 }
    Omit parent_id to leave it unchanged.
    """
    try:
        data = request.get_json(force=True)
        new_name = data.get('name')
        new_parent_id = data.get('parent_id', '__UNCHANGED__')

        cat, error = update_master_category(
            category_id=category_id,
            new_name=new_name,
            new_parent_id=new_parent_id,
            changed_by=data.get('changed_by', 'admin'),
        )
        if error:
            return jsonify({'status': 'error', 'message': error}), 400

        return jsonify({'status': 'success', 'data': cat.to_dict()}), 200

    except Exception as e:
        print(f'[master_categories] update error: {traceback.format_exc()}')
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ─── DEACTIVATE (SOFT-DELETE) ────────────────────────────────────────
@master_category_bp.route('/<int:category_id>/deactivate', methods=['PUT'])
def deactivate_category(category_id):
    """Soft-delete: set is_active = False."""
    try:
        data = request.get_json(silent=True) or {}
        cat, error = deactivate_master_category(
            category_id=category_id,
            changed_by=data.get('changed_by', 'admin'),
        )
        if error:
            return jsonify({'status': 'error', 'message': error}), 400

        return jsonify({'status': 'success', 'data': cat.to_dict()}), 200

    except Exception as e:
        print(f'[master_categories] deactivate error: {traceback.format_exc()}')
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ─── REACTIVATE ──────────────────────────────────────────────────────
@master_category_bp.route('/<int:category_id>/reactivate', methods=['PUT'])
def reactivate_category(category_id):
    """Restore a soft-deleted category."""
    try:
        from model.category_mapping_history import CategoryMappingHistory
        from datetime import datetime

        cat = MasterCategory.query.get(category_id)
        if not cat:
            return jsonify({'status': 'error', 'message': 'Category not found'}), 404

        cat.is_active = True
        cat.updated_at = datetime.utcnow()

        history = CategoryMappingHistory(
            master_category_id=cat.id,
            action='REACTIVATED',
            old_value='is_active=False',
            new_value='is_active=True',
            changed_by=(request.get_json(silent=True) or {}).get('changed_by', 'admin'),
            notes='Category reactivated',
        )
        db.session.add(history)
        db.session.commit()

        return jsonify({'status': 'success', 'data': cat.to_dict()}), 200

    except Exception as e:
        db.session.rollback()
        print(f'[master_categories] reactivate error: {traceback.format_exc()}')
        return jsonify({'status': 'error', 'message': str(e)}), 500
