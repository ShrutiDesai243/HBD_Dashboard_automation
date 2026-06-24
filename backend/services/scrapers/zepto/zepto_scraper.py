import asyncio
import os
import re
import sys
import argparse
import urllib.request
import xml.etree.ElementTree as ET
from playwright.async_api import async_playwright

# Package-relative imports fallback for standalone compatibility
try:
    from .parser import extract_products
    from .cleaner import process_and_save
    from .scripts.db_uploader import upload_products_to_mysql
except (ImportError, ValueError):
    from parser import extract_products
    from cleaner import process_and_save
    from scripts.db_uploader import upload_products_to_mysql

# Structured state communication hook
try:
    from .state import should_stop, set_current_state, increment_scraped, increment_stats, increment_categories_scraped, increment_new_categories_mapped, set_target_pincodes, add_new_categories, add_new_products
except (ImportError, ValueError):
    try:
        from state import should_stop, set_current_state, increment_scraped, increment_stats, increment_categories_scraped, increment_new_categories_mapped, set_target_pincodes, add_new_categories, add_new_products
    except (ImportError, ValueError):
        def should_stop():
            return False
        def set_current_state(category=None, subcategory=None, pincode=None):
            pass
        def increment_scraped(count=1):
            pass
        def increment_stats(inserted=0, updated=0, skipped=0):
            pass
        def increment_categories_scraped(count=1):
            pass
        def increment_new_categories_mapped(count=1):
            pass
        def set_target_pincodes(pincodes_str):
            pass
        def add_new_categories(categories_list):
            pass
        def add_new_products(products_list):
            pass

def load_default_pincodes():
    """Returns hardcoded default pincodes."""
    return "400053,560034,110016,122002,500081"


def fetch_subcategory_urls():
    """Fetches all subcategory URLs dynamically from Zepto's sitemap."""
    print("[+] Fetching categories sitemap...")
    url = "https://www.zepto.com/sitemap/categories.xml"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            xml_data = response.read()
        
        root = ET.fromstring(xml_data)
        namespace = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
        urls = []
        for url_tag in root.findall('ns:url', namespace):
            loc = url_tag.find('ns:loc', namespace)
            if loc is not None and loc.text:
                urls.append(loc.text.strip())
        return urls
    except Exception as e:
        print(f"[!] Failed to fetch categories sitemap: {e}")
        return []


def get_category_slugs(url):
    """Extracts both the main category and subcategory slugs from a Zepto URL."""
    parts = url.split("/")
    if len(parts) >= 6:
        return parts[4], parts[5]
    return None, None


def match_and_filter_urls(user_input, urls):
    """Matches a loose category/subcategory name to the sitemap slugs and returns corresponding URLs."""
    # Normalize input
    user_input_clean = re.sub(r'[^a-z0-9\s-]', '', user_input.lower()).strip()
    user_input_slug = re.sub(r'[\s]+', '-', user_input_clean)
    user_tokens = set(user_input_clean.replace('-', ' ').split())
    
    filtered_urls = []
    matched_slugs = set()
    
    for url in urls:
        main_slug, sub_slug = get_category_slugs(url)
        matched = False
        for slug in (main_slug, sub_slug):
            if not slug:
                continue
            slug_clean = slug.replace('-', ' ')
            slug_tokens = set(slug_clean.split())
            
            if (user_input_slug == slug or 
                user_input_slug in slug or 
                slug in user_input_slug or 
                user_tokens.intersection(slug_tokens)):
                matched = True
                matched_slugs.add(slug)
                break
        if matched:
            filtered_urls.append(url)
            
    if matched_slugs:
        print(f"[+] Matched sitemap slugs: {list(matched_slugs)}")
        
    return list(set(filtered_urls))


async def auto_scroll(page):
    previous_height = 0
    stable_rounds = 0

    while True:
        # Check stop signal inside loop
        if should_stop():
            print("[!] Stop signal detected. Aborting page scrolling.")
            break
            
        current_height = await page.evaluate(
            "() => document.body.scrollHeight"
        )

        if current_height == previous_height:
            stable_rounds += 1
        else:
            stable_rounds = 0

        if stable_rounds >= 5:
            print("[+] Finished scrolling")
            break

        previous_height = current_height

        await page.evaluate(
            "window.scrollTo(0, document.body.scrollHeight)"
        )

        await asyncio.sleep(0.8)


async def set_location(page, pincode):
    """Sets the user location on Zepto using a pincode."""
    print(f"[+] Setting location to pincode: {pincode}...")
    try:
        location_btn = page.locator("[data-testid='user-address']").first
        await location_btn.wait_for(state="visible", timeout=20000)
        
        # Click retry loop to handle event listener attachment delays
        modal_opened = False
        for attempt in range(4):
            if should_stop():
                print("[!] Stop signal detected. Aborting location selector attempts.")
                return False
                
            btn_text = await location_btn.inner_text()
            print(f"[+] Clicking location selector '{btn_text}' (attempt {attempt+1})...")
            try:
                if attempt % 2 == 0:
                    await location_btn.click()
                else:
                    await location_btn.evaluate("el => el.click()")
            except Exception as e:
                print(f"[!] Click error: {e}")
                
            await asyncio.sleep(4)
            
            if should_stop():
                return False
                
            # Check if search input is visible
            search_input = page.get_by_placeholder("Search a new address")
            if await search_input.count() > 0:
                modal_opened = True
                break
            print("[!] Modal did not open, retrying...")
            
        if not modal_opened:
            raise RuntimeError("Location modal did not open after 3 attempts.")
        
        if should_stop():
            return False
            
        # Fill in the pincode
        search_input = page.get_by_placeholder("Search a new address").first
        await search_input.fill(pincode)
        await asyncio.sleep(3)
        
        if should_stop():
            return False
            
        # Click the first suggestion containing the pincode
        suggestion = page.get_by_text(pincode).first
        await suggestion.click()
        await asyncio.sleep(5)
        
        if should_stop():
            return False
            
        # Confirm it was updated
        updated_text = await location_btn.inner_text()
        print(f"[+] Location updated to: '{updated_text}'")
        return True
    except Exception as e:
        print(f"[!] Failed to set location to {pincode}: {e}")
        try:
            await page.screenshot(path="set_location_error.png")
            print("[+] Error screenshot saved to set_location_error.png")
        except Exception as se:
            print(f"[!] Failed to save error screenshot: {se}")
        return False


async def scrape_category(context, url, pincode=None):
    if should_stop():
        return
        
    page = await context.new_page()

    print(f"\n[+] Opening: {url}")

    await page.goto(
        url,
        wait_until="domcontentloaded",
        timeout=60000
    )

    if should_stop():
        await page.close()
        return

    await page.wait_for_load_state("networkidle")
    await asyncio.sleep(3)

    if should_stop():
        await page.close()
        return

    # CATEGORY FROM URL
    parts = url.split("/")
    main_category = parts[4]
    subcategory = parts[5]

    main_category = (
        main_category
        .replace("-", " ")
        .title()
    )

    subcategory = (
        subcategory
        .replace("-", " ")
        .title()
    )

    print(f"[+] Subcategory: {subcategory}")

    await auto_scroll(page)

    if should_stop():
        await page.close()
        return

    products = await extract_products(
        page,
        main_category,
        subcategory
    )



    if products:
        if pincode:
            for p in products:
                p["pincode"] = pincode
        process_and_save(products)
        increment_scraped(len(products))
        res = upload_products_to_mysql(products)
        if isinstance(res, tuple):
            if len(res) == 6:
                num_inserts, num_updates, num_skips, new_mappings, new_categories, new_products_details = res
                increment_stats(inserted=num_inserts, updated=num_updates, skipped=num_skips)
                if new_mappings > 0:
                    increment_new_categories_mapped(new_mappings)
                    add_new_categories(new_categories)
                if new_products_details:
                    add_new_products(new_products_details)
            elif len(res) == 4:
                num_inserts, num_updates, num_skips, new_mappings = res
                increment_stats(inserted=num_inserts, updated=num_updates, skipped=num_skips)
                if new_mappings > 0:
                    increment_new_categories_mapped(new_mappings)
            elif len(res) == 3:
                num_inserts, num_updates, num_skips = res
                increment_stats(inserted=num_inserts, updated=num_updates, skipped=num_skips)

    increment_categories_scraped(1)
    await page.close()


async def main(args_list=None):
    import json
    default_pincodes = load_default_pincodes()
    
    # Parse arguments programmatically or from sys.argv
    parser = argparse.ArgumentParser(description="Zepto Category & Location Scraper")
    parser.add_argument("--category", "-c", type=str, help="Loose category or subcategory name to scrape")
    parser.add_argument("--pincodes", "-p", type=str, default=default_pincodes,
                        help="Comma-separated list of pincodes to scrape")
    parser.add_argument("--resume", action="store_true", help="Resume from last run state")
    args = parser.parse_args(args_list)
    
    pincodes = [p.strip() for p in args.pincodes.split(",") if p.strip()]
    set_target_pincodes(", ".join(pincodes))
    
    category_inputs = []
    if args.category:
        category_inputs = [c.strip() for c in args.category.split(",") if c.strip()]
    else:
        print("[+] No category keyword provided. Defaulting to dynamically scraping all categories from sitemap.")
        category_inputs = ["all"]
        
    all_sitemap_urls = fetch_subcategory_urls()
    
    # Process inputs: handle 'all', direct URLs, and category keywords
    urls = []
    is_all = any(cat.lower() == "all" for cat in category_inputs)
    
    if is_all:
        urls = all_sitemap_urls
        print(f"[+] Scraping ALL categories. Found {len(urls)} subcategory URLs in sitemap.")
    else:
        for cat in category_inputs:
            if cat.startswith("http://") or cat.startswith("https://"):
                urls.append(cat)
            else:
                matched = match_and_filter_urls(cat, all_sitemap_urls)
                urls.extend(matched)
        # Deduplicate
        urls = list(set(urls))
        
        if not urls:
            print(f"[!] No categories or subcategories matched the inputs {category_inputs}. Exiting.")
            sys.exit(1)
        print(f"[+] Found {len(urls)} subcategory URLs for matching categories.")

    # State file setup
    backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    state_file = os.path.join(backend_dir, "output", "zepto_scrape_state.json")
    
    completed_pincodes = set()
    completed_urls = set()
    
    if args.resume and os.path.exists(state_file):
        try:
            with open(state_file, "r", encoding="utf-8") as f:
                saved_state = json.load(f)
            saved_cat = saved_state.get("category_input", "")
            curr_cat = args.category or ""
            if saved_cat.strip().lower() == curr_cat.strip().lower():
                completed_pincodes = set(saved_state.get("completed_pincodes", []))
                completed_urls = set(saved_state.get("completed_urls", []))
                print(f"[+] Resuming last scrape task. Skipping {len(completed_pincodes)} pincodes and {len(completed_urls)} categories.")
            else:
                print(f"[+] Category input mismatch (saved: '{saved_cat}', current: '{curr_cat}'). Starting fresh.")
        except Exception as e:
            print(f"[!] Failed to load resume state: {e}")
    else:
        # Reset state file
        try:
            os.makedirs(os.path.dirname(state_file), exist_ok=True)
            with open(state_file, "w", encoding="utf-8") as f:
                json.dump({
                    "category_input": args.category or "",
                    "pincodes": pincodes,
                    "completed_pincodes": [],
                    "completed_urls": []
                }, f, indent=2)
        except Exception as e:
            print(f"[!] Failed to initialize state file: {e}")

    if should_stop():
        print("[!] Stop signal detected before starting browser context.")
        return

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-gpu", "--disable-dev-shm-usage", "--no-sandbox"]
        )

        for pincode in pincodes:
            if pincode in completed_pincodes:
                print(f"[+] Pincode {pincode} already completed. Skipping.")
                continue

            if should_stop():
                print("[!] Stop signal detected. Exiting pincode loop.")
                break
                
            print(f"\n[=] Starting scrape cycle for pincode: {pincode} [=]")
            
            # Create a context for the pincode with standard desktop viewport
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                locale="en-US",
                timezone_id="Asia/Kolkata"
            )
            
            # Open homepage and set location
            init_page = await context.new_page()
            try:
                if should_stop():
                    await context.close()
                    break
                    
                try:
                    await init_page.goto("https://www.zepto.com/", wait_until="domcontentloaded", timeout=20000)
                except Exception as e:
                    print(f"[!] domcontentloaded timed out (20s) for home page, proceeding: {e}")
                
                if should_stop():
                    await init_page.close()
                    await context.close()
                    break
                    
                await asyncio.sleep(5)  # Extended sleep for initial page setup
                
                if should_stop():
                    await init_page.close()
                    await context.close()
                    break
                
                success = await set_location(init_page, pincode)
                if not success:
                    print(f"[!] Skipping pincode {pincode} due to location setup failure.")
                    await context.close()
                    continue
            except Exception as e:
                print(f"[!] Error loading page for pincode {pincode}: {e}")
                await context.close()
                continue
            finally:
                await init_page.close()
                
            if should_stop():
                await context.close()
                break
                
            # Scrape each subcategory using this context
            for url in urls:
                if url in completed_urls:
                    print(f"[+] Category URL {url} already completed. Skipping.")
                    continue

                if should_stop():
                    print("[!] Stop signal detected. Exiting category loop.")
                    break
                try:
                    main_category, subcategory = get_category_slugs(url)
                    if main_category:
                        main_category = main_category.replace("-", " ").title()
                    if subcategory:
                        subcategory = subcategory.replace("-", " ").title()
                        
                    # Update structured state with progress coordinates
                    set_current_state(category=main_category, subcategory=subcategory, pincode=pincode)
                    
                    await scrape_category(
                        context,
                        url,
                        pincode
                    )
                    
                    completed_urls.add(url)
                    try:
                        with open(state_file, "r", encoding="utf-8") as f:
                            saved_state = json.load(f)
                        saved_state["completed_urls"] = list(completed_urls)
                        with open(state_file, "w", encoding="utf-8") as f:
                            json.dump(saved_state, f, indent=2)
                    except Exception:
                        pass
                except Exception as e:
                    print(f"[!] Category error for {url}: {e}")
                
                # Check stop flag after async scrape operation completes
                if should_stop():
                    break

            await context.close()
            
            # Pincode finished successfully! Mark completed.
            if not should_stop():
                completed_pincodes.add(pincode)
                completed_urls.clear()
                try:
                    with open(state_file, "r", encoding="utf-8") as f:
                        saved_state = json.load(f)
                    saved_state["completed_pincodes"] = list(completed_pincodes)
                    saved_state["completed_urls"] = []
                    with open(state_file, "w", encoding="utf-8") as f:
                        json.dump(saved_state, f, indent=2)
                except Exception:
                    pass

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())