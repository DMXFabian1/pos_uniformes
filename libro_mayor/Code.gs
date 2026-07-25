/**
 * LIBRO MAYOR COMPARTIDO — Daniel ↔ Coraima
 * Punto de entrada de la Web App (Google Apps Script).
 *
 * ── Cómo desplegar ──────────────────────────────────────────────
 * 1. Crea (o abre) una Hoja de cálculo de Google.
 * 2. Extensiones ▸ Apps Script. Pega estos archivos con los mismos nombres.
 * 3. Ejecuta una vez `ensureSchema_` para crear las hojas "Movimientos" y
 *    "Configuración" con sus encabezados.
 * 4. Implementar ▸ Nueva implementación ▸ Aplicación web.
 *      • Ejecutar como: Yo
 *      • Quién tiene acceso: el que prefieran (p. ej. "Cualquier usuario")
 * 5. Abre la URL en el iPhone y "Agregar a pantalla de inicio" (PWA).
 * ────────────────────────────────────────────────────────────────
 */

/**
 * Sirve la aplicación web como una sola página.
 * El usuario nunca ve la hoja; Sheets funciona solo como base de datos.
 * @return {HtmlOutput}
 */
function doGet() {
  ensureSchema_(); // crea hojas/encabezados si aún no existen (idempotente)
  return HtmlService.createTemplateFromFile('Index')
    .evaluate()
    .setTitle('Libro Mayor')
    .addMetaTag('viewport', 'width=device-width, initial-scale=1');
}

/**
 * Incluye el contenido de otro archivo .html dentro de UI.html.
 * Uso en la plantilla: <?!= include('Styles') ?>
 * @param {string} nombre  Nombre del archivo sin extensión.
 * @return {string} HTML del archivo.
 */
function include(nombre) {
  return HtmlService.createHtmlOutputFromFile(nombre).getContent();
}

/**
 * Menú en la hoja para inicializar el esquema desde el editor (opcional).
 */
function onOpen() {
  try {
    SpreadsheetApp.getUi()
      .createMenu('Libro Mayor')
      .addItem('Inicializar hojas', 'ensureSchema_')
      .addToUi();
  } catch (e) {
    // onOpen solo aplica si el script está enlazado a una hoja.
  }
}


/* ==================== Utils ==================== */

/**
 * UTILIDADES Y CONSTANTES DEL DOMINIO.
 * Funciones puras: no acceden a Sheets. Fáciles de leer y de probar.
 */

/** Nombres de las hojas usadas como base de datos. */
var SHEET_MOVIMIENTOS = 'Movimientos';
var SHEET_CONFIG = 'Configuración';

/**
 * Encabezados de la hoja "Movimientos".
 * El ORDEN define las columnas: no reordenar sin migrar los datos.
 */
var HEADERS = [
  'ID',
  'Fecha de creación',
  'Fecha del movimiento',
  'Hora',
  'Registrado por',
  'Tipo',
  'Monto',
  'Concepto',
  'Método',
  'Estado',
  'Aprobado por Daniel',
  'Fecha aprobación Daniel',
  'Aprobado por Coraima',
  'Fecha aprobación Coraima',
  'Saldo después del movimiento',
  'UUID',
  'Corrige a'
];

/** Personas del libro (no hay más usuarios). */
var PERSONAS = ['Daniel', 'Coraima'];

/** Tipos de movimiento válidos. */
var TIPOS = [
  'Daniel envió dinero',
  'Coraima envió dinero',
  'Daniel recibió dinero',
  'Coraima recibió dinero',
  'Ajuste de saldo'
];

/**
 * Nombres antiguos de los tipos → nombre actual.
 * Las filas viejas de la hoja se guardaron con estos nombres; se traducen
 * al leer para que el cálculo del saldo y la app funcionen sin migrar datos.
 */
var TIPOS_LEGADO = {
  'Daniel prestó dinero': 'Daniel envió dinero',
  'Coraima prestó dinero': 'Coraima envió dinero',
  'Daniel recibió un pago': 'Daniel recibió dinero',
  'Coraima recibió un pago': 'Coraima recibió dinero',
  'Ajuste': 'Ajuste de saldo'
};

/** Traduce un tipo antiguo a su nombre actual (deja igual los actuales). */
function normalizarTipo_(tipo) {
  return TIPOS_LEGADO[tipo] || tipo;
}

/** Métodos de registro del dinero ('' = no aplica, p. ej. en Ajuste). */
var METODOS = ['Transferencia', 'Tarjeta', 'Efectivo', ''];

/** Estados posibles de un movimiento. */
var ESTADOS = {
  PENDIENTE: 'Pendiente',
  CONFIRMADO: 'Confirmado',
  RECHAZADO: 'Rechazado',
  CORREGIDO: 'Corregido',
  CANCELADO: 'Cancelado'
};

/**
 * Signo de un tipo respecto al saldo.
 * Convención: saldo positivo = "Coraima le debe a Daniel".
 * Dinero que fluye Daniel → Coraima SUMA; Coraima → Daniel RESTA.
 * @param {string} tipo
 * @return {number} 1 o -1
 */
function signoDeTipo(tipo) {
  tipo = normalizarTipo_(tipo);
  if (tipo === 'Daniel envió dinero' || tipo === 'Coraima recibió dinero') return 1;
  if (tipo === 'Coraima envió dinero' || tipo === 'Daniel recibió dinero') return -1;
  return 1; // Ajuste de saldo: el signo lo aporta el propio monto (ver montoConSigno_)
}

/**
 * Monto con signo aplicado. En "Ajuste" el monto ya viene firmado.
 * @param {string} tipo
 * @param {number} monto
 * @return {number}
 */
function montoConSigno_(tipo, monto) {
  if (normalizarTipo_(tipo) === 'Ajuste de saldo') return Number(monto);
  return signoDeTipo(tipo) * Math.abs(Number(monto));
}

/** Genera un UUID v4 (identificador único e inmutable del movimiento). */
function generarUuid() {
  return Utilities.getUuid();
}

/** Marca de tiempo del servidor en ISO 8601. */
function ahoraIso() {
  return new Date().toISOString();
}

/**
 * Valida y normaliza un monto (siempre positivo, 2 decimales).
 * @throws si no es un número válido o es <= 0.
 */
function validarMonto(valor) {
  var n = Number(valor);
  if (!isFinite(n) || isNaN(n)) throw new Error('El monto no es un número válido.');
  n = Math.round(Math.abs(n) * 100) / 100;
  if (n <= 0) throw new Error('El monto debe ser mayor que cero.');
  if (n > 100000000) throw new Error('El monto excede el máximo permitido.');
  return n;
}

/**
 * Limpia texto libre: recorta a 140 chars y evita inyección de fórmulas.
 * Un texto que empieza con = + - @ se antepone con ' para que Sheets lo trate
 * como literal (la comilla no se muestra en la app ni en la celda).
 */
function limpiarTexto(txt) {
  if (txt === null || txt === undefined) return '';
  var s = String(txt).trim().slice(0, 140);
  if (/^[=+\-@]/.test(s)) s = "'" + s;
  return s;
}

/**
 * Valida que un valor pertenezca a una lista permitida.
 * @throws si el valor no está en la lista.
 */
function validarEnLista(valor, lista, etiqueta) {
  if (lista.indexOf(valor) === -1) {
    throw new Error('Valor inválido para "' + etiqueta + '": ' + valor);
  }
  return valor;
}

/**
 * Valida/normaliza la fecha del movimiento (YYYY-MM-DD). Predeterminado: hoy.
 */
function validarFecha_(fecha) {
  var tz = Session.getScriptTimeZone();
  if (!fecha) return Utilities.formatDate(new Date(), tz, 'yyyy-MM-dd');
  var s = String(fecha).slice(0, 10);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(s)) throw new Error('Fecha inválida (usa YYYY-MM-DD).');
  return s;
}


/* ==================== Database ==================== */

/**
 * CAPA DE DATOS — Google Sheets como base de datos.
 * Todo el acceso de lectura/escritura a las hojas vive aquí.
 */

/**
 * ID del libro de cálculo. Normalmente déjalo VACÍO:
 *  • Si el script está enlazado a una hoja (Extensiones ▸ Apps Script), usa esa.
 *  • Si es un proyecto independiente (script.google.com), el código crea una hoja
 *    automáticamente la primera vez y la recuerda. No necesitas hacer nada.
 *  • Si quieres forzar una hoja específica, pega aquí su ID.
 */
var SPREADSHEET_ID = '';

/** Devuelve el libro de cálculo (lo crea automáticamente si hace falta). */
function obtenerLibro_() {
  if (SPREADSHEET_ID) return SpreadsheetApp.openById(SPREADSHEET_ID);

  var activo = SpreadsheetApp.getActive();
  if (activo) return activo; // script enlazado a una hoja

  // Proyecto independiente: crea (una sola vez) una hoja propia y la recuerda.
  var props = PropertiesService.getScriptProperties();
  var id = props.getProperty('LIBRO_MAYOR_SS_ID');
  if (id) {
    try { return SpreadsheetApp.openById(id); } catch (e) { /* si se borró, se recrea abajo */ }
  }
  var libro = SpreadsheetApp.create('Libro Mayor — Base de datos');
  props.setProperty('LIBRO_MAYOR_SS_ID', libro.getId());
  return libro;
}

/**
 * Crea las hojas y encabezados si no existen. Es idempotente:
 * se puede ejecutar cuantas veces se quiera sin duplicar nada.
 */
function ensureSchema_() {
  var libro = obtenerLibro_();

  // Hoja Movimientos
  var mov = libro.getSheetByName(SHEET_MOVIMIENTOS) || libro.insertSheet(SHEET_MOVIMIENTOS);
  var encabezado = mov.getRange(1, 1, 1, HEADERS.length).getValues()[0];
  if (encabezado.join('|') !== HEADERS.join('|')) {
    mov.getRange(1, 1, 1, HEADERS.length).setValues([HEADERS]).setFontWeight('bold');
    mov.setFrozenRows(1);
  }

  // Hoja Configuración (parámetros modificables a futuro)
  var cfg = libro.getSheetByName(SHEET_CONFIG);
  if (!cfg) {
    cfg = libro.insertSheet(SHEET_CONFIG);
    cfg.getRange(1, 1, 1, 2).setValues([['Parámetro', 'Valor']]).setFontWeight('bold');
    cfg.setFrozenRows(1);
    cfg.getRange(2, 1, 6, 2).setValues([
      ['moneda', 'MXN'],
      ['locale', 'es-MX'],
      ['persona_a', 'Daniel'],
      ['persona_b', 'Coraima'],
      ['zona_horaria', Session.getScriptTimeZone()],
      ['version_esquema', '2']
    ]);
  }
  return true;
}

/** Índice (1-based) de una columna a partir de su encabezado. */
function colIndex_(nombre) {
  var i = HEADERS.indexOf(nombre);
  if (i === -1) throw new Error('Columna desconocida: ' + nombre);
  return i + 1;
}

/** Lee todos los movimientos de la hoja como objetos. */
function leerMovimientos_() {
  var mov = obtenerLibro_().getSheetByName(SHEET_MOVIMIENTOS);
  var ultima = mov.getLastRow();
  if (ultima < 2) return [];
  var valores = mov.getRange(2, 1, ultima - 1, HEADERS.length).getValues();
  return valores.map(function (fila, i) { return filaAObjeto_(fila, i + 2); });
}

/** Convierte una fila (array) en un objeto de movimiento tipado. */
function filaAObjeto_(fila, numeroFila) {
  var o = {};
  HEADERS.forEach(function (h, i) { o[h] = fila[i]; });
  return {
    fila: numeroFila,
    id: o['ID'],
    creadoEn: o['Fecha de creación'],
    fecha: o['Fecha del movimiento'],
    hora: o['Hora'],
    registradoPor: o['Registrado por'],
    tipo: normalizarTipo_(o['Tipo']),
    monto: Number(o['Monto']) || 0,
    concepto: o['Concepto'],
    metodo: o['Método'],
    estado: o['Estado'],
    aprobadoDaniel: esVerdadero_(o['Aprobado por Daniel']),
    fechaAprobDaniel: o['Fecha aprobación Daniel'],
    aprobadoCoraima: esVerdadero_(o['Aprobado por Coraima']),
    fechaAprobCoraima: o['Fecha aprobación Coraima'],
    saldoDespues: o['Saldo después del movimiento'] === '' ? null : Number(o['Saldo después del movimiento']),
    uuid: o['UUID'],
    corrigeA: o['Corrige a'] ? String(o['Corrige a']) : ''
  };
}

/** Interpreta como booleano los distintos formatos que puede devolver Sheets. */
function esVerdadero_(v) {
  return v === true || v === 'TRUE' || v === 'VERDADERO' || v === 'sí' || v === 'si';
}

/** Agrega un movimiento. `objeto` está indexado por encabezado. */
function agregarMovimiento_(objeto) {
  var mov = obtenerLibro_().getSheetByName(SHEET_MOVIMIENTOS);
  var fila = HEADERS.map(function (h) { return objeto[h] !== undefined ? objeto[h] : ''; });
  mov.appendRow(fila);
  return mov.getLastRow();
}

/**
 * Actualiza celdas de un movimiento localizado por su UUID.
 * @param {string} uuid
 * @param {!Object<string, *>} cambios  { 'Encabezado': nuevoValor, ... }
 * @return {number} número de fila actualizada
 */
function actualizarPorUuid_(uuid, cambios) {
  var mov = obtenerLibro_().getSheetByName(SHEET_MOVIMIENTOS);
  var ultima = mov.getLastRow();
  if (ultima < 2) throw new Error('No hay movimientos.');
  var colUuid = colIndex_('UUID');
  var uuids = mov.getRange(2, colUuid, ultima - 1, 1).getValues();
  for (var i = 0; i < uuids.length; i++) {
    if (uuids[i][0] === uuid) {
      var fila = i + 2;
      Object.keys(cambios).forEach(function (h) {
        mov.getRange(fila, colIndex_(h)).setValue(cambios[h]);
      });
      return fila;
    }
  }
  throw new Error('Movimiento no encontrado: ' + uuid);
}

/**
 * Recalcula la columna "Saldo después del movimiento" para TODOS los
 * confirmados en orden cronológico. Los no confirmados quedan en blanco.
 * @return {number} saldo final
 */
function recalcularSaldos_() {
  var mov = obtenerLibro_().getSheetByName(SHEET_MOVIMIENTOS);
  if (mov.getLastRow() < 2) return 0;
  var movimientos = leerMovimientos_();
  var colSaldo = colIndex_('Saldo después del movimiento');

  movimientos.forEach(function (m) {
    if (m.estado !== ESTADOS.CONFIRMADO) mov.getRange(m.fila, colSaldo).setValue('');
  });

  var saldo = 0;
  movimientos
    .filter(function (m) { return m.estado === ESTADOS.CONFIRMADO; })
    .sort(ordenCronologico_)
    .forEach(function (m) {
      saldo += montoConSigno_(m.tipo, m.monto);
      mov.getRange(m.fila, colSaldo).setValue(saldo);
    });
  return saldo;
}

/** Orden cronológico estable: por fecha del movimiento y luego por creación. */
function ordenCronologico_(a, b) {
  var fa = String(a.fecha), fb = String(b.fecha);
  if (fa < fb) return -1;
  if (fa > fb) return 1;
  return String(a.creadoEn) < String(b.creadoEn) ? -1 : 1;
}

/** Lee un parámetro de la hoja Configuración. */
function obtenerConfig_(clave, predeterminado) {
  var cfg = obtenerLibro_().getSheetByName(SHEET_CONFIG);
  if (!cfg || cfg.getLastRow() < 2) return predeterminado;
  var valores = cfg.getRange(2, 1, cfg.getLastRow() - 1, 2).getValues();
  for (var i = 0; i < valores.length; i++) {
    if (valores[i][0] === clave) return valores[i][1];
  }
  return predeterminado;
}


/* ==================== API ==================== */

/**
 * API DEL SERVIDOR.
 * Funciones llamadas desde el cliente con google.script.run.
 * Cada operación valida sus datos, usa LockService para evitar condiciones de
 * carrera y devuelve el estado completo y fresco para repintar la app.
 */

/**
 * Estado completo para pintar la app: saldo, configuración y movimientos.
 * @return {!Object}
 */
function api_getEstado() {
  ensureSchema_();
  var movimientos = leerMovimientos_();

  var saldo = 0;
  movimientos
    .filter(function (m) { return m.estado === ESTADOS.CONFIRMADO; })
    .sort(ordenCronologico_)
    .forEach(function (m) { saldo += montoConSigno_(m.tipo, m.monto); });

  return {
    ok: true,
    saldo: saldo,
    moneda: obtenerConfig_('moneda', 'MXN'),
    locale: obtenerConfig_('locale', 'es-MX'),
    personas: [obtenerConfig_('persona_a', 'Daniel'), obtenerConfig_('persona_b', 'Coraima')],
    movimientos: movimientos.map(serializar_),
    servidor: ahoraIso()
  };
}

/**
 * Registra un movimiento nuevo en estado Pendiente.
 * Quien lo registra queda auto-aprobado; el OTRO debe aprobarlo.
 * @param {!Object} datos { registradoPor, tipo, monto, concepto, metodo, fecha, dir }
 * @return {!Object} estado actualizado
 */
function api_registrarMovimiento(datos) {
  var lock = LockService.getScriptLock();
  lock.waitLock(20000);
  try {
    ensureSchema_();
    datos = datos || {};

    var persona = validarEnLista(datos.registradoPor, PERSONAS, 'registradoPor');
    var tipo = validarEnLista(datos.tipo, TIPOS, 'tipo');
    var metodo = tipo === 'Ajuste de saldo' ? '' : validarEnLista(datos.metodo || 'Transferencia', METODOS, 'método');
    var monto = validarMonto(datos.monto);
    var concepto = limpiarTexto(datos.concepto);
    var fecha = validarFecha_(datos.fecha);

    // En un Ajuste el monto se guarda CON signo según la dirección elegida.
    var montoGuardado = monto;
    if (tipo === 'Ajuste de saldo') {
      var dir = Number(datos.dir) < 0 ? -1 : 1;
      montoGuardado = dir * monto;
    }

    var ahora = new Date();
    var esDaniel = persona === 'Daniel';
    var tz = Session.getScriptTimeZone();

    var registro = {};
    registro['ID'] = siguienteId_();
    registro['Fecha de creación'] = ahora;
    registro['Fecha del movimiento'] = fecha;
    registro['Hora'] = Utilities.formatDate(ahora, tz, 'HH:mm:ss');
    registro['Registrado por'] = persona;
    registro['Tipo'] = tipo;
    registro['Monto'] = montoGuardado;
    registro['Concepto'] = concepto;
    registro['Método'] = metodo;
    registro['Estado'] = ESTADOS.PENDIENTE;
    registro['Aprobado por Daniel'] = esDaniel;
    registro['Fecha aprobación Daniel'] = esDaniel ? ahora : '';
    registro['Aprobado por Coraima'] = !esDaniel;
    registro['Fecha aprobación Coraima'] = !esDaniel ? ahora : '';
    registro['Saldo después del movimiento'] = '';
    registro['UUID'] = generarUuid();

    agregarMovimiento_(registro);
    return api_getEstado();
  } finally {
    lock.releaseLock();
  }
}

/**
 * Aprueba un movimiento en nombre de una persona.
 * Como quien registró ya está auto-aprobado, la aprobación del otro
 * lo deja Confirmado y recalcula los saldos.
 * @param {string} uuid
 * @param {string} persona
 * @return {!Object} estado actualizado
 */
function api_aprobarMovimiento(uuid, persona) {
  var lock = LockService.getScriptLock();
  lock.waitLock(20000);
  try {
    validarEnLista(persona, PERSONAS, 'persona');
    var m = buscarPorUuid_(leerMovimientos_(), uuid);
    if (m.estado !== ESTADOS.PENDIENTE) {
      throw new Error('Solo se pueden aprobar movimientos pendientes.');
    }

    var ahora = new Date();
    var cambios = {};
    if (persona === 'Daniel') {
      cambios['Aprobado por Daniel'] = true;
      cambios['Fecha aprobación Daniel'] = ahora;
    } else {
      cambios['Aprobado por Coraima'] = true;
      cambios['Fecha aprobación Coraima'] = ahora;
    }

    var ambos = (persona === 'Daniel' || m.aprobadoDaniel) &&
                (persona === 'Coraima' || m.aprobadoCoraima);
    if (ambos) cambios['Estado'] = ESTADOS.CONFIRMADO;

    actualizarPorUuid_(uuid, cambios);
    if (ambos) {
      // Si este movimiento corrige a otro, el original sale del saldo.
      if (m.corrigeA) actualizarPorUuid_(m.corrigeA, { 'Estado': ESTADOS.CORREGIDO });
      recalcularSaldos_();
    }
    return api_getEstado();
  } finally {
    lock.releaseLock();
  }
}

/**
 * Rechaza un movimiento pendiente. No afecta el saldo y no borra nada:
 * el movimiento queda registrado con estado "Rechazado" (trazabilidad).
 * @param {string} uuid
 * @param {string} persona
 * @return {!Object} estado actualizado
 */
function api_rechazarMovimiento(uuid, persona) {
  var lock = LockService.getScriptLock();
  lock.waitLock(20000);
  try {
    validarEnLista(persona, PERSONAS, 'persona');
    var m = buscarPorUuid_(leerMovimientos_(), uuid);
    if (m.estado !== ESTADOS.PENDIENTE) {
      throw new Error('Solo se pueden rechazar movimientos pendientes.');
    }
    var cambios = { 'Estado': ESTADOS.RECHAZADO };
    if (persona === 'Daniel') cambios['Fecha aprobación Daniel'] = new Date();
    else cambios['Fecha aprobación Coraima'] = new Date();
    actualizarPorUuid_(uuid, cambios);
    return api_getEstado();
  } finally {
    lock.releaseLock();
  }
}

/**
 * Corrige un movimiento CONFIRMADO sin borrar nada: crea un movimiento
 * nuevo (Pendiente) enlazado al original vía "Corrige a". Cuando el otro
 * lo aprueba, el original pasa a "Corregido" y sale del saldo; si lo
 * rechaza, el original queda intacto.
 * @param {string} uuid     UUID del movimiento a corregir.
 * @param {string} persona  Quién registra la corrección.
 * @param {!Object} datos   { tipo, monto, concepto, metodo, fecha, dir }
 * @return {!Object} estado actualizado
 */
function api_corregirMovimiento(uuid, persona, datos) {
  var lock = LockService.getScriptLock();
  lock.waitLock(20000);
  try {
    ensureSchema_();
    datos = datos || {};
    persona = validarEnLista(persona, PERSONAS, 'persona');

    var movimientos = leerMovimientos_();
    var original = buscarPorUuid_(movimientos, uuid);
    if (original.estado !== ESTADOS.CONFIRMADO) {
      throw new Error('Solo se pueden corregir movimientos confirmados.');
    }
    var yaEnCurso = movimientos.some(function (m) {
      return m.corrigeA === uuid &&
             (m.estado === ESTADOS.PENDIENTE || m.estado === ESTADOS.CONFIRMADO);
    });
    if (yaEnCurso) throw new Error('Este movimiento ya tiene una corrección en curso.');

    var tipo = validarEnLista(datos.tipo, TIPOS, 'tipo');
    var metodo = tipo === 'Ajuste de saldo' ? '' : validarEnLista(datos.metodo || 'Transferencia', METODOS, 'método');
    var monto = validarMonto(datos.monto);
    var concepto = limpiarTexto(datos.concepto);
    var fecha = validarFecha_(datos.fecha);

    var montoGuardado = monto;
    if (tipo === 'Ajuste de saldo') {
      var dir = Number(datos.dir) < 0 ? -1 : 1;
      montoGuardado = dir * monto;
    }

    var ahora = new Date();
    var esDaniel = persona === 'Daniel';
    var tz = Session.getScriptTimeZone();

    var registro = {};
    registro['ID'] = siguienteId_();
    registro['Fecha de creación'] = ahora;
    registro['Fecha del movimiento'] = fecha;
    registro['Hora'] = Utilities.formatDate(ahora, tz, 'HH:mm:ss');
    registro['Registrado por'] = persona;
    registro['Tipo'] = tipo;
    registro['Monto'] = montoGuardado;
    registro['Concepto'] = concepto;
    registro['Método'] = metodo;
    registro['Estado'] = ESTADOS.PENDIENTE;
    registro['Aprobado por Daniel'] = esDaniel;
    registro['Fecha aprobación Daniel'] = esDaniel ? ahora : '';
    registro['Aprobado por Coraima'] = !esDaniel;
    registro['Fecha aprobación Coraima'] = !esDaniel ? ahora : '';
    registro['Saldo después del movimiento'] = '';
    registro['UUID'] = generarUuid();
    registro['Corrige a'] = uuid;

    agregarMovimiento_(registro);
    return api_getEstado();
  } finally {
    lock.releaseLock();
  }
}

/**
 * Cancela un movimiento PENDIENTE propio (quien lo registró se arrepintió
 * antes de que el otro lo aprobara). Queda registrado como "Cancelado".
 * @param {string} uuid
 * @param {string} persona
 * @return {!Object} estado actualizado
 */
function api_cancelarMovimiento(uuid, persona) {
  var lock = LockService.getScriptLock();
  lock.waitLock(20000);
  try {
    validarEnLista(persona, PERSONAS, 'persona');
    var m = buscarPorUuid_(leerMovimientos_(), uuid);
    if (m.estado !== ESTADOS.PENDIENTE) {
      throw new Error('Solo se pueden cancelar movimientos pendientes.');
    }
    if (m.registradoPor !== persona) {
      throw new Error('Solo quien registró el movimiento puede cancelarlo.');
    }
    actualizarPorUuid_(uuid, { 'Estado': ESTADOS.CANCELADO });
    return api_getEstado();
  } finally {
    lock.releaseLock();
  }
}

/* ── Helpers internos ─────────────────────────────────────────── */

/** Serializa un movimiento para el cliente (fechas a strings). */
function serializar_(m) {
  return {
    id: m.id,
    uuid: m.uuid,
    creadoEn: aIso_(m.creadoEn),
    fecha: aFechaSimple_(m.fecha),
    hora: m.hora ? String(m.hora) : '',
    registradoPor: m.registradoPor,
    tipo: m.tipo,
    monto: Number(m.monto) || 0,
    concepto: m.concepto ? String(m.concepto) : '',
    metodo: m.metodo ? String(m.metodo) : '',
    estado: m.estado,
    aprobadoDaniel: !!m.aprobadoDaniel,
    fechaAprobDaniel: aIso_(m.fechaAprobDaniel),
    aprobadoCoraima: !!m.aprobadoCoraima,
    fechaAprobCoraima: aIso_(m.fechaAprobCoraima),
    saldoDespues: m.saldoDespues,
    corrigeA: m.corrigeA || ''
  };
}

function aIso_(v) {
  if (!v) return '';
  if (v instanceof Date) return v.toISOString();
  return String(v);
}

function aFechaSimple_(v) {
  if (v instanceof Date) return Utilities.formatDate(v, Session.getScriptTimeZone(), 'yyyy-MM-dd');
  return String(v).slice(0, 10);
}

/** Siguiente ID incremental. */
function siguienteId_() {
  var max = 0;
  leerMovimientos_().forEach(function (m) {
    var n = Number(m.id) || 0;
    if (n > max) max = n;
  });
  return max + 1;
}

/** Busca un movimiento por UUID o lanza error. */
function buscarPorUuid_(lista, uuid) {
  for (var i = 0; i < lista.length; i++) {
    if (lista[i].uuid === uuid) return lista[i];
  }
  throw new Error('Movimiento no encontrado: ' + uuid);
}
