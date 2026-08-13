'use strict';

const api = async (url, opts = {}) => {
  const init = { headers: { 'Content-Type': 'application/json' }, ...opts };
  const res = await fetch(url, init);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || ('Ошибка ' + res.status));
  return data;
};

const escapeHtml = (s) => String(s == null ? '' : s)
  .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  .replace(/"/g, '&quot;');

const toast = (msg) => {
  const el = document.getElementById('toast');
  if (!el) return;
  el.textContent = msg;
  el.classList.add('show');
  clearTimeout(el._t);
  el._t = setTimeout(() => el.classList.remove('show'), 4200);
};

const STATUS_RU = {
  pending: 'Ожидает',
  done: 'Готово',
  overdue: 'Просрочено',
  cancelled: 'Отменено',
};

// Показывает фото (если есть) или иконку-эмодзи
const iconHtml = (item, cls = '') =>
  item.photo_url
    ? '<span class="r-icon ' + cls + '"><img src="' + item.photo_url + '" alt=""></span>'
    : '<span class="r-icon ' + cls + '">' + escapeHtml(item.icon || '💊') + '</span>';

// ---------- звук ----------
let _audio = null;
let _soundBlocked = false;

function playReminderSound() {
  api('/api/settings').then((s) => {
    try {
      if (_audio) _audio.pause();
      _audio = new Audio('/static/sounds/' + s.sound_file);
      _audio.volume = (Number(s.sound_volume) || 70) / 100;
      const p = _audio.play();
      if (p && p.catch) p.catch(() => { _soundBlocked = true; });
    } catch (e) { _soundBlocked = true; }
  }).catch(() => {});
}

// Браузер Chrome не даёт играть звук без действия пользователя.
// После первого клика повторяем звук, если первый раз он не сыграл.
document.addEventListener('pointerdown', function retrySound() {
  if (_soundBlocked && _audio) {
    _soundBlocked = false;
    _audio.currentTime = 0;
    const p = _audio.play();
    if (p && p.catch) p.catch(() => {});
  }
}, { once: true });

function showSheet(html, onMount) {
  const root = document.getElementById('overlay-root');
  const ov = document.createElement('div');
  ov.className = 'overlay';
  ov.innerHTML = '<div class="sheet">' + html + '</div>';
  ov.addEventListener('click', (e) => {
    if (e.target === ov) ov.remove();
  });
  root.appendChild(ov);
  if (onMount) onMount(ov);
  return ov;
}

// ---------- большое напоминание (висит, пока не выполнена команда) ----------
const reminderQueue = [];
let currentOverlay = null;

function showReminder(d) {
  // то же напоминание уже показывается (повтор/просрочка) — просто прозвучим
  if (currentOverlay && currentOverlay.d.id === d.id) {
    playReminderSound();
    if (d.kind === 'overdue') {
      const st = currentOverlay.ov.querySelector('[data-ov-status]');
      if (st) {
        st.textContent = 'Просрочено';
        st.className = 'status overdue';
      }
    }
    pulseOverlay();
    return;
  }
  if (reminderQueue.some((q) => q.id === d.id)) return;
  reminderQueue.push(d);
  renderReminder();
}

function pulseOverlay() {
  if (!currentOverlay) return;
  const sheet = currentOverlay.ov.querySelector('.sheet');
  if (!sheet) return;
  sheet.classList.remove('pulse');
  void sheet.offsetWidth;
  sheet.classList.add('pulse');
}

function renderReminder() {
  if (currentOverlay || reminderQueue.length === 0) return;
  const d = reminderQueue.shift();
  const root = document.getElementById('overlay-root');

  let actions;
  if (d.is_start_prompt) {
    actions = '<button class="btn btn-primary big" data-ov-start>▶ Старт</button>';
  } else {
    actions =
      '<button class="btn btn-ok" data-ov-done>✓ Принято</button>' +
      '<button class="btn btn-ghost" data-ov-postpone>⏰ Перенести</button>' +
      '<button class="btn btn-ghost" data-ov-cancel>Отменить</button>';
  }

  const desc = d.description
    ? '<div class="rem-desc">' + escapeHtml(d.description) + '</div>' : '';
  const meal = d.meal_label
    ? '<div class="meal">🍽 ' + escapeHtml(d.meal_label) + '</div>' : '';
  const subtitle = d.is_start_prompt
    ? '<div class="rem-note">Нажмите «Старт» — я распределю приёмы на день.</div>'
    : '<div class="rem-when">Запланировано: ' + escapeHtml(d.time) +
      ' · ' + escapeHtml(d.date_label) + '</div>';

  const ov = document.createElement('div');
  ov.className = 'overlay rem-overlay';
  ov.innerHTML =
    '<div class="sheet reminder-sheet">' +
      '<div class="rem-head">' +
        iconHtml(d, 'big') +
        '<div class="rem-title-block">' +
          '<div class="rem-title">' + escapeHtml(d.med_name || d.title) + '</div>' +
          subtitle +
        '</div>' +
        '<span class="status ' + (d.status || 'pending') + '" data-ov-status>' +
          escapeHtml(d.status_label || STATUS_RU[d.status] || 'Ожидает') + '</span>' +
      '</div>' +
      desc +
      meal +
      '<div class="rem-actions">' + actions + '</div>' +
    '</div>';
  root.appendChild(ov);
  currentOverlay = { ov, d };
  playReminderSound();

  ov.querySelector('[data-ov-done]') &&
    ov.querySelector('[data-ov-done]').addEventListener('click', () =>
      actReminder(d.id, 'done', 'Принято ✅'));
  ov.querySelector('[data-ov-cancel]') &&
    ov.querySelector('[data-ov-cancel]').addEventListener('click', () =>
      actReminder(d.id, 'cancel', 'Напоминание отменено'));
  ov.querySelector('[data-ov-postpone]') &&
    ov.querySelector('[data-ov-postpone]').addEventListener('click', () =>
      postponeReminder(d.id));
  ov.querySelector('[data-ov-start]') &&
    ov.querySelector('[data-ov-start]').addEventListener('click', () =>
      api('/api/medications/' + d.medication_id + '/start', { method: 'POST' })
        .then(() => {
          toast('Приёмы на сегодня распределены 🌿');
          closeReminder();
        })
        .catch((e) => toast(e.message)));
}

function closeReminder() {
  if (currentOverlay) {
    currentOverlay.ov.remove();
    currentOverlay = null;
  }
  renderReminder();
}

async function actReminder(id, action, okMsg) {
  try {
    await api('/api/reminders/' + id + '/' + action, { method: 'POST' });
    toast(okMsg);
    closeReminder();
    window.dispatchEvent(new CustomEvent('reminder-fired', { detail: { id } }));
  } catch (e) {
    toast(e.message);
  }
}

function postponeReminder(id) {
  const sh = showSheet(
    '<h3>Перенести приём ⏰</h3>' +
    '<div class="pp-presets">' +
      '<button class="btn btn-ghost" data-m="30">Через 30 мин</button>' +
      '<button class="btn btn-ghost" data-m="60">Через 1 час</button>' +
      '<button class="btn btn-ghost" data-m="120">Через 2 часа</button>' +
      '<button class="btn btn-ghost" data-m="180">Через 3 часа</button>' +
    '</div>' +
    '<label class="muted small">Или выберите своё время:</label>' +
    '<input type="datetime-local" id="pp-dt" style="margin:8px 0 14px">' +
    '<div class="form-actions">' +
      '<button class="btn btn-primary" id="pp-ok">Перенести</button>' +
      '<button class="btn btn-ghost" id="pp-cancel">Закрыть</button>' +
    '</div>');

  const doPostpone = (payload) =>
    api('/api/reminders/' + id + '/postpone', { method: 'POST', body: JSON.stringify(payload) })
      .then(() => {
        sh.remove();
        toast('Приём перенесён');
        closeReminder();
        window.dispatchEvent(new CustomEvent('reminder-fired', { detail: { id } }));
      })
      .catch((e) => toast(e.message));

  sh.querySelectorAll('[data-m]').forEach((b) =>
    b.addEventListener('click', (e) => {
      e.stopPropagation();
      doPostpone({ minutes: Number(e.target.dataset.m) });
    }));
  sh.querySelector('#pp-ok').addEventListener('click', () => {
    const v = document.getElementById('pp-dt').value;
    if (v) doPostpone({ at: new Date(v).toISOString() });
    else doPostpone({ minutes: 60 });
  });
  sh.querySelector('#pp-cancel').addEventListener('click', () => sh.remove());
}
window.postponeReminder = postponeReminder;

// ---------- service worker + live-обновления ----------
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch(() => {});
  });
}

if (window.EventSource) {
  const es = new EventSource('/events');
  es.onmessage = (ev) => {
    let d;
    try { d = JSON.parse(ev.data); } catch (e) { return; }
    if (d.type !== 'reminder') return;
    showReminder(d);
    window.dispatchEvent(new CustomEvent('reminder-fired', { detail: d }));
  };
  es.onerror = () => { /* сервер перезапустится — браузер переподключится */ };
}
