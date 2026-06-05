import re

WORD_TRANSLATION = {
    "सनग्लास": "Sunglasses",
    "सनग्लासेस": "Sunglasses",
    "और": "&",
    "केस": "Case",
    "कवर": "Cover",
    "पुरुषों": "Men",
    "महिलाओं": "Women",
    "के": "of",
    "लिए": "for",
    "नवीनतम": "Latest",
    "ब्रांडेड": "Branded",
    "स्टाइलिश": "Stylish",
    "गॉगल्स": "Goggles",
    "प्रोटेक्शन": "Protection",
    "के साथ": "with",
    "साथ": "with",
    "शूज़": "Shoes",
    "जूते": "Shoes",
    "घड़ियां": "Watches",
    "चश्मा": "Glasses",
    "बटुआ": "Wallet",
    "बटुए": "Wallet",
    "बेल्ट": "Belt",
    "हैंडबैग": "Handbag",
    "पर्स": "Purse",
    "फैशन": "Fashion",
    "मेकअप": "Makeup",
    "टी-शर्ट्स": "T-Shirts",
    "शर्ट्स": "Shirts",
    "कुर्ता": "Kurta",
    "सूट": "Suit",
    "लॉन्जरी": "Lingerie",
    "नाइटवियर": "Nightwear",
    "वेस्टर्न": "Western",
    "वियर": "Wear",
    "जीन्स": "Jeans",
    "सैंडल": "Sandals",
    "स्पोर्ट्स": "Sports",
    "आउटडोर": "Outdoor",
    "गहने": "Jewelry",
    "आभूषण": "Jewelry",
    "लड़कियों": "Girls",
    "बच्चों": "Kids",
    "बैग": "Bag",
    "बैग्स": "Bags",
    "कंप्यूटर": "Computer",
    "सहायक": "Accessories",
    "उपकरण": "Accessories",
    "गृह": "Home",
    "सज्जा": "Decor",
    "ट्रैवल": "Travel",
    "सूटकेस": "Suitcase",
    "स्ट्रॉली": "Trolley",
    "चेक": "Check",
    "इन": "in",
}

def clean_hindi_text(text_val):
    if not text_val:
        return ""
    # Replace known Hindi words with English equivalents
    words = text_val.split()
    cleaned_words = []
    for w in words:
        # Strip punctuation
        w_clean = re.sub(r'[^\u0900-\u097fA-Za-z0-9]', '', w)
        if w_clean in WORD_TRANSLATION:
            cleaned_words.append(WORD_TRANSLATION[w_clean])
        elif re.search(r'[\u0900-\u097f]', w):
            # Skip pure Hindi words that aren't mapped (or remove them)
            continue
        else:
            cleaned_words.append(w)
            
    res = " ".join(cleaned_words)
    # Remove extra spaces
    res = re.sub(r'\s+', ' ', res).strip()
    return res

# Test samples
samples = [
    "tracer सनग्लास और केस कवर पुरुषों और महिलाओं के लिए नवीनतम ब्रांडेड और स्टाइलिश सनग्लास गॉगल्स uv प्रोटेक्शन vx7001 c7 60014-135 के साथ",
    "महिलाओं के जूते stylish sport sneakers",
    "सूटकेस, चेक इन और स्ट्रॉली travel luggage bags",
    "GRENARO P10 Wireless Mic for Youtubers"
]

for s in samples:
    print(f"Original: {s}")
    print(f"Cleaned:  {clean_hindi_text(s)}\n")
