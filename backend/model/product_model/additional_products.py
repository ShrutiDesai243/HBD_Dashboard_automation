from extensions import db

class Blinkit(db.Model):
    __tablename__ = 'blinkit'
    id = db.Column(db.Integer, primary_key=True)
    product = db.Column(db.String(255))
    category = db.Column(db.String(255))
    sub_category = db.Column(db.String(255))
    brand = db.Column(db.String(255))
    sale_price = db.Column(db.String(50))
    market_price = db.Column(db.String(50))
    type = db.Column(db.String(100))
    rating = db.Column(db.String(50))
    description = db.Column(db.Text)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.product,
            "category": self.category,
            "sub_category": self.sub_category,
            "brand": self.brand,
            "sale_price": self.sale_price,
            "market_price": self.market_price,
            "rating": self.rating,
            "description": self.description
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
    __tablename__ = 'dmart_products'
    id = db.Column(db.Integer, primary_key=True)
    asin = db.Column('ASIN', db.String(100))
    title = db.Column('Product_name', db.Text)
    imgUrl = db.Column('Image_URLs', db.Text)
    productUrl = db.Column('link', db.Text)
    stars = db.Column('rating', db.String(50))
    reviews = db.Column('Number_of_ratings', db.String(50))
    price = db.Column('price', db.String(100))
    listPrice = db.Column('listPrice', db.String(100), nullable=True)
    categoryName = db.Column('category', db.String(255))
    brand = db.Column('Brand', db.String(255))
    description = db.Column('description', db.Text)
    category_id = db.Column(db.Integer, db.ForeignKey('dmart_categories.category_id', ondelete='SET NULL'), nullable=True)
    quantity = db.Column('quantity', db.String(100), nullable=True)

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
            "asin": self.asin,
            "name": self.title,
            "price": self.price,
            "list_price": self.listPrice,
            "stars": self.stars,
            "reviews": self.reviews,
            "category": self.categoryName,
            "category_id": self.category_id,
            "quantity": self.quantity,
            "link": self.productUrl
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
    __tablename__ = 'india_mart'
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
