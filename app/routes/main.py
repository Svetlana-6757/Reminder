import json
import os
import queue
from datetime import date

from flask import Blueprint, Response, abort, render_template, send_file

import config
from ..events import hub
from ..models import Medication, Setting, db

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    return render_template('index.html', page='today')


@main_bp.route('/medications')
def medications():
    return render_template('medications.html', page='medications')


@main_bp.route('/medications/new')
def medication_new():
    return render_template('medication_form.html', page='medications',
                           med=None, today=date.today().isoformat())


@main_bp.route('/medications/<int:mid>/edit')
def medication_edit(mid):
    med = db.session.get(Medication, mid)
    if med is None:
        abort(404)
    return render_template('medication_form.html', page='medications',
                           med=med, today=date.today().isoformat())


@main_bp.route('/medications/<int:mid>')
def medication_detail(mid):
    med = db.session.get(Medication, mid)
    if med is None:
        abort(404)
    return render_template('medication_detail.html', page='medications', med=med)


@main_bp.route('/settings')
def settings_page():
    return render_template('settings.html', page='settings')


# ------------------------------------------------------------------ PWA

@main_bp.route('/manifest.json')
def manifest():
    name = Setting.get('app_name', 'Напоминания')
    data = {
        'name': name,
        'short_name': name[:12],
        'start_url': '/',
        'display': 'standalone',
        'background_color': '#f4f9f8',
        'theme_color': '#2fb5a7',
        'description': 'Вежливые напоминания о приёме лекарств',
        'icons': [
            {'src': '/icon-192.png', 'sizes': '192x192', 'type': 'image/png',
             'purpose': 'any'},
            {'src': '/icon-512.png', 'sizes': '512x512', 'type': 'image/png',
             'purpose': 'any maskable'},
        ],
    }
    return Response(json.dumps(data, ensure_ascii=False),
                    mimetype='application/manifest+json')


def _serve_icon(size):
    custom = os.path.join(config.ICON_DIR, 'custom-icon.png')
    if os.path.exists(custom):
        out = os.path.join(config.ICON_DIR, f'resize-{size}.png')
        if not os.path.exists(out):
            from PIL import Image
            im = Image.open(custom).convert('RGBA')
            im = im.resize((size, size), Image.LANCZOS)
            im.save(out, 'PNG')
        path = out
    else:
        path = os.path.join(config.ICON_DIR, f'icon-{size}.png')
    return send_file(os.path.abspath(path), mimetype='image/png')


@main_bp.route('/icon-192.png')
def icon_192():
    return _serve_icon(192)


@main_bp.route('/icon-512.png')
def icon_512():
    return _serve_icon(512)


@main_bp.route('/icon.png')
def icon_any():
    return _serve_icon(192)


@main_bp.route('/favicon.ico')
def favicon():
    return _serve_icon(192)


# ------------------------------------------------------------------ SSE

@main_bp.route('/events')
def events():
    def gen():
        q = hub.subscribe()
        try:
            yield 'retry: 3000\n\n'
            while True:
                try:
                    msg = q.get(timeout=15)
                    yield f'data: {msg}\n\n'
                except queue.Empty:
                    yield ': keepalive\n\n'
        finally:
            hub.unsubscribe(q)

    return Response(gen(), mimetype='text/event-stream', headers={
        'Cache-Control': 'no-cache',
        'X-Accel-Buffering': 'no',
        'Connection': 'keep-alive',
    })
