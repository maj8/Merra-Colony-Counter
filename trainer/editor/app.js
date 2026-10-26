/* Colony Counter — tap-to-count birds in colony photos.
 *
 * Edit DEFAULT_SPECIES to change the predefined list (it can also be edited
 * in the app via the ⋮ menu). Dots are stored in the image's own pixel
 * coordinates, keyed by file name, and saved in the browser between sessions.
 */
'use strict';

// Isle of May cliff-nesting seabirds. The first four were identified in the sample photo.
const DEFAULT_SPECIES = [
  'Guillemot',
  'Razorbill',
  'Kittiwake',
  'Shag',
  'Puffin',
  'Fulmar',
  'Herring Gull',
  'Lesser Black-backed Gull',
  'Great Black-backed Gull',
  'Cormorant',
  'Unidentified',
];

const COLOURS = ['#ff3b30', '#ffcc00', '#34c759', '#00c7ff', '#ff2dd4', '#ff9500',
                 '#af52de', '#ffffff', '#5ac8fa', '#a2845e', '#7cfc00', '#ff6f91'];

const STORE_KEY = 'colonyCounter.v1';
const DOT_R = 7;          // dot radius in screen pixels
const HIT_R = 14;         // tap-to-remove radius in screen pixels
const TAP_SLOP = 8;       // movement (px) before a touch becomes a pan

// ---------- persistent state ----------
let store = load();
function load() {
  try {
    const s = JSON.parse(localStorage.getItem(STORE_KEY));
    if (s && s.images) return { species: s.species || DEFAULT_SPECIES.slice(), images: s.images, current: s.current || 0 };
  } catch (e) { /* ignore */ }
  return { species: DEFAULT_SPECIES.slice(), images: {}, current: 0 };
}
function save() {
  try { localStorage.setItem(STORE_KEY, JSON.stringify(store)); }
  catch (e) { toast('Could not save — storage full? Export a backup.'); }
}
// store.images[name] = { w, h, points: [{x, y, s}] }  (s = species name)

// ---------- runtime state ----------
const files = new Map();      // name -> File
let names = [];               // sorted list of loaded file names
let curName = null;
let img = null;               // HTMLImageElement of current image
let imgURL = null;
let view = { scale: 1, tx: 0, ty: 0 };
const history = [];           // undo stack: {name, op:'add'|'remove', pt, idx}

// ---------- DOM ----------
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
    b.innerHTML = `<span class="sw"></span><span class="nm"></span><span class="n"></span>`;
    b.querySelector('.sw').style.background = COLOURS[i % COLOURS.length];
    b.querySelector('.nm').textContent = sp;
    b.querySelector('.n').textContent = counts[sp] || 0;
    b.onclick = () => { store.current = i; save(); renderSpecies(); };
    bar.appendChild(b);
  });
  const active = bar.children[store.current];
  if (active) active.scrollIntoView({ block: 'nearest', inline: 'nearest' });
}
function countsFor(name) {
  const c = {};
  const rec = name && store.images[name];
  if (rec) for (const p of rec.points) c[p.s] = (c[p.s] || 0) + 1;
  return c;
}

// ---------- image list ----------
function addFiles(list) {
  let added = 0;
  for (const f of list) {
    if (!/\.(jpe?g|png)$/i.test(f.name) && !/^image\/(jpeg|png)$/.test(f.type)) continue;
    const rel = f.webkitRelativePath || '';
    if (/(^|\/)(colony-trainer|results|results_val|annotated|_review|dataset|runs)\//.test(rel) || f.name.startsWith('annotated_')) continue;
    files.set(f.name, f);
    added++;
  }
  if (!added) { toast('No JPEG or PNG files found'); return; }
  names = [...files.keys()].sort((a, b) => a.localeCompare(b, undefined, { numeric: true }));
  renderImageSelect();
  if (!curName || !files.has(curName)) openImage(names[0]);
  toast(`${added} image${added > 1 ? 's' : ''} loaded`);
}
function renderImageSelect() {
  const sel = $('imageSelect');
  sel.innerHTML = '';
  for (const n of names) {
    const o = document.createElement('option');
    const k = store.images[n]?.points.length || 0;
    o.value = n;
    o.textContent = k ? `${n}  (${k})` : n;
    sel.appendChild(o);
  }
  sel.value = curName || '';
  updateNav();
}
function updateNav() {
  const i = names.indexOf(curName);
  $('prevBtn').disabled = i <= 0;
  $('nextBtn').disabled = i < 0 || i >= names.length - 1;
}
function openImage(name) {
  const f = files.get(name);
  if (!f) return;
  curName = name;
  if (imgURL) URL.revokeObjectURL(imgURL);
  imgURL = URL.createObjectURL(f);
  const im = new Image();
  im.onload = () => {
    img = im;
    const rec = store.images[name] || (store.images[name] = { w: 0, h: 0, points: [] });
    rec.w = im.naturalWidth; rec.h = im.naturalHeight;
    $('empty').hidden = true;
    fit();
    renderSpecies();
    renderImageSelect();
    status();
  };
  im.onerror = () => toast(`Could not open ${name}`);
  im.src = imgURL;
}

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
  // dots in screen space so they stay a constant size
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  const pts = store.images[curName]?.points || [];
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
function toImage(sx, sy) {
  return { x: (sx - view.tx) / view.scale, y: (sy - view.ty) / view.scale };
}
function zoomAt(sx, sy, factor) {
  const s = Math.min(Math.max(view.scale * factor, 0.02), 40);
  const f = s / view.scale;
  view.tx = sx - (sx - view.tx) * f;
  view.ty = sy - (sy - view.ty) * f;
  view.scale = s;
  draw();
}

// ---------- tapping ----------
function handleTap(sx, sy) {
  if (!img) return;
  const rec = store.images[curName];
  const sp = store.species[store.current];
  if (!sp) { toast('Add a species first (⋮ menu)'); return; }
  // remove a nearby dot of the selected species, if any
  let best = -1, bestD = HIT_R * HIT_R;
  rec.points.forEach((p, i) => {
    if (p.s !== sp) return;
    const dx = p.x * view.scale + view.tx - sx, dy = p.y * view.scale + view.ty - sy;
    const d = dx * dx + dy * dy;
    if (d <= bestD) { bestD = d; best = i; }
  });
  if (best >= 0) {
    const [pt] = rec.points.splice(best, 1);
    history.push({ name: curName, op: 'remove', pt, idx: best });
  } else {
    const { x, y } = toImage(sx, sy);
    if (x < 0 || y < 0 || x > img.naturalWidth || y > img.naturalHeight) return;
    const pt = { x: Math.round(x * 10) / 10, y: Math.round(y * 10) / 10, s: sp };
    rec.points.push(pt);
    history.push({ name: curName, op: 'add', pt });
  }
  if (history.length > 500) history.shift();
  save(); draw(); renderSpecies(); refreshOption(); status();
}
function undo() {
  const h = history.pop();
  if (!h) { toast('Nothing to undo'); return; }
  const rec = store.images[h.name];
  if (!rec) return;
  if (h.op === 'add') {
    const i = rec.points.lastIndexOf(h.pt);
    if (i >= 0) rec.points.splice(i, 1);
  } else {
    rec.points.splice(Math.min(h.idx, rec.points.length), 0, h.pt);
  }
  save();
  if (h.name !== curName && files.has(h.name)) { openImage(h.name); return; }
  draw(); renderSpecies(); refreshOption(); status();
}
function refreshOption() {
  const o = [...$('imageSelect').options].find((o) => o.value === curName);
  if (o) { const k = store.images[curName].points.length; o.textContent = k ? `${curName}  (${k})` : curName; }
}
function status() {
  const total = store.images[curName]?.points.length || 0;
  const done = Object.values(store.images).filter((r) => r.points.length).length;
  $('status').textContent = curName ? `${total} on this image · ${done} image${done === 1 ? '' : 's'} counted` : '';
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
    if (gesture.type === 'maybeTap' &&
        Math.hypot(e.offsetX - gesture.sx, e.offsetY - gesture.sy) > TAP_SLOP) gesture.type = 'pan';
    if (gesture.type === 'pan') {
      view.tx += e.offsetX - gesture.lx; view.ty += e.offsetY - gesture.ly;
      draw();
    }
    gesture.lx = e.offsetX; gesture.ly = e.offsetY;
  }
});
function endPointer(e) {
  if (!pointers.has(e.pointerId)) return;
  pointers.delete(e.pointerId);
  if (gesture && gesture.type === 'maybeTap' && e.type === 'pointerup' && gesture.button === 0) {
    handleTap(gesture.sx, gesture.sy);
  }
  if (pointers.size === 0) gesture = null;
  else if (gesture && gesture.type === 'pinch') {
    // one finger lifted: continue as a pan, never as a tap
    const [p] = [...pointers.values()];
    gesture = { type: 'pan', lx: p.x, ly: p.y };
  }
}
canvas.addEventListener('pointerup', endPointer);
canvas.addEventListener('pointercancel', endPointer);
canvas.addEventListener('wheel', (e) => {
  e.preventDefault();
  if (img) zoomAt(e.offsetX, e.offsetY, Math.exp(-e.deltaY * (e.deltaMode ? 0.05 : 0.0015)));
}, { passive: false });
canvas.addEventListener('contextmenu', (e) => e.preventDefault());

// ---------- CSV / export ----------
function csvCell(v) {
  const s = String(v);
  return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}
function toCSV(rows) { return rows.map((r) => r.map(csvCell).join(',')).join('\r\n') + '\r\n'; }

function masterCSV() {
  const rows = [['image', 'species', 'count']];
  const imageNames = Object.keys(store.images).sort((a, b) => a.localeCompare(b, undefined, { numeric: true }));
  for (const n of imageNames) {
    const c = countsFor(n);
    // predefined species first (in list order), then any older species no longer in the list
    const order = [...store.species, ...Object.keys(c).filter((s) => !store.species.includes(s))];
    for (const sp of order) if (c[sp]) rows.push([n, sp, c[sp]]);
  }
  return rows;
}
function pointsCSV() {
  const rows = [['image', 'species', 'x_px', 'y_px', 'image_width', 'image_height']];
  for (const [n, rec] of Object.entries(store.images))
    for (const p of rec.points) rows.push([n, p.s, p.x, p.y, rec.w, rec.h]);
  return rows;
}
async function deliver(filename, text, mime) {
  const blob = new Blob([text], { type: mime });
  // On phones/tablets, the share sheet is the easiest way to save or email the file
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

$('saveBtn').onclick = () => {
  deliver(`colony_backup_${stamp()}.json`, JSON.stringify(store), 'application/json');
  toast('Saved to your Downloads folder');
};
$('exportBtn').onclick = () => {
  const rows = masterCSV();
  if (rows.length === 1) { toast('No birds counted yet'); return; }
  deliver(`colony_counts_${stamp()}.csv`, toCSV(rows), 'text/csv');
};

// ---------- menu ----------
$('menuBtn').onclick = () => $('menu').showModal();
$('menu').addEventListener('close', () => {
  const v = $('menu').returnValue;
  $('menu').returnValue = '';
  if (v === 'points') {
    const rows = pointsCSV();
    if (rows.length === 1) return toast('No points yet');
    deliver(`colony_points_${stamp()}.csv`, toCSV(rows), 'text/csv');
  } else if (v === 'backup') {
    deliver(`colony_backup_${stamp()}.json`, JSON.stringify(store, null, 1), 'application/json');
  } else if (v === 'species') {
    $('speciesText').value = store.species.join('\n');
    $('speciesDlg').showModal();
  } else if (v === 'clearImage') {
    if (curName && confirm(`Remove all dots on ${curName}?`)) {
      store.images[curName].points = [];
      history.length = 0;
      save(); draw(); renderSpecies(); refreshOption(); status();
    }
  } else if (v === 'clearAll') {
    if (confirm('Delete ALL counts for ALL images? Export a backup first if unsure.')) {
      store.images = {};
      if (curName && img) store.images[curName] = { w: img.naturalWidth, h: img.naturalHeight, points: [] };
      history.length = 0;
      save(); draw(); renderSpecies(); renderImageSelect(); status();
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
    if (!confirm('Replace current data with this backup?')) return;
    store = { species: data.species || DEFAULT_SPECIES.slice(), images: data.images, current: 0 };
    history.length = 0;
    save(); renderSpecies(); renderImageSelect(); draw(); status();
    toast('Backup restored');
  } catch (err) { toast('That is not a Colony Counter backup'); }
};
$('speciesDlg').addEventListener('close', () => {
  const v = $('speciesDlg').returnValue;
  $('speciesDlg').returnValue = '';
  if (v === 'save' || v === 'reset') {
    const list = v === 'reset' ? DEFAULT_SPECIES.slice()
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
  if (e.target.tagName === 'TEXTAREA' || document.querySelector('dialog[open]')) return;
  if ((e.ctrlKey || e.metaKey) && e.key === 'z') { e.preventDefault(); undo(); }
  else if (e.key === 'ArrowRight') $('nextBtn').click();
  else if (e.key === 'ArrowLeft') $('prevBtn').click();
  else if (/^[1-9]$/.test(e.key) && store.species[+e.key - 1]) { store.current = +e.key - 1; save(); renderSpecies(); }
});
// Folder picking isn't supported on iOS Safari — hide the button there
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

if (window.CLAUDE_START && !Object.keys(store.images).some((k) => store.images[k].points.length)) {
  store = { species: CLAUDE_START.species, images: CLAUDE_START.images, current: 0 };
  save();
  toast("Claude's dots loaded - now open the countpics folder");
}
renderSpecies();
resize();

if ('serviceWorker' in navigator && location.protocol !== 'file:') {
  navigator.serviceWorker.register('sw.js').catch(() => {});
}
