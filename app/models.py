import json
from datetime import date, datetime, timedelta

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Medication(db.Model):
    __tablename__ = 'medications'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default='')
    icon = db.Column(db.String(16), default='💊')
    start_date = db.Column(db.Date, nullable=False, default=date.today)
    # срок приёма: permanent | days
    duration_type = db.Column(db.String(10), nullable=False, default='permanent')
    duration_days = db.Column(db.Integer, nullable=True)
    times_per_day = db.Column(db.Integer, nullable=False, default=1)
    # режим времени: exact | auto
    schedule_mode = db.Column(db.String(10), nullable=False, default='exact')
    exact_times = db.Column(db.Text, default='[]')  # JSON-список ["08:00", ...]
    # условия приёма: none | before | after | during
    meal_condition = db.Column(db.String(10), default='none')
    meal_offset_minutes = db.Column(db.Integer, default=0)
    photo = db.Column(db.String(255), nullable=True)  # файл фото упаковки
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    reminders = db.relationship(
        'Reminder', backref='medication', lazy='dynamic',
        cascade='all, delete-orphan')

    @property
    def exact_times_list(self):
        try:
            return json.loads(self.exact_times or '[]')
        except Exception:
            return []

    @property
    def last_day(self):
        if self.duration_type == 'days' and self.duration_days:
            return self.start_date + timedelta(days=self.duration_days - 1)
        return None

    def in_period(self, day):
        if day < self.start_date:
            return False
        last = self.last_day
        if last and day > last:
            return False
        return True

    def is_active_today(self, today=None):
        today = today or date.today()
        if not self.active:
            return False
        return self.in_period(today)

    def meal_label(self):
        off = self.meal_offset_minutes
        labels = {
            'none': '',
            'before': f'за {off} мин до еды' if off else 'до еды',
            'after': f'через {off} мин после еды' if off else 'после еды',
            'during': 'во время еды',
        }
        return labels.get(self.meal_condition, '')


class Reminder(db.Model):
    __tablename__ = 'reminders'

    id = db.Column(db.Integer, primary_key=True)
    medication_id = db.Column(db.Integer, db.ForeignKey('medications.id'), nullable=False)
    scheduled_for = db.Column(db.DateTime, nullable=False, index=True)
    # pending | done | overdue | cancelled
    status = db.Column(db.String(10), default='pending', index=True)
    repeat_count = db.Column(db.Integer, default=0)
    notified_at = db.Column(db.DateTime, nullable=True)
    done_at = db.Column(db.DateTime, nullable=True)
    is_start_prompt = db.Column(db.Boolean, default=False)
    postponed_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Setting(db.Model):
    __tablename__ = 'settings'

    key = db.Column(db.String(50), primary_key=True)
    value = db.Column(db.Text, default='')

    @staticmethod
    def get(key, default=None):
        s = db.session.get(Setting, key)
        return s.value if s is not None else default

    @staticmethod
    def set(key, value):
        s = db.session.get(Setting, key)
        if s is not None:
            s.value = str(value)
        else:
            db.session.add(Setting(key=key, value=str(value)))
        db.session.commit()


class PushSubscription(db.Model):
    __tablename__ = 'push_subscriptions'

    id = db.Column(db.Integer, primary_key=True)
    endpoint = db.Column(db.Text, nullable=False, unique=True)
    p256dh = db.Column(db.Text, nullable=False)
    auth = db.Column(db.Text, nullable=False)


def ensure_schema():
    """Лёгкая миграция для уже существующих баз (добавляет новые колонки)."""
    from sqlalchemy import inspect, text
    insp = inspect(db.engine)
    cols = [c['name'] for c in insp.get_columns('medications')]
    if 'photo' not in cols:
        with db.engine.begin() as conn:
            conn.execute(text('ALTER TABLE medications ADD COLUMN photo VARCHAR(255)'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
