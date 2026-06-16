import os
import sys
import re
from datetime import datetime

# Reconfigure stdout to use UTF-8 to prevent charmap encoding errors on Windows
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

# Ensure backend directory is in path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, backend_dir)

from app import app
from extensions import db
from model.master_category import MasterCategory
from model.platform_category_mapping import PlatformCategoryMapping
from model.category_mapping_synonyms import CategoryMappingSynonym
from services.category_sync_service import normalize_category_name, auto_map_pending

HINDI_TRANSLATIONS = {
    'ट्राइपॉड और मोनोपॉड': 'Tripods & Monopods',
    'ट्राइपॉड और मोनोपॉड एक्सेसरी': 'Tripod & Monopod Accessories',
    'व्यक्तिगत देखभाल': 'Personal Care',
    'व्यक्तिगत देखभाल के उपकरण': 'Personal Care Appliances',
    'व्यायाम और स्वास्थ्य': 'Exercise & Fitness',
    'व्यायाम और स्वास्थ्य एक्सेसरीज़': 'Exercise & Fitness Accessories',
    'Amazon फैशन': 'Amazon Fashion',
    'Mp3 प्‍लेयर आर्मबैंड': 'MP3 Player Armbands',
    'अंदरुनी देखभाल और स्वच्छता उत्पाद': 'Intimate Care & Hygiene Products',
    'आभूषण': 'Jewellery',
    'आयरन्स': 'Irons',
    'आयुर्वेद उत्पाद': 'Ayurvedic Products',
    'आहार और पोषण': 'Diet & Nutrition',
    'इनडोर लाइटिंग': 'Indoor Lighting',
    'एक्शन कैमरा एक्सेसरीज़': 'Action Camera Accessories',
    'एक्सटर्नल डिवाइस और डेटा स्टोरेज': 'External Devices & Data Storage',
    'एक्सरसाइज़ और फ़िटनेस एरोबिक ट्रेनिंग मशीन': 'Exercise & Fitness Aerobic Training Machines',
    'एक्सेसरीज़': 'Accessories',
    'एयर कंडीशनर': 'Air Conditioners',
    'एयर कूलर': 'Air Coolers',
    'ऑडियो हेडफ़ोन': 'Audio Headphones',
    'ऑफिस के प्रोडक्ट': 'Office Products',
    'औद्योगिक और वैज्ञानिक': 'Industrial & Scientific',
    'कंपोनेंट': 'Components',
    'कंप्यूटर एक्सेसरी': 'Computer Accessories',
    'कंप्यूटर और सहायक उपकरण': 'Computers & Accessories',
    'कार और motorbike': 'Car & Motorbike',
    'कार और मोटरबाइक': 'Car & Motorbike',
    'कार्पेट और रग्स': 'Carpets & Rugs',
    'किचन और डाइनिंग': 'Kitchen & Dining',
    'किचन और होम अप्लाएंसेस': 'Kitchen & Home Appliances',
    'किचन के लिए स्टोरेज और कंटेनर': 'Kitchen Storage & Containers',
    'किराना और स्वादिष्ट फूड्स': 'Grocery & Gourmet Foods',
    'कुशन और कुशन कवर': 'Cushions & Cushion Covers',
    'कैमकॉर्डर, कैमरा और दूरबीन के लिए पट्टियां': 'Camcorders, Camera & Binocular Straps',
    'कैमरा और फ़ोटो क्‍लीनर': 'Camera & Photo Cleaners',
    'कैमरा और फ़ोटो फ़िल्टर्स': 'Camera & Photo Filters',
    'कैमरे और फ़ोटो के लिए केस और बैग': 'Camera & Photo Cases & Bags',
    'कैमरे और फ़ोटो के लिए बैटरियाँ और चार्जर्स': 'Camera & Photo Batteries & Chargers',
    'कैम्पिंग और हाइकिंग के लिए हेडलैम्प': 'Camping & Hiking Headlamps',
    'कॉन्टेक्ट लेंसेस': 'Contact Lenses',
    'कॉफी, टी और पेय पदार्थ': 'Coffee, Tea & Beverages',
    'क्राफ़्ट मटेरियल्स': 'Craft Materials',
    'क्रिकेट उपकरण': 'Cricket Equipment',
    'खुशबू': 'Fragrance',
    'खेल, fitness और आउटडोर': 'Sports, Fitness & Outdoors',
    'खेल, फिटनेस और आउटडोर': 'Sports, Fitness & Outdoors',
    'गतिविधि ट्रैकर्स': 'Activity Trackers',
    'गार्डन और आउटडोर': 'Garden & Outdoor',
    'गृह सज्जा': 'Home Decor',
    'घड़ियां': 'Watches',
    'घरेलू सफाई की आपूर्ति': 'Household Cleaning Supplies',
    'घरेलू सामग्री': 'Household Supplies',
    'टेलिस्कोप एक्सेसरी': 'Telescope Accessories',
    'टेलीविज़न': 'Television',
    'टैबलेट': 'Tablets',
    'ट्रैवल एक्सेसरीज़': 'Travel Accessories',
    'ट्रैवल डफल्स': 'Travel Duffles',
    'डाइनिंग टेबल': 'Dining Table',
    'डिजिटल Slr कैमरे': 'Digital SLR Cameras',
    'डिजिटल कैमरा एक्‍सेसरीज़': 'Digital Camera Accessories',
    'डीप फैट फ़्रायर्स': 'Deep Fat Fryers',
    'डेस्कटॉप': 'Desktops',
    'डॉग्ज़': 'Dogs',
    'त्वचा की देखभाल': 'Skin Care',
    'नेटवर्किंग उपकरण': 'Networking Devices',
    'पक्षी': 'Birds',
    'परिवार का पोषण': 'Family Nutrition',
    'पुरषों के ग्लोव्स': "Men's Gloves",
    'पुरषों के घड़ियां': "Men's Watches",
    'पुरषों के बटुए': "Men's Wallets",
    'पुरुषों का फैशन': "Men's Fashion",
    'पुरुषों की जीन्स': "Men's Jeans",
    'पुरुषों की टाई': "Men's Ties",
    'पुरुषों की धोती': "Men's Dhotis",
    'पुरुषों के इनरवियर': "Men's Innerwear",
    'पुरुषों के कपड़े': "Men's Clothing",
    'पुरुषों के कुर्ता सेट': "Men's Kurta Sets",
    'पुरुषों के कुर्ते': "Men's Kurtas",
    'पुरुषों के कैज़ुअल शूज़': "Men's Casual Shoes",
    'पुरुषों के कोट, जैकेट और निहित': "Men's Coats, Jackets & Vests",
    'पुरुषों के गहने और आभूषण': "Men's Jewellery",
    'पुरुषों के टी-शर्ट्स और पोलोज़': "Men's T-Shirts & Polos",
    'पुरुषों के ट्रैक पैंट': "Men's Track Pants",
    'पुरुषों के थर्मल अंडरवियर': "Men's Thermal Underwear",
    'पुरुषों के देसी स्टोल': "Men's Ethnic Stoles",
    'पुरुषों के नेहरू जैकेट': "Men's Nehru Jackets",
    'पुरुषों के फ़ॉर्मल ट्राउज़र्स': "Men's Formal Trousers",
    'पुरुषों के फ़ॉर्मल शर्ट्स': "Men's Formal Shirts",
    'पुरुषों के फ़ॉर्मल शूज़': "Men's Formal Shoes",
    'पुरुषों के मफ़लर और स्कार्फ़': "Men's Mufflers & Scarves",
    'पुरुषों के विंटरवियर': "Men's Winterwear",
    'पुरुषों के शर्ट्स': "Men's Shirts",
    'पुरुषों के शूज़': "Men's Shoes",
    'पुरुषों के सनग्लासेस': "Men's Sunglasses",
    'पुरुषों के सूट्स, ब्लेज़र्स और वेस्टकोट': "Men's Suits, Blazers & Waistcoats",
    'पुरुषों के स्पोर्ट्स और आउटडोर जूते': "Men's Sports & Outdoor Shoes",
    'पुरुषों के स्पोर्ट्स कोट और ब्लेज़र्स': "Men's Sports Coats & Blazers",
    'पुरुषों के स्पोर्ट्स शर्ट्स एंड टीज़': "Men's Sports Shirts & T-Shirts",
    'पुरुषों के स्पोर्ट्स शॉर्ट्स': "Men's Sports Shorts",
    'पुरुषों के स्‍वेटर्स': "Men's Sweaters",
    'पुरुषों के हैट्स और कैप्स': "Men's Hats & Caps",
    'पुरुषों बेल्ट': "Men's Belts",
    'प्मेमोरी कार्ड': 'Memory Cards',
    'प्रिंटर': 'Printers',
    'फ़ाइन आर्ट': 'Fine Art',
    'फ़िल्म': 'Films',
    'फ़िश और एक्वेटिक्स': 'Fish & Aquatics',
    'फ़ुटबॉल': 'Football',
    'फ़ोटो स्‍टूडियो और लाइटिंग': 'Photo Studio & Lighting',
    'फ़्लैश एक्सेसरी': 'Flash Accessories',
    'बटुए और पॉकेट आर्गेनाइज़र': 'Wallets & Pocket Organisers',
    'बालों की देखभाल': 'Hair Care',
    'बिल्लियाँ': 'Cats',
    'बेडशीट्स': 'Bedsheets',
    'बेडिंग और लिनेन': 'Bedding & Linen',
    'बेबी के गहने और आभूषण': 'Baby Jewellery',
    'बैकपैक्‍स': 'Backpacks',
    'बैग और बैकपैक्स': 'Bags & Backpacks',
    'बैडमिंटन': 'Badminton',
    'महिलाओं की ब्रा और स्पोर्ट्‍स ब्रा': "Women's Bra & Sports Bra",
    'महिलाओं की लहंगा चोली': "Women's Lehenga Choli",
    'महिलाओं की लॉन्जरी और नाइटवियर': "Women's Lingerie & Nightwear",
    'महिलाओं के कुर्ते और कुर्तियां': "Women's Kurtas & Kurtis",
    'महिलाओं के गहने और आभूषण': "Women's Jewellery",
    'महिलाओं के जूते': "Women's Shoes",
    'महिलाओं के ड्रेसेस और जंपसूट्स': "Women's Dresses & Jumpsuits",
    ' महिलाओं के फैशन': "Women's Fashion",
    'महिलाओं के फैशन': "Women's Fashion",
    'महिलाओं के फ़ैशन वाले सैंडल': "Women's Fashion Sandals",
    'महिलाओं के बैली फ़्लेट्स': "Women's Belly Flats",
    'महिलाओं के वेस्टर्न वियर': "Women's Western Wear",
    'महिलाओं के सनग्लासेस': "Women's Sunglasses",
    'महिलाओं के स्पोर्ट्‍सवियर': "Women's Sportswear",
    'महिलाओं के हैंडबैग': "Women's Handbags",
    'मिक्सर ग्राइंडर्स': 'Mixer Grinders',
    'मेकअप': 'Makeup',
    'मॉनीटर': 'Monitors',
    'मोबाइल एक्सेसरी': 'Mobile Accessories',
    'मोबाइल और एक्सेसरी': 'Mobile & Accessories',
    'योगा': 'Yoga',
    'यौन स्वास्थ और कामुकता': 'Sexual Wellness & Intimacy',
    'रकसैक और ट्रेकिंग बैकपैक': 'Rucksacks & Trekking Backpacks',
    'रनिंग Gps यूनिट': 'Running GPS Units',
    'रूम हीटर': 'Room Heaters',
    'रेफ्रिजरेटर': 'Refrigerators',
    'लक्ज़री ब्यूटी': 'Luxury Beauty',
    'लड़कियों के गहने और आभूषण': "Girls' Jewellery",
    'लड़कों के गहने और आभूषण': "Boys' Jewellery",
    'लूज़ जैमस्टोन और डायमंड': 'Loose Gemstones & Diamonds',
    'लेंस एक्सेसरी': 'Lens Accessories',
    'लैपटॉप': 'Laptops',
    'वयस्कों के डायपर्स और इनकंटिनेंस': 'Adult Diapers & Incontinence',
    'वाशिंग मशीन और ड्रायर': 'Washing Machines & Dryers',
    'वीडियो कैमरा एक्सेसरीज़': 'Video Camera Accessories',
    'वैक्यूम और फ़्लोर केयर': 'Vacuums & Floor Care',
    'शू एक्सेसरीज़ और केअर प्रोडक्ट्': 'Shoe Accessories & Care Products',
    'संगीत वाद्ययंत्र': 'Musical Instruments',
    'सभी कैटेगरी': 'All Categories',
    'सर्विलेंस कैमरे': 'Surveillance Cameras',
    'साइकलिंग': 'Cycling',
    'सामान एवं बैग': 'Luggage & Bags',
    'सूटकेस, चेक इन और स्ट्रॉली': 'Suitcases, Check-ins & Trolleys',
    'सेल फोन केस और कवर': 'Cell Phone Cases & Covers',
    'सेल फोन पोर्टेबल पावर बैंक': 'Cell Phone Portable Power Banks',
    'सॉफ्टवेयर': 'Software',
    'सौंदर्य': 'Personal Care & Beauty',
    'स्‍क्रीन गार्ड': 'Screen Guards',
    'स्टॉप वॉचेज़': 'Stopwatches',
    'स्ट्रेंथ ट्रेनिंग इक्विपमेंट': 'Strength Training Equipment',
    'स्नान और शावर': 'Bath & Shower',
    'स्नैक फूड': 'Snacks & Branded Foods',
    'स्पोर्ट्स कलेक्‍टिबल': 'Sports Collectibles',
    'स्पोर्ट्स सप्लिमेंट': 'Sports Supplements',
    'स्मॉल एनीमल': 'Small Animals',
    'स्लिप कवर': 'Slipcovers',
    'स्वास्थ्य देखभाल के डिवाइसेस': 'Healthcare Devices',
    'स्वेटशर्ट और हुडीज़': 'Sweatshirts & Hoodies',
    'हाई-फ़ाई और होम ऑडियो स्पीकर्स': 'Hi-Fi & Home Audio Speakers',
    'हीटिंग, कूलिंग और एयर क्वालिटी': 'Heating, Cooling & Air Quality',
    'हीटिंग, कूलिंग और air quality': 'Heating, Cooling & Air Quality',
    'हेलमेट': 'Helmets',
    'हेल्थ एवं पर्सनल केयर': 'Health & Personal Care',
    'हैंडबैग और पर्स': 'Handbags & Purses',
    'होम और किचन': 'Home & Kitchen',
    'होम थिएटर सिस्टम': 'Home Theatre Systems',
    'होम थिएटर, Tv और वीडियो': 'Home Theatre, TV & Video'
}

def is_hindi(text_val):
    if not text_val:
        return False
    return any('\u0900' <= char <= '\u097f' for char in text_val)

def run():
    print("=== Starting Hindi Categories Cleanup & Mapping ===")
    
    # 1. Soft deactivate active Hindi categories in master_categories
    active_cats = MasterCategory.query.filter_by(is_active=True).all()
    hindi_mc_ids = []
    
    print(f"Scanning {len(active_cats)} active master categories for Devanagari characters...")
    for mc in active_cats:
        if is_hindi(mc.name) or is_hindi(mc.path):
            hindi_mc_ids.append(mc.id)
            print(f"Deactivating Hindi category: {mc.path} (ID: {mc.id})")
            mc.is_active = False
            mc.updated_at = datetime.utcnow()
            
    if hindi_mc_ids:
        print(f"Total active Hindi master categories to deactivate: {len(hindi_mc_ids)}")
        
        # 2. Reset platform mapping entries pointing to these deactivated Hindi categories
        mappings = PlatformCategoryMapping.query.filter(
            PlatformCategoryMapping.master_category_id.in_(hindi_mc_ids),
            PlatformCategoryMapping.is_active == True
        ).all()
        
        print(f"Resetting {len(mappings)} mappings to PENDING status...")
        for m in mappings:
            print(f"Resetting mapping: '{m.platform_category_raw}' -> PENDING (was ID: {m.master_category_id})")
            m.master_category_id = None
            m.mapping_status = 'PENDING'
            m.confidence_score = 0.0
            m.updated_at = datetime.utcnow()
    else:
        print("No active Hindi master categories found to deactivate.")
        
    # 3. Add synonym mappings to the database
    print("\nRegistering Hindi translation synonyms...")
    synonyms_added = 0
    synonyms_updated = 0
    
    for raw, canonical in HINDI_TRANSLATIONS.items():
        norm_raw = normalize_category_name(raw)
        syn = CategoryMappingSynonym.query.filter_by(raw_value=norm_raw).first()
        if syn:
            if syn.canonical_value != canonical:
                print(f"Updating synonym: '{norm_raw}' -> '{canonical}' (was '{syn.canonical_value}')")
                syn.canonical_value = canonical
                synonyms_updated += 1
        else:
            print(f"Adding synonym: '{norm_raw}' -> '{canonical}'")
            syn = CategoryMappingSynonym(
                raw_value=norm_raw,
                canonical_value=canonical
            )
            db.session.add(syn)
            synonyms_added += 1
            
    print(f"Synonym registration complete: {synonyms_added} added, {synonyms_updated} updated.")
    
    # Commit database transaction
    try:
        db.session.commit()
        print("\nDatabase transaction committed successfully!")
    except Exception as e:
        db.session.rollback()
        print(f"\n[ERROR] Failed to commit database changes: {e}")
        return
        
    # 4. Trigger auto mapping pipeline
    print("\nRunning auto_map_pending() to map pending categories using the new synonyms...")
    try:
        res = auto_map_pending()
        print(f"Auto-mapper results: {res}")
    except Exception as e:
        print(f"[ERROR] Auto-mapper execution failed: {e}")

if __name__ == '__main__':
    with app.app_context():
        run()
