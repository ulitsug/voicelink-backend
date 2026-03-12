import os
import socket

from flask import Flask
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_migrate import Migrate
from flask_socketio import SocketIO

from config import Config
from models import db
from sockets import register_socket_events

# Initialize extensions
migrate = Migrate()
jwt = JWTManager()
socketio = SocketIO(cors_allowed_origins="*", async_mode='eventlet')


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
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

    app.register_blueprint(auth_bp)
    app.register_blueprint(contacts_bp)
    app.register_blueprint(calls_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(groups_bp)
    app.register_blueprint(calendar_bp)

    # Register SocketIO events
    register_socket_events(socketio)

    @app.route('/')
    def index():
        return {'status': 'ok', 'service': 'VoiceLink API', 'version': '1.0'}

    # Create tables if they don't exist
    with app.app_context():
        db.create_all()

    return app


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
        certfile=cert_path if ssl_context else None,
        keyfile=key_path if ssl_context else None,
    )
