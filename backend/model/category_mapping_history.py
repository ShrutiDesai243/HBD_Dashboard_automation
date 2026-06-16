from extensions import db
from datetime import datetime


class CategoryMappingHistory(db.Model):
    """
    Audit trail table — records every change made to category mappings.
    Follows the strict no-deletion policy: rows are only inserted, never
    updated or deleted.

    Captures:
      - Which mapping was changed
      - What the old and new master_category_id were
      - What action was performed (CREATED, MAPPED, REMAPPED, DEACTIVATED, etc.)
      - When it happened
      - Who did it (user info, if available)
    """
    __tablename__ = 'category_mapping_history'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    mapping_id = db.Column(
        db.Integer,
        db.ForeignKey('platform_category_mapping.id', ondelete='RESTRICT'),
        nullable=True,
        index=True,
        comment='FK to the platform_category_mapping row that was changed'
    )
    master_category_id = db.Column(
        db.Integer,
        db.ForeignKey('master_categories.id', ondelete='RESTRICT'),
        nullable=True,
        comment='FK if the change was on a master category directly'
    )
    action = db.Column(
        db.String(50), nullable=False,
        comment='CREATED | MAPPED | REMAPPED | APPROVED | DEACTIVATED | REACTIVATED | RENAMED'
    )
    old_value = db.Column(
        db.String(500), nullable=True,
        comment='Previous state (e.g. old master_category_id or old name)'
    )
    new_value = db.Column(
        db.String(500), nullable=True,
        comment='New state after the change'
    )
    changed_by = db.Column(
        db.String(100), nullable=True, default='system',
        comment='Username or "system" for automated changes'
    )
    notes = db.Column(
        db.Text, nullable=True,
        comment='Optional free-text explanation of the change'
    )
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # ---- Relationships ----
    mapping = db.relationship(
        'PlatformCategoryMapping',
        backref=db.backref('history', lazy='dynamic', order_by='CategoryMappingHistory.created_at.desc()')
    )

    # ---- Table config ----
    __table_args__ = (
        {'mysql_charset': 'utf8mb4', 'mysql_collate': 'utf8mb4_unicode_ci'},
    )

    def to_dict(self):
        return {
            'id': self.id,
            'mapping_id': self.mapping_id,
            'master_category_id': self.master_category_id,
            'action': self.action,
            'old_value': self.old_value,
            'new_value': self.new_value,
            'changed_by': self.changed_by,
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f'<CategoryMappingHistory {self.id}: {self.action} on mapping {self.mapping_id}>'
