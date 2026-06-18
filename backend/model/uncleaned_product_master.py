from sqlalchemy import Column, Integer, String, Float, Text, DateTime, func
from extensions import db

class UncleanedProductMaster(db.Model):
    __tablename__ = "uncleaned_product_master_table"

    id = Column(Integer, primary_key=True, autoincrement=True)
    marketplace_name = Column(String(100), nullable=True)
    asin = Column(String(100), nullable=True)
    product_name = Column(Text, nullable=True)
    brand = Column(String(255), nullable=True)
    category_name = Column(String(255), nullable=True)
    sub_category_name = Column(String(255), nullable=True)
    price = Column(String(100), nullable=True)
    list_price = Column(String(100), nullable=True)
    product_category_id = Column(Integer, nullable=True)
    reason = Column(String(255), nullable=True)
    product_url = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "product_id": self.id,
            "marketplace_name": self.marketplace_name,
            "asin": self.asin,
            "product_name": self.product_name,
            "brand": self.brand,
            "category_name": self.category_name,
            "sub_category_name": self.sub_category_name,
            "price": self.price,
            "list_price": self.list_price,
            "product_category_id": self.product_category_id,
            "reason": self.reason,
            "product_url": self.product_url,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
