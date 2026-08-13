'use strict';

let state = {
  duration: 'permanent',
  mode: 'exact',
  meal: 'none',
  times: 1,
  exactTimes: [],
  photoFile: null,
  removePhoto: false,
};

function readState() {
  state.duration = document.querySelector('#seg-duration .seg-item.sel').dataset.val;
  state.mode = document.querySelector('#seg-mode .seg-item.sel').dataset.val;
  state.meal = document.querySelector('#seg-meal .seg-item.sel').dataset.val;
  state.times = Math.max(1, parseInt(document.getElementById('f-times').value, 10) || 1);
  state.exactTimes = Array.from(document.querySelectorAll('.time-input'))
    .map((i) => i.value)
    .filter(Boolean);
}

function renderTimes() {
  const list = document.getElementById('times-list');
  list.innerHTML = '';
  for (let i = 0; i < state.times; i++) {
    const wrap = document.createElement('div');
    wrap.className = 'inline';
    wrap.style.marginBottom = '8px';
    const input = document.createElement('input');
    input.type = 'time';
    input.className = 'time-input';
    input.value = state.exactTimes[i] || '';
    wrap.appendChild(input);
    list.appendChild(wrap);
  }
}

function syncUI() {
  document.querySelectorAll('#seg-duration .seg-item').forEach((b) =>
    b.classList.toggle('sel', b.dataset.val === state.duration));
  document.querySelectorAll('#seg-mode .seg-item').forEach((b) =>
    b.classList.toggle('sel', b.dataset.val === state.mode));
  document.querySelectorAll('#seg-meal .seg-item').forEach((b) =>
    b.classList.toggle('sel', b.dataset.val === state.meal));

  document.getElementById('days-wrap').classList.toggle('hidden', state.duration !== 'days');
  document.getElementById('exact-wrap').classList.toggle('hidden', state.mode !== 'exact');
  document.getElementById('auto-hint').classList.toggle('hidden', state.mode !== 'auto');
  document.getElementById('offset-wrap').classList.toggle('hidden',
    state.meal !== 'before' && state.meal !== 'after');

  if (state.mode === 'exact') renderTimes();
  const n = state.times;
  document.getElementById('auto-hint').textContent =
    'Каждое утро я напомню нажать «Старт» и сам равномерно распределю приёмы на 12 часов бодрствования.';
}

function bindSeg() {
  ['seg-duration', 'seg-mode', 'seg-meal'].forEach((id) => {
    document.getElementById(id).addEventListener('click', (e) => {
      const btn = e.target.closest('.seg-item');
      if (!btn) return;
      readState();
      if (id === 'seg-duration') state.duration = btn.dataset.val;
      if (id === 'seg-mode') state.mode = btn.dataset.val;
      if (id === 'seg-meal') state.meal = btn.dataset.val;
      syncUI();
    });
  });
}

async function submit() {
  readState();
  const name = document.getElementById('f-name').value.trim();
  if (!name) { toast('Укажите название лекарства'); return; }
  if (state.mode === 'exact' && state.exactTimes.length === 0) {
    toast('Укажите время приёма');
    return;
  }

  const payload = {
    name,
    description: document.getElementById('f-desc').value,
    icon: document.querySelector('.emoji.sel') ? document.querySelector('.emoji.sel').dataset.emoji : '💊',
    start_date: document.getElementById('f-start').value,
    duration_type: state.duration,
    duration_days: parseInt(document.getElementById('f-days').value, 10) || 7,
    times_per_day: state.times,
    schedule_mode: state.mode,
    exact_times: state.exactTimes,
    meal_condition: state.meal,
    meal_offset_minutes: parseInt(document.getElementById('f-offset').value, 10) || 0,
  };

  const editing = window.MED_ID || null;
  try {
    let med;
    if (editing) {
      med = await api('/api/medications/' + editing, { method: 'PUT', body: JSON.stringify(payload) });
    } else {
      med = await api('/api/medications', { method: 'POST', body: JSON.stringify(payload) });
    }

    // фото
    if (state.removePhoto) {
      await api('/api/medications/' + med.id + '/photo', { method: 'DELETE' });
    } else if (state.photoFile) {
      const fd = new FormData();
      fd.append('photo', state.photoFile);
      const res = await fetch('/api/medications/' + med.id + '/photo', { method: 'POST', body: fd });
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        throw new Error(d.error || 'Не удалось загрузить фото');
      }
    }

    toast(editing ? 'Сохранено' : 'Лекарство добавлено 🌿');
    window.location.href = '/medications';
  } catch (e) {
    toast(e.message);
  }
}

// ---------- фото ----------
function updatePhotoPreview() {
  const prev = document.getElementById('photo-preview');
  const removeBtn = document.getElementById('btn-remove-photo');
  if (state.photoFile) {
    prev.innerHTML = '<img src="' + URL.createObjectURL(state.photoFile) + '" alt="">';
    removeBtn.classList.remove('hidden');
  } else if (window.MED_HAS_PHOTO && !state.removePhoto) {
    prev.innerHTML = '<img src="/med-photo/' + window.MED_ID + '" alt="">';
    removeBtn.classList.remove('hidden');
  } else {
    prev.innerHTML = '<span class="photo-placeholder">📷</span>';
    removeBtn.classList.add('hidden');
  }
}

function bindPhoto() {
  const input = document.getElementById('f-photo');
  document.getElementById('btn-pick-photo').addEventListener('click', () => input.click());
  input.addEventListener('change', () => {
    const file = input.files[0];
    if (!file) return;
    state.photoFile = file;
    state.removePhoto = false;
    updatePhotoPreview();
  });
  document.getElementById('btn-remove-photo').addEventListener('click', () => {
    state.photoFile = null;
    input.value = '';
    state.removePhoto = window.MED_HAS_PHOTO && !state.photoFile;
    updatePhotoPreview();
  });
}

function init() {
  const f = document.getElementById('f-times');

  // начальное состояние из серверной разметки
  state.duration = document.querySelector('#seg-duration .seg-item.sel').dataset.val;
  state.mode = document.querySelector('#seg-mode .seg-item.sel').dataset.val;
  state.meal = document.querySelector('#seg-meal .seg-item.sel').dataset.val;
  state.times = Math.max(1, parseInt(f.value, 10) || 1);

  state.exactTimes = window.MED_TIMES ? window.MED_TIMES.slice() : [];
  syncUI();

  bindSeg();
  bindPhoto();
  updatePhotoPreview();

  f.addEventListener('input', () => {
    readState();
    syncUI();
  });

  document.querySelectorAll('.emoji').forEach((b) =>
    b.addEventListener('click', () => {
      document.querySelectorAll('.emoji').forEach((x) => x.classList.remove('sel'));
      b.classList.add('sel');
    }));

  document.getElementById('med-form').addEventListener('submit', (e) => {
    e.preventDefault();
    submit();
  });
  document.getElementById('btn-cancel').addEventListener('click', () => {
    window.location.href = '/medications';
  });

  const del = document.getElementById('btn-delete');
  if (del) {
    del.addEventListener('click', () => {
      if (!confirm('Удалить лекарство и всю историю приёма?')) return;
      api('/api/medications/' + window.MED_ID, { method: 'DELETE' })
        .then(() => { window.location.href = '/medications'; })
        .catch((err) => toast(err.message));
    });
  }
}

document.addEventListener('DOMContentLoaded', init);
