import os
from concurrent.futures import ThreadPoolExecutor

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from pywebpush import WebPushException, webpush

import config
from .models import PushSubscription, db

_executor = ThreadPoolExecutor(max_workers=4)


def _private_key():
    if not os.path.exists(config.VAPID_PATH):
        key = ec.generate_private_key(ec.SECP256R1())
        pem = key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption())
        with open(config.VAPID_PATH, 'wb') as f:
            f.write(pem)
    with open(config.VAPID_PATH, 'rb') as f:
        return f.read()


def public_key():
    """URL-safe base64 публичного ключа для подписки на push с клиента."""
    from base64 import urlsafe_b64encode
    priv = serialization.load_pem_private_key(_private_key(), password=None)
    raw = priv.public_key().public_bytes(
        serialization.Encoding.X962,
        serialization.PublicFormat.UncompressedPoint)
    return urlsafe_b64encode(raw).rstrip(b'=').decode('ascii')


def _claims():
    host = config.BASE_URL.split('//')[-1].split('/')[0]
    email = 'admin@example.com'
    if host and host.count('.') > 0:
        email = 'admin@' + host
    return {'sub': 'mailto:' + email}


def send(sub, payload):
    try:
        webpush(
            subscription_info=sub,
            data=json_dumps(payload).encode('utf-8'),
            vapid_private_key=_private_key(),
            vapid_claims=_claims(),
            timeout=10)
    except WebPushException as e:
        if e.response is not None and e.response.status_code in (404, 410):
            try:
                PushSubscription.query.filter_by(endpoint=sub['endpoint']).delete()
                db.session.commit()
            except Exception:
                db.session.rollback()
        print('push error:', e)


def json_dumps(payload):
    import json
    return json.dumps(payload, ensure_ascii=False)


def send_async(payload):
    subs = PushSubscription.query.all()
    for s in subs:
        sub = {
            'endpoint': s.endpoint,
            'keys': {'p256dh': s.p256dh, 'auth': s.auth},
        }
        _executor.submit(send, sub, payload)


def send_test():
    send_async({
        'type': 'test',
        'kind': 'test',
        'title': 'Проверка уведомлений',
        'body': 'Уведомления работают! Звук и всплывающее окно — как надо.',
        'url': '/settings',
    })
