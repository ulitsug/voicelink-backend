"""
Encryption utilities for E2E encrypted messaging.

Uses Web Crypto API on the frontend for key generation and encryption.
The backend only stores and relays encrypted data and public keys.
"""


def store_public_key(user, public_key_pem):
    """Store user's public key for E2E encryption key exchange."""
    user.public_key = public_key_pem


def get_public_key(user):
    """Retrieve user's public key."""
    return user.public_key
