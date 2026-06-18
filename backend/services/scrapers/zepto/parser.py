import re
from datetime import datetime

BASE_URL = "https://www.zeptonow.com"


def clean_price(price_text):

    if not price_text:
        return 0

    price_text = re.sub(r"[^\d.]", "", price_text)

    try:
        return int(float(price_text))
    except:
        return 0


def _is_quantity_text(text):
    """Checks if a string represents quantity/packaging weight or count and should be filtered out of description."""
    text = text.lower().strip()
    
    # 1. Standard Units Regex
    unit_pattern = r"^(\d+(?:\.\d+)?)\s*(kg|g|gm|gms|gram|grams|ml|l|ltr|litre|litres|liter|liters|pcs?|pieces?|units?|pack|sheets?)$"
    if re.match(unit_pattern, text):
        return True
        
    # 2. Count Variations Regex
    count_pattern = r"^(pack\s+of\s+\d+|\d+\s+pack)$"
    if re.match(count_pattern, text):
        return True
        
    # 3. Quantity Labels Regex
    qty_pattern = r"^qty:\s*\d+$"
    if re.match(qty_pattern, text):
        return True
        
    return False


def split_product_name(full_name):
    """Splits product name and isolates description using a three-pass separation process."""
    if not full_name:
        return "", ""
        
    name_candidate = full_name.strip()
    descriptions = []
    
    # Pass 1: Parentheses Extraction
    parentheses_matches = re.findall(r"\(([^)]+)\)", name_candidate)
    for match in parentheses_matches:
        match_clean = match.strip()
        if match_clean and not _is_quantity_text(match_clean):
            descriptions.append(match_clean)
            
    # Strip parentheses and their contents from the name candidate
    name_candidate = re.sub(r"\([^)]+\)", "", name_candidate)
    name_candidate = re.sub(r"\s+", " ", name_candidate).strip()
    
    # Pass 2: Pipe Delimiter Splitting
    if "|" in name_candidate:
        parts = name_candidate.split("|")
        name_candidate = parts[0].strip()
        for part in parts[1:]:
            part_clean = part.strip()
            if part_clean and not _is_quantity_text(part_clean):
                descriptions.append(part_clean)
                
    # Pass 3: Smart Comma Splitting (with Safety Heuristics)
    if "," in name_candidate:
        idx = name_candidate.find(",")
        before = name_candidate[:idx].strip()
        after = name_candidate[idx+1:].strip()
        
        # Heuristic 1: Minimum Length Check
        rule1 = len(before) >= 10
        
        # Heuristic 2: Forbidden Start Conjunction Check
        forbidden_words = ["&", "and", "or", "with", "for", "in", "of", "to", "at", "by", "a", "an", "the"]
        first_word_match = re.match(r"^([^\s,]+)", after.lower())
        rule2 = True
        if first_word_match:
            first_word = first_word_match.group(1)
            if first_word in forbidden_words:
                rule2 = False
                
        if rule1 and rule2:
            name_candidate = before
            for seg in after.split(","):
                seg_clean = seg.strip()
                if seg_clean and not _is_quantity_text(seg_clean):
                    descriptions.append(seg_clean)
                    
    # Clean up final name and description
    cleaned_name = re.sub(r"\s+", " ", name_candidate).strip()
    
    # Deduplicate descriptions in case of duplicate matches
    unique_descs = []
    for d in descriptions:
        if d not in unique_descs:
            unique_descs.append(d)
            
    merged_description = " | ".join(unique_descs).strip()
    
    # Safely remove duplicate descriptions (if product_name == product_description)
    if cleaned_name.lower() == merged_description.lower():
        merged_description = ""
        
    return cleaned_name, merged_description


async def extract_products(page, main_category, subcategory):

    products = []

    cards = page.locator("div[data-variant='edlp'], div[data-variant='superstore']")

    body_text = await page.locator("body").inner_text()
    try:
        print(body_text[:1000])
    except UnicodeEncodeError:
        print(body_text[:1000].encode('ascii', errors='ignore').decode('ascii'))

    count = await cards.count()

    print(f"[+] Found {count} products")

    visited = set()

    for i in range(count):

        try:
            card = cards.nth(i)

            # PRODUCT URL
            parent_anchor = card.locator(
                "xpath=ancestor::a[1]"
            )

            href = await parent_anchor.get_attribute(
                "href"
            )

            if not href:
                continue

            # REMOVE NON-PRODUCT LINKS
            if "/pn/" not in href:
                continue

            # DEDUPE INSIDE PAGE
            if href in visited:
                continue

            visited.add(href)

            # FULL URL
            if href.startswith("http"):
                product_url = href
            else:
                product_url = BASE_URL + href

            # SKU
            sku_match = re.search(
                r"/pvid/([a-zA-Z0-9\-]+)",
                href
            )

            sku_id = (
                sku_match.group(1)
                if sku_match else ""
            )

            # PRODUCT NAME
            try:

                full_product_text = await card.locator(
                    "[data-slot-id='ProductName'] span"
                ).inner_text()

                full_product_text = full_product_text.strip()

                product_name, product_description = split_product_name(full_product_text)

            except:
                continue



            # INVALID NAMES
            if (
                product_name.lower() in [
                    "add",
                    "notify"
                ]
                or len(product_name) < 3
            ):
                continue

            # IMAGE URL
            image_url = ""

            try:

                image_el = card.locator("img").first

                image_url = await image_el.get_attribute(
                    "src"
                )

                if not image_url:
                    image_url = ""

            except:
                image_url = ""

            # QUANTITY
            quantity = ""

            try:

                quantity = await card.locator(
                    "[data-slot-id='PackSize'], [data-slot-id='QuantityInfo']"
                ).inner_text()

                quantity = quantity.strip()

            except:
                quantity = ""

            # SELLING PRICE
            selling_price = 0

            try:

                selling_price_text = await card.locator(
                    "[data-slot-id='EdlpPrice'] .cptQT7, \
     [data-slot-id='SuperstorePrice'] .coaxYA"
                ).inner_text()

                selling_price = clean_price(
                    selling_price_text
                )

            except:
                pass

            # MRP
            mrp = selling_price

            try:

                mrp_text = await card.locator(
                    "[data-slot-id='EdlpPrice'] .cx3iWL, \
     [data-slot-id='SuperstorePrice'] .chXyOJ"
                ).inner_text()

                mrp = clean_price(mrp_text)

            except:
                pass

            # INVALID PRICE
            if selling_price <= 0:
                continue

            # FULL TEXT
            full_text = await card.inner_text()

            # RATING
            rating = ""

            rating_match = re.search(
                r"(\d\.\d)",
                full_text
            )

            if rating_match:
                try:
                    rating = float(rating_match.group(1))
                except:
                    rating=None

            # REVIEW COUNT
            review = ""

            review_match = re.search(
                r"\(([\d\.]+[kK]?)\)",
                full_text
            )

            if review_match:

                review = review_match.group(1)

                # 8.4k -> 8400
                try:
                    if "k" in review.lower():
                        review = float(review.lower().replace("k", "")) * 1000
                    else:
                        review = float(review)
                except:
                    review = None

            # SAVE PRODUCT
            products.append({

                "sku_id": str(sku_id) if sku_id else None,

                "product_name": str(product_name) if product_name else None,

                "product_description": str(product_description),

                "quantity": str(quantity) if quantity else None,

                "rating": rating,  # float or None

                "review": review,  # float or None

                "mrp": int(mrp) if mrp else None,

                "selling_price": int(selling_price) if selling_price else None,

                "main_category": str(main_category) if main_category else None,

                "subcategory": str(subcategory) if subcategory else None,

                "product_url": str(product_url) if product_url else None,

                "image_url": str(image_url) if image_url else None,

                "availability": 0 if ("sold out" in full_text.lower() or "notify" in full_text.lower()) else 1,

                "scraped_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            })

            try:
                print(f"[+] {product_name}")
            except UnicodeEncodeError:
                print(f"[+] {product_name.encode('ascii', errors='ignore').decode('ascii')}")

        except Exception as e:

            print(f"[!] Parse error: {e}")

            continue

    return products