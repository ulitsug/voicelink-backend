from datetime import datetime

from flask import Blueprint, jsonify, request

from models import db
from models.calendar_event import CalendarEvent, EventParticipant
from utils.auth import jwt_required_with_user

calendar_bp = Blueprint('calendar', __name__, url_prefix='/api/calendar')


@calendar_bp.route('/events', methods=['GET'])
@jwt_required_with_user
def get_events(user):
    # Get events where user is creator or participant
    own_events = CalendarEvent.query.filter_by(user_id=user.id).all()
    participant_event_ids = [
        ep.event_id for ep in
        EventParticipant.query.filter_by(user_id=user.id).all()
    ]
    participant_events = CalendarEvent.query.filter(
        CalendarEvent.id.in_(participant_event_ids)
    ).all() if participant_event_ids else []

    all_events = {e.id: e for e in own_events + participant_events}
    return jsonify({'events': [e.to_dict() for e in all_events.values()]})


@calendar_bp.route('/events', methods=['POST'])
@jwt_required_with_user
def create_event(user):
    data = request.get_json()
    title = data.get('title', '').strip()
    scheduled_at = data.get('scheduled_at')

    if not title or not scheduled_at:
        return jsonify({'error': 'Title and scheduled_at are required'}), 400

    try:
        scheduled_dt = datetime.fromisoformat(scheduled_at)
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid date format. Use ISO format.'}), 400

    event = CalendarEvent(
        title=title,
        description=data.get('description', '').strip(),
        user_id=user.id,
        group_id=data.get('group_id'),
        event_type=data.get('event_type', 'call'),
        scheduled_at=scheduled_dt,
        duration_minutes=data.get('duration_minutes', 30),
        reminder_minutes=data.get('reminder_minutes', 15),
        is_recurring=data.get('is_recurring', False),
        recurrence_rule=data.get('recurrence_rule'),
    )
    db.session.add(event)
    db.session.flush()

    # Add participants
    participant_ids = data.get('participant_ids', [])
    for pid in participant_ids:
        participant = EventParticipant(event_id=event.id, user_id=pid)
        db.session.add(participant)

    db.session.commit()
    return jsonify({'event': event.to_dict()}), 201


@calendar_bp.route('/events/<int:event_id>', methods=['PUT'])
@jwt_required_with_user
def update_event(user, event_id):
    event = db.session.get(CalendarEvent, event_id)
    if not event:
        return jsonify({'error': 'Event not found'}), 404

    if event.user_id != user.id:
        return jsonify({'error': 'Only the creator can update the event'}), 403

    data = request.get_json()
    if data.get('title'):
        event.title = data['title'].strip()
    if 'description' in data:
        event.description = data['description'].strip()
    if data.get('scheduled_at'):
        try:
            event.scheduled_at = datetime.fromisoformat(data['scheduled_at'])
        except (ValueError, TypeError):
            return jsonify({'error': 'Invalid date format'}), 400
    if data.get('duration_minutes'):
        event.duration_minutes = data['duration_minutes']
    if data.get('reminder_minutes') is not None:
        event.reminder_minutes = data['reminder_minutes']

    db.session.commit()
    return jsonify({'event': event.to_dict()})


@calendar_bp.route('/events/<int:event_id>', methods=['DELETE'])
@jwt_required_with_user
def delete_event(user, event_id):
    event = db.session.get(CalendarEvent, event_id)
    if not event:
        return jsonify({'error': 'Event not found'}), 404

    if event.user_id != user.id:
        return jsonify({'error': 'Only the creator can delete the event'}), 403

    db.session.delete(event)
    db.session.commit()
    return jsonify({'message': 'Event deleted'})


@calendar_bp.route('/events/<int:event_id>/respond', methods=['PUT'])
@jwt_required_with_user
def respond_to_event(user, event_id):
    participant = EventParticipant.query.filter_by(
        event_id=event_id, user_id=user.id
    ).first()

    if not participant:
        return jsonify({'error': 'Not invited to this event'}), 404

    data = request.get_json()
    status = data.get('status')
    if status not in ('accepted', 'declined'):
        return jsonify({'error': 'Status must be accepted or declined'}), 400

    participant.status = status
    db.session.commit()
    return jsonify({'message': f'Event {status}'})
