#!/usr/bin/env python3
"""Test script: connect 2 users and make a call between them."""
import time
import requests
import socketio

requests.packages.urllib3.disable_warnings()

# Login as testcaller (user 7)
r = requests.post('https://localhost:5001/api/auth/login', json={
    'username': 'testcaller',
    'password': 'test1234'
}, verify=False)
print(f'Login caller: {r.status_code}')
caller_token = r.json()['access_token']
caller_id = r.json()['user']['id']

# Login as testcallee — register if needed
r = requests.post('https://localhost:5001/api/auth/register', json={
    'username': 'testcallee',
    'email': 'testcallee@test.com',
    'password': 'test1234',
    'display_name': 'Test Callee'
}, verify=False)
if r.status_code == 409:
    r = requests.post('https://localhost:5001/api/auth/login', json={
        'username': 'testcallee',
        'password': 'test1234'
    }, verify=False)
print(f'Login callee: {r.status_code}')
callee_token = r.json()['access_token']
callee_id = r.json()['user']['id']

print(f'Caller ID: {caller_id}, Callee ID: {callee_id}')

# Connect callee socket FIRST
callee_sio = socketio.Client(ssl_verify=False)
callee_events = []

@callee_sio.event
def connect():
    print('CALLEE: Connected')

@callee_sio.on('authenticated')
def callee_auth(data):
    print(f'CALLEE: Authenticated, online users: {[u["username"] for u in data.get("online_users",[])]}')

@callee_sio.on('incoming_call')
def callee_incoming(data):
    print(f'CALLEE: >>> INCOMING CALL from {data.get("caller",{}).get("display_name")} (type={data.get("call_type")})')
    callee_events.append('incoming_call')

@callee_sio.on('call_error')
def callee_error(data):
    print(f'CALLEE: Call error: {data}')
    callee_events.append('call_error')

callee_sio.connect('https://localhost:5001', transports=['polling'])
callee_sio.emit('authenticate', {'token': callee_token})
time.sleep(2)

# Connect caller socket
caller_sio = socketio.Client(ssl_verify=False)
caller_events = []

@caller_sio.on('authenticated')
def caller_auth(data):
    print(f'CALLER: Authenticated, online users: {[u["username"] for u in data.get("online_users",[])]}')

@caller_sio.on('call_error')
def caller_error(data):
    print(f'CALLER: Call error: {data}')
    caller_events.append('call_error')

@caller_sio.on('call_accepted')
def caller_accepted(data):
    print(f'CALLER: Call accepted!')
    caller_events.append('call_accepted')

caller_sio.connect('https://localhost:5001', transports=['polling'])
caller_sio.emit('authenticate', {'token': caller_token})
time.sleep(2)

# Caller initiates call to callee
print(f'\nCALLER: Calling user {callee_id}...')
caller_sio.emit('call_user', {
    'target_id': callee_id,
    'call_type': 'voice',
    'offer': {'type': 'offer', 'sdp': 'test-sdp'},
    'call_id': None,
})

# Wait for callee to receive
time.sleep(3)

# Report results
print(f'\n=== RESULTS ===')
print(f'Callee events: {callee_events}')
print(f'Caller events: {caller_events}')
if 'incoming_call' in callee_events:
    print('SUCCESS: Incoming call received by callee!')
elif 'call_error' in caller_events:
    print('FAIL: Call error returned to caller')
else:
    print('FAIL: No events received')

callee_sio.disconnect()
caller_sio.disconnect()
print('Done')
