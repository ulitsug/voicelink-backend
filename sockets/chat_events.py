from flask import request, current_app
from flask_socketio import emit, join_room, leave_room

from models import db
from models.message import Message
from models.group import GroupMember
from sockets.presence_events import get_user_sid, get_sid_user


def register_chat_events(socketio):

    @socketio.on('send_message')
    def handle_send_message(data):
        sender_id = get_sid_user(request.sid)
        if not sender_id:
            return

        receiver_id = data.get('receiver_id')
        group_id = data.get('group_id')
        content = data.get('content', '').strip()
        encrypted_content = data.get('encrypted_content')
        message_type = data.get('message_type', 'text')

        message = Message(
            sender_id=sender_id,
            receiver_id=receiver_id,
            group_id=group_id,
            content=content,
            encrypted_content=encrypted_content,
            message_type=message_type,
            file_url=data.get('file_url'),
            file_name=data.get('file_name'),
            file_size=data.get('file_size'),
        )
        db.session.add(message)
        db.session.commit()

        msg_data = message.to_dict()

        if receiver_id:
            # Direct message
            target_sid = get_user_sid(receiver_id)
            if target_sid:
                emit('new_message', msg_data, room=target_sid)
            # Send push notification regardless (covers background/minimized tabs and offline)
            try:
                from services.push_service import send_message_notification
                from models.user import User
                sender = db.session.get(User, sender_id)
                sender_name = sender.display_name if sender else 'Someone'
                preview = content if message_type == 'text' else f'Sent a {message_type}'
                send_message_notification(receiver_id, sender_name, preview)
            except Exception as e:
                print(f'[Push] Chat notification error: {e}', flush=True)
            # Also send back to sender for confirmation
            emit('message_sent', msg_data)
        elif group_id:
            # Group message - send to all group members
            members = GroupMember.query.filter_by(group_id=group_id).all()
            for member in members:
                if member.user_id != sender_id:
                    member_sid = get_user_sid(member.user_id)
                    if member_sid:
                        emit('new_message', msg_data, room=member_sid)
            emit('message_sent', msg_data)

    @socketio.on('typing')
    def handle_typing(data):
        sender_id = get_sid_user(request.sid)
        if not sender_id:
            return

        receiver_id = data.get('receiver_id')
        group_id = data.get('group_id')

        if receiver_id:
            target_sid = get_user_sid(receiver_id)
            if target_sid:
                emit('user_typing', {
                    'user_id': sender_id,
                    'is_typing': data.get('is_typing', True),
                }, room=target_sid)
        elif group_id:
            members = GroupMember.query.filter_by(group_id=group_id).all()
            for member in members:
                if member.user_id != sender_id:
                    member_sid = get_user_sid(member.user_id)
                    if member_sid:
                        emit('user_typing', {
                            'user_id': sender_id,
                            'group_id': group_id,
                            'is_typing': data.get('is_typing', True),
                        }, room=member_sid)

    @socketio.on('mark_read')
    def handle_mark_read(data):
        user_id = get_sid_user(request.sid)
        if not user_id:
            return

        sender_id = data.get('sender_id')
        if sender_id:
            Message.query.filter(
                Message.sender_id == sender_id,
                Message.receiver_id == user_id,
                Message.is_read == False
            ).update({'is_read': True})
            db.session.commit()

            # Notify sender about read receipts
            sender_sid = get_user_sid(sender_id)
            if sender_sid:
                emit('messages_read', {
                    'reader_id': user_id,
                }, room=sender_sid)

    @socketio.on('join_group_room')
    def handle_join_group(data):
        user_id = get_sid_user(request.sid)
        if not user_id:
            return

        group_id = data.get('group_id')
        membership = GroupMember.query.filter_by(
            group_id=group_id, user_id=user_id
        ).first()

        if membership:
            join_room(f'group_{group_id}')

    @socketio.on('leave_group_room')
    def handle_leave_group(data):
        group_id = data.get('group_id')
        leave_room(f'group_{group_id}')

    @socketio.on('delete_message')
    def handle_delete_message(data):
        sender_id = get_sid_user(request.sid)
        if not sender_id:
            return

        message_id = data.get('message_id')
        if not message_id:
            return

        message = db.session.get(Message, message_id)
        if not message or message.sender_id != sender_id:
            return

        receiver_id = message.receiver_id
        group_id = message.group_id

        # Delete associated file
        if message.file_url:
            import os
            filename = message.file_url.split('/')[-1]
            upload_dir = current_app.config.get('UPLOAD_FOLDER', 'uploads')
            filepath = os.path.join(upload_dir, filename)
            if os.path.isfile(filepath):
                os.remove(filepath)

        db.session.delete(message)
        db.session.commit()

        delete_data = {'message_id': message_id, 'sender_id': sender_id}

        if receiver_id:
            target_sid = get_user_sid(receiver_id)
            if target_sid:
                emit('message_deleted', delete_data, room=target_sid)
            emit('message_deleted', delete_data)
        elif group_id:
            members = GroupMember.query.filter_by(group_id=group_id).all()
            for member in members:
                if member.user_id != sender_id:
                    member_sid = get_user_sid(member.user_id)
                    if member_sid:
                        emit('message_deleted', delete_data, room=member_sid)
            emit('message_deleted', delete_data)

    @socketio.on('delete_conversation')
    def handle_delete_conversation(data):
        user_id = get_sid_user(request.sid)
        if not user_id:
            return

        other_user_id = data.get('other_user_id')
        if not other_user_id:
            return

        import os
        messages = Message.query.filter(
            Message.group_id.is_(None),
            (
                ((Message.sender_id == user_id) & (Message.receiver_id == other_user_id)) |
                ((Message.sender_id == other_user_id) & (Message.receiver_id == user_id))
            )
        ).all()

        if not messages:
            return

        upload_dir = current_app.config.get('UPLOAD_FOLDER', 'uploads')
        for msg in messages:
            if msg.file_url:
                filename = msg.file_url.split('/')[-1]
                filepath = os.path.join(upload_dir, filename)
                if os.path.isfile(filepath):
                    os.remove(filepath)
            db.session.delete(msg)
        db.session.commit()

        delete_data = {'other_user_id': other_user_id, 'deleted_by': user_id}
        # Notify the other user
        target_sid = get_user_sid(other_user_id)
        if target_sid:
            emit('conversation_deleted', delete_data, room=target_sid)
        # Confirm to sender
        emit('conversation_deleted', delete_data)
