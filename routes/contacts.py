from flask import Blueprint, jsonify, request

from models import db
from models.contact import Contact
from models.user import User
from utils.auth import jwt_required_with_user

contacts_bp = Blueprint('contacts', __name__, url_prefix='/api/contacts')


@contacts_bp.route('', methods=['GET'])
@jwt_required_with_user
def get_contacts(user):
    contacts = Contact.query.filter_by(user_id=user.id, is_blocked=False).all()
    return jsonify({'contacts': [c.to_dict() for c in contacts]})


@contacts_bp.route('/users', methods=['GET'])
@jwt_required_with_user
def list_all_users(user):
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    search = request.args.get('q', '').strip()

    # Get IDs of existing contacts
    contact_ids = [c.contact_id for c in Contact.query.filter_by(user_id=user.id).all()]

    query = User.query.filter(User.id != user.id)

    if search:
        query = query.filter(
            (User.username.ilike(f'%{search}%')) | (User.display_name.ilike(f'%{search}%'))
        )

    pagination = query.order_by(User.display_name).paginate(
        page=page, per_page=per_page, error_out=False
    )

    users = []
    for u in pagination.items:
        user_dict = u.to_dict()
        user_dict['is_contact'] = u.id in contact_ids
        users.append(user_dict)

    return jsonify({
        'users': users,
        'total': pagination.total,
        'page': pagination.page,
        'pages': pagination.pages,
    })


@contacts_bp.route('/search', methods=['GET'])
@jwt_required_with_user
def search_users(user):
    query = request.args.get('q', '').strip()
    if len(query) < 2:
        return jsonify({'users': []})

    users = User.query.filter(
        User.id != user.id,
        (User.username.ilike(f'%{query}%') | User.display_name.ilike(f'%{query}%'))
    ).limit(20).all()

    return jsonify({'users': [u.to_dict() for u in users]})


@contacts_bp.route('', methods=['POST'])
@jwt_required_with_user
def add_contact(user):
    data = request.get_json()
    contact_id = data.get('contact_id')

    if not contact_id:
        return jsonify({'error': 'contact_id is required'}), 400

    if contact_id == user.id:
        return jsonify({'error': 'Cannot add yourself as contact'}), 400

    contact_user = db.session.get(User, contact_id)
    if not contact_user:
        return jsonify({'error': 'User not found'}), 404

    existing = Contact.query.filter_by(user_id=user.id, contact_id=contact_id).first()
    if existing:
        return jsonify({'error': 'Contact already exists'}), 409

    contact = Contact(user_id=user.id, contact_id=contact_id)
    db.session.add(contact)

    # Also add reverse contact
    reverse = Contact.query.filter_by(user_id=contact_id, contact_id=user.id).first()
    if not reverse:
        reverse_contact = Contact(user_id=contact_id, contact_id=user.id)
        db.session.add(reverse_contact)

    db.session.commit()
    return jsonify({'contact': contact.to_dict()}), 201


@contacts_bp.route('/<int:contact_id>', methods=['DELETE'])
@jwt_required_with_user
def remove_contact(user, contact_id):
    contact = Contact.query.filter_by(user_id=user.id, contact_id=contact_id).first()
    if not contact:
        return jsonify({'error': 'Contact not found'}), 404

    db.session.delete(contact)
    db.session.commit()
    return jsonify({'message': 'Contact removed'})


@contacts_bp.route('/<int:contact_id>/block', methods=['PUT'])
@jwt_required_with_user
def block_contact(user, contact_id):
    contact = Contact.query.filter_by(user_id=user.id, contact_id=contact_id).first()
    if not contact:
        return jsonify({'error': 'Contact not found'}), 404

    contact.is_blocked = True
    db.session.commit()
    return jsonify({'message': 'Contact blocked'})


@contacts_bp.route('/<int:contact_id>/unblock', methods=['PUT'])
@jwt_required_with_user
def unblock_contact(user, contact_id):
    contact = Contact.query.filter_by(user_id=user.id, contact_id=contact_id).first()
    if not contact:
        return jsonify({'error': 'Contact not found'}), 404

    contact.is_blocked = False
    db.session.commit()
    return jsonify({'message': 'Contact unblocked'})
