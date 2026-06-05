import os

mapping_path = r"scratch/static_mapping.py"
db_path = r"backend/services/scrapers/dmart_engine/database.py"

# Read static mapping dictionary content
with open(mapping_path, 'r', encoding='utf-8') as f:
    mapping_content = f.read().strip()

# Read database.py content
with open(db_path, 'r', encoding='utf-8') as f:
    db_content = f.read()

# 1. Insert the static mapping dictionary after logger declaration
logger_line = "logger = logging.getLogger(__name__)"
if logger_line in db_content and "STATIC_CATEGORY_MAPPING" not in db_content:
    db_content = db_content.replace(logger_line, logger_line + "\n\n" + mapping_content)
    print("Embedded STATIC_CATEGORY_MAPPING into database.py")
else:
    print("Warning: STATIC_CATEGORY_MAPPING already embedded or logger not found.")

# 2. Modify _get_deterministic_id to prioritize the static mapping
old_method = """    def _get_deterministic_id(self, path_str: str) -> int:
        \"\"\"Generate a 31-bit positive integer hash of the normalized category path.\"\"\"
        import hashlib
        normalized = " > ".join([p.strip().lower() for p in path_str.split('>') if p.strip()])
        hash_md5 = hashlib.md5(normalized.encode('utf-8')).hexdigest()
        val = int(hash_md5[:8], 16)
        return val & 0x7FFFFFFF"""

new_method = """    def _get_deterministic_id(self, path_str: str) -> int:
        \"\"\"Get pre-defined ID from static mapping or fallback to deterministic path hash.\"\"\"
        import hashlib
        normalized = " > ".join([p.strip().lower() for p in path_str.split('>') if p.strip()])
        
        # Check embedded static category mapping first to keep IDs consistent with original DB mapping
        if normalized in STATIC_CATEGORY_MAPPING:
            return STATIC_CATEGORY_MAPPING[normalized]['category_id']
            
        hash_md5 = hashlib.md5(normalized.encode('utf-8')).hexdigest()
        val = int(hash_md5[:8], 16)
        return val & 0x7FFFFFFF"""

if old_method in db_content:
    db_content = db_content.replace(old_method, new_method)
    print("Updated _get_deterministic_id method in database.py")
elif new_method in db_content:
    print("Method _get_deterministic_id already updated.")
else:
    print("Error: Could not find old _get_deterministic_id method in database.py!")
    # Let's try matching with single quotes or slightly different whitespace
    # (just in case, but standard template matches)

# Write modified database.py back
with open(db_path, 'w', encoding='utf-8') as f:
    f.write(db_content)

print("Done.")
