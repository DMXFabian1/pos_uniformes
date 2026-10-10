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
    #: Paleta de la barra del encabezado (degradado oscuro → medio → claro).
    #: Vacío = la de siempre (terracota). Es lo único de la ventana que cambia
    #: de color con la temporada; los botones de acción no (2026-10-10).
    color_barra: str = ""
    color_barra_claro: str = ""
    #: Si dos temporadas se empalman un día, gana la de mayor prioridad; a
    #: igual prioridad, la que va primero en la lista.
    prioridad: int = 0
    #: Un renglón chico debajo del saludo en el pie del menú. Opcional.
    mensaje_secundario: str = ""

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
        color_barra="#1f3a5f", color_barra_claro="#35598a", prioridad=10,
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
        color_barra="#1f5e3a", color_barra_claro="#2e8b57", prioridad=5,
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
        color_barra="#4a2358", color_barra_claro="#b85a1f", prioridad=0,
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
        color_barra="#6b1f3a", color_barra_claro="#c9661a", prioridad=1,
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
        color_barra="#7a1a1e", color_barra_claro="#b3262c", prioridad=0,
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
        color_barra="#1e2a4a", color_barra_claro="#6b2338", prioridad=0,
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
        color_barra="#9b1b3a", color_barra_claro="#d94c6a", prioridad=0,
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
        color_barra="#b03a63", color_barra_claro="#c9607a", prioridad=0,
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
_memoria_fechas: tuple[float, object] = (0.0, None)


def olvidar_lo_leido() -> None:
    """Tira la memoria para que la próxima lectura vaya a la base.

    La llama quien acaba de guardar: si no, su propio cambio tardaría medio
    minuto en verse en la máquina que lo hizo."""
    global _memoria, _memoria_fechas
    _memoria = (0.0, None)
    _memoria_fechas = (0.0, None)


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
    anotar("ajuste", modo=modo, temporada=elegido)

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
        # La prueba enseña hasta un borrador (para eso es); lo archivado no.
        return forzada_ if estado_guardado(forzada_) != ARCHIVADO else None
    modo, archivo = ajuste()
    if modo == APAGADA:
        return None
    if modo == FIJA:
        fija = temporada_de_archivo(archivo)
        return fija if fija is not None and _sale_al_publico(fija) else None
    hoy = hoy or hoy_en_mexico()
    candidatas = [t for t in temporadas_vigentes() if t.incluye(hoy) and _sale_al_publico(t)]
    if not candidatas:
        return None
    # La de mayor prioridad; a igual prioridad, la que va primero en la lista
    # (max() devuelve la primera de las máximas, así que el orden se respeta).
    return max(candidatas, key=lambda t: t.prioridad)


def hoy_en_mexico() -> date:
    """La fecha de la tienda, no la de la máquina.

    Un kiosko con el reloj en otra zona (o una Mac de viaje) decidiría la
    temporada con un día de diferencia justo en los bordes. La tienda está en
    San Felipe, Gto.: `America/Mexico_City`. Si el sistema no trae la zona,
    la fecha local es lo mejor que hay."""
    try:
        from datetime import datetime
        from zoneinfo import ZoneInfo

        return datetime.now(ZoneInfo("America/Mexico_City")).date()
    except Exception:  # noqa: BLE001 — sin tzdata, la fecha local
        return date.today()


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
        return next((t for t in temporadas_vigentes() if t.nombre == datos["nombre"]), None)
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
    anotar("prueba", temporada=nombre_archivo, horas=horas)
    return t


def quitar_forzada() -> bool:
    """Vuelve al calendario de verdad. True si había algo que quitar."""
    ruta = ruta_forzada()
    if not ruta.exists():
        return False
    try:
        ruta.unlink()
        anotar("prueba_quitada")
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

    Halloween fue la primera (07/10, dibujada por script); desde el 10/10 las
    ocho llevan ilustración de Daniel envuelta en SVG. Si a alguna le faltara
    el archivo, se queda con su emoji y su saludo, que es lo que había."""
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
    for t in temporadas_vigentes():
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


# ── El tema: lo que la PANTALLA toma de la temporada ─────────────────────────
#
# Daniel (2026-10-10): «misma interfaz, diferente ambientación». La temporada
# ya decidía el saludo, el emoji y un acento; ahora también da la paleta de la
# barra del encabezado. Fuera de temporada no hay «nada»: hay Maximoda, con su
# terracota de siempre y un «Bienvenido». Un solo objeto para que la ventana,
# el gate y el menú no tengan cada uno su idea de qué color toca.

@dataclass(frozen=True)
class Tema:
    nombre: str
    saludo: str
    emoji: str
    color: str              # acento: título del gate, raya del menú
    color_barra: str        # centro del degradado del encabezado
    color_barra_claro: str  # extremo claro del degradado
    color_barra_oscuro: str # extremo oscuro del degradado
    secundario: str = ""    # renglón opcional bajo el saludo (pie del menú)


#: La tienda tal cual: terracota, crema y vino. Es exactamente lo que había
#: antes de que existieran los temas, para que fuera de temporada no cambie
#: ni un pixel.
TEMA_MAXIMODA = Tema(
    nombre="Maximoda",
    saludo="Bienvenido a Maximoda",
    emoji="",
    color="#87492c",
    color_barra="#a84f2d",
    color_barra_claro="#c96a35",
    color_barra_oscuro="#6f331d",
)


def _oscurecer(color_hex: str, cuanto: float = 0.35) -> str:
    """Un tono más oscuro del mismo color, para el arranque del degradado."""
    try:
        h = color_hex.lstrip("#")
        r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
        f = 1.0 - max(0.0, min(1.0, cuanto))
        return "#%02x%02x%02x" % (int(r * f), int(g * f), int(b * f))
    except Exception:  # noqa: BLE001 — un color raro no tumba la pantalla
        return TEMA_MAXIMODA.color_barra_oscuro


def tema_de(t: "Temporada | None") -> Tema:
    """El tema de esa temporada; sin temporada, Maximoda."""
    if t is None:
        return TEMA_MAXIMODA
    barra = t.color_barra or TEMA_MAXIMODA.color_barra
    claro = t.color_barra_claro or (
        TEMA_MAXIMODA.color_barra_claro if not t.color_barra else t.color
    )
    return Tema(
        nombre=t.nombre,
        saludo=t.saludo,
        emoji=t.emoji,
        color=t.color,
        color_barra=barra,
        color_barra_claro=claro,
        color_barra_oscuro=_oscurecer(barra),
        secundario=t.mensaje_secundario,
    )


def tema_activo(hoy: date | None = None) -> Tema:
    """Lo que la pantalla debe vestir ahora mismo. Nunca None.

    En temporada, el tema de la temporada. Fuera, Maximoda con su bienvenida.
    Con los adornos **apagados** desde el menú, Maximoda sin saludo: apagar
    es apagar, no cambiar de frase."""
    try:
        t = actual(hoy)
    except Exception:  # noqa: BLE001 — un adorno no puede impedir que abra
        t = None
    if t is not None:
        return tema_de(t)
    try:
        if ajuste()[0] == APAGADA:
            return Tema(**{**TEMA_MAXIMODA.__dict__, "saludo": ""})
    except Exception:  # noqa: BLE001
        pass
    return TEMA_MAXIMODA


# ── Fechas configurables ─────────────────────────────────────────────────────
#
# Las fechas de arriba son el calendario de fábrica. La tienda puede mover el
# inicio, el fin o la prioridad de cualquiera sin tocar código: se guarda en
# `configuracion_negocio.temporada_fechas` (es de la TIENDA, como el modo) y
# se cachea en esta máquina para cuando no haya red. Formato:
#   {"halloween": {"desde": "10-15", "hasta": "11-02", "prioridad": 2}}
# Cada clave es el archivo de la temporada (`ARCHIVOS`); cada campo es
# opcional y lo que falte se queda de fábrica. Además de fechas, la misma
# entrada puede traer `estado` (ciclo de vida), `saludo` y `secundario`:
#   {"navidad": {"estado": "borrador", "saludo": "¡Felices fiestas!"}}
#
# Ciclo de vida (Daniel, 2026-10-10): borrador y en_revision solo se ven en
# PRUEBA (forzada de 2 h en una pantalla); aprobado entra al calendario y a
# «Siempre: X»; archivado no sale por ningún camino. «programado» y «activo»
# no se guardan: se deducen de la fecha (aprobado y todavía no / aprobado y
# hoy).

BORRADOR, EN_REVISION, APROBADO, ARCHIVADO = "borrador", "en_revision", "aprobado", "archivado"
ESTADOS_GUARDABLES = (BORRADOR, EN_REVISION, APROBADO, ARCHIVADO)
PROGRAMADO, ACTIVO = "programado", "activo"


def _fechas_de_la_tienda():
    """Lo que dice la BASE, o None si no hay nada o no se puede preguntar."""
    import time

    global _memoria_fechas
    ahora = time.time()
    guardado_en, valor = _memoria_fechas
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
            datos = getattr(config, "temporada_fechas", None)
            leido = dict(datos) if isinstance(datos, dict) else {}
    except Exception:  # noqa: BLE001 — sin red manda el cache de esta máquina
        return None
    _memoria_fechas = (ahora, leido)
    return leido


def ruta_fechas():
    """El cache local de las fechas, junto al ajuste."""
    from pos_uniformes.utils.config import satellite_data_dir

    return satellite_data_dir() / "data" / "temporada_fechas.json"


def fechas_configuradas() -> dict:
    """Los ajustes de fechas vigentes: la base manda; sin red, el cache local."""
    de_la_tienda = _fechas_de_la_tienda()
    if de_la_tienda is not None:
        return de_la_tienda
    ruta = ruta_fechas()
    if not ruta.exists():
        return {}
    try:
        import json

        datos = json.loads(ruta.read_text(encoding="utf-8"))
        return datos if isinstance(datos, dict) else {}
    except Exception:  # noqa: BLE001 — cache ilegible: el calendario de fábrica
        return {}


def _md(valor) -> "tuple[int, int] | None":
    """`"10-15"` → `(10, 15)`. None si no es una fecha mes-día válida."""
    try:
        mes, dia = str(valor).replace("/", "-").split("-")
        mes, dia = int(mes), int(dia)
        if 1 <= mes <= 12 and 1 <= dia <= 31:
            return (mes, dia)
    except Exception:  # noqa: BLE001
        pass
    return None


def validar_fechas(datos: dict) -> dict:
    """Deja solo lo que se entiende; lanza ValueError si algo está mal escrito.

    Mejor avisar al guardar que descubrir en octubre que Halloween no salió
    porque alguien escribió «31-10»."""
    limpio: dict = {}
    conocidos = set(ARCHIVOS.values())
    for archivo, campos in (datos or {}).items():
        if archivo not in conocidos:
            raise ValueError(f"no conozco la temporada {archivo!r}")
        if not isinstance(campos, dict):
            raise ValueError(f"{archivo}: se esperaba un diccionario")
        entrada: dict = {}
        for clave in ("desde", "hasta"):
            if clave in campos and campos[clave] not in (None, ""):
                if _md(campos[clave]) is None:
                    raise ValueError(f"{archivo}: {clave} debe ser mes-día, p. ej. 10-15")
                m, d = _md(campos[clave])
                entrada[clave] = f"{m:02d}-{d:02d}"
        if "prioridad" in campos and campos["prioridad"] not in (None, ""):
            try:
                entrada["prioridad"] = int(campos["prioridad"])
            except (TypeError, ValueError):
                raise ValueError(f"{archivo}: la prioridad debe ser un entero")
        if campos.get("estado"):
            if campos["estado"] not in ESTADOS_GUARDABLES:
                raise ValueError(
                    f"{archivo}: estado desconocido {campos['estado']!r}; "
                    f"vale {', '.join(ESTADOS_GUARDABLES)}"
                )
            if campos["estado"] != APROBADO:
                entrada["estado"] = campos["estado"]
        for clave in ("saludo", "secundario"):
            texto = str(campos.get(clave) or "").strip().replace("\n", " ")
            if texto:
                if len(texto) > 60:
                    raise ValueError(f"{archivo}: {clave} no puede pasar de 60 letras")
                entrada[clave] = texto
        if entrada:
            limpio[archivo] = entrada
    return limpio


def temporadas_vigentes() -> tuple[Temporada, ...]:
    """Las temporadas con las fechas y prioridades que la tienda configuró."""
    from dataclasses import replace

    ajustes = fechas_configuradas()
    if not ajustes:
        return TEMPORADAS
    salida = []
    for t in TEMPORADAS:
        cambios = ajustes.get(ARCHIVOS.get(t.nombre, ""), {})
        if not isinstance(cambios, dict) or not cambios:
            salida.append(t)
            continue
        kw = {}
        if _md(cambios.get("desde")):
            kw["desde"] = _md(cambios["desde"])
        if _md(cambios.get("hasta")):
            kw["hasta"] = _md(cambios["hasta"])
        if isinstance(cambios.get("prioridad"), int):
            kw["prioridad"] = cambios["prioridad"]
        if str(cambios.get("saludo") or "").strip():
            kw["saludo"] = str(cambios["saludo"]).strip()
        if str(cambios.get("secundario") or "").strip():
            kw["mensaje_secundario"] = str(cambios["secundario"]).strip()
        salida.append(replace(t, **kw) if kw else t)
    return tuple(salida)


def estado_guardado(t: "Temporada") -> str:
    """borrador / en_revision / aprobado / archivado. De fábrica, aprobado."""
    ajustes = fechas_configuradas()
    entrada = ajustes.get(ARCHIVOS.get(t.nombre, ""), {}) if isinstance(ajustes, dict) else {}
    estado = entrada.get("estado") if isinstance(entrada, dict) else None
    return estado if estado in ESTADOS_GUARDABLES else APROBADO


def estado_de(t: "Temporada", hoy: date | None = None) -> str:
    """El estado tal como lo pide el ciclo de vida, incluidos los deducidos.

    `activo` si es la que manda hoy; `programado` si está aprobada y hoy no
    toca; si no, lo guardado."""
    guardado = estado_guardado(t)
    if guardado != APROBADO:
        return guardado
    vigente = actual(hoy)
    if vigente is not None and vigente.nombre == t.nombre:
        return ACTIVO
    return PROGRAMADO


def _sale_al_publico(t: "Temporada") -> bool:
    """Solo lo aprobado entra al calendario o a «Siempre: X»."""
    return estado_guardado(t) == APROBADO


def guardar_fechas(datos: dict) -> bool:
    """Guarda las fechas en TODA la tienda. True si llegó a la base.

    Igual que `guardar_ajuste`: local primero (para sin red), base después."""
    import json

    global _memoria_fechas
    limpio = validar_fechas(datos)
    ruta = ruta_fechas()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(limpio, ensure_ascii=False), encoding="utf-8")
    _memoria_fechas = (0.0, None)
    anotar("fechas", configuradas=limpio)
    try:
        from pos_uniformes.database.connection import get_session
        from pos_uniformes.services.business_settings_service import (
            BusinessSettingsService,
        )

        with get_session() as session:
            config = BusinessSettingsService.get_or_create(session)
            config.temporada_fechas = limpio
            session.commit()
        _memoria_fechas = (0.0, None)
        return True
    except Exception:  # noqa: BLE001
        logger.warning("Las fechas de temporada no llegaron a la base: solo esta pantalla")
        return False


# ── Bitácora ─────────────────────────────────────────────────────────────────
#
# Cuando algo sale raro en octubre («¿quién puso Navidad?»), lo que se quiere
# es un renglón con fecha. Va al log de la aplicación y a un archivo local
# chico, de a un JSON por renglón, que se recorta solo.

MAX_RENGLONES_BITACORA = 300


def ruta_bitacora():
    from pos_uniformes.utils.config import satellite_data_dir

    return satellite_data_dir() / "data" / "temporada_bitacora.jsonl"


def anotar(evento: str, **datos) -> None:
    """Un renglón en la bitácora. Nunca lanza: anotar no vale un error."""
    import json
    from datetime import datetime

    renglon = {"cuando": datetime.now().isoformat(timespec="seconds"), "evento": evento, **datos}
    logger.info("temporada: %s %s", evento, datos)
    try:
        ruta = ruta_bitacora()
        ruta.parent.mkdir(parents=True, exist_ok=True)
        lineas = ruta.read_text(encoding="utf-8").splitlines() if ruta.exists() else []
        lineas.append(json.dumps(renglon, ensure_ascii=False))
        ruta.write_text("\n".join(lineas[-MAX_RENGLONES_BITACORA:]) + "\n", encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass


def bitacora(ultimos: int = 50) -> list[dict]:
    """Los últimos renglones, el más reciente al final."""
    import json

    try:
        ruta = ruta_bitacora()
        if not ruta.exists():
            return []
        salida = []
        for linea in ruta.read_text(encoding="utf-8").splitlines()[-ultimos:]:
            try:
                salida.append(json.loads(linea))
            except ValueError:
                continue
        return salida
    except Exception:  # noqa: BLE001
        return []
