import os
import socket
import platform
from datetime import datetime

from flask import Blueprint, jsonify, request

from models import db
from models.user import User
from models.contact import Contact
from models.message import Message
from models.call_log import CallLog
from models.group import Group, GroupMember
from models.system_config import SystemConfig
from utils.auth import admin_required

admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')


def _get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        return s.getsockname()[0]
    except Exception:
        return '127.0.0.1'
    finally:
        s.close()


# ── System Overview ──────────────────────────────────────────────

@admin_bp.route('/dashboard', methods=['GET'])
@admin_required
def admin_dashboard(user):
    total_users = User.query.count()
    total_messages = Message.query.count()
    total_calls = CallLog.query.count()
    total_groups = Group.query.count()
    total_contacts = Contact.query.count()

    active_calls = CallLog.query.filter(
        CallLog.status.in_(['initiated', 'ringing', 'active'])
    ).count()

    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    new_users_today = User.query.filter(User.created_at >= today).count()
    messages_today = Message.query.filter(Message.created_at >= today).count()
    calls_today = CallLog.query.filter(CallLog.started_at >= today).count()

    return jsonify({
        'total_users': total_users,
        'total_messages': total_messages,
        'total_calls': total_calls,
        'total_groups': total_groups,
        'total_contacts': total_contacts,
        'active_calls': active_calls,
        'new_users_today': new_users_today,
        'messages_today': messages_today,
        'calls_today': calls_today,
    })


# ── System Info ──────────────────────────────────────────────────

@admin_bp.route('/system-info', methods=['GET'])
@admin_required
def system_info(user):
    from config import Config
    local_ip = _get_local_ip()

    return jsonify({
        'hostname': socket.gethostname(),
        'local_ip': local_ip,
        'server_host': Config.SERVER_HOST,
        'server_port': Config.SERVER_PORT,
        'platform': platform.platform(),
        'python_version': platform.python_version(),
        'db_host': Config.DB_HOST,
        'db_port': Config.DB_PORT,
        'db_name': Config.DB_NAME,
        'db_user': Config.DB_USER,
        'turn_host': Config.TURN_SERVER_HOST,
        'turn_port': Config.TURN_SERVER_PORT,
        'turn_username': Config.TURN_USERNAME,
        'upload_folder': Config.UPLOAD_FOLDER,
        'max_upload_mb': Config.MAX_CONTENT_LENGTH // (1024 * 1024),
    })


# ── System Config (dynamic key/value) ───────────────────────────

@admin_bp.route('/config', methods=['GET'])
@admin_required
def get_all_config(user):
    configs = SystemConfig.query.order_by(SystemConfig.key).all()
    return jsonify({'configs': [c.to_dict() for c in configs]})


@admin_bp.route('/config', methods=['PUT'])
@admin_required
def update_config(user):
    data = request.get_json()
    key = data.get('key', '').strip()
    value = data.get('value')
    description = data.get('description')

    if not key:
        return jsonify({'error': 'key is required'}), 400

    row = SystemConfig.set(key, value, description)
    return jsonify({'config': row.to_dict()})


@admin_bp.route('/config/<key>', methods=['DELETE'])
@admin_required
def delete_config(user, key):
    row = SystemConfig.query.filter_by(key=key).first()
    if not row:
        return jsonify({'error': 'Config not found'}), 404
    db.session.delete(row)
    db.session.commit()
    return jsonify({'message': f'Config "{key}" deleted'})


# ── User Management ─────────────────────────────────────────────

@admin_bp.route('/users', methods=['GET'])
@admin_required
def list_users(user):
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    search = request.args.get('q', '').strip()
    role_filter = request.args.get('role', '').strip()

    query = User.query

    if search:
        query = query.filter(
            (User.username.ilike(f'%{search}%')) |
            (User.display_name.ilike(f'%{search}%')) |
            (User.email.ilike(f'%{search}%'))
        )

    if role_filter:
        query = query.filter(User.role == role_filter)

    pagination = query.order_by(User.id).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return jsonify({
        'users': [u.to_dict(include_email=True) for u in pagination.items],
        'total': pagination.total,
        'page': pagination.page,
        'pages': pagination.pages,
    })


@admin_bp.route('/users', methods=['POST'])
@admin_required
def create_user(user):
    data = request.get_json()
    username = data.get('username', '').strip()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    display_name = data.get('display_name', '').strip()
    role = data.get('role', 'user')

    if not all([username, email, password, display_name]):
        return jsonify({'error': 'All fields are required'}), 400

    if role not in ('user', 'admin'):
        return jsonify({'error': 'Invalid role. Use "user" or "admin"'}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({'error': 'Username already taken'}), 409

    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'Email already registered'}), 409

    new_user = User(
        username=username,
        email=email,
        display_name=display_name,
        role=role,
        email_verified=data.get('email_verified', False),
    )
    new_user.set_password(password)
    db.session.add(new_user)
    db.session.commit()

    return jsonify({'user': new_user.to_dict(include_email=True)}), 201


@admin_bp.route('/users/<int:user_id>', methods=['GET'])
@admin_required
def get_user(user, user_id):
    target = db.session.get(User, user_id)
    if not target:
        return jsonify({'error': 'User not found'}), 404

    # Count stats
    contacts_count = Contact.query.filter_by(user_id=user_id, is_blocked=False).count()
    messages_sent = Message.query.filter_by(sender_id=user_id).count()
    messages_received = Message.query.filter_by(receiver_id=user_id).count()
    calls_made = CallLog.query.filter_by(caller_id=user_id).count()
    calls_received = CallLog.query.filter_by(callee_id=user_id).count()
    groups_count = GroupMember.query.filter_by(user_id=user_id).count()

    user_data = target.to_dict(include_email=True)
    user_data['stats'] = {
        'contacts': contacts_count,
        'messages_sent': messages_sent,
        'messages_received': messages_received,
        'calls_made': calls_made,
        'calls_received': calls_received,
        'groups': groups_count,
    }

    return jsonify({'user': user_data})


@admin_bp.route('/users/<int:user_id>', methods=['PUT'])
@admin_required
def update_user(user, user_id):
    target = db.session.get(User, user_id)
    if not target:
        return jsonify({'error': 'User not found'}), 404

    # Prevent modifying super_admin role unless you are super_admin
    if target.is_super_admin and not user.is_super_admin:
        return jsonify({'error': 'Cannot modify super admin'}), 403

    data = request.get_json()

    if data.get('username'):
        existing = User.query.filter(User.username == data['username'], User.id != user_id).first()
        if existing:
            return jsonify({'error': 'Username already taken'}), 409
        target.username = data['username'].strip()

    if data.get('email'):
        existing = User.query.filter(User.email == data['email'].lower(), User.id != user_id).first()
        if existing:
            return jsonify({'error': 'Email already registered'}), 409
        target.email = data['email'].strip().lower()

    if data.get('display_name'):
        target.display_name = data['display_name'].strip()

    if 'bio' in data:
        target.bio = (data['bio'] or '').strip()[:250]

    if data.get('role') and not target.is_super_admin:
        if data['role'] in ('user', 'admin'):
            target.role = data['role']

    if data.get('password'):
        target.set_password(data['password'])

    db.session.commit()
    return jsonify({'user': target.to_dict(include_email=True)})


@admin_bp.route('/users/<int:user_id>', methods=['DELETE'])
@admin_required
def delete_user(user, user_id):
    target = db.session.get(User, user_id)
    if not target:
        return jsonify({'error': 'User not found'}), 404

    # Super admin cannot be deleted
    if target.is_super_admin:
        return jsonify({'error': 'Super admin cannot be deleted'}), 403

    # Cannot delete yourself
    if target.id == user.id:
        return jsonify({'error': 'Cannot delete your own account'}), 403

    # Delete user's related data
    Contact.query.filter((Contact.user_id == user_id) | (Contact.contact_id == user_id)).delete()
    Message.query.filter((Message.sender_id == user_id) | (Message.receiver_id == user_id)).delete()
    CallLog.query.filter((CallLog.caller_id == user_id) | (CallLog.callee_id == user_id)).delete()
    GroupMember.query.filter_by(user_id=user_id).delete()

    db.session.delete(target)
    db.session.commit()

    return jsonify({'message': f'User "{target.username}" deleted'})


# ── Platform Stats ───────────────────────────────────────────────

@admin_bp.route('/stats/messages', methods=['GET'])
@admin_required
def message_stats(user):
    from sqlalchemy import func

    total = Message.query.count()
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_count = Message.query.filter(Message.created_at >= today).count()

    by_type = db.session.query(
        Message.message_type, func.count(Message.id)
    ).group_by(Message.message_type).all()

    return jsonify({
        'total': total,
        'today': today_count,
        'by_type': {t: c for t, c in by_type},
    })


@admin_bp.route('/stats/calls', methods=['GET'])
@admin_required
def call_stats(user):
    from sqlalchemy import func

    total = CallLog.query.count()
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_count = CallLog.query.filter(CallLog.started_at >= today).count()

    by_status = db.session.query(
        CallLog.status, func.count(CallLog.id)
    ).group_by(CallLog.status).all()

    by_type = db.session.query(
        CallLog.call_type, func.count(CallLog.id)
    ).group_by(CallLog.call_type).all()

    avg_duration = db.session.query(func.avg(CallLog.duration)).filter(
        CallLog.duration > 0
    ).scalar() or 0

    return jsonify({
        'total': total,
        'today': today_count,
        'by_status': {s: c for s, c in by_status},
        'by_type': {t: c for t, c in by_type},
        'avg_duration_seconds': round(float(avg_duration)),
    })


# ── Email Verification Management ───────────────────────────

@admin_bp.route('/users/pending-verification', methods=['GET'])
@admin_required
def pending_verification_users(user):
    """List users whose email is not yet verified."""
    users = User.query.filter_by(email_verified=False).order_by(User.created_at.desc()).all()
    return jsonify({
        'users': [u.to_dict(include_email=True) for u in users],
        'total': len(users),
    })


@admin_bp.route('/users/<int:user_id>/send-verification', methods=['POST'])
@admin_required
def send_verification(user, user_id):
    """Admin sends a verification email to a user."""
    target = db.session.get(User, user_id)
    if not target:
        return jsonify({'error': 'User not found'}), 404

    if target.email_verified:
        return jsonify({'error': 'User email is already verified'}), 400

    token = target.generate_verification_token()
    db.session.commit()

    from services.email_service import send_verification_email
    sent = send_verification_email(target, token)

    if sent:
        return jsonify({'message': f'Verification email sent to {target.email}'})
    else:
        return jsonify({'error': 'Failed to send email. Check SMTP configuration.'}), 500


@admin_bp.route('/users/<int:user_id>/verify-email', methods=['POST'])
@admin_required
def admin_verify_email(user, user_id):
    """Admin manually verifies a user's email."""
    target = db.session.get(User, user_id)
    if not target:
        return jsonify({'error': 'User not found'}), 404

    target.email_verified = True
    target.verification_token = None
    target.verification_token_expires = None
    db.session.commit()

    return jsonify({
        'message': f'Email verified for {target.username}',
        'user': target.to_dict(include_email=True),
    })


@admin_bp.route('/users/<int:user_id>/unverify-email', methods=['POST'])
@admin_required
def admin_unverify_email(user, user_id):
    """Admin revokes a user's email verification."""
    target = db.session.get(User, user_id)
    if not target:
        return jsonify({'error': 'User not found'}), 404

    if target.is_super_admin:
        return jsonify({'error': 'Cannot unverify super admin'}), 403

    target.email_verified = False
    db.session.commit()

    return jsonify({
        'message': f'Email verification revoked for {target.username}',
        'user': target.to_dict(include_email=True),
    })


@admin_bp.route('/users/<int:user_id>/send-reset', methods=['POST'])
@admin_required
def admin_send_reset(user, user_id):
    """Admin sends a password reset email to a user."""
    target = db.session.get(User, user_id)
    if not target:
        return jsonify({'error': 'User not found'}), 404

    token = target.generate_reset_token()
    db.session.commit()

    from services.email_service import send_password_reset_email
    sent = send_password_reset_email(target, token)

    if sent:
        return jsonify({'message': f'Password reset email sent to {target.email}'})
    else:
        return jsonify({'error': 'Failed to send email. Check SMTP configuration.'}), 500
