import pandas as pd
import os
import re
from datetime import datetime

import os

_zepto_dir = os.path.dirname(os.path.abspath(__file__))
CATEGORY_FOLDER = os.path.join(_zepto_dir, "csv_output", "category_wise")


def process_and_save(data):

    os.makedirs(CATEGORY_FOLDER, exist_ok=True)

    if not data:
        return

    # Optional analysis and validation layer
    try:
        from .analysis import analyze_scraped_data
    except ImportError:
        try:
            from analysis import analyze_scraped_data
        except ImportError:
            analyze_scraped_data = None

    if analyze_scraped_data:
        try:
            analyze_scraped_data(data)
        except Exception as ae:
            print(f"[!] Error invoking analysis layer: {ae}")

    df = pd.DataFrame(data)

    # Ensure schema (pincode excluded, scraped_at included)
    required_cols = [
        "sku_id",
        "product_name",
        "product_description",
        "quantity",
        "rating",
        "review",
        "mrp",
        "selling_price",
        "main_category",
        "subcategory",
        "product_url",
        "image_url",
        "availability",
        "scraped_at"
    ]

    for col in required_cols:
        if col not in df.columns:
            df[col] = None

    df = df[required_cols]

    # Clean SKU and deduplicate
    df["sku_id"] = df["sku_id"].astype(str).str.strip()
    df = df[df["sku_id"].notna()]
    df = df.drop_duplicates(subset=["sku_id"])

    # Fix datatypes
    df["rating"] = pd.to_numeric(df["rating"], errors="coerce")
    df["review"] = pd.to_numeric(df["review"], errors="coerce")
    df["mrp"] = pd.to_numeric(df["mrp"], errors="coerce").fillna(0).astype(int)
    df["selling_price"] = pd.to_numeric(df["selling_price"], errors="coerce").fillna(0).astype(int)
    df["availability"] = pd.to_numeric(df["availability"], errors="coerce").fillna(1).astype(int)

    # Product_Desc
    df["product_description"] = (
        df["product_description"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    # Normalize text before comparison
    df["product_name"] = df["product_name"].astype(str).str.strip().str.lower()
    df["product_description"] = df["product_description"].astype(str).str.strip().str.lower()

    # 🚀 Remove duplicate descriptions
    df.loc[
        df["product_name"] == df["product_description"],
        "product_description"
    ] = None

    # Timestamp
    df["scraped_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Save category-wise (disabled as per direct DB upload requirement)
    # for (main_category, subcategory), group in df.groupby(
    #     ["main_category", "subcategory"]
    # ):
    # 
    #     if not main_category:
    #         main_category = "unknown"
    # 
    #     if not subcategory:
    #         subcategory = "unknown"
    # 
    #     main_folder = os.path.join(
    #         CATEGORY_FOLDER,
    #         str(main_category)
    #     )
    # 
    #     os.makedirs(
    #         main_folder,
    #         exist_ok=True
    #     )
    # 
    #     safe_subcategory = re.sub(
    #         r'[\\/:*?"<>|]',
    #         '',
    #         str(subcategory)
    #     )
    # 
    #     file_path = os.path.join(
    #         main_folder,
    #         f"{safe_subcategory}.csv"
    #     )
    # 
    #     if os.path.exists(file_path):
    # 
    #         existing = pd.read_csv(
    #             file_path,
    #             dtype={"sku_id": str}
    #         )
    # 
    #         merged = pd.concat(
    #             [existing, group],
    #             ignore_index=True
    #         )
    # 
    #         merged = merged.drop_duplicates(
    #             subset=["sku_id"]
    #         )
    # 
    #         merged.to_csv(
    #             file_path,
    #             index=False
    #         )
    # 
    #     else:
    # 
    #         group.to_csv(
    #             file_path,
    #             index=False
    #         )
    print("[+] Category-wise CSVs saving bypassed (direct DB upload enabled)")