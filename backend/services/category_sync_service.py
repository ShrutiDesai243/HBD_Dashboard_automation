"""
Category Sync Service
=====================
Core business logic for the Dynamic Categories Mapping Master.

Responsibilities:
  1. Scan each platform's product table, extract distinct categories,
     and auto-register new ones in platform_category_mapping as PENDING.
  2. Run predefined (non-AI) matching logic to auto-map pending entries
     to existing master_categories.
  3. Provide helpers for adding / updating master categories with full
     duplicate checking, path recomputation, and audit-trail recording.

No AI is used — matching relies on:
  • Exact normalized match (lowercase + strip + collapse whitespace)
  • Predefined synonym dictionary
  • Substring containment heuristics
"""

import re
import traceback
from datetime import datetime
from sqlalchemy import text, func
from extensions import db
from model.master_category import MasterCategory
from model.platform_category_mapping import PlatformCategoryMapping
from model.category_mapping_history import CategoryMappingHistory
from model.category_mapping_platforms import CategoryMappingPlatform
from model.category_mapping_synonyms import CategoryMappingSynonym


# ═══════════════════════════════════════════════════════════════════════
#  PLATFORM CONFIGURATION
#  Each entry tells the sync service which SQL to run to extract
#  distinct (category, subcategory) pairs from a platform's product table.
# ═══════════════════════════════════════════════════════════════════════

PLATFORM_CATEGORY_QUERIES = {
    'BigBasket': {
        'query': """
            SELECT DISTINCT category_path AS category, NULL AS subcategory
            FROM product_category_master
            WHERE marketplace_name = 'BigBasket' AND category_path IS NOT NULL AND category_path != ''
        """,
    },
    'Blinkit': {
        'query': """
            SELECT DISTINCT category_path AS category, NULL AS subcategory
            FROM product_category_master
            WHERE marketplace_name = 'Blinkit' AND category_path IS NOT NULL AND category_path != ''
        """,
    },
    'Zepto': {
        'query': """
            SELECT DISTINCT main_category AS category, subcategory AS subcategory
            FROM zepto
            WHERE main_category IS NOT NULL AND main_category != ''
        """,
    },
    'DMart': {
        'query': """
            SELECT DISTINCT category_path AS category, NULL AS subcategory
            FROM dmart_categories
            WHERE category_path IS NOT NULL AND category_path != ''
        """,
    },
    'IndiaMart': {
        'query': """
            SELECT DISTINCT category_path AS category, NULL AS subcategory
            FROM product_category_master
            WHERE marketplace_name = 'IndiaMART' AND category_path IS NOT NULL AND category_path != ''
        """,
    },
    'Amazon': {
        'query': """
            SELECT DISTINCT category_path AS category, NULL AS subcategory
            FROM product_category_master
            WHERE marketplace_name = 'Amazon' AND category_path IS NOT NULL AND category_path != ''
        """,
    },
    'Flipkart': {
        'query': """
            SELECT DISTINCT 
                category AS category, 
                CONCAT_WS(' > ', 
                    NULLIF(TRIM(subcategory), ''), 
                    NULLIF(TRIM(sub_sub_category), ''), 
                    NULLIF(TRIM(category_sub_sub_sub), '')
                ) AS subcategory
            FROM flipkart_products
            WHERE category IS NOT NULL AND category != ''
        """,
    },
    'JioMart': {
        'query': """
            SELECT DISTINCT 
                category AS category, 
                CONCAT_WS(' > ', 
                    NULLIF(TRIM(subcategory), ''), 
                    NULLIF(TRIM(sub_sub_category), ''), 
                    NULLIF(TRIM(category_sub_sub_sub), '')
                ) AS subcategory
            FROM jio_mart_products
            WHERE category IS NOT NULL AND category != ''
        """,
    },
}


# ═══════════════════════════════════════════════════════════════════════
#  PREDEFINED SYNONYM DICTIONARY
#  Maps commonly seen raw category strings to a canonical form.
#  Extend this dictionary as your team discovers new patterns.
# ═══════════════════════════════════════════════════════════════════════

CATEGORY_SYNONYMS = {
    # Grocery & Food
    'fruits & vegetables': 'Fruits & Vegetables',
    'fruits and vegetables': 'Fruits & Vegetables',
    'fresh fruits': 'Fruits & Vegetables',
    'fresh vegetables': 'Fruits & Vegetables',
    'dairy': 'Dairy & Bakery',
    'dairy & bakery': 'Dairy & Bakery',
    'dairy and bakery': 'Dairy & Bakery',
    'bakery': 'Dairy & Bakery',
    'milk & dairy': 'Dairy & Bakery',
    'beverages': 'Dairy & Beverages > Beverages',
    'drinks': 'Dairy & Beverages > Beverages',
    'cold drinks': 'Dairy & Beverages > Beverages',
    'soft drinks': 'Dairy & Beverages > Beverages',
    'snacks': 'Snacks & Branded Foods',
    'snacks & branded food': 'Snacks & Branded Foods',
    'snacks & branded foods': 'Snacks & Branded Foods',
    'snacks and branded food': 'Snacks & Branded Foods',
    'chips & snacks': 'Snacks & Branded Foods',
    'staples': 'Staples',
    'foodgrains': 'Staples',
    'foodgrains, oil & masala': 'Staples',
    'grocery & staples': 'Staples',
    'cleaning & household': 'Cleaning & Household',
    'cleaning': 'Cleaning & Household',
    'household': 'Cleaning & Household',
    'home & kitchen': 'Home & Kitchen',
    'home and kitchen': 'Home & Kitchen',
    'kitchen': 'Home & Kitchen',
    'personal care': 'Personal Care',
    'beauty & hygiene': 'Beauty & Hygiene',
    'beauty & personal care': 'Beauty & Hygiene',
    'beauty and hygiene': 'Beauty & Hygiene',
    'baby care': 'Baby & Kids > Baby Care',
    'baby products': 'Baby & Kids > Baby Care',
    'pet care': 'Pet Care',
    'pet supplies': 'Pet Care',
    'meat & seafood': 'Meat & Seafood',
    'meat, fish & eggs': 'Meat & Seafood',
    'non-veg': 'Meat & Seafood',
    'frozen food': 'Frozen Foods',
    'frozen foods': 'Frozen Foods',
    'frozen': 'Frozen Foods',
    'ice cream': 'Ice Cream & Desserts',
    'ice creams': 'Ice Cream & Desserts',
    'ice cream & desserts': 'Ice Cream & Desserts',
    'ready to eat': 'Ready to Eat & Cook',
    'ready to cook': 'Ready to Eat & Cook',
    'instant food': 'Ready to Eat & Cook',
    'breakfast': 'Breakfast & Cereals',
    'breakfast cereals': 'Breakfast & Cereals',
    'cereals': 'Breakfast & Cereals',
    'tea & coffee': 'Tea, Coffee & Health Drinks',
    'tea, coffee & health drinks': 'Tea, Coffee & Health Drinks',
    'tea coffee health drinks': 'Tea, Coffee & Health Drinks',
    'health drinks': 'Tea, Coffee & Health Drinks',
    'dry fruits': 'Dry Fruits & Nuts',
    'dry fruits & nuts': 'Dry Fruits & Nuts',
    'nuts': 'Dry Fruits & Nuts',

    # Electronics & Tech
    'electronics': 'Electronics',
    'electronics & appliances': 'Electronics',
    'computers & accessories': 'Computers & Accessories',
    'mobile accessories': 'Mobile Accessories',

    # Fashion
    'fashion': 'Fashion',
    'clothing': 'Fashion',
    'apparel': 'Fashion',
    'men\'s fashion': 'Fashion',
    'women\'s fashion': 'Fashion',

    # Sports
    'sports': 'Sports & Fitness',
    'sports & fitness': 'Sports & Fitness',
    'sports, fitness & outdoor': 'Sports & Fitness',
    'fitness': 'Sports & Fitness',

    # Industrial
    'industrial & scientific': 'Industrial & Scientific',
    'industrial': 'Industrial & Scientific',
}


# ═══════════════════════════════════════════════════════════════════════
#  TEXT NORMALIZATION
# ═══════════════════════════════════════════════════════════════════════

def normalize_category_name(name):
    """
    Normalize a category string for comparison:
      - lowercase
      - strip leading/trailing whitespace
      - collapse multiple spaces
      - remove trailing punctuation
    """
    if not name:
        return ''
    result = str(name).strip().lower()
    result = re.sub(r'\s+', ' ', result)
    result = re.sub(r'[,;.]+$', '', result)
    return result.strip()


# ═══════════════════════════════════════════════════════════════════════
#  SYNC: DISCOVER NEW CATEGORIES FROM PLATFORM TABLES
# ═══════════════════════════════════════════════════════════════════════

def sync_platform_categories(platform_name=None):
    """
    Scan product tables for each platform, discover new category strings,
    and insert them into platform_category_mapping with status='PENDING'.
    Also deactivates obsolete mapping entries and automatically cleans up
    unused system-generated master categories.

    Args:
        platform_name: If provided, sync only that platform.
                       Otherwise sync all configured platforms.

    Returns:
        dict with per-platform counts of newly discovered, updated, and deactivated categories.
    """
    # 1. Fetch dynamic platform queries from database
    db_platforms = {}
    try:
        query = CategoryMappingPlatform.query.filter_by(is_active=True)
        if platform_name:
            query = query.filter_by(platform_name=platform_name)
        rows = query.all()
        for r in rows:
            db_platforms[r.platform_name] = {'query': r.query_sql}
    except Exception as db_err:
        print(f'[CategorySync] Error fetching platforms from DB, falling back to static config: {db_err}')

    # 2. Fallback to static config if DB returned nothing
    if not db_platforms:
        if platform_name:
            if platform_name in PLATFORM_CATEGORY_QUERIES:
                db_platforms = {platform_name: PLATFORM_CATEGORY_QUERIES[platform_name]}
        else:
            db_platforms = PLATFORM_CATEGORY_QUERIES

    results = {}

    for pname, pconfig in db_platforms.items():
        new_count = 0
        deactivated_count = 0
        updated_count = 0
        try:
            # Fetch all existing mappings in database for this platform
            db_mappings = PlatformCategoryMapping.query.filter_by(
                platform_name=pname,
                is_active=True
            ).all()
            
            # Map of (category_lower, subcategory_lower) -> PlatformCategoryMapping
            db_lookup = {}
            for m in db_mappings:
                key = (m.platform_category_raw.lower(), (m.platform_subcategory_raw or '').lower())
                db_lookup[key] = m

            # Track combinations present in the raw query
            active_raw_keys = set()
            
            rows = db.session.execute(text(pconfig['query'])).fetchall()
            for row in rows:
                raw_cat = (row[0] or '').strip()
                raw_subcat = (row[1] or '').strip() if row[1] else ''

                if not raw_cat:
                    continue

                raw_key = (raw_cat.lower(), raw_subcat.lower())
                active_raw_keys.add(raw_key)

                # Check if this combo already exists (case-insensitive check)
                existing = db_lookup.get(raw_key)

                if existing:
                    # Case 1: Mapping exists, check if casing/spelling needs updating
                    if existing.platform_category_raw != raw_cat or existing.platform_subcategory_raw != raw_subcat:
                        old_val = f"{existing.platform_category_raw} / {existing.platform_subcategory_raw}"
                        existing.platform_category_raw = raw_cat
                        existing.platform_subcategory_raw = raw_subcat
                        existing.updated_at = datetime.utcnow()
                        
                        history = CategoryMappingHistory(
                            mapping_id=existing.id,
                            action='RENAMED',
                            old_value=old_val,
                            new_value=f"{raw_cat} / {raw_subcat}",
                            changed_by='system',
                            notes='Updated raw string casing to match product table'
                        )
                        db.session.add(history)
                        updated_count += 1
                else:
                    # Case 2: New mapping record
                    mapping = PlatformCategoryMapping(
                        platform_name=pname,
                        platform_category_raw=raw_cat,
                        platform_subcategory_raw=raw_subcat,
                        mapping_status='PENDING',
                        is_active=True,
                    )
                    db.session.add(mapping)
                    db.session.flush()  # Get ID

                    # Record creation in history
                    history = CategoryMappingHistory(
                        mapping_id=mapping.id,
                        action='CREATED',
                        new_value=f'{pname}: {raw_cat} / {raw_subcat}',
                        changed_by='system',
                        notes=f'Auto-discovered from {pname} product table',
                    )
                    db.session.add(history)
                    new_count += 1
                    
                    # Update db_lookup and active_raw_keys so duplicates in the query are skipped
                    db_lookup[raw_key] = mapping

            # Case 3: Deactivate obsolete mapping records
            for m in db_mappings:
                key = (m.platform_category_raw.lower(), (m.platform_subcategory_raw or '').lower())
                if key not in active_raw_keys:
                    m.is_active = False
                    m.updated_at = datetime.utcnow()
                    
                    history = CategoryMappingHistory(
                        mapping_id=m.id,
                        action='DEACTIVATED',
                        old_value='is_active=True',
                        new_value='is_active=False',
                        changed_by='system',
                        notes='Obsolete category combo (no longer exists in product table)'
                    )
                    db.session.add(history)
                    deactivated_count += 1

            db.session.commit()

        except Exception as e:
            db.session.rollback()
            print(f'[CategorySync] Error syncing {pname}: {traceback.format_exc()}')
            results[pname] = {'error': str(e)}
            continue

        results[pname] = {
            'new_categories': new_count,
            'updated_categories': updated_count,
            'deactivated_categories': deactivated_count
        }

    # Merge duplicates and clean up system master categories once after processing all platforms
    try:
        merge_duplicate_master_categories()
        _cleanup_unused_system_master_categories()
    except Exception as cleanup_err:
        print(f'[CategorySync] Error in post-sync cleanup: {cleanup_err}')

    return results


def _cleanup_unused_system_master_categories():
    """
    Find and soft-deactivate master categories that:
      1. Are active and system-generated (created by 'system').
      2. Have no active mappings pointing to them.
      3. Have no active child categories.
    Runs recursively from leaves up to roots to clean up empty branches.
    """
    try:
        # We process from highest level (deepest leaves) down to level 1 (roots)
        # to ensure childless parents are cleaned up in a single run.
        for level in range(4, 0, -1):
            # Find all candidates using a single bulk query
            sql = """
                SELECT mc.id FROM master_categories mc
                WHERE mc.level = :level AND mc.is_active = 1
                  AND NOT EXISTS (
                      SELECT 1 FROM platform_category_mapping pcm 
                      WHERE pcm.master_category_id = mc.id AND pcm.is_active = 1
                  )
                  AND NOT EXISTS (
                      SELECT 1 FROM master_categories child 
                      WHERE child.parent_id = mc.id AND child.is_active = 1
                  )
                  AND EXISTS (
                      SELECT 1 FROM category_mapping_history cmh 
                      WHERE cmh.master_category_id = mc.id AND cmh.action = 'CREATED' AND cmh.changed_by = 'system'
                  )
            """
            candidate_rows = db.session.execute(text(sql), {"level": level}).fetchall()
            candidate_ids = [r[0] for r in candidate_rows]
            
            if not candidate_ids:
                continue
                
            print(f"[Cleanup] Deactivating {len(candidate_ids)} unused system categories at level {level}...")
            
            # Deactivate them in bulk
            db.session.execute(
                text("UPDATE master_categories SET is_active = 0, updated_at = :now WHERE id IN :ids"),
                {"now": datetime.utcnow(), "ids": tuple(candidate_ids)}
            )
            
            # Record in history
            for mc_id in candidate_ids:
                history = CategoryMappingHistory(
                    master_category_id=mc_id,
                    action='DEACTIVATED',
                    old_value='is_active=True',
                    new_value='is_active=False',
                    changed_by='system',
                    notes='Unused system-generated category (no active mappings or children)'
                )
                db.session.add(history)
                
            db.session.flush()
                
        db.session.commit()
    except Exception as cleanup_err:
        db.session.rollback()
        print(f'[CategorySync] Error in _cleanup_unused_system_master_categories: {cleanup_err}')


def merge_duplicate_master_categories():
    """
    Find and merge duplicate master categories that have the same path.
    For each duplicate group:
      1. Identify the 'keep' category (preferring manually created ones, or the one with the lowest ID).
      2. Re-map all platform_category_mapping entries pointing to the duplicates to the 'keep' category.
      3. Re-parent any child categories pointing to the duplicates to the 'keep' category.
      4. Soft-deactivate the duplicate master categories.
    """
    try:
        active_cats = MasterCategory.query.filter_by(is_active=True).all()
        
        # Group by normalized path
        path_groups = {} # normalized_path -> list of MasterCategory
        for mc in active_cats:
            if not mc.path:
                continue
            path_norm = " > ".join([normalize_category_name(p) for p in mc.path.split(' > ') if p.strip()])
            if path_norm not in path_groups:
                path_groups[path_norm] = []
            path_groups[path_norm].append(mc)
            
        # Pre-load system created IDs to avoid N+1 queries during sorting
        system_created_ids = set()
        try:
            hist_rows = db.session.execute(text(
                "SELECT DISTINCT master_category_id FROM category_mapping_history WHERE action='CREATED' AND changed_by='system'"
            )).fetchall()
            system_created_ids = {r[0] for r in hist_rows}
        except Exception as hist_err:
            print(f"[Merge] Error fetching creation history: {hist_err}")

        merged_count = 0
        for path_norm, group in path_groups.items():
            if len(group) <= 1:
                continue
                
            # Sort the group: prefer manual over system-created, then lower ID first
            def sort_key(mc):
                is_system = mc.id in system_created_ids
                return (is_system, mc.id)
                
            group.sort(key=sort_key)
            keep_mc = group[0]
            duplicate_mcs = group[1:]
            
            for dup in duplicate_mcs:
                print(f"[Merge] Merging duplicate master category ID {dup.id} ('{dup.path}') -> ID {keep_mc.id} ('{keep_mc.path}')")
                
                # 1. Update mapping records pointing to dup
                mappings = PlatformCategoryMapping.query.filter_by(master_category_id=dup.id).all()
                for m in mappings:
                    m.master_category_id = keep_mc.id
                    m.updated_at = datetime.utcnow()
                    
                    history = CategoryMappingHistory(
                        mapping_id=m.id,
                        master_category_id=keep_mc.id,
                        action='REMAPPED',
                        old_value=f'master_id={dup.id}',
                        new_value=f'master_id={keep_mc.id}',
                        changed_by='system',
                        notes=f'Auto-merged duplicate master category "{dup.path}"'
                    )
                    db.session.add(history)
                    
                # 2. Re-parent children pointing to dup
                children = MasterCategory.query.filter_by(parent_id=dup.id).all()
                for child in children:
                    child.parent_id = keep_mc.id
                    child.updated_at = datetime.utcnow()
                    child.path = child.compute_path()  # Recompute path
                    
                    history = CategoryMappingHistory(
                        master_category_id=child.id,
                        action='MOVED',
                        old_value=f'parent_id={dup.id}',
                        new_value=f'parent_id={keep_mc.id}',
                        changed_by='system',
                        notes=f'Re-parented during auto-merge of duplicate master category "{dup.path}"'
                    )
                    db.session.add(history)
                    
                # 3. Soft-deactivate dup
                dup.is_active = False
                dup.updated_at = datetime.utcnow()
                
                history = CategoryMappingHistory(
                    master_category_id=dup.id,
                    action='DEACTIVATED',
                    old_value='is_active=True',
                    new_value='is_active=False',
                    changed_by='system',
                    notes=f'Deactivated duplicate master category during merge into ID {keep_mc.id}'
                )
                db.session.add(history)
                merged_count += 1
                
        if merged_count > 0:
            db.session.commit()
            print(f"[Merge] Successfully merged {merged_count} duplicate master categories.")
            
    except Exception as merge_err:
        db.session.rollback()
        print(f"[Merge] Error merging duplicate master categories: {merge_err}")



# ═══════════════════════════════════════════════════════════════════════
#  AUTO-MAPPER: PREDEFINED LOGIC (NO AI)
# ═══════════════════════════════════════════════════════════════════════

def auto_map_pending():
    """
    Attempt to map all PENDING entries in platform_category_mapping to
    existing master_categories using predefined rules:

      1. Exact normalized match against master category full paths
      2. Synonym dictionary lookup
      3. Substring containment match on full category paths

    Returns:
        dict with counts of auto-mapped and still-pending entries.
    """
    pending = PlatformCategoryMapping.query.filter_by(
        mapping_status='PENDING',
        is_active=True,
    ).all()

    # Pre-load all active master categories for matching
    master_cats = MasterCategory.query.filter_by(is_active=True).all()
    master_lookup_norm = {}   # normalized_path → MasterCategory
    for mc in master_cats:
        if mc.path:
            path_parts = [normalize_category_name(p) for p in mc.path.split(' > ') if p.strip()]
            key = " > ".join(path_parts)
            master_lookup_norm[key] = mc
        else:
            key = normalize_category_name(mc.name)
            master_lookup_norm[key] = mc

    # Pre-load all synonyms from database
    db_synonyms = {}
    try:
        syns = CategoryMappingSynonym.query.all()
        for s in syns:
            db_synonyms[normalize_category_name(s.raw_value)] = s.canonical_value
    except Exception as db_err:
        print(f'[CategorySync] Error loading synonyms from DB: {db_err}')

    mapped_count = 0
    still_pending = 0

    for mapping in pending:
        # Construct raw mapping's full path parts by splitting both columns by ' > '
        mapping_parts = []
        if mapping.platform_category_raw:
            mapping_parts.extend([p.strip() for p in re.split(r'\s*>\s*', mapping.platform_category_raw) if p.strip()])
        if mapping.platform_subcategory_raw:
            mapping_parts.extend([p.strip() for p in re.split(r'\s*>\s*', mapping.platform_subcategory_raw) if p.strip()])

        # Apply synonym replacement element-by-element
        resolved_parts = []
        for part in mapping_parts:
            part_norm = normalize_category_name(part)
            syn = db_synonyms.get(part_norm) or CATEGORY_SYNONYMS.get(part_norm)
            if syn:
                resolved_parts.append(normalize_category_name(syn))
            else:
                resolved_parts.append(part_norm)

        mapping_norm_path = " > ".join(resolved_parts)

        matched_master = None
        confidence = 0.0

        # ── Strategy 1: Exact normalized match ──
        if mapping_norm_path in master_lookup_norm:
            matched_master = master_lookup_norm[mapping_norm_path]
            confidence = 1.0

        # ── Strategy 2: Synonym dictionary ──
        if not matched_master:
            entire_raw_norm = normalize_category_name(" > ".join(mapping_parts))
            synonym_target = db_synonyms.get(entire_raw_norm) or CATEGORY_SYNONYMS.get(entire_raw_norm)
            if synonym_target:
                canonical_parts = [normalize_category_name(p) for p in synonym_target.split(' > ') if p.strip()]
                canonical_norm_path = " > ".join(canonical_parts)
                if canonical_norm_path in master_lookup_norm:
                    matched_master = master_lookup_norm[canonical_norm_path]
                    confidence = 0.9

        # ── Strategy 3: Substring containment ──
        if not matched_master:
            best_match = None
            best_score = 0.0
            mapping_parts_count = len(mapping_norm_path.split(' > '))
            for mc_norm, mc_obj in master_lookup_norm.items():
                if not mc_norm:
                    continue
                mc_parts_count = len(mc_norm.split(' > '))
                # Check if mapping path contains master path or vice versa
                if mapping_norm_path in mc_norm or mc_norm in mapping_norm_path:
                    # Crucial Fix: If master path has fewer levels than the platform path (e.g. mc='A > B', mapping='A > B > C'),
                    # do NOT match via substring containment. We want Strategy 4 to auto-generate the deeper Level 3/4 categories!
                    if mc_norm in mapping_norm_path and mc_parts_count < mapping_parts_count:
                        continue
                        
                    # Score by how much overlap there is
                    shorter = min(len(mapping_norm_path), len(mc_norm))
                    longer = max(len(mapping_norm_path), len(mc_norm))
                    score = shorter / longer if longer > 0 else 0
                    if score > best_score and score >= 0.6:
                        best_score = score
                        best_match = mc_obj
            if best_match:
                matched_master = best_match
                confidence = round(best_score * 0.8, 2)  # Scale down

        # ── Strategy 4: Auto-generation (Fallback) ──
        mapping_notes = 'Predefined auto-mapper logic'
        if not matched_master:
            try:
                # Combine category and subcategory into a single list of parts
                raw_parts = []
                if mapping.platform_category_raw:
                    raw_parts.extend([p.strip() for p in re.split(r'\s*>\s*', mapping.platform_category_raw) if p.strip()])
                if mapping.platform_subcategory_raw:
                    raw_parts.extend([p.strip() for p in re.split(r'\s*>\s*', mapping.platform_subcategory_raw) if p.strip()])

                if not raw_parts:
                    raise ValueError("No category parts found")

                # 1. Resolve or create root category
                raw_root_name = raw_parts[0]
                root_norm = normalize_category_name(raw_root_name)
                
                # Check synonym dictionary
                synonym_target = db_synonyms.get(root_norm) or CATEGORY_SYNONYMS.get(root_norm)
                if synonym_target:
                    raw_root_name = synonym_target
                    root_norm = normalize_category_name(raw_root_name)

                root_master = master_lookup_norm.get(root_norm)
                if not root_master:
                    # Check if it exists in DB (even if inactive)
                    root_master = MasterCategory.query.filter_by(
                        parent_id=None, name=raw_root_name
                    ).first()
                    
                    if not root_master:
                        roots = MasterCategory.query.filter_by(parent_id=None).all()
                        for r in roots:
                            if normalize_category_name(r.name) == root_norm:
                                root_master = r
                                break
                                
                    if root_master:
                        if not root_master.is_active:
                            root_master.is_active = True
                            root_master.updated_at = datetime.utcnow()
                            db.session.add(root_master)
                            db.session.flush()
                            
                            root_history = CategoryMappingHistory(
                                master_category_id=root_master.id,
                                action='ACTIVATED',
                                new_value=root_master.path,
                                changed_by='system',
                                notes='Reactivated root category during sync'
                            )
                            db.session.add(root_history)
                    else:
                        display_root_name = raw_root_name.title() if raw_root_name.islower() or raw_root_name.isupper() else raw_root_name
                        root_master = MasterCategory(
                            name=display_root_name,
                            parent_id=None,
                            level=1,
                            path=display_root_name,
                            is_active=True
                        )
                        db.session.add(root_master)
                        db.session.flush()  # Get ID
                        
                        root_history = CategoryMappingHistory(
                            master_category_id=root_master.id,
                            action='CREATED',
                            new_value=root_master.path,
                            changed_by='system',
                            notes='Auto-generated root category during sync'
                        )
                        db.session.add(root_history)
                    
                    # Update master lookup norm
                    master_lookup_norm[root_norm] = root_master
                    master_cats.append(root_master)

                current_parent = root_master

                # 2. Resolve or create nested subcategory levels (L2 > L3 > L4...)
                for idx, part in enumerate(raw_parts[1:]):
                    part_level = idx + 2
                    part_norm = normalize_category_name(part)
                    
                    # Construct full path and check in-memory cache first to avoid N+1 queries
                    child_path = f"{current_parent.path} > {part}"
                    child_path_parts = [normalize_category_name(p) for p in child_path.split(' > ') if p.strip()]
                    child_key = " > ".join(child_path_parts)
                    
                    child_node = master_lookup_norm.get(child_key)
                    
                    if not child_node:
                        # Find if child exists under current_parent (regardless of active status)
                        child_node = current_parent.children.filter_by(
                            name=part
                        ).first()
                        
                        if not child_node:
                            # Search by normalized name in all children (active or inactive)
                            all_children = current_parent.children.all()
                            for child in all_children:
                                if normalize_category_name(child.name) == part_norm:
                                    child_node = child
                                    break
                                
                    if child_node:
                        if not child_node.is_active:
                            child_node.is_active = True
                            child_node.updated_at = datetime.utcnow()
                            db.session.add(child_node)
                            db.session.flush()
                            
                            part_history = CategoryMappingHistory(
                                master_category_id=child_node.id,
                                action='ACTIVATED',
                                new_value=child_node.path,
                                changed_by='system',
                                notes=f'Reactivated level {part_level} category during sync'
                            )
                            db.session.add(part_history)
                    else:
                        display_part_name = part.title() if part.islower() or part.isupper() else part
                        child_node = MasterCategory(
                            name=display_part_name,
                            parent_id=current_parent.id,
                            level=part_level,
                            path=f"{current_parent.path} > {display_part_name}",
                            is_active=True
                        )
                        db.session.add(child_node)
                        db.session.flush()  # Get ID
                        
                        part_history = CategoryMappingHistory(
                            master_category_id=child_node.id,
                            action='CREATED',
                            new_value=child_node.path,
                            changed_by='system',
                            notes=f'Auto-generated level {part_level} category during sync'
                        )
                        db.session.add(part_history)
                        
                    # Add newly resolved/created category to master_lookup_norm
                    child_path_parts = [normalize_category_name(p) for p in child_node.path.split(' > ') if p.strip()]
                    child_key = " > ".join(child_path_parts)
                    master_lookup_norm[child_key] = child_node
                    
                    current_parent = child_node

                matched_master = current_parent
                confidence = 1.0
                mapping_notes = 'Auto-generated nested master category tree and mapped'
            except Exception as gen_err:
                db.session.rollback()
                print(f"[CategorySync] Error auto-generating category for {mapping}: {gen_err}")

        # ── Apply match ──
        if matched_master:
            old_status = mapping.mapping_status
            mapping.master_category_id = matched_master.id
            mapping.mapping_status = 'AUTO_MAPPED'
            mapping.confidence_score = confidence
            mapping.updated_at = datetime.utcnow()

            history = CategoryMappingHistory(
                mapping_id=mapping.id,
                master_category_id=matched_master.id,
                action='MAPPED',
                old_value=old_status,
                new_value=f'AUTO_MAPPED -> {matched_master.name} (conf={confidence})',
                changed_by='system',
                notes=mapping_notes,
            )
            db.session.add(history)
            mapped_count += 1
        else:
            still_pending += 1

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        print(f'[CategorySync] Error in auto_map_pending: {traceback.format_exc()}')

    return {
        'auto_mapped': mapped_count,
        'still_pending': still_pending,
    }


# ═══════════════════════════════════════════════════════════════════════
#  SYNC ALL: CONVENIENCE WRAPPER
# ═══════════════════════════════════════════════════════════════════════

def sync_all_platforms():
    """
    Full sync pipeline:
      1. Discover new categories from all platform product tables
      2. Run predefined auto-mapping on pending entries

    Returns combined results.
    """
    discovery_results = sync_platform_categories()
    mapping_results = auto_map_pending()
    return {
        'discovery': discovery_results,
        'auto_mapping': mapping_results,
    }


# ═══════════════════════════════════════════════════════════════════════
#  MASTER CATEGORY CRUD HELPERS
# ═══════════════════════════════════════════════════════════════════════

def add_master_category(name, parent_id=None, changed_by='system'):
    """
    Add a new category to the master tree.
    - Computes level and materialized path automatically.
    - Rejects duplicates (same name under the same parent).

    Returns:
        (MasterCategory, None) on success
        (None, error_message) on failure
    """
    name = name.strip()
    if not name:
        return None, 'Category name cannot be empty'

    # Check for duplicate under the same parent
    existing = MasterCategory.query.filter_by(
        name=name, parent_id=parent_id, is_active=True
    ).first()
    if existing:
        return None, f'Category "{name}" already exists under this parent'

    # Determine level and parent
    level = 1
    parent = None
    if parent_id:
        parent = MasterCategory.query.get(parent_id)
        if not parent:
            return None, f'Parent category with id {parent_id} not found'
        if not parent.is_active:
            return None, f'Parent category "{parent.name}" is deactivated'
        level = parent.level + 1

    new_cat = MasterCategory(
        name=name,
        parent_id=parent_id,
        level=level,
        is_active=True,
    )
    db.session.add(new_cat)
    db.session.flush()  # Get the ID

    # Compute and set materialized path
    if parent:
        new_cat.path = f'{parent.path} > {name}'
    else:
        new_cat.path = name

    # Record in audit trail
    history = CategoryMappingHistory(
        master_category_id=new_cat.id,
        action='CREATED',
        new_value=new_cat.path,
        changed_by=changed_by,
        notes=f'Master category created at level {level}',
    )
    db.session.add(history)

    try:
        db.session.commit()
        return new_cat, None
    except Exception as e:
        db.session.rollback()
        return None, str(e)


def update_master_category(category_id, new_name=None, new_parent_id='__UNCHANGED__', changed_by='system'):
    """
    Update a master category's name and/or parent.
    Recomputes path for this category and all descendants.

    Returns:
        (MasterCategory, None) on success
        (None, error_message) on failure
    """
    cat = MasterCategory.query.get(category_id)
    if not cat:
        return None, f'Category with id {category_id} not found'

    old_name = cat.name
    old_path = cat.path
    changes = []

    if new_name and new_name.strip() != cat.name:
        cat.name = new_name.strip()
        changes.append(f'Renamed: "{old_name}" → "{cat.name}"')

    if new_parent_id != '__UNCHANGED__':
        old_parent_id = cat.parent_id
        if new_parent_id != cat.parent_id:
            if new_parent_id:
                new_parent = MasterCategory.query.get(new_parent_id)
                if not new_parent:
                    return None, f'New parent {new_parent_id} not found'
                cat.parent_id = new_parent_id
                cat.level = new_parent.level + 1
            else:
                cat.parent_id = None
                cat.level = 1
            changes.append(f'Parent changed: {old_parent_id} → {new_parent_id}')

    # Recompute paths for this node and all descendants
    _recompute_paths_recursive(cat)

    if changes:
        history = CategoryMappingHistory(
            master_category_id=cat.id,
            action='RENAMED' if 'Renamed' in str(changes) else 'MOVED',
            old_value=old_path,
            new_value=cat.path,
            changed_by=changed_by,
            notes='; '.join(changes),
        )
        db.session.add(history)

    try:
        db.session.commit()
        return cat, None
    except Exception as e:
        db.session.rollback()
        return None, str(e)


def _recompute_paths_recursive(category):
    """Recompute the materialized path for a category and all its descendants."""
    category.path = category.compute_path()
    for child in category.children.filter_by(is_active=True):
        _recompute_paths_recursive(child)


def deactivate_master_category(category_id, changed_by='system'):
    """
    Soft-delete a master category (set is_active=False).
    Does NOT delete from DB. Does NOT cascade to children — they remain
    independently active unless explicitly deactivated.

    Returns:
        (MasterCategory, None) on success
        (None, error_message) on failure
    """
    cat = MasterCategory.query.get(category_id)
    if not cat:
        return None, f'Category with id {category_id} not found'

    cat.is_active = False
    cat.updated_at = datetime.utcnow()

    history = CategoryMappingHistory(
        master_category_id=cat.id,
        action='DEACTIVATED',
        old_value='is_active=True',
        new_value='is_active=False',
        changed_by=changed_by,
        notes='Category deactivated (soft-delete)',
    )
    db.session.add(history)

    try:
        db.session.commit()
        return cat, None
    except Exception as e:
        db.session.rollback()
        return None, str(e)


def update_mapping(mapping_id, master_category_id, changed_by='system'):
    """
    Manually map (or remap) a platform_category_mapping entry to a
    master category. Records full audit trail.

    Returns:
        (PlatformCategoryMapping, None) on success
        (None, error_message) on failure
    """
    mapping = PlatformCategoryMapping.query.get(mapping_id)
    if not mapping:
        return None, f'Mapping with id {mapping_id} not found'

    master_cat = MasterCategory.query.get(master_category_id)
    if not master_cat:
        return None, f'Master category with id {master_category_id} not found'
    if not master_cat.is_active:
        return None, f'Master category "{master_cat.name}" is deactivated'

    old_master_id = mapping.master_category_id
    old_status = mapping.mapping_status

    mapping.master_category_id = master_category_id
    mapping.mapping_status = 'MANUALLY_MAPPED'
    mapping.confidence_score = 1.0
    mapping.updated_at = datetime.utcnow()

    action = 'REMAPPED' if old_master_id else 'MAPPED'
    history = CategoryMappingHistory(
        mapping_id=mapping.id,
        master_category_id=master_category_id,
        action=action,
        old_value=f'master_id={old_master_id}, status={old_status}',
        new_value=f'master_id={master_category_id}, status=MANUALLY_MAPPED',
        changed_by=changed_by,
        notes=f'Manual mapping to "{master_cat.name}"',
    )
    db.session.add(history)

    try:
        db.session.commit()
        return mapping, None
    except Exception as e:
        db.session.rollback()
        return None, str(e)


def get_mapping_stats():
    """
    Return per-platform statistics:
      - total mappings
      - mapped (AUTO + MANUAL)
      - pending
      - unmapped

    Returns list of dicts.
    """
    stats = db.session.query(
        PlatformCategoryMapping.platform_name,
        PlatformCategoryMapping.mapping_status,
        func.count(PlatformCategoryMapping.id)
    ).filter_by(
        is_active=True
    ).group_by(
        PlatformCategoryMapping.platform_name,
        PlatformCategoryMapping.mapping_status
    ).all()

    # Aggregate into per-platform summaries
    platform_stats = {}
    for platform, status, count in stats:
        if platform not in platform_stats:
            platform_stats[platform] = {
                'platform_name': platform,
                'total': 0,
                'mapped': 0,
                'pending': 0,
                'unmapped': 0,
            }
        platform_stats[platform]['total'] += count
        if status in ('AUTO_MAPPED', 'MANUALLY_MAPPED'):
            platform_stats[platform]['mapped'] += count
        elif status == 'PENDING':
            platform_stats[platform]['pending'] += count
        elif status == 'UNMAPPED':
            platform_stats[platform]['unmapped'] += count

    return list(platform_stats.values())


def auto_sync_platform(platform_name):
    """
    Run discovery and auto-mapping for a specific platform.
    Designed to be called automatically at the end of scrapers or upload tasks.
    """
    try:
        discovery = sync_platform_categories(platform_name)
        mapping = auto_map_pending()
        print(f"[CategoryAutoSync] Completed for {platform_name}: {discovery}, auto-mapped: {mapping.get('auto_mapped')}")
        return {
            'status': 'success',
            'platform': platform_name,
            'discovery': discovery,
            'auto_mapping': mapping
        }
    except Exception as e:
        print(f"[CategoryAutoSync] Error syncing {platform_name}: {e}")
        return {
            'status': 'error',
            'platform': platform_name,
            'message': str(e)
        }
