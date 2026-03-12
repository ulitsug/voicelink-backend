from functools import wraps

from flask import jsonify
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request

from models import db
from models.user import User


def get_current_user():
    """Get the current authenticated user from JWT identity."""
    user_id = get_jwt_identity()
    return db.session.get(User, int(user_id))


def jwt_required_with_user(fn):
    """Decorator that provides the current user to the route function."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        verify_jwt_in_request()
        user = get_current_user()
        if not user:
            return jsonify({'error': 'User not found'}), 404
        return fn(user, *args, **kwargs)
    return wrapper
