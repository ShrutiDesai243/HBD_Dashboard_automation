import pandas as pd
from database.mysql_connection import get_mysql_connection
from utils.safe_get import safe_get
from utils.drop_non_essential_indexes import drop_non_essential_indexes
from utils.create_non_essential_indexes import create_non_essential_indexes

def upload_dmart_data(file_paths):
    if not file_paths:
        print("logic error")
        raise ValueError("No file provided to upload")
    
    connection = get_mysql_connection()
    cursor = connection.cursor()
    inserted = 0
    batch_size = 10000
    upload_success = False
    try:
        drop_non_essential_indexes(cursor,'dmart_products',['price','category'])
        connection.commit()
        for file in file_paths:
            with open(file,newline='',encoding='utf-8') as f:  
                chunkFile_data = pd.read_csv(file,chunksize=batch_size)
                for chunk in chunkFile_data:
                    chunk = chunk.rename(columns=lambda c:c.replace(' ','_'))
                    chunk_data=[]
                    for row in chunk.itertuples(index=False):
                        product_name = safe_get(row, 'title') or safe_get(row, 'Product_name') or safe_get(row, 'product_name')
                        brand = safe_get(row, 'brand') or safe_get(row, 'Brand') or safe_get(row, 'brand_name')
                        
                        # Self-healing brand extraction if brand is missing but name exists
                        if not brand and product_name:
                            words = product_name.split()
                            if words:
                                if len(words) > 1 and words[0].lower() == 'dmart' and words[1].lower() == 'premia':
                                    brand = "DMart Premia"
                                elif len(words) > 1 and words[0].lower() == 'wagh' and words[1].lower() == 'bakri':
                                    brand = "Wagh Bakri"
                                elif len(words) > 1 and words[0].lower() == 'thums' and words[1].lower() == 'up':
                                    brand = "Thums Up"
                                elif len(words) > 1 and words[0].lower() == 'red' and words[1].lower() == 'bull':
                                    brand = "Red Bull"
                                elif len(words) > 1 and words[0].lower() == 'tata' and words[1].lower() in ('tea', 'sampann', 'simply'):
                                    brand = "Tata"
                                else:
                                    brand = words[0].strip().strip(':').strip('-').strip()
                                if brand:
                                    brand = brand.title()

                        row_tuple = (
                            safe_get(row, 'asin') or safe_get(row, 'ASIN'),                             
                            product_name,
                            safe_get(row, 'imgUrl') or safe_get(row, 'Image_URLs') or safe_get(row, 'image_url'),
                            safe_get(row, 'productURL') or safe_get(row, 'link') or safe_get(row, 'product_url'),
                            safe_get(row, 'price'),
                            safe_get(row, 'listPrice') or safe_get(row, 'mrp'),
                            safe_get(row, 'categoryName') or safe_get(row, 'category') or "Uncategorized",
                            safe_get(row, 'quantity') or safe_get(row, 'pack_size') or safe_get(row, 'packSize'),
                            safe_get(row, 'availability') or 1,
                            brand,
                        )
                        chunk_data.append(row_tuple)

                    # storing the valus in the database
                    upload_dmart_data_query = '''
                    INSERT INTO dmart_products (
                        ASIN, Product_name, Image_URLs, link, price, listPrice, category, quantity, availability, Brand) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                        Product_name = VALUES(Product_name),
                        Image_URLs = VALUES(Image_URLs),
                        link = VALUES(link),
                        price = VALUES(price),
                        listPrice = VALUES(listPrice),
                        category = VALUES(category),
                        quantity = VALUES(quantity),
                        availability = VALUES(availability),
                        Brand = VALUES(Brand);
                    '''
                    try:
                        cursor.executemany(upload_dmart_data_query,chunk_data)
                        connection.commit()
                        inserted+=len(chunk_data)
                    except Exception:
                        print("roll error")
                        connection.rollback()
                        raise 
        upload_success = True
        return inserted
    finally:
        if upload_success:
            create_non_essential_indexes(cursor,'dmart_products',['price','category'])
            connection.commit()
        cursor.close()
        connection.close()
