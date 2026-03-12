# VoiceLink — Backend API

Real-time communication platform backend built with **Flask**, **Flask-SocketIO**, and **MySQL**. Provides REST APIs and WebSocket events for voice/video calling (WebRTC), real-time chat, contacts, groups, calendar scheduling, push notifications, and admin management.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Framework | Flask 3.0 |
| Real-time | Flask-SocketIO 5.3 (eventlet) |
| Database | MySQL 5.7+ via PyMySQL |
| ORM | Flask-SQLAlchemy |
| Migrations | Custom Laravel-like system (`migrate.py`) |
| Auth | JWT (Flask-JWT-Extended) + bcrypt |
| WebRTC Relay | STUN/TURN via coturn |
| Push Notifications | Web Push API via pywebpush + py-vapid |

## Features

- **Authentication** — Register, login, JWT tokens, profile management, avatar upload
- **Contacts** — Add/remove/block contacts, user search & discovery
- **Real-time Chat** — Direct & group messaging, file/image upload, typing indicators, read receipts
- **Voice & Video Calls** — WebRTC signaling (offer/answer/ICE), call logging, screen sharing, renegotiation
- **Groups** — Create/manage groups, group chat, group calls, role-based permissions (admin/member)
- **Calendar** — Event scheduling with participants, RSVP (accept/decline), recurring events
- **Presence** — Online/offline status tracking via Socket.IO heartbeats
- **Push Notifications** — Web Push for incoming calls and messages (no Firebase)
- **Admin Panel** — User management, system stats, dynamic configuration
- **E2E Encryption** — Public key exchange support (encryption handled client-side)

## Project Structure

```
backend/
├── app.py                          # Flask app factory + server entry point
├── config.py                       # Configuration (DB, JWT, TURN, VAPID, uploads)
├── migrate.py                      # Database migration CLI manager
├── requirements.txt                # Python dependencies
├── .env                            # Environment variables (local, git-ignored)
├── .env.example                    # Environment variable template
├── start_turn.sh                   # coturn TURN server launcher
├── turnserver.conf                 # coturn configuration
│
├── database/
│   ├── migrations/                 # Versioned database migration files
│   │   ├── 2026_03_13_000001_create_users_table.py
│   │   ├── 2026_03_13_000002_create_contacts_table.py
│   │   ├── 2026_03_13_000003_create_groups_tables.py
│   │   ├── 2026_03_13_000004_create_messages_table.py
│   │   ├── 2026_03_13_000005_create_call_logs_table.py
│   │   ├── 2026_03_13_000006_create_calendar_events_tables.py
│   │   ├── 2026_03_13_000007_create_push_subscriptions_table.py
│   │   └── 2026_03_13_000008_create_system_config_table.py
│   └── seeders/
│       └── seeder.py               # Default data seeder (admin user, config)
│
├── models/
│   ├── __init__.py                 # SQLAlchemy init + model imports
│   ├── user.py                     # User model
│   ├── contact.py                  # Contact model
│   ├── message.py                  # Message model
│   ├── call_log.py                 # CallLog model
│   ├── group.py                    # Group + GroupMember models
│   ├── calendar_event.py           # CalendarEvent + EventParticipant models
│   ├── push_subscription.py        # PushSubscription model
│   └── system_config.py            # SystemConfig model
│
├── routes/
│   ├── auth.py                     # /api/auth/*     — register, login, profile
│   ├── contacts.py                 # /api/contacts/* — CRUD, search, block
│   ├── calls.py                    # /api/calls/*    — ICE config, call history
│   ├── chat.py                     # /api/chat/*     — messages, files, conversations
│   ├── groups.py                   # /api/groups/*   — CRUD, members, group chat
│   ├── calendar_routes.py          # /api/calendar/* — events, RSVP
│   ├── admin.py                    # /api/admin/*    — admin dashboard, user mgmt
│   └── push.py                     # /api/push/*     — push subscriptions, VAPID key
│
├── sockets/
│   ├── __init__.py                 # Socket event registration
│   ├── presence_events.py          # Authentication, online/offline tracking
│   ├── call_events.py              # WebRTC call signaling
│   └── chat_events.py              # Real-time messaging events
│
├── services/
│   └── push_service.py             # Web Push notification sender
│
└── uploads/                        # User-uploaded files (git-ignored)
    └── avatars/                    # Avatar images
```

---

## Getting Started

### Prerequisites

- **Python** 3.10 or higher
- **MySQL** 5.7+ (via MAMP, MySQL Server, MariaDB, or Docker)
- **SSL certificates** for HTTPS (required for WebRTC on non-localhost)
- **coturn** (optional, for TURN relay behind NAT)

### 1. Clone & Setup

```bash
git clone <repository-url>
cd backend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate          # macOS/Linux
# venv\Scripts\activate           # Windows

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your settings:

| Variable | Required | Description |
|----------|----------|-------------|
| `SECRET_KEY` | Yes | Flask secret key for sessions |
| `JWT_SECRET_KEY` | Yes | Key for signing JWT tokens |
| `DB_HOST` | Yes | MySQL host (default: 127.0.0.1) |
| `DB_PORT` | Yes | MySQL port (default: 3306) |
| `DB_DATABASE` | Yes | Database name (default: py_voip) |
| `DB_USERNAME` | Yes | Database user (default: root) |
| `DB_PASSWORD` | Yes | Database password |
| `DB_SOCKET` | No | Unix socket path (MAMP: `/Applications/MAMP/tmp/mysql/mysql.sock`) |
| `SERVER_HOST` | No | Bind address (default: 0.0.0.0) |
| `SERVER_PORT` | No | Server port (default: 5001) |
| `TURN_SERVER_HOST` | No | TURN server IP for WebRTC |
| `TURN_SERVER_PORT` | No | TURN port (default: 3478) |
| `TURN_USERNAME` | No | TURN auth username |
| `TURN_PASSWORD` | No | TURN auth password |
| `VAPID_PUBLIC_KEY` | No | VAPID public key for Web Push |
| `VAPID_PRIVATE_KEY` | No | VAPID private key (PEM format) |
| `VAPID_CLAIMS_EMAIL` | No | Contact email for VAPID (mailto:...) |

### 3. Database Setup

```bash
# Create the MySQL database
mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS py_voip CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

# Initialize migration system
python migrate.py init

# Run all migrations to create tables
python migrate.py migrate

# Seed default data (super admin + config)
python migrate.py seed
```

### 4. Generate SSL Certificates

Required for WebRTC to work on non-localhost connections:

```bash
# Generate self-signed certificate (place in project root, one level above backend/)
cd ..
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes \
  -subj "/C=US/ST=Local/L=Network/O=VoiceLink/CN=voicelink.local"
cd backend
```

### 5. Run the Server

```bash
source venv/bin/activate
python app.py
```

Output:
```
======================================================================
  VoiceLink Server Starting...
   Backend API:     https://127.0.0.1:5001/api
   Network access:  https://<your-ip>:5001/api
   Frontend:        https://localhost:3000
   Database:        MySQL (py_voip)
======================================================================
  SSL enabled
```

### 6. TURN Server (Optional)

For WebRTC calls through NAT/firewalls:

```bash
# Install coturn
brew install coturn          # macOS
# sudo apt install coturn    # Ubuntu/Debian

# Start with included config
bash start_turn.sh
```

---

## Migration System

VoiceLink includes a **Laravel-like migration manager** (`migrate.py`) for version-controlled database schema management.

> **⚠️ IMPORTANT: Database Change Policy**
>
> **ALL database schema modifications MUST go through the migration system.** Direct manual changes to the database (via SQL clients, raw queries in code, or `db.create_all()`) are **strictly prohibited** in development and production.
>
> This includes:
> - Creating new tables
> - Adding, renaming, or dropping columns
> - Modifying column types, defaults, or constraints
> - Adding or removing indexes and foreign keys
> - Inserting default/seed data
>
> See the [Database Change Policy](#database-change-policy) section for full details.

### Commands

| Command | Description |
|---------|-------------|
| `python migrate.py init` | Initialize the migration system (creates DB + tracking table) |
| `python migrate.py make <name>` | Create a new migration file |
| `python migrate.py migrate` | Run all pending migrations |
| `python migrate.py rollback` | Rollback the last batch of migrations |
| `python migrate.py rollback --steps=N` | Rollback N batches |
| `python migrate.py status` | Show status of all migrations |
| `python migrate.py reset` | Rollback all, then re-run all migrations |
| `python migrate.py fresh` | Drop ALL tables, re-run all migrations (destructive) |
| `python migrate.py seed` | Run database seeders (admin user, default config) |

### Creating a New Migration

```bash
python migrate.py make add_phone_to_users
```

This creates a timestamped file in `database/migrations/`:
```
database/migrations/2026_03_13_143022_add_phone_to_users.py
```

Each migration has `up(conn)` and `down(conn)` functions:

```python
def up(conn):
    with conn.cursor() as cur:
        cur.execute("ALTER TABLE users ADD COLUMN phone VARCHAR(20) DEFAULT NULL")
    conn.commit()

def down(conn):
    with conn.cursor() as cur:
        cur.execute("ALTER TABLE users DROP COLUMN phone")
    conn.commit()
```

### Migration Tracking

Migrations are tracked in a `migrations` table with batch numbering. Each `migrate` run creates a new batch, allowing targeted rollbacks.

---

## Database Schema

### Tables

| Table | Description |
|-------|-------------|
| `users` | User accounts, authentication, profiles |
| `contacts` | User-to-user contact relationships |
| `groups` | Communication groups |
| `group_members` | Group membership with roles (admin/member) |
| `messages` | Direct and group messages (text, files, encrypted) |
| `call_logs` | Voice/video call history and duration tracking |
| `calendar_events` | Scheduled events and calls |
| `event_participants` | Event invitation responses (pending/accepted/declined) |
| `push_subscriptions` | Web Push notification endpoint subscriptions |
| `system_config` | Dynamic key-value application configuration |
| `migrations` | Migration version tracking (auto-managed) |

### Entity Relationships

```
users ─┬── contacts (user_id, contact_id)
       ├── messages (sender_id, receiver_id)
       ├── call_logs (caller_id, callee_id)
       ├── groups (created_by) ─── group_members (group_id, user_id)
       │                      └── messages (group_id)
       ├── calendar_events (user_id) ─── event_participants (event_id, user_id)
       ├── push_subscriptions (user_id)
       └── system_config (system-level, no FK)
```

---

## API Reference

All endpoints use JSON request/response bodies unless noted. Authentication uses Bearer JWT tokens in the `Authorization` header.

### Auth — `/api/auth`

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `POST` | `/register` | No | Register new user. Body: `{username, email, password, display_name}`. Returns `{user, access_token}` (201) |
| `POST` | `/login` | No | Login. Body: `{username, password}` (username accepts email). Returns `{user, access_token}` |
| `GET` | `/me` | JWT | Get current user profile |
| `PUT` | `/update-profile` | JWT | Update profile. Body: `{display_name?, bio?, avatar_url?, public_key?}` |
| `PUT` | `/change-password` | JWT | Change password. Body: `{current_password, new_password}` (min 6 chars) |
| `POST` | `/upload-avatar` | JWT | Upload avatar (multipart, jpg/png/gif/webp). Returns `{avatar_url}` |
| `DELETE` | `/remove-avatar` | JWT | Remove avatar image |
| `GET` | `/avatars/<filename>` | No | Serve static avatar file |
| `GET` | `/dashboard-stats` | JWT | Dashboard stats: contacts, groups, unread, calls, recent contacts |

### Contacts — `/api/contacts`

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `GET` | `/` | JWT | List all non-blocked contacts |
| `GET` | `/users` | JWT | All users (paginated). Query: `?page=&per_page=&q=` |
| `GET` | `/search?q=` | JWT | Search users by name (min 2 chars, limit 20) |
| `POST` | `/` | JWT | Add contact. Body: `{contact_id}`. Creates bidirectional (201) |
| `DELETE` | `/<contact_id>` | JWT | Remove contact (one-way) |
| `PUT` | `/<contact_id>/block` | JWT | Block contact |
| `PUT` | `/<contact_id>/unblock` | JWT | Unblock contact |

### Chat — `/api/chat`

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `GET` | `/messages/<user_id>` | JWT | Paginated DM history. Auto-marks as read. Query: `?page=&per_page=` |
| `POST` | `/messages` | JWT | Send message. Body: `{receiver_id?, group_id?, content?, message_type?}` (201) |
| `POST` | `/upload` | JWT | Upload file attachment (multipart). Returns `{file_url, file_name, file_size}` |
| `GET` | `/files/<filename>` | No | Serve uploaded file |
| `GET` | `/unread` | JWT | Unread message counts grouped by sender |
| `GET` | `/conversations` | JWT | All conversations with last message, user info, unread count |

### Calls — `/api/calls`

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `GET` | `/ice-config` | JWT | STUN/TURN ICE server config (URLs, credentials) |
| `GET` | `/history` | JWT | Paginated call history. Query: `?page=&per_page=` (max 100) |
| `POST` | `/log` | JWT | Create call log. Body: `{callee_id, group_id?, call_type?}` (201) |
| `PUT` | `/log/<call_id>` | JWT | Update call status. Body: `{status}` (auto-sets timestamps) |

### Groups — `/api/groups`

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `GET` | `/` | JWT | List user's groups with member info |
| `POST` | `/` | JWT | Create group. Body: `{name, description?, member_ids?[]}` (201) |
| `GET` | `/<id>` | JWT | Group details (must be member) |
| `PUT` | `/<id>` | JWT | Update group (admin only). Body: `{name?, description?}` |
| `DELETE` | `/<id>` | JWT | Delete group (creator only) |
| `POST` | `/<id>/members` | JWT | Add member (admin). Body: `{user_id}` (201) |
| `DELETE` | `/<id>/members/<uid>` | JWT | Remove member (admin) or leave group (self) |
| `GET` | `/<id>/messages` | JWT | Paginated group messages (must be member) |

### Calendar — `/api/calendar`

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `GET` | `/events` | JWT | Events created by user or as participant |
| `POST` | `/events` | JWT | Create event. Body: `{title, scheduled_at, participant_ids?[], ...}` (201) |
| `PUT` | `/events/<id>` | JWT | Update event (creator only) |
| `DELETE` | `/events/<id>` | JWT | Delete event (creator only) |
| `PUT` | `/events/<id>/respond` | JWT | RSVP. Body: `{status}` (`accepted` or `declined`) |

### Admin — `/api/admin` (admin role required)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/dashboard` | Dashboard totals (users, messages, calls, groups, today's stats) |
| `GET` | `/system-info` | Server info (hostname, IP, platform, python, DB config) |
| `GET` | `/config` | List all dynamic system config entries |
| `PUT` | `/config` | Upsert config. Body: `{key, value, description?}` |
| `DELETE` | `/config/<key>` | Delete config entry |
| `GET` | `/users` | Paginated user list. Query: `?page=&per_page=&q=&role=` |
| `POST` | `/users` | Create user. Body: `{username, email, password, display_name, role?}` (201) |
| `GET` | `/users/<id>` | User detail + stats (contacts, messages, calls, groups) |
| `PUT` | `/users/<id>` | Update user (cannot modify super_admin unless you are one) |
| `DELETE` | `/users/<id>` | Delete user + all data (cannot delete self or super_admin) |
| `GET` | `/stats/messages` | Message stats: total, today, by_type |
| `GET` | `/stats/calls` | Call stats: total, today, by_status, by_type, avg_duration |

### Push — `/api/push`

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `POST` | `/subscribe` | JWT | Subscribe to push. Body: `{subscription: {endpoint, keys: {p256dh, auth}}}` |
| `POST` | `/unsubscribe` | JWT | Unsubscribe. Body: `{endpoint?}` (no endpoint = remove all) |
| `GET` | `/vapid-key` | No | Returns `{public_key}` for client Push API subscription |

### Health Check

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Returns `{status: "ok", service: "VoiceLink API", version: "1.0"}` |

---

## Socket.IO Events

Connect via Socket.IO client to the server URL. After connecting, emit `authenticate` with a JWT token.

### Presence Events

| Event | Direction | Data | Description |
|-------|-----------|------|-------------|
| `authenticate` | client → server | `{token}` | Authenticate socket with JWT. Joins personal room |
| `authenticated` | server → client | `{user, online_users[]}` | Auth success with current user + online list |
| `auth_error` | server → client | `{error}` | Auth failure message |
| `user_status_changed` | server → all | `{user_id, status, username}` | Broadcast when user goes online/offline |
| `get_online_users` | client → server | — | Request online user list |
| `online_users` | server → client | `{users[]}` | Response with online users |
| `heartbeat` | client → server | — | Keep-alive ping |
| `heartbeat_ack` | server → client | `{status, user_id}` | Keep-alive response |

### Chat Events

| Event | Direction | Data | Description |
|-------|-----------|------|-------------|
| `send_message` | client → server | `{receiver_id?, group_id?, content?, message_type?, file_url?, ...}` | Send message (saves to DB, delivers real-time) |
| `new_message` | server → client | message object | New message delivered to recipient |
| `message_sent` | server → client | message object | Confirmation back to sender |
| `typing` | client → server | `{receiver_id?, group_id?, is_typing}` | Typing indicator |
| `user_typing` | server → client | `{user_id, is_typing}` | Forwarded typing status |
| `mark_read` | client → server | `{sender_id}` | Mark all messages from sender as read |
| `messages_read` | server → client | `{reader_id}` | Notify sender their messages were read |
| `join_group_room` | client → server | `{group_id}` | Join group socket room |
| `leave_group_room` | client → server | `{group_id}` | Leave group socket room |

### Call Events (WebRTC Signaling)

| Event | Direction | Data | Description |
|-------|-----------|------|-------------|
| `call_user` | client → server | `{target_id, call_type?, offer?, call_id?}` | Initiate call (checks availability, sends push) |
| `incoming_call` | server → client | `{caller_id, caller, call_type, offer, call_id}` | Incoming call notification |
| `call_accepted` | client → server | `{caller_id, answer?, call_id?}` | Accept call |
| `call_accepted` | server → client | `{callee_id, callee, answer, call_id}` | Call accepted by callee |
| `call_rejected` | bidirectional | `{caller_id or from_id, call_id}` | Reject call |
| `ice_candidate` | bidirectional | `{target_id, candidate}` / `{candidate, from_id}` | ICE candidate relay |
| `end_call` | client → server | `{target_id, call_id?}` | End active call |
| `call_ended` | server → client | `{from_id, call_id}` | Call ended notification |
| `call_error` | server → client | `{error}` | Call setup error (offline, busy, etc.) |
| `renegotiate_offer` | bidirectional | `{target_id, offer}` / `{from_id, offer}` | Mid-call renegotiation offer |
| `renegotiate_answer` | bidirectional | `{target_id, answer}` / `{from_id, answer}` | Mid-call renegotiation answer |
| `screen_share_started` | bidirectional | `{target_id}` / `{from_id}` | Screen share began |
| `screen_share_stopped` | bidirectional | `{target_id}` / `{from_id}` | Screen share ended |
| `group_call_initiate` | client → server | `{participant_ids[], group_id?, call_type?}` | Start group call |
| `group_call_invite` | server → client | `{caller_id, caller, group_id, call_type, participants[]}` | Group call invitation |
| `group_call_join` | client → server | `{participant_ids[], offer?}` | Join group call |
| `group_call_peer_joined` | server → client | `{user_id, user, offer}` | Peer joined group call |

---

## Default Credentials

After running `python migrate.py seed`:

| Field | Value |
|-------|-------|
| Username | `admin` |
| Password | `4321` |
| Role | `super_admin` |

---

## Database Change Policy

**All database schema modifications MUST be performed through the migration system (`migrate.py`).** This is a strict project convention — no exceptions.

### Why?

- **Version control** — Every schema change is recorded in a timestamped migration file, providing a complete audit trail of how the database evolved.
- **Reproducibility** — Any developer (or CI/CD pipeline) can recreate the exact database schema from scratch by running `python migrate.py fresh`.
- **Rollback safety** — Every migration has a `down()` function, allowing changes to be safely reversed if something goes wrong.
- **Team collaboration** — Migration files are committed to git. Teammates pull changes and run `python migrate.py migrate` to stay in sync — no manual SQL needed.
- **Deployment consistency** — Production, staging, and development databases all share the same schema history, eliminating drift.

### Rules

1. **NEVER modify the database directly.** Do not use phpMyAdmin, MySQL Workbench, the `mysql` CLI, or any other tool to alter tables, columns, indexes, or data in a way that affects the schema.

2. **NEVER use `db.create_all()` for schema creation.** The Flask-SQLAlchemy `db.create_all()` call in `app.py` exists only as a safety net — it does **not** replace migrations. Models alone do not track schema changes over time.

3. **NEVER add raw `ALTER TABLE` or `CREATE TABLE` statements in route handlers, socket events, or application code.** Schema changes belong in migration files only.

4. **ALWAYS create a migration file** for any of the following changes:
   - Creating a new table
   - Adding, renaming, or removing a column
   - Changing a column's type, default value, or nullability
   - Adding or dropping indexes, unique constraints, or foreign keys
   - Modifying table options (engine, charset, collation)

5. **ALWAYS update the corresponding SQLAlchemy model** when you create a migration. The model in `models/` must match what the migration creates — they must stay in sync.

6. **ALWAYS test migrations locally** before committing:
   ```bash
   python migrate.py migrate     # Apply your new migration
   python migrate.py rollback    # Verify rollback works
   python migrate.py migrate     # Re-apply to confirm idempotency
   ```

7. **NEVER edit a migration file that has already been run** on any environment (including by teammates). If you need to change something, create a new migration that alters the previous result.

8. **Use the seeder for default data**, not migrations. Migrations are for schema; seeders (`database/seeders/seeder.py`) are for initial data.

### Workflow: Adding a New Feature That Needs Schema Changes

```bash
# Step 1: Create a migration file
python migrate.py make add_phone_number_to_users

# Step 2: Edit the generated file in database/migrations/
#         Implement up() and down() functions with raw SQL

# Step 3: Update the SQLAlchemy model to match
#         e.g., add `phone = db.Column(db.String(20))` to models/user.py

# Step 4: Apply the migration
python migrate.py migrate

# Step 5: Verify
python migrate.py status

# Step 6: Test rollback
python migrate.py rollback
python migrate.py migrate

# Step 7: Commit both migration file AND model changes together
git add database/migrations/2026_03_13_*.py models/user.py
git commit -m "feat: add phone number field to users"
```

### Workflow: Fresh Setup (New Developer / New Server)

```bash
# Creates database if needed + migration tracking table
python migrate.py init

# Runs all migration files in order
python migrate.py migrate

# Seeds default data (admin user, system config)
python migrate.py seed
```

### Workflow: Pulling Teammate's Changes

```bash
git pull origin main

# Apply any new migrations they added
python migrate.py migrate
```

### Migration File Structure

Every migration file must export two functions:

```python
def up(conn):
    """Apply the migration — create tables, add columns, etc."""
    with conn.cursor() as cur:
        cur.execute("ALTER TABLE users ADD COLUMN phone VARCHAR(20) DEFAULT NULL")
    conn.commit()

def down(conn):
    """Reverse the migration — drop what up() created."""
    with conn.cursor() as cur:
        cur.execute("ALTER TABLE users DROP COLUMN phone")
    conn.commit()
```

**Both `up()` and `down()` are mandatory.** A migration without a working `down()` cannot be safely rolled back.

---

## License

MIT
