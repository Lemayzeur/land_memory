// LAND MEMORY dashboard. The browser only draws; the Flask server (app.py) runs all the science.
const $ = id => document.getElementById(id), radio = n => document.querySelector(`input[name=${n}]:checked`).value;
const fmt = (v, d = 2) => (v == null || !isFinite(v)) ? '–' : (+v).toFixed(d), sgn = (v, d = 1) => (v >= 0 ? '+' : '') + fmt(v, d);
const deb = (fn, ms) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; };
const post = (u, b) => fetch(u, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b) }).then(r => r.json());
const COL = { hh: '#b2182b', hv: '#2166ac' }, charts = {};
const LEGEND = { t: 'Direction A: red = observation above the cell\'s own history, blue = below (only cells beyond the threshold are coloured)',
  z: 'Direction B: red = stronger response than similar places, blue = weaker (beyond threshold)', b: 'Rainfall-response slope: darker = larger change in backscatter per unit of API',
  mean: 'Mean backscatter (dB): darker = higher', n: 'Number of valid observations per cell: darker = more', delta: 'Digital Twin: simulated change in backscatter for the scenario (red up, blue down)' };
let cfg, map, bbox, jobId = null, meta = null, marker, sel = null, drawing = false, p0 = null, timer = null, rep = null;

// ---------- every control feeds this one request string ----------
const sc = () => ({ rain_mm: $('rain_mm').value, prev: radio('prev'), scn: radio('scn'), change: $('chg').value, dry: $('dry').value });
const qs = () => new URLSearchParams({ pol: $('pol').value, k: $('k').value, peers: $('peers').value, layer: $('layer').value, thr: $('thr').value, di: $('di').value || -1, ...sc() }).toString();
const body = () => ({ bbox, maturity: $('maturity').value, track: $('track').value, rain: $('rain').value, demo: $('demo').checked, token: $('token').value });
const log = t => { $('log').textContent = t; };

// ---------- area of interest ----------
function setBBox(b) {
  bbox = b.map(v => +v.toFixed(4)); $('bbox').textContent = `W ${bbox[0]}  S ${bbox[1]}  E ${bbox[2]}  N ${bbox[3]}`; const [w, s, e, n] = bbox;
  map.getSource('aoi').setData({ type: 'Feature', geometry: { type: 'Polygon', coordinates: [[[w, s], [e, s], [e, n], [w, n], [w, s]]] } });
}
function clampBox(a, b) { const m = cfg.max_side, x2 = a.lng + Math.max(-m, Math.min(m, b.lng - a.lng)), y2 = a.lat + Math.max(-m, Math.min(m, b.lat - a.lat)); return [Math.min(a.lng, x2), Math.min(a.lat, y2), Math.max(a.lng, x2), Math.max(a.lat, y2)]; }
function resetResult() { jobId = null; sel = null; rep = null; if (map.getLayer('ov')) { map.removeLayer('ov'); map.removeSource('ov'); } if (marker) marker.remove(); $('meta').innerHTML = ''; $('sum').textContent = ''; $('prog').style.width = '0'; }
function newArea(b, fly) { resetResult(); setBBox(b); if (fly) map.fitBounds([[b[0], b[1]], [b[2], b[3]]], { padding: 40 }); }

// ---------- find data (fast) / build analysis (slow background job, or instant if precomputed) ----------
async function find() {
  log('Searching ASF…'); const r = await post('/test/search', { bbox, maturity: $('maturity').value });
  $('track').innerHTML = '<option value="">Auto: track with most dates</option>' + r.tracks.map(t => `<option value="${t.key}">${t.label}</option>`).join('');
  log(`Found ${r.count} acquisitions.\n` + r.diag.join('\n') + (r.count ? '' : '\nNo granules: try Scan, another maturity or area, or Demo data.'));
}
async function build() {
  resetResult(); 
  log('Starting…'); 
  const r = await post('/test/jobs', body()); 
  jobId = r.id; 
  clearInterval(timer); 
  timer = setInterval(poll, 1200); 

  // cancel the above query after 15 seconds, avoid lagging
  setTimeout(() => {
    clearInterval(timer);
  }, 15000);
}

async function poll() {
  const m = await fetch(`/test/jobs/${jobId}`).then(r => r.json()); 
  $('prog').style.width = m.progress + '%'; log(m.log.join('\n') + (m.diag.length ? '\n' + m.diag.join('\n') : ''));
  if (m.status === 'running') 
    return; clearInterval(timer);
  if (m.status !== 'done') { 
    log(`${m.error}\n` + m.diag.join('\n')); 
    return;
  }
  meta = m; showMeta(m); refresh();
}
function showMeta(m) {
  $('banner').className = m.demo ? 'demo' : ''; $('banner').textContent = m.demo ? 'DEMO DATA · synthetic, not NISAR' : 'NISAR GCOV · ' + [...new Set(m.dates.map(d => d.maturity))].join(' + ') + ' · ' + m.source;
  $('di').innerHTML = m.dates.map((d, i) => `<option value="${i}">${d.date.slice(0, 10)}${i === m.dates.length - 1 ? ' (latest)' : ''}</option>`).join(''); $('di').value = m.dates.length - 1;
  $('meta').innerHTML = `<b>${m.dates.length}</b> acquisitions · ${m.cell_m} m cells · rain: ${m.rain_label} · <i>${m.source}</i>` + (m.rain_missing ? `<br>${m.rain_missing} rain days missing (never treated as zero)` : '') +
    (m.mixed ? '<br><span class="warn">Mixed maturity or CRID: processing differences may look like change.</span>' : '') + (m.skipped.length ? `<br>Skipped ${m.skipped.length} unreadable files.` : '') +
    `<details><summary>Dates, versions, rain before each pass (mm)</summary><table><tr><th>date (UTC)</th><th>maturity</th><th>CRID</th><th>1d</th><th>3d</th><th>7d</th><th>30d</th></tr>` +
    m.dates.map(d => `<tr><td>${d.date}</td><td>${d.maturity}</td><td>${d.crid}</td><td>${fmt(d.r1, 1)}</td><td>${fmt(d.r3, 1)}</td><td>${fmt(d.r7, 1)}</td><td>${fmt(d.r30, 1)}</td></tr>`).join('') + '</table></details>';
}

// ---------- map overlay (PNG drawn by the server) and area summary ----------
function overlay() {
  if (!jobId) return; const [w, s, e, n] = bbox, coordinates = [[w, n], [e, n], [e, s], [w, s]], url = `/test/jobs/${jobId}/overlay.png?${qs()}&t=${Date.now()}`;
  if (map.getSource('ov')) map.getSource('ov').updateImage({ url, coordinates });
  else { map.addSource('ov', { type: 'image', url, coordinates }); map.addLayer({ id: 'ov', type: 'raster', source: 'ov', paint: { 'raster-opacity': +$('opa').value, 'raster-resampling': 'nearest' } }, 'aoi-line'); }
  $('legend').textContent = LEGEND[$('layer').value];
  fetch(`/test/jobs/${jobId}/summary?${qs()}`).then(r => r.json()).then(s => { $('sum').innerHTML = `<b>Area summary</b>: ${s.cells} cells · median ${s.nobs} observations · median R² ${fmt(s.r2)} · flagged: ${fmt(s.temporal_flag, 1)}% vs own history, ${fmt(s.peer_flag, 1)}% vs similar places`; });
}
const refresh = () => { overlay(); loadPixel(); };

// ---------- charts ----------
function chart(id, type, data, options) {          // tabs re-create their <canvas>, so drop a chart bound to an old canvas
  const el = $(id); if (charts[id] && charts[id].canvas !== el) { charts[id].destroy(); delete charts[id]; }
  if (charts[id]) { Object.assign(charts[id], { data, options }); charts[id].update(); } else charts[id] = new Chart(el, { type, data, options });
}
const base = (x, y) => ({ responsive: true, maintainAspectRatio: false, scales: { x: { type: 'linear', title: { display: true, text: x } }, y: { title: { display: true, text: y } } }, plugins: { legend: { labels: { boxWidth: 12 } } } });
function fitData(r, pol, twin) {
  const m = r.pol[pol]; if (!m) return { datasets: [] }; const used = r.acq.filter(a => a.used && a[pol] != null), xs = [0, Math.max(r.twin.api_after, ...used.map(a => a.api)) * 1.1];
  const ds = [{ label: 'Observed dates', type: 'scatter', data: used.map(a => ({ x: a.api, y: a[pol] })), backgroundColor: '#0E1B2C' },
    { label: 'This cell', type: 'line', data: xs.map(v => ({ x: v, y: m.a + m.b * v })), borderColor: COL.hh, pointRadius: 0 },
    { label: 'If it responded like similar places', type: 'line', data: xs.map(v => ({ x: v, y: m.a + (m.med ?? m.b) * v })), borderColor: COL.hv, borderDash: [6, 4], pointRadius: 0 }];
  if (twin) ds.push({ label: 'Scenario: before → after', type: 'line', data: [{ x: r.twin.api_prev, y: m.twin.ref }, { x: r.twin.api_after, y: m.twin.scn }], borderColor: '#E8A23B', backgroundColor: '#E8A23B', pointRadius: 6, borderWidth: 3 });
  return { datasets: ds };
}

// ---------- the five sections ----------
async function loadPixel() {
  if (!jobId || !sel) return; const r = await fetch(`/test/jobs/${jobId}/pixel?${qs()}&lon=${sel.lng}&lat=${sel.lat}`).then(x => x.json());
  if (!r.ok) { $('t-explore').innerHTML = `<p class="note">${r.msg}</p>`; return; } rep = r; renderExplore(r); renderHistory(r); renderBehavior(r); renderUnusual(r); renderTwin(r);
}
function renderExplore(r) {
  const h = r.pol.hh, v = r.pol.hv, ex = r.acq.filter(a => !a.used).length;
  $('t-explore').innerHTML = `<h4>Selected analysis cell</h4><p class="small">${fmt(r.lat, 4)}, ${fmt(r.lon, 4)} · about ${r.cell_m} m wide. An analysis area, not necessarily one farm.</p>
   <table><tr><td>Land cover (WorldCover)</td><td>${r.land}</td></tr><tr><td>Compared with</td><td>${r.peer} (${r.peers_n} cells)</td></tr><tr><td>NISAR dates in the analysis</td><td>${r.acq.length}</td></tr>
   <tr><td>Valid observations used (HH / HV)</td><td>${h ? h.n : '–'} / ${v ? v.n : '–'}</td></tr><tr><td>Dates excluded (rain gap)</td><td>${ex}</td></tr><tr><td>Confidence</td><td><b>${r.confidence}</b></td></tr></table>
   <p class="note">Open the other tabs for this cell's history, learned behavior, unusual-change checks and the Digital Twin. Few observations mean low confidence; treat results as exploratory.</p>`;
}
function renderHistory(r) {
  const days = r.days, by = {}; r.acq.forEach(a => by[a.date.slice(0, 10)] = a);
  const pts = pol => ({ type: 'line', showLine: false, yAxisID: 'y2', label: pol.toUpperCase() + ' (dB), hollow = excluded', borderColor: COL[pol], pointRadius: 5, data: days.map(d => by[d] ? by[d][pol] : null), pointBackgroundColor: days.map(d => by[d] && by[d].used ? COL[pol] : 'transparent') });
  const data = { labels: days, datasets: [{ type: 'bar', label: 'Daily rain (mm)', data: r.rain, backgroundColor: '#9ec5e8', yAxisID: 'y' }, { type: 'line', label: 'API (rain-history index)', data: r.api, borderColor: '#2166ac', pointRadius: 0, yAxisID: 'y' },
    { type: 'line', showLine: false, label: 'Missing rain data', data: r.rain.map(v => v == null ? 0 : null), pointStyle: 'triangle', pointBackgroundColor: '#b3261e', borderColor: '#b3261e', pointRadius: 5, yAxisID: 'y' }, pts('hh'), pts('hv')] };
  const o = { responsive: true, maintainAspectRatio: false, scales: { x: { ticks: { maxTicksLimit: 8 } }, y: { title: { display: true, text: 'mm' } }, y2: { position: 'right', grid: { drawOnChartArea: false }, title: { display: true, text: 'backscatter (dB)' } } }, plugins: { legend: { labels: { boxWidth: 10 } } } };
  $('t-history').innerHTML = `<h4>What happened and what the satellite observed</h4><div class="cv"><canvas id="ch-hist"></canvas></div>
   <p class="note">Dots are NISAR observation dates; hollow dots were excluded because rain data was missing nearby. Missing rain (red triangles) is never counted as zero. Gaps between dots are missing observations, not "no change".</p>`; chart('ch-hist', 'bar', data, o);
}
function renderBehavior(r) {
  const pol = $('pol').value, rows = ['hh', 'hv'].map(p => { const m = r.pol[p]; return m ? `<div class="eq">${p.toUpperCase()}(dB) = ${fmt(m.a)} ${m.b >= 0 ? '+' : '−'} ${fmt(Math.abs(m.b), 3)} × API</div>` : ''; }).join('');
  const T = ['hh', 'hv'].map(p => { const m = r.pol[p]; return m ? `<tr><td>${p.toUpperCase()}</td><td>${m.n}</td><td>${fmt(m.b, 3)} ± ${fmt(m.se, 3)}</td><td>${fmt(m.r2)}</td><td>${fmt(m.sd)}</td></tr>` : ''; }).join('');
  const m = r.pol[pol], sens = m ? m.sens.map(s => `<tr><td>${s.k}</td><td>${fmt(s.b, 3)}</td><td>${fmt(s.r2)}</td></tr>`).join('') : '';
  $('t-behavior').innerHTML = `<h4>Learned rainfall-response relationship</h4>${rows}<table><tr><th></th><th>n</th><th>slope ± se (dB per API unit)</th><th>R²</th><th>resid. sd (dB)</th></tr>${T}</table>
   <div class="cv"><canvas id="ch-fit"></canvas></div><h4>Sensitivity to the API decay k (${pol.toUpperCase()})</h4><table><tr><th>k</th><th>slope</th><th>R²</th></tr>${sens}</table>
   <p class="note">A statistical relationship, not proof that rainfall caused the radar changes. A low R² or few observations means the model is weak for this cell.</p>`;
  chart('ch-fit', 'scatter', fitData(r, pol, false), base('API (rain-history index, mm-equivalent)', pol.toUpperCase() + ' backscatter (dB)'));
}
function renderUnusual(r) {
  const di = $('di').selectedOptions[0]?.text || '', pol = $('pol').value, thr = +$('thr').value;
  const card = p => { const m = r.pol[p]; if (!m) return `<tr><td>${p.toUpperCase()}</td><td colspan=5>not enough data</td></tr>`; const t = m.temporal;
    return `<tr><td>${p.toUpperCase()}</td><td>${fmt(t.exp, 1)}</td><td>${fmt(t.obs, 1)}</td><td>${t.resid == null ? '–' : sgn(t.resid)}</td><td>${fmt(t.t, 1)}</td><td>${t.t != null && Math.abs(t.t) >= thr ? '<span class="flag">unusual</span>' : 'expected'}</td></tr>`; };
  const peer = p => { const m = r.pol[p]; return m ? `<tr><td>${p.toUpperCase()}</td><td>${fmt(m.b, 3)} ± ${fmt(m.se, 3)}</td><td>${fmt(m.med, 3)}</td><td>${fmt(m.z, 1)}</td><td>${m.z != null && Math.abs(m.z) >= thr ? '<span class="flag">differs from similar places</span>' : 'typical'}</td></tr>` : ''; };
  $('t-unusual').innerHTML = `<h4>A · This cell vs its own history (${di})</h4><table><tr><th></th><th>expected dB</th><th>observed dB</th><th>difference</th><th>std. residual</th><th></th></tr>${card('hh')}${card('hv')}</table>
   <p class="note">The expected value comes from a model fitted on all OTHER dates, so the tested observation is not used to judge itself.</p>
   <h4>B · This cell vs similar places (${r.peer}, ${r.peers_n} cells)</h4><table><tr><th></th><th>slope ± se</th><th>peer median</th><th>score</th><th></th></tr>${peer('hh')}${peer('hv')}</table>
   <div class="cv"><canvas id="ch-peer"></canvas></div><p class="note"><b>An unusual result is not proof of a specific event.</b> It marks a location to investigate. Slopes with large uncertainty are scored cautiously; confidence: ${r.confidence}.</p>`;
  const m = r.pol[pol]; if (!m) return; const e = m.hist.edges, mid = m.hist.counts.map((_, i) => (e[i] + e[i + 1]) / 2), mine = mid.reduce((bi, v, i) => Math.abs(v - m.b) < Math.abs(mid[bi] - m.b) ? i : bi, 0);
  chart('ch-peer', 'bar', { labels: mid.map(v => v.toFixed(3)), datasets: [{ label: `${pol.toUpperCase()} slopes of similar cells (highlight = this cell)`, data: m.hist.counts, backgroundColor: mid.map((_, i) => i === mine ? '#b2182b' : '#9ec5e8') }] }, { responsive: true, maintainAspectRatio: false, plugins: { legend: { labels: { boxWidth: 10 } } } });
}
function renderTwin(r) {
  const R = p => { const m = r.pol[p]; return m ? `<tr><td>${p.toUpperCase()}</td><td>${fmt(m.twin.ref, 1)}</td><td>${fmt(m.twin.norm, 1)}</td><td><b>${fmt(m.twin.scn, 1)}</b> ± ${fmt(m.twin.half, 1)}</td><td>${sgn(m.twin.scn - m.twin.ref)}</td></tr>` : ''; };
  $('twinout').innerHTML = `<p>API: <b>${fmt(r.twin.api_prev, 1)}</b> → <b>${fmt(r.twin.api_after, 1)}</b> mm-equivalent</p><table><tr><th>estimate (dB)</th><th>before</th><th>after, normal</th><th>after, selected</th><th>change</th></tr>${R('hh')}${R('hv')}</table>
   <p class="note">"Previous conditions" use this area's own history: dry = 10th, moderate = median, wet = 90th percentile of its API values.</p>`;
  chart('ch-twin', 'scatter', fitData(r, $('pol').value, true), base('API (rain-history index)', $('pol').value.toUpperCase() + ' backscatter (dB)'));
}
function twinText() {
  const p = { dry: 'Relatively dry', mod: 'Moderate', wet: 'Already wet' }[radio('prev')], ch = radio('scn') === 'changed';
  $('rv').textContent = $('rain_mm').value; $('dv').textContent = $('dry').value; $('cv').textContent = ($('chg').value > 0 ? '+' : '') + $('chg').value; $('chgrow').hidden = !ch;
  $('yin').innerHTML = `${$('rain_mm').value} mm rainfall<br>Previous conditions: ${p}<br>${+$('dry').value ? $('dry').value + ' dry days afterwards<br>' : ''}Scenario: ${ch ? 'Changed landscape conditions (' + $('cv').textContent + '% response)' : 'Normal conditions'}`;
}

// ---------- start-up: Artibonite first; precomputed if available, otherwise demo (no token) ----------
fetch('/test/config').then(r => r.json()).then(c => {
  cfg = c; $('preset').innerHTML = Object.keys(c.presets).map(k => `<option>${k}</option>`).join('') + '<option>Custom (drawn)</option>'; const b = c.presets[c.default];
  map = new maplibregl.Map({ container: 'map', bounds: [[b[0], b[1]], [b[2], b[3]]], fitBoundsOptions: { padding: 60 },
    style: { version: 8, sources: { osm: { type: 'raster', tileSize: 256, attribution: '© OpenStreetMap contributors', tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'] } }, layers: [{ id: 'osm', type: 'raster', source: 'osm' }] } });
  map.on('load', async () => {
    map.addSource('aoi', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } }); map.addLayer({ id: 'aoi-line', type: 'line', source: 'aoi', paint: { 'line-color': '#E8A23B', 'line-width': 3 } });
    setBBox(b); $('preset').value = c.default;                      // no slow web search here: the screen must never wait on NASA
    const pre = await post('/test/jobs', { ...body(), demo: false, cache_only: true });
    if (pre.id) { jobId = pre.id; poll(); }                         // saved real analysis: opens instantly
    else { $('demo').checked = true; build(); }                     // otherwise show the labelled DEMO, so the map is never empty
  });
  map.on('mousedown', e => { if (drawing) p0 = e.lngLat; });
  map.on('mousemove', e => { if (drawing && p0) setBBox(clampBox(p0, e.lngLat)); });
  map.on('mouseup', () => { if (drawing && p0) { drawing = false; map.dragPan.enable(); map.getCanvas().style.cursor = ''; $('draw').textContent = 'Draw area on map'; $('preset').value = 'Custom (drawn)'; p0 = null; resetResult(); find(); } });
  map.on('click', e => { if (drawing || !jobId) return; sel = e.lngLat; if (marker) marker.remove(); marker = new maplibregl.Marker({ color: '#b2182b' }).setLngLat(sel).addTo(map); loadPixel(); });
});
$('draw').onclick = () => { drawing = true; map.dragPan.disable(); map.getCanvas().style.cursor = 'crosshair'; $('draw').textContent = 'Drag a rectangle…'; };
$('preset').onchange = () => { const b = cfg.presets[$('preset').value]; if (b) { newArea(b, true); find(); } };
$('find').onclick = find; $('build').onclick = build; $('maturity').onchange = find;
$('scan').onclick = async () => { log('Scanning presets…'); const r = await fetch('/test/scan').then(x => x.json()); log('NISAR acquisitions found (provisional+validated):\n' + r.map(([n, c]) => `${c < 0 ? 'error' : c}  ${n}`).join('\n')); };
for (const id of ['pol', 'peers', 'k', 'thr', 'layer', 'di']) $(id).onchange = () => { $('kv').textContent = $('k').value; $('tv').textContent = $('thr').value; refresh(); };
$('k').oninput = () => $('kv').textContent = $('k').value; $('thr').oninput = () => $('tv').textContent = $('thr').value;
$('opa').oninput = () => map.getLayer('ov') && map.setPaintProperty('ov', 'raster-opacity', +$('opa').value);
const pixSoft = deb(loadPixel, 150);
for (const el of document.querySelectorAll('#t-twin input')) { el.oninput = () => { twinText(); pixSoft(); }; el.onchange = () => { if ($('layer').value === 'delta') overlay(); }; }
$('showscn').onclick = () => { $('layer').value = 'delta'; overlay(); };
document.querySelectorAll('nav button').forEach(b => b.onclick = () => { document.querySelectorAll('nav button,.tab').forEach(x => x.classList.remove('on')); b.classList.add('on'); $('t-' + b.dataset.tab).classList.add('on'); Object.values(charts).forEach(c => c.resize()); });
$('instant').onclick = () => { $('demo').checked = true; build(); };            // fake data, ready in seconds
$('about').onclick = () => $('modal').hidden = false; $('mclose').onclick = () => $('modal').hidden = true;
twinText();