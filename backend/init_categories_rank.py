import os, urllib.parse
from dotenv import load_dotenv
load_dotenv('.env')
from sqlalchemy import create_engine, text

db_user = os.getenv('DB_USER')
db_password = urllib.parse.quote_plus(os.getenv('DB_PASSWORD'))
db_host = os.getenv('DB_HOST')
db_name = os.getenv('DB_NAME')

engine = create_engine(f"mysql+pymysql://{db_user}:{db_password}@{db_host}/{db_name}")

with engine.connect() as conn:
    print("Testing DB Connection...")
    # Create Top_categories_rank table
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS `Top_categories_rank` (
            `id` int(11) NOT NULL AUTO_INCREMENT,
            `category_name` varchar(255) DEFAULT NULL,
            `category_rank` int(11) DEFAULT NULL,
            `business_count` int(11) DEFAULT 0,
            PRIMARY KEY (`id`),
            UNIQUE KEY `idx_cat_name` (`category_name`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """))
    print("Ensured Top_categories_rank exists.")
    
    # Get all categories from category_master
    cats = conn.execute(text("SELECT category_name FROM category_master")).fetchall()
    cats = [c[0] for c in cats if c[0]]
    print(f"Found {len(cats)} categories in category_master.")
    
    # Check how many are already in Top_categories_rank
    existing = conn.execute(text("SELECT COUNT(*) FROM Top_categories_rank")).scalar()
    if existing == 0 and len(cats) > 0:
        print("Populating Top_categories_rank...")
        
        # Rank them by current business count in master_table to be smart
        counts = conn.execute(text("""
            SELECT business_category, COUNT(1) as cnt
            FROM master_table
            WHERE business_category IS NOT NULL AND business_category != ''
            GROUP BY business_category
            ORDER BY cnt DESC
        """)).fetchall()
        
        counts_dict = {row[0].strip().lower(): row[1] for row in counts if row[0]}
        
        cat_with_counts = []
        for cat in cats:
            c_lower = cat.strip().lower()
            cat_with_counts.append({'name': cat, 'count': counts_dict.get(c_lower, 0)})
            
        # Sort by count desc
        cat_with_counts.sort(key=lambda x: x['count'], reverse=True)
        
        total_cats = len(cat_with_counts)
        chunk_size = total_cats // 4
        
        insert_data = []
        for i, item in enumerate(cat_with_counts):
            if i < chunk_size:
                rank = 1
            elif i < chunk_size * 2:
                rank = 2
            elif i < chunk_size * 3:
                rank = 3
            else:
                rank = 4
            insert_data.append({"cat": item['name'], "rank": rank, "bc": item['count']})
            
        # Insert
        for d in insert_data:
            conn.execute(text("""
                INSERT INTO Top_categories_rank (category_name, category_rank, business_count)
                VALUES (:cat, :rank, :bc)
                ON DUPLICATE KEY UPDATE category_rank=VALUES(category_rank), business_count=VALUES(business_count)
            """), d)
        conn.commit()
        print("Successfully populated Top_categories_rank.")
    else:
        print(f"Top_categories_rank already has {existing} rows. Skipping initial population.")
