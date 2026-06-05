import pandas as pd
import re
from database.mysql_connection import get_mysql_connection
from utils.safe_get import safe_get
from utils.drop_non_essential_indexes import drop_non_essential_indexes
from utils.create_non_essential_indexes import create_non_essential_indexes

def extract_numeric(val):
    if not val:
        return 0.0
    val_str = str(val).strip()
    cleaned = re.sub(r'[^\d.]', '', val_str)
    try:
        return float(cleaned) if cleaned else 0.0
    except ValueError:
        return 0.0

def upload_india_mart_data(file_paths):
    if not file_paths:
        raise ValueError("No file provided to upload")
    
    connection = get_mysql_connection()
    cursor = connection.cursor()
    inserted = 0
    batch_size = 10000
    upload_success = False
    try:
        drop_non_essential_indexes(cursor, 'indiamart_products', ['category_name', 'sub_category_name', 'price_numeric'])
        connection.commit()
        for file in file_paths:
            with open(file, newline='', encoding='utf-8') as f:  
                chunkFile_data = pd.read_csv(file, chunksize=batch_size)
                for chunk in chunkFile_data:
                    # Clean headers to lowercase and replace spaces with underscores
                    chunk.columns = [c.strip().lower().replace(' ', '_').replace('-', '_') for c in chunk.columns]
                    
                    chunk_data = []
                    for row in chunk.itertuples(index=False):
                        asin = safe_get(row, 'asin') or safe_get(row, 'id')
                        if not asin:
                            continue
                            
                        category_name = safe_get(row, 'category_name') or safe_get(row, 'category') or safe_get(row, 'categoryname') or ""
                        sub_category_name = safe_get(row, 'sub_category_name') or safe_get(row, 'sub_category') or ""
                        product_name = safe_get(row, 'product_name') or safe_get(row, 'title') or safe_get(row, 'name') or ""
                        description = safe_get(row, 'description') or ""
                        price = safe_get(row, 'price') or ""
                        
                        stars = safe_get(row, 'stars') or safe_get(row, 'rating')
                        try:
                            stars = float(stars) if stars is not None else 0.0
                        except ValueError:
                            stars = 0.0
                            
                        reviews = safe_get(row, 'reviews') or safe_get(row, 'review_count') or safe_get(row, 'review')
                        try:
                            reviews = int(float(reviews)) if reviews is not None else 0
                        except ValueError:
                            reviews = 0
                            
                        manufacturer = safe_get(row, 'manufacturer') or safe_get(row, 'brand') or safe_get(row, 'seller') or ""
                        contact_number = safe_get(row, 'contact_number') or safe_get(row, 'phone') or ""
                        location = safe_get(row, 'location') or safe_get(row, 'city') or ""
                        gst_registration_date = safe_get(row, 'gst_registration_date') or ""
                        badges = safe_get(row, 'badges') or ""
                        productUrl = safe_get(row, 'producturl') or safe_get(row, 'link') or ""
                        imgUrl = safe_get(row, 'imgurl') or safe_get(row, 'image_url') or ""
                        price_numeric = extract_numeric(price)
                        
                        chunk_data.append((
                            str(asin),
                            category_name,
                            sub_category_name,
                            product_name,
                            description,
                            price,
                            stars,
                            reviews,
                            manufacturer,
                            contact_number,
                            location,
                            gst_registration_date,
                            badges,
                            productUrl,
                            imgUrl,
                            price_numeric
                        ))
                    
                    insert_query = """
                        INSERT INTO indiamart_products (
                            asin, category_name, sub_category_name, product_name, description, Price, stars, reviews, manufacturer, contact_number, location, gst_registration_date, badges, productUrl, imgUrl, price_numeric, added_time
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                        ON DUPLICATE KEY UPDATE
                            category_name = VALUES(category_name),
                            sub_category_name = VALUES(sub_category_name),
                            product_name = VALUES(product_name),
                            description = VALUES(description),
                            Price = VALUES(Price),
                            stars = VALUES(stars),
                            reviews = VALUES(reviews),
                            manufacturer = VALUES(manufacturer),
                            contact_number = VALUES(contact_number),
                            location = VALUES(location),
                            gst_registration_date = VALUES(gst_registration_date),
                            badges = VALUES(badges),
                            productUrl = VALUES(productUrl),
                            imgUrl = VALUES(imgUrl),
                            price_numeric = VALUES(price_numeric),
                            added_time = NOW();
                    """
                    try:
                        cursor.executemany(insert_query, chunk_data)
                        connection.commit()
                        inserted += len(chunk_data)
                    except Exception as e:
                        connection.rollback()
                        raise e
        upload_success = True
        return inserted
    finally:
        if upload_success:
            create_non_essential_indexes(cursor, 'indiamart_products', ['category_name', 'sub_category_name', 'price_numeric'])
            connection.commit()
        cursor.close()
        connection.close()
