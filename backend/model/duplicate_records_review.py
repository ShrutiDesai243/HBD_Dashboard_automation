from sqlalchemy import Column, Integer, String, Text, TIMESTAMP, func
from extensions import db

class DuplicateRecordsReview(db.Model):
    __tablename__ = "duplicate_records_review"

    id = Column(Integer, primary_key=True, autoincrement=True)
    table_name = Column(String(100), nullable=False) # 'master_table', 'product_master'
    duplicate_key = Column(String(500), index=True, nullable=False) # deduplication criteria key
    original_id = Column(Integer, nullable=False)
    duplicate_id = Column(Integer, nullable=False)
    record_data = Column(Text, nullable=False) # JSON format of the row
    created_at = Column(TIMESTAMP, server_default=func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "table_name": self.table_name,
            "duplicate_key": self.duplicate_key,
            "original_id": self.original_id,
            "duplicate_id": self.duplicate_id,
            "record_data": self.record_data,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
