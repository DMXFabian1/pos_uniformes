"""La hoja de conteo en papel carta: el formato de la tira, de a tres por fila.

Hasta el 2026-09-10 la hoja salía en la impresora de tickets: tiras de 80 mm,
una por producto. El formato de esa tira es el bueno (Daniel lo diseñó y lo
usa): por prenda, una tabla **Talla | Exist. | Pedido**, con el nombre limpio,
la pieza y los colores. Esta hoja lo conserva tal cual y lo acomoda de a
**tres tarjetas por fila** en carta, para la HP. Cada prenda va **numerada
igual que en la pantalla de captura** (las dos leen
`conteo_jornada_service.alcance`).

Todo aquí es puro: recibe los grupos y devuelve HTML. Imprimir es cosa de la
UI (`ui/helpers/conteo_hoja_carta_print_helper.py`).
"""

from __future__ import annotations

from datetime import date
from html import escape

# Tarjetas por fila en la hoja carta. Tres deja espacio para escribir a mano
# en Exist. y Pedido; cuatro quedaba apretado.
TARJETAS_POR_FILA = 3

# Alturas estimadas en puntos, para decidir dónde cortar página SIN partir
# una tarjeta a la mitad (QTextDocument sí parte tablas entre páginas).
_PT_TITULO = 40      # renglón del nombre (puede ser de dos líneas)
_PT_SUB = 13         # pieza · colores
_PT_CABECERA = 18    # Talla | Exist. | Pedido
_PT_FILA = 20        # una talla
_PT_SEPARACION = 10  # aire entre filas de tarjetas
# Carta: 792 pt de alto, márgenes 12 mm arriba/abajo (~68 pt) → ~724 pt
# útiles. La primera página además carga el encabezado de la hoja (~80 pt).
PT_UTIL_PRIMERA = 640
PT_UTIL_SIGUIENTES = 710
PT_UTIL_POR_PAGINA = PT_UTIL_PRIMERA  # compatibilidad

_ESTILO = """
<style>
  body { font-family: Helvetica, Arial, sans-serif; color: #000; }
  h1 { font-size: 16pt; margin: 0 0 2pt 0; }
  p.meta { font-size: 10pt; color: #333; margin: 0 0 3pt 0; }
  p.regla { font-size: 9.5pt; font-weight: bold; margin: 0 0 8pt 0; }
  p.pie { font-size: 9pt; color: #333; margin-top: 10pt; }
</style>
"""

# QTextDocument (el motor que imprime) ignora casi todo el CSS de tablas:
# bordes, alturas y fondos van como ATRIBUTOS HTML, que sí respeta.
_TARJETA_ABRE = '<table border="1" cellspacing="0" cellpadding="4" width="100%" bordercolor="#000000">'
_FONDO_TITULO = "#dddddd"
_FONDO_CAB = "#eeeeee"


def nombre_para_hoja(producto_raw: str, titulo: str, tipo_pieza: str = "") -> str:
    """El nombre limpio, igual que en la tira térmica: sin la escuela, sin
    "Ad hoc", sin lo que sigue al "|" y sin espacios dobles."""
    import re

    producto = str(producto_raw or "").split("|")[0].strip()
    if titulo:
        producto = re.sub(re.escape(titulo), "", producto, flags=re.IGNORECASE).strip()
    producto = re.sub(r"\bAd\s+hoc\b", "", producto, flags=re.IGNORECASE).strip()
    producto = re.sub(r"\s{2,}", " ", producto).strip(" ·-")
    return producto or (tipo_pieza or str(producto_raw or ""))


def _subtitulo(g: dict, nombre: str) -> str:
    variantes = g["variantes"]
    tipo = str(g.get("tipo_pieza") or "")
    colores = sorted({
        str(getattr(v, "color", "") or "") for v in variantes
        if getattr(v, "color", "") and str(getattr(v, "color", "")).lower() not in ("sin color", "")
    })
    partes = [tipo if tipo and tipo.lower() not in nombre.lower() else "", ", ".join(colores)]
    return " · ".join(x for x in partes if x)


def altura_tarjeta_pt(g: dict, titulo: str) -> int:
    """Cuánto mide (aprox.) una tarjeta, para la paginación."""
    nombre = nombre_para_hoja(g.get("producto_nombre", ""), titulo, str(g.get("tipo_pieza") or ""))
    alto = _PT_TITULO + _PT_CABECERA + _PT_FILA * len(g["variantes"])
    if _subtitulo(g, nombre):
        alto += _PT_SUB
    return alto


def _tarjeta(numero: int, total: int, g: dict, titulo: str) -> str:
    """Una prenda: el formato de la tira térmica, en tarjeta.

        N/total · Nombre
        tipo de pieza · colores
        Talla | Exist. | Pedido
        ...una fila por talla
    """
    variantes = g["variantes"]
    tipo = str(g.get("tipo_pieza") or "")
    nombre = nombre_para_hoja(g.get("producto_nombre", ""), titulo, tipo)
    sub = _subtitulo(g, nombre)
    filas = [
        f'<tr><td colspan="3" bgcolor="{_FONDO_TITULO}"><b>{numero}/{total}</b>&nbsp; <b>{escape(nombre)}</b></td></tr>',
    ]
    if sub:
        filas.append(f'<tr><td colspan="3" align="center"><font size="2" color="#333333">{escape(sub)}</font></td></tr>')
    filas.append(
        f'<tr><td width="34%" align="center" bgcolor="{_FONDO_CAB}"><b>Talla</b></td>'
        f'<td width="33%" align="center" bgcolor="{_FONDO_CAB}"><b>Exist.</b></td>'
        f'<td width="33%" align="center" bgcolor="{_FONDO_CAB}"><b>Pedido</b></td></tr>'
    )
    for v in variantes:
        talla = escape(str(getattr(v, "talla", "") or "U"))
        filas.append(
            f'<tr><td align="center" height="{_PT_FILA}"><b>{talla}</b></td>'
            f'<td height="{_PT_FILA}">&nbsp;</td><td height="{_PT_FILA}">&nbsp;</td></tr>'
        )
    return _TARJETA_ABRE + "".join(filas) + "</table>"


def paginar(
    alturas: list[int],
    *,
    por_fila: int = TARJETAS_POR_FILA,
    tope: int = PT_UTIL_PRIMERA,
    tope_siguientes: int | None = None,
) -> list[list[int]]:
    """Reparte las tarjetas en páginas (puro): cada página es una lista de
    índices. Una fila de tarjetas no se parte, y una página no rebasa su tope
    (la primera trae el encabezado de la hoja, las demás caben un poco más)."""
    tope_siguientes = tope if tope_siguientes is None else tope_siguientes
    filas = [list(range(i, min(i + por_fila, len(alturas)))) for i in range(0, len(alturas), por_fila)]
    paginas: list[list[int]] = []
    actual: list[int] = []
    usado = 0
    for fila in filas:
        alto = max(alturas[i] for i in fila) + _PT_SEPARACION
        limite = tope if not paginas else tope_siguientes
        if actual and usado + alto > limite:
            paginas.append(actual)
            actual, usado = [], 0
        actual.extend(fila)
        usado += alto
    if actual:
        paginas.append(actual)
    return paginas


def construir_hoja_html(
    grupos: list[dict],
    *,
    titulo: str,
    fecha: date | None = None,
    quien: str = "",
    nivel: str = "",
) -> str:
    """HTML de la hoja completa. `grupos` viene de `conteo_jornada_service.alcance`.

    Es el formato de siempre (la tira térmica: Talla | Exist. | Pedido por
    prenda), acomodado de a tres tarjetas por fila en carta. Los números N/total
    son los mismos que muestra la pantalla de captura. Las páginas se cortan
    entre filas de tarjetas, nunca a media tarjeta.
    """
    fecha = fecha or date.today()
    total = len(grupos)
    total_tallas = sum(len(g["variantes"]) for g in grupos)
    cuenta = escape(quien) if quien else "_" * 26
    nivel_txt = f" &nbsp;&nbsp;&nbsp; Nivel: {escape(nivel)}" if nivel else ""
    partes = [
        _ESTILO,
        f"<h1>HOJA DE CONTEO &nbsp;·&nbsp; {escape(titulo)}</h1>",
        f'<p class="meta">Cuenta: {cuenta}{nivel_txt} &nbsp;&nbsp;&nbsp; Fecha: {fecha:%d/%m/%Y}'
        f" &nbsp;&nbsp;&nbsp; {total} prendas · {total_tallas} tallas</p>",
        '<p class="regla">Exist. = cuántas hay. Si no contaste una talla, déjala vacía — vacío NO es cero. '
        "Pedido = cuántas pedir (opcional).</p>",
    ]
    tarjetas = [_tarjeta(i, total, g, titulo) for i, g in enumerate(grupos, 1)]
    alturas = [altura_tarjeta_pt(g, titulo) for g in grupos]
    ancho = 100 // TARJETAS_POR_FILA
    for n_pag, indices in enumerate(paginar(alturas, tope_siguientes=PT_UTIL_SIGUIENTES)):
        if n_pag:
            partes.append('<p style="page-break-before: always; margin: 0;"></p>')
        filas = []
        for i in range(0, len(indices), TARJETAS_POR_FILA):
            tramo = [tarjetas[k] for k in indices[i:i + TARJETAS_POR_FILA]]
            tramo += [""] * (TARJETAS_POR_FILA - len(tramo))
            filas.append(
                "<tr>" + "".join(f'<td width="{ancho}%" valign="top">{t}</td>' for t in tramo) + "</tr>"
            )
        partes.append(
            f'<table cellspacing="{_PT_SEPARACION}" cellpadding="0" width="100%" border="0">'
            + "".join(filas) + "</table>"
        )
    partes.append(
        '<p class="pie">Al terminar: computadora → Conteos → tu gafete → Capturar. '
        "La pantalla trae las prendas con estos mismos números.</p>"
    )
    return "\n".join(partes)


def grupos_para_hoja(session, *, escuela_id: int | None, tipo_pieza: str = "") -> tuple[str, list[dict]]:
    """(título, grupos) para una escuela o una prenda básica."""
    from pos_uniformes.database.models import Escuela
    from pos_uniformes.services.conteo_jornada_service import alcance

    grupos = alcance(session, escuela_id, tipo_pieza)
    if escuela_id is None:
        titulo = f"Básicos · {tipo_pieza}" if tipo_pieza else "Básicos"
    else:
        escuela = session.get(Escuela, escuela_id)
        titulo = escuela.nombre if escuela is not None else f"Escuela {escuela_id}"
    return titulo, grupos
