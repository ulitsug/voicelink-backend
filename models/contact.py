from datetime import datetime

from models import db


class Contact(db.Model):
    __tablename__ = 'contacts'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    nickname = db.Column(db.String(100), nullable=True)
    is_blocked = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    user = db.relationship('User', foreign_keys=[user_id], backref=db.backref('contacts_list', lazy='dynamic'))
    contact = db.relationship('User', foreign_keys=[contact_id])

    __table_args__ = (
        db.UniqueConstraint('user_id', 'contact_id', name='uq_user_contact'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'contact_id': self.contact_id,
            'nickname': self.nickname,
            'is_blocked': self.is_blocked,
            'contact': self.contact.to_dict() if self.contact else None,
            'created_at': self.created_at.isoformat(),
        }
