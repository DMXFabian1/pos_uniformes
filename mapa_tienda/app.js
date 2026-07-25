'use strict';

/* ================== Catálogo de piezas ================== */
const CATALOG = {
  gondola:   { nombre: 'Góndola',   color: '#4F46E5', serie: 'letra',   niveles: 4 },
  rack:      { nombre: 'Rack',      color: '#0D9488', serie: 'numero',  niveles: 2 },
  tubular:   { nombre: 'Tubular',   color: '#64748B', serie: 'numero',  niveles: 3, continuo: true },
  cascada:   { nombre: 'Cascada',   color: '#C026D3', serie: 'numero',  niveles: 5 },
  estanteria:{ nombre: 'Estantería', color: '#15803D', serie: 'numero', niveles: 4 },
  vitrina:   { nombre: 'Vitrina',   color: '#DB2777', serie: 'numero',  niveles: 3 },
  mostrador: { nombre: 'Mostrador', color: '#F97316', serie: 'numero',  niveles: 1 },
  mesa:      { nombre: 'Mesa',      color: '#CA8A04', serie: 'numero',  niveles: 1 },
  probador:  { nombre: 'Probador',  color: '#7C3AED', serie: 'numero',  niveles: 0 },
  caja:      { nombre: 'Caja',      color: '#A16207', serie: 'numero',  niveles: 1 },
  escalera:  { nombre: 'Escalera',  color: '#0891B2', serie: 'numero',  niveles: 0 },
  columna:   { nombre: 'Columna',   color: '#57534E', serie: 'ninguna', niveles: 0 },
};
const MAX_NIVELES = 10;
const MAX_COLUMNAS = 15;
const MAX_PISOS = 4;
const SECTOR_COLORS = ['#D97706', '#059669', '#2563EB', '#DB2777', '#7C3AED', '#DC2626', '#0D9488', '#65A30D'];
const MUEBLES = ['gondola', 'rack', 'tubular', 'cascada', 'estanteria', 'vitrina', 'mostrador', 'mesa', 'probador', 'caja', 'escalera'];
const STORAGE_KEY = 'mapa_tienda_v1';
const BASE_CELL = 34;

/* ================== Estado ================== */
let state = nuevoEstado();
let tool = 'select';
let zoom = 1;
let selectedId = null;
let selectedSector = null;
let multiSel = []; // ids marcados con Shift+clic para unificar
let marcoSel = null; // {rect, pieceIds, walls, doors, sectorIds} del marco de selección
let clipboard = null; // pieza copiada con Ctrl+C
let undoStack = [];

function nuevoEstado() {
  return {
    version: 2,
    cols: 24,
    rows: 16,
    seq: {},        // contador por tipo para nombres (global, no se repiten entre pisos)
    pisoActivo: 0,
    pisos: [nuevoPiso('Planta baja')],
  };
}

function nuevoPiso(nombre) {
  return {
    nombre,
    walls: [],    // ["x,y", ...]
    doors: [],
    pieces: [],   // {id, tipo, label, niveles, columnas, x, y, w, h}
    sectores: [], // {id, nombre, color, x, y, w, h}
  };
}

function nuevoId() {
  return 'p' + Date.now() + Math.floor(Math.random() * 999);
}

function piso() {
  return state.pisos[state.pisoActivo] || state.pisos[0];
}

/* ================== Referencias DOM ================== */
const $ = (id) => document.getElementById(id);
const stage = $('stage');
const gridBg = $('gridBg');
const layerCells = $('layerCells');
const layerPieces = $('layerPieces');
const layerPreview = $('layerPreview');

/* ================== Utilidades ================== */
const cellPx = () => Math.round(BASE_CELL * zoom);
const key = (x, y) => `${x},${y}`;

function wallSet() { return new Set(piso().walls); }
function doorSet() { return new Set(piso().doors); }

// una pieza unificada (forma libre, ej. escalera en L) guarda sus rectángulos en `partes`
function rectsDe(p) {
  return p.partes || [{ x: p.x, y: p.y, w: p.w, h: p.h }];
}

function pieceAt(x, y) {
  return piso().pieces.find(p =>
    rectsDe(p).some(r => x >= r.x && x < r.x + r.w && y >= r.y && y < r.y + r.h)
  ) || null;
}

function rectLibre(x, y, w, h, ignoreId = null) {
  if (x < 0 || y < 0 || x + w > state.cols || y + h > state.rows) return false;
  const walls = wallSet(), doors = doorSet();
  for (let i = x; i < x + w; i++) {
    for (let j = y; j < y + h; j++) {
      if (walls.has(key(i, j)) || doors.has(key(i, j))) return false;
    }
  }
  return !piso().pieces.some(p =>
    p.id !== ignoreId &&
    rectsDe(p).some(r =>
      x < r.x + r.w && x + w > r.x &&
      y < r.y + r.h && y + h > r.y
    )
  );
}

function puedeMover(p, dx, dy) {
  return rectsDe(p).every(r => rectLibre(r.x + dx, r.y + dy, r.w, r.h, p.id));
}

// re-arma un conjunto de celdas en rectángulos (para recortar piezas con el borrador)
function rectsDesdeCeldas(celdas) {
  const set = new Set(celdas);
  const rects = [];
  while (set.size) {
    let base = null;
    for (const k of set) {
      const [x, y] = k.split(',').map(Number);
      if (!base || y < base.y || (y === base.y && x < base.x)) base = { x, y };
    }
    let w = 1;
    while (set.has(key(base.x + w, base.y))) w++;
    let h = 1;
    bajando: while (true) {
      for (let i = 0; i < w; i++) {
        if (!set.has(key(base.x + i, base.y + h))) break bajando;
      }
      h++;
    }
    for (let i = 0; i < w; i++) {
      for (let j = 0; j < h; j++) set.delete(key(base.x + i, base.y + j));
    }
    rects.push({ x: base.x, y: base.y, w, h });
  }
  return rects;
}

function quitarCeldaDePieza(p, x, y) {
  const celdas = new Set();
  for (const r of rectsDe(p)) {
    for (let i = r.x; i < r.x + r.w; i++) {
      for (let j = r.y; j < r.y + r.h; j++) celdas.add(key(i, j));
    }
  }
  celdas.delete(key(x, y));
  if (!celdas.size) {
    piso().pieces = piso().pieces.filter(q => q.id !== p.id);
    if (selectedId === p.id) selectedId = null;
    return;
  }
  const rects = rectsDesdeCeldas(celdas);
  p.x = rects[0].x; p.y = rects[0].y;
  p.w = rects[0].w; p.h = rects[0].h;
  if (rects.length > 1) p.partes = rects;
  else delete p.partes;
}

function siguienteNombre(tipo) {
  const cat = CATALOG[tipo];
  const n = (state.seq[tipo] || 0) + 1;
  state.seq[tipo] = n;
  if (cat.serie === 'letra') {
    let s = '', v = n;
    while (v > 0) { v--; s = String.fromCharCode(65 + (v % 26)) + s; v = Math.floor(v / 26); }
    return `${cat.nombre} ${s}`;
  }
  if (cat.serie === 'numero') return `${cat.nombre} ${n}`;
  return cat.nombre;
}

let toastTimer = null;
function toast(msg) {
  const el = $('toast');
  el.textContent = msg;
  el.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.hidden = true; }, 2200);
}

/* ================== Persistencia ================== */
function guardar() {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(state)); } catch (_) {}
}

function cargar() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return;
    const data = JSON.parse(raw);
    if (data && typeof data.cols === 'number' && (Array.isArray(data.pieces) || Array.isArray(data.pisos))) {
      state = Object.assign(nuevoEstado(), data);
      migrar();
    }
  } catch (_) {}
}

function migrar() {
  // v1 → v2: un solo plano suelto pasa a ser la Planta baja.
  // Ojo: nuevoEstado() ya trae un pisos default, así que la señal de formato
  // viejo es que existan los arreglos en la raíz, no que falte pisos.
  if (Array.isArray(state.pieces) || Array.isArray(state.walls) ||
      !Array.isArray(state.pisos) || !state.pisos.length) {
    state.pisos = [{
      nombre: 'Planta baja',
      walls: state.walls || [],
      doors: state.doors || [],
      pieces: state.pieces || [],
    }];
  }
  delete state.walls; delete state.doors; delete state.pieces;
  state.version = 2;
  if (typeof state.pisoActivo !== 'number' || state.pisoActivo >= state.pisos.length) state.pisoActivo = 0;
  for (const f of state.pisos) {
    if (!Array.isArray(f.sectores)) f.sectores = [];
    for (const p of f.pieces) {
      if (typeof p.niveles !== 'number') p.niveles = CATALOG[p.tipo]?.niveles ?? 0;
      if (typeof p.columnas !== 'number') p.columnas = p.niveles ? Math.max(p.w, p.h) : 0;
      if (CATALOG[p.tipo]?.continuo && p.niveles) {
        // cortes: por nivel, posiciones (fracción 0-1) de cada separación del tubo
        if (!Array.isArray(p.cortes)) {
          const esp = Array.isArray(p.espacios) ? p.espacios : [];
          p.cortes = Array.from({ length: p.niveles }, (_, i) => {
            const n = esp[i] || 1;
            return Array.from({ length: n - 1 }, (_, j) => Math.round(((j + 1) / n) * 100) / 100);
          });
        }
        if (p.cortes.length !== p.niveles) {
          p.cortes = Array.from({ length: p.niveles }, (_, i) => p.cortes[i] || []);
        }
        delete p.espacios;
      }
    }
  }
}

function snapshot() {
  undoStack.push(JSON.stringify(state));
  if (undoStack.length > 60) undoStack.shift();
}

function undo() {
  if (!undoStack.length) { toast('Nada que deshacer'); return; }
  state = JSON.parse(undoStack.pop());
  if (state.pisoActivo >= state.pisos.length) state.pisoActivo = 0;
  if (selectedId && !piso().pieces.some(p => p.id === selectedId)) selectedId = null;
  if (selectedSector && !(piso().sectores || []).some(s => s.id === selectedSector)) selectedSector = null;
  multiSel = [];
  marcoSel = null;
  guardar();
  renderAll();
}

/* ================== Render ================== */
function renderAll() {
  const c = cellPx();
  stage.style.setProperty('--cell', c + 'px');
  stage.style.width = (state.cols * c) + 'px';
  stage.style.height = (state.rows * c) + 'px';

  // sectores (zonas de fondo)
  const layerSectores = $('layerSectores');
  layerSectores.innerHTML = '';
  for (const s of piso().sectores) {
    const d = document.createElement('div');
    d.className = 'sector' + (s.id === selectedSector ? ' selected' : '');
    d.style.setProperty('--sc', s.color);
    d.style.left = (s.x * c) + 'px';
    d.style.top = (s.y * c) + 'px';
    d.style.width = (s.w * c) + 'px';
    d.style.height = (s.h * c) + 'px';
    const tag = document.createElement('span');
    tag.className = 'sector-tag';
    tag.textContent = s.nombre;
    d.appendChild(tag);
    if (s.id === selectedSector) agregarTiradores(d, 'sector');
    layerSectores.appendChild(d);
  }

  // celdas estructurales
  layerCells.innerHTML = '';
  const frag = document.createDocumentFragment();
  for (const [lista, clase] of [[piso().walls, 'pared'], [piso().doors, 'puerta']]) {
    for (const k of lista) {
      const [x, y] = k.split(',').map(Number);
      const d = document.createElement('div');
      d.className = 'cell ' + clase;
      d.style.left = (x * c) + 'px';
      d.style.top = (y * c) + 'px';
      frag.appendChild(d);
    }
  }
  layerCells.appendChild(frag);

  // piezas: se dibujan celda por celda para que las unificadas se vean
  // como UNA sola figura (borde solo en los lados expuestos)
  layerPieces.innerHTML = '';
  for (const p of piso().pieces) {
    const marcada = p.id === selectedId || multiSel.includes(p.id);
    const rects = rectsDe(p);
    const celdas = new Set();
    for (const r of rects) {
      for (let i = r.x; i < r.x + r.w; i++) {
        for (let j = r.y; j < r.y + r.h; j++) celdas.add(key(i, j));
      }
    }
    const minX = Math.min(...rects.map(r => r.x));
    const minY = Math.min(...rects.map(r => r.y));
    const maxX = Math.max(...rects.map(r => r.x + r.w));
    const maxY = Math.max(...rects.map(r => r.y + r.h));

    const g = document.createElement('div');
    g.className = 'piece' + (marcada ? ' selected' : '');
    g.dataset.id = p.id;
    g.style.setProperty('--pc', CATALOG[p.tipo].color);
    g.style.left = (minX * c) + 'px';
    g.style.top = (minY * c) + 'px';
    g.style.width = ((maxX - minX) * c) + 'px';
    g.style.height = ((maxY - minY) * c) + 'px';

    for (const k of celdas) {
      const [i, j] = k.split(',').map(Number);
      const d = document.createElement('div');
      d.className = 'pcell';
      d.style.left = ((i - minX) * c) + 'px';
      d.style.top = ((j - minY) * c) + 'px';
      d.style.width = c + 'px';
      d.style.height = c + 'px';
      const arr = !celdas.has(key(i, j - 1));
      const aba = !celdas.has(key(i, j + 1));
      const izq = !celdas.has(key(i - 1, j));
      const der = !celdas.has(key(i + 1, j));
      d.style.borderWidth = `${arr ? 2 : 0}px ${der ? 2 : 0}px ${aba ? 2 : 0}px ${izq ? 2 : 0}px`;
      d.style.borderRadius =
        `${arr && izq ? 8 : 0}px ${arr && der ? 8 : 0}px ${aba && der ? 8 : 0}px ${aba && izq ? 8 : 0}px`;
      if (aba) d.classList.add('fondo');
      g.appendChild(d);
    }

    const r0 = rects[0];
    if (!(r0.w * c < 46 && r0.h * c < 46)) {
      const lbl = document.createElement('span');
      lbl.className = 'plabel';
      if (r0.h > r0.w && r0.w * c < 60) lbl.classList.add('vertical');
      lbl.textContent = p.label;
      lbl.style.left = ((r0.x - minX) * c + (r0.w * c) / 2) + 'px';
      lbl.style.top = ((r0.y - minY) * c + (r0.h * c) / 2) + 'px';
      g.appendChild(lbl);
    }
    if (p.id === selectedId && !p.partes && multiSel.length < 2) agregarTiradores(g, 'pieza');
    layerPieces.appendChild(g);
  }

  // marco de selección persistente
  layerPreview.innerHTML = '';
  if (marcoSel) {
    const d = document.createElement('div');
    d.className = 'marco-rect';
    d.style.left = (marcoSel.rect.x * c) + 'px';
    d.style.top = (marcoSel.rect.y * c) + 'px';
    d.style.width = (marcoSel.rect.w * c) + 'px';
    d.style.height = (marcoSel.rect.h * c) + 'px';
    layerPreview.appendChild(d);
  }

  renderPisos();
  renderCounts();
  renderSelInfo();
  $('zoomLabel').textContent = Math.round(zoom * 100) + '%';
  $('inpCols').value = state.cols;
  $('inpRows').value = state.rows;
}

function renderPisos() {
  const cont = $('pisoTabs');
  cont.innerHTML = '';
  state.pisos.forEach((f, i) => {
    const b = document.createElement('button');
    b.className = 'piso-tab' + (i === state.pisoActivo ? ' active' : '');
    b.textContent = f.nombre;
    b.addEventListener('click', () => {
      if (i === state.pisoActivo) return;
      state.pisoActivo = i;
      selectedId = null;
      selectedSector = null;
      multiSel = [];
      marcoSel = null;
      guardar();
      renderAll();
    });
    cont.appendChild(b);
  });
  $('btnAddPiso').hidden = state.pisos.length >= MAX_PISOS;
  $('btnDelPiso').hidden = state.pisos.length <= 1;
}

function renderCounts() {
  const cont = $('counts');
  cont.innerHTML = '';
  for (const tipo of [...MUEBLES, 'columna']) {
    const n = piso().pieces.filter(p => p.tipo === tipo).length;
    if (!n) continue;
    const row = document.createElement('div');
    row.className = 'count-row';
    row.innerHTML = `<span class="dotname"><span class="dot" style="background:${CATALOG[tipo].color}"></span>${CATALOG[tipo].nombre}s</span><b>${n}</b>`;
    cont.appendChild(row);
  }
  if (!cont.children.length) cont.innerHTML = '<span style="color:var(--muted)">Aún no hay piezas</span>';
}

function renderSelInfo() {
  const box = $('selInfo');
  const ph = box.querySelector('.sel-placeholder');
  const det = box.querySelector('.sel-detail');
  const p = piso().pieces.find(q => q.id === selectedId);
  const s = piso().sectores.find(q => q.id === selectedSector);
  if (marcoSel) {
    ph.hidden = true; det.hidden = false;
    for (const id of ['btnRotate', 'btnDuplicar', 'btnRename', 'btnColorSector', 'btnNiveles', 'btnSeparar', 'selTipo']) $(id).hidden = true;
    $('btnCopiarSel').hidden = false;
    const piezas = marcoSel.pieceIds.map(id => piso().pieces.find(q => q.id === id)).filter(Boolean);
    $('btnUnificar').hidden = !(piezas.length > 1 && piezas.every(q => q.tipo === piezas[0].tipo));
    const estructura = marcoSel.walls.length + marcoSel.doors.length;
    $('selName').textContent = 'Área marcada';
    $('selSize').textContent = `${piezas.length} piezas · ${estructura} celdas de pared/puerta · Ctrl+V pega aquí o en otro piso`;
    return;
  }

  const varios = multiSel.length > 1;
  if (!p && !s && !varios) {
    ph.hidden = false; det.hidden = true;
    return;
  }
  ph.hidden = true; det.hidden = false;
  $('btnCopiarSel').hidden = true;

  const compuesta = p && p.partes && p.partes.length > 1;
  $('btnRotate').hidden = !p || compuesta;
  $('btnDuplicar').hidden = !p;
  $('selTipo').hidden = !p || varios;
  if (p) $('selTipo').value = p.tipo;
  $('btnRename').hidden = varios;
  $('btnColorSector').hidden = !s;
  $('btnUnificar').hidden = !varios;
  $('btnSeparar').hidden = !compuesta;
  $('btnNiveles').hidden = !(p && p.niveles);

  if (varios) {
    const piezas = multiSel.map(id => piso().pieces.find(q => q.id === id)).filter(Boolean);
    const mismoTipo = piezas.every(q => q.tipo === piezas[0].tipo);
    $('selName').textContent = `${piezas.length} piezas marcadas`;
    $('selSize').textContent = mismoTipo ? 'listas para unificar' : 'tipos distintos: no se pueden unificar';
    return;
  }
  if (p) {
    const celdas = rectsDe(p).reduce((n, r) => n + r.w * r.h, 0);
    $('selName').textContent = p.label;
    $('selSize').textContent = compuesta
      ? `forma libre · ${p.partes.length} partes · ${celdas} celdas · ${(celdas * 0.25).toFixed(1)} m²`
      : `${p.w} × ${p.h} celdas · ${(p.w * 0.5).toFixed(1)} × ${(p.h * 0.5).toFixed(1)} m`;
    if (p.niveles) {
      if (CATALOG[p.tipo].continuo) {
        const total = (Array.isArray(p.cortes) ? p.cortes : []).reduce((a, c) => a + c.length + 1, 0) || p.niveles;
        $('btnNiveles').textContent = total > p.niveles
          ? `Frente (${p.niveles} tubos · ${total} espacios)`
          : `Frente (${p.niveles} tubos)`;
      } else {
        $('btnNiveles').textContent = `Frente (${p.niveles} × ${p.columnas || Math.max(p.w, p.h)})`;
      }
    }
  } else {
    $('selName').textContent = `Zona: ${s.nombre}`;
    $('selSize').textContent = `${s.w} × ${s.h} celdas · ${(s.w * 0.5).toFixed(1)} × ${(s.h * 0.5).toFixed(1)} m`;
  }
}

function unificarSeleccion() {
  const piezas = multiSel.map(id => piso().pieces.find(q => q.id === id)).filter(Boolean);
  if (piezas.length < 2) return;
  if (!piezas.every(q => q.tipo === piezas[0].tipo)) {
    toast('Solo se pueden unificar piezas del mismo tipo');
    return;
  }
  snapshot();
  const base = piezas[0];
  base.partes = piezas.flatMap(q => rectsDe(q).map(r => ({ ...r })));
  base.x = base.partes[0].x; base.y = base.partes[0].y;
  base.w = base.partes[0].w; base.h = base.partes[0].h;
  const otros = new Set(multiSel.filter(id => id !== base.id));
  piso().pieces = piso().pieces.filter(q => !otros.has(q.id));
  multiSel = [];
  marcoSel = null;
  selectedId = base.id;
  guardar();
  renderAll();
  toast(`Unificadas como "${base.label}" — ahora cuenta como 1`);
}

function separarPieza() {
  const p = piso().pieces.find(q => q.id === selectedId);
  if (!p || !p.partes || p.partes.length < 2) return;
  snapshot();
  const rects = p.partes;
  delete p.partes;
  Object.assign(p, rects[0]);
  for (const r of rects.slice(1)) {
    piso().pieces.push({
      id: nuevoId(),
      tipo: p.tipo,
      label: siguienteNombre(p.tipo),
      niveles: p.niveles,
      columnas: p.columnas,
      ...r,
    });
  }
  guardar();
  renderAll();
  toast('Separada en piezas individuales');
}

function sectorEn(x, y) {
  const lista = piso().sectores;
  for (let i = lista.length - 1; i >= 0; i--) {
    const s = lista[i];
    if (x >= s.x && x < s.x + s.w && y >= s.y && y < s.y + s.h) return s;
  }
  return null;
}

/* ================== Vista frontal (niveles) ================== */
let nivelesId = null;

function abrirNiveles(id) {
  const p = piso().pieces.find(q => q.id === id);
  if (!p || !p.niveles) return;
  nivelesId = id;
  renderNiveles();
  $('modalNiveles').hidden = false;
}

function cerrarNiveles() {
  nivelesId = null;
  $('modalNiveles').hidden = true;
}

function renderNiveles() {
  const p = piso().pieces.find(q => q.id === nivelesId);
  if (!p) { cerrarNiveles(); return; }
  const continuo = !!CATALOG[p.tipo].continuo;
  if (continuo && (!Array.isArray(p.cortes) || p.cortes.length !== p.niveles)) {
    const base = Array.isArray(p.cortes) ? p.cortes : [];
    p.cortes = Array.from({ length: p.niveles }, (_, i) => base[i] || []);
  }
  $('mnTitle').textContent = `${p.label} · de frente`;
  $('mnCount').textContent = p.niveles;
  $('ctrlColumnas').hidden = continuo;
  if (!continuo) $('mcCount').textContent = p.columnas || Math.max(p.w, p.h);
  const cont = $('mnFrente');
  cont.innerHTML = '';
  cont.style.setProperty('--pc', CATALOG[p.tipo].color);
  const largo = Math.max(p.w, p.h);
  for (let n = 1; n <= p.niveles; n++) {
    const nivel = document.createElement('div');
    nivel.className = 'nivel';
    const tag = document.createElement('span');
    tag.className = 'nivel-tag';
    tag.textContent = `Nivel ${n}`;
    nivel.appendChild(tag);
    const fila = document.createElement('div');
    fila.className = 'nivel-fila';
    if (continuo) {
      const ctrl = document.createElement('span');
      ctrl.className = 'nivel-ctrl';
      const menos = document.createElement('button');
      menos.className = 'mini-btn';
      menos.textContent = '−';
      menos.title = 'Quitar la última separación de este tubo';
      menos.addEventListener('click', () => cambiarSeparacion(n - 1, -1));
      const info = document.createElement('span');
      info.textContent = `${p.cortes[n - 1].length} sep`;
      const mas = document.createElement('button');
      mas.className = 'mini-btn';
      mas.textContent = '+';
      mas.title = 'Agregar separación a este tubo (luego arrástrala)';
      mas.addEventListener('click', () => cambiarSeparacion(n - 1, 1));
      ctrl.append(menos, info, mas);
      nivel.appendChild(ctrl);
      construirTubo(fila, p, n - 1, largo);
    } else {
      const secciones = p.columnas || Math.max(p.w, p.h);
      for (let s = 0; s < secciones; s++) {
        const hueco = document.createElement('div');
        hueco.className = 'hueco';
        fila.appendChild(hueco);
      }
    }
    nivel.appendChild(fila);
    cont.appendChild(nivel);
  }
}

const SEP_PX = 10;

function construirTubo(fila, p, idx, largo) {
  fila.innerHTML = '';
  const cortes = p.cortes[idx];
  const fr = [0, ...cortes, 1];
  const totalPx = largo * 70 - cortes.length * SEP_PX;
  for (let i = 0; i < fr.length - 1; i++) {
    const seg = document.createElement('div');
    seg.className = 'hueco barra';
    seg.style.width = Math.max(30, Math.round((fr[i + 1] - fr[i]) * totalPx)) + 'px';
    const cm = document.createElement('span');
    cm.className = 'seg-cm';
    cm.textContent = Math.round((fr[i + 1] - fr[i]) * largo * 50) + ' cm';
    seg.appendChild(cm);
    fila.appendChild(seg);
    if (i < fr.length - 2) {
      const sep = document.createElement('div');
      sep.className = 'separador';
      sep.title = 'Arrastra para ajustar el largo de cada espacio';
      instalarArrastreSeparador(sep, p, idx, i, largo);
      fila.appendChild(sep);
    }
  }
}

function actualizarTubo(fila, p, idx, largo) {
  const cortes = p.cortes[idx];
  const fr = [0, ...cortes, 1];
  const totalPx = largo * 70 - cortes.length * SEP_PX;
  fila.querySelectorAll('.hueco.barra').forEach((seg, i) => {
    seg.style.width = Math.max(30, Math.round((fr[i + 1] - fr[i]) * totalPx)) + 'px';
    const cm = seg.querySelector('.seg-cm');
    if (cm) cm.textContent = Math.round((fr[i + 1] - fr[i]) * largo * 50) + ' cm';
  });
}

function instalarArrastreSeparador(sep, p, idx, k, largo) {
  sep.addEventListener('pointerdown', (e) => {
    e.preventDefault();
    e.stopPropagation();
    const fila = sep.parentElement;
    const rect = fila.getBoundingClientRect();
    let cambio = false;
    const mover = (ev) => {
      const cortes = p.cortes[idx];
      const prev = k > 0 ? cortes[k - 1] : 0;
      const next = k < cortes.length - 1 ? cortes[k + 1] : 1;
      let f = Math.round(((ev.clientX - rect.left) / rect.width) * 20) / 20; // pasos de 5%
      f = Math.max(prev + 0.05, Math.min(next - 0.05, f));
      if (f !== cortes[k]) {
        if (!cambio) { snapshot(); cambio = true; }
        cortes[k] = f;
        actualizarTubo(fila, p, idx, largo);
      }
    };
    const soltar = () => {
      window.removeEventListener('pointermove', mover);
      window.removeEventListener('pointerup', soltar);
      if (cambio) guardar();
    };
    window.addEventListener('pointermove', mover);
    window.addEventListener('pointerup', soltar);
  });
}

function cambiarSeparacion(idx, delta) {
  const p = piso().pieces.find(q => q.id === nivelesId);
  if (!p) return;
  if (!Array.isArray(p.cortes)) p.cortes = Array.from({ length: p.niveles }, () => []);
  const c = p.cortes[idx] || (p.cortes[idx] = []);
  if (delta > 0) {
    // parte a la mitad el espacio más grande de este tubo
    const fr = [0, ...c, 1];
    let mejorIdx = 0, mejorLargo = 0;
    for (let i = 0; i < fr.length - 1; i++) {
      const len = fr[i + 1] - fr[i];
      if (len > mejorLargo) { mejorLargo = len; mejorIdx = i; }
    }
    if (mejorLargo < 0.12) { toast('Ya no cabe otra separación en este tubo'); return; }
    snapshot();
    c.push(Math.round(((fr[mejorIdx] + fr[mejorIdx + 1]) / 2) * 20) / 20);
    c.sort((a, b) => a - b);
  } else {
    if (!c.length) return;
    snapshot();
    c.pop();
  }
  guardar();
  renderNiveles();
  renderSelInfo();
}

function cambiarNiveles(delta) {
  const p = piso().pieces.find(q => q.id === nivelesId);
  if (!p) return;
  const n = p.niveles + delta;
  if (n < 1 || n > MAX_NIVELES) return;
  snapshot();
  p.niveles = n;
  if (CATALOG[p.tipo].continuo) {
    const base = Array.isArray(p.cortes) ? p.cortes : [];
    p.cortes = Array.from({ length: n }, (_, i) => base[i] || []);
  }
  guardar();
  renderNiveles();
  renderSelInfo();
}

function cambiarColumnas(delta) {
  const p = piso().pieces.find(q => q.id === nivelesId);
  if (!p) return;
  const n = (p.columnas || Math.max(p.w, p.h)) + delta;
  if (n < 1 || n > MAX_COLUMNAS) return;
  snapshot();
  p.columnas = n;
  guardar();
  renderNiveles();
  renderSelInfo();
}

function agregarTiradores(cont, objetivo) {
  for (const esquina of ['nw', 'ne', 'sw', 'se']) {
    const h = document.createElement('div');
    h.className = 'handle ' + esquina;
    h.dataset.corner = esquina;
    h.dataset.target = objetivo;
    cont.appendChild(h);
  }
}

function renderPreview(rect, valida) {
  layerPreview.innerHTML = '';
  if (!rect) return;
  const c = cellPx();
  for (const r of Array.isArray(rect) ? rect : [rect]) {
    const d = document.createElement('div');
    d.className = 'preview-rect' + (valida ? '' : ' invalid');
    d.style.left = (r.x * c) + 'px';
    d.style.top = (r.y * c) + 'px';
    d.style.width = (r.w * c) + 'px';
    d.style.height = (r.h * c) + 'px';
    layerPreview.appendChild(d);
  }
}

/* ================== Interacción con el lienzo ================== */
let drag = null; // {tipo: 'draw'|'paint'|'move', ...}
let ultimoClick = { id: null, t: 0 };

function celdaDesdeEvento(e) {
  const r = stage.getBoundingClientRect();
  const c = cellPx();
  return {
    x: Math.max(0, Math.min(state.cols - 1, Math.floor((e.clientX - r.left) / c))),
    y: Math.max(0, Math.min(state.rows - 1, Math.floor((e.clientY - r.top) / c))),
  };
}

stage.addEventListener('pointerdown', (e) => {
  if (e.button !== 0) return;
  stage.setPointerCapture(e.pointerId);
  const cel = celdaDesdeEvento(e);

  if (tool === 'select') {
    const handleEl = e.target.closest('.handle');
    if (handleEl) {
      const esPieza = handleEl.dataset.target === 'pieza';
      const obj = esPieza
        ? piso().pieces.find(q => q.id === selectedId)
        : piso().sectores.find(q => q.id === selectedSector);
      if (obj) {
        drag = {
          tipo: esPieza ? 'resize' : 'resizesec',
          esquina: handleEl.dataset.corner,
          base: { x: obj.x, y: obj.y, w: obj.w, h: obj.h },
          dest: null,
        };
      }
      return;
    }
    const pieceEl = e.target.closest('.piece');
    if (pieceEl && e.shiftKey) {
      // Shift+clic: marcar/desmarcar para unificar
      const id = pieceEl.dataset.id;
      if (!multiSel.length && selectedId && selectedId !== id) multiSel = [selectedId];
      if (multiSel.includes(id)) multiSel = multiSel.filter(x => x !== id);
      else multiSel.push(id);
      selectedId = multiSel.length === 1 ? multiSel[0] : null;
      if (multiSel.length === 1) multiSel = [];
      selectedSector = null;
      renderAll();
      return;
    }
    if (pieceEl) {
      multiSel = [];
      const id = pieceEl.dataset.id;
      // doble clic manual: el re-render rompe el dblclick nativo
      const ahora = performance.now();
      if (ultimoClick.id === id && ahora - ultimoClick.t < 400) {
        ultimoClick = { id: null, t: 0 };
        drag = null;
        abrirNiveles(id);
        return;
      }
      ultimoClick = { id, t: ahora };
      selectedId = id;
      selectedSector = null;
      const p = piso().pieces.find(q => q.id === selectedId);
      drag = { tipo: 'move', offx: cel.x - p.x, offy: cel.y - p.y, moved: false, dest: null };
    } else {
      const sec = sectorEn(cel.x, cel.y);
      selectedId = null;
      multiSel = [];
      ultimoClick = { id: null, t: 0 };
      if (sec) {
        selectedSector = sec.id;
        drag = { tipo: 'movesec', offx: cel.x - sec.x, offy: cel.y - sec.y, moved: false, dest: null };
      } else {
        selectedSector = null;
      }
    }
    renderAll();
    return;
  }

  if (tool === 'pared' || tool === 'puerta') {
    snapshot();
    drag = { tipo: 'paint', herramienta: tool, last: cel };
    pintarCelda(cel);
    return;
  }

  if (tool === 'columna') {
    snapshot();
    drag = { tipo: 'paint', herramienta: 'columna', last: cel };
    pintarCelda(cel);
    return;
  }

  if (tool === 'borrador') {
    snapshot();
    drag = { tipo: 'paint', herramienta: 'borrador', last: cel };
    pintarCelda(cel);
    return;
  }

  if (MUEBLES.includes(tool)) {
    drag = { tipo: 'draw', inicio: cel, fin: cel };
    const r = rectDesdeDrag();
    renderPreview(r, rectLibre(r.x, r.y, r.w, r.h));
    return;
  }

  if (tool === 'sector') {
    drag = { tipo: 'drawsec', inicio: cel, fin: cel };
    renderPreview(rectDesdeDrag(), true);
    return;
  }

  if (tool === 'marco') {
    marcoSel = null;
    multiSel = [];
    selectedId = null;
    selectedSector = null;
    drag = { tipo: 'marco', inicio: cel, fin: cel };
    renderPreview(rectDesdeDrag(), true);
  }
});

stage.addEventListener('pointermove', (e) => {
  if (!drag) return;
  const cel = celdaDesdeEvento(e);

  if (drag.tipo === 'draw') {
    drag.fin = cel;
    const r = rectDesdeDrag();
    renderPreview(r, rectLibre(r.x, r.y, r.w, r.h));
  } else if (drag.tipo === 'drawsec' || drag.tipo === 'marco') {
    drag.fin = cel;
    renderPreview(rectDesdeDrag(), true);
  } else if (drag.tipo === 'resize' || drag.tipo === 'resizesec') {
    const b = drag.base;
    const ax = drag.esquina.includes('w') ? b.x + b.w - 1 : b.x;
    const ay = drag.esquina.includes('n') ? b.y + b.h - 1 : b.y;
    const r = {
      x: Math.min(ax, cel.x),
      y: Math.min(ay, cel.y),
      w: Math.abs(cel.x - ax) + 1,
      h: Math.abs(cel.y - ay) + 1,
    };
    drag.dest = r;
    const valida = drag.tipo === 'resizesec' || rectLibre(r.x, r.y, r.w, r.h, selectedId);
    renderPreview(r, valida);
  } else if (drag.tipo === 'movesec') {
    const s = piso().sectores.find(q => q.id === selectedSector);
    if (!s) return;
    const nx = Math.max(0, Math.min(state.cols - s.w, cel.x - drag.offx));
    const ny = Math.max(0, Math.min(state.rows - s.h, cel.y - drag.offy));
    if (nx !== s.x || ny !== s.y || drag.moved) {
      drag.moved = true;
      drag.dest = { x: nx, y: ny };
      renderPreview({ x: nx, y: ny, w: s.w, h: s.h }, true);
    }
  } else if (drag.tipo === 'paint') {
    pintarLinea(drag.last || cel, cel);
    drag.last = cel;
  } else if (drag.tipo === 'move') {
    const p = piso().pieces.find(q => q.id === selectedId);
    if (!p) return;
    const rects = rectsDe(p);
    const minX = Math.min(...rects.map(r => r.x));
    const minY = Math.min(...rects.map(r => r.y));
    const maxX = Math.max(...rects.map(r => r.x + r.w));
    const maxY = Math.max(...rects.map(r => r.y + r.h));
    let dx = (cel.x - drag.offx) - p.x;
    let dy = (cel.y - drag.offy) - p.y;
    dx = Math.max(-minX, Math.min(state.cols - maxX, dx));
    dy = Math.max(-minY, Math.min(state.rows - maxY, dy));
    if (dx !== 0 || dy !== 0 || drag.moved) {
      drag.moved = true;
      drag.dest = { dx, dy };
      renderPreview(
        rects.map(r => ({ x: r.x + dx, y: r.y + dy, w: r.w, h: r.h })),
        puedeMover(p, dx, dy)
      );
    }
  }
});

stage.addEventListener('pointerup', () => {
  if (!drag) return;
  const d = drag;
  drag = null;
  renderPreview(null);

  if (d.tipo === 'draw') {
    const r = rectDesdeDrag(d);
    if (rectLibre(r.x, r.y, r.w, r.h)) {
      snapshot();
      piso().pieces.push({
        id: nuevoId(),
        tipo: tool,
        label: siguienteNombre(tool),
        niveles: CATALOG[tool].niveles,
        columnas: CATALOG[tool].niveles ? (CATALOG[tool].continuo ? 1 : Math.max(r.w, r.h)) : 0,
        ...(CATALOG[tool].continuo && CATALOG[tool].niveles
          ? { cortes: Array.from({ length: CATALOG[tool].niveles }, () => []) }
          : {}),
        ...r,
      });
      selectedId = piso().pieces[piso().pieces.length - 1].id;
      guardar();
      renderAll();
    } else {
      toast('Ahí no cabe: hay algo estorbando');
    }
  } else if (d.tipo === 'drawsec') {
    const r = rectDesdeDrag(d);
    const nombre = prompt('Nombre de la zona (ej. Secundaria, Preescolar, Bodega):');
    if (nombre && nombre.trim()) {
      snapshot();
      const s = {
        id: nuevoId(),
        nombre: nombre.trim(),
        color: SECTOR_COLORS[piso().sectores.length % SECTOR_COLORS.length],
        ...r,
      };
      piso().sectores.push(s);
      selectedSector = s.id;
      selectedId = null;
      guardar();
      renderAll();
    }
  } else if (d.tipo === 'marco') {
    const r = rectDesdeDrag(d);
    const toca = (q) => q.x < r.x + r.w && q.x + q.w > r.x && q.y < r.y + r.h && q.y + q.h > r.y;
    const dentro = (k) => {
      const [x, y] = k.split(',').map(Number);
      return x >= r.x && x < r.x + r.w && y >= r.y && y < r.y + r.h;
    };
    marcoSel = {
      rect: r,
      pieceIds: piso().pieces.filter(p => rectsDe(p).some(toca)).map(p => p.id),
      walls: piso().walls.filter(dentro),
      doors: piso().doors.filter(dentro),
      sectorIds: piso().sectores.filter(toca).map(s => s.id),
    };
    multiSel = [...marcoSel.pieceIds];
    renderAll();
  } else if (d.tipo === 'resize' && d.dest) {
    const p = piso().pieces.find(q => q.id === selectedId);
    const r = d.dest;
    if (p && rectLibre(r.x, r.y, r.w, r.h, p.id)) {
      snapshot();
      Object.assign(p, r);
      guardar();
      renderAll();
    } else {
      toast('Ahí no cabe ese tamaño');
      renderAll();
    }
  } else if (d.tipo === 'resizesec' && d.dest) {
    const s = piso().sectores.find(q => q.id === selectedSector);
    if (s) {
      snapshot();
      Object.assign(s, d.dest);
      guardar();
      renderAll();
    }
  } else if (d.tipo === 'movesec' && d.moved && d.dest) {
    const s = piso().sectores.find(q => q.id === selectedSector);
    if (s) {
      snapshot();
      s.x = d.dest.x; s.y = d.dest.y;
      guardar();
      renderAll();
    }
  } else if (d.tipo === 'move' && d.moved && d.dest) {
    const p = piso().pieces.find(q => q.id === selectedId);
    const { dx, dy } = d.dest;
    if (p && puedeMover(p, dx, dy)) {
      snapshot();
      if (p.partes) p.partes.forEach(r => { r.x += dx; r.y += dy; });
      p.x += dx; p.y += dy;
      guardar();
      renderAll();
    } else {
      toast('Ahí no cabe');
      renderAll();
    }
  } else if (d.tipo === 'paint') {
    guardar();
  }
});

function rectDesdeDrag(d = drag) {
  const x1 = Math.min(d.inicio.x, d.fin.x), x2 = Math.max(d.inicio.x, d.fin.x);
  const y1 = Math.min(d.inicio.y, d.fin.y), y2 = Math.max(d.inicio.y, d.fin.y);
  return { x: x1, y: y1, w: x2 - x1 + 1, h: y2 - y1 + 1 };
}

function pintarLinea(a, b) {
  const pasos = Math.max(Math.abs(b.x - a.x), Math.abs(b.y - a.y));
  for (let i = 1; i <= pasos; i++) {
    pintarCelda({
      x: Math.round(a.x + (b.x - a.x) * (i / pasos)),
      y: Math.round(a.y + (b.y - a.y) * (i / pasos)),
    });
  }
}

function pintarCelda(cel) {
  const k = key(cel.x, cel.y);
  const h = drag.herramienta;

  if (h === 'pared' || h === 'puerta') {
    if (pieceAt(cel.x, cel.y)) return;
    const walls = wallSet(), doors = doorSet();
    walls.delete(k); doors.delete(k);
    (h === 'pared' ? walls : doors).add(k);
    piso().walls = [...walls];
    piso().doors = [...doors];
    renderAll();
    return;
  }

  if (h === 'columna') {
    if (!rectLibre(cel.x, cel.y, 1, 1)) return;
    piso().pieces.push({
      id: nuevoId(),
      tipo: 'columna',
      label: CATALOG.columna.nombre,
      niveles: 0,
      columnas: 0,
      x: cel.x, y: cel.y, w: 1, h: 1,
    });
    renderAll();
    return;
  }

  if (h === 'borrador') {
    const walls = wallSet(), doors = doorSet();
    let cambio = walls.delete(k) || doors.delete(k);
    const p = pieceAt(cel.x, cel.y);
    if (p) {
      // solo la celda tocada; la pieza completa se elimina con Seleccionar + Eliminar
      quitarCeldaDePieza(p, cel.x, cel.y);
      cambio = true;
    }
    if (cambio) {
      piso().walls = [...walls];
      piso().doors = [...doors];
      renderAll();
    }
  }
}

/* ================== Acciones sobre la selección ================== */
function girarSeleccion() {
  const p = piso().pieces.find(q => q.id === selectedId);
  if (!p) return;
  if (p.partes && p.partes.length > 1) { toast('Las piezas unificadas no se giran; sepárala primero'); return; }
  if (p.w === p.h) { toast('Es cuadrada, se ve igual girada'); return; }
  const nx = Math.min(p.x, state.cols - p.h);
  const ny = Math.min(p.y, state.rows - p.w);
  if (rectLibre(nx, ny, p.h, p.w, p.id)) {
    snapshot();
    [p.w, p.h] = [p.h, p.w];
    p.x = nx; p.y = ny;
    guardar();
    renderAll();
  } else {
    toast('No hay espacio para girarla ahí');
  }
}

function eliminarSeleccion() {
  if (marcoSel) {
    snapshot();
    const ids = new Set(marcoSel.pieceIds);
    const w = new Set(marcoSel.walls), dr = new Set(marcoSel.doors);
    piso().pieces = piso().pieces.filter(q => !ids.has(q.id));
    piso().walls = piso().walls.filter(k => !w.has(k));
    piso().doors = piso().doors.filter(k => !dr.has(k));
    marcoSel = null;
    multiSel = [];
    selectedId = null;
    guardar();
    renderAll();
    return;
  }
  if (multiSel.length > 1) {
    snapshot();
    const ids = new Set(multiSel);
    piso().pieces = piso().pieces.filter(q => !ids.has(q.id));
    multiSel = [];
    selectedId = null;
    guardar();
    renderAll();
    return;
  }
  if (selectedId) {
    snapshot();
    piso().pieces = piso().pieces.filter(q => q.id !== selectedId);
    selectedId = null;
  } else if (selectedSector) {
    snapshot();
    piso().sectores = piso().sectores.filter(q => q.id !== selectedSector);
    selectedSector = null;
  } else {
    return;
  }
  guardar();
  renderAll();
}

function renombrarSeleccion() {
  const p = piso().pieces.find(q => q.id === selectedId);
  const s = piso().sectores.find(q => q.id === selectedSector);
  const obj = p || s;
  if (!obj) return;
  const actual = p ? p.label : s.nombre;
  const nuevo = prompt('Nuevo nombre:', actual);
  if (nuevo && nuevo.trim()) {
    snapshot();
    if (p) p.label = nuevo.trim(); else s.nombre = nuevo.trim();
    guardar();
    renderAll();
  }
}

function cambiarTipo(nuevoTipo) {
  const p = piso().pieces.find(q => q.id === selectedId);
  if (!p || p.tipo === nuevoTipo || !CATALOG[nuevoTipo]) return;
  snapshot();
  const nombreAuto = p.label.startsWith(CATALOG[p.tipo].nombre);
  p.tipo = nuevoTipo;
  if (nombreAuto) p.label = siguienteNombre(nuevoTipo);
  const cat = CATALOG[nuevoTipo];
  if (!cat.niveles) {
    p.niveles = 0;
    p.columnas = 0;
  } else if (!p.niveles) {
    p.niveles = cat.niveles;
    p.columnas = Math.max(p.w, p.h);
  }
  if (cat.continuo && p.niveles) {
    p.columnas = 1;
    p.cortes = Array.from({ length: p.niveles }, (_, i) => (Array.isArray(p.cortes) && p.cortes[i]) || []);
  } else if (!cat.continuo) {
    delete p.cortes;
    delete p.espacios;
    if (p.niveles && (!p.columnas || p.columnas < 2)) p.columnas = Math.max(p.w, p.h);
  }
  guardar();
  renderAll();
  toast(`Ahora es ${p.label}`);
}

function cambiarColorSector() {
  const s = piso().sectores.find(q => q.id === selectedSector);
  if (!s) return;
  snapshot();
  const i = SECTOR_COLORS.indexOf(s.color);
  s.color = SECTOR_COLORS[(i + 1) % SECTOR_COLORS.length];
  guardar();
  renderAll();
}

function copiarPieza() {
  const p = piso().pieces.find(q => q.id === selectedId);
  if (!p) return;
  clipboard = JSON.parse(JSON.stringify(p));
  toast(`Copiado: ${p.label} — pégalo con Ctrl+V (aquí o en otro piso)`);
}

function copiarMarco() {
  if (!marcoSel) return;
  const ids = new Set(marcoSel.pieceIds);
  const sids = new Set(marcoSel.sectorIds);
  clipboard = JSON.parse(JSON.stringify({
    tipoClip: 'area',
    rect: marcoSel.rect,
    walls: marcoSel.walls,
    doors: marcoSel.doors,
    pieces: piso().pieces.filter(p => ids.has(p.id)),
    sectores: piso().sectores.filter(s => sids.has(s.id)),
  }));
  toast(`Área copiada (${clipboard.pieces.length} piezas) — cambia de piso si quieres y Ctrl+V`);
}

function pegarMarco() {
  snapshot();
  const walls = wallSet(), doors = doorSet();
  for (const k of clipboard.walls) {
    const [x, y] = k.split(',').map(Number);
    if (!pieceAt(x, y) && !doors.has(k)) walls.add(k);
  }
  piso().walls = [...walls];
  for (const k of clipboard.doors) {
    const [x, y] = k.split(',').map(Number);
    if (!pieceAt(x, y) && !wallSet().has(k)) doors.add(k);
  }
  piso().doors = [...doors];

  let pegadas = 0, saltadas = 0;
  for (const pc of clipboard.pieces) {
    const rects = pc.partes || [{ x: pc.x, y: pc.y, w: pc.w, h: pc.h }];
    if (rects.every(r => rectLibre(r.x, r.y, r.w, r.h))) {
      const nueva = JSON.parse(JSON.stringify(pc));
      nueva.id = nuevoId();
      nueva.label = pc.tipo === 'columna' ? pc.label : siguienteNombre(pc.tipo);
      piso().pieces.push(nueva);
      pegadas++;
    } else {
      saltadas++;
    }
  }
  for (const sc of clipboard.sectores) {
    const nuevo = JSON.parse(JSON.stringify(sc));
    nuevo.id = nuevoId();
    piso().sectores.push(nuevo);
  }
  guardar();
  renderAll();
  toast(`Pegado: ${pegadas} piezas y la estructura del área${saltadas ? ` · ${saltadas} no cupieron` : ''}`);
}

function pegarPieza() {
  if (!clipboard) { toast('No hay nada copiado'); return; }
  const rects = clipboard.partes
    ? clipboard.partes.map(r => ({ ...r }))
    : [{ x: clipboard.x, y: clipboard.y, w: clipboard.w, h: clipboard.h }];
  const minX = Math.min(...rects.map(r => r.x));
  const minY = Math.min(...rects.map(r => r.y));
  const bw = Math.max(...rects.map(r => r.x + r.w)) - minX;
  const bh = Math.max(...rects.map(r => r.y + r.h)) - minY;
  const libre = (dx, dy) => rects.every(r => rectLibre(r.x + dx, r.y + dy, r.w, r.h));
  // primero cerca del original, luego donde haya lugar
  let delta = null;
  if (libre(1, 1)) delta = { dx: 1, dy: 1 };
  else if (libre(0, 0)) delta = { dx: 0, dy: 0 };
  else {
    for (let y = 0; y <= state.rows - bh && !delta; y++) {
      for (let x = 0; x <= state.cols - bw; x++) {
        const dx = x - minX, dy = y - minY;
        if (libre(dx, dy)) { delta = { dx, dy }; break; }
      }
    }
  }
  if (!delta) { toast('No hay espacio libre para pegar aquí'); return; }
  snapshot();
  const movidos = rects.map(r => ({ x: r.x + delta.dx, y: r.y + delta.dy, w: r.w, h: r.h }));
  const nueva = {
    id: nuevoId(),
    tipo: clipboard.tipo,
    label: siguienteNombre(clipboard.tipo),
    niveles: clipboard.niveles,
    columnas: clipboard.columnas,
    ...movidos[0],
  };
  if (movidos.length > 1) nueva.partes = movidos;
  piso().pieces.push(nueva);
  selectedId = nueva.id;
  selectedSector = null;
  multiSel = [];
  guardar();
  renderAll();
}

/* ================== Barra de herramientas ================== */
document.querySelectorAll('.tool-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tool-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    tool = btn.dataset.tool;
    if (tool !== 'select') { selectedId = null; selectedSector = null; multiSel = []; }
    if (tool !== 'marco') marcoSel = null;
    renderAll();
  });
});

$('btnUndo').addEventListener('click', undo);

$('btnAddPiso').addEventListener('click', () => {
  if (state.pisos.length >= MAX_PISOS) return;
  snapshot();
  state.pisos.push(nuevoPiso(`Piso ${state.pisos.length + 1}`));
  state.pisoActivo = state.pisos.length - 1;
  selectedId = null;
  selectedSector = null;
  guardar();
  renderAll();
  toast(`${piso().nombre} agregado — está vacío, dibújalo`);
});

$('btnDupPiso').addEventListener('click', () => {
  if (state.pisos.length >= MAX_PISOS) { toast(`Máximo ${MAX_PISOS} pisos`); return; }
  snapshot();
  const f = piso();
  const nuevo = nuevoPiso(`Piso ${state.pisos.length + 1}`);
  nuevo.walls = [...f.walls];
  nuevo.doors = [...f.doors];
  nuevo.pieces = f.pieces
    .filter(p => p.tipo === 'columna' || p.tipo === 'escalera')
    .map(p => ({ ...JSON.parse(JSON.stringify(p)), id: nuevoId() }));
  state.pisos.push(nuevo);
  state.pisoActivo = state.pisos.length - 1;
  selectedId = null;
  selectedSector = null;
  guardar();
  renderAll();
  toast('Piso duplicado: paredes, puertas, columnas y escaleras (los muebles no)');
});

$('btnRenPiso').addEventListener('click', () => {
  const nuevo = prompt('Nombre del piso:', piso().nombre);
  if (nuevo && nuevo.trim()) {
    snapshot();
    piso().nombre = nuevo.trim();
    guardar();
    renderAll();
  }
});

$('btnDelPiso').addEventListener('click', () => {
  if (state.pisos.length <= 1) return;
  const f = piso();
  if (f.pieces.length || f.walls.length || f.doors.length || f.sectores.length) {
    toast('Ese piso no está vacío: bórralo primero con Limpiar o el borrador');
    return;
  }
  snapshot();
  state.pisos.splice(state.pisoActivo, 1);
  state.pisoActivo = Math.max(0, state.pisoActivo - 1);
  selectedId = null;
  guardar();
  renderAll();
});
$('btnNiveles').addEventListener('click', () => abrirNiveles(selectedId));
$('mnClose').addEventListener('click', cerrarNiveles);
$('mnMenos').addEventListener('click', () => cambiarNiveles(-1));
$('mnMas').addEventListener('click', () => cambiarNiveles(1));
$('mcMenos').addEventListener('click', () => cambiarColumnas(-1));
$('mcMas').addEventListener('click', () => cambiarColumnas(1));
$('modalNiveles').addEventListener('click', (e) => {
  if (e.target === $('modalNiveles')) cerrarNiveles();
});
$('btnRotate').addEventListener('click', girarSeleccion);
$('btnDelete').addEventListener('click', eliminarSeleccion);
$('btnRename').addEventListener('click', renombrarSeleccion);
$('btnDuplicar').addEventListener('click', () => { copiarPieza(); pegarPieza(); });
$('btnColorSector').addEventListener('click', cambiarColorSector);
$('btnUnificar').addEventListener('click', unificarSeleccion);
$('btnSeparar').addEventListener('click', separarPieza);
$('btnCopiarSel').addEventListener('click', copiarMarco);
$('selTipo').addEventListener('change', (e) => cambiarTipo(e.target.value));

let mostrarNombres = localStorage.getItem('mapa_tienda_nombres') !== 'no';
function aplicarNombres() {
  stage.classList.toggle('sin-nombres', !mostrarNombres);
  $('btnNombres').classList.toggle('apagado', !mostrarNombres);
}
$('btnNombres').addEventListener('click', () => {
  mostrarNombres = !mostrarNombres;
  localStorage.setItem('mapa_tienda_nombres', mostrarNombres ? 'si' : 'no');
  aplicarNombres();
});

$('btnZoomIn').addEventListener('click', () => { zoom = Math.min(2, zoom + 0.15); renderAll(); });
$('btnZoomOut').addEventListener('click', () => { zoom = Math.max(0.5, zoom - 0.15); renderAll(); });

$('btnApplySize').addEventListener('click', () => {
  const cols = parseInt($('inpCols').value, 10);
  const rows = parseInt($('inpRows').value, 10);
  if (!cols || !rows || cols < 6 || rows < 6 || cols > 60 || rows > 60) {
    toast('Tamaño válido: entre 6 y 60 celdas');
    return;
  }
  const fueraPieza = state.pisos.some(f => f.pieces.some(p => p.x + p.w > cols || p.y + p.h > rows));
  const fueraCelda = state.pisos.some(f => [...f.walls, ...f.doors].some(k => {
    const [x, y] = k.split(',').map(Number);
    return x >= cols || y >= rows;
  }));
  if (fueraPieza || fueraCelda) {
    toast('Hay piezas fuera del nuevo tamaño; muévelas o bórralas primero');
    return;
  }
  snapshot();
  state.cols = cols;
  state.rows = rows;
  guardar();
  renderAll();
});

$('btnClear').addEventListener('click', () => {
  if (!confirm(`¿Borrar todo lo de "${piso().nombre}"? (se puede deshacer con Ctrl+Z)`)) return;
  snapshot();
  const f = piso();
  f.walls = [];
  f.doors = [];
  f.pieces = [];
  selectedId = null;
  guardar();
  renderAll();
});

$('btnPrint').addEventListener('click', () => {
  const f = piso();
  // ajusta el zoom para que el área usada quepa a lo ancho de la hoja
  let maxX = 8, maxY = 8;
  for (const p of f.pieces) for (const r of rectsDe(p)) { maxX = Math.max(maxX, r.x + r.w); maxY = Math.max(maxY, r.y + r.h); }
  for (const k of [...f.walls, ...f.doors]) {
    const [x, y] = k.split(',').map(Number);
    maxX = Math.max(maxX, x + 1); maxY = Math.max(maxY, y + 1);
  }
  for (const s of f.sectores) { maxX = Math.max(maxX, s.x + s.w); maxY = Math.max(maxY, s.y + s.h); }
  const zoomPrevio = zoom;
  zoom = Math.max(0.3, Math.min(1.5, 980 / ((maxX + 1) * BASE_CELL)));
  $('printHead').textContent = `Mapa de la Tienda — ${f.nombre}`;
  renderAll();
  window.addEventListener('afterprint', () => { zoom = zoomPrevio; renderAll(); }, { once: true });
  window.print();
});

$('btnExport').addEventListener('click', () => {
  const blob = new Blob([JSON.stringify(state, null, 2)], { type: 'application/json' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'mapa-tienda.json';
  a.click();
  URL.revokeObjectURL(a.href);
});

$('btnImport').addEventListener('click', () => $('fileImport').click());
$('fileImport').addEventListener('change', (e) => {
  const file = e.target.files[0];
  e.target.value = '';
  if (!file) return;
  const reader = new FileReader();
  reader.onload = () => {
    try {
      const data = JSON.parse(reader.result);
      if (typeof data.cols !== 'number' || (!Array.isArray(data.pieces) && !Array.isArray(data.pisos))) throw new Error('formato');
      snapshot();
      state = Object.assign(nuevoEstado(), data);
      migrar();
      selectedId = null;
      guardar();
      renderAll();
      toast('Mapa importado');
    } catch (_) {
      toast('Ese archivo no parece un mapa válido');
    }
  };
  reader.readAsText(file);
});

/* ================== Teclado ================== */
document.addEventListener('keydown', (e) => {
  if (e.target.matches('input, textarea')) return;
  if (!$('modalNiveles').hidden) {
    if (e.key === 'Escape') cerrarNiveles();
    return;
  }
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z') { e.preventDefault(); undo(); return; }
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'c') {
    if (marcoSel) copiarMarco(); else copiarPieza();
    return;
  }
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'v') {
    if (!clipboard) { toast('No hay nada copiado'); return; }
    if (clipboard.tipoClip === 'area') pegarMarco(); else pegarPieza();
    return;
  }
  if (e.key === 'Escape') { selectedId = null; selectedSector = null; multiSel = []; marcoSel = null; renderAll(); return; }
  if (!selectedId && !selectedSector && multiSel.length < 2 && !marcoSel) return;
  if (e.key.toLowerCase() === 'r') girarSeleccion();
  if (e.key === 'Delete' || e.key === 'Backspace') { e.preventDefault(); eliminarSeleccion(); }
});

/* ================== Inicio ================== */
cargar();
aplicarNombres();
renderAll();
