"""
items.py
========
Place this at flipkart_scraper/items.py
"""

import scrapy


class FlipkartItem(scrapy.Item):
    # Category breadcrumb
    main_category = scrapy.Field()
    subcategory   = scrapy.Field()
    leaf_category = scrapy.Field()

    # Identity
    product_id   = scrapy.Field()   # PID extracted from URL
    product_url  = scrapy.Field()   # clean URL (no tracking params)
    product_name = scrapy.Field()   # full name from <a title="...">
    brand        = scrapy.Field()   # div.Fo1I0b (fashion / some electronics)

    # Pricing
    price    = scrapy.Field()   # selling price   div.hZ3P6w
    mrp      = scrapy.Field()   # MRP             div.kRYCnD
    discount = scrapy.Field()   # "67% off"       div.HQe8jr span

    # Ratings
    rating  = scrapy.Field()   # div.MKiFS6
    reviews = scrapy.Field()   # normalised count string

    # Media
    image_url = scrapy.Field()  # img.UCc1lI or img.MZeksS

    # Specs (appliances only — None for other categories)
    spec_bullets = scrapy.Field()  # "| "-joined li.DTBslk text