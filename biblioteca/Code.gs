/**
 * MI BIBLIOTECA — catálogo personal de libros con escáner de ISBN.
 *
 * Cada libro vive en una de dos listas: "biblioteca" (los que tienes) o
 * "compras" (los que quieres comprar). Al escanear o escribir un ISBN, el
 * servidor busca los datos del libro en Google Books y, si no aparece,
 * en Open Library. Los datos se guardan en la hoja "Libros" de la hoja de
 * cálculo a la que está vinculado este proyecto de Apps Script.
 */

// ═══════════════════ CONFIGURACIÓN — edita solo esto ═══════════════════
var CONFIG = {
  TITULO: 'Mi Biblioteca',
  NOMBRE_HOJA: 'Libros'
};
// ═══════════════════════════════════════════════════════════════════════

var LISTAS = ['biblioteca', 'compras'];
var ESTADOS_LECTURA = ['Pendiente', 'Leyendo', 'Leído'];

var COLUMNAS = [
  'id', 'uuid', 'agregadoEn', 'actualizadoEn', 'isbn', 'titulo', 'autores',
  'editorial', 'anio', 'paginas', 'categoria', 'portadaUrl', 'lista',
  'estadoLectura', 'calificacion', 'notas'
];

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
  return JSON.stringify({ titulo: CONFIG.TITULO });
}

function onOpen() {
  try {
    SpreadsheetApp.getUi().createMenu(CONFIG.TITULO)
      .addItem('Preparar hoja de libros', 'prepararHoja')
      .addToUi();
  } catch (e) { /* no hay UI cuando corre como web app */ }
}

function prepararHoja() { obtenerHoja_(); }

// ─────────────────────────── Utilidades ───────────────────────────

function generarUuid() { return Utilities.getUuid(); }

function ahoraIso() { return new Date().toISOString(); }

function limpiarTexto(texto, max) {
  return String(texto == null ? '' : texto).replace(/\s+/g, ' ').trim().slice(0, max || 200);
}

function validarEnLista(valor, lista, nombreCampo) {
  if (lista.indexOf(valor) === -1) throw new Error('Valor no permitido para ' + (nombreCampo || 'campo') + ': ' + valor);
  return valor;
}

/**
 * Normaliza un ISBN: quita guiones/espacios, valida el dígito de control
 * y convierte ISBN-10 a ISBN-13. Devuelve '' si viene vacío.
 * Lanza error si el código no es un ISBN válido.
 */
function normalizarIsbn(isbn) {
  var s = String(isbn == null ? '' : isbn).replace(/[^0-9Xx]/g, '').toUpperCase();
  if (!s) return '';
  if (s.length === 10) {
    var suma10 = 0;
    for (var i = 0; i < 10; i++) {
      var d = s.charAt(i) === 'X' ? 10 : Number(s.charAt(i));
      if (isNaN(d) || (s.charAt(i) === 'X' && i !== 9)) throw new Error('ISBN inválido');
      suma10 += (10 - i) * d;
    }
    if (suma10 % 11 !== 0) throw new Error('ISBN inválido (dígito de control)');
    var nucleo = '978' + s.slice(0, 9);
    return nucleo + digitoEan13_(nucleo);
  }
  if (s.length === 13) {
    if (s.indexOf('X') > -1) throw new Error('ISBN inválido');
    if (digitoEan13_(s.slice(0, 12)) !== s.charAt(12)) throw new Error('ISBN inválido (dígito de control)');
    return s;
  }
  throw new Error('Un ISBN tiene 10 o 13 dígitos');
}

function digitoEan13_(doce) {
  var suma = 0;
  for (var i = 0; i < 12; i++) suma += Number(doce.charAt(i)) * (i % 2 === 0 ? 1 : 3);
  return String((10 - (suma % 10)) % 10);
}

// ─────────────────────────── Hoja de datos ───────────────────────────

function obtenerHoja_() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  if (!ss) {
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
  }
  return hoja;
}

function leerLibros_(hoja) {
  var ultima = hoja.getLastRow();
  if (ultima < 2) return [];
  var valores = hoja.getRange(2, 1, ultima - 1, COLUMNAS.length).getValues();
  return valores.map(function (fila) {
    var l = {};
    COLUMNAS.forEach(function (col, i) { l[col] = fila[i]; });
    l.id = Number(l.id);
    l.isbn = String(l.isbn || '');
    l.anio = l.anio ? String(l.anio).slice(0, 4) : '';
    l.paginas = Number(l.paginas) || 0;
    l.calificacion = Number(l.calificacion) || 0;
    l.agregadoEn = normalizarStamp_(l.agregadoEn);
    l.actualizadoEn = normalizarStamp_(l.actualizadoEn);
    return l;
  });
}

function normalizarStamp_(v) {
  if (v instanceof Date) return v.toISOString();
  return String(v || '');
}

function filaDeUuid_(libros, uuid) {
  for (var i = 0; i < libros.length; i++) {
    if (String(libros[i].uuid) === String(uuid)) return i;
  }
  return -1;
}

// ─────────────────────────── Búsqueda de metadatos ───────────────────────────

function api_buscarIsbn(isbn) {
  var limpio = normalizarIsbn(isbn);
  if (!limpio) throw new Error('Escribe un ISBN');
  var meta = buscarGoogleBooks_('isbn:' + limpio);
  if (meta && meta.length) {
    var m = meta[0];
    m.isbn = m.isbn || limpio;
    return { encontrado: true, libro: m };
  }
  var ol = buscarOpenLibrary_(limpio);
  if (ol) return { encontrado: true, libro: ol };
  return { encontrado: false, libro: { isbn: limpio, titulo: '', autores: '', editorial: '', anio: '', paginas: 0, categoria: '', portadaUrl: '' } };
}

function api_buscarTitulo(consulta) {
  var q = limpiarTexto(consulta, 120);
  if (q.length < 2) return [];
  return buscarGoogleBooks_(q) || [];
}

function buscarGoogleBooks_(q) {
  try {
    var url = 'https://www.googleapis.com/books/v1/volumes?maxResults=8&printType=books&q=' + encodeURIComponent(q);
    var resp = UrlFetchApp.fetch(url, { muteHttpExceptions: true });
    if (resp.getResponseCode() !== 200) return null;
    var datos = JSON.parse(resp.getContentText());
    if (!datos.items || !datos.items.length) return null;
    return datos.items.map(function (item) {
      var v = item.volumeInfo || {};
      var isbn13 = '', isbn10 = '';
      (v.industryIdentifiers || []).forEach(function (idn) {
        if (idn.type === 'ISBN_13') isbn13 = idn.identifier;
        if (idn.type === 'ISBN_10') isbn10 = idn.identifier;
      });
      var isbn = '';
      try { isbn = normalizarIsbn(isbn13 || isbn10); } catch (e) { isbn = ''; }
      var portada = ((v.imageLinks || {}).thumbnail || '').replace(/^http:/, 'https:');
      return {
        isbn: isbn,
        titulo: limpiarTexto(v.title, 200),
        autores: limpiarTexto((v.authors || []).join(', '), 200),
        editorial: limpiarTexto(v.publisher, 120),
        anio: String(v.publishedDate || '').slice(0, 4),
        paginas: Number(v.pageCount) || 0,
        categoria: limpiarTexto((v.categories || [])[0], 60),
        portadaUrl: portada
      };
    });
  } catch (e) {
    return null;
  }
}

function buscarOpenLibrary_(isbn13) {
  try {
    var url = 'https://openlibrary.org/api/books?format=json&jscmd=data&bibkeys=ISBN:' + isbn13;
    var resp = UrlFetchApp.fetch(url, { muteHttpExceptions: true });
    if (resp.getResponseCode() !== 200) return null;
    var datos = JSON.parse(resp.getContentText());
    var d = datos['ISBN:' + isbn13];
    if (!d) return null;
    return {
      isbn: isbn13,
      titulo: limpiarTexto(d.title, 200),
      autores: limpiarTexto((d.authors || []).map(function (a) { return a.name; }).join(', '), 200),
      editorial: limpiarTexto(((d.publishers || [])[0] || {}).name, 120),
      anio: String(d.publish_date || '').replace(/^.*?(\d{4}).*$/, '$1'),
      paginas: Number(d.number_of_pages) || 0,
      categoria: '',
      portadaUrl: ((d.cover || {}).medium || (d.cover || {}).small || '').replace(/^http:/, 'https:')
    };
  } catch (e) {
    return null;
  }
}

// ─────────────────────────── API para la app ───────────────────────────

function api_getEstado() {
  return { libros: leerLibros_(obtenerHoja_()) };
}

function api_agregarLibro(payload) {
  var lock = LockService.getScriptLock();
  lock.waitLock(20000);
  try {
    var lista = validarEnLista(limpiarTexto(payload.lista, 20), LISTAS, 'lista');
    var titulo = limpiarTexto(payload.titulo, 200);
    if (!titulo) throw new Error('El libro necesita un título');
    var isbn = payload.isbn ? normalizarIsbn(payload.isbn) : '';

    var hoja = obtenerHoja_();
    var libros = leerLibros_(hoja);

    // Duplicados por ISBN: si ya lo tienes avisa; si estaba "por comprar"
    // y ahora lo agregas a la biblioteca, se mueve en lugar de duplicarse.
    if (isbn) {
      for (var i = 0; i < libros.length; i++) {
        if (libros[i].isbn === isbn) {
          if (libros[i].lista === 'biblioteca') throw new Error('Ese libro ya está en tu biblioteca: ' + libros[i].titulo);
          if (lista === 'compras') throw new Error('Ese libro ya está en tu lista de compras: ' + libros[i].titulo);
          return actualizarFila_(hoja, libros, i, { lista: 'biblioteca' });
        }
      }
    }

    var maxId = libros.reduce(function (a, l) { return Math.max(a, l.id || 0); }, 0);
    var ahora = ahoraIso();
    var fila = {
      id: maxId + 1,
      uuid: generarUuid(),
      agregadoEn: ahora,
      actualizadoEn: ahora,
      isbn: isbn,
      titulo: titulo,
      autores: limpiarTexto(payload.autores, 200),
      editorial: limpiarTexto(payload.editorial, 120),
      anio: limpiarTexto(payload.anio, 4),
      paginas: Number(payload.paginas) || 0,
      categoria: limpiarTexto(payload.categoria, 60),
      portadaUrl: limpiarTexto(payload.portadaUrl, 500),
      lista: lista,
      estadoLectura: 'Pendiente',
      calificacion: 0,
      notas: limpiarTexto(payload.notas, 1000)
    };
    hoja.appendRow(COLUMNAS.map(function (c) { return fila[c]; }));
    return api_getEstado();
  } finally {
    lock.releaseLock();
  }
}

function api_actualizarLibro(uuid, cambios) {
  var lock = LockService.getScriptLock();
  lock.waitLock(20000);
  try {
    var hoja = obtenerHoja_();
    var libros = leerLibros_(hoja);
    var idx = filaDeUuid_(libros, uuid);
    if (idx === -1) throw new Error('Libro no encontrado');

    var limpios = {};
    if (cambios.lista != null) limpios.lista = validarEnLista(String(cambios.lista), LISTAS, 'lista');
    if (cambios.estadoLectura != null) limpios.estadoLectura = validarEnLista(String(cambios.estadoLectura), ESTADOS_LECTURA, 'estado de lectura');
    if (cambios.calificacion != null) {
      var cal = Math.round(Number(cambios.calificacion));
      if (isNaN(cal) || cal < 0 || cal > 5) throw new Error('La calificación va de 0 a 5');
      limpios.calificacion = cal;
    }
    if (cambios.notas != null) limpios.notas = limpiarTexto(cambios.notas, 1000);
    if (cambios.categoria != null) limpios.categoria = limpiarTexto(cambios.categoria, 60);
    if (cambios.titulo != null) {
      var t = limpiarTexto(cambios.titulo, 200);
      if (!t) throw new Error('El título no puede quedar vacío');
      limpios.titulo = t;
    }
    if (cambios.autores != null) limpios.autores = limpiarTexto(cambios.autores, 200);
    if (!Object.keys(limpios).length) throw new Error('Nada que actualizar');

    return actualizarFila_(hoja, libros, idx, limpios);
  } finally {
    lock.releaseLock();
  }
}

function actualizarFila_(hoja, libros, idx, cambios) {
  var filaNum = idx + 2; // +1 encabezado, +1 índice base 1
  cambios.actualizadoEn = ahoraIso();
  Object.keys(cambios).forEach(function (campo) {
    var col = COLUMNAS.indexOf(campo);
    if (col > -1) hoja.getRange(filaNum, col + 1).setValue(cambios[campo]);
  });
  return api_getEstado();
}

function api_eliminarLibro(uuid) {
  var lock = LockService.getScriptLock();
  lock.waitLock(20000);
  try {
    var hoja = obtenerHoja_();
    var libros = leerLibros_(hoja);
    var idx = filaDeUuid_(libros, uuid);
    if (idx === -1) throw new Error('Libro no encontrado');
    hoja.deleteRow(idx + 2);
    return api_getEstado();
  } finally {
    lock.releaseLock();
  }
}
