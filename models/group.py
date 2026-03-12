from datetime import datetime

from models import db


class Group(db.Model):
    __tablename__ = 'groups'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(500), nullable=True)
    avatar_url = db.Column(db.String(255), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    creator = db.relationship('User', backref='created_groups')
    members = db.relationship('GroupMember', backref='group', lazy='dynamic', cascade='all, delete-orphan')
    messages = db.relationship('Message', backref='group', lazy='dynamic')

    def to_dict(self, include_members=False):
        data = {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'avatar_url': self.avatar_url,
            'created_by': self.created_by,
            'creator': self.creator.to_dict() if self.creator else None,
            'member_count': self.members.count(),
            'created_at': self.created_at.isoformat(),
        }
        if include_members:
            data['members'] = [m.to_dict() for m in self.members.all()]
        return data


class GroupMember(db.Model):
    __tablename__ = 'group_members'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    group_id = db.Column(db.Integer, db.ForeignKey('groups.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    role = db.Column(db.String(20), default='member')  # admin, member
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('group_id', 'user_id', name='uq_group_user'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'group_id': self.group_id,
            'user_id': self.user_id,
            'role': self.role,
            'user': self.user.to_dict() if self.user else None,
            'joined_at': self.joined_at.isoformat(),
        }
