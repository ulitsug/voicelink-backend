import os
import socket

from flask import Flask
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_socketio import SocketIO

from config import Config
from models import db
from sockets import register_socket_events

# Initialize extensions
jwt = JWTManager()
socketio = SocketIO(cors_allowed_origins="*", async_mode='threading')


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Initialize extensions
    db.init_app(app)
    jwt.init_app(app)
    CORS(app, resources={r"/api/*": {"origins": "*"}})
    socketio.init_app(app)

    # Ensure upload directory exists
    os.makedirs(app.config.get('UPLOAD_FOLDER', 'uploads'), exist_ok=True)

    # Register blueprints
    from routes.auth import auth_bp
    from routes.contacts import contacts_bp
    from routes.calls import calls_bp
    from routes.chat import chat_bp
    from routes.groups import groups_bp
    from routes.calendar_routes import calendar_bp
    from routes.admin import admin_bp
    from routes.push import push_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(contacts_bp)
    app.register_blueprint(calls_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(groups_bp)
    app.register_blueprint(calendar_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(push_bp)

    # Register SocketIO events
    register_socket_events(socketio)

    @app.route('/')
    def index():
        return {'status': 'ok', 'service': 'VoiceLink API', 'version': '1.0'}

    # Seed super admin if not present (schema is managed by migrate.py)
    with app.app_context():
        _seed_super_admin()

    return app


def _seed_super_admin():
    """Ensure user id=1 exists as the undeletable super admin."""
    from models.user import User

    admin = db.session.get(User, 1)
    if admin:
        # Ensure existing user 1 is super_admin with correct credentials
        if admin.role != 'super_admin' or admin.username != 'admin':
            admin.username = 'admin'
            admin.email = 'admin@voicelink.local'
            admin.display_name = 'System Admin'
            admin.role = 'super_admin'
            admin.email_verified = True
            admin.set_password('4321')
            db.session.commit()
            print('🔑 Super admin credentials reset (username: admin, password: 4321)')
        elif not admin.email_verified:
            admin.email_verified = True
            db.session.commit()
    else:
        admin = User(
            id=1,
            username='admin',
            email='admin@voicelink.local',
            display_name='System Admin',
            role='super_admin',
            email_verified=True,
        )
        admin.set_password('4321')
        db.session.add(admin)
        db.session.commit()
        print('🔑 Super admin created (username: admin, password: 4321)')


app = create_app()


if __name__ == '__main__':
    # Get local IP address
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        local_ip = s.getsockname()[0]
    except Exception:
        local_ip = '127.0.0.1'
    finally:
        s.close()

    port = Config.SERVER_PORT

    print('=' * 70)
    print('🚀 VoiceLink Server Starting...')
    print(f'   Backend API:     http://127.0.0.1:{port}/api')
    print(f'   Network access:  http://{local_ip}:{port}/api')
    print(f'   Frontend:        http://localhost:3000')
    print(f'   Database:        MySQL (py_voip)')
    print('=' * 70)

    # Check for SSL certificates
    cert_path = os.path.join(os.path.dirname(__file__), '..', 'cert.pem')
    key_path = os.path.join(os.path.dirname(__file__), '..', 'key.pem')

    ssl_context = None
    if os.path.exists(cert_path) and os.path.exists(key_path):
        ssl_context = (cert_path, key_path)
        print('🔒 SSL enabled')

    socketio.run(
        app,
        debug=True,
        use_reloader=False,
        host=Config.SERVER_HOST,
        port=port,
        ssl_context=ssl_context,
    )
