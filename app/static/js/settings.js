'use strict';

function urlBase64ToUint8Array(base64) {
  const padding = '='.repeat((4 - (base64.length % 4)) % 4);
  const raw = atob((base64 + padding).replace(/-/g, '+').replace(/_/g, '/'));
  const out = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
  return out;
}

function b64(buffer) {
  const bytes = new Uint8Array(buffer);
  let bin = '';
  bytes.forEach((b) => { bin += String.fromCharCode(b); });
  return btoa(bin).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

let pushStatusEl = null;

function setPushStatus(text) {
  if (pushStatusEl) pushStatusEl.textContent = text;
}

async function initSettings() {
  let settings, sounds;
  try {
    settings = await api('/api/settings');
    sounds = await api('/api/sounds');
  } catch (e) { return; }

  document.getElementById('s-app-name').value = settings.app_name;
  document.getElementById('s-wake').value = settings.wake_time;
  document.getElementById('s-volume').value = settings.sound_volume;
  document.getElementById('volume-label').textContent = settings.sound_volume + '%';

  const sel = document.getElementById('s-sound');
  sel.innerHTML = '';
  sounds.forEach((s) => {
    const opt = document.createElement('option');
    opt.value = s.file;
    opt.textContent = s.label;
    sel.appendChild(opt);
  });
  sel.value = settings.sound_file;
  sel.addEventListener('change', () => {
    const a = new Audio('/static/sounds/' + sel.value);
    a.volume = (Number(document.getElementById('s-volume').value) || 70) / 100;
    a.play().catch(() => {});
  });

  const appIconRow = document.getElementById('app-icon-row');
  appIconRow.querySelectorAll('.emoji').forEach((b) => {
    if (b.dataset.emoji === settings.app_icon) b.classList.add('sel');
  });
  appIconRow.addEventListener('click', (e) => {
    const btn = e.target.closest('.emoji');
    if (!btn) return;
    appIconRow.querySelectorAll('.emoji').forEach((x) => x.classList.remove('sel'));
    btn.classList.add('sel');
  });

  const vol = document.getElementById('s-volume');
  vol.addEventListener('input', () => {
    document.getElementById('volume-label').textContent = vol.value + '%';
  });

  const playBtn = document.getElementById('btn-play-sound');
  playBtn.addEventListener('click', () => {
    const a = new Audio('/static/sounds/' + sel.value);
    a.volume = (Number(vol.value) || 70) / 100;
    a.play().catch(() => toast('Не удалось воспроизвести звук'));
  });

  document.getElementById('settings-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const iconEl = appIconRow.querySelector('.emoji.sel');
    const payload = {
      app_name: document.getElementById('s-app-name').value.trim() || 'Напоминания',
      app_icon: iconEl ? iconEl.dataset.emoji : '💊',
      wake_time: document.getElementById('s-wake').value || '08:00',
      sound_file: sel.value,
      sound_volume: vol.value,
    };
    try {
      await api('/api/settings', { method: 'POST', body: JSON.stringify(payload) });
      toast('Настройки сохранены');
      document.title = payload.app_name;
      document.querySelector('.brand-name').textContent = payload.app_name;
      document.querySelector('.brand-icon').textContent = payload.app_icon;
    } catch (err) { toast(err.message); }
  });

  const fileInput = document.getElementById('s-icon-file');
  fileInput.addEventListener('change', async () => {
    const file = fileInput.files[0];
    if (!file) return;
    const fd = new FormData();
    fd.append('icon', file);
    try {
      const res = await fetch('/api/settings/icon', { method: 'POST', body: fd });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Ошибка');
      toast('Иконка обновлена. Обновите страницу (может понадобиться очистка кэша).');
    } catch (err) { toast(err.message); }
  });

  // push
  pushStatusEl = document.getElementById('push-status');
  document.getElementById('btn-enable-push').addEventListener('click', enablePush);
  document.getElementById('btn-test-push').addEventListener('click', async () => {
    try {
      await api('/api/push/test', { method: 'POST' });
      toast('Проверочное уведомление отправлено');
    } catch (e) { toast(e.message); }
  });

  if (settings.push_active) {
    setPushStatus('✓ Уведомления уже подключены.');
  } else if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
    setPushStatus('Браузер не поддерживает push-уведомления. Откройте сайт в Chrome или Firefox на телефоне.');
  }
}

async function enablePush() {
  if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
    toast('Браузер не поддерживает push-уведомления');
    return;
  }
  try {
    if (!('Notification' in window)) {
      toast('Нет поддержки уведомлений');
      return;
    }
    if (Notification.permission === 'denied') {
      setPushStatus('Уведомления заблокированы в настройках браузера. Разрешите их вручную.');
      return;
    }
    const permission = await Notification.requestPermission();
    if (permission !== 'granted') {
      toast('Разрешение на уведомления не получено');
      return;
    }
    const reg = await navigator.serviceWorker.ready;
    const key = await api('/api/push/key');
    let sub = await reg.pushManager.getSubscription();
    if (!sub) {
      sub = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(key.key),
      });
    }
    await api('/api/push/subscribe', {
      method: 'POST',
      body: JSON.stringify({
        endpoint: sub.endpoint,
        keys: {
          p256dh: b64(sub.getKey('p256dh')),
          auth: b64(sub.getKey('auth')),
        },
      }),
    });
    setPushStatus('✓ Уведомления включены!');
    toast('Уведомления включены ✅');
  } catch (e) {
    toast('Ошибка: ' + e.message);
    setPushStatus('Не удалось подключить уведомления: ' + e.message);
  }
}

document.addEventListener('DOMContentLoaded', initSettings);
