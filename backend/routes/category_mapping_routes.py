"""
Category Mapping Routes
=======================
API for managing platform-to-master category mappings.
All endpoints are under /api/category-mapping.

Endpoints:
  GET    /                      List all mappings (with filters)
  GET    /pending               List PENDING / UNMAPPED entries
  GET    /stats                 Per-platform mapping statistics
  POST   /sync                  Trigger full sync for all platforms
  POST   /sync/<platform>       Trigger sync for one platform
  PUT    /<id>/map              Manually map to a master category
  PUT    /<id>/approve          Approve an auto-mapped entry
  PUT    /<id>/unmap            Mark as UNMAPPED (no match available)
  GET    /history               View audit trail
"""

from flask import Blueprint, request, jsonify
import traceback
from datetime import datetime

from model.platform_category_mapping import PlatformCategoryMapping
from model.category_mapping_history import CategoryMappingHistory
from model.category_mapping_platforms import CategoryMappingPlatform
from model.category_mapping_synonyms import CategoryMappingSynonym
from services.category_sync_service import (
    sync_platform_categories,
    sync_all_platforms,
    auto_map_pending,
    update_mapping,
    get_mapping_stats,
)
from extensions import db

category_mapping_bp = Blueprint('category_mapping_bp', __name__)


# ─── LIST ALL MAPPINGS ───────────────────────────────────────────────
@category_mapping_bp.route('/', methods=['GET'], strict_slashes=False)
def list_mappings():
    """
    List platform category mappings with optional filters.
    Query params:
      - platform (str): filter by platform name
      - status (str): PENDING | AUTO_MAPPED | MANUALLY_MAPPED | UNMAPPED
      - search (str): search in raw category name
      - active_only (bool, default true)
      - page / limit: pagination
    """
    try:
        platform = request.args.get('platform', '').strip()
        status = request.args.get('status', '').strip()
        search = request.args.get('search', '').strip()
        active_only = request.args.get('active_only', 'true').lower() != 'false'
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 50, type=int)
        limit = max(1, min(limit, 200))

        query = PlatformCategoryMapping.query
        if active_only:
            query = query.filter_by(is_active=True)
        if platform and platform.lower() != 'all':
            query = query.filter(
                PlatformCategoryMapping.platform_name.ilike(platform)
            )
        if status:
            query = query.filter_by(mapping_status=status.upper())
        if search:
            query = query.filter(
                PlatformCategoryMapping.platform_category_raw.ilike(f'%{search}%')
            )

        query = query.order_by(
            PlatformCategoryMapping.platform_name.asc(),
            PlatformCategoryMapping.platform_category_raw.asc(),
        )
        pagination = query.paginate(page=page, per_page=limit, error_out=False)

        return jsonify({
            'status': 'success',
            'data': [m.to_dict() for m in pagination.items],
            'total_count': pagination.total,
            'total_pages': pagination.pages,
            'current_page': page,
        }), 200

    except Exception as e:
        print(f'[category_mapping] list error: {traceback.format_exc()}')
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ─── LIST PENDING ────────────────────────────────────────────────────
@category_mapping_bp.route('/pending', methods=['GET'])
def list_pending():
    """List all PENDING and UNMAPPED entries for review."""
    try:
        platform = request.args.get('platform', '').strip()
        search = request.args.get('search', '').strip()
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 50, type=int)

        query = PlatformCategoryMapping.query.filter(
            PlatformCategoryMapping.is_active == True,
            PlatformCategoryMapping.mapping_status.in_(['PENDING', 'UNMAPPED']),
        )
        if platform and platform.lower() != 'all':
            query = query.filter(
                PlatformCategoryMapping.platform_name.ilike(platform)
            )
        if search:
            query = query.filter(
                PlatformCategoryMapping.platform_category_raw.ilike(f'%{search}%')
            )

        query = query.order_by(
            PlatformCategoryMapping.platform_name.asc(),
            PlatformCategoryMapping.platform_category_raw.asc(),
        )
        pagination = query.paginate(page=page, per_page=limit, error_out=False)

        return jsonify({
            'status': 'success',
            'data': [m.to_dict() for m in pagination.items],
            'total_count': pagination.total,
            'total_pages': pagination.pages,
            'current_page': page,
        }), 200

    except Exception as e:
        print(f'[category_mapping] pending error: {traceback.format_exc()}')
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ─── STATS ───────────────────────────────────────────────────────────
@category_mapping_bp.route('/stats', methods=['GET'])
def mapping_stats():
    """Return per-platform mapping statistics."""
    try:
        stats = get_mapping_stats()
        return jsonify({'status': 'success', 'data': stats}), 200
    except Exception as e:
        print(f'[category_mapping] stats error: {traceback.format_exc()}')
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ─── SYNC ALL PLATFORMS ──────────────────────────────────────────────
@category_mapping_bp.route('/sync', methods=['POST'])
def trigger_sync_all():
    """
    Trigger full sync:
      1. Discover new categories from ALL platform product tables
      2. Run predefined auto-mapping on pending entries
    """
    try:
        results = sync_all_platforms()
        return jsonify({'status': 'success', 'data': results}), 200
    except Exception as e:
        print(f'[category_mapping] sync-all error: {traceback.format_exc()}')
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ─── SYNC SINGLE PLATFORM ───────────────────────────────────────────
@category_mapping_bp.route('/sync/<string:platform>', methods=['POST'])
def trigger_sync_platform(platform):
    """Sync categories from a single platform, then auto-map."""
    try:
        discovery = sync_platform_categories(platform)
        mapping = auto_map_pending()
        return jsonify({
            'status': 'success',
            'data': {
                'discovery': discovery,
                'auto_mapping': mapping,
            }
        }), 200
    except Exception as e:
        print(f'[category_mapping] sync/{platform} error: {traceback.format_exc()}')
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ─── MANUAL MAP ──────────────────────────────────────────────────────
@category_mapping_bp.route('/<int:mapping_id>/map', methods=['PUT'])
def manual_map(mapping_id):
    """
    Manually map a platform category to a master category.
    Body JSON: { "master_category_id": 42 }
    """
    try:
        data = request.get_json(force=True)
        master_category_id = data.get('master_category_id')
        if not master_category_id:
            return jsonify({
                'status': 'error',
                'message': 'master_category_id is required',
            }), 400

        mapping, error = update_mapping(
            mapping_id=mapping_id,
            master_category_id=master_category_id,
            changed_by=data.get('changed_by', 'admin'),
        )
        if error:
            return jsonify({'status': 'error', 'message': error}), 400

        return jsonify({'status': 'success', 'data': mapping.to_dict()}), 200

    except Exception as e:
        print(f'[category_mapping] map error: {traceback.format_exc()}')
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ─── APPROVE AUTO-MAP ────────────────────────────────────────────────
@category_mapping_bp.route('/<int:mapping_id>/approve', methods=['PUT'])
def approve_mapping(mapping_id):
    """Approve an AUTO_MAPPED entry → promotes it to MANUALLY_MAPPED."""
    try:
        mapping = PlatformCategoryMapping.query.get(mapping_id)
        if not mapping:
            return jsonify({'status': 'error', 'message': 'Mapping not found'}), 404

        old_status = mapping.mapping_status
        mapping.mapping_status = 'MANUALLY_MAPPED'
        mapping.confidence_score = 1.0
        mapping.updated_at = datetime.utcnow()

        data = request.get_json(silent=True) or {}
        history = CategoryMappingHistory(
            mapping_id=mapping.id,
            master_category_id=mapping.master_category_id,
            action='APPROVED',
            old_value=old_status,
            new_value='MANUALLY_MAPPED',
            changed_by=data.get('changed_by', 'admin'),
            notes='Admin approved auto-mapping',
        )
        db.session.add(history)
        db.session.commit()

        return jsonify({'status': 'success', 'data': mapping.to_dict()}), 200

    except Exception as e:
        db.session.rollback()
        print(f'[category_mapping] approve error: {traceback.format_exc()}')
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ─── APPROVE ALL AUTO-MAPPINGS ───────────────────────────────────────
@category_mapping_bp.route('/approve-all', methods=['POST'])
def approve_all_mappings():
    """Approve all AUTO_MAPPED entries for a platform or all platforms using bulk updates."""
    try:
        data = request.get_json(silent=True) or {}
        platform = data.get('platform', '').strip()
        changed_by = data.get('changed_by', 'admin')
        
        # 1. Fetch matching entries to build history (id, master_category_id)
        query = PlatformCategoryMapping.query.filter_by(
            mapping_status='AUTO_MAPPED',
            is_active=True
        )
        if platform and platform.lower() != 'all':
            query = query.filter(PlatformCategoryMapping.platform_name.ilike(platform))
            
        auto_mapped_entries = query.all()
        count = len(auto_mapped_entries)
        
        if count == 0:
            return jsonify({
                'status': 'success',
                'message': 'No auto-mapped categories found to approve.',
                'approved_count': 0
            }), 200
            
        # 2. Run bulk update on PlatformCategoryMapping
        update_query = PlatformCategoryMapping.query.filter_by(
            mapping_status='AUTO_MAPPED',
            is_active=True
        )
        if platform and platform.lower() != 'all':
            update_query = update_query.filter(PlatformCategoryMapping.platform_name.ilike(platform))
            
        update_query.update({
            PlatformCategoryMapping.mapping_status: 'MANUALLY_MAPPED',
            PlatformCategoryMapping.confidence_score: 1.0,
            PlatformCategoryMapping.updated_at: datetime.utcnow()
        }, synchronize_session=False)
        
        # 3. Perform bulk insert for CategoryMappingHistory
        history_mappings = [
            {
                'mapping_id': m.id,
                'master_category_id': m.master_category_id,
                'action': 'APPROVED',
                'old_value': 'AUTO_MAPPED',
                'new_value': 'MANUALLY_MAPPED',
                'changed_by': changed_by,
                'notes': 'Bulk approved all auto-mappings',
                'created_at': datetime.utcnow()
            }
            for m in auto_mapped_entries
        ]
        db.session.bulk_insert_mappings(CategoryMappingHistory, history_mappings)
        
        db.session.commit()
        return jsonify({
            'status': 'success',
            'message': f'Successfully approved {count} auto-mapped categories.',
            'approved_count': count
        }), 200
    except Exception as e:
        db.session.rollback()
        print(f'[category_mapping] approve-all error: {traceback.format_exc()}')
        return jsonify({'status': 'error', 'message': str(e)}), 500




# ─── MARK AS UNMAPPED ────────────────────────────────────────────────
@category_mapping_bp.route('/<int:mapping_id>/unmap', methods=['PUT'])
def unmap_entry(mapping_id):
    """Mark a mapping as UNMAPPED (explicitly no match available)."""
    try:
        mapping = PlatformCategoryMapping.query.get(mapping_id)
        if not mapping:
            return jsonify({'status': 'error', 'message': 'Mapping not found'}), 404

        old_status = mapping.mapping_status
        mapping.mapping_status = 'UNMAPPED'
        mapping.master_category_id = None
        mapping.confidence_score = 0.0
        mapping.updated_at = datetime.utcnow()

        data = request.get_json(silent=True) or {}
        history = CategoryMappingHistory(
            mapping_id=mapping.id,
            action='UNMAPPED',
            old_value=old_status,
            new_value='UNMAPPED',
            changed_by=data.get('changed_by', 'admin'),
            notes='Admin marked as unmapped',
        )
        db.session.add(history)
        db.session.commit()

        return jsonify({'status': 'success', 'data': mapping.to_dict()}), 200

    except Exception as e:
        db.session.rollback()
        print(f'[category_mapping] unmap error: {traceback.format_exc()}')
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ─── AUDIT HISTORY ───────────────────────────────────────────────────
@category_mapping_bp.route('/history', methods=['GET'])
def get_history():
    """View audit trail with optional filters."""
    try:
        mapping_id = request.args.get('mapping_id', type=int)
        master_category_id = request.args.get('master_category_id', type=int)
        action = request.args.get('action', '').strip()
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 50, type=int)

        query = CategoryMappingHistory.query
        if mapping_id:
            query = query.filter_by(mapping_id=mapping_id)
        if master_category_id:
            query = query.filter_by(master_category_id=master_category_id)
        if action:
            query = query.filter_by(action=action.upper())

        query = query.order_by(CategoryMappingHistory.created_at.desc())
        pagination = query.paginate(page=page, per_page=limit, error_out=False)

        return jsonify({
            'status': 'success',
            'data': [h.to_dict() for h in pagination.items],
            'total_count': pagination.total,
            'total_pages': pagination.pages,
            'current_page': page,
        }), 200

    except Exception as e:
        print(f'[category_mapping] history error: {traceback.format_exc()}')
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ─── SETTINGS: GET PLATFORMS ─────────────────────────────────────────
@category_mapping_bp.route('/settings/platforms', methods=['GET'])
def get_platforms_setting():
    try:
        platforms = CategoryMappingPlatform.query.order_by(CategoryMappingPlatform.platform_name.asc()).all()
        return jsonify({'status': 'success', 'data': [p.to_dict() for p in platforms]}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ─── SETTINGS: ADD PLATFORM ──────────────────────────────────────────
@category_mapping_bp.route('/settings/platforms', methods=['POST'])
def add_platform_setting():
    try:
        data = request.get_json(force=True)
        name = data.get('platform_name', '').strip()
        query_sql = data.get('query_sql', '').strip()
        if not name or not query_sql:
            return jsonify({'status': 'error', 'message': 'platform_name and query_sql are required'}), 400
        
        # Check duplicate
        existing = CategoryMappingPlatform.query.filter_by(platform_name=name).first()
        if existing:
            return jsonify({'status': 'error', 'message': f"Platform '{name}' is already configured"}), 400
            
        p_cfg = CategoryMappingPlatform(
            platform_name=name,
            query_sql=query_sql,
            is_active=True
        )
        db.session.add(p_cfg)
        db.session.commit()
        return jsonify({'status': 'success', 'data': p_cfg.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ─── SETTINGS: UPDATE PLATFORM ───────────────────────────────────────
@category_mapping_bp.route('/settings/platforms/<int:platform_id>', methods=['PUT'])
def update_platform_setting(platform_id):
    try:
        p_cfg = CategoryMappingPlatform.query.get(platform_id)
        if not p_cfg:
            return jsonify({'status': 'error', 'message': 'Platform configuration not found'}), 404
        
        data = request.get_json(force=True)
        name = data.get('platform_name')
        query_sql = data.get('query_sql')
        is_active = data.get('is_active')
        
        if name and name.strip():
            p_cfg.platform_name = name.strip()
        if query_sql and query_sql.strip():
            p_cfg.query_sql = query_sql.strip()
        if is_active is not None:
            p_cfg.is_active = bool(is_active)
            
        db.session.commit()
        return jsonify({'status': 'success', 'data': p_cfg.to_dict()}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ─── SETTINGS: DEACTIVATE PLATFORM ───────────────────────────────────
@category_mapping_bp.route('/settings/platforms/<int:platform_id>/deactivate', methods=['PUT'])
def deactivate_platform_setting(platform_id):
    try:
        p_cfg = CategoryMappingPlatform.query.get(platform_id)
        if not p_cfg:
            return jsonify({'status': 'error', 'message': 'Platform configuration not found'}), 404
        p_cfg.is_active = False
        db.session.commit()
        return jsonify({'status': 'success', 'data': p_cfg.to_dict()}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ─── SETTINGS: GET SYNONYMS ──────────────────────────────────────────
@category_mapping_bp.route('/settings/synonyms', methods=['GET'])
def get_synonyms_setting():
    try:
        search = request.args.get('search', '').strip()
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 50, type=int)
        
        query = CategoryMappingSynonym.query
        if search:
            query = query.filter(
                (CategoryMappingSynonym.raw_value.ilike(f'%{search}%')) |
                (CategoryMappingSynonym.canonical_value.ilike(f'%{search}%'))
            )
        query = query.order_by(CategoryMappingSynonym.raw_value.asc())
        pagination = query.paginate(page=page, per_page=limit, error_out=False)
        
        return jsonify({
            'status': 'success',
            'data': [s.to_dict() for s in pagination.items],
            'total_count': pagination.total,
            'total_pages': pagination.pages,
            'current_page': page
        }), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ─── SETTINGS: ADD SYNONYM ───────────────────────────────────────────
@category_mapping_bp.route('/settings/synonyms', methods=['POST'])
def add_synonym_setting():
    try:
        from services.category_sync_service import normalize_category_name
        data = request.get_json(force=True)
        raw = data.get('raw_value', '').strip()
        canonical = data.get('canonical_value', '').strip()
        if not raw or not canonical:
            return jsonify({'status': 'error', 'message': 'raw_value and canonical_value are required'}), 400
            
        norm_raw = normalize_category_name(raw)
        # Check duplicate
        existing = CategoryMappingSynonym.query.filter_by(raw_value=norm_raw).first()
        if existing:
            return jsonify({'status': 'error', 'message': f"Synonym rule for '{norm_raw}' already exists"}), 400
            
        syn = CategoryMappingSynonym(
            raw_value=norm_raw,
            canonical_value=canonical
        )
        db.session.add(syn)
        db.session.commit()
        return jsonify({'status': 'success', 'data': syn.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ─── SETTINGS: DELETE SYNONYM ────────────────────────────────────────
@category_mapping_bp.route('/settings/synonyms/<int:synonym_id>', methods=['DELETE'])
def delete_synonym_setting(synonym_id):
    try:
        syn = CategoryMappingSynonym.query.get(synonym_id)
        if not syn:
            return jsonify({'status': 'error', 'message': 'Synonym rule not found'}), 404
        db.session.delete(syn)
        db.session.commit()
        return jsonify({'status': 'success', 'message': 'Synonym rule deleted'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500
