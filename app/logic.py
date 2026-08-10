from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from flask import current_app

STATUS_LABELS = {
    'pending': 'Ожидает',
    'done': 'Готово',
    'overdue': 'Просрочено',
    'cancelled': 'Отменено',
}


def _tz():
    return ZoneInfo(current_app.config['TIMEZONE'])


def now_local():
    """Текущее время в часовом поясе приложения (naive)."""
    return datetime.now(_tz()).replace(tzinfo=None)


def today_local():
    return now_local().date()


def day_span(day):
    start = datetime.combine(day, time(0, 0))
    return start, start + timedelta(days=1)


def parse_clock(s, default=time(8, 0)):
    try:
        h, m = s.strip().split(':')
        return time(int(h), int(m))
    except Exception:
        return default


def wake_time_for_day(day):
    from .models import Setting
    t = parse_clock(Setting.get('wake_time', '08:00'))
    return datetime.combine(day, t)


def intake_times_for_day(med, day):
    """Время приёмов лекарства в конкретный день."""
    result = []
    if med.schedule_mode == 'exact':
        for tstr in med.exact_times_list:
            result.append(datetime.combine(day, parse_clock(tstr)))
    else:
        n = max(1, med.times_per_day)
        t0 = wake_time_for_day(day)
        step = timedelta(hours=12.0 / n)
        for i in range(n):
            result.append(t0 + i * step)
    return result


def serialize_med(med, today=None):
    today = today or today_local()
    last = med.last_day
    if not med.active:
        status = 'paused'
    elif last and today > last:
        status = 'finished'
    elif med.start_date > today:
        status = 'planned'
    else:
        status = 'active'
    return {
        'id': med.id,
        'name': med.name,
        'description': med.description,
        'icon': med.icon,
        'start_date': med.start_date.isoformat(),
        'duration_type': med.duration_type,
        'duration_days': med.duration_days,
        'last_day': last.isoformat() if last else None,
        'times_per_day': med.times_per_day,
        'schedule_mode': med.schedule_mode,
        'exact_times': med.exact_times_list,
        'meal_condition': med.meal_condition,
        'meal_offset_minutes': med.meal_offset_minutes,
        'meal_label': med.meal_label(),
        'active': med.active,
        'status': status,
    }


def serialize_reminder(r):
    med = r.medication
    can_start = r.is_start_prompt and r.status in ('pending', 'overdue')
    return {
        'id': r.id,
        'medication_id': med.id,
        'med_name': med.name,
        'icon': med.icon,
        'description': med.description,
        'meal_label': med.meal_label(),
        'time': r.scheduled_for.strftime('%H:%M'),
        'scheduled_for': r.scheduled_for.strftime('%Y-%m-%dT%H:%M'),
        'date_label': r.scheduled_for.strftime('%d.%m.%Y'),
        'status': r.status,
        'status_label': STATUS_LABELS.get(r.status, r.status),
        'is_start_prompt': r.is_start_prompt,
        'can_act': r.status in ('pending', 'overdue'),
        'can_start': can_start,
    }
