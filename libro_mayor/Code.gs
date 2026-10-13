/**
 * LIBRO MAYOR — registro compartido de préstamos y pagos entre dos personas.
 *
 * Cada movimiento que registra una persona queda "Pendiente" hasta que la otra
 * lo aprueba (queda "Confirmado") o lo rechaza. Solo lo confirmado cuenta para
 * el saldo. Un movimiento Pendiente puede ser editado o eliminado por quien lo
 * registró; una vez Confirmado ya no se toca: un error se corrige con un
 * movimiento de tipo "Ajuste".
 *
 * Los datos viven en la hoja "Movimientos" de la hoja de cálculo a la que está
 * vinculado este proyecto de Apps Script. Las columnas se localizan por su
 * encabezado (no por posición), y las que falten se agregan solas al final.
 */

// ═══════════════════ CONFIGURACIÓN — edita solo esto ═══════════════════
var CONFIG = {
  TITULO: 'Libro Mayor',
  // Las dos personas del libro. El saldo positivo está "a favor" de la primera.
  PERSONAS: ['Daniel', 'Coraima'],
  // Color de avatar de cada persona, en el mismo orden.
  COLORES: ['#a5673a', '#c25d84'],
  NOMBRE_HOJA: 'Movimientos'
};
// ═══════════════════════════════════════════════════════════════════════

var METODOS = ['Transferencia', 'Tarjeta', 'Efectivo'];
var ESTADOS = ['Pendiente', 'Confirmado', 'Rechazado'];

var COLUMNAS = [
  'id', 'uuid', 'creadoEn', 'fecha', 'hora', 'registradoPor', 'tipo', 'monto',
  'concepto', 'metodo', 'estado', 'aprobado1', 'fechaAprob1', 'aprobado2', 'fechaAprob2',
  'monedaOriginal', 'montoOriginal'
];

function tiposValidos() {
  var p1 = CONFIG.PERSONAS[0], p2 = CONFIG.PERSONAS[1];
  return [p1 + ' prestó dinero', p2 + ' prestó dinero', p1 + ' recibió un pago', p2 + ' recibió un pago', 'Ajuste'];
}

// ─────────────────────────── Web app ───────────────────────────

function doGet() {
  return HtmlService.createTemplateFromFile('Index')
    .evaluate()
    .setTitle(CONFIG.TITULO)
    .addMetaTag('viewport', 'width=device-width, initial-scale=1')
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
}

function include(nombre) {
  return HtmlService.createHtmlOutputFromFile(nombre).getContent();
}

function clientConfigJson() {
  return JSON.stringify({
    titulo: CONFIG.TITULO,
    personas: CONFIG.PERSONAS,
    colores: CONFIG.COLORES
  });
}

function onOpen() {
  try {
    SpreadsheetApp.getUi().createMenu(CONFIG.TITULO)
      .addItem('Preparar hoja de movimientos', 'prepararHoja')
      .addToUi();
  } catch (e) { /* no hay UI cuando corre como web app */ }
}

function prepararHoja() { obtenerHoja_(); }

// ─────────────────────────── Utilidades ───────────────────────────

function generarUuid() { return Utilities.getUuid(); }

function ahoraIso() { return new Date().toISOString(); }

function signoDeTipo(tipo) {
  var p1 = CONFIG.PERSONAS[0], p2 = CONFIG.PERSONAS[1];
  if (tipo === p1 + ' prestó dinero' || tipo === p2 + ' recibió un pago') return 1;
  if (tipo === p2 + ' prestó dinero' || tipo === p1 + ' recibió un pago') return -1;
  return 1;
}

function validarMonto(monto) {
  var n = Number(monto);
  if (!isFinite(n) || isNaN(n)) throw new Error('Monto inválido');
  n = Math.round(Math.abs(n) * 100) / 100;
  if (n <= 0) throw new Error('El monto debe ser mayor a cero');
  if (n > 999999999) throw new Error('Monto demasiado grande');
  return n;
}

function limpiarTexto(texto, max) {
  return String(texto == null ? '' : texto).replace(/\s+/g, ' ').trim().slice(0, max || 120);
}

function validarEnLista(valor, lista, nombreCampo) {
  if (lista.indexOf(valor) === -1) throw new Error('Valor no permitido para ' + (nombreCampo || 'campo') + ': ' + valor);
  return valor;
}

function validarFecha_(fecha) {
  var f = String(fecha || '').slice(0, 10);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(f)) throw new Error('Fecha inválida');
  return f;
}

/** Valida la pareja opcional moneda original + monto original. */
function validarMonedaOriginal_(payload) {
  var moneda = limpiarTexto(payload.monedaOriginal, 6).toUpperCase();
  var montoCrudo = payload.montoOriginal;
  var tiene = montoCrudo !== '' && montoCrudo != null && Number(montoCrudo) !== 0;
  if (moneda && !tiene) throw new Error('Pusiste la moneda original pero falta el monto original');
  if (!moneda && tiene) throw new Error('Pusiste el monto original pero falta la moneda (COP, USD…)');
  if (!moneda) return { monedaOriginal: '', montoOriginal: '' };
  if (!/^[A-Z]{3,6}$/.test(moneda)) throw new Error('La moneda original debe ser un código tipo COP o USD');
  return { monedaOriginal: moneda, montoOriginal: validarMonto(montoCrudo) };
}

/** Valida los campos editables de un movimiento (alta y edición comparten reglas). */
function datosDeMovimiento_(payload) {
  var tipo = validarEnLista(limpiarTexto(payload.tipo, 60), tiposValidos(), 'tipo');
  var monto = validarMonto(payload.monto);
  var metodo = '';
  if (tipo !== 'Ajuste') {
    metodo = validarEnLista(limpiarTexto(payload.metodo, 30), METODOS, 'método');
  } else {
    // Un ajuste guarda el monto con signo según la dirección elegida.
    monto = (Number(payload.dir) < 0 ? -1 : 1) * monto;
  }
  var mo = validarMonedaOriginal_(payload);
  return {
    tipo: tipo,
    monto: monto,
    metodo: metodo,
    concepto: limpiarTexto(payload.concepto, 120),
    fecha: validarFecha_(payload.fecha),
    monedaOriginal: mo.monedaOriginal,
    montoOriginal: mo.montoOriginal
  };
}

// ─────────────────────────── Hoja de datos ───────────────────────────

function obtenerHoja_() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  if (!ss) {
    // Proyecto no vinculado a una hoja: crea (una sola vez) su propia hoja de cálculo.
    var props = PropertiesService.getScriptProperties();
    var id = props.getProperty('SPREADSHEET_ID');
    if (id) {
      ss = SpreadsheetApp.openById(id);
    } else {
      ss = SpreadsheetApp.create(CONFIG.TITULO + ' — datos');
      props.setProperty('SPREADSHEET_ID', ss.getId());
    }
  }
  var hoja = ss.getSheetByName(CONFIG.NOMBRE_HOJA);
  if (!hoja) {
    hoja = ss.insertSheet(CONFIG.NOMBRE_HOJA);
    hoja.getRange(1, 1, 1, COLUMNAS.length).setValues([COLUMNAS]).setFontWeight('bold');
    hoja.setFrozenRows(1);
  } else {
    asegurarColumnas_(hoja);
  }
  return hoja;
}

/** Agrega al final los encabezados que falten (migraciones sin tocar datos). */
function asegurarColumnas_(hoja) {
  var actuales = leerEncabezados_(hoja);
  var faltantes = COLUMNAS.filter(function (c) { return actuales.indexOf(c) === -1; });
  if (!faltantes.length) return;
  hoja.getRange(1, actuales.length + 1, 1, faltantes.length).setValues([faltantes]).setFontWeight('bold');
}

function leerEncabezados_(hoja) {
  var ancho = Math.max(1, hoja.getLastColumn());
  return hoja.getRange(1, 1, 1, ancho).getValues()[0]
    .map(function (v) { return String(v || '').trim(); })
    .filter(function (v) { return v !== ''; });
}

/** Mapa encabezado → índice de columna (base 0). */
function mapaColumnas_(hoja) {
  var mapa = {};
  leerEncabezados_(hoja).forEach(function (nombre, i) { mapa[nombre] = i; });
  return mapa;
}

/** Escribe una fila nueva colocando cada valor bajo su encabezado. */
function escribirFila_(hoja, filaObj) {
  var encabezados = leerEncabezados_(hoja);
  hoja.appendRow(encabezados.map(function (h) {
    return filaObj.hasOwnProperty(h) ? filaObj[h] : '';
  }));
}

/** Actualiza celdas de una fila existente, por nombre de encabezado. */
function actualizarCeldas_(hoja, filaNum, cambios) {
  var mapa = mapaColumnas_(hoja);
  Object.keys(cambios).forEach(function (campo) {
    if (mapa.hasOwnProperty(campo)) {
      hoja.getRange(filaNum, mapa[campo] + 1).setValue(cambios[campo]);
    }
  });
}

function leerMovimientos_(hoja) {
  var ultima = hoja.getLastRow();
  if (ultima < 2) return [];
  var mapa = mapaColumnas_(hoja);
  var ancho = Math.max(1, hoja.getLastColumn());
  var valores = hoja.getRange(2, 1, ultima - 1, ancho).getValues();
  return valores.map(function (fila) {
    var m = {};
    COLUMNAS.forEach(function (col) {
      m[col] = mapa.hasOwnProperty(col) ? fila[mapa[col]] : '';
    });
    m.id = Number(m.id);
    m.monto = Number(m.monto);
    m.fecha = normalizarFecha_(m.fecha);
    m.creadoEn = normalizarStamp_(m.creadoEn);
    m.aprobado1 = m.aprobado1 === true || m.aprobado1 === 'TRUE' || m.aprobado1 === 'true';
    m.aprobado2 = m.aprobado2 === true || m.aprobado2 === 'TRUE' || m.aprobado2 === 'true';
    m.fechaAprob1 = normalizarStamp_(m.fechaAprob1);
    m.fechaAprob2 = normalizarStamp_(m.fechaAprob2);
    m.monedaOriginal = limpiarTexto(m.monedaOriginal, 6).toUpperCase();
    m.montoOriginal = Number(m.montoOriginal) || 0;
    return m;
  });
}

function normalizarFecha_(v) {
  if (v instanceof Date) {
    return Utilities.formatDate(v, Session.getScriptTimeZone(), 'yyyy-MM-dd');
  }
  return String(v || '').slice(0, 10);
}

function normalizarStamp_(v) {
  if (v instanceof Date) return v.toISOString();
  return String(v || '');
}

function montoConSigno_(m) {
  if (m.tipo === 'Ajuste') return Number(m.monto);
  return signoDeTipo(m.tipo) * Math.abs(Number(m.monto));
}

function cronologico_(a, b) {
  if (a.fecha < b.fecha) return -1;
  if (a.fecha > b.fecha) return 1;
  return a.creadoEn < b.creadoEn ? -1 : 1;
}

function buscarPorUuid_(movimientos, uuid) {
  for (var i = 0; i < movimientos.length; i++) {
    if (String(movimientos[i].uuid) === String(uuid)) return i;
  }
  return -1;
}

// ─────────────────────────── API para la app ───────────────────────────

function api_getEstado() {
  var movimientos = leerMovimientos_(obtenerHoja_());
  // El saldo SOLO suma movimientos confirmados.
  var confirmados = movimientos.filter(function (m) { return m.estado === 'Confirmado'; }).sort(cronologico_);
  var saldo = 0;
  var saldoPorUuid = {};
  confirmados.forEach(function (m) {
    saldo += montoConSigno_(m);
    saldoPorUuid[m.uuid] = Math.round(saldo * 100) / 100;
  });
  movimientos.forEach(function (m) {
    m.saldoDespues = saldoPorUuid.hasOwnProperty(m.uuid) ? saldoPorUuid[m.uuid] : null;
  });
  // Lo pendiente se informa aparte, nunca dentro del saldo.
  var pendienteNeto = movimientos
    .filter(function (m) { return m.estado === 'Pendiente'; })
    .reduce(function (a, m) { return a + montoConSigno_(m); }, 0);
  return {
    saldo: Math.round(saldo * 100) / 100,
    pendienteNeto: Math.round(pendienteNeto * 100) / 100,
    movimientos: movimientos
  };
}

function api_registrarMovimiento(payload) {
  var lock = LockService.getScriptLock();
  lock.waitLock(20000);
  try {
    var registradoPor = validarEnLista(limpiarTexto(payload.registradoPor, 40), CONFIG.PERSONAS, 'persona');
    var datos = datosDeMovimiento_(payload);

    var hoja = obtenerHoja_();
    var movimientos = leerMovimientos_(hoja);
    var maxId = movimientos.reduce(function (a, m) { return Math.max(a, m.id || 0); }, 0);
    var ahora = ahoraIso();
    var esPersona1 = registradoPor === CONFIG.PERSONAS[0];

    escribirFila_(hoja, {
      id: maxId + 1,
      uuid: generarUuid(),
      creadoEn: ahora,
      fecha: datos.fecha,
      hora: Utilities.formatDate(new Date(), Session.getScriptTimeZone(), 'HH:mm'),
      registradoPor: registradoPor,
      tipo: datos.tipo,
      monto: datos.monto,
      concepto: datos.concepto,
      metodo: datos.metodo,
      estado: 'Pendiente',
      aprobado1: esPersona1,
      fechaAprob1: esPersona1 ? ahora : '',
      aprobado2: !esPersona1,
      fechaAprob2: !esPersona1 ? ahora : '',
      monedaOriginal: datos.monedaOriginal,
      montoOriginal: datos.montoOriginal
    });
    return api_getEstado();
  } finally {
    lock.releaseLock();
  }
}

/** Solo quien registró un movimiento puede editarlo, y solo mientras está Pendiente. */
function api_editarMovimiento(uuid, quien, payload) {
  var lock = LockService.getScriptLock();
  lock.waitLock(20000);
  try {
    quien = validarEnLista(limpiarTexto(quien, 40), CONFIG.PERSONAS, 'persona');
    var hoja = obtenerHoja_();
    var movimientos = leerMovimientos_(hoja);
    var idx = buscarPorUuid_(movimientos, uuid);
    if (idx === -1) throw new Error('Movimiento no encontrado');
    var m = movimientos[idx];
    if (m.estado !== 'Pendiente') throw new Error('Solo se pueden editar movimientos pendientes');
    if (m.registradoPor !== quien) throw new Error('Solo quien lo registró puede editarlo');

    var datos = datosDeMovimiento_(payload);
    actualizarCeldas_(hoja, idx + 2, {
      tipo: datos.tipo,
      monto: datos.monto,
      concepto: datos.concepto,
      metodo: datos.metodo,
      fecha: datos.fecha,
      monedaOriginal: datos.monedaOriginal,
      montoOriginal: datos.montoOriginal
    });
    return api_getEstado();
  } finally {
    lock.releaseLock();
  }
}

/** Solo quien registró un movimiento puede eliminarlo, y solo mientras está Pendiente. */
function api_eliminarMovimiento(uuid, quien) {
  var lock = LockService.getScriptLock();
  lock.waitLock(20000);
  try {
    quien = validarEnLista(limpiarTexto(quien, 40), CONFIG.PERSONAS, 'persona');
    var hoja = obtenerHoja_();
    var movimientos = leerMovimientos_(hoja);
    var idx = buscarPorUuid_(movimientos, uuid);
    if (idx === -1) throw new Error('Movimiento no encontrado');
    var m = movimientos[idx];
    if (m.estado !== 'Pendiente') throw new Error('Solo se pueden eliminar movimientos pendientes');
    if (m.registradoPor !== quien) throw new Error('Solo quien lo registró puede eliminarlo');
    hoja.deleteRow(idx + 2);
    return api_getEstado();
  } finally {
    lock.releaseLock();
  }
}

function api_aprobarMovimiento(uuid, quien) {
  return resolverPendiente_(uuid, quien, true);
}

function api_rechazarMovimiento(uuid, quien) {
  return resolverPendiente_(uuid, quien, false);
}

function resolverPendiente_(uuid, quien, aprobar) {
  var lock = LockService.getScriptLock();
  lock.waitLock(20000);
  try {
    quien = validarEnLista(limpiarTexto(quien, 40), CONFIG.PERSONAS, 'persona');
    var hoja = obtenerHoja_();
    var movimientos = leerMovimientos_(hoja);
    var idx = buscarPorUuid_(movimientos, uuid);
    if (idx === -1) throw new Error('Movimiento no encontrado');
    var m = movimientos[idx];
    if (m.estado !== 'Pendiente') throw new Error('Este movimiento ya fue resuelto');
    if (m.registradoPor === quien) throw new Error('No puedes aprobar tu propio movimiento');

    var filaNum = idx + 2; // +1 encabezado, +1 índice base 1
    var ahora = ahoraIso();
    if (aprobar) {
      var esPersona1 = quien === CONFIG.PERSONAS[0];
      var cambios = { estado: 'Confirmado' };
      cambios[esPersona1 ? 'aprobado1' : 'aprobado2'] = true;
      cambios[esPersona1 ? 'fechaAprob1' : 'fechaAprob2'] = ahora;
      actualizarCeldas_(hoja, filaNum, cambios);
    } else {
      actualizarCeldas_(hoja, filaNum, { estado: 'Rechazado' });
    }
    return api_getEstado();
  } finally {
    lock.releaseLock();
  }
}
