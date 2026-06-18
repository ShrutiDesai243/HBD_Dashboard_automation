import os
import re
import pandas as pd
from datetime import datetime

# Feature flag - defaults to False in production, can be set to True for testing/validation
ENABLE_ANALYSIS = os.environ.get("ZEPTO_ENABLE_ANALYSIS", "False").lower() in ("true", "1", "yes")

def analyze_scraped_data(products, pincode=None):
    """
    Performs data quality analysis, validation, anomaly detection, and duplicate checks
    on the scraped products. Decoupled and error-safe to not block scraper execution.
    """
    if not ENABLE_ANALYSIS:
        return
        
    print("\n" + "="*60)
    print("[ANALYSIS] Running data quality analysis and validation layer...")
    print("="*60)
    
    try:
        total_scraped = len(products)
        if total_scraped == 0:
            print("[ANALYSIS] No products to analyze.")
            print("[ANALYSIS] Total scraped: 0")
            print("[ANALYSIS] Valid: 0")
            print("[ANALYSIS] Duplicates: 0")
            print("[ANALYSIS] Invalid: 0")
            print("="*60 + "\n")
            return
            
        # Standardize products list into a DataFrame for easier analysis
        df = pd.DataFrame(products)
        
        # Ensure required columns exist for analysis
        for col in ["sku_id", "product_name", "selling_price", "mrp", "main_category", "subcategory", "pincode", "product_url", "availability"]:
            if col not in df.columns:
                df[col] = None
                
        # Fill missing values for text columns to avoid errors
        df["product_name"] = df["product_name"].fillna("").astype(str).str.strip()
        df["main_category"] = df["main_category"].fillna("").astype(str).str.strip()
        df["subcategory"] = df["subcategory"].fillna("").astype(str).str.strip()
        df["pincode"] = df["pincode"].fillna(str(pincode) if pincode else "").astype(str).str.strip()
        
        # Convert prices to numeric
        df["selling_price"] = pd.to_numeric(df["selling_price"], errors="coerce").fillna(0)
        df["mrp"] = pd.to_numeric(df["mrp"], errors="coerce").fillna(0)
        
        # 1. Unique product count (deduplicate by name + pincode)
        df["name_lower"] = df["product_name"].str.lower()
        unique_by_name_pincode = df.drop_duplicates(subset=["name_lower", "pincode"])
        unique_count = len(unique_by_name_pincode)
        
        # 2. Missing fields count (name, price, category)
        missing_name = df[df["product_name"] == ""].shape[0]
        missing_price = df[df["selling_price"] == 0].shape[0]
        missing_category = df[(df["main_category"] == "") & (df["subcategory"] == "")].shape[0]
        
        # 3. Price anomalies: price = 0, mrp < price, extreme discounts (>90%)
        price_zero = df[df["selling_price"] == 0].shape[0]
        mrp_less_than_price = df[df["mrp"] < df["selling_price"]].shape[0]
        
        extreme_discount = 0
        for idx, row in df.iterrows():
            m_val = row["mrp"]
            s_val = row["selling_price"]
            if m_val > 0:
                discount_pct = (m_val - s_val) / m_val
                if discount_pct > 0.9:
                    extreme_discount += 1
                    
        # 4. Data quality validation
        # Each product must have: non-empty name, price > 0, category exists, valid pincode
        # Pincode validation checks if it is a 6-digit numeric code
        valid_mask = (
            (df["product_name"] != "") &
            (df["selling_price"] > 0) &
            ((df["main_category"] != "") | (df["subcategory"] != "")) &
            (df["pincode"].str.match(r"^\d{6}$"))
        )
        
        valid_df = df[valid_mask]
        invalid_df = df[~valid_mask]
        
        valid_count = len(valid_df)
        invalid_count = len(invalid_df)
        
        # 5. Duplicate detection using (name + category + pincode)
        df["combined_category"] = df["main_category"] + " > " + df["subcategory"]
        duplicates_mask = df.duplicated(subset=["name_lower", "combined_category", "pincode"], keep="first")
        duplicate_count = df[duplicates_mask].shape[0]
        
        # 6. Logging output summary (Matching exact required output formats)
        print(f"[ANALYSIS] Total scraped: {total_scraped}")
        print(f"[ANALYSIS] Valid: {valid_count}")
        print(f"[ANALYSIS] Duplicates: {duplicate_count}")
        print(f"[ANALYSIS] Invalid: {invalid_count}")
        
        # Print detailed warnings if there are issues
        if missing_name > 0 or missing_price > 0 or missing_category > 0:
            print(f"[ANALYSIS] [WARNING] Missing fields -> Names: {missing_name}, Prices: {missing_price}, Categories: {missing_category}")
            
        if price_zero > 0 or mrp_less_than_price > 0 or extreme_discount > 0:
            print(f"[ANALYSIS] [WARNING] Price anomalies -> Price = 0: {price_zero}, MRP < Price: {mrp_less_than_price}, Extreme Discounts (>90%): {extreme_discount}")
            
        if invalid_count > 0:
            print(f"[ANALYSIS] [INFO] Invalid products breakdown:")
            inv_names = invalid_df[invalid_df["product_name"] == ""].shape[0]
            inv_prices = invalid_df[invalid_df["selling_price"] <= 0].shape[0]
            inv_cats = invalid_df[(invalid_df["main_category"] == "") & (invalid_df["subcategory"] == "")].shape[0]
            inv_pins = invalid_df[~invalid_df["pincode"].str.match(r"^\d{6}$")].shape[0]
            print(f"    - Empty Name: {inv_names}")
            print(f"    - Price <= 0: {inv_prices}")
            print(f"    - Missing Category: {inv_cats}")
            print(f"    - Invalid Pincode (must be 6 digits): {inv_pins}")
            
        # 7. Optional debug export: Save cleaned CSV ONLY when ENABLE_ANALYSIS = True
        if valid_count > 0:
            # Clean up temporary fields used in analysis before saving
            clean_export_df = valid_df.drop(columns=["name_lower", "combined_category"], errors="ignore")
            
            # Save debug output
            debug_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "csv_output", "analysis_debug")
            os.makedirs(debug_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            category_slug = "all"
            if len(products) > 0:
                first_prod = products[0]
                if first_prod.get("main_category"):
                    category_slug = first_prod["main_category"].lower().replace(" ", "_")
                    
            debug_file_path = os.path.join(debug_dir, f"cleaned_{category_slug}_{timestamp}.csv")
            clean_export_df.to_csv(debug_file_path, index=False)
            print(f"[ANALYSIS] Saved cleaned debug CSV: {debug_file_path}")
            
    except Exception as e:
        print(f"[ANALYSIS] [ERROR] Analysis execution failed: {e}")
        # Decoupled - do not raise exception so it does not block scraper execution

    print("="*60 + "\n")
