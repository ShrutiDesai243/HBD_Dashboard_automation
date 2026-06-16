from extensions import db
from datetime import datetime


class CategoryMappingSynonym(db.Model):
    """
    Configures spelling normalizations and synonym mappings for the auto-mapper engine.
    Enables admins to define rules like 'fruits and vegetables' -> 'Fruits & Vegetables'
    entirely from the React dashboard settings.
    """
    __tablename__ = 'category_mapping_synonyms'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    raw_value = db.Column(
        db.String(255), unique=True, nullable=False, index=True,
        comment='Normalized raw category string'
    )
    canonical_value = db.Column(
        db.String(255), nullable=False,
        comment='Canonical master category target name'
    )
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        {'mysql_charset': 'utf8mb4', 'mysql_collate': 'utf8mb4_unicode_ci'},
    )

    def to_dict(self):
        return {
            'id': self.id,
            'raw_value': self.raw_value,
            'canonical_value': self.canonical_value,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f'<CategoryMappingSynonym "{self.raw_value}" -> "{self.canonical_value}">'
