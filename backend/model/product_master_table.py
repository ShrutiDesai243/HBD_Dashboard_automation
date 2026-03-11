from sqlalchemy import Column, Integer, String, Float, Text, DateTime, func
from extensions import db

class ProductMaster(db.Model):
    __tablename__ = "product_master_table"  # Ensure this matches your DB table name

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String(50), nullable=True)
    business_name = Column(String(255), nullable=True)
    category = Column(String(255), nullable=True)
    sub_category = Column(String(255), nullable=True)
    owner_name = Column(String(255), nullable=True)
    mobile = Column(String(50), nullable=True)
    phone = Column(String(50), nullable=True)
    email = Column(String(150), nullable=True)
    website = Column(String(255), nullable=True)
    address = Column(Text, nullable=True)
    city = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    pincode = Column(String(20), nullable=True)
    area = Column(String(100), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    rating = Column(Float, nullable=True)
    review_count = Column(Integer, nullable=True)
    listing_url = Column(Text, nullable=True)
    image_url = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def to_dict(self):
        """Converts SQLAlchemy object to JSON-ready dictionary"""
        data = {c.name: getattr(self, c.name) for c in self.__table__.columns}
        # Format dates for JSON
        if self.created_at:
            data['created_at'] = self.created_at.isoformat()
        if self.updated_at:
            data['updated_at'] = self.updated_at.isoformat()
        return data