import threading
from datetime import timedelta

from apscheduler.schedulers.background import BackgroundScheduler

import config
from . import notify
from .logic import (day_span, intake_times_for_day, now_local,
                    today_local, wake_time_for_day)
from .models import Medication, Reminder, db


class SchedulerManager:
    """Планировщик: генерация напоминаний, обработка срабатываний, статусов."""

    def __init__(self, app):
        self.app = app
        self.scheduler = BackgroundScheduler(timezone=app.config['TIMEZONE'])

    def start(self):
        self.scheduler.add_job(
            self.tick, 'interval', seconds=30, id='tick',
            max_instances=1, coalesce=True, replace_existing=True)
        self.scheduler.start()
        threading.Thread(target=self._safe_tick, daemon=True).start()

    def _safe_tick(self):
        try:
            self.tick()
        except Exception as e:  # noqa: BLE001
            print('scheduler tick error:', e)

    # ------------------------------------------------------------------ tick

    def tick(self):
        with self.app.app_context():
            self._ensure_reminders()
            self._process_due()

    # --------------------------------------------------------- генерация

    def _ensure_reminders(self):
        today = today_local()
        tomorrow = today + timedelta(days=1)
        changed = False
        for med in Medication.query.filter_by(active=True).all():
            if med.schedule_mode == 'exact':
                for day in (today, tomorrow):
                    if med.in_period(day) and self._ensure_exact_day(med, day):
                        changed = True
            else:
                if med.in_period(today) and self._ensure_start_prompt(med, today):
                    changed = True
        if changed:
            db.session.commit()

    def _ensure_exact_day(self, med, day):
        start, end = day_span(day)
        exists = med.reminders.filter(
            Reminder.scheduled_for >= start,
            Reminder.scheduled_for < end,
            Reminder.is_start_prompt.is_(False),
        ).first()
        if exists:
            return False
        now = now_local()
        for sched in intake_times_for_day(med, day):
            if day == today_local() and sched < now:
                continue
            db.session.add(Reminder(medication_id=med.id, scheduled_for=sched))
        return True

    def _ensure_start_prompt(self, med, today):
        start, end = day_span(today)
        exists = med.reminders.filter(
            Reminder.scheduled_for >= start,
            Reminder.scheduled_for < end,
            Reminder.is_start_prompt.is_(True),
        ).first()
        if exists:
            return False
        when = wake_time_for_day(today)
        db.session.add(Reminder(
            medication_id=med.id, scheduled_for=when, is_start_prompt=True))
        return True

    def regen(self, med):
        """Пересоздать напоминания после сохранения карточки."""
        with self.app.app_context():
            today = today_local()
            tomorrow = today + timedelta(days=1)
            changed = False
            if med.active:
                if med.schedule_mode == 'exact':
                    for day in (today, tomorrow):
                        if med.in_period(day) and self._ensure_exact_day(med, day):
                            changed = True
                else:
                    if med.in_period(today) and self._ensure_start_prompt(med, today):
                        changed = True
            if changed:
                db.session.commit()

    def start_day(self, med, day):
        """Кнопка «Старт» для режима «само»: распределить приёмы на день."""
        start, end = day_span(day)
        existing = med.reminders.filter(
            Reminder.scheduled_for >= start,
            Reminder.scheduled_for < end,
            Reminder.is_start_prompt.is_(False),
        ).count()
        if existing:
            return 0
        now = now_local()
        count = 0
        for sched in intake_times_for_day(med, day):
            if sched < now:
                continue
            db.session.add(Reminder(medication_id=med.id, scheduled_for=sched))
            count += 1
        db.session.commit()
        return count

    # --------------------------------------------------------- срабатывания

    def _process_due(self):
        now = now_local()
        changed = False

        # первичное срабатывание
        due = Reminder.query.filter(
            Reminder.status == 'pending',
            Reminder.scheduled_for <= now,
            Reminder.notified_at.is_(None),
        ).all()
        for r in due:
            kind = 'start' if r.is_start_prompt else 'due'
            notify.fire(r, kind=kind)
            r.notified_at = now
            changed = True
        if changed:
            db.session.commit()

        # повторы и автопросрочка
        candidates = Reminder.query.filter(
            Reminder.status == 'pending',
            Reminder.notified_at.isnot(None),
            Reminder.scheduled_for <= now,
        ).all()
        changed = False
        for r in candidates:
            minutes = (now - r.scheduled_for).total_seconds() // 60
            if (not r.is_start_prompt
                    and r.repeat_count < config.MAX_REPEATS
                    and minutes >= config.REPEAT_INTERVAL_MINUTES * (r.repeat_count + 1)):
                notify.fire(r, kind='repeat')
                r.repeat_count += 1
                changed = True
            if minutes >= config.AUTO_OVERDUE_MINUTES and r.status == 'pending':
                r.status = 'overdue'
                notify.fire(r, kind='overdue')
                changed = True
        if changed:
            db.session.commit()
