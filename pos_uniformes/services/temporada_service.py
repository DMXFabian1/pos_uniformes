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

import logging
from dataclasses import dataclass
from datetime import date

logger = logging.getLogger(__name__)

#: Ancho útil del ticket (38 columnas menos los bordes del recuadro).
ANCHO_TICKET = 34
#: El papel completo. El arte usa 34 porque vive dentro del recuadro; el
#: respaldo de un marcador no, y se centra contra el papel entero.
ANCHO_PAPEL_TEXTO = 38
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


#: Cómo se elige la temporada. Vive en un ajuste porque Daniel quiso poder
#: encenderlas y apagarlas desde el menú, sin esperar a la fecha y sin depender
#: de que alguien se acuerde de quitar una prueba (2026-10-07).
AUTO, APAGADA, FIJA = "auto", "apagada", "fija"


def ruta_ajuste():
    """Dónde vive el ajuste de ESTA máquina.

    `satellite_data_dir` y no `runtime_base_dir`: en el kiosko empaquetado el
    segundo es la carpeta del .exe, y esa carpeta la reemplaza la
    actualización — Daniel ponía Halloween, cerraba el programa y al volver
    ya no estaba (2026-10-09). En AppData sobrevive, que es donde ya viven
    los otros ajustes por máquina (impresoras, ESC/POS).

    Fuera del kiosko las dos carpetas son la misma, así que nada se mueve.
    """
    from pos_uniformes.utils.config import satellite_data_dir

    return satellite_data_dir() / "data" / "temporada_ajuste.json"


#: Cuánto vale lo leído de la base antes de volver a preguntar. La temporada
#: se consulta en cada ticket y en cada repintado: sin esto sería una
#: consulta por renglón impreso. Medio minuto sobra para algo que se cambia
#: tres veces al año.
SEGUNDOS_DE_MEMORIA = 30.0
_memoria: tuple[float, object] = (0.0, None)


def olvidar_lo_leido() -> None:
    """Tira la memoria para que la próxima lectura vaya a la base.

    La llama quien acaba de guardar: si no, su propio cambio tardaría medio
    minuto en verse en la máquina que lo hizo."""
    global _memoria
    _memoria = (0.0, None)


def _ajuste_de_la_tienda():
    """Lo que dice la BASE, o None si no hay nada o no se puede preguntar.

    Es de la tienda y no de la máquina: ponerlo en una pantalla y que las
    otras no se enteren era peor que no tenerlo (Daniel, 2026-10-09).
    """
    import time

    global _memoria
    ahora = time.time()
    guardado_en, valor = _memoria
    if ahora - guardado_en < SEGUNDOS_DE_MEMORIA:
        return valor
    leido = None
    try:
        from pos_uniformes.database.connection import get_session
        from pos_uniformes.services.business_settings_service import (
            BusinessSettingsService,
        )

        with get_session() as session:
            config = BusinessSettingsService.get_or_create(session)
            modo = str(getattr(config, "temporada_modo", "") or "")
            if modo in (AUTO, APAGADA, FIJA):
                leido = (modo, str(getattr(config, "temporada_archivo", "") or ""))
    except Exception:  # noqa: BLE001 — sin red manda el cache de esta máquina
        return None
    _memoria = (ahora, leido)
    return leido


def ajuste() -> tuple[str, str]:
    """(modo, archivo). La tienda manda; el archivo local es la red de abajo.

    Por omisión, el calendario de siempre."""
    de_la_tienda = _ajuste_de_la_tienda()
    if de_la_tienda is not None:
        return de_la_tienda
    ruta = ruta_ajuste()
    if not ruta.exists():
        return AUTO, ""
    try:
        import json

        datos = json.loads(ruta.read_text(encoding="utf-8"))
        modo = str(datos.get("modo") or AUTO)
        if modo not in (AUTO, APAGADA, FIJA):
            modo = AUTO
        return modo, str(datos.get("temporada") or "")
    except Exception:  # noqa: BLE001 — ajuste ilegible: el calendario de siempre
        return AUTO, ""


def guardar_ajuste(modo: str, archivo: str = "") -> bool:
    """Guarda cómo se eligen las temporadas en TODA la tienda.

    Devuelve True si llegó a la base —o sea, si las demás pantallas se van a
    enterar— y False si solo quedó en ésta.

    Se escribe en los dos lados a propósito: la base es la que ven las demás,
    y el archivo local es lo que salva al kiosko cuando se queda sin red.
    """
    import json

    if modo not in (AUTO, APAGADA, FIJA):
        raise ValueError(f"modo inválido: {modo!r}")
    if modo == FIJA and temporada_de_archivo(archivo) is None:
        raise ValueError(f"no conozco la temporada {archivo!r}")
    elegido = archivo if modo == FIJA else ""

    ruta = ruta_ajuste()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(
        json.dumps({"modo": modo, "temporada": elegido}), encoding="utf-8"
    )
    olvidar_lo_leido()

    try:
        from pos_uniformes.database.connection import get_session
        from pos_uniformes.services.business_settings_service import (
            BusinessSettingsService,
        )

        with get_session() as session:
            config = BusinessSettingsService.get_or_create(session)
            config.temporada_modo = modo
            config.temporada_archivo = elegido
            session.commit()
        olvidar_lo_leido()
        return True
    except Exception:  # noqa: BLE001 — esta máquina ya quedó bien; se avisa
        logger.warning("La temporada no llegó a la base: solo cambia esta pantalla")
        return False


def actual(hoy: date | None = None) -> Temporada | None:
    """La temporada de hoy, o None si es un día cualquiera del año.

    La mayor parte del año no hay nada, y eso está bien: un adorno que sale
    siempre deja de notarse, y entonces no adorna.

    El orden importa:

    1. Una temporada **forzada** que no haya vencido manda sobre todo. Es para
       mirar un adorno ahora mismo (`scripts/probar_temporada.bat`) y vence
       sola, para que una prueba no se quede puesta hasta marzo.
    2. El **ajuste** de la máquina: apagadas, o una fija que Daniel eligió.
    3. El calendario, que es lo de siempre.
    """
    forzada_ = forzada()
    if forzada_ is not None:
        return forzada_
    modo, archivo = ajuste()
    if modo == APAGADA:
        return None
    if modo == FIJA:
        return temporada_de_archivo(archivo)
    hoy = hoy or date.today()
    for t in TEMPORADAS:
        if t.incluye(hoy):
            return t
    return None


# ── Forzar una temporada para verla antes ────────────────────────────────────
#
# Halloween entra el 20 de octubre, y querer verlo el 2 es razonable. Lo que no
# es razonable es que se quede forzado: por eso **vence solo**. Una tienda con
# el arbolito de Navidad en marzo porque alguien probó y se le olvidó quitarlo
# es peor que no haber tenido la herramienta.

HORAS_FORZADA = 2.0


def ruta_forzada():
    """La prueba de dos horas, en la misma carpeta que el ajuste."""
    from pos_uniformes.utils.config import satellite_data_dir

    return satellite_data_dir() / "data" / "temporada_forzada.json"


def forzada() -> "Temporada | None":
    """La temporada forzada que siga vigente, o None."""
    ruta = ruta_forzada()
    if not ruta.exists():          # el caso de siempre: ni se abre el archivo
        return None
    try:
        import json
        from datetime import datetime, timezone

        datos = json.loads(ruta.read_text(encoding="utf-8"))
        hasta = datetime.fromisoformat(str(datos["hasta"]))
        if hasta.tzinfo is None:
            hasta = hasta.replace(tzinfo=timezone.utc)
        if hasta <= datetime.now(timezone.utc):
            return None
        return next((t for t in TEMPORADAS if t.nombre == datos["nombre"]), None)
    except Exception:  # noqa: BLE001 — un archivo raro no fuerza nada
        return None


def forzar(nombre_archivo: str, *, horas: float = HORAS_FORZADA) -> "Temporada | None":
    """Fuerza una temporada por unas horas. Devuelve cuál, o None si no existe."""
    import json
    from datetime import datetime, timedelta, timezone

    t = temporada_de_archivo(nombre_archivo)
    if t is None:
        return None
    ruta = ruta_forzada()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(
        json.dumps(
            {
                "nombre": t.nombre,
                "hasta": (datetime.now(timezone.utc) + timedelta(hours=horas)).isoformat(),
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return t


def quitar_forzada() -> bool:
    """Vuelve al calendario de verdad. True si había algo que quitar."""
    ruta = ruta_forzada()
    if not ruta.exists():
        return False
    try:
        ruta.unlink()
        return True
    except OSError:
        return False


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
    return _solo_arte_de(t) + [t.saludo]


def _solo_arte(hoy: date | None = None) -> list[str]:
    """El dibujo de ASCII de hoy, sin el saludo."""
    return _solo_arte_de(actual(hoy))


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

#: Un marcador puede llevar su propio respaldo escrito: `[[IMG:logo|MAXIMODA]]`.
#:
#: Existe porque el ticket se ARMA en una máquina y se IMPRIME en otra. El 07/10
#: Daniel mandó una reimpresión desde la Mac: el texto preguntó «¿esta PC dibuja
#: tickets?», la Mac dijo que no, y el papel salió de la principal —que sí
#: dibuja— con el nombre escrito y sin logo. La pregunta estaba en la máquina
#: equivocada. Ahora el marcador va SIEMPRE y cada camino de impresión decide:
#: el que sabe poner puntos pone el logo, el que no, escribe el respaldo.
SEPARADOR_RESPALDO = "|"


def partir_marcador(cuerpo: str) -> tuple[str, str]:
    """`"logo|MAXIMODA"` -> `("logo", "MAXIMODA")`. Sin respaldo, `("logo", "")`."""
    nombre, _, respaldo = str(cuerpo or "").partition(SEPARADOR_RESPALDO)
    return nombre.strip(), respaldo.strip()

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


def carpeta_imagenes_ticket():
    """Imágenes del ticket que NO son de temporada (el logo, por ahora)."""
    from pathlib import Path

    return Path(__file__).resolve().parents[1] / "assets" / "ticket"


def carpeta_escenas():
    """Las ilustraciones de pantalla completa (una por temporada, si la hay)."""
    from pathlib import Path

    return Path(__file__).resolve().parents[1] / "assets" / "escenas"


def escena_de(t: "Temporada | None"):
    """El SVG de fondo de esa temporada, o None si no tiene.

    Casi ninguna tiene: dibujar una escena es trabajo de ilustración, no de
    calendario. Halloween es la primera porque Daniel la pidió (07/10). Las
    demás siguen con su emoji y su saludo, que es lo que había."""
    if t is None:
        return None
    archivo = ARCHIVOS.get(t.nombre)
    if not archivo:
        return None
    ruta = carpeta_escenas() / f"{archivo}.svg"
    return ruta if ruta.exists() else None


def imagen_para_marcador(nombre: str):
    """La ruta del PNG de ese marcador, o None si no está.

    Busca en los dibujos de temporada y en las imágenes fijas del ticket. Es
    una sola función y no dos porque del otro lado —el que imprime— un dibujo
    es un dibujo: no tiene por qué saber si es una calabaza o el logo de la
    tienda (2026-10-07, al meter el logo).
    """
    solo, _ = partir_marcador(nombre)
    limpio = "".join(c for c in solo if c.isalnum() or c == "_")
    if not limpio:
        return None
    for carpeta in (carpeta_dibujos(), carpeta_imagenes_ticket()):
        ruta = carpeta / f"{limpio}.png"
        if ruta.exists():
            return ruta
    return None


def marcador_de(nombre: str, respaldo: str = "") -> str:
    """El marcador que se escribe en el texto del ticket para pedir ese dibujo.

    `respaldo` es lo que se escribe cuando quien imprime no sabe poner puntos
    (el camino de Qt, la vista previa). Va dentro del marcador, no aparte,
    porque el ticket cruza la cola de impresión como una sola cadena: lo que no
    viaje ahí, no llega.

    Vacío si el PNG no está: así quien lo arma no tiene que comprobar nada y un
    archivo que falta nunca deja un `[[...]]` impreso en el papel."""
    limpio = "".join(c for c in str(nombre or "") if c.isalnum() or c == "_")
    if not limpio or imagen_para_marcador(limpio) is None:
        return ""
    # Ni el separador ni el cierre pueden ir dentro del respaldo: partirían el
    # marcador por la mitad y el resto saldría crudo en el papel.
    limpio_respaldo = str(respaldo or "").replace(SEPARADOR_RESPALDO, " ").replace("]", "")
    cola = f"{SEPARADOR_RESPALDO}{limpio_respaldo}" if limpio_respaldo else ""
    return f"{MARCADOR_INICIO}{limpio}{cola}{MARCADOR_FIN}"


def marcador_de_ticket(hoy: date | None = None) -> str:
    """El marcador del dibujo de hoy, o '' si no hay temporada o no hay PNG."""
    t = actual(hoy)
    if t is None:
        return ""
    archivo = ARCHIVOS.get(t.nombre)
    if not archivo or imagen_para_marcador(archivo) is None:
        return ""
    return f"{MARCADOR_INICIO}{archivo}{MARCADOR_FIN}"


def temporada_de_archivo(archivo: str) -> "Temporada | None":
    """La temporada a la que pertenece ese dibujo. Lo contrario de `ARCHIVOS`."""
    buscado = str(archivo or "").strip()
    for t in TEMPORADAS:
        if ARCHIVOS.get(t.nombre) == buscado:
            return t
    return None


def sin_marcadores(texto: str, hoy: date | None = None) -> str:
    """Cambia el marcador por el dibujo de ASCII, para quien no imprime puntos.

    Lo usan la vista previa en pantalla y el camino de QPrinter. Sin esto, en
    esos dos saldría el texto crudo «[[IMG:halloween]]», que es peor que no
    poner nada.

    El dibujo sale **del marcador**, no de la fecha de hoy. Parece lo mismo y no
    lo es: un ticket de Halloween reimpreso el 1 de noviembre llevaba el
    marcador de la calabaza y se le ponía la calavera — o nada, si ya no había
    temporada. Lo que manda es lo que dice el papel.
    """
    if MARCADOR_INICIO not in (texto or ""):
        return texto
    salida = []
    for i, parte in enumerate(texto.split(MARCADOR_INICIO)):
        if i == 0:
            salida.append(parte)
            continue
        cuerpo, _, resto = parte.partition(MARCADOR_FIN)
        archivo, respaldo = partir_marcador(cuerpo)
        renglones = _solo_arte_de(temporada_de_archivo(archivo))
        if not renglones and respaldo:
            # El marcador trae escrito cómo decirse sin dibujo. Es el caso del
            # logo: sin puntos, el nombre de la tienda. Se centra contra el
            # papel entero y no contra el recuadro, porque no va dentro de uno.
            salida.append(respaldo.center(ANCHO_PAPEL_TEXTO) + resto)
            continue
        if not renglones:
            # Ni PNG ni dibujo de ASCII: el marcador desaparecía sin decir
            # nada y el papel salía como si nunca se hubiera pedido un dibujo.
            # Pasó con el logo el 2026-10-07: la hoja de prueba salió sin logo
            # y sin pista de por qué. Un hueco que se ve es lo que permite
            # preguntar; uno que no se ve se queda ahí meses.
            renglones = [f"(falta el dibujo: {archivo})"]
        arte = "\n".join(r.center(ANCHO_TICKET) for r in renglones)
        salida.append(arte + resto)
    return "".join(salida)


def _solo_arte_de(t: "Temporada | None") -> list[str]:
    """El dibujo de ASCII de ESA temporada, sin el saludo."""
    if t is None:
        return []
    arte = [a for a in t.arte[:MAX_RENGLONES] if len(a) <= ANCHO_TICKET]
    ancho = max((len(a) for a in arte), default=0)
    return [a.ljust(ancho) for a in arte]
