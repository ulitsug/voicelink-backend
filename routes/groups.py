from flask import Blueprint, jsonify, request

from models import db
from models.group import Group, GroupMember
from models.message import Message
from utils.auth import jwt_required_with_user

groups_bp = Blueprint('groups', __name__, url_prefix='/api/groups')


@groups_bp.route('', methods=['GET'])
@jwt_required_with_user
def get_groups(user):
    memberships = GroupMember.query.filter_by(user_id=user.id).all()
    group_ids = [m.group_id for m in memberships]
    groups = Group.query.filter(Group.id.in_(group_ids)).all() if group_ids else []
    return jsonify({'groups': [g.to_dict(include_members=True) for g in groups]})


@groups_bp.route('', methods=['POST'])
@jwt_required_with_user
def create_group(user):
    data = request.get_json()
    name = data.get('name', '').strip()

    if not name:
        return jsonify({'error': 'Group name is required'}), 400

    group = Group(
        name=name,
        description=data.get('description', '').strip(),
        created_by=user.id,
    )
    db.session.add(group)
    db.session.flush()

    # Add creator as admin
    admin_member = GroupMember(group_id=group.id, user_id=user.id, role='admin')
    db.session.add(admin_member)

    # Add other members
    member_ids = data.get('member_ids', [])
    for member_id in member_ids:
        if member_id != user.id:
            member = GroupMember(group_id=group.id, user_id=member_id)
            db.session.add(member)

    db.session.commit()
    return jsonify({'group': group.to_dict(include_members=True)}), 201


@groups_bp.route('/<int:group_id>', methods=['GET'])
@jwt_required_with_user
def get_group(user, group_id):
    group = db.session.get(Group, group_id)
    if not group:
        return jsonify({'error': 'Group not found'}), 404

    membership = GroupMember.query.filter_by(group_id=group_id, user_id=user.id).first()
    if not membership:
        return jsonify({'error': 'Not a member of this group'}), 403

    return jsonify({'group': group.to_dict(include_members=True)})


@groups_bp.route('/<int:group_id>', methods=['PUT'])
@jwt_required_with_user
def update_group(user, group_id):
    group = db.session.get(Group, group_id)
    if not group:
        return jsonify({'error': 'Group not found'}), 404

    membership = GroupMember.query.filter_by(group_id=group_id, user_id=user.id, role='admin').first()
    if not membership:
        return jsonify({'error': 'Only admins can update the group'}), 403

    data = request.get_json()
    if data.get('name'):
        group.name = data['name'].strip()
    if 'description' in data:
        group.description = data['description'].strip()

    db.session.commit()
    return jsonify({'group': group.to_dict(include_members=True)})


@groups_bp.route('/<int:group_id>/members', methods=['POST'])
@jwt_required_with_user
def add_member(user, group_id):
    group = db.session.get(Group, group_id)
    if not group:
        return jsonify({'error': 'Group not found'}), 404

    membership = GroupMember.query.filter_by(group_id=group_id, user_id=user.id, role='admin').first()
    if not membership:
        return jsonify({'error': 'Only admins can add members'}), 403

    data = request.get_json()
    user_id = data.get('user_id')

    existing = GroupMember.query.filter_by(group_id=group_id, user_id=user_id).first()
    if existing:
        return jsonify({'error': 'User is already a member'}), 409

    new_member = GroupMember(group_id=group_id, user_id=user_id)
    db.session.add(new_member)
    db.session.commit()

    return jsonify({'member': new_member.to_dict()}), 201


@groups_bp.route('/<int:group_id>/members/<int:member_user_id>', methods=['DELETE'])
@jwt_required_with_user
def remove_member(user, group_id, member_user_id):
    group = db.session.get(Group, group_id)
    if not group:
        return jsonify({'error': 'Group not found'}), 404

    # Allow admin to remove others, or user to leave
    if member_user_id != user.id:
        admin_check = GroupMember.query.filter_by(group_id=group_id, user_id=user.id, role='admin').first()
        if not admin_check:
            return jsonify({'error': 'Only admins can remove members'}), 403

    member = GroupMember.query.filter_by(group_id=group_id, user_id=member_user_id).first()
    if not member:
        return jsonify({'error': 'Member not found'}), 404

    db.session.delete(member)
    db.session.commit()
    return jsonify({'message': 'Member removed'})


@groups_bp.route('/<int:group_id>/messages', methods=['GET'])
@jwt_required_with_user
def get_group_messages(user, group_id):
    membership = GroupMember.query.filter_by(group_id=group_id, user_id=user.id).first()
    if not membership:
        return jsonify({'error': 'Not a member of this group'}), 403

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    per_page = min(per_page, 100)

    messages = Message.query.filter_by(group_id=group_id).order_by(
        Message.created_at.desc()
    ).paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'messages': [m.to_dict() for m in reversed(messages.items)],
        'total': messages.total,
        'page': messages.page,
        'pages': messages.pages,
    })


@groups_bp.route('/<int:group_id>', methods=['DELETE'])
@jwt_required_with_user
def delete_group(user, group_id):
    group = db.session.get(Group, group_id)
    if not group:
        return jsonify({'error': 'Group not found'}), 404

    if group.created_by != user.id:
        return jsonify({'error': 'Only the creator can delete the group'}), 403

    db.session.delete(group)
    db.session.commit()
    return jsonify({'message': 'Group deleted'})
