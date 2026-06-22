import os
import zipfile
import csv
import glob

# The 8 base prefixes provided by the user
prefixes = [
    "Accessory_Stores-20260622T210106Z",
    "Air_conditioned_restaurants-20260622T210148Z",
    "Alcohol-Free_Cafes-20260622T210156Z",
    "American_Restaurants-20260622T210200Z",
    "Architectural_Services-20260622T210204Z",
    "atm-20260622T210212Z",
    "Auto_Parts_Dealers-20260622T210216Z",
    "Ayurvedic_Doctor-20260622T210255Z"
]

downloads_dir = r"C:\Users\User\Downloads"

def escape_sql(val):
    if val is None or val.strip() == "":
        return "NULL"
    # escape single quotes
    val = val.replace("'", "''")
    # escape backslashes
    val = val.replace("\\", "\\\\")
    return f"'{val}'"

global_business_id_counter = 100000

for prefix in prefixes:
    # Find the zip file
    zip_pattern = os.path.join(downloads_dir, f"{prefix}*.zip")
    zip_files = glob.glob(zip_pattern)
    if not zip_files:
        print(f"Not found: {zip_pattern}")
        continue
    
    zip_file = zip_files[0]
    sql_filename = os.path.join(downloads_dir, f"{prefix}.sql")
    
    with open(sql_filename, "w", encoding="utf-8") as sql_file:
        with zipfile.ZipFile(zip_file, "r") as z:
            for file_info in z.infolist():
                if file_info.filename.endswith(".csv"):
                    with z.open(file_info) as f:
                        content = f.read().decode("utf-8-sig")
                        reader = csv.DictReader(content.splitlines())
                        
                        insert_statements = []
                        for row in reader:
                            # Map CSV columns to SQL columns
                            # name,address,website,phone_number,reviews_count,reviews_average,category,subcategory,city,state,area
                            
                            business_name = escape_sql(row.get("name", ""))
                            address = escape_sql(row.get("address", ""))
                            website_url = escape_sql(row.get("website", ""))
                            primary_phone = escape_sql(row.get("phone_number", ""))
                            ratings = row.get("reviews_count", "NULL")
                            stars = row.get("reviews_average", "NULL")
                            if not ratings.strip(): ratings = "NULL"
                            if not stars.strip(): stars = "NULL"
                            
                            business_category = escape_sql(row.get("category", ""))
                            business_subcategory = escape_sql(row.get("subcategory", ""))
                            city = escape_sql(row.get("city", ""))
                            state = escape_sql(row.get("state", ""))
                            area = escape_sql(row.get("area", ""))
                            
                            global_business_id = str(global_business_id_counter)
                            global_business_id_counter += 1
                            
                            columns = [
                                "global_business_id",
                                "business_name",
                                "address",
                                "website_url",
                                "primary_phone",
                                "ratings",
                                "stars",
                                "business_category",
                                "business_subcategory",
                                "city",
                                "state",
                                "area"
                            ]
                            
                            values = [
                                global_business_id,
                                business_name,
                                address,
                                website_url,
                                primary_phone,
                                ratings,
                                stars,
                                business_category,
                                business_subcategory,
                                city,
                                state,
                                area
                            ]
                            
                            sql = f"INSERT INTO `master_table` ({', '.join(columns)}) VALUES ({', '.join(values)});"
                            insert_statements.append(sql)
                            
                        if insert_statements:
                            sql_file.write("\n".join(insert_statements) + "\n")
    print(f"Generated {sql_filename}")
