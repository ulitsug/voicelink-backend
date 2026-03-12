from datetime import datetime

from models import db


class CallLog(db.Model):
    __tablename__ = 'call_logs'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    caller_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    callee_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    group_id = db.Column(db.Integer, db.ForeignKey('groups.id'), nullable=True, index=True)
    call_type = db.Column(db.String(20), nullable=False)  # voice, video, screen_share
    status = db.Column(db.String(20), default='initiated')  # initiated, ringing, active, ended, missed, rejected
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    answered_at = db.Column(db.DateTime, nullable=True)
    ended_at = db.Column(db.DateTime, nullable=True)
    duration = db.Column(db.Integer, default=0)  # in seconds

    def to_dict(self):
        return {
            'id': self.id,
            'caller_id': self.caller_id,
            'callee_id': self.callee_id,
            'group_id': self.group_id,
            'call_type': self.call_type,
            'status': self.status,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'answered_at': self.answered_at.isoformat() if self.answered_at else None,
            'ended_at': self.ended_at.isoformat() if self.ended_at else None,
            'duration': self.duration,
            'caller': self.caller.to_dict() if self.caller else None,
            'callee': self.callee.to_dict() if self.callee else None,
        }
