from extensions import db


class Blinkit(db.Model):
    __tablename__ = 'blinkit'

    product_id = db.Column(db.BigInteger, primary_key=True)
    product_name = db.Column(db.Text)
    brand = db.Column(db.String(255))
    category = db.Column(db.String(255))
    sub_category = db.Column(db.String(255))
    price = db.Column(db.Numeric(10, 2))
    mrp = db.Column(db.Numeric(10, 2))
    discount = db.Column(db.Numeric(10, 2))
    quantity = db.Column(db.String(100))
    availability = db.Column(db.Boolean)
    image_url = db.Column(db.Text)
    product_url = db.Column(db.Text)

    def to_dict(self):
        return {
            "product_id": self.product_id,
            "product_name": self.product_name,
            "brand": self.brand,
            "category": self.category,
            "sub_category": self.sub_category,
            "price": float(self.price) if self.price else 0,
            "mrp": float(self.mrp) if self.mrp else 0,
            "discount": float(self.discount) if self.discount else 0,
            "quantity": self.quantity,
            "availability": bool(self.availability),
            "image_url": self.image_url,
            "product_url": self.product_url
        }

class DMartCategory(db.Model):
    __tablename__ = 'dmart_categories'
    category_id = db.Column(db.Integer, primary_key=True)
    category_name = db.Column(db.String(255), nullable=False)
    slug = db.Column(db.String(255), nullable=True)
    parent_id = db.Column(db.Integer, db.ForeignKey('dmart_categories.category_id', ondelete='SET NULL'), nullable=True)
    category_level = db.Column(db.Integer, nullable=True)
    category_path = db.Column(db.String(512), nullable=True)

    parent = db.relationship('DMartCategory', remote_side=[category_id], backref='children')

    def to_dict(self):
        return {
            "category_id": self.category_id,
            "category_name": self.category_name,
            "slug": self.slug,
            "parent_id": self.parent_id,
            "category_level": self.category_level,
            "category_path": self.category_path
        }

class DMart(db.Model):
    """dmart_products table — 10,740 rows.
    Actual columns: id, ASIN, Product_name, Image_URLs, link, price, listPrice,
                    category, Brand, description, category_id, quantity, availability
    """
    __tablename__ = 'dmart_products'
    id = db.Column(db.Integer, primary_key=True)
    ASIN = db.Column('ASIN', db.String(100))
    Product_name = db.Column('Product_name', db.Text)
    Image_URLs = db.Column('Image_URLs', db.Text)
    link = db.Column(db.Text)
    price = db.Column('price', db.String(100))
    listPrice = db.Column('listPrice', db.String(100), nullable=True)
    category = db.Column(db.String(255))
    Brand = db.Column('Brand', db.String(255))
    description = db.Column(db.Text)
    category_id = db.Column(db.Integer, db.ForeignKey('dmart_categories.category_id', ondelete='SET NULL'), nullable=True)
    quantity = db.Column('quantity', db.String(100), nullable=True)
    availability = db.Column('availability', db.Integer, default=1)
    scraped_at = db.Column('scraped_at', db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())

    @property
    def asin(self):
        return self.ASIN

    @asin.setter
    def asin(self, value):
        self.ASIN = value

    @property
    def title(self):
        return self.Product_name

    @title.setter
    def title(self, value):
        self.Product_name = value

    @property
    def imgUrl(self):
        return self.Image_URLs

    @imgUrl.setter
    def imgUrl(self, value):
        self.Image_URLs = value

    @property
    def productUrl(self):
        return self.link

    @productUrl.setter
    def productUrl(self, value):
        self.link = value

    @property
    def categoryName(self):
        return self.category

    @categoryName.setter
    def categoryName(self, value):
        self.category = value

    @property
    def brand(self):
        return self.Brand

    @brand.setter
    def brand(self, value):
        self.Brand = value

    @property
    def isBestSeller(self):
        return "false"

    @isBestSeller.setter
    def isBestSeller(self, value):
        pass

    @property
    def boughtInLastMonth(self):
        return "0"

    @boughtInLastMonth.setter
    def boughtInLastMonth(self, value):
        pass

    def to_dict(self):
        return {
            "id": self.id,
            "asin": self.ASIN,
            "name": self.Product_name,
            "price": self.price,
            "list_price": self.listPrice,
            "brand": self.Brand,
            "category": self.category,
            "category_id": self.category_id,
            "quantity": self.quantity,
            "availability": bool(self.availability) if self.availability is not None else True,
            "image_url": self.Image_URLs,
            "link": self.link,
            "scraped_at": self.scraped_at.isoformat() if self.scraped_at else None
        }


class JioMart(db.Model):
    __tablename__ = 'jio_mart_products'
    id = db.Column(db.Integer, primary_key=True)
    asin = db.Column(db.String(100))
    title = db.Column(db.Text)
    imgUrl = db.Column(db.Text)
    productUrl = db.Column(db.Text)
    stars = db.Column(db.String(50))
    reviews = db.Column(db.String(50))
    price = db.Column(db.String(100))
    listPrice = db.Column(db.String(100))
    categoryName = db.Column(db.String(255))
    isBestSeller = db.Column(db.String(50))
    boughtInLastMonth = db.Column(db.String(100))

    def to_dict(self):
        return {
            "id": self.id,
            "asin": self.asin,
            "name": self.title,
            "price": self.price,
            "list_price": self.listPrice,
            "stars": self.stars,
            "reviews": self.reviews,
            "category": self.categoryName,
            "link": self.productUrl
        }


class Flipkart(db.Model):
    __tablename__ = 'flipkart_products'
    id = db.Column(db.Integer, primary_key=True)
    asin = db.Column(db.String(100))
    title = db.Column(db.Text)
    imgUrl = db.Column(db.Text)
    productUrl = db.Column(db.Text)
    stars = db.Column(db.String(50))
    reviews = db.Column(db.String(50))
    price = db.Column(db.String(100))
    listPrice = db.Column(db.String(100))
    categoryName = db.Column(db.String(255))
    isBestSeller = db.Column(db.String(50))
    boughtInLastMonth = db.Column(db.String(100))

    def to_dict(self):
        return {
            "id": self.id,
            "asin": self.asin,
            "name": self.title,
            "price": self.price,
            "list_price": self.listPrice,
            "stars": self.stars,
            "reviews": self.reviews,
            "category": self.categoryName,
            "link": self.productUrl
        }


class IndiaMart(db.Model):
    """indiamart_products table — 46,116 rows (was wrongly pointing to india_mart).
    Actual columns: id, asin, category_name, sub_category_name, product_name,
                    description, Price, stars, reviews, manufacturer, contact_number,
                    location, gst_registration_date, badges, productUrl, imgUrl,
                    price_numeric, added_time
    """
    __tablename__ = 'indiamart_products'
    id = db.Column(db.Integer, primary_key=True)
    asin = db.Column(db.String(100))
    category_name = db.Column(db.String(255))
    sub_category_name = db.Column(db.String(255))
    product_name = db.Column(db.Text)
    description = db.Column(db.Text)
    Price = db.Column('Price', db.String(100))
    stars = db.Column(db.Float)
    reviews = db.Column(db.Integer)
    manufacturer = db.Column(db.String(255))
    contact_number = db.Column(db.String(100))
    location = db.Column(db.String(255))
    gst_registration_date = db.Column(db.DateTime)
    badges = db.Column(db.Text)
    productUrl = db.Column(db.Text)
    imgUrl = db.Column(db.Text)
    price_numeric = db.Column(db.Numeric(12, 2))
    added_time = db.Column(db.DateTime)

    def to_dict(self):
        return {
            "id": self.id,
            "asin": self.asin,
            "name": self.product_name,
            "category": self.category_name,
            "sub_category": self.sub_category_name,
            "price": float(self.price_numeric) if self.price_numeric else 0,
            "price_str": self.Price,
            "stars": float(self.stars) if self.stars else 0,
            "reviews": self.reviews or 0,
            "manufacturer": self.manufacturer,
            "location": self.location,
            "badges": self.badges,
            "link": self.productUrl,
            "image_url": self.imgUrl,
        }


class BigBasketNew(db.Model):
    """bigbasket table — 34,559 rows (the ~34-35K table).
    Columns: sku_id, product_name, product_url, rating, review, mrp,
             selling_price, main_category, subcategory
    """
    __tablename__ = 'bigbasket'
    sku_id = db.Column(db.BigInteger, primary_key=True)
    product_name = db.Column(db.String(512))
    product_url = db.Column(db.Text)
    rating = db.Column(db.Float)
    review = db.Column(db.Integer)
    mrp = db.Column(db.Float)
    selling_price = db.Column(db.Float)
    main_category = db.Column(db.String(255))
    subcategory = db.Column(db.String(255))

    def to_dict(self):
        return {
            "id": self.sku_id,
            "name": self.product_name,
            "category": self.main_category,
            "sub_category": self.subcategory,
            "sale_price": self.selling_price,
            "market_price": self.mrp,
            "rating": self.rating,
            "reviews": self.review,
            "link": self.product_url,
        }


class Vivo(db.Model):
    __tablename__ = 'vivo'
    id = db.Column(db.Integer, primary_key=True)
    pos_id = db.Column(db.String(100))
    hardware_id = db.Column(db.String(100))
    store_id = db.Column(db.String(100))
    merchant_name = db.Column(db.String(255))
    store_name = db.Column(db.String(255))
    address = db.Column(db.Text)
    city = db.Column(db.String(100))
    state = db.Column(db.String(100))
    pin_code = db.Column(db.String(20))

    def to_dict(self):
        return {
            "id": self.id,
            "pos_id": self.pos_id,
            "merchant_name": self.merchant_name,
            "name": self.store_name,
            "address": self.address,
            "city": self.city,
            "state": self.state,
            "pin_code": self.pin_code
        }


class Zepto(db.Model):
    __tablename__ = 'zepto'

    sku_id = db.Column(db.String(100), primary_key=True)
    product_name = db.Column(db.String(255))
    description = db.Column(db.Text)
    quantity = db.Column(db.Text)
    rating = db.Column(db.Float)
    review = db.Column(db.Float)
    mrp = db.Column(db.Integer)
    selling_price = db.Column(db.Integer)
    main_category = db.Column(db.Text)
    subcategory = db.Column(db.Text)
    product_url = db.Column(db.String(500))
    image_url = db.Column(db.Text)
    scraped_at = db.Column(db.DateTime)

    def to_dict(self):
        return {
            "id": self.sku_id,
            "sku_id": self.sku_id,
            "name": self.product_name,
            "description": self.description,
            "quantity": self.quantity,
            "rating": self.rating,
            "review": self.review,
            "mrp": self.mrp,
            "price": self.selling_price,
            "category": self.main_category,
            "subcategory": self.subcategory,
            "product_url": self.product_url,
            "image_url": self.image_url,
        }

