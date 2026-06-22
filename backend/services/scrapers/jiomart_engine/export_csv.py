"""
Export SQLite Products to Clean CSV
====================================
Dumps deduplicated products from SQLite to a clean CSV file,
with full category hierarchy columns.

Usage:
    python export_csv.py                          # Default output: jiomart_products_export.csv
    python export_csv.py output_file.csv          # Custom output filename
"""

import os
import sys
import csv

# Fix Windows console encoding
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import db

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_OUTPUT = os.path.join(BASE_DIR, "jiomart_products_export.csv")

CSV_HEADERS = [
    "sku_id",
    "product_name",
    "product_url",
    "mrp",
    "selling_price",
    "brand",
    "quantity",
    "size",
    "main_category",
    "level1_category",
    "level2_category",
    "level3_category",
    "first_seen_at",
    "last_seen_at",
]


def export_products(output_file):
    """Export all products with hierarchy to CSV."""
    print(f"[1/2] Querying products from database...")
    rows = db.export_all_products_with_hierarchy()
    print(f"  → {len(rows):,} product rows retrieved")

    print(f"\n[2/2] Writing to: {os.path.basename(output_file)}")
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)

    # Verify
    file_size = os.path.getsize(output_file)
    size_mb = file_size / (1024 * 1024)
    print(f"\n  Export complete!")
    print(f"  Rows written:  {len(rows):,}")
    print(f"  File size:     {size_mb:.1f} MB")
    print(f"  Output:        {output_file}")

    # Quick duplicate check
    skus = [r.get("sku_id") for r in rows if r.get("sku_id")]
    unique_skus = set(skus)
    if len(skus) != len(unique_skus):
        print(f"\n  ⚠ WARNING: {len(skus) - len(unique_skus)} duplicate SKUs found in export!")
        print(f"    This may be due to products being linked to multiple category paths.")
        print(f"    Consider using GROUP BY sku_id in the export query.")
    else:
        print(f"\n  ✓ Zero duplicates confirmed: {len(unique_skus):,} unique SKUs")


def main():
    print("=" * 60)
    print("  JioMart SQLite → CSV Export")
    print("=" * 60)

    db.init_db()

    # Determine output file
    output_file = DEFAULT_OUTPUT
    if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
        output_file = sys.argv[1]
        if not os.path.isabs(output_file):
            output_file = os.path.join(BASE_DIR, output_file)

    total_products = db.get_product_count()
    print(f"\n  Products in database: {total_products:,}")

    if total_products == 0:
        print("  No products to export.")
        return

    export_products(output_file)


if __name__ == "__main__":
    main()
