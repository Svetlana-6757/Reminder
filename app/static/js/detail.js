'use strict';

const MED_PERIOD = {
  permanent: 'Постоянно',
  days: 'Курс на дней',
};
const MED_MODE = {
  exact: 'Точное время',
  auto: 'Авто: утром «Старт»',
};
const MEAL_LABEL = {
  none: 'Без условий',
  before: 'До еды',
  after: 'После еды',
  during: 'Во время еды',
};
const STATUS_LABEL = {
  active: 'активен',
  paused: 'на паузе',
  finished: 'курс завершён',
  planned: 'ещё не начался',
};

function groupByDate(items) {
  const groups = {};
  items.forEach((r) => {
    const key = r.scheduled_for.slice(0, 10);
    (groups[key] = groups[key] || []).push(r);
  });
  return Object.entries(groups);
}

function fmtDt(v) {
  const [d, t] = v.split('T');
  const [y, m, dd] = d.split('-');
  return dd + '.' + m + '.' + y;
}

async function loadDetail() {
  let med, history;
  try {
    med = await api('/api/medications/' + window.MED_ID);
    history = await api('/api/medications/' + window.MED_ID + '/history');
  } catch (e) {
    toast(e.message);
    return;
  }

  const st = document.getElementById('med-status');
  st.textContent = STATUS_LABEL[med.status] || med.status;
  st.className = 'status ' + med.status;

  const times = med.schedule_mode === 'exact'
    ? med.exact_times.join(', ')
    : med.times_per_day + ' раз(а) в день (авто)';
  const period = med.duration_type === 'days'
    ? (med.duration_days + ' дн. · до ' + fmtDt(med.last_day))
    : 'Постоянно';

  const meta = document.getElementById('med-meta');
  meta.innerHTML =
    '<div class="item"><div class="k">Режим</div><div>' + escapeHtml(MED_MODE[med.schedule_mode]) + '</div></div>' +
    '<div class="item"><div class="k">Время</div><div>' + escapeHtml(times) + '</div></div>' +
    '<div class="item"><div class="k">Срок</div><div>' + escapeHtml(period) + '</div></div>' +
    '<div class="item"><div class="k">Условия</div><div>' + escapeHtml(MEAL_LABEL[med.meal_condition] || '') +
      (med.meal_offset_minutes && med.meal_condition !== 'none'
        ? ' (' + med.meal_offset_minutes + ' мин)' : '') + '</div></div>';

  const desc = document.getElementById('med-desc');
  desc.textContent = med.description;
  if (!med.description) desc.classList.add('hidden');
  else desc.classList.remove('hidden');

  const histEl = document.getElementById('history');
  histEl.innerHTML = '';
  const empty = document.getElementById('hist-empty');
  empty.classList.toggle('hidden', history.length > 0);

  groupByDate(history).forEach(([date, rows]) => {
    const head = document.createElement('div');
    head.className = 'section-title';
    head.style.margin = '14px 0 6px';
    head.style.fontSize = '13px';
    head.style.color = 'var(--muted)';
    head.textContent = fmtDt(date);
    histEl.appendChild(head);
    rows.forEach((r) => {
      const row = document.createElement('div');
      row.className = 'card history-row';
      row.innerHTML =
        '<span class="time">' + escapeHtml(r.time) + '</span>' +
        '<span class="muted small">' + escapeHtml(r.med_name) + '</span>' +
        '<span style="margin-left:auto" class="status ' + r.status + '">' +
          r.status_label + '</span>';
      histEl.appendChild(row);
    });
  });
}

function init() {
  loadDetail();

  const toggle = document.getElementById('btn-toggle');
  const del = document.getElementById('btn-delete');
  if (toggle) {
    toggle.addEventListener('click', async () => {
      try {
        const m = await api('/api/medications/' + window.MED_ID + '/toggle', { method: 'POST' });
        toast(m.active ? 'Приём возобновлён' : 'На паузе');
        loadDetail();
      } catch (e) { toast(e.message); }
    });
  }
  if (del) {
    del.addEventListener('click', () => {
      if (!confirm('Удалить лекарство и всю историю приёма?')) return;
      api('/api/medications/' + window.MED_ID, { method: 'DELETE' })
        .then(() => { window.location.href = '/medications'; })
        .catch((e) => toast(e.message));
    });
  }
}

document.addEventListener('DOMContentLoaded', init);
