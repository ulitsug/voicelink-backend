#!/usr/bin/env python3
"""
VoiceLink Backend API Test Suite
=================================
Tests all REST API endpoints with dummy data to verify correctness.
Run:  py test_api.py
"""

import requests
import sys
import json
import time

BASE = 'http://127.0.0.1:5001/api'
PASS = 0
FAIL = 0
ERRORS = []


def log(status, endpoint, detail=''):
    global PASS, FAIL
    icon = '✓' if status else '✗'
    color = '' if status else ' <<<'
    msg = f"  [{icon}] {endpoint}"
    if detail:
        msg += f"  — {detail}"
    msg += color
    print(msg)
    if status:
        PASS += 1
    else:
        FAIL += 1
        ERRORS.append(f"{endpoint}: {detail}")


def test(label, resp, expected_status, key=None):
    """Assert status code, optionally check json key exists."""
    ok = resp.status_code == expected_status
    detail = f"status={resp.status_code} (expected {expected_status})"
    if ok and key:
        try:
            data = resp.json()
            if key not in data:
                ok = False
                detail += f" | missing key '{key}'"
            else:
                detail += f" | {key} present"
        except Exception:
            ok = False
            detail += " | invalid JSON"
    log(ok, label, detail)
    return ok


# ═══════════════════════════════════════════════════════════════════
# 0. Health check
# ═══════════════════════════════════════════════════════════════════
print('\n' + '=' * 60)
print('  VoiceLink API Test Suite')
print('=' * 60)

print('\n── Health ──')
try:
    r = requests.get(f'{BASE[:-4]}/', timeout=5)
    test('GET /', r, 200, 'status')
except requests.ConnectionError:
    print('  [✗] Cannot connect to server at', BASE)
    print('      Start the server first:  py app.py')
    sys.exit(1)

# ═══════════════════════════════════════════════════════════════════
# 1. Auth — Register + Login
# ═══════════════════════════════════════════════════════════════════
print('\n── Auth ──')

# Register test users
r = requests.post(f'{BASE}/auth/register', json={
    'username': 'testuser_a',
    'email': 'testa@test.local',
    'password': 'test1234',
    'display_name': 'Test User A',
})
# 201 = new, 409 = already exists — both acceptable
test('POST /auth/register (user A)', r, 201 if r.status_code == 201 else 409)

r = requests.post(f'{BASE}/auth/register', json={
    'username': 'testuser_b',
    'email': 'testb@test.local',
    'password': 'test1234',
    'display_name': 'Test User B',
})
test('POST /auth/register (user B)', r, 201 if r.status_code == 201 else 409)

# Validation tests
r = requests.post(f'{BASE}/auth/register', json={})
test('POST /auth/register (empty body)', r, 400)

r = requests.post(f'{BASE}/auth/register', json={
    'username': 'x', 'email': 'x@x.x', 'password': '12', 'display_name': 'X',
})
test('POST /auth/register (short username)', r, 400)

# Login as admin (always verified)
r = requests.post(f'{BASE}/auth/login', json={
    'username': 'admin', 'password': '4321',
})
test('POST /auth/login (admin)', r, 200, 'access_token')
admin_token = r.json().get('access_token', '') if r.status_code == 200 else ''
admin_headers = {'Authorization': f'Bearer {admin_token}'}

# Before logging in as test users, verify them via admin
# (test users need email_verified = True)
if admin_token:
    # Use admin endpoint to verify test users
    r = requests.get(f'{BASE}/admin/users', headers=admin_headers)
    if r.status_code == 200:
        users_list = r.json().get('users', [])
        for u in users_list:
            if u.get('username') in ('testuser_a', 'testuser_b') and not u.get('email_verified'):
                requests.post(
                    f'{BASE}/admin/users/{u["id"]}/verify-email',
                    headers=admin_headers,
                )

# Login as test user A
r = requests.post(f'{BASE}/auth/login', json={
    'username': 'testuser_a', 'password': 'test1234',
})
login_ok = r.status_code == 200
test('POST /auth/login (user A)', r, 200, 'access_token')

if not login_ok:
    print(f'  !! User A login failed ({r.status_code}): {r.text}')
    # Try to still continue tests with admin
    token_a = admin_token
else:
    token_a = r.json()['access_token']
headers_a = {'Authorization': f'Bearer {token_a}'}

# Login as test user B
r = requests.post(f'{BASE}/auth/login', json={
    'username': 'testuser_b', 'password': 'test1234',
})
if r.status_code == 200:
    token_b = r.json()['access_token']
else:
    token_b = admin_token
headers_b = {'Authorization': f'Bearer {token_b}'}
test('POST /auth/login (user B)', r, 200, 'access_token')

# Login validation
r = requests.post(f'{BASE}/auth/login', json={'username': 'noone', 'password': 'wrong'})
test('POST /auth/login (invalid creds)', r, 401)

r = requests.post(f'{BASE}/auth/login', json={})
test('POST /auth/login (empty body)', r, 400)

# Get me
r = requests.get(f'{BASE}/auth/me', headers=headers_a)
test('GET /auth/me', r, 200, 'user')
user_a_id = r.json().get('user', {}).get('id')

r = requests.get(f'{BASE}/auth/me', headers=headers_b)
user_b_id = r.json().get('user', {}).get('id') if r.status_code == 200 else None
test('GET /auth/me (user B)', r, 200, 'user')

# Unauthorized
r = requests.get(f'{BASE}/auth/me')
test('GET /auth/me (no token)', r, 401)

r = requests.get(f'{BASE}/auth/me', headers={'Authorization': 'Bearer invalidtoken'})
test('GET /auth/me (bad token)', r, 422)

# Update profile
r = requests.put(f'{BASE}/auth/update-profile', json={
    'display_name': 'Test User A Updated',
    'bio': 'Hello from test suite',
}, headers=headers_a)
test('PUT /auth/update-profile', r, 200, 'user')

# Change password and change back
r = requests.put(f'{BASE}/auth/change-password', json={
    'current_password': 'test1234',
    'new_password': 'test12345',
}, headers=headers_a)
test('PUT /auth/change-password', r, 200)

r = requests.put(f'{BASE}/auth/change-password', json={
    'current_password': 'test12345',
    'new_password': 'test1234',
}, headers=headers_a)
test('PUT /auth/change-password (revert)', r, 200)

# Dashboard stats
r = requests.get(f'{BASE}/auth/dashboard-stats', headers=headers_a)
test('GET /auth/dashboard-stats', r, 200, 'contacts')

# ═══════════════════════════════════════════════════════════════════
# 2. Contacts
# ═══════════════════════════════════════════════════════════════════
print('\n── Contacts ──')

if user_b_id:
    r = requests.post(f'{BASE}/contacts', json={'contact_id': user_b_id}, headers=headers_a)
    test('POST /contacts (add B)', r, 201 if r.status_code == 201 else 409)

r = requests.get(f'{BASE}/contacts', headers=headers_a)
test('GET /contacts', r, 200, 'contacts')

r = requests.get(f'{BASE}/contacts/users', headers=headers_a)
test('GET /contacts/users', r, 200, 'users')

r = requests.get(f'{BASE}/contacts/search?q=test', headers=headers_a)
test('GET /contacts/search', r, 200, 'users')

# Block / unblock
if user_b_id:
    r = requests.put(f'{BASE}/contacts/{user_b_id}/block', headers=headers_a)
    test('PUT /contacts/:id/block', r, 200)

    r = requests.put(f'{BASE}/contacts/{user_b_id}/unblock', headers=headers_a)
    test('PUT /contacts/:id/unblock', r, 200)

# ═══════════════════════════════════════════════════════════════════
# 3. Chat
# ═══════════════════════════════════════════════════════════════════
print('\n── Chat ──')

# Send message from A to B
msg_id = None
if user_b_id:
    r = requests.post(f'{BASE}/chat/messages', json={
        'receiver_id': user_b_id,
        'content': 'Hello from test suite!',
        'message_type': 'text',
    }, headers=headers_a)
    test('POST /chat/messages', r, 201, 'message')
    if r.status_code == 201:
        msg_id = r.json()['message']['id']

    # Send another message
    r = requests.post(f'{BASE}/chat/messages', json={
        'receiver_id': user_b_id,
        'content': 'Second test message',
        'message_type': 'text',
    }, headers=headers_a)
    test('POST /chat/messages (2nd)', r, 201)

    # Get messages
    r = requests.get(f'{BASE}/chat/messages/{user_b_id}', headers=headers_a)
    test('GET /chat/messages/:user_id', r, 200, 'messages')

# Conversations
r = requests.get(f'{BASE}/chat/conversations', headers=headers_a)
test('GET /chat/conversations', r, 200, 'conversations')

# Unread counts
r = requests.get(f'{BASE}/chat/unread', headers=headers_b)
test('GET /chat/unread', r, 200, 'unread')

# Validation
r = requests.post(f'{BASE}/chat/messages', json={'content': 'hi'}, headers=headers_a)
test('POST /chat/messages (no receiver)', r, 400)

# Delete message
if msg_id:
    r = requests.delete(f'{BASE}/chat/messages/{msg_id}', headers=headers_a)
    test('DELETE /chat/messages/:id', r, 200, 'success')

    # Try deleting non-existent
    r = requests.delete(f'{BASE}/chat/messages/999999', headers=headers_a)
    test('DELETE /chat/messages (not found)', r, 404)

# Delete conversation
if user_b_id:
    r = requests.delete(f'{BASE}/chat/conversations/{user_b_id}', headers=headers_a)
    test('DELETE /chat/conversations/:id', r, 200)

# ═══════════════════════════════════════════════════════════════════
# 4. Calls
# ═══════════════════════════════════════════════════════════════════
print('\n── Calls ──')

# ICE config
r = requests.get(f'{BASE}/calls/ice-config', headers=headers_a)
test('GET /calls/ice-config', r, 200, 'iceServers')

# Call history
r = requests.get(f'{BASE}/calls/history', headers=headers_a)
test('GET /calls/history', r, 200, 'calls')

# Create call log
call_id = None
if user_b_id:
    r = requests.post(f'{BASE}/calls/log', json={
        'callee_id': user_b_id,
        'call_type': 'voice',
    }, headers=headers_a)
    test('POST /calls/log', r, 201, 'call')
    if r.status_code == 201:
        call_id = r.json()['call']['id']

# Update call log — mark active
if call_id:
    r = requests.put(f'{BASE}/calls/log/{call_id}', json={
        'status': 'active',
    }, headers=headers_a)
    test('PUT /calls/log/:id (active)', r, 200, 'call')
    if r.status_code == 200:
        call_data = r.json()['call']
        has_answered = call_data.get('answered_at') is not None
        log(has_answered, 'PUT /calls/log (answered_at set)', f"answered_at={call_data.get('answered_at')}")

    time.sleep(1)  # Let some duration pass

    # End call with new fields
    r = requests.put(f'{BASE}/calls/log/{call_id}', json={
        'status': 'ended',
        'end_reason': 'normal',
        'quality_score': 4,
    }, headers=headers_a)
    test('PUT /calls/log/:id (ended)', r, 200, 'call')
    if r.status_code == 200:
        call_data = r.json()['call']
        log(call_data.get('end_reason') == 'normal', 'call end_reason', f"end_reason={call_data.get('end_reason')}")
        log(call_data.get('quality_score') == 4, 'call quality_score', f"quality_score={call_data.get('quality_score')}")
        log(call_data.get('duration', 0) >= 1, 'call duration calculated', f"duration={call_data.get('duration')}")

    # Unauthorized update
    r = requests.put(f'{BASE}/calls/log/{call_id}', json={'status': 'ended'}, headers=headers_b)
    # User B is the callee, so this should succeed (403 only if not participant)
    test('PUT /calls/log (callee update)', r, 200)

# Not found
r = requests.put(f'{BASE}/calls/log/999999', json={'status': 'ended'}, headers=headers_a)
test('PUT /calls/log (not found)', r, 404)

# Active calls endpoint
r = requests.get(f'{BASE}/calls/active', headers=headers_a)
test('GET /calls/active', r, 200, 'active_calls')
if r.status_code == 200:
    data = r.json()
    log('count' in data, 'active_calls has count', f"count={data.get('count')}")

# Create another call log for testing video type
if user_b_id:
    r = requests.post(f'{BASE}/calls/log', json={
        'callee_id': user_b_id,
        'call_type': 'video',
    }, headers=headers_a)
    test('POST /calls/log (video)', r, 201)

# Verify history shows our logs
r = requests.get(f'{BASE}/calls/history', headers=headers_a)
test('GET /calls/history (with data)', r, 200, 'calls')
if r.status_code == 200:
    calls = r.json()['calls']
    log(len(calls) >= 2, 'call history count', f"found {len(calls)} calls")

# Quality score validation — out of range
if call_id:
    r = requests.put(f'{BASE}/calls/log/{call_id}', json={
        'quality_score': 10,
    }, headers=headers_a)
    test('PUT /calls/log (bad quality_score)', r, 200)
    if r.status_code == 200:
        # quality_score should not change because 10 > 5
        log(r.json()['call'].get('quality_score') == 4, 'quality_score unchanged for invalid', '')

# ═══════════════════════════════════════════════════════════════════
# 5. Groups
# ═══════════════════════════════════════════════════════════════════
print('\n── Groups ──')

group_id = None
r = requests.post(f'{BASE}/groups', json={
    'name': 'Test Group',
    'member_ids': [user_b_id] if user_b_id else [],
}, headers=headers_a)
test('POST /groups', r, 201, 'group')
if r.status_code == 201:
    group_id = r.json()['group']['id']

r = requests.get(f'{BASE}/groups', headers=headers_a)
test('GET /groups', r, 200, 'groups')

if group_id:
    r = requests.get(f'{BASE}/groups/{group_id}', headers=headers_a)
    test('GET /groups/:id', r, 200, 'group')

    # Update group
    r = requests.put(f'{BASE}/groups/{group_id}', json={
        'name': 'Test Group Renamed',
    }, headers=headers_a)
    test('PUT /groups/:id', r, 200)

    # Send group message
    r = requests.post(f'{BASE}/chat/messages', json={
        'group_id': group_id,
        'content': 'Hello group from test suite!',
        'message_type': 'text',
    }, headers=headers_a)
    test('POST /chat/messages (group)', r, 201)

# Validation
r = requests.post(f'{BASE}/groups', json={}, headers=headers_a)
test('POST /groups (no name)', r, 400)

# Not found
r = requests.get(f'{BASE}/groups/999999', headers=headers_a)
test('GET /groups (not found)', r, 404)

# ═══════════════════════════════════════════════════════════════════
# 6. Calendar Events
# ═══════════════════════════════════════════════════════════════════
print('\n── Calendar ──')

event_id = None
r = requests.post(f'{BASE}/calendar/events', json={
    'title': 'Test Meeting',
    'scheduled_at': '2026-03-15T10:00:00',
    'event_type': 'meeting',
    'description': 'A test calendar event',
    'duration_minutes': 60,
}, headers=headers_a)
test('POST /calendar/events', r, 201, 'event')
if r.status_code == 201:
    event_id = r.json()['event']['id']

r = requests.get(f'{BASE}/calendar/events', headers=headers_a)
test('GET /calendar/events', r, 200, 'events')

if event_id:
    r = requests.get(f'{BASE}/calendar/events/{event_id}', headers=headers_a)
    test('GET /calendar/events/:id', r, 200, 'event')

    r = requests.put(f'{BASE}/calendar/events/{event_id}', json={
        'title': 'Updated Meeting',
    }, headers=headers_a)
    test('PUT /calendar/events/:id', r, 200)

    # Clean up
    r = requests.delete(f'{BASE}/calendar/events/{event_id}', headers=headers_a)
    test('DELETE /calendar/events/:id', r, 200)

# ═══════════════════════════════════════════════════════════════════
# 7. Admin
# ═══════════════════════════════════════════════════════════════════
print('\n── Admin ──')

r = requests.get(f'{BASE}/admin/users', headers=admin_headers)
test('GET /admin/users', r, 200, 'users')

r = requests.get(f'{BASE}/admin/dashboard', headers=admin_headers)
test('GET /admin/dashboard', r, 200)

r = requests.get(f'{BASE}/admin/system-info', headers=admin_headers)
test('GET /admin/system-info', r, 200)

r = requests.get(f'{BASE}/admin/stats/messages', headers=admin_headers)
test('GET /admin/stats/messages', r, 200)

r = requests.get(f'{BASE}/admin/stats/calls', headers=admin_headers)
test('GET /admin/stats/calls', r, 200)

# Non-admin should be denied (only test if user A logged in as non-admin)
if token_a != admin_token:
    r = requests.get(f'{BASE}/admin/users', headers=headers_a)
    test('GET /admin/users (non-admin)', r, 403)
else:
    log(True, 'GET /admin/users (non-admin)', 'SKIPPED — user A is admin fallback')

# ═══════════════════════════════════════════════════════════════════
# 8. Push Subscriptions
# ═══════════════════════════════════════════════════════════════════
print('\n── Push ──')

r = requests.get(f'{BASE}/push/vapid-key', headers=headers_a)
test('GET /push/vapid-key', r, 200, 'public_key')

r = requests.post(f'{BASE}/push/subscribe', json={
    'subscription': {
        'endpoint': 'https://example.com/push/test',
        'keys': {'p256dh': 'test_key', 'auth': 'test_auth'},
    },
}, headers=headers_a)
test('POST /push/subscribe', r, 200 if r.status_code == 200 else 201)

# ═══════════════════════════════════════════════════════════════════
# 9. Cleanup — delete test group
# ═══════════════════════════════════════════════════════════════════
print('\n── Cleanup ──')

if group_id:
    r = requests.delete(f'{BASE}/groups/{group_id}', headers=headers_a)
    test('DELETE /groups/:id (cleanup)', r, 200)

# Remove contact we added
if user_b_id:
    r = requests.delete(f'{BASE}/contacts/{user_b_id}', headers=headers_a)
    test('DELETE /contacts/:id (cleanup)', r, 200 if r.status_code == 200 else 404)

# ═══════════════════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════════════════
print('\n' + '=' * 60)
print(f'  Results:  {PASS} passed,  {FAIL} failed')
print('=' * 60)

if ERRORS:
    print('\n  Failed tests:')
    for e in ERRORS:
        print(f'    ✗ {e}')
    print()

sys.exit(1 if FAIL > 0 else 0)
