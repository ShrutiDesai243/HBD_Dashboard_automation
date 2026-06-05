import pandas as pd
from database.mysql_connection import get_mysql_connection
from utils.safe_get import safe_get

def upload_zepto_data(file_paths):
    if not file_paths:
        raise ValueError("No file provided to upload")
    
    connection = get_mysql_connection()
    cursor = connection.cursor()
    inserted = 0
    batch_size = 10000
    try:
        for file in file_paths:
            chunkFile_data = pd.read_csv(file, chunksize=batch_size)
            for chunk in chunkFile_data:
                # Clean headers: lowercase and replace spaces/hyphens with underscores
                chunk.columns = [c.strip().lower().replace(' ', '_').replace('-', '_') for c in chunk.columns]
                
                chunk_data = []
                for row in chunk.itertuples(index=False):
                    sku_id = safe_get(row, 'sku_id') or safe_get(row, 'sku') or safe_get(row, 'id')
                    if not sku_id:
                        continue
                    
                    product_name = safe_get(row, 'product_name') or safe_get(row, 'name') or safe_get(row, 'title')
                    description = safe_get(row, 'description') or safe_get(row, 'desc') or ""
                    quantity = safe_get(row, 'quantity') or safe_get(row, 'qty') or ""
                    
                    # Convert numeric fields
                    rating = safe_get(row, 'rating')
                    try:
                        rating = float(rating) if rating is not None else 0.0
                    except ValueError:
                        rating = 0.0
                        
                    review = safe_get(row, 'review') or safe_get(row, 'reviews')
                    try:
                        review = float(review) if review is not None else 0.0
                    except ValueError:
                        review = 0.0
                        
                    mrp = safe_get(row, 'mrp') or safe_get(row, 'market_price')
                    try:
                        mrp = float(mrp) if mrp is not None else 0.0
                    except ValueError:
                        mrp = 0.0
                        
                    selling_price = safe_get(row, 'selling_price') or safe_get(row, 'sale_price') or safe_get(row, 'price')
                    try:
                        selling_price = float(selling_price) if selling_price is not None else 0.0
                    except ValueError:
                        selling_price = 0.0
                        
                    main_category = safe_get(row, 'main_category') or safe_get(row, 'category') or ""
                    subcategory = safe_get(row, 'subcategory') or safe_get(row, 'sub_category') or ""
                    product_url = safe_get(row, 'product_url') or safe_get(row, 'link') or ""
                    image_url = safe_get(row, 'image_url') or safe_get(row, 'img_url') or ""
                    
                    chunk_data.append((
                        str(sku_id),
                        product_name,
                        description,
                        quantity,
                        rating,
                        review,
                        mrp,
                        selling_price,
                        main_category,
                        subcategory,
                        product_url,
                        image_url
                    ))
                
                insert_query = """
                    INSERT INTO zepto (
                        sku_id, product_name, description, quantity, rating, review, mrp, selling_price, main_category, subcategory, product_url, image_url, scraped_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                    ON DUPLICATE KEY UPDATE
                        product_name = VALUES(product_name),
                        description = VALUES(description),
                        quantity = VALUES(quantity),
                        rating = VALUES(rating),
                        review = VALUES(review),
                        mrp = VALUES(mrp),
                        selling_price = VALUES(selling_price),
                        main_category = VALUES(main_category),
                        subcategory = VALUES(subcategory),
                        product_url = VALUES(product_url),
                        image_url = VALUES(image_url),
                        scraped_at = NOW();
                """
                if chunk_data:
                    cursor.executemany(insert_query, chunk_data)
                    connection.commit()
                    inserted += len(chunk_data)
        return inserted
    except Exception as e:
        connection.rollback()
        raise e
    finally:
        cursor.close()
        connection.close()
