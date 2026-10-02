"""Temporadas: un detalle del calendario en el ticket y en la pantalla.

Idea de Daniel (02/10): *"poner temáticas… que se viera un dibujito en el
ticket, tal vez también que la app tuviera motivos, nada exagerado, pero sí algo
sutil"*.

Un solo lugar decide **en qué fecha estamos**, y de ahí beben el ticket y la
pantalla. Si estuviera repartido, un año alguien mueve Halloween en un lado y no
en el otro.

Tres reglas que vienen de que esto es una tienda, no una tarjeta de felicitación:

- **El dibujo es de ASCII, sin emoji.** La impresora térmica dibuja el texto con
  una fuente monoespaciada: las líneas y los acentos salen, los emoji no (y
  cuando no salen, salen como cuadritos). Los emoji se quedan para la pantalla.
- **Nunca más de cuatro renglones.** El ticket es un papel que cuesta y que se
  guarda; un adorno que empuja el total hacia abajo deja de ser un adorno.
- **El saludo pesa más que el dibujo.** «Feliz Día de Muertos» de la tienda de
  uniformes de su hijo es lo que la señora va a leer; el dibujo es el adorno del
  adorno.

Para una tienda de uniformes la temporada que de verdad importa no es ninguna
fiesta: es **el regreso a clases**. Va primero por eso.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

#: Ancho útil del ticket (38 columnas menos los bordes del recuadro).
ANCHO_TICKET = 34
#: Tope de renglones del dibujo. El ticket es papel que cuesta.
MAX_RENGLONES = 4


@dataclass(frozen=True)
class Temporada:
    nombre: str
    #: (mes, día) de inicio y fin, inclusive. Puede cruzar el año.
    desde: tuple[int, int]
    hasta: tuple[int, int]
    saludo: str                 # lo que lee el cliente en el ticket
    arte: tuple[str, ...]       # ASCII puro, para la impresora
    emoji: str                  # solo para la pantalla
    color: str                  # acento sutil para la pantalla

    def incluye(self, dia: date) -> bool:
        md = (dia.month, dia.day)
        if self.desde <= self.hasta:
            return self.desde <= md <= self.hasta
        # Cruza el año (Navidad → Reyes).
        return md >= self.desde or md <= self.hasta


#: El orden importa: la primera que coincide gana. El regreso a clases va
#: primero porque es la temporada de esta tienda, y porque si algún año se
#: empalma con una fiesta, el uniforme es lo que trae a la gente.
TEMPORADAS: tuple[Temporada, ...] = (
    Temporada(
        nombre="Regreso a clases",
        desde=(7, 15), hasta=(9, 10),
        saludo="¡Buen regreso a clases!",
        arte=(
            "  ______________________",
            " |______________________>",
        ),
        emoji="✏️",
        color="#c2763a",
    ),
    Temporada(
        nombre="Independencia",
        desde=(9, 11), hasta=(9, 17),
        saludo="¡Viva México!",
        arte=(
            "   *     *     *",
            "  ---------------",
        ),
        emoji="🇲🇽",
        color="#2e7d5b",
    ),
    Temporada(
        nombre="Halloween",
        desde=(10, 20), hasta=(10, 31),
        saludo="¡Feliz Halloween!",
        arte=(
            "    \\|",
            " .-\"\"\"-.",
            "( o   o )",
            " '-www-'",
        ),
        emoji="🎃",
        color="#d4752a",
    ),
    Temporada(
        nombre="Día de Muertos",
        desde=(11, 1), hasta=(11, 2),
        saludo="Feliz Día de Muertos",
        arte=(
            " .-\"\"\"-.",
            "( o   o )",
            "(   ^   )",
            " '-|||-'",
        ),
        emoji="💀",
        color="#b5651d",
    ),
    Temporada(
        nombre="Navidad",
        desde=(12, 1), hasta=(12, 25),
        saludo="¡Feliz Navidad!",
        arte=(
            "    *",
            "   /_\\",
            "  /___\\",
            "    |_|",
        ),
        emoji="🎄",
        color="#2e7d5b",
    ),
    Temporada(
        nombre="Año nuevo y Reyes",
        desde=(12, 26), hasta=(1, 6),
        saludo="¡Feliz año!",
        arte=(
            "    *  .  *  .  *",
            "      \\  |  /",
        ),
        emoji="✨",
        color="#a8812a",
    ),
    Temporada(
        nombre="San Valentín",
        desde=(2, 10), hasta=(2, 14),
        saludo="Feliz 14 de febrero",
        arte=(
            " /\\/\\",
            "(    )",
            " \\  /",
            "  \\/",
        ),
        emoji="❤️",
        color="#b03a48",
    ),
    Temporada(
        nombre="Día de las Madres",
        desde=(5, 5), hasta=(5, 10),
        saludo="Feliz día, mamá",
        arte=(
            "       (@)",
            "       /|\\",
            "        |",
        ),
        emoji="🌷",
        color="#b03a63",
    ),
)


def actual(hoy: date | None = None) -> Temporada | None:
    """La temporada de hoy, o None si es un día cualquiera del año.

    La mayor parte del año no hay nada, y eso está bien: un adorno que sale
    siempre deja de notarse, y entonces no adorna.
    """
    hoy = hoy or date.today()
    for t in TEMPORADAS:
        if t.incluye(hoy):
            return t
    return None


def renglones_de_ticket(hoy: date | None = None) -> list[str]:
    """Las líneas (sin recuadro) que van al pie del ticket. Vacío si no hay temporada.

    Los renglones del dibujo vienen **rellenados al mismo ancho**. No es un
    detalle: quien imprime los centra uno por uno, y centrar cada renglón por su
    cuenta le da a cada uno un margen distinto — el dibujo se desarma y queda un
    reguero de símbolos. Con todos del mismo ancho, el centrado les toca igual y
    el bloque conserva su forma.

    El saludo va sin rellenar: ese sí se centra solo, como cualquier frase.
    """
    t = actual(hoy)
    if t is None:
        return []
    arte = [a for a in t.arte[:MAX_RENGLONES] if len(a) <= ANCHO_TICKET]
    ancho = max((len(a) for a in arte), default=0)
    return [a.ljust(ancho) for a in arte] + [t.saludo]


def saludo_de_pantalla(hoy: date | None = None) -> str:
    """'🎃 ¡Feliz Halloween!' para la pantalla. Vacío si no hay temporada."""
    t = actual(hoy)
    return f"{t.emoji} {t.saludo}" if t else ""


# ── El dibujo de verdad (PNG) ────────────────────────────────────────────────
#
# La térmica sabe imprimir puntos, no solo letras, así que el dibujo puede ser
# una imagen y no un montón de caracteres. Pero el ticket viaja como una CADENA
# por toda la cola de impresión, así que la imagen no puede ir dentro: va un
# marcador en su propio renglón, y cada camino de impresión lo resuelve como
# puede —ESC/POS lo cambia por los puntos; los demás, por el dibujo de ASCII,
# que para eso se queda.

MARCADOR_INICIO = "[[IMG:"
MARCADOR_FIN = "]]"

#: Nombre de archivo por temporada. Si falta el PNG, se usa el ASCII de arriba.
ARCHIVOS = {
    "Regreso a clases": "regreso_a_clases",
    "Independencia": "independencia",
    "Halloween": "halloween",
    "Día de Muertos": "dia_de_muertos",
    "Navidad": "navidad",
    "Año nuevo y Reyes": "anio_nuevo",
    "San Valentín": "san_valentin",
    "Día de las Madres": "dia_de_las_madres",
}


def carpeta_dibujos():
    from pathlib import Path

    return Path(__file__).resolve().parents[1] / "assets" / "temporadas"


def imagen_para_marcador(nombre: str):
    """La ruta del PNG de ese marcador, o None si no está."""
    limpio = "".join(c for c in str(nombre or "") if c.isalnum() or c == "_")
    if not limpio:
        return None
    ruta = carpeta_dibujos() / f"{limpio}.png"
    return ruta if ruta.exists() else None


def marcador_de_ticket(hoy: date | None = None) -> str:
    """El marcador del dibujo de hoy, o '' si no hay temporada o no hay PNG."""
    t = actual(hoy)
    if t is None:
        return ""
    archivo = ARCHIVOS.get(t.nombre)
    if not archivo or imagen_para_marcador(archivo) is None:
        return ""
    return f"{MARCADOR_INICIO}{archivo}{MARCADOR_FIN}"


def sin_marcadores(texto: str, hoy: date | None = None) -> str:
    """Cambia el marcador por el dibujo de ASCII, para quien no imprime puntos.

    Lo usan la vista previa en pantalla y el camino de QPrinter. Sin esto, en
    esos dos saldría el texto crudo «[[IMG:halloween]]», que es peor que no
    poner nada.
    """
    if MARCADOR_INICIO not in (texto or ""):
        return texto
    arte = "\n".join(r.center(ANCHO_TICKET) for r in _solo_arte(hoy))
    salida = []
    for i, parte in enumerate(texto.split(MARCADOR_INICIO)):
        if i == 0:
            salida.append(parte)
            continue
        _, _, resto = parte.partition(MARCADOR_FIN)
        salida.append(arte + resto)
    return "".join(salida)


def _solo_arte(hoy: date | None = None) -> list[str]:
    """El dibujo de ASCII sin el saludo (el saludo ya va aparte en el ticket)."""
    t = actual(hoy)
    if t is None:
        return []
    arte = [a for a in t.arte[:MAX_RENGLONES] if len(a) <= ANCHO_TICKET]
    ancho = max((len(a) for a in arte), default=0)
    return [a.ljust(ancho) for a in arte]
