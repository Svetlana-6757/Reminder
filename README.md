# Структура проекта

- `run.py` — точка входа приложения
- `config.py` — настройки (часовой пояс, секретный ключ, логика напоминаний)
- `app/` — исходный код приложения
  - `__init__.py` — создание Flask-приложения, планировщика, иконок и звуков
  - `models.py` — модели базы данных (лекарства, напоминания, настройки, push-подписки)
  - `logic.py` — расчёт расписания, сериализация
  - `scheduler.py` — планировщик: генерация напоминаний, срабатывания, статусы, повторы
  - `notify.py` — формирование вежливых уведомлений
  - `push.py` — Web Push (VAPID)
  - `events.py` — SSE-канал для живого обновления страниц
  - `assets.py` — генерация иконок (Pillow) и звуков (WAV)
  - `routes/` — страницы (`main.py`) и REST API (`api.py`)
  - `templates/` — HTML-шаблоны
  - `static/` — CSS, JS, сервис-воркер, звуки
- `data/` — создаётся автоматически: база, ключи VAPID, иконки

# Запуск локально (Windows)

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

Откройте http://127.0.0.1:5000

# Установка на российском сервере (Ubuntu/Debian)

```
sudo apt update
sudo apt install -y python3 python3-venv python3-pip nginx
```

Скопируйте проект, затем:

```
cd Reminder
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Настройки через переменные окружения (в systemd):

- `REMINDER_TZ` — часовой пояс, по умолчанию `Europe/Moscow`
- `REMINDER_SECRET` — секретный ключ Flask (обязательно смените!)
- `REMINDER_BASE_URL` — публичный адрес, например `https://reminders.example.ru`

## systemd-сервис (`/etc/systemd/system/reminder.service`)

```ini
[Unit]
Description=Reminder app
After=network.target

[Service]
WorkingDirectory=/opt/Reminder
ExecStart=/opt/Reminder/.venv/bin/gunicorn -w 1 -k gthread --threads 8 --timeout 120 -b 127.0.0.1:5000 run:app
Restart=always
User=www-data
Environment=REMINDER_SECRET=поменяйте-меня
Environment=REMINDER_BASE_URL=https://reminders.example.ru

[Install]
WantedBy=multi-user.target
```

```
sudo systemctl daemon-reload
sudo systemctl enable --now reminder
```

> **Важно:** один worker (`-w 1`). Планировщик живёт в процессе приложения —
> при нескольких воркерах напоминания будут дублироваться.

## Nginx + HTTPS (обязательно для уведомлений)

`/etc/nginx/sites-available/reminder`:

```
server {
    listen 80;
    server_name reminders.example.ru;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_buffering off;
    }
}
```

```
sudo ln -s /etc/nginx/sites-available/reminder /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d reminders.example.ru
```

# Как включить уведомления на телефоне

1. Откройте сайт в Chrome (Android) или Safari (iPhone).
2. Настройки → «Включить уведомления» → разрешите уведомления браузеру.
3. «Добавить на главный экран» — так напоминания станут как у настоящего приложения.

# Как это работает

- **Точное время.** Для каждого дня курса приёма создаются напоминания на указанные часы.
- **Авто-режим («Старт»).** Каждое утро в заданное время приходит напоминание нажать «Старт».
  Приложение делит 12 часов бодрствования на нужное число приёмов и создаёт расписание на день.
- **Срабатывание.** Напоминание показывает push-уведомление поверх всех окон.
  Повторный сигнал — каждые 5 минут, до 3 раз. Через 15 минут без реакции статус
  меняется на «Просрочено».
- **Действия:** «Принято», «Перенести» (пресеты или своё время), «Отменить».
- **Окончание курса.** Когда срок приёма (дней) прошёл, напоминания перестают появляться,
  но карточка и история остаются.
- **Звук и громкость** выбираются в настройках. Если приложение открыто — звук играет сразу;
  когда оно закрыто, звук уведомления использует системные настройки телефона.
