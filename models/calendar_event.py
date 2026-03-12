from datetime import datetime

from models import db


class CalendarEvent(db.Model):
    __tablename__ = 'calendar_events'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    group_id = db.Column(db.Integer, db.ForeignKey('groups.id'), nullable=True)
    event_type = db.Column(db.String(20), default='call')  # call, meeting
    scheduled_at = db.Column(db.DateTime, nullable=False)
    duration_minutes = db.Column(db.Integer, default=30)
    reminder_minutes = db.Column(db.Integer, default=15)  # minutes before event
    is_recurring = db.Column(db.Boolean, default=False)
    recurrence_rule = db.Column(db.String(100), nullable=True)  # daily, weekly, monthly
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    user = db.relationship('User', backref='calendar_events')
    participants = db.relationship('EventParticipant', backref='event', lazy='dynamic', cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'user_id': self.user_id,
            'group_id': self.group_id,
            'event_type': self.event_type,
            'scheduled_at': self.scheduled_at.isoformat(),
            'duration_minutes': self.duration_minutes,
            'reminder_minutes': self.reminder_minutes,
            'is_recurring': self.is_recurring,
            'recurrence_rule': self.recurrence_rule,
            'participants': [p.to_dict() for p in self.participants.all()],
            'created_at': self.created_at.isoformat(),
        }


class EventParticipant(db.Model):
    __tablename__ = 'event_participants'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    event_id = db.Column(db.Integer, db.ForeignKey('calendar_events.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    status = db.Column(db.String(20), default='pending')  # pending, accepted, declined

    user = db.relationship('User')

    __table_args__ = (
        db.UniqueConstraint('event_id', 'user_id', name='uq_event_user'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'event_id': self.event_id,
            'user_id': self.user_id,
            'status': self.status,
            'user': self.user.to_dict() if self.user else None,
        }
