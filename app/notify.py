import json

from . import push
from .events import hub


def _payload(reminder, kind):
    med = reminder.medication
    t = reminder.scheduled_for.strftime('%H:%M')
    meal = med.meal_label()

    if reminder.is_start_prompt:
        title = 'Доброе утро! 🌅'
        body = (f'Пора начинать приём «{med.name}». Нажмите «Старт» в приложении — '
                f'я сам распределю приёмы на день.')
    elif kind == 'overdue':
        title = f'⏰ «{med.name}» — приём просрочен'
        body = (f'Было запланировано на {t}, но ещё не отмечено. '
                f'Пожалуйста, примите лекарство или перенесите приём.')
    elif kind == 'repeat':
        note = f' ({meal})' if meal else ''
        title = f'🔔 Ещё напоминаю: {med.name}'
        body = f'Всё ещё жду{note}. Примите, пожалуйста, или перенесите приём.'
    else:
        title = f'{med.icon} Пора принять {med.name}'
        body = f'Запланировано на {t}.'.strip()
        if meal:
            body += f' Принимать {meal}.'

    return {
        'type': 'reminder',
        'id': reminder.id,
        'kind': kind,
        'title': title,
        'body': body,
        'url': '/?focus=' + str(reminder.id),
    }


def fire(reminder, kind='due'):
    payload = _payload(reminder, kind)
    hub.publish(json.dumps({
        'type': 'reminder',
        'id': reminder.id,
        'kind': kind,
        'title': payload['title'],
        'body': payload['body'],
    }))
    push.send_async(payload)
