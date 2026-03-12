"""Push notification service — sends Web Push messages to subscribed clients."""

import json
from pywebpush import webpush, WebPushException
from flask import current_app

from models import db
from models.push_subscription import PushSubscription


def send_push_to_user(user_id, payload):
    """Send a push notification to all subscriptions for a given user.

    Args:
        user_id: Target user ID
        payload: Dict with keys like title, body, type, url, tag, caller_id, call_type
    """
    subscriptions = PushSubscription.query.filter_by(user_id=user_id).all()
    if not subscriptions:
        return

    vapid_private_key = current_app.config['VAPID_PRIVATE_KEY']
    vapid_claims_email = current_app.config['VAPID_CLAIMS_EMAIL']
    data = json.dumps(payload)

    stale = []
    for sub in subscriptions:
        try:
            webpush(
                subscription_info={
                    'endpoint': sub.endpoint,
                    'keys': {
                        'p256dh': sub.p256dh,
                        'auth': sub.auth,
                    },
                },
                data=data,
                vapid_private_key=vapid_private_key,
                vapid_claims={'sub': vapid_claims_email},
                timeout=5,
            )
        except WebPushException as e:
            status = e.response.status_code if e.response is not None else 0
            # 404 or 410 means the subscription is expired/invalid
            if status in (404, 410):
                stale.append(sub.id)
            else:
                print(f'[Push] Error sending to user {user_id}: {e}', flush=True)
        except Exception as e:
            print(f'[Push] Unexpected error: {e}', flush=True)

    # Clean up stale subscriptions
    if stale:
        PushSubscription.query.filter(PushSubscription.id.in_(stale)).delete(synchronize_session=False)
        db.session.commit()


def send_call_notification(user_id, caller_name, call_type='voice'):
    """Send a push notification for an incoming call."""
    send_push_to_user(user_id, {
        'title': f'Incoming {call_type} call',
        'body': f'{caller_name} is calling you',
        'type': 'call',
        'call_type': call_type,
        'tag': 'incoming-call',
        'url': '/',
    })


def send_message_notification(user_id, sender_name, message_preview):
    """Send a push notification for a new message."""
    body = message_preview[:100] if message_preview else 'Sent you a message'
    send_push_to_user(user_id, {
        'title': sender_name,
        'body': body,
        'type': 'message',
        'tag': f'msg-{sender_name}',
        'url': '/chat',
    })
