from flask import request
from flask_socketio import emit

from models import db
from models.user import User
from sockets.presence_events import get_user_sid, get_sid_user


# In-memory active call tracking: user_id -> partner_user_id
active_calls = {}


def _get_user_info(user_id):
    """Look up user display info for signaling payloads."""
    user = db.session.get(User, user_id)
    if user:
        return {'id': user.id, 'display_name': user.display_name, 'username': user.username}
    return {'id': user_id, 'display_name': f'User #{user_id}', 'username': 'unknown'}


def register_call_events(socketio):

    @socketio.on('call_user')
    def handle_call_user(data):
        caller_id = get_sid_user(request.sid)
        from sockets.presence_events import user_to_sid, sid_to_user
        print(f'[CALL] call_user received: sid={request.sid} caller_id={caller_id} target_id={data.get("target_id")} (type={type(data.get("target_id")).__name__})', flush=True)
        print(f'[CALL] user_to_sid state: {user_to_sid}', flush=True)
        print(f'[CALL] sid_to_user state: {sid_to_user}', flush=True)
        if not caller_id:
            print('[CALL] ERROR: caller not authenticated', flush=True)
            emit('call_error', {'error': 'Not authenticated'})
            return

        target_id = data.get('target_id')
        if isinstance(target_id, str):
            target_id = int(target_id)

        target_sid = get_user_sid(target_id)
        print(f'[CALL] target_sid for {target_id}: {target_sid}', flush=True)

        if not target_sid:
            target_info = _get_user_info(target_id)
            print(f'[CALL] target {target_id} is offline, sending call_error', flush=True)
            emit('call_error', {'error': f'{target_info["display_name"]} is currently offline and cannot receive calls.'})
            return

        # Check if target is already in a call
        if target_id in active_calls:
            target_info = _get_user_info(target_id)
            print(f'[CALL] target {target_id} is busy', flush=True)
            emit('call_error', {'error': f'{target_info["display_name"]} is currently on another call. Try again later.'})
            return

        # Track the pending call
        active_calls[caller_id] = target_id

        caller_info = _get_user_info(caller_id)
        print(f'[CALL] Emitting incoming_call to {target_sid} (user {target_id})', flush=True)

        emit('incoming_call', {
            'caller_id': caller_id,
            'caller': caller_info,
            'call_type': data.get('call_type', 'voice'),
            'offer': data.get('offer'),
            'call_id': data.get('call_id'),
        }, room=target_sid)

    @socketio.on('call_accepted')
    def handle_call_accepted(data):
        callee_id = get_sid_user(request.sid)
        if not callee_id:
            return

        caller_id = data.get('caller_id')
        if isinstance(caller_id, str):
            caller_id = int(caller_id)

        caller_sid = get_user_sid(caller_id)

        # Track both sides as in active call
        active_calls[callee_id] = caller_id
        active_calls[caller_id] = callee_id

        callee_info = _get_user_info(callee_id)

        if caller_sid:
            emit('call_accepted', {
                'callee_id': callee_id,
                'callee': callee_info,
                'answer': data.get('answer'),
                'call_id': data.get('call_id'),
            }, room=caller_sid)

    @socketio.on('call_rejected')
    def handle_call_rejected(data):
        user_id = get_sid_user(request.sid)
        if not user_id:
            return

        caller_id = data.get('caller_id')
        if isinstance(caller_id, str):
            caller_id = int(caller_id)

        caller_sid = get_user_sid(caller_id)

        # Clear call tracking
        active_calls.pop(caller_id, None)
        active_calls.pop(user_id, None)

        if caller_sid:
            emit('call_rejected', {
                'from_id': user_id,
                'call_id': data.get('call_id'),
            }, room=caller_sid)

    @socketio.on('ice_candidate')
    def handle_ice_candidate(data):
        user_id = get_sid_user(request.sid)
        if not user_id:
            return

        target_id = data.get('target_id')
        if isinstance(target_id, str):
            target_id = int(target_id)

        target_sid = get_user_sid(target_id)

        if target_sid:
            emit('ice_candidate', {
                'candidate': data.get('candidate'),
                'from_id': user_id,
            }, room=target_sid)

    @socketio.on('end_call')
    def handle_end_call(data):
        user_id = get_sid_user(request.sid)
        if not user_id:
            return

        target_id = data.get('target_id')
        if isinstance(target_id, str):
            target_id = int(target_id)

        # Clear call tracking for both sides
        active_calls.pop(user_id, None)
        active_calls.pop(target_id, None)

        target_sid = get_user_sid(target_id)
        if target_sid:
            emit('call_ended', {
                'from_id': user_id,
                'call_id': data.get('call_id'),
            }, room=target_sid)

    # Screen sharing signaling
    @socketio.on('screen_share_started')
    def handle_screen_share_started(data):
        user_id = get_sid_user(request.sid)
        if not user_id:
            return

        target_id = data.get('target_id')
        if isinstance(target_id, str):
            target_id = int(target_id)
        target_sid = get_user_sid(target_id)

        if target_sid:
            emit('screen_share_started', {
                'from_id': user_id,
            }, room=target_sid)

    @socketio.on('screen_share_stopped')
    def handle_screen_share_stopped(data):
        user_id = get_sid_user(request.sid)
        if not user_id:
            return

        target_id = data.get('target_id')
        if isinstance(target_id, str):
            target_id = int(target_id)
        target_sid = get_user_sid(target_id)

        if target_sid:
            emit('screen_share_stopped', {
                'from_id': user_id,
            }, room=target_sid)

    # Renegotiation support (for adding/removing video mid-call)
    @socketio.on('renegotiate_offer')
    def handle_renegotiate_offer(data):
        user_id = get_sid_user(request.sid)
        if not user_id:
            return

        target_id = data.get('target_id')
        if isinstance(target_id, str):
            target_id = int(target_id)
        target_sid = get_user_sid(target_id)

        if target_sid:
            emit('renegotiate_offer', {
                'from_id': user_id,
                'offer': data.get('offer'),
            }, room=target_sid)

    @socketio.on('renegotiate_answer')
    def handle_renegotiate_answer(data):
        user_id = get_sid_user(request.sid)
        if not user_id:
            return

        target_id = data.get('target_id')
        if isinstance(target_id, str):
            target_id = int(target_id)
        target_sid = get_user_sid(target_id)

        if target_sid:
            emit('renegotiate_answer', {
                'from_id': user_id,
                'answer': data.get('answer'),
            }, room=target_sid)

    # Group call signaling
    @socketio.on('group_call_initiate')
    def handle_group_call(data):
        caller_id = get_sid_user(request.sid)
        if not caller_id:
            return

        caller_info = _get_user_info(caller_id)
        participant_ids = data.get('participant_ids', [])
        for pid in participant_ids:
            if isinstance(pid, str):
                pid = int(pid)
            target_sid = get_user_sid(pid)
            if target_sid:
                emit('group_call_invite', {
                    'caller_id': caller_id,
                    'caller': caller_info,
                    'group_id': data.get('group_id'),
                    'call_type': data.get('call_type', 'voice'),
                    'participants': participant_ids,
                }, room=target_sid)

    @socketio.on('group_call_join')
    def handle_group_call_join(data):
        user_id = get_sid_user(request.sid)
        if not user_id:
            return

        user_info = _get_user_info(user_id)
        participant_ids = data.get('participant_ids', [])
        for pid in participant_ids:
            if isinstance(pid, str):
                pid = int(pid)
            if pid != user_id:
                target_sid = get_user_sid(pid)
                if target_sid:
                    emit('group_call_peer_joined', {
                        'user_id': user_id,
                        'user': user_info,
                        'offer': data.get('offer'),
                    }, room=target_sid)
