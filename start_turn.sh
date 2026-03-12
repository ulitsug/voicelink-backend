#!/bin/bash
# Start the coturn TURN server for VoiceLink
# Usage: ./start_turn.sh

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
CONF="$SCRIPT_DIR/turnserver.conf"

# Get local IP
LOCAL_IP=$(python3 -c "import socket; s=socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.connect(('8.8.8.8',80)); print(s.getsockname()[0]); s.close()" 2>/dev/null || echo "127.0.0.1")

echo "========================================"
echo "  VoiceLink TURN Server"
echo "  Listening IP:  $LOCAL_IP"
echo "  STUN/TURN:     $LOCAL_IP:3478"
echo "  Credentials:   voicelink / voicelink2026"
echo "========================================"

exec turnserver -c "$CONF" --listening-ip="$LOCAL_IP" --relay-ip="$LOCAL_IP" --external-ip="$LOCAL_IP"
