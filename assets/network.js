// LähiLab network: simulated demo boxes + the Finland map on the overview page.
// Show-case only: these boxes are fixed demo data (not from the board). The live box (BOX-12)
// comes from the real notifications and is merged in by app.js.

/* eslint-disable no-unused-vars */

const DEMO_BOXES = [
  { box_id: 'BOX-01', location: 'Helsinki · Kallio library', region: 'Uusimaa', lat: 60.184, lon: 24.950,
    kits: 9, types: { HPV: 6, FIT: 3 }, temp_c: 21.8, level: 'soon', light: 'yellow', pickup: true, time: '09:42' },
  { box_id: 'BOX-03', location: 'Espoo · Iso Omena health centre', region: 'Uusimaa', lat: 60.161, lon: 24.738,
    kits: 7, types: { HPV: 4, FIT: 3 }, temp_c: 21.1, labelSide: 'left', level: 'ok', light: 'green', pickup: false, time: '09:37' },
  { box_id: 'BOX-05', location: 'Tampere · Hervanta pharmacy', region: 'Pirkanmaa', lat: 61.450, lon: 23.851,
    kits: 8, types: { HPV: 5, FIT: 3 }, temp_c: 22.4, level: 'urgent', light: 'red', pickup: true, time: '09:40' },
  { box_id: 'BOX-07', location: 'Turku · Varissuo library', region: 'Southwest Finland', lat: 60.447, lon: 22.367,
    kits: 6, types: { HPV: 3, FIT: 3 }, temp_c: 20.6, level: 'ok', light: 'green', pickup: false, time: '09:31' },
  { box_id: 'BOX-09', location: 'Jyväskylä · Kompassi library', region: 'Central Finland', lat: 62.242, lon: 25.747,
    kits: 5, types: { HPV: 3, FIT: 2 }, temp_c: 20.9, level: 'ok', light: 'green', pickup: false, time: '09:28' },
  { box_id: 'BOX-14', location: 'Lahti · Kauppatori pharmacy', region: 'Päijät-Häme', lat: 60.983, lon: 25.656,
    kits: 4, types: { HPV: 2, FIT: 2 }, temp_c: 22.0, level: 'soon', light: 'yellow', pickup: true, time: '09:35' },
  { box_id: 'BOX-16', location: 'Oulu · Linnanmaa health centre', region: 'North Ostrobothnia', lat: 65.012, lon: 25.471,
    kits: 4, types: { HPV: 2, FIT: 2 }, temp_c: 19.7, level: 'ok', light: 'green', pickup: false, time: '09:22' },
  { box_id: 'BOX-18', location: 'Vaasa · city library', region: 'Ostrobothnia', lat: 63.096, lon: 21.616,
    kits: 3, types: { HPV: 2, FIT: 1 }, temp_c: 20.3, level: 'ok', light: 'green', pickup: false, time: '09:18' },
  { box_id: 'BOX-21', location: 'Joensuu · Rantakylä pharmacy', region: 'North Karelia', lat: 62.601, lon: 29.763,
    kits: 2, types: { HPV: 1, FIT: 1 }, temp_c: 21.2, level: 'ok', light: 'green', pickup: false, time: '09:12' },
  { box_id: 'BOX-23', location: 'Mikkeli · health centre', region: 'South Savo', lat: 61.688, lon: 27.272,
    kits: 2, types: { HPV: 1, FIT: 1 }, temp_c: 20.8, level: 'ok', light: 'green', pickup: false, time: '09:09' },
  { box_id: 'BOX-25', location: 'Kajaani · city library', region: 'Kainuu', lat: 64.227, lon: 27.728,
    kits: 1, types: { HPV: 1, FIT: 0 }, temp_c: 19.9, level: 'ok', light: 'green', pickup: false, time: '09:05' },
  { box_id: 'BOX-27', location: 'Kuusamo · pharmacy', region: 'North Ostrobothnia', lat: 65.964, lon: 29.189,
    kits: 1, types: { HPV: 0, FIT: 1 }, temp_c: 18.9, level: 'ok', light: 'green', pickup: false, time: '08:58' },
  { box_id: 'BOX-29', location: 'Rovaniemi · Lappia library', region: 'Lapland', lat: 66.503, lon: 25.729,
    kits: 1, types: { HPV: 1, FIT: 0 }, temp_c: 19.4, level: 'soon', light: 'yellow', pickup: true, time: '08:51' },
  { box_id: 'BOX-31', location: 'Ivalo · health centre', region: 'Lapland', lat: 68.658, lon: 27.540,
    kits: 0, types: { HPV: 0, FIT: 0 }, temp_c: 18.2, level: 'empty', light: 'off', pickup: false, time: '08:44' },
].map(box => ({ ...box, demo: true }));

// Where the real boxes stand (the board only sends a location name).
const LIVE_BOX_PLACES = {
  'BOX-12': { region: 'North Savo', lat: 62.893, lon: 27.678 },
};

// Simplified outline of Finland (lon, lat), clockwise from Hanko. Good enough for a show map.
const FINLAND_OUTLINE = [
  [22.95, 59.82], [23.5, 59.95], [24.3, 60.05], [24.95, 60.15], [25.65, 60.25], [26.4, 60.38],
  [26.95, 60.45], [27.75, 60.52], [28.25, 60.65], [28.7, 60.85], [29.3, 61.2], [29.9, 61.55],
  [30.5, 61.95], [31.05, 62.3], [31.4, 62.65], [31.58, 62.9], [31.25, 63.15], [30.75, 63.45],
  [30.0, 63.75], [29.95, 64.1], [30.1, 64.4], [30.05, 64.75], [29.65, 65.0], [29.75, 65.3],
  [29.85, 65.6], [29.95, 66.05], [29.4, 66.5], [29.05, 66.95], [29.6, 67.3], [29.9, 67.6],
  [29.35, 68.1], [28.7, 68.45], [28.45, 68.55], [28.8, 68.9], [28.93, 69.05], [28.85, 69.25],
  [28.3, 69.45], [28.5, 69.75], [28.0, 70.05], [27.6, 70.08], [27.0, 69.92], [26.5, 69.95],
  [25.9, 69.6], [25.75, 69.35], [25.6, 69.0], [25.1, 68.75], [24.2, 68.72], [23.6, 68.75],
  [22.9, 68.7], [22.35, 68.85], [21.9, 69.05], [21.3, 69.3], [20.55, 69.06], [21.0, 68.9],
  [21.75, 68.55], [22.4, 68.45], [23.1, 68.2], [23.6, 67.95], [23.5, 67.55], [23.75, 67.1],
  [23.6, 66.75], [23.9, 66.5], [23.7, 66.2], [24.15, 65.85], [24.6, 65.7], [25.1, 65.5],
  [25.3, 65.25], [25.45, 65.0], [24.9, 64.85], [24.5, 64.7], [24.2, 64.45], [23.9, 64.2],
  [23.2, 63.88], [22.7, 63.7], [22.2, 63.45], [21.5, 63.25], [21.25, 63.0], [21.4, 62.7],
  [21.2, 62.4], [21.4, 62.1], [21.55, 61.7], [21.45, 61.3], [21.4, 60.95], [21.35, 60.75],
  [21.8, 60.5], [22.3, 60.35], [22.6, 60.2], [23.1, 60.05],
];
const ALAND_OUTLINE = [[19.6, 60.1], [20.05, 59.98], [20.35, 60.12], [20.3, 60.35], [19.85, 60.42], [19.55, 60.28]];

// Lab hubs the courier routes lead to (generic, unnamed).
const LAB_HUBS = [
  { name: 'Lab hub · south', lat: 60.21, lon: 24.9 },
  { name: 'Lab hub · west', lat: 61.5, lon: 23.76 },
  { name: 'Lab hub · north', lat: 65.06, lon: 25.47 },
];

const MAP_W = 370;
const MAP_H = 640;
const SVG_NS = 'http://www.w3.org/2000/svg';

/** lon/lat -> SVG x/y. Longitude is shrunk by cos(lat), so the north narrows like on a globe. */
function projectPoint(lon, lat) {
  const k = 58;
  return [176 + (lon - 25.5) * Math.cos((lat * Math.PI) / 180) * k, 16 + (70.15 - lat) * k];
}

function svgEl(tag, attrs = {}, parent = null) {
  const el = document.createElementNS(SVG_NS, tag);
  Object.entries(attrs).forEach(([key, value]) => el.setAttribute(key, value));
  if (parent) parent.appendChild(el);
  return el;
}

function pointInPolygon(x, y, poly) {
  let inside = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, yi] = poly[i];
    const [xj, yj] = poly[j];
    if ((yi > y) !== (yj > y) && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}

const toPath = poly => `M ${poly.map(([x, y]) => `${x.toFixed(1)} ${y.toFixed(1)}`).join(' L ')} Z`;

/** The static layer (graticule, dot-matrix country, outline, lab hubs) is drawn once. */
let mapStaticDrawn = false;
let mapDynamicLayer = null;

function drawMapBase(svg) {
  const defs = svgEl('defs', {}, svg);
  const glow = svgEl('filter', { id: 'map-glow', x: '-50%', y: '-50%', width: '200%', height: '200%' }, defs);
  svgEl('feGaussianBlur', { stdDeviation: '3', result: 'b' }, glow);
  const merge = svgEl('feMerge', {}, glow);
  svgEl('feMergeNode', { in: 'b' }, merge);
  svgEl('feMergeNode', { in: 'SourceGraphic' }, merge);
  const fill = svgEl('linearGradient', { id: 'map-fill', x1: '0', y1: '0', x2: '0', y2: '1' }, defs);
  svgEl('stop', { offset: '0', 'stop-color': 'var(--map-fill-top)' }, fill);
  svgEl('stop', { offset: '1', 'stop-color': 'var(--map-fill-bottom)' }, fill);

  // Graticule
  const grid = svgEl('g', { class: 'map-graticule' }, svg);
  for (let lat = 60; lat <= 70; lat += 2) {
    const pts = [];
    for (let lon = 18; lon <= 33; lon += 0.5) pts.push(projectPoint(lon, lat));
    svgEl('polyline', { points: pts.map(p => p.join(',')).join(' ') }, grid);
    const [lx, ly] = projectPoint(33, lat);
    const label = svgEl('text', { x: Math.min(lx, MAP_W - 4), y: ly - 3, 'text-anchor': 'end' }, grid);
    label.textContent = `${lat}°N`;
  }
  for (let lon = 20; lon <= 32; lon += 3) {
    const pts = [];
    for (let lat = 59.5; lat <= 70.5; lat += 0.5) pts.push(projectPoint(lon, lat));
    svgEl('polyline', { points: pts.map(p => p.join(',')).join(' ') }, grid);
  }

  const mainland = FINLAND_OUTLINE.map(([lon, lat]) => projectPoint(lon, lat));
  const aland = ALAND_OUTLINE.map(([lon, lat]) => projectPoint(lon, lat));

  svgEl('path', { d: toPath(mainland) + ' ' + toPath(aland), class: 'map-land' }, svg);

  // Dot-matrix fill
  const dots = svgEl('g', { class: 'map-dots' }, svg);
  const step = 7;
  for (let y = step / 2; y < MAP_H; y += step) {
    for (let x = step / 2; x < MAP_W; x += step) {
      if (pointInPolygon(x, y, mainland) || pointInPolygon(x, y, aland)) {
        svgEl('circle', { cx: x, cy: y, r: 1.05 }, dots);
      }
    }
  }

  svgEl('path', { d: toPath(mainland) + ' ' + toPath(aland), class: 'map-outline', filter: 'url(#map-glow)' }, svg);

  mapDynamicLayer = svgEl('g', { class: 'map-dynamic' }, svg);
  mapStaticDrawn = true;
}

function nearestHub(box) {
  let best = LAB_HUBS[0];
  let bestD = Infinity;
  LAB_HUBS.forEach(hub => {
    const d = (hub.lat - box.lat) ** 2 + ((hub.lon - box.lon) * 0.5) ** 2;
    if (d < bestD) { bestD = d; best = hub; }
  });
  return best;
}

const LIGHT_COLORS = { green: 'var(--green)', yellow: 'var(--yellow)', red: 'var(--red)', off: 'var(--muted)' };

function setReadout(box) {
  const readout = document.getElementById('map-readout');
  if (!readout) return;
  if (!box) {
    readout.innerHTML = '<span class="readout-hint">Point at a box to inspect it</span>';
    return;
  }
  readout.replaceChildren();
  const title = document.createElement('strong');
  title.textContent = `${box.box_id}${box.demo ? '' : ' · LIVE'}`;
  const where = document.createElement('span');
  where.textContent = `${box.location} — ${box.region}`;
  const stats = document.createElement('span');
  const temp = typeof box.temp_c === 'number' ? `${box.temp_c} °C` : '– °C';
  const kits = typeof box.kits === 'number' ? box.kits : '–';
  stats.textContent = `${kits} samples · ${temp} · ${box.level || 'no status'}${box.pickup ? ' · pickup' : ''}`;
  readout.append(title, where, stats);
}

/** Region totals; a region is "low" when it holds less than half the average regional sample count. */
function regionSummary(boxes) {
  const regions = new Map();
  boxes.forEach(box => {
    const r = regions.get(box.region) || { region: box.region, kits: 0, boxes: 0, lat: 0, lon: 0 };
    r.kits += typeof box.kits === 'number' ? box.kits : 0;
    r.boxes += 1;
    r.lat += box.lat;
    r.lon += box.lon;
    regions.set(box.region, r);
  });
  const list = Array.from(regions.values()).map(r => ({ ...r, lat: r.lat / r.boxes, lon: r.lon / r.boxes }));
  const mean = list.reduce((t, r) => t + r.kits, 0) / Math.max(list.length, 1);
  list.forEach(r => { r.low = r.kits < mean * 0.5; });
  list.sort((a, b) => b.kits - a.kits);
  return { list, mean };
}

/** Called by app.js on every dashboard refresh with the live boxes from the board. */
function renderNetworkMap(liveBoxes) {
  const svg = document.getElementById('finland-map');
  if (!svg) return;
  if (!mapStaticDrawn) drawMapBase(svg);

  const live = Object.entries(LIVE_BOX_PLACES).map(([id, place]) => {
    const latest = liveBoxes.find(b => b.box_id === id);
    return { box_id: id, location: latest ? latest.location : 'Kuopio library', demo: false, ...place,
      kits: latest ? latest.kits : null, temp_c: latest ? latest.temp_c : null,
      level: latest ? latest.level : null, light: latest ? latest.light : 'off', pickup: latest ? latest.pickup : false };
  });
  const all = [...live, ...DEMO_BOXES];
  const { list: regions } = regionSummary(all);
  const lowRegions = new Set(regions.filter(r => r.low).map(r => r.region));
  const maxKits = Math.max(1, ...all.map(b => (typeof b.kits === 'number' ? b.kits : 0)));

  mapDynamicLayer.replaceChildren();

  // Courier routes
  const routes = svgEl('g', { class: 'map-routes' }, mapDynamicLayer);
  all.forEach(box => {
    const hub = nearestHub(box);
    const [x1, y1] = projectPoint(box.lon, box.lat);
    const [x2, y2] = projectPoint(hub.lon, hub.lat);
    if (Math.hypot(x2 - x1, y2 - y1) < 6) return;
    const mx = (x1 + x2) / 2 + (y2 - y1) * 0.18;
    const my = (y1 + y2) / 2 - (x2 - x1) * 0.18;
    svgEl('path', { d: `M ${x1} ${y1} Q ${mx} ${my} ${x2} ${y2}`, class: box.pickup ? 'route is-active' : 'route' }, routes);
  });

  // Low-coverage regions: a dashed halo + label around the region's centre
  const gaps = svgEl('g', { class: 'map-gaps' }, mapDynamicLayer);
  regions.filter(r => r.low).forEach(r => {
    const [x, y] = projectPoint(r.lon, r.lat);
    svgEl('circle', { cx: x, cy: y, r: 26, class: 'gap-halo' }, gaps);
    // Two-line label to the right of the halo (the east side of the map has free space).
    const label = svgEl('text', { x: x + 30, y: y - 3, class: 'gap-label' }, gaps);
    const top = svgEl('tspan', { x: x + 30, class: 'gap-tag' }, label);
    top.textContent = 'LOW COVERAGE';
    const name = svgEl('tspan', { x: x + 30, dy: 9 }, label);
    name.textContent = r.region.toUpperCase();
  });

  // Lab hubs
  const hubs = svgEl('g', { class: 'map-hubs' }, mapDynamicLayer);
  LAB_HUBS.forEach(hub => {
    const [x, y] = projectPoint(hub.lon, hub.lat);
    svgEl('rect', { x: x - 4, y: y - 4, width: 8, height: 8, transform: `rotate(45 ${x} ${y})`, class: 'hub' }, hubs);
  });

  // Boxes
  const markers = svgEl('g', { class: 'map-markers' }, mapDynamicLayer);
  all.forEach(box => {
    const [x, y] = projectPoint(box.lon, box.lat);
    const kits = typeof box.kits === 'number' ? box.kits : 0;
    const r = 3.5 + Math.sqrt(kits / maxKits) * 7;
    const color = LIGHT_COLORS[box.light] || LIGHT_COLORS.off;
    const g = svgEl('g', { class: `marker${box.demo ? '' : ' is-live'}${lowRegions.has(box.region) ? ' is-low' : ''}`,
      tabindex: '0', style: `--c: ${color}` }, markers);
    svgEl('circle', { cx: x, cy: y, r: r + 6, class: 'marker-pulse' }, g);
    svgEl('circle', { cx: x, cy: y, r, class: 'marker-core' }, g);
    if (kits > 0) {
      const left = box.labelSide === 'left';
      const t = svgEl('text', { x: left ? x - r - 4 : x + r + 4, y: y + 3.5, class: 'marker-label',
        'text-anchor': left ? 'end' : 'start' }, g);
      t.textContent = kits;
    }
    if (!box.demo) {
      const t = svgEl('text', { x: x + r + 4, y: y - 8, class: 'marker-live' }, g);
      t.textContent = 'LIVE';
    }
    const title = svgEl('title', {}, g);
    title.textContent = `${box.box_id} · ${box.location} · ${kits} samples`;
    g.addEventListener('mouseenter', () => setReadout(box));
    g.addEventListener('focus', () => setReadout(box));
    g.addEventListener('mouseleave', () => setReadout(null));
    g.addEventListener('blur', () => setReadout(null));
  });

  renderRegionPanel(all, regions);
  if (!document.querySelector('#map-readout strong')) setReadout(null);
}

function renderRegionPanel(all, regions) {
  const list = document.getElementById('region-list');
  if (!list) return;
  const max = Math.max(1, ...regions.map(r => r.kits));
  list.replaceChildren(...regions.map(r => {
    const li = document.createElement('li');
    li.className = r.low ? 'region-row is-low' : 'region-row';
    const head = document.createElement('div');
    head.className = 'region-head';
    const name = document.createElement('span');
    name.textContent = r.region;
    const value = document.createElement('strong');
    value.textContent = r.kits;
    head.append(name, value);
    if (r.low) {
      const chip = document.createElement('em');
      chip.textContent = 'low';
      name.appendChild(chip);
    }
    const bar = document.createElement('div');
    bar.className = 'region-bar';
    const fillEl = document.createElement('i');
    fillEl.style.width = `${Math.max(4, (r.kits / max) * 100)}%`;
    bar.appendChild(fillEl);
    li.append(head, bar);
    return li;
  }));

  const total = all.reduce((t, b) => t + (typeof b.kits === 'number' ? b.kits : 0), 0);
  document.getElementById('net-boxes').textContent = all.length;
  document.getElementById('net-samples').textContent = total;
  document.getElementById('net-low').textContent = regions.filter(r => r.low).length;
}
