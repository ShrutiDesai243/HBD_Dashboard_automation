from sqlalchemy import Column, Integer, String, Text, TIMESTAMP, func
from extensions import db

class DataCleaningLog(db.Model):
    __tablename__ = "data_cleaning_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(50), index=True, nullable=False)
    run_type = Column(String(20), nullable=False) # 'dry-run', 'apply', 'rollback'
    status = Column(String(20), nullable=False, default='running') # 'running', 'completed', 'failed'
    table_name = Column(String(100), nullable=False) # 'master_table', 'product_master', 'all'
    backup_table_name = Column(String(100), nullable=True)
    
    total_rows = Column(Integer, default=0)
    cleaned_rows = Column(Integer, default=0)
    duplicate_rows = Column(Integer, default=0)
    missing_location_rows = Column(Integer, default=0)
    invalid_phone_email_rows = Column(Integer, default=0)
    unmatched_location_rows = Column(Integer, default=0)
    wrong_category_rows = Column(Integer, default=0)
    
    error_message = Column(Text, nullable=True)
    details = Column(Text, nullable=True) # JSON format string
    created_at = Column(TIMESTAMP, server_default=func.now())
    completed_at = Column(TIMESTAMP, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "run_id": self.run_id,
            "run_type": self.run_type,
            "status": self.status,
            "table_name": self.table_name,
            "backup_table_name": self.backup_table_name,
            "total_rows": self.total_rows or 0,
            "cleaned_rows": self.cleaned_rows or 0,
            "duplicate_rows": self.duplicate_rows or 0,
            "missing_location_rows": self.missing_location_rows or 0,
            "invalid_phone_email_rows": self.invalid_phone_email_rows or 0,
            "unmatched_location_rows": self.unmatched_location_rows or 0,
            "wrong_category_rows": self.wrong_category_rows or 0,
            "error_message": self.error_message,
            "details": self.details,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None
        }
