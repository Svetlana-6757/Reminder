'use strict';

const PERIOD_LABEL = {
  permanent: 'постоянно',
  days: 'на несколько дней',
};
const MODE_LABEL = {
  exact: 'точное время',
  auto: 'утром «Старт»',
};

function fmtDate(iso) {
  if (!iso) return '';
  const [y, m, d] = iso.split('-');
  return d + '.' + m + '.' + y;
}

function medCard(m) {
  const d = document.createElement('div');
  d.className = 'card medication';
  d.dataset.id = m.id;
  d.style.cursor = 'pointer';

  const times = m.schedule_mode === 'exact'
    ? m.exact_times.join(', ')
    : m.times_per_day + ' раз(а) в день';
  const meal = m.meal_label ? ' · ' + m.meal_label : '';
  const period = m.duration_type === 'days'
    ? 'до ' + fmtDate(m.last_day)
    : 'постоянно';
  const statusLabel = m.status === 'active' ? 'активен' :
    m.status === 'paused' ? 'на паузе' :
    m.status === 'finished' ? 'курс завершён' :
    m.status === 'planned' ? 'ещё не начался' : m.status;

  d.innerHTML =
    '<div class="r-top">' +
      '<span class="r-icon">' + escapeHtml(m.icon) + '</span>' +
      '<div class="r-main">' +
        '<div class="r-name">' + escapeHtml(m.name) + '</div>' +
        '<div class="desc">' + escapeHtml(times) + escapeHtml(meal) + '</div>' +
        '<div class="desc">' + escapeHtml(period) + '</div>' +
      '</div>' +
      '<span class="status ' + m.status + '">' + statusLabel + '</span>' +
    '</div>' +
    '<div class="r-actions">' +
      '<button class="btn btn-ghost" data-nav="' + m.id + '">Открыть</button>' +
      '<button class="btn btn-ghost" data-edit="' + m.id + '">Изменить</button>' +
      '<button class="btn btn-danger" data-del="' + m.id + '">Удалить</button>' +
    '</div>';
  return d;
}

async function loadMeds() {
  let meds;
  try {
    meds = await api('/api/medications');
  } catch (e) {
    return;
  }
  const q = (document.getElementById('med-search').value || '').toLowerCase().trim();
  if (q) meds = meds.filter((m) => m.name.toLowerCase().includes(q));

  const el = document.getElementById('med-list');
  el.innerHTML = '';
  document.getElementById('med-empty').classList.toggle('hidden', meds.length > 0);
  meds.forEach((m) => el.appendChild(medCard(m)));
}

function init() {
  loadMeds();

  document.getElementById('med-search').addEventListener('input', loadMeds);

  document.getElementById('med-list').addEventListener('click', (e) => {
    const nav = e.target.closest('[data-nav]');
    const edit = e.target.closest('[data-edit]');
    const del = e.target.closest('[data-del]');
    if (nav) {
      window.location.href = '/medications/' + nav.dataset.nav;
      return;
    }
    if (edit) {
      window.location.href = '/medications/' + edit.dataset.edit + '/edit';
      return;
    }
    if (del) {
      const id = del.dataset.del;
      if (!confirm('Удалить лекарство и всю историю приёма?')) return;
      api('/api/medications/' + id, { method: 'DELETE' })
        .then(() => { toast('Удалено'); loadMeds(); })
        .catch((err) => toast(err.message));
    }
  });
}

document.addEventListener('DOMContentLoaded', init);
