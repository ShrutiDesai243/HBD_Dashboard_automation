from extensions import db
from datetime import datetime


class CategoryMappingPlatform(db.Model):
    """
    Configures which tables and SQL queries the sync service scans for categories.
    Enables admins to dynamically add, edit, or deactivate platform sync configurations
    directly from the frontend UI.
    """
    __tablename__ = 'category_mapping_platforms'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    platform_name = db.Column(
        db.String(100), unique=True, nullable=False, index=True,
        comment='e.g. BigBasket, Blinkit, Zepto, DMart, Dunzo'
    )
    query_sql = db.Column(
        db.Text, nullable=False,
        comment='SQL query returning (category, subcategory) fields'
    )
    is_active = db.Column(
        db.Boolean, nullable=False, default=True,
        comment='Soft-delete configuration flag'
    )
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    __table_args__ = (
        {'mysql_charset': 'utf8mb4', 'mysql_collate': 'utf8mb4_unicode_ci'},
    )

    def to_dict(self):
        return {
            'id': self.id,
            'platform_name': self.platform_name,
            'query_sql': self.query_sql,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f'<CategoryMappingPlatform {self.platform_name}>'
