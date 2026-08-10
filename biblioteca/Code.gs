/**
 * MI BIBLIOTECA — catálogo personal de libros con escáner de ISBN y
 * rastreador de lectura (sesiones con cronómetro, progreso, metas y rachas).
 *
 * Cada libro vive en una de dos listas: "biblioteca" (los que tienes) o
 * "compras" (los que quieres comprar). Al escanear o escribir un ISBN, el
 * servidor busca los datos del libro en Google Books y, si no aparece,
 * en Open Library. Cada sesión de lectura guarda su duración y el avance
 * de páginas; de ahí salen la velocidad, las rachas y las estadísticas.
 *
 * Los datos se guardan en las hojas "Libros" y "Sesiones" de la hoja de
 * cálculo a la que está vinculado este proyecto de Apps Script.
 */

// ═══════════════════ CONFIGURACIÓN — edita solo esto ═══════════════════
var CONFIG = {
  TITULO: 'Mi Biblioteca',
  NOMBRE_HOJA_LIBROS: 'Libros',
  NOMBRE_HOJA_SESIONES: 'Sesiones',
  NOMBRE_HOJA_CITAS: 'Citas',
  // Metas iniciales (después se cambian desde Ajustes en la app).
  METAS_DEFAULT: { minutosDia: 30, librosAnio: 12 }
};
// ═══════════════════════════════════════════════════════════════════════

var LISTAS = ['biblioteca', 'compras'];
var ESTADOS_LECTURA = ['Pendiente', 'Leyendo', 'Leído'];

var COLUMNAS = [
  'id', 'uuid', 'agregadoEn', 'actualizadoEn', 'isbn', 'titulo', 'autores',
  'editorial', 'anio', 'paginas', 'categoria', 'portadaUrl', 'lista',
  'estadoLectura', 'calificacion', 'notas', 'paginaActual', 'terminadoEn',
  'precio', 'tienda', 'prestadoA', 'prestadoEn'
];

var COLUMNAS_SESIONES = [
  'id', 'uuid', 'libroUuid', 'inicio', 'fin', 'duracionSeg', 'paginaInicio', 'paginaFin'
];

var COLUMNAS_CITAS = [
  'id', 'uuid', 'libroUuid', 'texto', 'pagina', 'creadoEn'
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
      .addItem('Preparar hojas de datos', 'prepararHoja')
      .addToUi();
  } catch (e) { /* no hay UI cuando corre como web app */ }
}

function prepararHoja() { obtenerHojaLibros_(); obtenerHojaSesiones_(); obtenerHojaCitas_(); }

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

// ─────────────────────────── Hojas de datos ───────────────────────────

function obtenerLibroSs_() {
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
  return ss;
}

function obtenerHoja_(nombre, columnas) {
  var ss = obtenerLibroSs_();
  var hoja = ss.getSheetByName(nombre);
  if (!hoja) {
    hoja = ss.insertSheet(nombre);
    hoja.getRange(1, 1, 1, columnas.length).setValues([columnas]).setFontWeight('bold');
    hoja.setFrozenRows(1);
  }
  return hoja;
}

function obtenerHojaLibros_() { return obtenerHoja_(CONFIG.NOMBRE_HOJA_LIBROS, COLUMNAS); }
function obtenerHojaSesiones_() { return obtenerHoja_(CONFIG.NOMBRE_HOJA_SESIONES, COLUMNAS_SESIONES); }
function obtenerHojaCitas_() { return obtenerHoja_(CONFIG.NOMBRE_HOJA_CITAS, COLUMNAS_CITAS); }

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
    l.paginaActual = Number(l.paginaActual) || 0;
    l.calificacion = Number(l.calificacion) || 0;
    l.agregadoEn = normalizarStamp_(l.agregadoEn);
    l.actualizadoEn = normalizarStamp_(l.actualizadoEn);
    l.terminadoEn = normalizarStamp_(l.terminadoEn);
    l.precio = Number(l.precio) || 0;
    l.tienda = String(l.tienda || '');
    l.prestadoA = String(l.prestadoA || '');
    l.prestadoEn = normalizarStamp_(l.prestadoEn);
    return l;
  });
}

function leerCitas_(hoja) {
  var ultima = hoja.getLastRow();
  if (ultima < 2) return [];
  var valores = hoja.getRange(2, 1, ultima - 1, COLUMNAS_CITAS.length).getValues();
  return valores.map(function (fila) {
    var c = {};
    COLUMNAS_CITAS.forEach(function (col, i) { c[col] = fila[i]; });
    c.id = Number(c.id);
    c.pagina = Number(c.pagina) || 0;
    c.texto = String(c.texto || '');
    c.creadoEn = normalizarStamp_(c.creadoEn);
    return c;
  });
}

function leerSesiones_(hoja) {
  var ultima = hoja.getLastRow();
  if (ultima < 2) return [];
  var valores = hoja.getRange(2, 1, ultima - 1, COLUMNAS_SESIONES.length).getValues();
  return valores.map(function (fila) {
    var s = {};
    COLUMNAS_SESIONES.forEach(function (col, i) { s[col] = fila[i]; });
    s.id = Number(s.id);
    s.duracionSeg = Number(s.duracionSeg) || 0;
    s.paginaInicio = Number(s.paginaInicio) || 0;
    s.paginaFin = Number(s.paginaFin) || 0;
    s.inicio = normalizarStamp_(s.inicio);
    s.fin = normalizarStamp_(s.fin);
    return s;
  });
}

function normalizarStamp_(v) {
  if (v instanceof Date) return v.toISOString();
  return String(v || '');
}

function filaDeUuid_(items, uuid) {
  for (var i = 0; i < items.length; i++) {
    if (String(items[i].uuid) === String(uuid)) return i;
  }
  return -1;
}

function leerMetas_() {
  try {
    var crudo = PropertiesService.getScriptProperties().getProperty('METAS');
    if (crudo) {
      var m = JSON.parse(crudo);
      if (m && m.minutosDia > 0 && m.librosAnio > 0) return m;
    }
  } catch (e) {}
  return { minutosDia: CONFIG.METAS_DEFAULT.minutosDia, librosAnio: CONFIG.METAS_DEFAULT.librosAnio };
}

// ─────────────────────────── Búsqueda de metadatos ───────────────────────────

function api_buscarIsbn(isbn) {
  var limpio = normalizarIsbn(isbn);
  if (!limpio) throw new Error('Escribe un ISBN');
  var libro = null;
  var g = buscarGoogleBooks_('isbn:' + limpio);
  if (g && g.length) libro = g[0];
  // Completa lo que falte con Open Library (mangas y ediciones en español
  // suelen tener ficha incompleta en Google Books).
  if (!libro || !libro.portadaUrl || !libro.paginas || !libro.titulo) {
    var ol = buscarOpenLibrary_(limpio);
    if (!libro) libro = ol;
    else if (ol) {
      if (!libro.titulo) libro.titulo = ol.titulo;
      if (!libro.autores) libro.autores = ol.autores;
      if (!libro.editorial) libro.editorial = ol.editorial;
      if (!libro.anio) libro.anio = ol.anio;
      if (!libro.paginas) libro.paginas = ol.paginas;
      if (!libro.portadaUrl) libro.portadaUrl = ol.portadaUrl;
    }
  }
  if (libro) {
    libro.isbn = libro.isbn || limpio;
    enriquecer_(libro);
    return { encontrado: true, libro: libro };
  }
  return { encontrado: false, libro: { isbn: limpio, titulo: '', autores: '', editorial: '', anio: '', paginas: 0, categoria: '', portadaUrl: '' } };
}

/**
 * Rellena portada y páginas faltantes probando más fuentes:
 * 1) archivo de portadas de Open Library por ISBN,
 * 2) buscador de Open Library por título+autor,
 * 3) otras ediciones en Google Books por título.
 */
function enriquecer_(libro) {
  if (!libro.portadaUrl && libro.isbn) {
    var urlPortada = 'https://covers.openlibrary.org/b/isbn/' + libro.isbn + '-L.jpg';
    if (urlExiste_(urlPortada + '?default=false')) libro.portadaUrl = urlPortada;
  }
  if ((!libro.portadaUrl || !libro.paginas) && libro.titulo) {
    try {
      var q = libro.titulo + (libro.autores ? ' ' + libro.autores.split(',')[0] : '');
      var resp = UrlFetchApp.fetch('https://openlibrary.org/search.json?limit=5&fields=cover_i,number_of_pages_median&q=' + encodeURIComponent(q), { muteHttpExceptions: true });
      if (resp.getResponseCode() === 200) {
        var docs = (JSON.parse(resp.getContentText()).docs) || [];
        for (var i = 0; i < docs.length; i++) {
          if (!libro.portadaUrl && docs[i].cover_i) libro.portadaUrl = 'https://covers.openlibrary.org/b/id/' + docs[i].cover_i + '-L.jpg';
          if (!libro.paginas && docs[i].number_of_pages_median) libro.paginas = Number(docs[i].number_of_pages_median) || 0;
          if (libro.portadaUrl && libro.paginas) break;
        }
      }
    } catch (e) {}
  }
  if ((!libro.portadaUrl || !libro.paginas) && libro.titulo) {
    var otras = buscarGoogleBooks_('intitle:' + libro.titulo) || [];
    for (var j = 0; j < otras.length; j++) {
      if (!libro.portadaUrl && otras[j].portadaUrl) libro.portadaUrl = otras[j].portadaUrl;
      if (!libro.paginas && otras[j].paginas) libro.paginas = otras[j].paginas;
      if (libro.portadaUrl && libro.paginas) break;
    }
  }
}

function urlExiste_(url) {
  try {
    return UrlFetchApp.fetch(url, { muteHttpExceptions: true }).getResponseCode() === 200;
  } catch (e) { return false; }
}

/** Reintenta portada/páginas para un libro ya guardado. */
function api_enriquecerLibro(uuid) {
  var lock = LockService.getScriptLock();
  lock.waitLock(20000);
  try {
    var hoja = obtenerHojaLibros_();
    var libros = leerLibros_(hoja);
    var idx = filaDeUuid_(libros, uuid);
    if (idx === -1) throw new Error('Libro no encontrado');
    var l = libros[idx];
    var meta = { isbn: l.isbn, titulo: l.titulo, autores: l.autores, paginas: l.paginas, portadaUrl: l.portadaUrl };
    enriquecer_(meta);
    var cambios = {};
    if (meta.portadaUrl && !l.portadaUrl) cambios.portadaUrl = meta.portadaUrl;
    if (meta.paginas && !l.paginas) cambios.paginas = meta.paginas;
    var encontrado = Object.keys(cambios).length > 0;
    if (encontrado) actualizarFila_(hoja, libros, idx, cambios);
    return { encontrado: encontrado, estado: api_getEstado() };
  } finally {
    lock.releaseLock();
  }
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
  return {
    libros: leerLibros_(obtenerHojaLibros_()),
    sesiones: leerSesiones_(obtenerHojaSesiones_()),
    citas: leerCitas_(obtenerHojaCitas_()),
    metas: leerMetas_()
  };
}

function api_agregarLibro(payload) {
  var lock = LockService.getScriptLock();
  lock.waitLock(20000);
  try {
    var lista = validarEnLista(limpiarTexto(payload.lista, 20), LISTAS, 'lista');
    var titulo = limpiarTexto(payload.titulo, 200);
    if (!titulo) throw new Error('El libro necesita un título');
    var isbn = payload.isbn ? normalizarIsbn(payload.isbn) : '';

    var hoja = obtenerHojaLibros_();
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
      notas: limpiarTexto(payload.notas, 1000),
      paginaActual: 0,
      terminadoEn: '',
      precio: Math.max(0, Math.round((Number(payload.precio) || 0) * 100) / 100),
      tienda: limpiarTexto(payload.tienda, 80),
      prestadoA: '',
      prestadoEn: ''
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
    var hoja = obtenerHojaLibros_();
    var libros = leerLibros_(hoja);
    var idx = filaDeUuid_(libros, uuid);
    if (idx === -1) throw new Error('Libro no encontrado');
    var libro = libros[idx];

    var limpios = {};
    if (cambios.lista != null) limpios.lista = validarEnLista(String(cambios.lista), LISTAS, 'lista');
    if (cambios.estadoLectura != null) {
      var est = validarEnLista(String(cambios.estadoLectura), ESTADOS_LECTURA, 'estado de lectura');
      limpios.estadoLectura = est;
      // Al marcar "Leído" queda la fecha (para la meta anual) y el avance completo.
      if (est === 'Leído') {
        limpios.terminadoEn = libro.terminadoEn || ahoraIso();
        if (libro.paginas > 0) limpios.paginaActual = libro.paginas;
      } else {
        limpios.terminadoEn = '';
      }
    }
    if (cambios.calificacion != null) {
      var cal = Math.round(Number(cambios.calificacion));
      if (isNaN(cal) || cal < 0 || cal > 5) throw new Error('La calificación va de 0 a 5');
      limpios.calificacion = cal;
    }
    if (cambios.paginaActual != null) {
      var pag = Math.round(Number(cambios.paginaActual));
      if (isNaN(pag) || pag < 0) throw new Error('Página inválida');
      if (libro.paginas > 0 && pag > libro.paginas) pag = libro.paginas;
      limpios.paginaActual = pag;
    }
    if (cambios.paginas != null) {
      var tot = Math.round(Number(cambios.paginas));
      if (isNaN(tot) || tot < 0) throw new Error('Número de páginas inválido');
      limpios.paginas = tot;
    }
    if (cambios.notas != null) limpios.notas = limpiarTexto(cambios.notas, 1000);
    if (cambios.categoria != null) limpios.categoria = limpiarTexto(cambios.categoria, 60);
    if (cambios.precio != null) {
      var pr = Number(cambios.precio);
      if (isNaN(pr) || pr < 0) throw new Error('Precio inválido');
      limpios.precio = Math.round(pr * 100) / 100;
    }
    if (cambios.tienda != null) limpios.tienda = limpiarTexto(cambios.tienda, 80);
    if (cambios.portadaUrl != null) limpios.portadaUrl = limpiarTexto(cambios.portadaUrl, 500);
    if (cambios.prestadoA != null) {
      var pa = limpiarTexto(cambios.prestadoA, 60);
      limpios.prestadoA = pa;
      limpios.prestadoEn = pa ? ahoraIso() : '';
    }
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
    var hoja = obtenerHojaLibros_();
    var libros = leerLibros_(hoja);
    var idx = filaDeUuid_(libros, uuid);
    if (idx === -1) throw new Error('Libro no encontrado');
    hoja.deleteRow(idx + 2);
    // Sus sesiones y citas también se van, para no dejar datos huérfanos.
    var hojaSes = obtenerHojaSesiones_();
    var sesiones = leerSesiones_(hojaSes);
    for (var i = sesiones.length - 1; i >= 0; i--) {
      if (String(sesiones[i].libroUuid) === String(uuid)) hojaSes.deleteRow(i + 2);
    }
    var hojaCitas = obtenerHojaCitas_();
    var citas = leerCitas_(hojaCitas);
    for (var j = citas.length - 1; j >= 0; j--) {
      if (String(citas[j].libroUuid) === String(uuid)) hojaCitas.deleteRow(j + 2);
    }
    return api_getEstado();
  } finally {
    lock.releaseLock();
  }
}

// ─────────────────────────── Sesiones de lectura ───────────────────────────

function api_registrarSesion(payload) {
  var lock = LockService.getScriptLock();
  lock.waitLock(20000);
  try {
    var hojaLibros = obtenerHojaLibros_();
    var libros = leerLibros_(hojaLibros);
    var idx = filaDeUuid_(libros, payload.libroUuid);
    if (idx === -1) throw new Error('Libro no encontrado');
    var libro = libros[idx];

    var dur = Math.round(Number(payload.duracionSeg));
    if (isNaN(dur) || dur < 10) throw new Error('La sesión es demasiado corta para guardarse');
    if (dur > 12 * 3600) dur = 12 * 3600;

    var pagInicio = Math.max(0, Math.round(Number(payload.paginaInicio)) || 0);
    var pagFin = Math.max(0, Math.round(Number(payload.paginaFin)) || 0);
    if (libro.paginas > 0 && pagFin > libro.paginas) pagFin = libro.paginas;
    if (pagFin && pagInicio > pagFin) pagInicio = pagFin;

    var inicio = String(payload.inicio || '');
    if (!/^\d{4}-\d{2}-\d{2}T/.test(inicio)) inicio = new Date(Date.now() - dur * 1000).toISOString();

    var hojaSes = obtenerHojaSesiones_();
    var sesiones = leerSesiones_(hojaSes);
    var maxId = sesiones.reduce(function (a, s) { return Math.max(a, s.id || 0); }, 0);
    var fila = {
      id: maxId + 1,
      uuid: generarUuid(),
      libroUuid: libro.uuid,
      inicio: inicio,
      fin: ahoraIso(),
      duracionSeg: dur,
      paginaInicio: pagInicio,
      paginaFin: pagFin
    };
    hojaSes.appendRow(COLUMNAS_SESIONES.map(function (c) { return fila[c]; }));

    // El libro avanza: página actual y, si estaba pendiente, pasa a "Leyendo".
    var cambios = {};
    if (pagFin > 0) cambios.paginaActual = pagFin;
    if (libro.estadoLectura === 'Pendiente') cambios.estadoLectura = 'Leyendo';
    if (payload.termine === true) {
      cambios.estadoLectura = 'Leído';
      cambios.terminadoEn = ahoraIso();
      if (libro.paginas > 0) cambios.paginaActual = libro.paginas;
    }
    if (Object.keys(cambios).length) actualizarFila_(hojaLibros, libros, idx, cambios);

    return api_getEstado();
  } finally {
    lock.releaseLock();
  }
}

function api_eliminarSesion(uuid) {
  var lock = LockService.getScriptLock();
  lock.waitLock(20000);
  try {
    var hoja = obtenerHojaSesiones_();
    var sesiones = leerSesiones_(hoja);
    var idx = filaDeUuid_(sesiones, uuid);
    if (idx === -1) throw new Error('Sesión no encontrada');
    hoja.deleteRow(idx + 2);
    return api_getEstado();
  } finally {
    lock.releaseLock();
  }
}

// ─────────────────────────── Citas favoritas ───────────────────────────

function api_agregarCita(payload) {
  var lock = LockService.getScriptLock();
  lock.waitLock(20000);
  try {
    var libros = leerLibros_(obtenerHojaLibros_());
    if (filaDeUuid_(libros, payload.libroUuid) === -1) throw new Error('Libro no encontrado');
    var texto = String(payload.texto == null ? '' : payload.texto).trim().slice(0, 500);
    if (!texto) throw new Error('Escribe la cita');
    var pagina = Math.max(0, Math.round(Number(payload.pagina)) || 0);

    var hoja = obtenerHojaCitas_();
    var citas = leerCitas_(hoja);
    var maxId = citas.reduce(function (a, c) { return Math.max(a, c.id || 0); }, 0);
    var fila = {
      id: maxId + 1,
      uuid: generarUuid(),
      libroUuid: String(payload.libroUuid),
      texto: texto,
      pagina: pagina,
      creadoEn: ahoraIso()
    };
    hoja.appendRow(COLUMNAS_CITAS.map(function (c) { return fila[c]; }));
    return api_getEstado();
  } finally {
    lock.releaseLock();
  }
}

function api_eliminarCita(uuid) {
  var lock = LockService.getScriptLock();
  lock.waitLock(20000);
  try {
    var hoja = obtenerHojaCitas_();
    var citas = leerCitas_(hoja);
    var idx = filaDeUuid_(citas, uuid);
    if (idx === -1) throw new Error('Cita no encontrada');
    hoja.deleteRow(idx + 2);
    return api_getEstado();
  } finally {
    lock.releaseLock();
  }
}

// ─────────────────────────── Comparador de precios ───────────────────────────

/**
 * Busca precios para un libro de la lista de compras.
 * Buscalibre se consulta automáticamente (precio real); para las tiendas
 * que bloquean consultas automatizadas (Amazon, Google Shopping…) se
 * devuelven enlaces directos a la búsqueda exacta.
 */
function api_compararPrecios(consulta) {
  var isbn = '';
  try { isbn = consulta && consulta.isbn ? normalizarIsbn(consulta.isbn) : ''; } catch (e) {}
  var titulo = limpiarTexto(consulta && consulta.titulo, 120);
  if (!isbn && !titulo) throw new Error('Falta el ISBN o el título');

  var resultados = buscarBuscalibre_(isbn, titulo);
  var q = encodeURIComponent(isbn || titulo);
  var enlaces = [
    { tienda: 'Amazon México', url: 'https://www.amazon.com.mx/s?k=' + q, icono: 'shopping_cart' },
    { tienda: 'Google Shopping', url: 'https://www.google.com/search?tbm=shop&q=' + q, icono: 'storefront' },
    { tienda: 'Gandhi', url: 'https://www.gandhi.com.mx/busqueda?query=' + q, icono: 'store' },
    { tienda: 'MercadoLibre', url: 'https://listado.mercadolibre.com.mx/' + (isbn || q), icono: 'sell' }
  ];
  return { resultados: resultados, enlaces: enlaces };
}

function buscarBuscalibre_(isbn, titulo) {
  var items = fetchBuscalibre_(isbn || titulo);
  if (!items.length && isbn && titulo) items = fetchBuscalibre_(titulo);
  // Se conserva el orden de relevancia de Buscalibre; solo la coincidencia
  // exacta de ISBN sube al frente (ordenar por precio metía relleno barato).
  if (isbn) {
    items.forEach(function (it) { it.coincideIsbn = it.isbn === isbn; });
    items.sort(function (a, b) { return (b.coincideIsbn ? 1 : 0) - (a.coincideIsbn ? 1 : 0); });
  }
  return items.slice(0, 5);
}

function fetchBuscalibre_(q) {
  try {
    var resp = UrlFetchApp.fetch('https://www.buscalibre.com.mx/libros/search?q=' + encodeURIComponent(q), {
      muteHttpExceptions: true,
      followRedirects: true,
      headers: { 'User-Agent': 'Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Mobile Safari/537.36' }
    });
    if (resp.getResponseCode() !== 200) return [];
    var html = resp.getContentText();
    var bloques = html.split('class="box-producto').slice(1, 9);
    var items = [];
    bloques.forEach(function (b) {
      var isbnM = (b.match(/data-isbn="(\d{10,13})"/) || [])[1] || '';
      var urlM = (b.match(/href="(https:\/\/www\.buscalibre\.com\.mx\/[^"]+)"/) || [])[1] || '';
      var titM = (b.match(/<h3 class="title">([^<]+)<\/h3>/) || [])[1] || '';
      var precioM = (b.match(/class="precioAhora[^"]*">\s*\$?\s*([\d.,]+)/) || [])[1] || '';
      var precio = Number(String(precioM).replace(/,/g, ''));
      if (titM && precio > 0 && urlM) {
        items.push({ tienda: 'Buscalibre', titulo: limpiarTexto(titM, 120), isbn: isbnM, precio: Math.round(precio * 100) / 100, url: urlM, coincideIsbn: false });
      }
    });
    return items;
  } catch (e) { return []; }
}

function api_setMetas(metas) {
  var minutos = Math.round(Number(metas && metas.minutosDia));
  var librosAnio = Math.round(Number(metas && metas.librosAnio));
  if (isNaN(minutos) || minutos < 5 || minutos > 600) throw new Error('La meta diaria va de 5 a 600 minutos');
  if (isNaN(librosAnio) || librosAnio < 1 || librosAnio > 365) throw new Error('La meta anual va de 1 a 365 libros');
  PropertiesService.getScriptProperties().setProperty('METAS', JSON.stringify({ minutosDia: minutos, librosAnio: librosAnio }));
  return api_getEstado();
}
