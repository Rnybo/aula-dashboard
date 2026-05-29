// js/cast.js — Google Cast / Nest afspiller widget

let castState = {};        // device name → state
let castPanelOpen = false;
let castWs = null;

// App-ikoner
const CAST_APP_ICONS = {
  'Spotify':       '🎵',
  'YouTube':       '▶️',
  'YouTube Music': '🎶',
  'DR':            '📻',
  'Netflix':       '🎬',
  'Default Media Receiver': '🔊',
};

function castAppIcon(app) {
  if (!app) return '🔊';
  for (const [k, v] of Object.entries(CAST_APP_ICONS)) {
    if (app.toLowerCase().includes(k.toLowerCase())) return v;
  }
  return '🔊';
}

function castActivePlaying() {
  return Object.values(castState).filter(s => s.state === 'PLAYING' || s.state === 'BUFFERING' || s.state === 'PAUSED');
}

function castRenderHomeWidget() {
  const el = document.getElementById('cast-home-widget');
  if (!el) return;
  const active = castActivePlaying();
  if (active.length === 0) { el.style.display = 'none'; return; }
  el.style.display = 'flex';
  el.innerHTML = active.map(s => {
    const artHtml = s.image
      ? `<img class="cast-home-art" src="${s.image}" onerror="this.style.display='none'">`
      : `<div class="cast-home-art-placeholder">${castAppIcon(s.app)}</div>`;
    const enc = encodeURIComponent(s.device);
    const isPaused = s.state === 'PAUSED';
    return `
      <div class="cast-home-card ${isPaused ? 'paused' : 'playing'}" onclick="castTogglePanel()">
        ${artHtml}
        <div class="cast-home-info">
          <div class="cast-home-device">${castAppIcon(s.app)} ${s.device}</div>
          <div class="cast-home-title">${s.title || '(ukendt titel)'}</div>
          ${s.artist ? `<div class="cast-home-artist">${s.artist}</div>` : ''}
        </div>
        <div class="cast-home-controls" onclick="event.stopPropagation()">
          <button onclick="castControl('${s.device}','previous')" title="Forrige">⏮</button>
          <button onclick="castControl('${s.device}','${isPaused ? 'play' : 'pause'}')">${isPaused ? '▶' : '⏸'}</button>
          <button onclick="castControl('${s.device}','next')" title="Næste">⏭</button>
        </div>
      </div>`;
  }).join('');
}

function castRenderButton() {
  const playing = castActivePlaying().filter(s => s.state === 'PLAYING' || s.state === 'BUFFERING');
  const btn = document.getElementById('cast-btn');
  if (!btn) return;
  if (playing.length === 0) {
    btn.style.display = 'none';
    if (castPanelOpen) castClosePanel();
  } else {
    btn.style.display = 'flex';
    const isPlaying = playing.some(s => s.state === 'PLAYING' || s.state === 'BUFFERING');
    btn.innerHTML = isPlaying ? '🎵' : '⏸';
    btn.title = playing.map(s => `${s.device}: ${s.title || s.app}`).join('\n');
    if (castPanelOpen) castRenderPanel();
  }
}

function castOpenPanel() {
  castPanelOpen = true;
  const panel = document.getElementById('cast-panel');
  if (panel) { panel.style.display = 'block'; castRenderPanel(); }
}

function castClosePanel() {
  castPanelOpen = false;
  const panel = document.getElementById('cast-panel');
  if (panel) panel.style.display = 'none';
}

function castTogglePanel() {
  castPanelOpen ? castClosePanel() : castOpenPanel();
}

function castRenderPanel() {
  const panel = document.getElementById('cast-panel');
  if (!panel) return;
  const playing = castActivePlaying();
  if (playing.length === 0) { castClosePanel(); return; }

  panel.innerHTML = playing.map(s => `
    <div class="cast-device">
      <div class="cast-device-header">
        <span class="cast-app-icon">${castAppIcon(s.app)}</span>
        <span class="cast-device-name">${s.device}</span>
        <span class="cast-status ${s.state === 'PAUSED' ? 'paused' : ''}">${s.state === 'PAUSED' ? 'Sat på pause' : s.state === 'BUFFERING' ? 'Indlæser...' : 'Afspiller'}</span>
      </div>
      ${s.image ? `<img class="cast-album-art" src="${s.image}" onerror="this.style.display='none'">` : ''}
      <div class="cast-track-info">
        <div class="cast-title">${s.title || '(ukendt titel)'}</div>
        ${s.artist ? `<div class="cast-artist">${s.artist}</div>` : ''}
        ${s.album  ? `<div class="cast-album">${s.album}</div>`   : ''}
      </div>
      ${s.volume !== null ? `<div class="cast-volume">🔊 ${Math.round(s.volume * 100)}%</div>` : ''}
      <div class="cast-controls">
        <button onclick="castControl('${s.device}','previous')" title="Forrige">⏮</button>
        <button onclick="castControl('${s.device}','seek_back')" title="10 sek tilbage">⏪</button>
        <button onclick="castControl('${s.device}','${s.state === 'PAUSED' ? 'play' : 'pause'}')" class="cast-playpause">
          ${s.state === 'PAUSED' ? '▶' : '⏸'}
        </button>
        <button onclick="castControl('${s.device}','seek_fwd')" title="10 sek frem">⏩</button>
        <button onclick="castControl('${s.device}','next')" title="Næste">⏭</button>
        <button onclick="castControl('${s.device}','stop')" title="Stop" class="cast-stop">⏹</button>
      </div>
      <button class="cast-transfer-btn" onclick="castShowTransferMenu('${s.device}', this)">📡 Afspil på...</button>
      <div class="cast-vol-row">
        <span>🔇</span>
        <input type="range" min="0" max="100" value="${Math.round((s.volume||0)*100)}"
          oninput="castSetVolume('${s.device}', this.value/100)">
        <span>🔊</span>
      </div>
    </div>
  `).join('');
}

async function castShowTransferMenu(sourceDevice, anchorEl) {
  const key = window.API_KEY || '';
  let devices = [];
  try {
    const r = await fetch('/api/cast/devices', { headers: { 'x-api-key': key } });
    devices = (await r.json()).devices || [];
  } catch(e) {}

  document.querySelectorAll('.cast-transfer-menu').forEach(el => el.remove());
  const others = devices.filter(d => d !== sourceDevice);
  if (others.length === 0) return;

  const menu = document.createElement('div');
  menu.className = 'cast-transfer-menu';
  menu.innerHTML = others.map(d =>
    `<div class="cast-transfer-item" data-device="${d}">${d}</div>`
  ).join('');

  const rect = anchorEl.getBoundingClientRect();
  menu.style.cssText = `position:fixed;bottom:${window.innerHeight - rect.top + 4}px;left:${rect.left}px;
    background:#fff;border:1px solid var(--border);border-radius:8px;
    box-shadow:0 4px 16px rgba(0,0,0,0.15);z-index:2000;min-width:160px;overflow:hidden`;
  document.body.appendChild(menu);

  menu.querySelectorAll('.cast-transfer-item').forEach(item => {
    item.addEventListener('click', async () => {
      menu.remove();
      try {
        await fetch(`/api/cast/${encodeURIComponent(sourceDevice)}/transfer`, {
          method: 'POST',
          headers: { 'x-api-key': key, 'Content-Type': 'application/json' },
          body: JSON.stringify({ target: item.dataset.device })
        });
      } catch(e) { console.warn('Transfer fejl:', e); }
    });
  });

  setTimeout(() => document.addEventListener('click', function close() {
    menu.remove(); document.removeEventListener('click', close);
  }), 50);
}

async function castControl(device, action) {
  const enc = encodeURIComponent(device);
  const key = window.API_KEY || '';
  const headers = { 'x-api-key': key, 'Content-Type': 'application/json' };
  if (action === 'seek_back' || action === 'seek_fwd') {
    const delta = action === 'seek_back' ? -10 : 10;
    await fetch(`/api/cast/${enc}/seek`, { method: 'POST', headers, body: JSON.stringify({ delta }) });
  } else if (action === 'previous') {
    await fetch(`/api/cast/${enc}/previous`, { method: 'POST', headers });
  } else if (action === 'next') {
    await fetch(`/api/cast/${enc}/next`, { method: 'POST', headers });
  } else {
    await fetch(`/api/cast/${enc}/${action}`, { method: 'POST', headers });
  }
}let _volTimer = null;
function castSetVolume(device, level) {
  clearTimeout(_volTimer);
  _volTimer = setTimeout(() => {
    const key = window.API_KEY || '';
    fetch(`/api/cast/${encodeURIComponent(device)}/volume`, {
      method: 'POST',
      headers: { 'x-api-key': key, 'Content-Type': 'application/json' },
      body: JSON.stringify({ level: parseFloat(level) })
    });
  }, 200);
}

function castStartWS() {
  if (castWs && castWs.readyState === WebSocket.OPEN) return;
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  castWs = new WebSocket(`${proto}://${location.host}/ws/cast`);
  castWs.onmessage = e => {
    try {
      const s = JSON.parse(e.data);
      if (s.device) { castState[s.device] = s; castRenderButton(); }
    } catch(err) {}
  };
  castWs.onclose = () => { castWs = null; setTimeout(castStartWS, 10000); };
  castWs.onerror = () => { castWs && castWs.close(); };
}

async function castInit() {
  try {
    const r = await apiFetch('/api/cast/state');
    castState = await r.json() || {};
    castRenderButton();
  } catch(e) {}
  castStartWS();
}
