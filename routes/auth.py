import os
import uuid
from datetime import datetime

from flask import Blueprint, jsonify, request, current_app, send_from_directory
from flask_jwt_extended import create_access_token

from models import db
from models.user import User
from models.contact import Contact
from models.message import Message
from models.call_log import CallLog
from models.group import Group, GroupMember
from utils.auth import jwt_required_with_user

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')


@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    username = data.get('username', '').strip()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    display_name = data.get('display_name', '').strip()

    if not all([username, email, password, display_name]):
        return jsonify({'error': 'All fields are required'}), 400

    if len(username) < 3 or len(username) > 50:
        return jsonify({'error': 'Username must be 3-50 characters'}), 400

    if len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({'error': 'Username already taken'}), 409

    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'Email already registered'}), 409

    user = User(
        username=username,
        email=email,
        display_name=display_name,
        email_verified=False,
    )
    user.set_password(password)

    db.session.add(user)
    db.session.commit()

    return jsonify({
        'message': 'Registration successful. Please wait for admin to send you a verification email.',
        'pending_verification': True,
    }), 201


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    username = data.get('username', '').strip()
    password = data.get('password', '')

    if not all([username, password]):
        return jsonify({'error': 'Username and password are required'}), 400

    # Allow login with username or email
    user = User.query.filter(
        (User.username == username) | (User.email == username.lower())
    ).first()

    if not user or not user.check_password(password):
        return jsonify({'error': 'Invalid credentials'}), 401

    # Admin/super_admin bypass email verification
    if not user.is_admin and not user.email_verified:
        return jsonify({'error': 'Email not verified. Please check your email for a verification link or contact admin.'}), 403

    access_token = create_access_token(identity=str(user.id))

    return jsonify({
        'message': 'Login successful',
        'user': user.to_dict(include_email=True),
        'access_token': access_token,
    })


@auth_bp.route('/verify-email', methods=['POST'])
def verify_email():
    data = request.get_json()
    token = data.get('token', '').strip() if data else ''

    if not token:
        return jsonify({'error': 'Verification token is required'}), 400

    user = User.query.filter_by(verification_token=token).first()
    if not user:
        return jsonify({'error': 'Invalid verification token'}), 400

    if user.verification_token_expires and user.verification_token_expires < datetime.utcnow():
        return jsonify({'error': 'Verification token has expired. Please request a new one from admin.'}), 400

    user.email_verified = True
    user.verification_token = None
    user.verification_token_expires = None
    db.session.commit()

    access_token = create_access_token(identity=str(user.id))

    return jsonify({
        'message': 'Email verified successfully. You can now log in.',
        'user': user.to_dict(include_email=True),
        'access_token': access_token,
    })


@auth_bp.route('/forgot-password', methods=['POST'])
def forgot_password():
    data = request.get_json()
    email = data.get('email', '').strip().lower() if data else ''

    if not email:
        return jsonify({'error': 'Email is required'}), 400

    user = User.query.filter_by(email=email).first()

    # Always return success to not leak whether email exists
    if not user:
        return jsonify({'message': 'If the email exists, a password reset link has been sent.'})

    token = user.generate_reset_token()
    db.session.commit()

    from services.email_service import send_password_reset_email
    send_password_reset_email(user, token)

    return jsonify({'message': 'If the email exists, a password reset link has been sent.'})


@auth_bp.route('/reset-password', methods=['POST'])
def reset_password():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    token = data.get('token', '').strip()
    new_password = data.get('password', '')

    if not token:
        return jsonify({'error': 'Reset token is required'}), 400

    if len(new_password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400

    user = User.query.filter_by(reset_token=token).first()
    if not user:
        return jsonify({'error': 'Invalid reset token'}), 400

    if user.reset_token_expires and user.reset_token_expires < datetime.utcnow():
        return jsonify({'error': 'Reset token has expired. Please request a new one.'}), 400

    user.set_password(new_password)
    user.reset_token = None
    user.reset_token_expires = None
    db.session.commit()

    return jsonify({'message': 'Password reset successfully. You can now log in with your new password.'})


@auth_bp.route('/me', methods=['GET'])
@jwt_required_with_user
def get_me(user):
    return jsonify({'user': user.to_dict(include_email=True)})


@auth_bp.route('/update-profile', methods=['PUT'])
@jwt_required_with_user
def update_profile(user):
    data = request.get_json()
    if data.get('display_name'):
        user.display_name = data['display_name'].strip()[:100]
    if 'bio' in data:
        user.bio = (data['bio'] or '').strip()[:250]
    if data.get('avatar_url'):
        user.avatar_url = data['avatar_url']
    if data.get('public_key'):
        user.public_key = data['public_key']

    db.session.commit()
    return jsonify({'user': user.to_dict(include_email=True)})


@auth_bp.route('/change-password', methods=['PUT'])
@jwt_required_with_user
def change_password(user):
    data = request.get_json()
    current_password = data.get('current_password', '')
    new_password = data.get('new_password', '')

    if not user.check_password(current_password):
        return jsonify({'error': 'Current password is incorrect'}), 400

    if len(new_password) < 6:
        return jsonify({'error': 'New password must be at least 6 characters'}), 400

    user.set_password(new_password)
    db.session.commit()

    return jsonify({'message': 'Password changed successfully'})


ALLOWED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}


@auth_bp.route('/upload-avatar', methods=['POST'])
@jwt_required_with_user
def upload_avatar(user):
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if not file.filename:
        return jsonify({'error': 'No file selected'}), 400

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        return jsonify({'error': 'Only image files are allowed (jpg, png, gif, webp)'}), 400

    safe_filename = f"avatar_{user.id}_{uuid.uuid4().hex[:8]}{ext}"
    avatar_dir = os.path.join(current_app.config.get('UPLOAD_FOLDER', 'uploads'), 'avatars')
    os.makedirs(avatar_dir, exist_ok=True)

    # Remove old avatar file if exists
    if user.avatar_url and user.avatar_url.startswith('/api/auth/avatars/'):
        old_name = user.avatar_url.split('/')[-1]
        old_path = os.path.join(avatar_dir, old_name)
        if os.path.exists(old_path):
            os.remove(old_path)

    filepath = os.path.join(avatar_dir, safe_filename)
    file.save(filepath)

    avatar_url = f"/api/auth/avatars/{safe_filename}"
    user.avatar_url = avatar_url
    db.session.commit()

    return jsonify({
        'avatar_url': avatar_url,
        'user': user.to_dict(include_email=True),
    })


@auth_bp.route('/remove-avatar', methods=['DELETE'])
@jwt_required_with_user
def remove_avatar(user):
    if user.avatar_url and user.avatar_url.startswith('/api/auth/avatars/'):
        old_name = user.avatar_url.split('/')[-1]
        avatar_dir = os.path.join(current_app.config.get('UPLOAD_FOLDER', 'uploads'), 'avatars')
        old_path = os.path.join(avatar_dir, old_name)
        if os.path.exists(old_path):
            os.remove(old_path)

    user.avatar_url = None
    db.session.commit()
    return jsonify({'user': user.to_dict(include_email=True)})


@auth_bp.route('/avatars/<filename>', methods=['GET'])
def serve_avatar(filename):
    if '/' in filename or '\\' in filename or '..' in filename:
        return jsonify({'error': 'Invalid filename'}), 400
    avatar_dir = os.path.join(current_app.config.get('UPLOAD_FOLDER', 'uploads'), 'avatars')
    return send_from_directory(avatar_dir, filename)


@auth_bp.route('/dashboard-stats', methods=['GET'])
@jwt_required_with_user
def dashboard_stats(user):
    contacts_count = Contact.query.filter_by(user_id=user.id, is_blocked=False).count()

    groups_count = GroupMember.query.filter_by(user_id=user.id).count()

    unread_messages = Message.query.filter_by(
        receiver_id=user.id, is_read=False
    ).count()

    total_calls = CallLog.query.filter(
        (CallLog.caller_id == user.id) | (CallLog.callee_id == user.id)
    ).count()

    missed_calls = CallLog.query.filter(
        CallLog.callee_id == user.id,
        CallLog.status == 'missed'
    ).count()

    recent_contacts = Contact.query.filter_by(
        user_id=user.id, is_blocked=False
    ).order_by(Contact.created_at.desc()).limit(5).all()

    recent_contact_users = []
    for c in recent_contacts:
        u = db.session.get(User, c.contact_id)
        if u:
            recent_contact_users.append(u.to_dict())

    return jsonify({
        'contacts': contacts_count,
        'groups': groups_count,
        'unread_messages': unread_messages,
        'total_calls': total_calls,
        'missed_calls': missed_calls,
        'recent_contacts': recent_contact_users,
    })
