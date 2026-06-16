from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path


SOURCE = Path(r"C:\Users\User\Downloads\category_master (2).sql")
OUT_DIR = Path(__file__).resolve().parent / "cleaned"
TABLE = "category_master"
COLUMN = "category_name"


ACRONYMS = {
    "ac": "AC",
    "atm": "ATM",
    "b2b": "B2B",
    "dj": "DJ",
    "it": "IT",
    "led": "LED",
    "ro": "RO",
    "seo": "SEO",
    "ups": "UPS",
}
LOWER_WORDS = {"and", "or", "of", "for", "in", "on", "at", "to", "the", "a", "an"}
SPELLING_FIXES = {
    "Acccessory": "Accessory",
    "acccessory": "accessory",
    "Photograher": "Photographer",
    "photograher": "photographer",
    "Laundary": "Laundry",
    "laundary": "laundry",
    "Bunglow": "Bungalow",
    "bunglow": "bungalow",
    "Grament": "Garment",
    "grament": "garment",
    "Langage": "Language",
    "langage": "language",
}

SEMANTIC_ALIASES = {
    "ac dealer": "AC Dealers",
    "ac dealers": "AC Dealers",
    "top ac dealer": "AC Dealers",
    "top ac dealers": "AC Dealers",
    "accountant": "Accountants",
    "accountants": "Accountants",
    "accessory store": "Accessory Stores",
    "accessory stores": "Accessory Stores",
    "chartered accountant": "Chartered Accountants",
    "chartered accountants": "Chartered Accountants",
    "local chartered accountant": "Chartered Accountants",
    "local chartered accountants": "Chartered Accountants",
    "architect": "Architectural Services",
    "architectural service": "Architectural Services",
    "architectural services": "Architectural Services",
    "auto parts dealer": "Auto Parts Dealers",
    "auto parts dealers": "Auto Parts Dealers",
    "bank": "Banks",
    "banks": "Banks",
    "banquet hall": "Banquet Halls",
    "banquet halls": "Banquet Halls",
    "marriage and reception hall": "Banquet Halls",
    "beauty parlour": "Beauty Parlour",
    "bike dealer": "Bike Dealers",
    "bike dealers": "Bike Dealers",
    "bike showroom": "Bike Dealers",
    "boutique": "Boutiques",
    "boutiques": "Boutiques",
    "builder": "Builders",
    "builders": "Builders",
    "building contractor": "Building Contractors",
    "building contractors": "Building Contractors",
    "burger restaurant": "Burger Restaurants",
    "burger restaurants": "Burger Restaurants",
    "car dealer": "Car Dealers",
    "car dealers": "Car Dealers",
    "car showroom": "Car Dealers",
    "car service": "Car Service Centres",
    "car service centre": "Car Service Centres",
    "car service centres": "Car Service Centres",
    "caterer": "Catering Services",
    "caterers": "Catering Services",
    "catering service": "Catering Services",
    "catering services": "Catering Services",
    "clinic": "Clinics",
    "clinics": "Clinics",
    "club": "Clubs",
    "clubs": "Clubs",
    "computer and laptop repair and services": "Computer & Laptop Repair Services",
    "computer and laptop repair services": "Computer & Laptop Repair Services",
    "computer & laptop repair & services": "Computer & Laptop Repair Services",
    "computer repair service": "Computer Repair Services",
    "computer repair services": "Computer Repair Services",
    "computer services and repair": "Computer Repair Services",
    "computer services & repair": "Computer Repair Services",
    "dance class": "Dance Classes",
    "dance classes": "Dance Classes",
    "dentist": "Dentists",
    "dentists": "Dentists",
    "top dentist": "Dentists",
    "top dentists": "Dentists",
    "dietitian": "Dietitians",
    "dietitians": "Dietitians",
    "department store": "Departmental Stores",
    "departmental store": "Departmental Stores",
    "departmental stores": "Departmental Stores",
    "dermatologist": "Dermatologists",
    "dermatologists": "Dermatologists",
    "dessert restaurant": "Dessert Restaurants",
    "dessert restaurants": "Dessert Restaurants",
    "dj": "DJs",
    "djs": "DJs",
    "doctor": "Doctors",
    "doctors": "Doctors",
    "local doctors and clinics": "Doctors and Clinics",
    "electrician": "Electricians",
    "electricians": "Electricians",
    "electronic store": "Electronics Stores",
    "electronic stores": "Electronics Stores",
    "electronics store": "Electronics Stores",
    "electronics stores": "Electronics Stores",
    "event organizer": "Event Management Agencies",
    "event planner": "Event Management Agencies",
    "fabricator": "Fabricators",
    "fabricators": "Fabricators",
    "fashion store": "Fashion Stores",
    "fashion stores": "Fashion Stores",
    "florist": "Florists",
    "florists": "Florists",
    "furniture shop": "Furniture Stores",
    "furniture shops": "Furniture Stores",
    "furniture store": "Furniture Stores",
    "furniture stores": "Furniture Stores",
    "top furniture dealer": "Furniture Stores",
    "top furniture dealers": "Furniture Stores",
    "garment store": "Garment Stores",
    "garment stores": "Garment Stores",
    "readymade garment shop": "Garment Stores",
    "readymade garment shops": "Garment Stores",
    "general store": "General Stores",
    "general stores": "General Stores",
    "gift shop": "Gift Shops",
    "gift shops": "Gift Shops",
    "fancy and gift shop": "Gift Shops",
    "fancy & gift shop": "Gift Shops",
    "gym": "Gyms",
    "gyms": "Gyms",
    "handicraft shop": "Handicraft Stores",
    "handicraft shops": "Handicraft Stores",
    "handicraft store": "Handicraft Stores",
    "handicraft stores": "Handicraft Stores",
    "hardware and electrical shops": "Hardware and Electrical Stores",
    "hardware and electrical stores": "Hardware and Electrical Stores",
    "hospital": "Hospitals",
    "hospitals": "Hospitals",
    "hotel": "Hotels",
    "hotels": "Hotels",
    "house keeping services": "Housekeeping Services",
    "housekeeping service": "Housekeeping Services",
    "housekeeping services": "Housekeeping Services",
    "ice cream parlor": "Ice Cream Shops",
    "ice cream shop": "Ice Cream Shops",
    "insurance service": "Insurance Services",
    "insurance services": "Insurance Services",
    "interior designer": "Interior Designers",
    "interior designers": "Interior Designers",
    "italian restaurant": "Italian Restaurants",
    "italian restaurants": "Italian Restaurants",
    "jewellery shop": "Jewellery Stores",
    "jewellery shops": "Jewellery Stores",
    "jewellery showroom": "Jewellery Stores",
    "jewellery showrooms": "Jewellery Stores",
    "top jewellery store": "Jewellery Stores",
    "top jewellery stores": "Jewellery Stores",
    "language class": "Language Classes",
    "language classes": "Language Classes",
    "laundry service": "Laundry Services",
    "laundry services": "Laundry Services",
    "lawyer": "Lawyers",
    "lawyers": "Lawyers",
    "legal service": "Legal Services",
    "legal services": "Legal Services",
    "list of top builders and developers": "Builders and Developers",
    "list of top builders & developers": "Builders and Developers",
    "luggage and bags": "Luggage Shops",
    "luggage shop": "Luggage Shops",
    "luggage shops": "Luggage Shops",
    "man accessory": "Men Accessories",
    "men accessory": "Men Accessories",
    "men accessories": "Men Accessories",
    "medical store": "Medical Stores",
    "medical stores": "Medical Stores",
    "milk parlor": "Milk Parlors",
    "milk parlors": "Milk Parlors",
    "mobile store": "Mobile Stores",
    "mobile stores": "Mobile Stores",
    "modular kitchen": "Modular Kitchen Dealers",
    "modular kitchen dealer": "Modular Kitchen Dealers",
    "modular kitchen dealers": "Modular Kitchen Dealers",
    "movers and packers": "Packers and Movers",
    "movers & packers": "Packers and Movers",
    "packers and movers": "Packers and Movers",
    "packers & movers": "Packers and Movers",
    "north indian restaurant": "North Indian Restaurants",
    "north indian restaurants": "North Indian Restaurants",
    "nursing service": "Nursing Services",
    "nursing services": "Nursing Services",
    "optical shop": "Optical Stores",
    "optical store": "Optical Stores",
    "optical stores": "Optical Stores",
    "organic store": "Organic Stores",
    "organic stores": "Organic Stores",
    "packing service": "Packaging Services",
    "packaging service": "Packaging Services",
    "packaging services": "Packaging Services",
    "painting contractor": "Painting Contractors",
    "painting contractors": "Painting Contractors",
    "painter": "Painting Contractors",
    "pathology laboratory": "Pathology Laboratories",
    "pathology laboratories": "Pathology Laboratories",
    "pest control": "Pest Control Services",
    "pest control service": "Pest Control Services",
    "pest control services": "Pest Control Services",
    "pet shop": "Pet Shops",
    "pet shops": "Pet Shops",
    "pet store": "Pet Shops",
    "pet stores": "Pet Shops",
    "pharma store": "Pharmacies",
    "pharmacy": "Pharmacies",
    "pharmacies": "Pharmacies",
    "local pharmacies": "Pharmacies",
    "photographer": "Photographers",
    "photographers": "Photographers",
    "photographers and videographers": "Photographers and Videographers",
    "photography and videography services": "Photographers and Videographers",
    "photography & videography services": "Photographers and Videographers",
    "top film photography and videography services": "Photographers and Videographers",
    "top film photography & videography services": "Photographers and Videographers",
    "videographer and photographer": "Photographers and Videographers",
    "pizza": "Pizza Places",
    "pizza place": "Pizza Places",
    "pizza places": "Pizza Places",
    "placement service": "Placement Services",
    "placement services": "Placement Services",
    "play school": "Play Schools",
    "play schools": "Play Schools",
    "play schools and day care": "Play Schools and Day Care",
    "play schools & day care": "Play Schools and Day Care",
    "plumber": "Plumber Services",
    "plumber service": "Plumber Services",
    "plumber services": "Plumber Services",
    "quick bite cafes": "Quick Bites",
    "quick bites": "Quick Bites",
    "real estate agent": "Real Estate Agents",
    "real estate agents": "Real Estate Agents",
    "real estate agencies and brokers": "Real Estate Agents",
    "real estate agencies & brokers": "Real Estate Agents",
    "top real estate agent": "Real Estate Agents",
    "top real estate agents": "Real Estate Agents",
    "reiki center": "Reiki Centers",
    "reiki centers": "Reiki Centers",
    "resort": "Resorts",
    "resorts": "Resorts",
    "restaurant": "Restaurants",
    "restaurants": "Restaurants",
    "scrap dealer": "Scrap Dealers",
    "scrap dealers": "Scrap Dealers",
    "security system": "Security Systems",
    "security systems": "Security Systems",
    "shoe store": "Shoe Stores",
    "shoe stores": "Shoe Stores",
    "top shoe dealer": "Shoe Stores",
    "top shoe dealers": "Shoe Stores",
    "south indian restaurant": "South Indian Restaurants",
    "south indian restaurants": "South Indian Restaurants",
    "stationery shop": "Stationery Stores",
    "stationery store": "Stationery Stores",
    "stationery stores": "Stationery Stores",
    "supermarket": "Supermarkets",
    "supermarkets": "Supermarkets",
    "tailor": "Tailors",
    "tailors": "Tailors",
    "top tailor": "Tailors",
    "top tailors": "Tailors",
    "tax consultant": "Tax Consultants",
    "tax consultants": "Tax Consultants",
    "taxi and cab": "Taxi Services",
    "taxi & cab": "Taxi Services",
    "taxi service": "Taxi Services",
    "taxi services": "Taxi Services",
    "tea shop": "Tea Shops",
    "tea shops": "Tea Shops",
    "tiffin service": "Tiffin Services",
    "tiffin services": "Tiffin Services",
    "travel agent": "Travel Agents",
    "travel agents": "Travel Agents",
    "top travel agent": "Travel Agents",
    "top travel agents": "Travel Agents",
    "ups dealer": "UPS Dealers",
    "ups dealers": "UPS Dealers",
    "used car dealer": "Used Car Dealers",
    "used car dealers": "Used Car Dealers",
    "used cars": "Used Car Dealers",
    "vocational training": "Vocational Training Centers",
    "vocational training center": "Vocational Training Centers",
    "vocational training centers": "Vocational Training Centers",
    "website designer": "Website Designers",
    "website designers": "Website Designers",
    "internet website designers": "Website Designers",
    "website development and hosting companies": "Website Designers",
    "wedding planner": "Wedding Planners",
    "wedding planners": "Wedding Planners",
    "woman accessory": "Women Accessories",
    "women accessory": "Women Accessories",
    "women accessories": "Women Accessories",
    "yoga": "Yoga Classes",
    "yoga class": "Yoga Classes",
    "yoga classes": "Yoga Classes",
}


def sql_unescape(value: str) -> str:
    return value.replace("\\'", "'").replace("\\\\", "\\")


def sql_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def smart_title_word(word: str, is_first: bool) -> str:
    if word == "&":
        return word
    if word.startswith("(") and word.endswith(")") and len(word) > 2:
        inner = word[1:-1]
        return f"({smart_title_phrase(inner)})"

    parts = word.split("-")
    cleaned_parts = []
    for part in parts:
        prefix = ""
        suffix = ""
        while part and part[0] in "([{":
            prefix += part[0]
            part = part[1:]
        while part and part[-1] in ")]},":
            suffix = part[-1] + suffix
            part = part[:-1]

        lower = part.lower()
        if lower in ACRONYMS:
            cleaned = ACRONYMS[lower]
        elif lower in LOWER_WORDS and not is_first:
            cleaned = lower
        else:
            cleaned = lower.capitalize()
        cleaned_parts.append(f"{prefix}{cleaned}{suffix}")
    return "-".join(cleaned_parts)


def smart_title_phrase(value: str) -> str:
    words = value.split(" ")
    return " ".join(smart_title_word(word, index == 0) for index, word in enumerate(words))


def clean_category(value: str) -> str:
    value = sql_unescape(value)
    value = value.replace("_", " ")
    value = re.sub(r"\s+", " ", value.strip())
    for bad, good in SPELLING_FIXES.items():
        value = value.replace(bad, good)
    return smart_title_phrase(value)


def semantic_key(value: str) -> str:
    key = value.casefold()
    key = key.replace("&", " and ")
    key = re.sub(r"[^a-z0-9]+", " ", key)
    return re.sub(r"\s+", " ", key).strip()


def semantic_category(value: str) -> str:
    return SEMANTIC_ALIASES.get(semantic_key(value), value)


def extract_values(sql: str) -> list[str]:
    insert_pattern = re.compile(
        rf"INSERT INTO `{re.escape(TABLE)}` \(`{re.escape(COLUMN)}`\) VALUES\s*(.*?);",
        re.IGNORECASE | re.DOTALL,
    )
    match = insert_pattern.search(sql)
    if not match:
        raise ValueError(f"Could not find INSERT block for `{TABLE}`")
    return [sql_unescape(raw) for raw in re.findall(r"\('((?:[^'\\]|\\.)*)'\)", match.group(1))]


def format_insert(values: list[str]) -> str:
    rows = ",\n".join(f"('{sql_escape(value)}')" for value in values)
    return f"INSERT INTO `{TABLE}` (`{COLUMN}`) VALUES\n{rows};"


def build_header(mode: str) -> str:
    generated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return "\n".join(
        [
            "-- Cleaned category_master SQL",
            f"-- Source: {SOURCE}",
            f"-- Generated: {generated}",
            f"-- Mode: {mode}",
            "",
            'SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";',
            "START TRANSACTION;",
            'SET time_zone = "+00:00";',
            "/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;",
            "/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;",
            "/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;",
            "/*!40101 SET NAMES utf8mb4 */;",
            "",
        ]
    )


def create_table_sql(if_not_exists: bool = False) -> str:
    maybe = " IF NOT EXISTS" if if_not_exists else ""
    return "\n".join(
        [
            f"CREATE TABLE{maybe} `{TABLE}` (",
            f"  `{COLUMN}` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL,",
            f"  PRIMARY KEY (`{COLUMN}`),",
            f"  KEY `idx_category_name` (`{COLUMN}`)",
            ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;",
        ]
    )


def footer() -> str:
    return "\n".join(
        [
            "COMMIT;",
            "/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;",
            "/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;",
            "/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;",
            "",
        ]
    )


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    sql = SOURCE.read_text(encoding="utf-8-sig")
    original_values = extract_values(sql)

    seen = set()
    cleaned_values = []
    changes = []
    duplicate_rows = []
    for original in original_values:
        cleaned = clean_category(original)
        key = cleaned.casefold()
        if original != cleaned:
            changes.append({"from": original, "to": cleaned})
        if key in seen:
            duplicate_rows.append({"original": original, "cleaned_as": cleaned})
            continue
        seen.add(key)
        cleaned_values.append(cleaned)

    cleaned_values.sort(key=lambda value: value.casefold())

    files = {
        "full_replace": OUT_DIR / "category_master_cleaned_FULL_REPLACE.sql",
        "create_if_not_exists": OUT_DIR / "category_master_cleaned_CREATE_IF_NOT_EXISTS.sql",
        "table_import_replace_data": OUT_DIR / "category_master_cleaned_TABLE_IMPORT_REPLACE_DATA.sql",
        "semantic_full_replace": OUT_DIR / "category_master_cleaned_semantic_FULL_REPLACE.sql",
        "semantic_create_if_not_exists": OUT_DIR / "category_master_cleaned_semantic_CREATE_IF_NOT_EXISTS.sql",
        "semantic_table_import_replace_data": OUT_DIR / "category_master_cleaned_semantic_TABLE_IMPORT_REPLACE_DATA.sql",
        "report": OUT_DIR / "category_master_cleaned_report.json",
        "semantic_report": OUT_DIR / "category_master_cleaned_semantic_report.json",
    }

    files["full_replace"].write_text(
        "\n".join(
            [
                build_header("full_replace"),
                f"DROP TABLE IF EXISTS `{TABLE}`;",
                create_table_sql(),
                "",
                format_insert(cleaned_values),
                footer(),
            ]
        ),
        encoding="utf-8",
    )

    files["create_if_not_exists"].write_text(
        "\n".join(
            [
                build_header("create_if_not_exists"),
                create_table_sql(if_not_exists=True),
                "",
                format_insert(cleaned_values),
                footer(),
            ]
        ),
        encoding="utf-8",
    )

    files["table_import_replace_data"].write_text(
        "\n".join(
            [
                "-- Import this from phpMyAdmin while viewing the existing category_master table.",
                "-- It replaces only this table's data; it does not recreate the table.",
                "SET FOREIGN_KEY_CHECKS=0;",
                f"TRUNCATE TABLE `{TABLE}`;",
                format_insert(cleaned_values),
                "SET FOREIGN_KEY_CHECKS=1;",
                "",
            ]
        ),
        encoding="utf-8",
    )

    semantic_seen = set()
    semantic_values = []
    semantic_changes = []
    semantic_duplicate_rows = []
    for original in original_values:
        cleaned = clean_category(original)
        semantic = semantic_category(cleaned)
        if cleaned != semantic:
            semantic_changes.append({"from": cleaned, "to": semantic, "source": original})
        key = semantic.casefold()
        if key in semantic_seen:
            semantic_duplicate_rows.append({"original": original, "cleaned_as": cleaned, "semantic_as": semantic})
            continue
        semantic_seen.add(key)
        semantic_values.append(semantic)

    semantic_values.sort(key=lambda value: value.casefold())

    files["semantic_full_replace"].write_text(
        "\n".join(
            [
                build_header("semantic_full_replace"),
                f"DROP TABLE IF EXISTS `{TABLE}`;",
                create_table_sql(),
                "",
                format_insert(semantic_values),
                footer(),
            ]
        ),
        encoding="utf-8",
    )

    files["semantic_create_if_not_exists"].write_text(
        "\n".join(
            [
                build_header("semantic_create_if_not_exists"),
                create_table_sql(if_not_exists=True),
                "",
                format_insert(semantic_values),
                footer(),
            ]
        ),
        encoding="utf-8",
    )

    files["semantic_table_import_replace_data"].write_text(
        "\n".join(
            [
                "-- Import this from phpMyAdmin while viewing the existing category_master table.",
                "-- This semantic-cleaned version replaces only this table's data; it does not recreate the table.",
                "SET FOREIGN_KEY_CHECKS=0;",
                f"TRUNCATE TABLE `{TABLE}`;",
                format_insert(semantic_values),
                "SET FOREIGN_KEY_CHECKS=1;",
                "",
            ]
        ),
        encoding="utf-8",
    )

    semantic_report = {
        "source": str(SOURCE),
        "table": TABLE,
        "column": COLUMN,
        "original_rows": len(original_values),
        "semantic_cleaned_rows": len(semantic_values),
        "semantic_unique_case_insensitive": len({value.casefold() for value in semantic_values}),
        "max_semantic_length": max(len(value) for value in semantic_values) if semantic_values else 0,
        "removed_duplicate_rows": len(semantic_duplicate_rows),
        "semantic_renamed_rows_before_dedup": len(semantic_changes),
        "semantic_changes": semantic_changes,
        "duplicates_removed": semantic_duplicate_rows,
        "output_files": {
            name: str(path)
            for name, path in files.items()
            if name.startswith("semantic_")
        },
    }
    files["semantic_report"].write_text(json.dumps(semantic_report, indent=2, ensure_ascii=False), encoding="utf-8")

    report = {
        "source": str(SOURCE),
        "table": TABLE,
        "column": COLUMN,
        "original_rows": len(original_values),
        "original_unique_exact": len(set(original_values)),
        "cleaned_rows": len(cleaned_values),
        "cleaned_unique_case_insensitive": len({value.casefold() for value in cleaned_values}),
        "max_cleaned_length": max(len(value) for value in cleaned_values) if cleaned_values else 0,
        "removed_duplicate_rows": len(duplicate_rows),
        "changed_rows_before_dedup": len(changes),
        "changes": changes,
        "duplicates_removed": duplicate_rows,
        "output_files": {name: str(path) for name, path in files.items()},
    }
    files["report"].write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(
        json.dumps(
            {
                "conservative": {k: v for k, v in report.items() if k not in {"changes", "duplicates_removed", "output_files"}},
                "semantic": {
                    k: v
                    for k, v in semantic_report.items()
                    if k not in {"semantic_changes", "duplicates_removed", "output_files"}
                },
                "output_files": {name: str(path) for name, path in files.items()},
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
