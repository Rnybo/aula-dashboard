/**
 * js/presence_edit.js — Rediger fremmødetider for børn i Aula
 *
 * Åbnes ved klik på presence-bar i kalenderen.
 * Generisk: virker uanset antal børn og hvem der er logget ind.
 */

// State for den aktuelle redigering
let _peState = {
  childId:   null,   // institutionProfileId for det primære barn
  date:      null,   // "YYYY-MM-DD"
};

// Cache af pickup responsibles (hentes én gang per session)
let _pickupCache = null;

/**
 * Åbnes fra presence-bar onclick.
 * childId    — institutionProfileId (int)
 * date       — "YYYY-MM-DD"
 * entryTime  — "HH:MM:SS" eller "HH:MM" (kan være null)
 * exitTime   — "HH:MM:SS" eller "HH:MM" (kan være null)
 * exitWith   — string (kan være null/"")
 * comment    — string (kan være null/"")
 */
async function openPresenceEdit(childId, date, entryTime, exitTime, exitWith, comment) {
  if (clLocked) return;

  _peState.childId = childId;
  _peState.date    = date;

  // Titel: barnets navn
  const child = CHILDREN.find(c => c.id === childId);
  document.getElementById('presence-edit-title').textContent =
    'Rediger fremmøde — ' + (child ? child.name : 'Barn');

  // Dato label
  const d = new Date(date + 'T00:00:00');
  document.getElementById('presence-edit-date').textContent =
    d.toLocaleDateString('da-DK', { weekday: 'long', day: 'numeric', month: 'long' });

  // Tidsfelter — trim til HH:MM
  document.getElementById('presence-edit-entry').value    = (entryTime || '').substring(0, 5);
  document.getElementById('presence-edit-exit').value     = (exitTime  || '').substring(0, 5);
  document.getElementById('presence-edit-exitwith').value = exitWith   || '';
  document.getElementById('presence-edit-comment').value  = comment    || '';
  document.getElementById('presence-edit-repeat').value   = 'never';

  // Session-tjek — deaktivér Gem hvis Aula ikke er logget ind
  const saveBtn = document.getElementById('presence-edit-save');
  const noSession = sessionWasExpired;
  saveBtn.disabled = noSession;
  if (noSession) {
    _peShowStatus('Log ind i Aula for at gemme ændringer', '#fff3cd', '#856404');
  } else {
    document.getElementById('presence-edit-status').style.display = 'none';
  }

  // Søskende-checkboxes (alle andre børn end det aktive)
  const siblings = CHILDREN.filter(c => c.id !== childId);
  const siblingWrap = document.getElementById('presence-edit-siblings');
  const siblingList = document.getElementById('presence-edit-siblings-list');
  if (siblings.length > 0) {
    siblingList.innerHTML = siblings.map(s =>
      `<label class="presence-sibling-label">
        <input type="checkbox" class="pe-sibling-cb" data-id="${s.id}">
        <span>${s.name}</span>
      </label>`
    ).join('');
    siblingWrap.style.display = 'block';
  } else {
    siblingWrap.style.display = 'none';
  }

  // Hent pickup responsibles (med cache)
  await _loadPickupResponsibles();

  document.getElementById('presence-edit-overlay').classList.add('open');
}

async function _loadPickupResponsibles() {
  const datalist = document.getElementById('presence-exitwith-list');
  datalist.innerHTML = '';

  if (_pickupCache) {
    _fillDatalist(datalist, _pickupCache);
    return;
  }

  try {
    const allIds = CHILDREN.map(c => c.id).join(',');
    const res = await apiFetch(`/api/presence/pickup-responsibles?child_ids=${allIds}`);
    if (!res.ok) return;
    _pickupCache = await res.json();
    _fillDatalist(datalist, _pickupCache);
  } catch (e) {
    // Ikke kritisk — fritekst virker stadig
  }
}

function _fillDatalist(datalist, data) {
  // Saml unikke navne på tværs af alle børn
  const seen = new Set();
  for (const entry of data) {
    for (const p of (entry.relatedPersons || [])) {
      const label = p.relation ? `${p.name} (${p.relation})` : p.name;
      if (!seen.has(label)) {
        seen.add(label);
        const opt = document.createElement('option');
        opt.value = label;
        datalist.appendChild(opt);
      }
    }
    for (const s of (entry.pickupSuggestions || [])) {
      if (!seen.has(s.pickupName)) {
        seen.add(s.pickupName);
        const opt = document.createElement('option');
        opt.value = s.pickupName;
        datalist.appendChild(opt);
      }
    }
  }
}

function closePresenceEdit(e) {
  if (e && e.target !== document.getElementById('presence-edit-overlay')) return;
  document.getElementById('presence-edit-overlay').classList.remove('open');
}

async function savePresenceEdit() {
  const btn = document.getElementById('presence-edit-save');

  const entryTime     = document.getElementById('presence-edit-entry').value;
  const exitTime      = document.getElementById('presence-edit-exit').value;
  const exitWith      = document.getElementById('presence-edit-exitwith').value.trim();
  const comment       = document.getElementById('presence-edit-comment').value.trim();
  const repeatPattern = document.getElementById('presence-edit-repeat').value;

  if (!entryTime && !exitTime) {
    _peShowStatus('Angiv mindst ankomst- eller afgangstid', '#fff3cd', '#856404');
    return;
  }

  // Byg updates-liste: primært barn + valgte søskende
  const selectedSiblings = [...document.querySelectorAll('.pe-sibling-cb:checked')]
    .map(cb => parseInt(cb.dataset.id));
  const allChildIds = [_peState.childId, ...selectedSiblings];

  const updates = allChildIds.map(cid => ({
    childId:       cid,
    date:          _peState.date,
    entryTime:     entryTime,
    exitTime:      exitTime,
    exitWith:      exitWith,
    comment:       comment,
    repeatPattern: repeatPattern,
  }));

  btn.disabled = true;
  btn.textContent = 'Gemmer…';
  _peShowStatus('Sender til Aula…', '#e8f4fd', '#1565c0');

  try {
    const res = await apiFetch('/api/presence/update', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ updates }),
    });
    const results = await res.json();

    const failed = results.filter(r => !r.ok);
    if (failed.length === 0) {
      _peShowStatus('Gemt!', '#d4edda', '#155724');
      await loadPresence();
      setTimeout(() => {
        document.getElementById('presence-edit-overlay').classList.remove('open');
      }, 900);
    } else {
      const errMsg = failed.map(r => `Barn ${r.childId}: ${r.error || 'fejl'}`).join(', ');
      _peShowStatus('Fejl: ' + errMsg, '#f8d7da', '#721c24');
    }
  } catch (e) {
    _peShowStatus('Netværksfejl — prøv igen', '#f8d7da', '#721c24');
  } finally {
    btn.disabled = false;
    btn.textContent = '💾 Gem';
  }
}

function _peShowStatus(msg, bg, color) {
  const el = document.getElementById('presence-edit-status');
  el.textContent = msg;
  el.style.background = bg;
  el.style.color = color;
  el.style.display = 'block';
}
