from datetime import datetime

import bcrypt

from models import db


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(50), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    display_name = db.Column(db.String(100), nullable=False)
    bio = db.Column(db.String(250), nullable=True)
    avatar_url = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(20), default='offline')  # online, offline, busy, away
    public_key = db.Column(db.Text, nullable=True)  # For E2E encryption
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    sent_messages = db.relationship('Message', foreign_keys='Message.sender_id', backref='sender', lazy='dynamic')
    received_messages = db.relationship('Message', foreign_keys='Message.receiver_id', backref='receiver', lazy='dynamic')
    call_logs_as_caller = db.relationship('CallLog', foreign_keys='CallLog.caller_id', backref='caller', lazy='dynamic')
    call_logs_as_callee = db.relationship('CallLog', foreign_keys='CallLog.callee_id', backref='callee', lazy='dynamic')
    group_memberships = db.relationship('GroupMember', backref='user', lazy='dynamic')

    def set_password(self, password):
        self.password_hash = bcrypt.hashpw(
            password.encode('utf-8'), bcrypt.gensalt()
        ).decode('utf-8')

    def check_password(self, password):
        return bcrypt.checkpw(
            password.encode('utf-8'),
            self.password_hash.encode('utf-8')
        )

    def to_dict(self, include_email=False):
        data = {
            'id': self.id,
            'username': self.username,
            'display_name': self.display_name,
            'bio': self.bio,
            'avatar_url': self.avatar_url,
            'status': self.status,
            'last_seen': self.last_seen.isoformat() if self.last_seen else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
        if include_email:
            data['email'] = self.email
        return data
