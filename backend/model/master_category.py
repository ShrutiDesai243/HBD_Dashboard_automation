from extensions import db
from datetime import datetime


class MasterCategory(db.Model):
    """
    Central master categories table — the single source of truth for all
    product/delivery categories across every marketplace platform.

    Design principles:
      - Auto-increment integer PK for performance
      - Self-referencing parent_id for hierarchy (Level 1 → 2 → 3 …)
      - Materialized `path` column avoids recursive queries
      - `is_active` flag enforces strict no-deletion policy
      - UNIQUE(parent_id, name) prevents duplicate children under the same parent
    """
    __tablename__ = 'master_categories'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(255), nullable=False, index=True)
    parent_id = db.Column(
        db.Integer,
        db.ForeignKey('master_categories.id', ondelete='RESTRICT'),
        nullable=True,
        index=True
    )
    level = db.Column(
        db.Integer, nullable=False, default=1,
        comment='1 = Main Category, 2 = Sub, 3 = Child, …'
    )
    path = db.Column(
        db.String(512), nullable=False, default='',
        comment='Materialized path e.g. "Groceries > Dairy > Milk"'
    )
    is_active = db.Column(
        db.Boolean, nullable=False, default=True,
        comment='Soft-delete flag — never physically delete rows'
    )
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # ---- Relationships ----
    parent = db.relationship(
        'MasterCategory', remote_side=[id],
        backref=db.backref('children', lazy='dynamic'),
        foreign_keys=[parent_id]
    )

    # ---- Constraints ----
    __table_args__ = (
        db.UniqueConstraint('parent_id', 'name', name='uq_parent_name'),
        {'mysql_charset': 'utf8mb4', 'mysql_collate': 'utf8mb4_unicode_ci'}
    )

    # ---- Helpers ----

    def compute_path(self):
        """Rebuild the materialized path by walking up the parent chain."""
        parts = [self.name]
        current = self
        # Safety limit to prevent infinite loops on bad data
        for _ in range(10):
            if current.parent_id is None or current.parent is None:
                break
            current = current.parent
            parts.insert(0, current.name)
        return ' > '.join(parts)

    def to_dict(self, include_children=False):
        data = {
            'id': self.id,
            'name': self.name,
            'parent_id': self.parent_id,
            'level': self.level,
            'path': self.path,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_children:
            data['children'] = [
                c.to_dict(include_children=True)
                for c in self.children.filter_by(is_active=True).order_by(MasterCategory.name)
            ]
        return data

    def __repr__(self):
        return f'<MasterCategory {self.id}: {self.path}>'
