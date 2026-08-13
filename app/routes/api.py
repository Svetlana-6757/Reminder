import json
import os
from datetime import date, datetime, timedelta

from flask import Blueprint, current_app, jsonify, request

from .. import push
from ..logic import (day_span, now_local, serialize_med, serialize_reminder,
                     _tz, today_local)
from ..models import Medication, PushSubscription, Reminder, Setting, db

api_bp = Blueprint('api', __name__, url_prefix='/api')


def _json_body():
    return request.get_json(silent=True) or {}


def _get_med(mid):
    med = db.session.get(Medication, mid)
    if med is None:
        return None, jsonify({'error': 'not found'}), 404
    return med, None, None


# ------------------------------------------------------------------ сегодня

@api_bp.route('/today')
def today():
    status = request.args.get('status', '').strip() or None
    today_d = today_local()
    start, end = day_span(today_d)

    query = Reminder.query.filter(
        Reminder.scheduled_for >= start,
        Reminder.scheduled_for < end,
    )
    # нерешённые напоминания прошлых дней (pending / overdue) тоже показываем
    past = Reminder.query.filter(
        Reminder.scheduled_for < start,
        Reminder.status.in_(['pending', 'overdue']),
    )
    rows = query.union(past).all()

    if status:
        rows = [r for r in rows if r.status == status]

    rows.sort(key=lambda r: r.scheduled_for)
    return jsonify({
        'date': today_d.isoformat(),
        'items': [serialize_reminder(r) for r in rows],
    })


# ------------------------------------------------------------------ лекарства

@api_bp.route('/medications')
def medications_list():
    meds = Medication.query.order_by(Medication.name).all()
    return jsonify([serialize_med(m) for m in meds])


@api_bp.route('/medications/<int:mid>')
def medication_get(mid):
    med, err, code = _get_med(mid)
    if err:
        return err, code
    return jsonify(serialize_med(med))


@api_bp.route('/medications/<int:mid>/history')
def medication_history(mid):
    med, err, code = _get_med(mid)
    if err:
        return err, code
    rows = (med.reminders.order_by(Reminder.scheduled_for.desc())
            .limit(200).all())
    return jsonify([serialize_reminder(r) for r in rows])


def _parse_payload():
    b = _json_body()
    errors = []
    name = (b.get('name') or '').strip()
    if not name:
        errors.append('Название обязательно')
    times_per_day = int(b.get('times_per_day') or 1)
    if times_per_day < 1:
        times_per_day = 1

    exact_times = []
    if b.get('schedule_mode') == 'exact':
        for t in b.get('exact_times') or []:
            t = (t or '').strip()
            if t:
                try:
                    datetime.strptime(t, '%H:%M')
                    exact_times.append(t)
                except ValueError:
                    errors.append(f'Некорректное время: {t}')
    if b.get('schedule_mode') == 'exact' and not exact_times:
        errors.append('Укажите время приёма')

    start_date = None
    try:
        start_date = date.fromisoformat(b.get('start_date') or date.today().isoformat())
    except ValueError:
        errors.append('Некорректная дата начала')

    duration_type = b.get('duration_type') or 'permanent'
    duration_days = None
    if duration_type == 'days':
        try:
            duration_days = max(1, int(b.get('duration_days') or 7))
        except (TypeError, ValueError):
            duration_days = 7

    meal = b.get('meal_condition') or 'none'
    if meal not in ('none', 'before', 'after', 'during'):
        meal = 'none'
    try:
        offset = max(0, min(240, int(b.get('meal_offset_minutes') or 0)))
    except (TypeError, ValueError):
        offset = 0

    return {
        'errors': errors,
        'data': {
            'name': name,
            'description': (b.get('description') or '').strip(),
            'icon': (b.get('icon') or '💊')[:8],
            'start_date': start_date,
            'duration_type': duration_type,
            'duration_days': duration_days,
            'times_per_day': times_per_day,
            'schedule_mode': b.get('schedule_mode') == 'auto' and 'auto' or 'exact',
            'exact_times': exact_times,
            'meal_condition': meal,
            'meal_offset_minutes': offset,
        },
    }


@api_bp.route('/medications', methods=['POST'])
def medication_create():
    parsed = _parse_payload()
    if parsed['errors']:
        return jsonify({'error': '; '.join(parsed['errors'])}), 400
    d = parsed['data']
    med = Medication(
        name=d['name'], description=d['description'], icon=d['icon'],
        start_date=d['start_date'], duration_type=d['duration_type'],
        duration_days=d['duration_days'], times_per_day=d['times_per_day'],
        schedule_mode=d['schedule_mode'],
        exact_times=json.dumps(d['exact_times'], ensure_ascii=False),
        meal_condition=d['meal_condition'],
        meal_offset_minutes=d['meal_offset_minutes'],
    )
    db.session.add(med)
    db.session.commit()
    current_app.scheduler.regen(med)
    return jsonify(serialize_med(med)), 201


@api_bp.route('/medications/<int:mid>', methods=['PUT'])
def medication_update(mid):
    med, err, code = _get_med(mid)
    if err:
        return err, code
    parsed = _parse_payload()
    if parsed['errors']:
        return jsonify({'error': '; '.join(parsed['errors'])}), 400
    d = parsed['data']
    med.name = d['name']
    med.description = d['description']
    med.icon = d['icon']
    med.start_date = d['start_date']
    med.duration_type = d['duration_type']
    med.duration_days = d['duration_days']
    med.times_per_day = d['times_per_day']
    med.schedule_mode = d['schedule_mode']
    med.exact_times = json.dumps(d['exact_times'], ensure_ascii=False)
    med.meal_condition = d['meal_condition']
    med.meal_offset_minutes = d['meal_offset_minutes']
    db.session.commit()
    current_app.scheduler.regen(med)
    return jsonify(serialize_med(med))


@api_bp.route('/medications/<int:mid>', methods=['DELETE'])
def medication_delete(mid):
    med, err, code = _get_med(mid)
    if err:
        return err, code
    if med.photo:
        import config as _config
        path = os.path.join(_config.MED_PHOTO_DIR, med.photo)
        if os.path.exists(path):
            os.remove(path)
    db.session.delete(med)
    db.session.commit()
    return jsonify({'ok': True})


@api_bp.route('/medications/<int:mid>/toggle', methods=['POST'])
def medication_toggle(mid):
    med, err, code = _get_med(mid)
    if err:
        return err, code
    med.active = not med.active
    db.session.commit()
    current_app.scheduler.regen(med)
    return jsonify(serialize_med(med))


@api_bp.route('/medications/<int:mid>/photo', methods=['POST'])
def medication_photo_upload(mid):
    med, err, code = _get_med(mid)
    if err:
        return err, code
    file = request.files.get('photo')
    if not file or not file.filename:
        return jsonify({'error': 'Файл не выбран'}), 400
    name = (file.filename or '').lower()
    if not name.endswith(('.png', '.jpg', '.jpeg', '.webp', '.heic', '.heif', '.bmp', '.gif')):
        return jsonify({'error': 'Формат должен быть изображением'}), 400
    try:
        import config as _config
        from PIL import Image, ImageOps
        import pillow_heif
        pillow_heif.register_heif_opener()
        img = Image.open(file.stream)
        img = ImageOps.exif_transpose(img)
        if img.mode in ('RGBA', 'LA', 'P'):
            bg = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            bg.paste(img, (0, 0), img.split()[-1] if len(img.getbands()) >= 4 else None)
            img = bg
        elif img.mode != 'RGB':
            img = img.convert('RGB')
        img.thumbnail((640, 640), Image.LANCZOS)
        os.makedirs(_config.MED_PHOTO_DIR, exist_ok=True)
        out = os.path.join(_config.MED_PHOTO_DIR, f'{med.id}.jpg')
        img.save(out, 'JPEG', quality=86)
        med.photo = f'{med.id}.jpg'
        db.session.commit()
    except Exception as e:
        print('photo upload error:', e)
        return jsonify({'error': 'Не удалось обработать изображение'}), 400
    return jsonify(serialize_med(med))


@api_bp.route('/medications/<int:mid>/photo', methods=['DELETE'])
def medication_photo_delete(mid):
    med, err, code = _get_med(mid)
    if err:
        return err, code
    if med.photo:
        import config as _config
        path = os.path.join(_config.MED_PHOTO_DIR, med.photo)
        if os.path.exists(path):
            os.remove(path)
        med.photo = None
        db.session.commit()
    return jsonify(serialize_med(med))


@api_bp.route('/medications/<int:mid>/start', methods=['POST'])
def medication_start(mid):
    med, err, code = _get_med(mid)
    if err:
        return err, code
    if med.schedule_mode != 'auto':
        return jsonify({'error': 'Не авто-режим'}), 400
    today = today_local()
    start, end = day_span(today)
    created = current_app.scheduler.start_day(med, today)
    prompts = med.reminders.filter(
        Reminder.is_start_prompt.is_(True),
        Reminder.scheduled_for >= start,
        Reminder.scheduled_for < end,
    ).all()
    now = now_local()
    for p in prompts:
        if p.status != 'done':
            p.status = 'done'
            p.done_at = now
    db.session.commit()
    return jsonify({'ok': True, 'created': created})


# --------------------------------------------------------------- напоминания

@api_bp.route('/reminders/<int:rid>/done', methods=['POST'])
def reminder_done(rid):
    r = db.session.get(Reminder, rid)
    if r is None:
        return jsonify({'error': 'not found'}), 404
    if r.status in ('pending', 'overdue'):
        r.status = 'done'
        r.done_at = now_local()
        db.session.commit()
    return jsonify(serialize_reminder(r))


@api_bp.route('/reminders/<int:rid>/cancel', methods=['POST'])
def reminder_cancel(rid):
    r = db.session.get(Reminder, rid)
    if r is None:
        return jsonify({'error': 'not found'}), 404
    if r.status in ('pending', 'overdue'):
        r.status = 'cancelled'
        db.session.commit()
    return jsonify(serialize_reminder(r))


@api_bp.route('/reminders/<int:rid>/postpone', methods=['POST'])
def reminder_postpone(rid):
    r = db.session.get(Reminder, rid)
    if r is None:
        return jsonify({'error': 'not found'}), 404
    if r.status == 'cancelled':
        return jsonify({'error': 'Уже отменено'}), 400

    b = _json_body()
    now = now_local()
    new_dt = None

    at = b.get('at')
    if at:
        try:
            new_dt = datetime.fromisoformat(str(at).replace('Z', '+00:00'))
            if new_dt.tzinfo is not None:
                new_dt = new_dt.astimezone(_tz()).replace(tzinfo=None)
        except ValueError:
            new_dt = None
        if new_dt is None:
            return jsonify({'error': 'Некорректное время переноса'}), 400
    else:
        try:
            minutes = max(1, int(b.get('minutes') or 60))
        except (TypeError, ValueError):
            minutes = 60
        new_dt = now + timedelta(minutes=minutes)

    r.scheduled_for = new_dt
    r.status = 'pending'
    r.notified_at = None
    r.repeat_count = 0
    r.postponed_count = (r.postponed_count or 0) + 1
    db.session.commit()
    return jsonify(serialize_reminder(r))


# --------------------------------------------------------------- настройки

@api_bp.route('/settings')
def settings_get():
    return jsonify({
        'app_name': Setting.get('app_name', 'Напоминания'),
        'app_icon': Setting.get('app_icon', '💊'),
        'wake_time': Setting.get('wake_time', '08:00'),
        'sound_file': Setting.get('sound_file', 'chime.wav'),
        'sound_volume': int(Setting.get('sound_volume', '70')),
        'push_active': PushSubscription.query.count() > 0,
    })


@api_bp.route('/settings', methods=['POST'])
def settings_save():
    b = _json_body()
    allowed = {'app_name', 'app_icon', 'wake_time', 'sound_file', 'sound_volume'}
    for key in allowed:
        if key in b and b[key] is not None:
            Setting.set(key, b[key])
    return jsonify({'ok': True})


@api_bp.route('/settings/icon', methods=['POST'])
def settings_icon_upload():
    import time
    import config as _config
    file = request.files.get('icon')
    if not file:
        return jsonify({'error': 'Файл не выбран'}), 400
    name = (file.filename or '').lower()
    if not name.endswith(('.png', '.jpg', '.jpeg', '.webp')):
        return jsonify({'error': 'Формат должен быть PNG или JPG'}), 400
    dest = os.path.join(_config.ICON_DIR, 'custom-icon.png')
    file.save(dest)
    for s in (192, 512):
        out = os.path.join(_config.ICON_DIR, f'resize-{s}.png')
        if os.path.exists(out):
            os.remove(out)
    Setting.set('icon_version', str(int(time.time())))
    return jsonify({'ok': True, 'version': Setting.get('icon_version')})


@api_bp.route('/sounds')
def sounds_list():
    sounds = ['chime.wav', 'bell.wav', 'pulse.wav', 'marimba.wav']
    labels = {
        'chime.wav': 'Мягкий колокольчик',
        'bell.wav': 'Колокол',
        'pulse.wav': 'Короткие сигналы',
        'marimba.wav': 'Маракас',
    }
    return jsonify([{'file': s, 'label': labels.get(s, s)} for s in sounds])


# ------------------------------------------------------------------ push

@api_bp.route('/push/key')
def push_key():
    return jsonify({'key': push.public_key()})


@api_bp.route('/push/subscribe', methods=['POST'])
def push_subscribe():
    b = _json_body()
    endpoint = (b.get('endpoint') or '').strip()
    keys = b.get('keys') or {}
    if not endpoint:
        return jsonify({'error': 'Нет endpoint'}), 400
    existing = PushSubscription.query.filter_by(endpoint=endpoint).first()
    if existing:
        existing.p256dh = keys.get('p256dh', '')
        existing.auth = keys.get('auth', '')
        db.session.commit()
        return jsonify({'ok': True})
    db.session.add(PushSubscription(
        endpoint=endpoint, p256dh=keys.get('p256dh', ''),
        auth=keys.get('auth', '')))
    db.session.commit()
    return jsonify({'ok': True})


@api_bp.route('/push/unsubscribe', methods=['POST'])
def push_unsubscribe():
    b = _json_body()
    endpoint = (b.get('endpoint') or '').strip()
    if endpoint:
        PushSubscription.query.filter_by(endpoint=endpoint).delete()
        db.session.commit()
    return jsonify({'ok': True})


@api_bp.route('/push/test', methods=['POST'])
def push_test():
    push.send_test()
    return jsonify({'ok': True})
