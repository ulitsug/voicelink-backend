import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'voicelink-default-secret-key-2026')
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'voicelink-default-jwt-key-2026')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(seconds=int(os.getenv('JWT_ACCESS_TOKEN_EXPIRES', 315360000)))

    # MySQL via MAMP socket (Unix) or TCP/IP (Windows/TCP)
    DB_USER = os.getenv('DB_USERNAME', 'root')
    DB_PASS = os.getenv('DB_PASSWORD', 'root')
    DB_HOST = os.getenv('DB_HOST', '127.0.0.1')
    DB_PORT = os.getenv('DB_PORT', '3306')
    DB_NAME = os.getenv('DB_DATABASE', 'py_voip')
    DB_SOCKET = os.getenv('DB_SOCKET', '/Applications/MAMP/tmp/mysql/mysql.sock')

    # Build SQLAlchemy connection string (Windows uses TCP/IP, Unix can use socket)
    _base_uri = f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    SQLALCHEMY_DATABASE_URI = (
        _base_uri if not os.path.exists(DB_SOCKET)
        else f"{_base_uri}?unix_socket={DB_SOCKET}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Server
    SERVER_HOST = os.getenv('SERVER_HOST', '0.0.0.0')
    SERVER_PORT = int(os.getenv('SERVER_PORT', 5001))

    # Upload settings
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB max file upload
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')

    # TURN server
    TURN_SERVER_HOST = os.getenv('TURN_SERVER_HOST', '10.10.23.228')
    TURN_SERVER_PORT = int(os.getenv('TURN_SERVER_PORT', 3478))
    TURN_USERNAME = os.getenv('TURN_USERNAME', 'voicelink')
    TURN_PASSWORD = os.getenv('TURN_PASSWORD', 'voicelink2026')

    # VAPID keys for Web Push notifications
    VAPID_PRIVATE_KEY = os.getenv(
        'VAPID_PRIVATE_KEY',
        '-----BEGIN PRIVATE KEY-----\n'
        'MIGHAgEAMBMGByqGSM49AgEGCCqGSM49AwEHBG0wawIBAQQgmO1xeONqBW6GQYG9\n'
        'tt7KiGv7qsTjEy94D5SBsHFEO5GhRANCAAS6GGoJhl+DVyLnCyY6hZSEY0aOeJMP\n'
        '2LjCBf1/7MbPJl5WSGKIAQCj2vUG+r8CzFiHzBg6+VLIHbHjBDN0hDH8\n'
        '-----END PRIVATE KEY-----\n'
    )
    VAPID_PUBLIC_KEY = os.getenv(
        'VAPID_PUBLIC_KEY',
        'BLoYagmGX4NXIucLJjqFlIRjRo54kw_YuMIF_X_sxs8mXlZIYogBAKPa9Qb6vwLMWIfMGDr5UsgdseMEM3SEMfw'
    )
    VAPID_CLAIMS_EMAIL = os.getenv('VAPID_CLAIMS_EMAIL', 'mailto:admin@voicelink.local')
