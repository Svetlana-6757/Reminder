import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
DB_PATH = os.path.join(DATA_DIR, 'reminder.db')
VAPID_PATH = os.path.join(DATA_DIR, 'vapid.json')
ICON_DIR = os.path.join(DATA_DIR, 'icons')
MED_PHOTO_DIR = os.path.join(DATA_DIR, 'med_photos')

# Часовой пояс сервера (в нём считаются напоминания)
TIMEZONE = os.environ.get('REMINDER_TZ', 'Europe/Moscow')
# Секретный ключ Flask. Обязательно замените на сервере.
SECRET_KEY = os.environ.get('REMINDER_SECRET', 'change-me-on-server')
# Публичный адрес приложения (для Web Push и mailto в VAPID)
BASE_URL = os.environ.get('REMINDER_BASE_URL', 'http://127.0.0.1:5000')

# Логика напоминаний
AUTO_OVERDUE_MINUTES = 15        # через сколько минут «Ожидает» -> «Просрочено»
REPEAT_INTERVAL_MINUTES = 5      # интервал повторного звукового сигнала
MAX_REPEATS = 3                  # сколько раз повторяется сигнал
WAKE_HOURS = 12                  # время бодрствования при авто-расписании
