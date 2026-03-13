import os
import socket
from datetime import datetime

from flask import Blueprint, jsonify, request

from models import db
from models.call_log import CallLog
from utils.auth import jwt_required_with_user

calls_bp = Blueprint('calls', __name__, url_prefix='/api/calls')


def _get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        return s.getsockname()[0]
    except Exception:
        return '127.0.0.1'
    finally:
        s.close()


@calls_bp.route('/ice-config', methods=['GET'])
@jwt_required_with_user
def get_ice_config(user):
    """Return ICE (STUN/TURN) server configuration for WebRTC."""
    from config import Config
    local_ip = _get_local_ip()

    turn_host = Config.TURN_SERVER_HOST or local_ip
    turn_port = Config.TURN_SERVER_PORT
    turn_user = Config.TURN_USERNAME
    turn_password = Config.TURN_PASSWORD

    ice_servers = [
        # Local TURN server (UDP + TCP)
        {
            'urls': [
                f'turn:{turn_host}:{turn_port}',
                f'turn:{turn_host}:{turn_port}?transport=tcp',
            ],
            'username': turn_user,
            'credential': turn_password,
        },
        # Local network STUN (via coturn)
        {'urls': f'stun:{turn_host}:{turn_port}'},
        # Public fallback STUN
        {'urls': 'stun:stun.l.google.com:19302'},
        {'urls': 'stun:stun1.l.google.com:19302'},
    ]

    return jsonify({
        'iceServers': ice_servers,
        'localIp': local_ip,
    })


@calls_bp.route('/history', methods=['GET'])
@jwt_required_with_user
def get_call_history(user):
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    per_page = min(per_page, 100)

    calls = CallLog.query.filter(
        (CallLog.caller_id == user.id) | (CallLog.callee_id == user.id)
    ).order_by(CallLog.started_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return jsonify({
        'calls': [c.to_dict() for c in calls.items],
        'total': calls.total,
        'page': calls.page,
        'pages': calls.pages,
    })


@calls_bp.route('/log', methods=['POST'])
@jwt_required_with_user
def create_call_log(user):
    data = request.get_json()

    call_log = CallLog(
        caller_id=user.id,
        callee_id=data.get('callee_id'),
        group_id=data.get('group_id'),
        call_type=data.get('call_type', 'voice'),
        status='initiated',
    )
    db.session.add(call_log)
    db.session.commit()

    return jsonify({'call': call_log.to_dict()}), 201


@calls_bp.route('/log/<int:call_id>', methods=['PUT'])
@jwt_required_with_user
def update_call_log(user, call_id):
    call_log = db.session.get(CallLog, call_id)
    if not call_log:
        return jsonify({'error': 'Call log not found'}), 404

    if call_log.caller_id != user.id and call_log.callee_id != user.id:
        return jsonify({'error': 'Unauthorized'}), 403

    data = request.get_json()
    if data.get('status'):
        call_log.status = data['status']
    if data.get('status') == 'active':
        call_log.answered_at = datetime.utcnow()
    if data.get('status') == 'ended':
        call_log.ended_at = datetime.utcnow()
        if call_log.answered_at:
            call_log.duration = int((call_log.ended_at - call_log.answered_at).total_seconds())
    if data.get('end_reason'):
        call_log.end_reason = data['end_reason']
    if data.get('quality_score') is not None:
        score = data['quality_score']
        if isinstance(score, int) and 1 <= score <= 5:
            call_log.quality_score = score

    db.session.commit()
    return jsonify({'call': call_log.to_dict()})


@calls_bp.route('/active', methods=['GET'])
@jwt_required_with_user
def get_active_calls(user):
    """Return list of users currently in active calls."""
    from sockets.call_events import active_calls, call_meta, call_media_state
    from models.user import User

    seen = set()
    result = []
    for uid, partner_id in active_calls.items():
        if uid in seen:
            continue
        seen.add(uid)
        seen.add(partner_id)
        caller = db.session.get(User, uid)
        callee = db.session.get(User, partner_id)
        meta = call_meta.get(uid, call_meta.get(partner_id, {}))
        result.append({
            'caller': caller.to_dict() if caller else {'id': uid},
            'callee': callee.to_dict() if callee else {'id': partner_id},
            'call_type': meta.get('call_type', 'voice'),
            'started_at': meta.get('started_at'),
        })

    return jsonify({'active_calls': result, 'count': len(result)})
