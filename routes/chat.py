import os
import uuid

from flask import Blueprint, jsonify, request, current_app, send_from_directory

from models import db
from models.message import Message
from utils.auth import jwt_required_with_user

chat_bp = Blueprint('chat', __name__, url_prefix='/api/chat')


@chat_bp.route('/messages/<int:other_user_id>', methods=['GET', 'DELETE'])
@jwt_required_with_user
def handle_messages_by_id(user, other_user_id):
    if request.method == 'DELETE':
        return _delete_message(user, other_user_id)
    return _get_messages(user, other_user_id)


def _get_messages(user, other_user_id):
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    per_page = min(per_page, 100)

    messages = Message.query.filter(
        ((Message.sender_id == user.id) & (Message.receiver_id == other_user_id)) |
        ((Message.sender_id == other_user_id) & (Message.receiver_id == user.id))
    ).order_by(Message.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    # Mark unread messages as read
    Message.query.filter(
        Message.sender_id == other_user_id,
        Message.receiver_id == user.id,
        Message.is_read == False
    ).update({'is_read': True})
    db.session.commit()

    return jsonify({
        'messages': [m.to_dict() for m in reversed(messages.items)],
        'total': messages.total,
        'page': messages.page,
        'pages': messages.pages,
    })


@chat_bp.route('/messages', methods=['POST'])
@jwt_required_with_user
def send_message(user):
    data = request.get_json()

    receiver_id = data.get('receiver_id')
    group_id = data.get('group_id')
    content = data.get('content', '').strip()
    encrypted_content = data.get('encrypted_content')
    message_type = data.get('message_type', 'text')

    if not receiver_id and not group_id:
        return jsonify({'error': 'receiver_id or group_id is required'}), 400

    if message_type == 'text' and not content and not encrypted_content:
        return jsonify({'error': 'Message content is required'}), 400

    message = Message(
        sender_id=user.id,
        receiver_id=receiver_id,
        group_id=group_id,
        content=content,
        encrypted_content=encrypted_content,
        message_type=message_type,
    )
    db.session.add(message)
    db.session.commit()

    return jsonify({'message': message.to_dict()}), 201


@chat_bp.route('/upload', methods=['POST'])
@jwt_required_with_user
def upload_file(user):
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if not file.filename:
        return jsonify({'error': 'No file selected'}), 400

    # Generate unique filename
    ext = os.path.splitext(file.filename)[1]
    safe_filename = f"{uuid.uuid4().hex}{ext}"

    upload_dir = current_app.config.get('UPLOAD_FOLDER', 'uploads')
    os.makedirs(upload_dir, exist_ok=True)

    filepath = os.path.join(upload_dir, safe_filename)
    file.save(filepath)

    file_url = f"/api/chat/files/{safe_filename}"

    return jsonify({
        'file_url': file_url,
        'file_name': file.filename,
        'file_size': os.path.getsize(filepath),
    })


@chat_bp.route('/files/<filename>', methods=['GET'])
def serve_file(filename):
    # Prevent path traversal
    if '/' in filename or '\\' in filename or '..' in filename:
        return jsonify({'error': 'Invalid filename'}), 400

    upload_dir = current_app.config.get('UPLOAD_FOLDER', 'uploads')
    return send_from_directory(upload_dir, filename)


@chat_bp.route('/unread', methods=['GET'])
@jwt_required_with_user
def get_unread_counts(user):
    unread = db.session.query(
        Message.sender_id,
        db.func.count(Message.id).label('count')
    ).filter(
        Message.receiver_id == user.id,
        Message.is_read == False
    ).group_by(Message.sender_id).all()

    counts = {row.sender_id: row.count for row in unread}
    return jsonify({'unread': counts})


@chat_bp.route('/conversations', methods=['GET'])
@jwt_required_with_user
def get_conversations(user):
    """Return all 1-to-1 conversations for the current user, each with
    the other user's info, last message, and unread count."""
    from models.user import User
    from sqlalchemy import case, and_, or_, func

    uid = user.id

    # Sub-query: compute the "other" user id for each direct message row
    other_id = case(
        (Message.sender_id == uid, Message.receiver_id),
        else_=Message.sender_id,
    ).label('other_id')

    # All direct messages that involve the current user
    direct = (
        db.session.query(
            other_id,
            func.max(Message.id).label('last_msg_id'),
        )
        .filter(
            Message.group_id.is_(None),
            or_(Message.sender_id == uid, Message.receiver_id == uid),
        )
        .group_by('other_id')
    ).subquery()

    # Join with messages to get last message data, and with users for profile
    rows = (
        db.session.query(Message, User)
        .join(direct, Message.id == direct.c.last_msg_id)
        .join(User, User.id == direct.c.other_id)
        .order_by(Message.created_at.desc())
        .all()
    )

    # Unread counts per sender
    unread_rows = (
        db.session.query(
            Message.sender_id,
            func.count(Message.id).label('cnt'),
        )
        .filter(
            Message.receiver_id == uid,
            Message.is_read == False,
            Message.group_id.is_(None),
        )
        .group_by(Message.sender_id)
        .all()
    )
    unread_map = {r.sender_id: r.cnt for r in unread_rows}

    conversations = []
    for msg, other_user in rows:
        conversations.append({
            'user': other_user.to_dict(),
            'last_message': {
                'id': msg.id,
                'content': msg.content,
                'message_type': msg.message_type,
                'sender_id': msg.sender_id,
                'created_at': msg.created_at.isoformat(),
                'is_read': msg.is_read,
            },
            'unread_count': unread_map.get(other_user.id, 0),
        })

    return jsonify({'conversations': conversations})


def _delete_message(user, message_id):
    """Delete a single message. Only the sender can delete their own message."""
    message = db.session.get(Message, message_id)
    if not message:
        return jsonify({'error': 'Message not found'}), 404

    if message.sender_id != user.id:
        return jsonify({'error': 'You can only delete your own messages'}), 403

    # Delete associated file if it exists
    if message.file_url:
        filename = message.file_url.split('/')[-1]
        upload_dir = current_app.config.get('UPLOAD_FOLDER', 'uploads')
        filepath = os.path.join(upload_dir, filename)
        if os.path.isfile(filepath):
            os.remove(filepath)

    receiver_id = message.receiver_id
    group_id = message.group_id
    db.session.delete(message)
    db.session.commit()

    return jsonify({
        'success': True,
        'message_id': message_id,
        'receiver_id': receiver_id,
        'group_id': group_id,
    })


@chat_bp.route('/conversations/<int:other_user_id>', methods=['DELETE'])
@jwt_required_with_user
def delete_conversation(user, other_user_id):
    """Delete all messages in a 1-to-1 conversation between current user and other user."""
    messages = Message.query.filter(
        Message.group_id.is_(None),
        (
            ((Message.sender_id == user.id) & (Message.receiver_id == other_user_id)) |
            ((Message.sender_id == other_user_id) & (Message.receiver_id == user.id))
        )
    ).all()

    if not messages:
        return jsonify({'error': 'No conversation found'}), 404

    # Delete associated files
    upload_dir = current_app.config.get('UPLOAD_FOLDER', 'uploads')
    for msg in messages:
        if msg.file_url:
            filename = msg.file_url.split('/')[-1]
            filepath = os.path.join(upload_dir, filename)
            if os.path.isfile(filepath):
                os.remove(filepath)

    count = len(messages)
    for msg in messages:
        db.session.delete(msg)
    db.session.commit()

    return jsonify({
        'success': True,
        'other_user_id': other_user_id,
        'deleted_count': count,
    })
