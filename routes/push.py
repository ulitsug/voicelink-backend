"""Push notification API routes — subscribe/unsubscribe endpoints."""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from models import db
from models.push_subscription import PushSubscription
from config import Config

push_bp = Blueprint('push', __name__, url_prefix='/api/push')


@push_bp.route('/subscribe', methods=['POST'])
@jwt_required()
def subscribe():
    user_id = get_jwt_identity()
    data = request.get_json()
    sub = data.get('subscription', {})

    endpoint = sub.get('endpoint')
    keys = sub.get('keys', {})
    p256dh = keys.get('p256dh')
    auth = keys.get('auth')

    if not endpoint or not p256dh or not auth:
        return jsonify({'error': 'Invalid subscription data'}), 400

    # Upsert: update if endpoint exists, otherwise create
    existing = PushSubscription.query.filter_by(user_id=user_id, endpoint=endpoint).first()
    if existing:
        existing.p256dh = p256dh
        existing.auth = auth
    else:
        new_sub = PushSubscription(
            user_id=user_id,
            endpoint=endpoint,
            p256dh=p256dh,
            auth=auth,
        )
        db.session.add(new_sub)

    db.session.commit()
    return jsonify({'status': 'subscribed'}), 200


@push_bp.route('/unsubscribe', methods=['POST'])
@jwt_required()
def unsubscribe():
    user_id = get_jwt_identity()
    data = request.get_json()
    endpoint = data.get('endpoint')

    if endpoint:
        PushSubscription.query.filter_by(user_id=user_id, endpoint=endpoint).delete()
    else:
        # Remove all subscriptions for this user
        PushSubscription.query.filter_by(user_id=user_id).delete()

    db.session.commit()
    return jsonify({'status': 'unsubscribed'}), 200


@push_bp.route('/vapid-key', methods=['GET'])
def vapid_key():
    """Return the public VAPID key so frontend can subscribe."""
    return jsonify({'public_key': Config.VAPID_PUBLIC_KEY}), 200
