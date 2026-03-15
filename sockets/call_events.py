import time
import uuid
import threading

from flask import request
from flask_socketio import emit

from models import db
from models.user import User
from sockets.presence_events import get_user_sid, get_sid_user


# In-memory active call tracking: user_id -> partner_user_id
active_calls = {}
# Call metadata: call_key -> { started_at, call_type, caller_id, callee_id }
call_meta = {}
# Media state per user in call: user_id -> { muted, video_on, screen_sharing }
call_media_state = {}
# Ring start times for timeout: caller_id -> timestamp
ring_start = {}

# ── Call Session Management ──────────────────────────────
# Persistent call sessions that survive socket disconnections
# session_id -> { session_id, caller_id, callee_id, call_type, started_at, status, call_id }
call_sessions = {}
# user_id -> session_id (quick lookup)
user_call_session = {}
# Disconnected users with pending reconnection: user_id -> { timer, session_id, disconnected_at }
disconnected_users = {}

RING_TIMEOUT_SECONDS = 45
# Grace period (seconds) before ending a call on network disconnection
DISCONNECT_GRACE_SECONDS = 120

def _get_user_info(user_id):
    """Look up user display info for signaling payloads."""
    user = db.session.get(User, user_id)
    if user:
        return {'id': user.id, 'display_name': user.display_name, 'username': user.username}
    return {'id': user_id, 'display_name': f'User #{user_id}', 'username': 'unknown'}


def _create_call_session(caller_id, callee_id, call_type, call_id=None):
    """Create a persistent call session that survives socket disconnections."""
    session_id = str(uuid.uuid4())
    session = {
        'session_id': session_id,
        'caller_id': caller_id,
        'callee_id': callee_id,
        'call_type': call_type,
        'started_at': time.time(),
        'status': 'active',
        'call_id': call_id,
    }
    call_sessions[session_id] = session
    user_call_session[caller_id] = session_id
    user_call_session[callee_id] = session_id
    print(f'[CALL-SESSION] Created session {session_id} for users {caller_id} <-> {callee_id}', flush=True)
    return session_id


def _end_call_session(session_id, reason='normal'):
    """End and clean up a call session."""
    session = call_sessions.pop(session_id, None)
    if not session:
        return
    caller_id = session['caller_id']
    callee_id = session['callee_id']
    user_call_session.pop(caller_id, None)
    user_call_session.pop(callee_id, None)
    # Clean up any pending disconnect timers
    for uid in [caller_id, callee_id]:
        dc = disconnected_users.pop(uid, None)
        if dc and dc.get('timer'):
            dc['timer'].cancel()
    print(f'[CALL-SESSION] Ended session {session_id} reason={reason}', flush=True)


def _cleanup_call_tracking(user_id, partner_id=None):
    """Remove in-memory call tracking for a user (and optionally partner)."""
    active_calls.pop(user_id, None)
    ring_start.pop(user_id, None)
    call_media_state.pop(user_id, None)
    if partner_id:
        active_calls.pop(partner_id, None)
        ring_start.pop(partner_id, None)
        call_media_state.pop(partner_id, None)
        call_key = tuple(sorted([user_id, partner_id]))
        call_meta.pop(call_key, None)


def handle_user_disconnect(user_id, socketio, app):
    """Called from presence_events on socket disconnect.
    Instead of ending the call immediately, start a 120-second grace period."""
    session_id = user_call_session.get(user_id)
    if not session_id:
        # No active call session — nothing to preserve
        partner_id = active_calls.pop(user_id, None)
        if partner_id:
            active_calls.pop(partner_id, None)
            ring_start.pop(user_id, None)
            call_media_state.pop(user_id, None)
            partner_sid = get_user_sid(partner_id)
            if partner_sid:
                with app.app_context():
                    socketio.emit('call_ended', {
                        'from_id': user_id,
                        'reason': 'disconnected',
                    }, room=partner_sid)
        return

    session = call_sessions.get(session_id)
    if not session:
        return

    partner_id = session['callee_id'] if session['caller_id'] == user_id else session['caller_id']
    print(f'[CALL-SESSION] User {user_id} disconnected during session {session_id}, '
          f'starting {DISCONNECT_GRACE_SECONDS}s grace period', flush=True)

    # Notify the partner that the other side is reconnecting
    partner_sid = get_user_sid(partner_id)
    if partner_sid:
        socketio.emit('call_peer_disconnected', {
            'user_id': user_id,
            'session_id': session_id,
            'grace_seconds': DISCONNECT_GRACE_SECONDS,
        }, room=partner_sid)

    # Start grace period timer
    def _grace_expired():
        with app.app_context():
            dc = disconnected_users.pop(user_id, None)
            if not dc:
                return  # User reconnected before timer fired
            print(f'[CALL-SESSION] Grace period expired for user {user_id}, ending session {session_id}', flush=True)
            _end_call_session(session_id, reason='network_timeout')
            _cleanup_call_tracking(user_id, partner_id)

            # Notify the partner that the call is truly over
            p_sid = get_user_sid(partner_id)
            if p_sid:
                socketio.emit('call_ended', {
                    'from_id': user_id,
                    'reason': 'network_timeout',
                    'session_id': session_id,
                }, room=p_sid)
                socketio.emit('user_call_status', {'user_id': user_id, 'in_call': False}, room=p_sid)
                socketio.emit('user_call_status', {'user_id': partner_id, 'in_call': False}, room=p_sid)

    timer = threading.Timer(DISCONNECT_GRACE_SECONDS, _grace_expired)
    timer.daemon = True
    timer.start()
    disconnected_users[user_id] = {
        'timer': timer,
        'session_id': session_id,
        'disconnected_at': time.time(),
    }


def handle_user_reconnect(user_id, socketio):
    """Called from presence_events when a user re-authenticates.
    Restores call session if within grace period."""
    dc = disconnected_users.pop(user_id, None)
    if not dc:
        return  # No pending reconnection

    # Cancel the grace expiry timer
    if dc.get('timer'):
        dc['timer'].cancel()

    session_id = dc['session_id']
    session = call_sessions.get(session_id)
    if not session:
        return  # Session was ended by partner

    partner_id = session['callee_id'] if session['caller_id'] == user_id else session['caller_id']
    elapsed = time.time() - dc['disconnected_at']
    print(f'[CALL-SESSION] User {user_id} reconnected after {elapsed:.1f}s, restoring session {session_id}', flush=True)

    # Restore active_calls tracking
    active_calls[user_id] = partner_id
    active_calls[partner_id] = user_id

    # Notify the reconnected user to resume their call
    user_sid = get_user_sid(user_id)
    if user_sid:
        socketio.emit('call_session_restore', {
            'session_id': session_id,
            'partner_id': partner_id,
            'partner': _get_user_info(partner_id),
            'call_type': session['call_type'],
            'started_at': session['started_at'],
            'call_id': session.get('call_id'),
            'elapsed': elapsed,
        }, room=user_sid)

    # Notify the partner that their peer is back
    partner_sid = get_user_sid(partner_id)
    if partner_sid:
        socketio.emit('call_peer_reconnected', {
            'user_id': user_id,
            'session_id': session_id,
        }, room=partner_sid)


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
            # Send push notification for the missed call
            try:
                from services.push_service import send_call_notification
                caller_info = _get_user_info(caller_id)
                send_call_notification(target_id, caller_info['display_name'], data.get('call_type', 'voice'))
            except Exception as e:
                print(f'[Push] Call notification error: {e}', flush=True)
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
        ring_start[caller_id] = time.time()
        call_media_state[caller_id] = {
            'muted': False,
            'video_on': data.get('call_type') == 'video',
            'screen_sharing': False,
        }

        caller_info = _get_user_info(caller_id)
        print(f'[CALL] Emitting incoming_call to {target_sid} (user {target_id})', flush=True)

        # Also send push notification (handles background/minimized tabs)
        try:
            from services.push_service import send_call_notification
            send_call_notification(target_id, caller_info['display_name'], data.get('call_type', 'voice'))
        except Exception as e:
            print(f'[Push] Call notification error: {e}', flush=True)

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
        ring_start.pop(caller_id, None)

        # Initialize media state for callee
        call_media_state[callee_id] = {
            'muted': False,
            'video_on': data.get('call_type', 'voice') == 'video',
            'screen_sharing': False,
        }

        # Store call metadata
        call_key = tuple(sorted([caller_id, callee_id]))
        call_meta[call_key] = {
            'started_at': time.time(),
            'call_type': data.get('call_type', 'voice'),
            'caller_id': caller_id,
            'callee_id': callee_id,
        }

        # Create persistent call session for resilience
        session_id = _create_call_session(
            caller_id, callee_id,
            data.get('call_type', 'voice'),
            call_id=data.get('call_id'),
        )

        callee_info = _get_user_info(callee_id)

        if caller_sid:
            emit('call_accepted', {
                'callee_id': callee_id,
                'callee': callee_info,
                'answer': data.get('answer'),
                'call_id': data.get('call_id'),
                'session_id': session_id,
            }, room=caller_sid)

        # Broadcast that both users are now in a call
        emit('user_call_status', {
            'user_id': caller_id,
            'in_call': True,
        }, broadcast=True)
        emit('user_call_status', {
            'user_id': callee_id,
            'in_call': True,
        }, broadcast=True)

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
        ring_start.pop(caller_id, None)
        call_media_state.pop(caller_id, None)
        call_media_state.pop(user_id, None)

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

        # End the call session if one exists
        session_id = user_call_session.get(user_id)
        if session_id:
            _end_call_session(session_id, reason=data.get('reason', 'normal'))

        # Clear call tracking for both sides
        _cleanup_call_tracking(user_id, target_id)

        target_sid = get_user_sid(target_id)
        if target_sid:
            emit('call_ended', {
                'from_id': user_id,
                'call_id': data.get('call_id'),
                'reason': data.get('reason', 'ended'),
            }, room=target_sid)

        # Broadcast that both users are no longer in a call
        emit('user_call_status', {
            'user_id': user_id,
            'in_call': False,
        }, broadcast=True)
        emit('user_call_status', {
            'user_id': target_id,
            'in_call': False,
        }, broadcast=True)

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

    # ── Media state synchronization ──────────────────────────

    @socketio.on('media_state_changed')
    def handle_media_state_changed(data):
        """Sync mute/video/screen state to the call partner."""
        user_id = get_sid_user(request.sid)
        if not user_id:
            return

        # Update local tracking
        call_media_state[user_id] = {
            'muted': data.get('muted', False),
            'video_on': data.get('video_on', False),
            'screen_sharing': data.get('screen_sharing', False),
        }

        target_id = data.get('target_id')
        if isinstance(target_id, str):
            target_id = int(target_id)
        target_sid = get_user_sid(target_id)
        if target_sid:
            emit('remote_media_state', {
                'user_id': user_id,
                'muted': data.get('muted', False),
                'video_on': data.get('video_on', False),
                'screen_sharing': data.get('screen_sharing', False),
            }, room=target_sid)

    # ── Call reconnection signaling ──────────────────────────

    @socketio.on('call_reconnecting')
    def handle_call_reconnecting(data):
        """Notify call partner that we are reconnecting (ICE restart in progress)."""
        user_id = get_sid_user(request.sid)
        if not user_id:
            return
        target_id = data.get('target_id')
        if isinstance(target_id, str):
            target_id = int(target_id)
        target_sid = get_user_sid(target_id)
        if target_sid:
            emit('call_reconnecting', {
                'user_id': user_id,
            }, room=target_sid)

    @socketio.on('call_reconnected')
    def handle_call_reconnected(data):
        """Notify call partner that reconnection succeeded."""
        user_id = get_sid_user(request.sid)
        if not user_id:
            return
        target_id = data.get('target_id')
        if isinstance(target_id, str):
            target_id = int(target_id)
        target_sid = get_user_sid(target_id)
        if target_sid:
            emit('call_reconnected', {
                'user_id': user_id,
            }, room=target_sid)

    # ── Ring timeout check ───────────────────────────────────

    @socketio.on('check_ring_timeout')
    def handle_check_ring_timeout(data):
        """Called by caller periodically to check if ring has timed out."""
        user_id = get_sid_user(request.sid)
        if not user_id:
            return
        start = ring_start.get(user_id)
        if start and (time.time() - start) > RING_TIMEOUT_SECONDS:
            # Timeout — auto-end the call attempt
            target_id = active_calls.pop(user_id, None)
            ring_start.pop(user_id, None)
            call_media_state.pop(user_id, None)
            if target_id:
                active_calls.pop(target_id, None)
                call_media_state.pop(target_id, None)
                target_sid = get_user_sid(target_id)
                if target_sid:
                    emit('call_ended', {
                        'from_id': user_id,
                        'reason': 'no_answer',
                        'call_id': data.get('call_id'),
                    }, room=target_sid)
            emit('call_error', {
                'error': 'No answer. The call was not picked up.',
                'reason': 'timeout',
            })

    # ── Call quality report ──────────────────────────────────

    @socketio.on('call_quality_report')
    def handle_call_quality_report(data):
        """Receive quality stats from a client and relay to the partner."""
        user_id = get_sid_user(request.sid)
        if not user_id:
            return
        target_id = data.get('target_id')
        if isinstance(target_id, str):
            target_id = int(target_id)
        target_sid = get_user_sid(target_id)
        if target_sid:
            emit('partner_quality_report', {
                'user_id': user_id,
                'quality': data.get('quality', 'good'),
                'rtt': data.get('rtt', 0),
                'packet_loss': data.get('packet_loss', 0),
                'bitrate_in': data.get('bitrate_in', 0),
                'bitrate_out': data.get('bitrate_out', 0),
            }, room=target_sid)

    # ── Call session management events ───────────────────────

    @socketio.on('call_session_check')
    def handle_call_session_check(data):
        """Client asks if they have an active call session (used after reconnect)."""
        user_id = get_sid_user(request.sid)
        if not user_id:
            return

        session_id = user_call_session.get(user_id)
        if session_id and session_id in call_sessions:
            session = call_sessions[session_id]
            partner_id = session['callee_id'] if session['caller_id'] == user_id else session['caller_id']
            emit('call_session_exists', {
                'session_id': session_id,
                'partner_id': partner_id,
                'partner': _get_user_info(partner_id),
                'call_type': session['call_type'],
                'started_at': session['started_at'],
                'call_id': session.get('call_id'),
            })
        else:
            emit('call_session_exists', {'session_id': None})

    @socketio.on('call_session_rejoin')
    def handle_call_session_rejoin(data):
        """Client sends a new WebRTC offer to rejoin an existing call session."""
        user_id = get_sid_user(request.sid)
        if not user_id:
            return

        session_id = data.get('session_id')
        session = call_sessions.get(session_id)
        if not session:
            emit('call_error', {'error': 'Call session no longer exists'})
            return

        partner_id = session['callee_id'] if session['caller_id'] == user_id else session['caller_id']
        partner_sid = get_user_sid(partner_id)

        if partner_sid:
            emit('call_rejoin_offer', {
                'from_id': user_id,
                'offer': data.get('offer'),
                'session_id': session_id,
            }, room=partner_sid)
        else:
            emit('call_error', {'error': 'Call partner is no longer connected'})

    @socketio.on('call_rejoin_answer')
    def handle_call_rejoin_answer(data):
        """Partner responds to a rejoin offer with an answer."""
        user_id = get_sid_user(request.sid)
        if not user_id:
            return

        target_id = data.get('target_id')
        if isinstance(target_id, str):
            target_id = int(target_id)
        target_sid = get_user_sid(target_id)

        if target_sid:
            emit('call_rejoin_answer', {
                'from_id': user_id,
                'answer': data.get('answer'),
                'session_id': data.get('session_id'),
            }, room=target_sid)
