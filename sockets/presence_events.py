from datetime import datetime

from flask import request
from flask_socketio import emit, join_room

from models import db
from models.user import User

# In-memory user session tracking
# Maps socket SID to user_id
sid_to_user = {}
# Maps user_id to socket SID
user_to_sid = {}


def get_user_sid(user_id):
    """Get the socket SID for a given user_id (int)."""
    return user_to_sid.get(int(user_id) if user_id is not None else None)


def get_sid_user(sid):
    """Get the user_id for a given socket SID."""
    return sid_to_user.get(sid)


def register_presence_events(socketio):

    @socketio.on('connect')
    def handle_connect():
        print(f'[SOCKET] Client connected: {request.sid}', flush=True)

    @socketio.on('disconnect')
    def handle_disconnect():
        sid = request.sid
        user_id = sid_to_user.pop(sid, None)
        print(f'[SOCKET] Client disconnected: sid={sid} user_id={user_id}', flush=True)
        if user_id:
            user_to_sid.pop(user_id, None)

            # Clean up any active calls
            from sockets.call_events import active_calls
            partner_id = active_calls.pop(user_id, None)
            if partner_id:
                active_calls.pop(partner_id, None)
                partner_sid = get_user_sid(partner_id)
                if partner_sid:
                    emit('call_ended', {
                        'from_id': user_id,
                        'reason': 'disconnected',
                    }, room=partner_sid)

            # Update user status
            user = db.session.get(User, user_id)
            if user:
                user.status = 'offline'
                user.last_seen = datetime.utcnow()
                db.session.commit()

                # Notify all clients
                emit('user_status_changed', {
                    'user_id': user_id,
                    'status': 'offline',
                    'username': user.username,
                }, broadcast=True)

            print(f'[SOCKET] User disconnected: {user_id}', flush=True)

    @socketio.on('authenticate')
    def handle_authenticate(data):
        """Authenticate socket connection with JWT token."""
        from flask_jwt_extended import decode_token
        token = data.get('token')
        if not token:
            emit('auth_error', {'error': 'Token required'})
            return

        try:
            decoded = decode_token(token)
            user_id = int(decoded['sub'])
        except Exception:
            emit('auth_error', {'error': 'Invalid token'})
            return

        user = db.session.get(User, user_id)
        if not user:
            emit('auth_error', {'error': 'User not found'})
            return

        # Clean up old session for this user (handles reconnection)
        old_sid = user_to_sid.get(user_id)
        if old_sid and old_sid != request.sid:
            sid_to_user.pop(old_sid, None)

        # Register session
        sid_to_user[request.sid] = user_id
        user_to_sid[user_id] = request.sid

        # Join personal room
        join_room(f'user_{user_id}')

        # Update status
        user.status = 'online'
        db.session.commit()

        # Get online users
        online_user_ids = list(user_to_sid.keys())
        online_users = User.query.filter(User.id.in_(online_user_ids)).all() if online_user_ids else []

        emit('authenticated', {
            'user': user.to_dict(),
            'online_users': [u.to_dict() for u in online_users],
        })

        # Notify others
        emit('user_status_changed', {
            'user_id': user_id,
            'status': 'online',
            'username': user.username,
        }, broadcast=True, include_self=False)

        print(f'[SOCKET] User authenticated: {user.username} (ID: {user_id})', flush=True)

    @socketio.on('get_online_users')
    def handle_get_online_users():
        online_user_ids = list(user_to_sid.keys())
        online_users = User.query.filter(User.id.in_(online_user_ids)).all() if online_user_ids else []
        emit('online_users', {
            'users': [u.to_dict() for u in online_users],
        })

    @socketio.on('heartbeat')
    def handle_heartbeat():
        """Client-side heartbeat for keeping socket session alive."""
        sid = request.sid
        user_id = sid_to_user.get(sid)
        if user_id:
            emit('heartbeat_ack', {'status': 'ok', 'user_id': user_id})
