from extensions import db
from datetime import datetime


class PlatformCategoryMapping(db.Model):
    """
    Unified bridge table that connects raw scraped category strings from
    each marketplace platform to the central master_categories tree.

    Design principles:
      - Each raw (platform_name + category + subcategory) combo maps to
        exactly one master_category_id via FK.
      - UNIQUE constraint on (platform, raw_cat, raw_subcat) prevents
        duplicate mapping rows.
      - mapping_status tracks the lifecycle:
        PENDING  → freshly discovered, not yet mapped
        AUTO_MAPPED → matched by the predefined auto-mapper logic
        MANUALLY_MAPPED → confirmed / overridden by an admin
        UNMAPPED → explicitly marked as "no match available"
      - is_active flag for soft-delete (no physical deletes ever).
    """
    __tablename__ = 'platform_category_mapping'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    platform_name = db.Column(
        db.String(100), nullable=False, index=True,
        comment='e.g. BigBasket, Blinkit, Zepto, DMart, IndiaMart, Amazon'
    )
    platform_category_raw = db.Column(
        db.String(255), nullable=False,
        comment='Category string exactly as scraped from the platform'
    )
    platform_subcategory_raw = db.Column(
        db.String(255), nullable=True, default='',
        comment='Subcategory string exactly as scraped (nullable)'
    )
    master_category_id = db.Column(
        db.Integer,
        db.ForeignKey('master_categories.id', ondelete='RESTRICT'),
        nullable=True,
        index=True,
        comment='NULL means mapping is pending'
    )
    mapping_status = db.Column(
        db.String(30), nullable=False, default='PENDING',
        comment='PENDING | AUTO_MAPPED | MANUALLY_MAPPED | UNMAPPED'
    )
    confidence_score = db.Column(
        db.Float, default=0.0,
        comment='Match confidence from auto-mapper (0.0–1.0)'
    )
    is_active = db.Column(
        db.Boolean, nullable=False, default=True,
        comment='Soft-delete flag'
    )
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # ---- Relationships ----
    master_category = db.relationship(
        'MasterCategory',
        backref=db.backref('platform_mappings', lazy='dynamic')
    )

    # ---- Constraints ----
    __table_args__ = (
        db.UniqueConstraint(
            'platform_name', 'platform_category_raw', 'platform_subcategory_raw',
            name='uq_platform_raw_category'
        ),
        db.Index('idx_mapping_status_active', 'mapping_status', 'is_active'),
        {'mysql_charset': 'utf8mb4', 'mysql_collate': 'utf8mb4_unicode_ci'}
    )

    def to_dict(self):
        return {
            'id': self.id,
            'platform_name': self.platform_name,
            'platform_category_raw': self.platform_category_raw,
            'platform_subcategory_raw': self.platform_subcategory_raw or '',
            'master_category_id': self.master_category_id,
            'master_category_name': (
                self.master_category.name if self.master_category else None
            ),
            'master_category_path': (
                self.master_category.path if self.master_category else None
            ),
            'mapping_status': self.mapping_status,
            'confidence_score': self.confidence_score,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return (
            f'<PlatformCategoryMapping {self.platform_name}:'
            f' "{self.platform_category_raw}" → {self.master_category_id}>'
        )
