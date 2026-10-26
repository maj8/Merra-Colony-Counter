/* Merra Colony Counter (https://colony.merra.org) — tap-to-count birds in colony photos.
   Free to use with acknowledgement of Merra; see LICENSE.md.
 *
 * Two ways to use it:
 *  1. Survey mode: an administrator puts images in survey/images/ and a survey/survey.js file
 *     (made with admin.html) next to this app. Users just open the app and count.
 *  2. Own-images mode (no survey.js): users open their own photos.
 *
 * Dots are stored in each image's own pixel coordinates, keyed by file name, and saved in the
 * browser between sessions. Time spent on each image is recorded while the image is open, the
 * app is visible and the user is active; it adds up across sessions.
 */
'use strict';

const DEFAULT_SPECIES = [
  'Guillemot', 'Razorbill', 'Kittiwake', 'Shag', 'Puffin', 'Fulmar', 'Herring Gull',
  'Lesser Black-backed Gull', 'Great Black-backed Gull', 'Cormorant', 'Unidentified',
];
const COLOURS = ['#ff3b30', '#ffcc00', '#34c759', '#00c7ff', '#ff2dd4', '#ff9500',
                 '#af52de', '#ffffff', '#5ac8fa', '#a2845e', '#7cfc00', '#ff6f91'];

const SURVEY = (window.SURVEY && Array.isArray(window.SURVEY.images)) ? window.SURVEY : null;
const STORE_KEY = SURVEY ? `colonyCounter.v3.survey.${SURVEY.id || 'default'}` : 'colonyCounter.v1';
const DOT_R = 7;            // dot radius in screen pixels
const HIT_R = 14;           // click radius for hitting an existing dot
const TAP_SLOP = 8;         // movement (px) before a touch becomes a pan
const IDLE_MS = ((window.SURVEY && window.SURVEY.idleSeconds) || 60) * 1000;  // no input for this long = clock pauses
const MAX_TICK_MS = 5000;   // ignore longer gaps (computer asleep etc.)

// ---------- persistent state ----------
// store.images[name] = { w, h, points: [{x, y, s}], timeMs, sessions, done, firstOpened, lastActive, doneAt }
let store = load();
function load() {
  try {
    const s = JSON.parse(localStorage.getItem(STORE_KEY));
    if (s && s.images) {
      return { species: s.species || defaultSpecies(), images: s.images, current: s.current || 0,
               observer: s.observer || '', surveyId: s.surveyId || (SURVEY && SURVEY.id) || '' };
    }
  } catch (e) { /* ignore */ }
  return { species: defaultSpecies(), images: {}, current: 0, observer: '', surveyId: (SURVEY && SURVEY.id) || '' };
}
function defaultSpecies() {
  return (SURVEY && Array.isArray(SURVEY.species) && SURVEY.species.length) ? SURVEY.species.slice() : DEFAULT_SPECIES.slice();
}
function save() {
  try { localStorage.setItem(STORE_KEY, JSON.stringify(store)); }
  catch (e) { toast('Could not save — storage full? Use Save to download a backup.'); }
}
function rec(name) {
  if (!store.images[name]) {
    store.images[name] = { w: 0, h: 0, points: [], timeMs: 0, sessions: 0, done: false };
    const pre = SURVEY && SURVEY.images.find((i) => i.file === name);
    if (pre && Array.isArray(pre.points)) store.images[name].points = pre.points.map((p) => ({ x: p.x, y: p.y, s: p.s }));
  }
  const r = store.images[name];
  if (r.timeMs == null) r.timeMs = 0;
  if (r.sessions == null) r.sessions = 0;
  return r;
}

// ---------- runtime state ----------
const files = new Map();      // name -> File (own-images mode) or URL string (survey mode)
let names = [];               // ordered list of image names
let curName = null;
let img = null;
let imgURL = null;
let view = { scale: 1, tx: 0, ty: 0 };
const history = [];           // undo stack

const $ = (id) => document.getElementById(id);
const canvas = $('canvas'), ctx = canvas.getContext('2d');
const stage = $('stage');

// ---------- species bar ----------
function colourOf(sp) {
  const i = store.species.indexOf(sp);
  return COLOURS[(i < 0 ? store.species.length : i) % COLOURS.length];
}
function renderSpecies() {
  const bar = $('speciesBar');
  bar.innerHTML = '';
  const counts = countsFor(curName);
  store.species.forEach((sp, i) => {
    const b = document.createElement('button');
    b.className = 'chip';
    b.setAttribute('role', 'radio');
    b.setAttribute('aria-checked', String(i === store.current));
    b.innerHTML = '<span class="sw"></span><span class="nm"></span><span class="n"></span>';
    b.querySelector('.sw').style.background = COLOURS[i % COLOURS.length];
    b.querySelector('.nm').textContent = sp;
    b.querySelector('.n').textContent = counts[sp] || 0;
    b.onclick = () => { store.current = i; save(); renderSpecies(); };
    bar.appendChild(b);
  });
}
function countsFor(name) {
  const c = {};
  const r = name && store.images[name];
  if (r) for (const p of r.points) c[p.s] = (c[p.s] || 0) + 1;
  return c;
}

// ---------- image list ----------
function addFiles(list) {
  let added = 0;
  for (const f of list) {
    if (!/\.(jpe?g|png)$/i.test(f.name) && !/^image\/(jpeg|png)$/.test(f.type)) continue;
    const relPath = f.webkitRelativePath || '';
    if (/(^|\/)(colony-trainer|results|results_val|annotated|_review|dataset|runs)\//.test(relPath) ||
        f.name.startsWith('annotated_')) continue;
    files.set(f.name, f);
    added++;
  }
  if (!added) { toast('No JPEG or PNG files found'); return; }
  names = [...files.keys()].sort((a, b) => a.localeCompare(b, undefined, { numeric: true }));
  renderImageSelect();
  if (!curName || !files.has(curName)) openImage(names[0]);
  toast(`${added} image${added > 1 ? 's' : ''} loaded`);
}
function loadSurvey() {
  for (const it of SURVEY.images) files.set(it.file, 'survey/images/' + encodeURIComponent(it.file));
  names = SURVEY.images.map((i) => i.file);
  $('surveyRow').hidden = false;
  $('surveyTitle').textContent = SURVEY.title || 'Survey';
  if (!SURVEY.allowOwnImages) { $('openBtn').hidden = true; $('folderBtn').hidden = true; }
  if (SURVEY.lockSpecies !== false) $('speciesMenuBtn').hidden = true;
  $('emptyLead').innerHTML = '<strong>Loading survey images…</strong>';
  if (SURVEY.instructions) {
    for (const id of ['surveyInstr', 'menuInstr']) { $(id).textContent = SURVEY.instructions; $(id).hidden = false; }
  }
  renderImageSelect();
  // resume where the user left off: first image not yet done
  const next = names.find((n) => !(store.images[n] && store.images[n].done)) || names[0];
  if (next) openImage(next);
}
function optionLabel(n) {
  const r = store.images[n];
  const k = r ? r.points.length : 0;
  return `${r && r.done ? '✓ ' : ''}${n}${k ? `  (${k})` : ''}`;
}
function renderImageSelect() {
  const sel = $('imageSelect');
  sel.innerHTML = '';
  for (const n of names) {
    const o = document.createElement('option');
    o.value = n;
    o.textContent = optionLabel(n);
    sel.appendChild(o);
  }
  sel.value = curName || '';
  updateNav();
  renderProgress();
}
function refreshOption() {
  const o = [...$('imageSelect').options].find((x) => x.value === curName);
  if (o) o.textContent = optionLabel(curName);
  renderProgress();
}
function renderProgress() {
  if (!SURVEY) return;
  const done = names.filter((n) => store.images[n] && store.images[n].done).length;
  const ms = names.reduce((t, n) => t + ((store.images[n] && store.images[n].timeMs) || 0), 0);
  $('progress').textContent = `${done}/${names.length} done · ${fmtTime(ms)} total`;
}
function updateNav() {
  const i = names.indexOf(curName);
  $('prevBtn').disabled = i <= 0;
  $('nextBtn').disabled = i < 0 || i >= names.length - 1;
}
function openImage(name) {
  const src = files.get(name);
  if (!src) return;
  closeSession();
  curName = name;
  if (imgURL) { URL.revokeObjectURL(imgURL); imgURL = null; }
  let url = src;
  if (typeof src !== 'string') { imgURL = URL.createObjectURL(src); url = imgURL; }
  const im = new Image();
  img = null; draw();
  $('empty').hidden = false;
  $('emptyLead').innerHTML = '';
  $('emptyLead').append(Object.assign(document.createElement('strong'), { textContent: `Loading ${name}\u2026` }));
  $('imageSelect').value = name;
  updateNav();
  im.onload = () => {
    if (curName !== name) return;
    img = im;
    const r = rec(name);
    r.w = im.naturalWidth; r.h = im.naturalHeight;
    r.sessions += 1;
    if (!r.firstOpened) r.firstOpened = new Date().toISOString();
    save();
    $('empty').hidden = true;
    fit();
    renderSpecies();
    renderImageSelect();
    renderDone();
    status();
    markActive();
  };
  im.onerror = () => {
    if (curName !== name) return;
    const lead = $('emptyLead');
    lead.innerHTML = '';
    const b = document.createElement('strong');
    b.textContent = `Could not open ${name}`;
    const p = document.createElement('span');
    p.className = 'err';
    p.textContent = typeof src === 'string'
      ? ` \u2014 the app looked for it at ${new URL(url, location.href).href.replace(/^file:\/\/\/?/, '')}. ` +
        'The survey photos must be in the survey/images folder next to index.html, with exactly the same file names.'
      : ' \u2014 the file could not be read as an image.';
    lead.append(b, document.createElement('br'), p);
    toast(`Could not open ${name}`);
  };
  im.src = url;
}

// ---------- timing ----------
let lastActivity = 0;
let lastTick = Date.now();
let unsavedSince = 0;
function markActive() { lastActivity = Date.now(); }
function timingActive() {
  if (!curName || !img) return false;
  const r = store.images[curName];
  if (!r || r.done) return false;
  if (document.visibilityState !== 'visible' || !document.hasFocus()) return false;
  if (document.querySelector('dialog[open]')) return false;
  return Date.now() - lastActivity < IDLE_MS;
}
function tick() {
  const now = Date.now();
  const dt = now - lastTick;
  lastTick = now;
  if (timingActive() && dt > 0 && dt <= MAX_TICK_MS) {
    const r = store.images[curName];
    r.timeMs += dt;
    r.lastActive = new Date(now).toISOString();
    if (!unsavedSince) unsavedSince = now;
    if (now - unsavedSince > 10000) { save(); unsavedSince = 0; }
  }
  renderTimer();
}
function closeSession() { if (unsavedSince) { save(); unsavedSince = 0; } }
function fmtTime(ms) {
  const s = Math.floor(ms / 1000);
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60;
  return h ? `${h}:${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}` : `${m}:${String(sec).padStart(2, '0')}`;
}
let progressTick = 0;
function renderTimer() {
  const el = $('timer');
  if (!curName || !store.images[curName]) { el.textContent = ''; return; }
  const r = store.images[curName];
  const running = timingActive();
  el.textContent = `⏱ ${fmtTime(r.timeMs)}${r.done ? ' ✓' : running ? '' : ' (paused)'}`;
  el.classList.toggle('paused', !running);
  if (++progressTick % 5 === 0) renderProgress();
}
['pointerdown', 'pointermove', 'wheel', 'keydown', 'touchstart'].forEach((ev) =>
  window.addEventListener(ev, markActive, { passive: true, capture: true }));
document.addEventListener('visibilitychange', () => { lastTick = Date.now(); closeSession(); });
window.addEventListener('pagehide', closeSession);
window.addEventListener('blur', () => { tick(); closeSession(); });
window.addEventListener('focus', () => { lastTick = Date.now(); markActive(); });
setInterval(tick, 1000);

// ---------- done ----------
function renderDone() {
  const r = curName && store.images[curName];
  const d = !!(r && r.done);
  $('doneBtn').setAttribute('aria-pressed', String(d));
  $('doneBtn').textContent = d ? 'Done ✓' : 'Done';
  $('doneBanner').hidden = !d;
}
$('doneBtn').onclick = () => {
  if (!curName || !img) return;
  tick();
  const r = rec(curName);
  r.done = !r.done;
  r.doneAt = r.done ? new Date().toISOString() : undefined;
  save(); renderDone(); refreshOption(); renderTimer();
  if (r.done) {
    toast(`Done in ${fmtTime(r.timeMs)}`);
    const next = names.find((n, i) => i > names.indexOf(curName) && !(store.images[n] && store.images[n].done)) ||
                 names.find((n) => !(store.images[n] && store.images[n].done));
    if (next) setTimeout(() => openImage(next), 600);
    else if (SURVEY) setTimeout(() => toast('All images done — press Save to send your results'), 800);
  } else {
    markActive();
    toast('Reopened — the clock continues');
  }
};

// ---------- view / drawing ----------
function resize() {
  const dpr = window.devicePixelRatio || 1;
  const r = stage.getBoundingClientRect();
  canvas.width = Math.round(r.width * dpr);
  canvas.height = Math.round(r.height * dpr);
  draw();
}
function fit() {
  if (!img) return;
  const r = stage.getBoundingClientRect();
  const s = Math.min(r.width / img.naturalWidth, r.height / img.naturalHeight);
  view = { scale: s, tx: (r.width - img.naturalWidth * s) / 2, ty: (r.height - img.naturalHeight * s) / 2 };
  draw();
}
function draw() {
  const dpr = window.devicePixelRatio || 1;
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  if (!img) return;
  ctx.setTransform(dpr * view.scale, 0, 0, dpr * view.scale, dpr * view.tx, dpr * view.ty);
  ctx.imageSmoothingEnabled = view.scale < 2;
  ctx.drawImage(img, 0, 0);
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  const pts = (store.images[curName] && store.images[curName].points) || [];
  for (const p of pts) {
    const sx = p.x * view.scale + view.tx, sy = p.y * view.scale + view.ty;
    ctx.beginPath();
    ctx.arc(sx, sy, DOT_R, 0, Math.PI * 2);
    ctx.fillStyle = colourOf(p.s);
    ctx.fill();
    ctx.lineWidth = 2;
    ctx.strokeStyle = '#000';
    ctx.stroke();
  }
}
function toImage(sx, sy) { return { x: (sx - view.tx) / view.scale, y: (sy - view.ty) / view.scale }; }
function zoomAt(sx, sy, factor) {
  const s = Math.min(Math.max(view.scale * factor, 0.02), 40);
  const f = s / view.scale;
  view.tx = sx - (sx - view.tx) * f;
  view.ty = sy - (sy - view.ty) * f;
  view.scale = s;
  draw();
}

// ---------- editing ----------
function nearestDot(sx, sy) {
  const r = store.images[curName];
  let best = -1, bestD = HIT_R * HIT_R;
  r.points.forEach((p, i) => {
    const dx = p.x * view.scale + view.tx - sx, dy = p.y * view.scale + view.ty - sy;
    const d = dx * dx + dy * dy;
    if (d <= bestD) { bestD = d; best = i; }
  });
  return best;
}
function editable() {
  if (!img) return false;
  if (store.images[curName] && store.images[curName].done) {
    toast('This image is marked done — press Done to reopen it');
    return false;
  }
  return true;
}
function afterEdit() {
  if (history.length > 500) history.shift();
  save(); draw(); renderSpecies(); refreshOption(); status();
}
// Click: empty space -> add a dot; dot of selected species -> remove; dot of another species -> relabel.
function handleTap(sx, sy) {
  if (!editable()) return;
  const r = store.images[curName];
  const sp = store.species[store.current];
  if (!sp) { toast('No species selected'); return; }
  const i = nearestDot(sx, sy);
  if (i >= 0) {
    const p = r.points[i];
    if (p.s === sp) {
      r.points.splice(i, 1);
      history.push({ name: curName, op: 'remove', pt: p, idx: i });
    } else {
      history.push({ name: curName, op: 'relabel', pt: p, old: p.s });
      toast(`${p.s} → ${sp}`);
      p.s = sp;
    }
  } else {
    const { x, y } = toImage(sx, sy);
    if (x < 0 || y < 0 || x > img.naturalWidth || y > img.naturalHeight) return;
    const pt = { x: Math.round(x * 10) / 10, y: Math.round(y * 10) / 10, s: sp };
    r.points.push(pt);
    history.push({ name: curName, op: 'add', pt });
  }
  afterEdit();
}
// Right click: remove whatever dot is there.
function handleRemove(sx, sy) {
  if (!editable()) return;
  const r = store.images[curName];
  const i = nearestDot(sx, sy);
  if (i < 0) { toast('No dot here to remove'); return; }
  const [pt] = r.points.splice(i, 1);
  history.push({ name: curName, op: 'remove', pt, idx: i });
  afterEdit();
}
function undo() {
  const h = history.pop();
  if (!h) { toast('Nothing to undo'); return; }
  const r = store.images[h.name];
  if (!r) return;
  if (h.op === 'relabel') h.pt.s = h.old;
  else if (h.op === 'add') { const i = r.points.lastIndexOf(h.pt); if (i >= 0) r.points.splice(i, 1); }
  else r.points.splice(Math.min(h.idx, r.points.length), 0, h.pt);
  save();
  if (h.name !== curName && files.has(h.name)) { openImage(h.name); return; }
  draw(); renderSpecies(); refreshOption(); status();
}
function status() {
  const total = (store.images[curName] && store.images[curName].points.length) || 0;
  const counted = Object.values(store.images).filter((r) => r.points.length).length;
  $('status').textContent = curName ? `${total} on this image · ${counted} image${counted === 1 ? '' : 's'} with dots` : '';
}

// ---------- pointer input: tap, drag-pan, pinch-zoom ----------
const pointers = new Map();
let gesture = null;
canvas.addEventListener('pointerdown', (e) => {
  canvas.setPointerCapture(e.pointerId);
  pointers.set(e.pointerId, { x: e.offsetX, y: e.offsetY });
  if (pointers.size === 1) {
    gesture = { type: 'maybeTap', sx: e.offsetX, sy: e.offsetY, lx: e.offsetX, ly: e.offsetY, button: e.button };
  } else if (pointers.size === 2) {
    const [a, b] = [...pointers.values()];
    gesture = { type: 'pinch', dist: Math.hypot(a.x - b.x, a.y - b.y), mx: (a.x + b.x) / 2, my: (a.y + b.y) / 2 };
  }
});
canvas.addEventListener('pointermove', (e) => {
  if (!pointers.has(e.pointerId)) return;
  pointers.set(e.pointerId, { x: e.offsetX, y: e.offsetY });
  if (!gesture || !img) return;
  if (gesture.type === 'pinch' && pointers.size >= 2) {
    const [a, b] = [...pointers.values()];
    const dist = Math.hypot(a.x - b.x, a.y - b.y);
    const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2;
    view.tx += mx - gesture.mx; view.ty += my - gesture.my;
    if (gesture.dist > 0) zoomAt(mx, my, dist / gesture.dist); else draw();
    gesture.dist = dist; gesture.mx = mx; gesture.my = my;
  } else if (gesture.type === 'maybeTap' || gesture.type === 'pan') {
    if (gesture.type === 'maybeTap' && Math.hypot(e.offsetX - gesture.sx, e.offsetY - gesture.sy) > TAP_SLOP) gesture.type = 'pan';
    if (gesture.type === 'pan') { view.tx += e.offsetX - gesture.lx; view.ty += e.offsetY - gesture.ly; draw(); }
    gesture.lx = e.offsetX; gesture.ly = e.offsetY;
  }
});
function endPointer(e) {
  if (!pointers.has(e.pointerId)) return;
  pointers.delete(e.pointerId);
  if (gesture && gesture.type === 'maybeTap' && e.type === 'pointerup' && gesture.button === 0) handleTap(gesture.sx, gesture.sy);
  if (pointers.size === 0) gesture = null;
  else if (gesture && gesture.type === 'pinch') { const [p] = [...pointers.values()]; gesture = { type: 'pan', lx: p.x, ly: p.y }; }
}
canvas.addEventListener('pointerup', endPointer);
canvas.addEventListener('pointercancel', endPointer);
canvas.addEventListener('wheel', (e) => {
  e.preventDefault();
  if (img) zoomAt(e.offsetX, e.offsetY, Math.exp(-e.deltaY * (e.deltaMode ? 0.05 : 0.0015)));
}, { passive: false });
canvas.addEventListener('contextmenu', (e) => { e.preventDefault(); handleRemove(e.offsetX, e.offsetY); });

// ---------- exports ----------
function csvCell(v) {
  const s = v == null ? '' : String(v);
  return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}
function toCSV(rows) { return rows.map((r) => r.map(csvCell).join(',')).join('\r\n') + '\r\n'; }
const byName = (a, b) => a.localeCompare(b, undefined, { numeric: true });
function imageOrder() {
  const known = names.filter((n) => store.images[n]);
  return [...known, ...Object.keys(store.images).filter((n) => !known.includes(n)).sort(byName)];
}
const minutes = (ms) => Math.round((ms || 0) / 600) / 100;   // 2 decimals
function masterCSV() {
  const rows = [['observer', 'image', 'species', 'count', 'minutes_spent', 'status']];
  for (const n of imageOrder()) {
    const r = store.images[n];
    const c = countsFor(n);
    const st = r.done ? 'done' : (r.timeMs || r.points.length ? 'in progress' : 'not started');
    const order = [...store.species, ...Object.keys(c).filter((s) => !store.species.includes(s))];
    let any = false;
    for (const sp of order) if (c[sp]) { rows.push([store.observer, n, sp, c[sp], minutes(r.timeMs), st]); any = true; }
    if (!any && r.done) rows.push([store.observer, n, '(no birds)', 0, minutes(r.timeMs), st]);
  }
  return rows;
}
function timesCSV() {
  const rows = [['observer', 'image', 'minutes_spent', 'seconds_spent', 'status', 'birds', 'sessions', 'first_opened', 'last_active', 'done_at']];
  const list = SURVEY ? names : imageOrder();
  for (const n of list) {
    const r = store.images[n] || { points: [], timeMs: 0, sessions: 0 };
    rows.push([store.observer, n, minutes(r.timeMs), Math.round((r.timeMs || 0) / 1000),
      r.done ? 'done' : (r.timeMs || r.points.length ? 'in progress' : 'not started'),
      r.points.length, r.sessions || 0, r.firstOpened || '', r.lastActive || '', r.doneAt || '']);
  }
  return rows;
}
function pointsCSV() {
  const rows = [['observer', 'image', 'species', 'x_px', 'y_px', 'image_width', 'image_height']];
  for (const n of imageOrder()) {
    const r = store.images[n];
    for (const p of r.points) rows.push([store.observer, n, p.s, p.x, p.y, r.w, r.h]);
  }
  return rows;
}
async function deliver(filename, text, mime) {
  const blob = new Blob([text], { type: mime });
  const file = new File([blob], filename, { type: mime });
  const coarse = matchMedia('(pointer: coarse)').matches;
  if (coarse && navigator.canShare && navigator.canShare({ files: [file] })) {
    try { await navigator.share({ files: [file], title: filename }); return; }
    catch (e) { if (e.name === 'AbortError') return; }
  }
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 2000);
}
const stamp = () => new Date().toISOString().slice(0, 16).replace(/[:T]/g, '-');
const who = () => (store.observer || 'anon').replace(/[^\w-]+/g, '_').slice(0, 30);
function backupJSON() {
  return JSON.stringify({ ...store, app: 'colony-counter', version: 3, generator: 'Merra Colony Counter (merra.org)', surveyId: (SURVEY && SURVEY.id) || '',
                          surveyTitle: (SURVEY && SURVEY.title) || '', savedAt: new Date().toISOString() });
}
$('saveBtn').onclick = () => {
  tick(); save();
  deliver(`colony_backup_${who()}_${stamp()}.json`, backupJSON(), 'application/json');
  toast('Saved to your Downloads folder');
};
$('exportBtn').onclick = () => {
  tick();
  const rows = masterCSV();
  if (rows.length === 1) { toast('Nothing counted yet'); return; }
  deliver(`colony_counts_${who()}_${stamp()}.csv`, toCSV(rows), 'text/csv');
};

// ---------- observer ----------
function askObserver(required) {
  $('observerInput').value = store.observer || '';
  $('observerDlg').dataset.required = required ? '1' : '';
  $('observerDlg').showModal();
  setTimeout(() => $('observerInput').focus(), 50);
}
$('observerDlg').addEventListener('cancel', (e) => { if ($('observerDlg').dataset.required) e.preventDefault(); });
$('observerDlg').addEventListener('close', () => {
  const v = $('observerInput').value.trim();
  if (!v && $('observerDlg').dataset.required) { setTimeout(() => askObserver(true), 0); return; }
  if (v) { store.observer = v; save(); }
  lastTick = Date.now(); markActive();
});

// ---------- menu ----------
$('menuBtn').onclick = () => {
  $('observerLine').textContent = `Observer: ${store.observer || '(not set)'}` + (SURVEY ? ` · Survey: ${SURVEY.title || SURVEY.id}` : '');
  $('menu').showModal();
};
$('menu').addEventListener('close', () => {
  const v = $('menu').returnValue;
  $('menu').returnValue = '';
  lastTick = Date.now();
  if (v === 'observer') askObserver(false);
  else if (v === 'times') { tick(); deliver(`colony_times_${who()}_${stamp()}.csv`, toCSV(timesCSV()), 'text/csv'); }
  else if (v === 'points') {
    const rows = pointsCSV();
    if (rows.length === 1) return toast('No points yet');
    deliver(`colony_points_${who()}_${stamp()}.csv`, toCSV(rows), 'text/csv');
  } else if (v === 'backup') {
    tick(); deliver(`colony_backup_${who()}_${stamp()}.json`, backupJSON(), 'application/json');
  } else if (v === 'species') {
    $('speciesText').value = store.species.join('\n');
    $('speciesDlg').showModal();
  } else if (v === 'clearImage') {
    if (curName && confirm(`Remove all dots on ${curName}? (The time spent is kept.)`)) {
      store.images[curName].points = [];
      history.length = 0;
      save(); draw(); renderSpecies(); refreshOption(); status();
    }
  } else if (v === 'clearAll') {
    if (confirm('Delete ALL dots AND recorded times for ALL images? Save a backup first if unsure.')) {
      store.images = {};
      if (curName && img) rec(curName).w = img.naturalWidth;
      history.length = 0;
      save(); draw(); renderSpecies(); renderImageSelect(); renderDone(); status();
    }
  }
});
$('restoreInput').onchange = async (e) => {
  const f = e.target.files[0];
  e.target.value = '';
  $('menu').close();
  if (!f) return;
  try {
    const data = JSON.parse(await f.text());
    if (!data.images) throw new Error('bad file');
    if (SURVEY && data.surveyId && data.surveyId !== SURVEY.id &&
        !confirm(`This backup is from a different survey (${data.surveyId}). Restore anyway?`)) return;
    if (!confirm('Replace current dots and times with this backup?')) return;
    store = { species: data.species || defaultSpecies(), images: data.images, current: 0,
              observer: data.observer || store.observer, surveyId: (SURVEY && SURVEY.id) || '' };
    history.length = 0;
    save(); renderSpecies(); renderImageSelect(); renderDone(); draw(); status();
    toast('Backup restored');
  } catch (err) { toast('That is not a Colony Counter backup'); }
};
$('speciesDlg').addEventListener('close', () => {
  const v = $('speciesDlg').returnValue;
  $('speciesDlg').returnValue = '';
  if (v === 'save' || v === 'reset') {
    const list = v === 'reset' ? defaultSpecies()
      : [...new Set($('speciesText').value.split('\n').map((s) => s.trim()).filter(Boolean))];
    if (!list.length) return toast('List cannot be empty');
    store.species = list;
    store.current = Math.min(store.current, list.length - 1);
    save(); renderSpecies(); draw();
  }
});

// ---------- wiring ----------
$('fileInput').onchange = (e) => { addFiles(e.target.files); e.target.value = ''; };
$('folderInput').onchange = (e) => { addFiles(e.target.files); e.target.value = ''; };
$('imageSelect').onchange = (e) => openImage(e.target.value);
$('prevBtn').onclick = () => { const i = names.indexOf(curName); if (i > 0) openImage(names[i - 1]); };
$('nextBtn').onclick = () => { const i = names.indexOf(curName); if (i < names.length - 1) openImage(names[i + 1]); };
$('undoBtn').onclick = undo;
$('fitBtn').onclick = fit;
document.addEventListener('keydown', (e) => {
  if (e.target.tagName === 'TEXTAREA' || e.target.tagName === 'INPUT' || document.querySelector('dialog[open]')) return;
  if ((e.ctrlKey || e.metaKey) && e.key === 'z') { e.preventDefault(); undo(); }
  else if (e.key === 'ArrowRight') $('nextBtn').click();
  else if (e.key === 'ArrowLeft') $('prevBtn').click();
  else if (/^[1-9]$/.test(e.key) && store.species[+e.key - 1]) { store.current = +e.key - 1; save(); renderSpecies(); }
});
if (!('webkitdirectory' in document.createElement('input')) || /iPad|iPhone|iPod/.test(navigator.userAgent)) {
  $('folderBtn').hidden = true;
}
new ResizeObserver(resize).observe(stage);

let toastTimer;
function toast(msg) {
  let t = document.querySelector('.toast');
  if (!t) { t = document.createElement('div'); t.className = 'toast'; document.body.appendChild(t); }
  t.textContent = msg; t.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { t.hidden = true; }, 2200);
}

// ---------- start ----------
if (window.CLAUDE_START && !SURVEY && !Object.keys(store.images).some((k) => store.images[k].points.length)) {
  store.species = CLAUDE_START.species; store.images = CLAUDE_START.images; save();
}
if (SURVEY && store.species.length === 0) store.species = defaultSpecies();
renderSpecies();
resize();
renderDone();
if (SURVEY) loadSurvey();
if (!store.observer && (SURVEY ? SURVEY.askObserver !== false : true)) askObserver(!!SURVEY);

if ('serviceWorker' in navigator && location.protocol !== 'file:') {
  navigator.serviceWorker.register('sw.js').catch(() => {});
}
