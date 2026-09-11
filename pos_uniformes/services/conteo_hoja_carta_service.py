"""La hoja de conteo en papel carta: una rejilla producto × talla.

Hasta el 2026-09-10 la hoja salía en la impresora de tickets: tiras de 80 mm,
una por producto, sin numerar. Para una escuela de 14 prendas eran 14 tiras
que se traspapelan. Esta hoja va a la HP en tamaño carta: **un renglón por
prenda**, una casilla por talla, y cada prenda **numerada igual que en la
pantalla de captura** (las dos leen `conteo_jornada_service.alcance`).

Todo aquí es puro: recibe los grupos y devuelve HTML. Imprimir es cosa de la
UI (`ui/helpers/conteo_hoja_carta_print_helper.py`).
"""

from __future__ import annotations

from datetime import date
from html import escape

# Casillas por renglón antes de partir la rejilla en dos filas (letra legible
# a mano necesita ~1.6 cm por casilla; en carta caben 11 holgadas).
CASILLAS_POR_FILA = 11

_ESTILO = """
<style>
  body { font-family: Helvetica, Arial, sans-serif; color: #000; }
  h1 { font-size: 17pt; margin: 0 0 2pt 0; }
  .meta { font-size: 10pt; color: #333; margin: 0 0 4pt 0; }
  .regla { font-size: 10pt; font-weight: bold; margin: 0 0 10pt 0; }
  .prenda { font-size: 11pt; font-weight: bold; margin: 9pt 0 3pt 0; }
  table.tallas { border-collapse: separate; border-spacing: 3pt 0; }
  table.tallas td.t { font-size: 8.5pt; color: #444; text-align: center; padding: 0 0 1pt 0; }
  table.tallas td.c { border: 1pt solid #333; width: 42pt; height: 26pt; }
  .pie { font-size: 9pt; color: #333; margin-top: 12pt; }
  hr { border: 0; border-top: 0.5pt solid #999; margin: 5pt 0 0 0; }
</style>
"""


def _rejilla(tallas: list[str]) -> str:
    """Filas de encabezado/casillas, partidas cada CASILLAS_POR_FILA."""
    partes = []
    for i in range(0, len(tallas), CASILLAS_POR_FILA):
        tramo = tallas[i:i + CASILLAS_POR_FILA]
        cab = "".join(f'<td class="t">{escape(t) or "&nbsp;"}</td>' for t in tramo)
        cajas = "".join('<td class="c">&nbsp;</td>' for _ in tramo)
        partes.append(f'<table class="tallas"><tr>{cab}</tr><tr>{cajas}</tr></table>')
    return "".join(partes)


def construir_hoja_html(
    grupos: list[dict],
    *,
    titulo: str,
    fecha: date | None = None,
    quien: str = "",
) -> str:
    """HTML de la hoja completa. `grupos` viene de `conteo_jornada_service.alcance`."""
    fecha = fecha or date.today()
    total_tallas = sum(len(g["variantes"]) for g in grupos)
    cuenta = escape(quien) if quien else "_" * 28
    partes = [
        _ESTILO,
        f"<h1>HOJA DE CONTEO &nbsp;·&nbsp; {escape(titulo)}</h1>",
        f'<p class="meta">Cuenta: {cuenta} &nbsp;&nbsp;&nbsp; Fecha: {fecha:%d/%m/%Y}'
        f" &nbsp;&nbsp;&nbsp; {len(grupos)} prendas · {total_tallas} tallas</p>",
        '<p class="regla">Escribe cuántas hay de cada talla. Si no contaste una talla, '
        "déjala vacía — vacío NO es cero.</p>",
    ]
    for numero, g in enumerate(grupos, 1):
        nombre = str(g.get("producto_nombre") or "").split(" | ")[0].strip()
        tallas = [str(getattr(v, "talla", "") or "") for v in g["variantes"]]
        partes.append(f'<p class="prenda">{numero}.&nbsp; {escape(nombre)}</p>')
        partes.append(_rejilla(tallas))
        partes.append("<hr>")
    partes.append(
        '<p class="pie">Al terminar, ve a la computadora → Conteos → pasa tu gafete → '
        "Capturar. La pantalla trae las prendas en este mismo orden y con estos números.</p>"
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
