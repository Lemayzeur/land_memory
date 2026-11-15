// LAND MEMORY dashboard. The browser only draws; all science runs on the Flask server (app.py).
const $ = id => document.getElementById(id), radio = n => document.querySelector(`input[name=${n}]:checked`).value;
const deb = (fn, ms) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; };
const post = (u, b) => fetch(u, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b) }).then(r => r.json());
const START = 'Artibonite, Haiti';
let cfg, map, bbox, jobId = null, chart, marker, sel = null, drawing = false, p0 = null, timer = null;

// ---------- request parameters (every control feeds this one function) ----------
const qs = () => new URLSearchParams({ pol: $('pol').value, k: $('k').value, peers: $('peers').value, layer: $('layer').value,
  thr: $('thr').value, rain_mm: $('rain_mm').value, prev: radio('prev'), scn: radio('scn'), change: $('chg').value }).toString();
const body = () => ({ bbox, maturity: $('maturity').value, track: $('track').value, rain: $('rain').value, demo: $('demo').checked, token: $('token').value });
const log = t => { $('log').textContent = t; };

// ---------- area of interest ----------
function setBBox(b) {
  bbox = b.map(v => +v.toFixed(4)); $('bbox').textContent = `W ${bbox[0]}  S ${bbox[1]}  E ${bbox[2]}  N ${bbox[3]}`;
  const [w, s, e, n] = bbox;
  map.getSource('aoi').setData({ type: 'Feature', geometry: { type: 'Polygon', coordinates: [[[w, s], [e, s], [e, n], [w, n], [w, s]]] } });
}
function clampBox(a, b) {
  const m = cfg.max_side, dx = Math.max(-m, Math.min(m, b.lng - a.lng)), dy = Math.max(-m, Math.min(m, b.lat - a.lat));
  const x2 = a.lng + dx, y2 = a.lat + dy; return [Math.min(a.lng, x2), Math.min(a.lat, y2), Math.max(a.lng, x2), Math.max(a.lat, y2)];
}
function resetResult() { jobId = null; if (map.getLayer('ov')) { map.removeLayer('ov'); map.removeSource('ov'); } if (marker) marker.remove(); $('meta').innerHTML = ''; $('prog').style.width = '0'; }
function newArea(b, fly) { resetResult(); setBBox(b); if (fly) map.fitBounds([[b[0], b[1]], [b[2], b[3]]], { padding: 40 }); }

// ---------- 1) find data (fast)  2) build analysis (slow, background job) ----------
async function find() {
  log('Searching ASF…'); const r = await post('/api/search', { bbox, maturity: $('maturity').value });
  $('track').innerHTML = '<option value="">Auto: track with most dates</option>' + r.tracks.map(t => `<option value="${t.key}">${t.label}</option>`).join('');
  log(`Found ${r.count} acquisitions.\n` + r.diag.join('\n') + (r.count ? '' : '\nNo granules: try Scan, padding the area, another maturity, or Demo data.'));
}
async function build() {
  resetResult(); log('Starting…'); const r = await post('/api/jobs', body()); jobId = r.id; clearInterval(timer); timer = setInterval(poll, 1200);
}
async function poll() {
  const m = await fetch(`/api/jobs/${jobId}`).then(r => r.json()); $('prog').style.width = m.progress + '%';
  log(m.log.join('\n') + (m.diag.length ? '\n' + m.diag.join('\n') : ''));
  if (m.status === 'running') return; clearInterval(timer);
  if (m.status !== 'done') { log(`${m.error}\n` + m.diag.join('\n')); return; }
  showMeta(m); refresh();
}
function showMeta(m) {
  $('banner').className = m.demo ? 'demo' : ''; $('banner').textContent = m.demo ? 'DEMO DATA · synthetic, not NISAR' : 'NISAR GCOV · ' + [...new Set(m.dates.map(d => d.maturity))].join(' + ');
  $('meta').innerHTML = `<b>${m.dates.length}</b> acquisitions · rain: ${m.rain_label}` + (m.mixed ? '<br><span class="warn">Mixed maturity or CRID: processing differences may look like change.</span>' : '') +
    (m.skipped.length ? `<br>Skipped ${m.skipped.length} unreadable files.` : '') +
    `<details><summary>Dates, versions, rain before each pass (mm)</summary><table><tr><th>date (UTC)</th><th>maturity</th><th>CRID</th><th>1d</th><th>3d</th><th>7d</th><th>30d</th></tr>` +
    m.dates.map(d => `<tr><td>${d.date}</td><td>${d.maturity}</td><td>${d.crid}</td><td>${d.r1}</td><td>${d.r3}</td><td>${d.r7}</td><td>${d.r30}</td></tr>`).join('') + '</table></details>';
}

// ---------- map overlay (PNG made by the server) ----------
function overlay() {
  if (!jobId) return; const [w, s, e, n] = bbox, coordinates = [[w, n], [e, n], [e, s], [w, s]], url = `/api/jobs/${jobId}/overlay.png?${qs()}&t=${Date.now()}`;
  if (map.getSource('ov')) map.getSource('ov').updateImage({ url, coordinates });
  else { map.addSource('ov', { type: 'image', url, coordinates }); map.addLayer({ id: 'ov', type: 'raster', source: 'ov', paint: { 'raster-opacity': +$('opa').value, 'raster-resampling': 'nearest' } }, 'aoi-line'); }
}
async function pixel() {
  if (!jobId || !sel) return; const r = await fetch(`/api/jobs/${jobId}/pixel?${qs()}&lon=${sel.lng}&lat=${sel.lat}`).then(x => x.json());
  if (!r.ok) { $('info').textContent = r.msg; return; }
  const S = r.scn, flag = Math.abs(r.z) >= +$('thr').value, d = S.scn - S.ref, pol = $('pol').value.toUpperCase();
  $('info').innerHTML = `Peers: <b>${r.peer}</b> · ${pol}<br>Response slope <b>${r.b.toFixed(3)}</b> dB/mm (±${r.se.toFixed(3)}) vs peer median ${r.med.toFixed(3)}<br>
   z = <b>${r.z.toFixed(1)}</b> ${flag ? '<span class="flag">responds unlike its peers</span>' : '(within peer range)'}<br>
   <b>Twin:</b> ${S.ref.toFixed(1)} dB before → <b>${S.scn.toFixed(1)} dB</b> (±${S.half.toFixed(1)}) after the event · change ${d >= 0 ? '+' : ''}${d.toFixed(1)} dB`;
  const xs = [0, Math.max(S.api_after, ...r.api) * 1.1], pts = r.api.map((a, i) => ({ x: a, y: r.y[i] })).filter(p => p.y !== null);
  const data = { datasets: [
    { label: 'Observed dates', data: pts, backgroundColor: '#0E1B2C' },
    { label: 'This location', type: 'line', data: xs.map(v => ({ x: v, y: r.a + r.b * v })), borderColor: '#b2182b', pointRadius: 0 },
    { label: 'If it responded like peers', type: 'line', data: xs.map(v => ({ x: v, y: r.a + r.med * v })), borderColor: '#2166ac', borderDash: [6, 4], pointRadius: 0 },
    { label: 'Scenario: before → after', type: 'line', data: [{ x: r.api_prev, y: S.ref }, { x: S.api_after, y: S.scn }], borderColor: '#E8A23B', backgroundColor: '#E8A23B', pointRadius: 6, borderWidth: 3 }] };
  const opt = { scales: { x: { type: 'linear', title: { display: true, text: 'Recent rain index (mm)' } }, y: { title: { display: true, text: pol + ' backscatter (dB)' } } }, plugins: { legend: { labels: { boxWidth: 12 } } } };
  chart ? (chart.data = data, chart.options = opt, chart.update()) : chart = new Chart($('chart'), { type: 'scatter', data, options: opt });
}
const refresh = () => { overlay(); pixel(); }, refreshSoft = deb(pixel, 150);
function twinText() {
  const p = { dry: 'Relatively dry', mod: 'Moderate', wet: 'Already wet' }[radio('prev')], ch = radio('scn') === 'changed';
  $('rv').textContent = $('rain_mm').value; $('cv').textContent = ($('chg').value > 0 ? '+' : '') + $('chg').value; $('chgrow').hidden = !ch;
  $('yin').innerHTML = `${$('rain_mm').value} mm rainfall<br>Previous conditions: ${p}<br>Scenario: ${ch ? 'Changed landscape conditions (' + $('cv').textContent + '% response)' : 'Normal conditions'}`;
}

// ---------- start-up ----------
fetch('/api/config').then(r => r.json()).then(c => {
  cfg = c; $('preset').innerHTML = Object.keys(c.presets).map(k => `<option>${k}</option>`).join('') + '<option>Custom (drawn)</option>';
  const b = c.presets[START];
  map = new maplibregl.Map({ container: 'map', bounds: [[b[0], b[1]], [b[2], b[3]]], fitBoundsOptions: { padding: 60 },
    style: { version: 8, sources: { osm: { type: 'raster', tileSize: 256, attribution: '© OpenStreetMap contributors', tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'] } }, layers: [{ id: 'osm', type: 'raster', source: 'osm' }] } });
  map.on('load', async () => {
    map.addSource('aoi', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } });
    map.addLayer({ id: 'aoi-line', type: 'line', source: 'aoi', paint: { 'line-color': '#E8A23B', 'line-width': 3 } });
    setBBox(b); $('preset').value = START;
    if (!c.has_token) $('demo').checked = true;                  // first launch with no credentials: show the demo straight away
    if (!$('demo').checked) await find(); else { await find(); build(); }
  });
  map.on('mousedown', e => { if (drawing) p0 = e.lngLat; });
  map.on('mousemove', e => { if (drawing && p0) setBBox(clampBox(p0, e.lngLat)); });
  map.on('mouseup', e => { if (drawing && p0) { drawing = false; map.dragPan.enable(); map.getCanvas().style.cursor = ''; $('draw').textContent = 'Draw area on map'; $('preset').value = 'Custom (drawn)'; p0 = null; resetResult(); find(); } });
  map.on('click', e => { if (drawing || !jobId) return; sel = e.lngLat; if (marker) marker.remove(); marker = new maplibregl.Marker({ color: '#b2182b' }).setLngLat(sel).addTo(map); pixel(); });
});
$('draw').onclick = () => { drawing = true; map.dragPan.disable(); map.getCanvas().style.cursor = 'crosshair'; $('draw').textContent = 'Drag a rectangle…'; };
$('preset').onchange = () => { const b = cfg.presets[$('preset').value]; if (b) { newArea(b, true); find(); } };
$('find').onclick = find; $('build').onclick = build; $('maturity').onchange = find;
$('scan').onclick = async () => { log('Scanning presets…'); const r = await fetch('/api/scan').then(x => x.json()); log('NISAR acquisitions found (provisional+validated):\n' + r.map(([n, c]) => `${c < 0 ? 'error' : c}  ${n}`).join('\n')); };
for (const id of ['pol', 'peers', 'k', 'thr', 'layer']) $(id).onchange = () => { $('kv').textContent = $('k').value; $('tv').textContent = $('thr').value; refresh(); };
$('k').oninput = () => $('kv').textContent = $('k').value; $('thr').oninput = () => $('tv').textContent = $('thr').value;
$('opa').oninput = () => map.getLayer('ov') && map.setPaintProperty('ov', 'raster-opacity', +$('opa').value);
for (const el of document.querySelectorAll('#twin input')) { el.oninput = () => { twinText(); refreshSoft(); }; el.onchange = () => { if ($('layer').value === 'delta') overlay(); }; }
$('showscn').onclick = () => { $('layer').value = 'delta'; overlay(); };
twinText();