# VoiceLink — Backend API

Real-time communication platform backend built with **Flask**, **Flask-SocketIO**, and **MySQL**. Provides REST APIs and WebSocket events for voice/video calling (WebRTC), real-time chat, contacts, groups, and calendar scheduling.

> **Frontend repo:** [voicelink-frontend](https://github.com/mubahood/voicelink-frontend)

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Framework | Flask 3.0 |
| Real-time | Flask-SocketIO 5.3 (eventlet) |
| Database | MySQL via PyMySQL |
| ORM | Flask-SQLAlchemy + Flask-Migrate |
| Auth | JWT (Flask-JWT-Extended) — bcrypt password hashing |
| WebRTC Relay | STUN/TURN via coturn |

## Features

- **Authentication** — Register, login, JWT tokens, profile management, avatar upload
- **Contacts** — Add/remove/block contacts, user search & discovery
- **Real-time Chat** — Direct & group messaging, file/image upload, typing indicators, read receipts
- **Voice & Video Calls** — WebRTC signaling (offer/answer/ICE), call logging, screen sharing
- **Groups** — Create/manage groups, group chat, group calls, role-based permissions
- **Calendar** — Event scheduling with participants, RSVP (accept/decline), reminders
- **Presence** — Online/offline status tracking via Socket.IO heartbeats
- **E2E Encryption** — Public key exchange support (encryption handled client-side)

## Project Structure

```
backend/
├── app.py                  # Flask app factory + server entry point
├── config.py               # Configuration (DB, JWT, TURN, uploads)
├── requirements.txt        # Python dependencies
├── .env.example            # Environment variable template
├── start_turn.sh           # coturn TURN server launcher
├── turnserver.conf         # coturn configuration
├── models/
│   ├── __init__.py         # SQLAlchemy init + model imports
│   ├── user.py             # User model
│   ├── contact.py          # Contact model
│   ├── message.py          # Message model
│   ├── call_log.py         # CallLog model
│   ├── group.py            # Group + GroupMember models
│   └── calendar_event.py   # CalendarEvent + EventParticipant models
├── routes/
│   ├── auth.py             # /api/auth/* — register, login, profile
│   ├── contacts.py         # /api/contacts/* — CRUD, search, block
│   ├── calls.py            # /api/calls/* — ICE config, call history
│   ├── chat.py             # /api/chat/* — messages, files, conversations
│   ├── groups.py           # /api/groups/* — CRUD, members, group messages
│   └── calendar_routes.py  # /api/calendar/* — events, RSVP
├── sockets/
│   ├── __init__.py         # Socket event registration
│   ├── presence_events.py  # Authentication, online/offline tracking
│   ├── call_events.py      # WebRTC call signaling
│   └── chat_events.py      # Real-time messaging events
└── utils/
    ├── auth.py             # jwt_required_with_user decorator
    └── encryption.py       # E2E key storage utility
```

## API Reference

### Auth (`/api/auth`)

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `POST` | `/register` | No | Create account |
| `POST` | `/login` | No | Login (username or email) |
| `GET` | `/me` | Yes | Get current user profile |
| `PUT` | `/update-profile` | Yes | Update display name, bio, avatar, public key |
| `PUT` | `/change-password` | Yes | Change password |
| `POST` | `/upload-avatar` | Yes | Upload avatar image |
| `DELETE` | `/remove-avatar` | Yes | Remove avatar |
| `GET` | `/dashboard-stats` | Yes | Dashboard statistics |

### Contacts (`/api/contacts`)

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `GET` | `/` | Yes | List user's contacts |
| `GET` | `/users` | Yes | List all users (paginated) |
| `GET` | `/search?q=` | Yes | Search users |
| `POST` | `/` | Yes | Add contact (bi-directional) |
| `DELETE` | `/<contact_id>` | Yes | Remove contact |
| `PUT` | `/<contact_id>/block` | Yes | Block contact |
| `PUT` | `/<contact_id>/unblock` | Yes | Unblock contact |

### Chat (`/api/chat`)

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `GET` | `/messages/<user_id>` | Yes | Get DM messages (paginated) |
| `POST` | `/messages` | Yes | Send message |
| `POST` | `/upload` | Yes | Upload file attachment |
| `GET` | `/files/<filename>` | No | Serve uploaded file |
| `GET` | `/unread` | Yes | Unread counts per sender |
| `GET` | `/conversations` | Yes | All conversations with last message |

### Calls (`/api/calls`)

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `GET` | `/ice-config` | Yes | STUN/TURN ICE server configuration |
| `GET` | `/history` | Yes | Call history (paginated) |
| `POST` | `/log` | Yes | Create call log |
| `PUT` | `/log/<call_id>` | Yes | Update call log |

### Groups (`/api/groups`)

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `GET` | `/` | Yes | List user's groups |
| `POST` | `/` | Yes | Create group |
| `GET` | `/<id>` | Yes | Get group details |
| `PUT` | `/<id>` | Yes | Update group (admin) |
| `DELETE` | `/<id>` | Yes | Delete group (creator) |
| `POST` | `/<id>/members` | Yes | Add member (admin) |
| `DELETE` | `/<id>/members/<uid>` | Yes | Remove member |
| `GET` | `/<id>/messages` | Yes | Group messages (paginated) |

### Calendar (`/api/calendar`)

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `GET` | `/events` | Yes | List user's events |
| `POST` | `/events` | Yes | Create event with participants |
| `PUT` | `/events/<id>` | Yes | Update event (creator) |
| `DELETE` | `/events/<id>` | Yes | Delete event (creator) |
| `PUT` | `/events/<id>/respond` | Yes | Accept/decline event |

## Socket.IO Events

### Presence
- `authenticate` → `authenticated` / `auth_error`
- `get_online_users` → `online_users`
- `heartbeat` → `heartbeat_ack`
- Server broadcasts: `user_status_changed`

### Chat
- `send_message` → `new_message` / `message_sent`
- `typing` → `user_typing`
- `mark_read` → `messages_read`
- `join_group_room` / `leave_group_room`

### Calls (WebRTC Signaling)
- `call_user` → `incoming_call`
- `call_accepted` / `call_rejected`
- `ice_candidate` (relay)
- `end_call` → `call_ended`
- `renegotiate_offer` / `renegotiate_answer`
- `screen_share_started` / `screen_share_stopped`

## Database Models

| Model | Table | Key Fields |
|-------|-------|------------|
| User | `users` | username, email, password_hash, display_name, bio, avatar_url, status, public_key |
| Contact | `contacts` | user_id, contact_id, nickname, is_blocked |
| Message | `messages` | sender_id, receiver_id, group_id, content, message_type, file_url, is_read |
| CallLog | `call_logs` | caller_id, callee_id, call_type, status, duration |
| Group | `groups` | name, description, created_by |
| GroupMember | `group_members` | group_id, user_id, role (admin/member) |
| CalendarEvent | `calendar_events` | title, user_id, event_type, scheduled_at, duration_minutes |
| EventParticipant | `event_participants` | event_id, user_id, status (pending/accepted/declined) |

## Getting Started

### Prerequisites

- Python 3.10+
- MySQL (via MAMP, MySQL Server, or Docker)
- SSL certificates for HTTPS (optional but recommended for WebRTC)

### Installation

```bash
# Clone the repository
git clone https://github.com/mubahood/voicelink-backend.git
cd voicelink-backend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your database credentials and secrets
```

### Database Setup

```bash
# Create the MySQL database
mysql -u root -p -e "CREATE DATABASE py_voip;"

# Tables are auto-created on first run via SQLAlchemy
```

### Generate SSL Certificates (optional)

```bash
# Self-signed cert for local development
openssl req -x509 -newkey rsa:4096 -keyout ../key.pem -out ../cert.pem -days 365 -nodes
```

### Run

```bash
source venv/bin/activate
python app.py
```

The server starts on `https://localhost:5001` (with SSL) or `http://localhost:5001` (without).

### TURN Server (for WebRTC behind NAT)

```bash
# Install coturn
brew install coturn  # macOS
# sudo apt install coturn  # Ubuntu

# Start with included config
bash start_turn.sh
```

## License

MIT
