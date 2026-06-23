"""Safely reset the JioMart SQLite database."""
import os
import sqlite3
import db

def main():
    print("=" * 60)
    print("  RESETTING DATABASE")
    print("=" * 60)
    
    # Connect and drop all tables
    conn = db.get_connection()
    try:
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.execute("DROP TABLE IF EXISTS product_categories")
        conn.execute("DROP TABLE IF EXISTS products")
        conn.execute("DROP TABLE IF EXISTS scrape_runs")
        conn.execute("DROP TABLE IF EXISTS category_scrape_status")
        conn.execute("DROP TABLE IF EXISTS categories")
        conn.execute("PRAGMA foreign_keys = ON")
        conn.commit()
        print("[DB] All tables dropped successfully.")
    except Exception as e:
        print(f"[ERROR] Failed to drop tables: {e}")
        return
    finally:
        conn.close()

    # Re-initialize DB
    db.init_db()
    
    print("\n[SUCCESS] Database reset to clean slate (0 products, 0 categories).")

if __name__ == "__main__":
    main()
