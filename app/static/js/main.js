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

let _audio = null;
function playReminderSound() {
  api('/api/settings').then((s) => {
    try {
      if (_audio) _audio.pause();
      _audio = new Audio('/static/sounds/' + s.sound_file);
      _audio.volume = (Number(s.sound_volume) || 70) / 100;
      _audio.play().catch(() => {});
    } catch (e) { /* ignore */ }
  }).catch(() => {});
}

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
    playReminderSound();
    toast(d.body || d.title);
    window.dispatchEvent(new CustomEvent('reminder-fired', { detail: d }));
  };
  es.onerror = () => { /* сервер перезапустится — браузер переподключится */ };
}
