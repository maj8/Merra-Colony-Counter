/* Merra Colony Counter: survey files.
 *
 * A survey file is the zip the survey set-up page makes (colony-survey_<id>.zip). A counter
 * opens it here with "Open survey file"; the settings and photos are read in the browser and
 * kept on this device (IndexedDB), so the survey works offline from then on. Nothing is sent
 * anywhere: the photos never leave the device.
 *
 * Runs before app.js. If the page already has a survey (survey/survey.js next to index.html,
 * e.g. an unzipped survey on a computer) it does nothing; otherwise it loads the survey kept
 * on this device, if any, then starts app.js.
 */
(function () {
  'use strict';
  const DB = 'merra-colony-counter', STORE = 'survey-files', KEY = 'active';

  function db() {
    return new Promise((ok, bad) => {
      const r = indexedDB.open(DB, 1);
      r.onupgradeneeded = () => r.result.createObjectStore(STORE);
      r.onsuccess = () => ok(r.result);
      r.onerror = () => bad(r.error);
    });
  }
  async function idb(mode, fn) {
    const d = await db();
    return new Promise((ok, bad) => {
      const tx = d.transaction(STORE, mode);
      const req = fn(tx.objectStore(STORE));
      tx.oncomplete = () => { d.close(); ok(req && req.result); };
      tx.onerror = tx.onabort = () => { d.close(); bad(tx.error || new Error('Storage failed')); };
    });
  }
  const getKept = () => idb('readonly', (s) => s.get(KEY));
  const keep = (v) => idb('readwrite', (s) => s.put(v, KEY));
  const forget = () => idb('readwrite', (s) => s.delete(KEY));

  /* ---------- reading a zip (stored or deflated entries; what browsers, Windows and Macs make) ---------- */
  async function unzip(file) {
    const buf = new Uint8Array(await file.arrayBuffer());
    const dv = new DataView(buf.buffer, buf.byteOffset, buf.byteLength);
    let eocd = -1;
    for (let i = buf.length - 22; i >= Math.max(0, buf.length - 65557); i--) {
      if (dv.getUint32(i, true) === 0x06054b50) { eocd = i; break; }
    }
    if (eocd < 0) throw new Error('This is not a zip file.');
    const count = dv.getUint16(eocd + 10, true);
    let p = dv.getUint32(eocd + 16, true);
    const dec = new TextDecoder();
    const entries = new Map();
    for (let n = 0; n < count; n++) {
      if (dv.getUint32(p, true) !== 0x02014b50) throw new Error('The zip file is damaged.');
      const method = dv.getUint16(p + 10, true);
      const csize = dv.getUint32(p + 20, true);
      const nlen = dv.getUint16(p + 28, true), xlen = dv.getUint16(p + 30, true), clen = dv.getUint16(p + 32, true);
      const local = dv.getUint32(p + 42, true);
      const name = dec.decode(buf.subarray(p + 46, p + 46 + nlen));
      p += 46 + nlen + xlen + clen;
      if (name.endsWith('/') || name.includes('__MACOSX/') || /(^|\/)\._/.test(name)) continue;
      const lnlen = dv.getUint16(local + 26, true), lxlen = dv.getUint16(local + 28, true);
      const start = local + 30 + lnlen + lxlen;
      entries.set(name, { method, data: buf.subarray(start, start + csize) });
    }
    return {
      names: [...entries.keys()],
      async blob(name, type) {
        const e = entries.get(name);
        if (e.method === 0) return new Blob([e.data], { type });
        if (e.method === 8) {
          if (typeof DecompressionStream === 'undefined') throw new Error('This browser cannot open compressed zip files. Please update it, or use the zip exactly as the survey set-up page made it.');
          const out = new Blob([e.data]).stream().pipeThrough(new DecompressionStream('deflate-raw'));
          return new Blob([await new Response(out).arrayBuffer()], { type });
        }
        throw new Error(`The zip uses a compression this app cannot read (${name}).`);
      },
    };
  }

  // survey.js as the set-up page writes it: a comment, then  self.SURVEY = {JSON};
  function parseSurveyJs(text) {
    const i = text.indexOf('{'), j = text.lastIndexOf('}');
    if (i < 0 || j < i) throw new Error('The survey settings in this file could not be read.');
    const s = JSON.parse(text.slice(i, j + 1));
    if (!s || !Array.isArray(s.images) || !s.images.length) throw new Error('This survey has no photos.');
    return s;
  }

  async function readSurveyFile(file, progress) {
    const z = await unzip(file);
    const sjs = z.names.find((n) => /(^|\/)survey\/survey\.js$/.test(n));
    if (!sjs) throw new Error('This zip is not a Merra Colony Counter survey (there is no survey/survey.js inside). Ask the organiser for the survey file made on colony.merra.org.');
    const prefix = sjs.slice(0, -'survey/survey.js'.length);
    const survey = parseSurveyJs(await (await z.blob(sjs, 'text/javascript')).text());
    const photos = {}, missing = [];
    let k = 0;
    for (const it of survey.images) {
      progress && progress(++k, survey.images.length);
      const path = `${prefix}survey/images/${it.file}`;
      if (!z.names.includes(path)) { missing.push(it.file); continue; }
      photos[it.file] = await z.blob(path, /\.png$/i.test(it.file) ? 'image/png' : 'image/jpeg');
    }
    if (missing.length) throw new Error(`Photos missing from the survey file: ${missing.slice(0, 4).join(', ')}${missing.length > 4 ? ' …' : ''}`);
    return { survey, photos, fileName: file.name, opened: new Date().toISOString() };
  }

  // Called by the app's "Open survey file" button.
  async function openSurveyFile(file, ui) {
    const said = (t) => ui && ui.status && ui.status(t);
    said('Reading the survey file…');
    const kept = await readSurveyFile(file, (i, n) => said(`Reading photo ${i} of ${n}…`));
    said('Keeping the survey on this device…');
    try {
      await keep(kept);
    } catch (e) {
      throw new Error('There is not enough space on this device to keep the survey. Free some space and try again.');
    }
    if (navigator.storage && navigator.storage.persist) navigator.storage.persist().catch(() => {});
    return kept.survey;
  }

  window.MerraSurveyFile = {
    open: openSurveyFile,
    remove: forget,
    get fromDevice() { return !!window.SURVEY_FROM_DEVICE; },
  };

  function startApp() {
    const s = document.createElement('script');
    s.src = 'app.js';
    document.body.appendChild(s);
  }

  if (window.SURVEY || !window.indexedDB) { startApp(); return; }
  getKept().then((kept) => {
    if (kept && kept.survey) {
      window.SURVEY = kept.survey;
      window.SURVEY_FILES = {};
      for (const [name, blob] of Object.entries(kept.photos || {})) window.SURVEY_FILES[name] = URL.createObjectURL(blob);
      window.SURVEY_FROM_DEVICE = true;
    }
  }).catch(() => { /* private window or storage blocked: carry on without */ }).finally(startApp);
})();
