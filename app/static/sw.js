'use strict';

self.addEventListener('install', (e) => {
  self.skipWaiting();
});

self.addEventListener('activate', (e) => {
  e.waitUntil(clients.claim());
});

self.addEventListener('push', (e) => {
  let data = { title: 'Напоминание', body: '', url: '/', id: null, kind: 'due' };
  if (e.data) {
    try { data = Object.assign(data, e.data.json()); } catch (err) {}
  }

  const options = {
    body: data.body,
    icon: '/icon-192.png',
    badge: '/icon-192.png',
    vibrate: [180, 90, 180],
    tag: 'rem-' + (data.id || Date.now()),
    renotify: true,
    data: { url: data.url || '/', id: data.id, kind: data.kind },
    actions: [
      { action: 'done', title: '✓ Принято' },
      { action: 'open', title: 'Открыть' },
    ],
  };
  if (data.kind === 'overdue') options.vibrate = [300, 120, 300, 120, 400];

  e.waitUntil(self.registration.showNotification(data.title, options));
});

self.addEventListener('notificationclick', (e) => {
  const n = e.notification;
  n.close();
  const data = n.data || {};

  if (e.action === 'done' && data.id) {
    e.waitUntil(
      fetch('/api/reminders/' + data.id + '/done', { method: 'POST' })
        .catch(() => {})
    );
    return;
  }

  const target = data.url || '/';
  e.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((list) => {
      for (const c of list) {
        if ('focus' in c) return c.navigate(target).then(() => c.focus()).catch(() => c.focus());
      }
      return clients.openWindow(target);
    })
  );
});
