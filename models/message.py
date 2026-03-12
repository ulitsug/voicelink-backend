from datetime import datetime

from models import db


class Message(db.Model):
    __tablename__ = 'messages'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    receiver_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    group_id = db.Column(db.Integer, db.ForeignKey('groups.id'), nullable=True, index=True)
    content = db.Column(db.Text, nullable=True)
    encrypted_content = db.Column(db.Text, nullable=True)  # E2E encrypted content
    message_type = db.Column(db.String(20), default='text')  # text, file, image, system
    file_url = db.Column(db.String(500), nullable=True)
    file_name = db.Column(db.String(255), nullable=True)
    file_size = db.Column(db.Integer, nullable=True)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def to_dict(self):
        return {
            'id': self.id,
            'sender_id': self.sender_id,
            'receiver_id': self.receiver_id,
            'group_id': self.group_id,
            'content': self.content,
            'message_type': self.message_type,
            'file_url': self.file_url,
            'file_name': self.file_name,
            'file_size': self.file_size,
            'is_read': self.is_read,
            'sender': self.sender.to_dict() if self.sender else None,
            'created_at': self.created_at.isoformat(),
        }
