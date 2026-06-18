from sqlalchemy import Column, Integer, String, Text, TIMESTAMP, func, ForeignKey
from extensions import db

class UnmatchedDataReview(db.Model):
    __tablename__ = "unmatched_data_review"

    review_id = Column(Integer, primary_key=True, autoincrement=True)
    data_type = Column(String(50), index=True) # enum('city','state','area','category')
    invalid_value = Column(String(255))
    correction_status = Column(String(20), index=True, default='pending') # enum('pending','corrected')
    created_at = Column(TIMESTAMP, server_default=func.now())
    
    # Context columns for safe cleaning process
    table_name = Column(String(100), nullable=True)
    row_id = Column(Integer, nullable=True)
    row_data = Column(Text, nullable=True)

    def to_dict(self):
        return {
            "review_id": self.review_id,
            "data_type": self.data_type,
            "invalid_value": self.invalid_value,
            "correction_status": self.correction_status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "table_name": self.table_name,
            "row_id": self.row_id,
            "row_data": self.row_data,
        }
