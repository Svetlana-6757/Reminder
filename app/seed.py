from .models import Setting

DEFAULTS = {
    'app_name': 'Напоминания',
    'app_icon': '💊',
    'wake_time': '08:00',
    'sound_file': 'chime.wav',
    'sound_volume': '70',
}


def seed_defaults():
    for key, value in DEFAULTS.items():
        if Setting.get(key) is None:
            Setting.set(key, value)
