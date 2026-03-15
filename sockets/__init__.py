from sockets.presence_events import register_presence_events
from sockets.call_events import register_call_events
from sockets.chat_events import register_chat_events


def register_socket_events(socketio, app=None):
    """Register all SocketIO event handlers."""
    register_presence_events(socketio, app)
    register_call_events(socketio)
    register_chat_events(socketio)
