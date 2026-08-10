'use strict';

let currentStatus = '';

const DAYS_RU = ['воскресенье', 'понедельник', 'вторник', 'среда',
                 'четверг', 'пятница', 'суббота'];
const MONTHS_RU = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
                   'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'];

function initGreeting() {
  const now = new Date();
  const label = document.getElementById('date-label');
  label.textContent = DAYS_RU[now.getDay()] + ', ' + now.getDate() + ' ' +
    MONTHS_RU[now.getMonth()];

  const h = now.getHours();
  const title = document.getElementById('greet-title');
  const sub = document.getElementById('greet-sub');
  if (h >= 5 && h < 12) {
    title.textContent = 'Доброе утро! ☀️';
    sub.textContent = 'Надеюсь, вы хорошо спали.';
  } else if (h < 18) {
    title.textContent = 'Добрый день! 🌿';
    sub.textContent = 'Не забывайте про здоровье.';
  } else {
    title.textContent = 'Добрый вечер! 🌙';
    sub.textContent = 'Ещё есть время принять лекарства.';
  }
}

function reminderCard(r) {
  const d = document.createElement('div');
  d.className = 'card reminder ' + r.status;
  d.dataset.id = r.id;

  let actions = '';
  if (r.can_start) {
    actions = '<button class="btn btn-primary big" data-start="' + r.id + '">▶ Старт</button>';
  } else if (r.can_act && !r.is_start_prompt) {
    actions =
      '<button class="btn btn-ok" data-act="done" data-id="' + r.id + '">✓ Принято</button>' +
      '<button class="btn btn-ghost" data-act="postpone" data-id="' + r.id + '">⏰ Перенести</button>' +
      '<button class="btn btn-ghost" data-act="cancel" data-id="' + r.id + '">Отменить</button>';
  }

  const meal = r.meal_label ? '<div class="meal">🍽 ' + escapeHtml(r.meal_label) + '</div>' : '';
  const desc = r.description ? '<div class="desc">' + escapeHtml(r.description) + '</div>' : '';
  const promptBadge = r.is_start_prompt ? ' <span class="pill">утро</span>' : '';

  d.innerHTML =
    '<div class="r-top">' +
      '<span class="r-icon">' + escapeHtml(r.icon || '💊') + '</span>' +
      '<div class="r-main">' +
        '<div class="r-name">' + escapeHtml(r.med_name) + promptBadge + '</div>' +
        desc +
      '</div>' +
      '<span class="status ' + r.status + '">' + r.status_label + '</span>' +
    '</div>' +
    '<div class="r-time">' + escapeHtml(r.time) + '</div>' +
    meal +
    (actions ? '<div class="r-actions">' + actions + '</div>' : '');
  return d;
}

async function loadToday() {
  const url = '/api/today' + (currentStatus ? '?status=' + currentStatus : '');
  let data;
  try {
    data = await api(url);
  } catch (e) {
    document.getElementById('reminders').innerHTML = '';
    return;
  }
  todayCache = data.items;
  const el = document.getElementById('reminders');
  el.innerHTML = '';
  const empty = document.getElementById('empty');
  empty.classList.toggle('hidden', data.items.length > 0);
  if (!data.items.length && !currentStatus) {
    empty.innerHTML = '<div class="empty-icon">🌿</div><p>На сегодня всё спокойно.</p>';
  }
  data.items.forEach((r) => el.appendChild(reminderCard(r)));

  const pending = data.items.filter((r) => r.status === 'pending').length;
  const sub = document.getElementById('greet-sub');
  if (data.items.length) {
    sub.textContent = pending
      ? 'Запланировано напоминаний: ' + data.items.length + ' · ожидают: ' + pending
      : 'На сегодня всё запланировано.';
  }
}

function bindActions() {
  const list = document.getElementById('reminders');
  list.addEventListener('click', (e) => {
    const startBtn = e.target.closest('[data-start]');
    const actBtn = e.target.closest('[data-act]');
    if (startBtn) {
      const rid = startBtn.dataset.start;
      const item = todayCache.find((r) => String(r.id) === String(rid));
      if (!item) return;
      api('/api/medications/' + item.medication_id + '/start', { method: 'POST' })
        .then(() => {
          toast('Приёмы на сегодня распределены 🌿');
          loadToday();
        }).catch((err) => toast(err.message));
      return;
    }
    if (!actBtn) return;
    const id = actBtn.dataset.id;
    if (actBtn.dataset.act === 'done') act('/api/reminders/' + id + '/done', 'Принято ✅');
    else if (actBtn.dataset.act === 'cancel') act('/api/reminders/' + id + '/cancel', 'Напоминание отменено');
    else if (actBtn.dataset.act === 'postpone') window.postponeReminder(id);
  });
}

let todayCache = [];

async function init() {
  initGreeting();
  bindActions();

  document.getElementById('filters').addEventListener('click', (e) => {
    const chip = e.target.closest('.chip');
    if (!chip) return;
    document.querySelectorAll('#filters .chip').forEach((c) => c.classList.remove('active'));
    chip.classList.add('active');
    currentStatus = chip.dataset.status;
    loadToday();
  });

  window.addEventListener('reminder-fired', () => loadToday());

  await loadToday();
}

document.addEventListener('DOMContentLoaded', init);
