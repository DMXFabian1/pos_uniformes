"""Los textos de la ventana «Revisar conteo», sin Qt (2026-11-15).

La ventana (`ConteoRevisionDialog`) solo pinta; aquí se decide qué decir:

- **Cuándo se contó**: «lun 5 oct · hace 41 días», y el aviso ámbar si el
  conteo ya tiene `DIAS_AVISO_VIEJO` días o más.
- **Por qué no hay nada que pedir**: el motivo real según el estado de cada
  talla (lo que hay alcanza, sin ventas, se acabó, faltan días), en vez de un
  texto fijo.
- **Qué hacer con una talla**: «pedir 6 · surtir 2», «¡URGENTE! …», «se acabó»
  (contaron 0 y nadie la pidió), «no se mueve», «sin datos».
- **La confirmación de aplicar y de descartar**, con botones en español y lo
  que de verdad pasa: a cada talla se le SUMA la diferencia de aquel día.
- **Ya revisado**: «Corregido el 22 sep por Daniel» / «No se usó (22 sep)».

Las reglas de `revision_service.sugerir` no cambian: esto solo las cuenta.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime, timezone

from pos_uniformes.services.revision_service import (
    BIEN,
    NO_SE_MUEVE,
    PEDIR,
    SIN_DATOS,
    SURTIR,
    URGENTE,
)

ZONA_TIENDA = "America/Mexico_City"
DIAS_AVISO_VIEJO = 7       # desde aquí, aviso ámbar: conviene recontar
DIAS_BOTON_VIEJO = 14      # desde aquí, el botón de corregir dice la edad del conteo

_DIAS = ("lun", "mar", "mié", "jue", "vie", "sáb", "dom")
_MESES = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")

ACCION = (URGENTE, PEDIR, SURTIR)


# --- fechas -------------------------------------------------------------------------

def _zona():
    try:
        from zoneinfo import ZoneInfo

        return ZoneInfo(ZONA_TIENDA)
    except Exception:  # noqa: BLE001 — sin tzdata, la zona de la máquina
        return None


def hoy_tienda() -> date:
    """La fecha en la tienda (San Felipe, Gto.), no la de la máquina."""
    zona = _zona()
    return datetime.now(zona).date() if zona else date.today()


def fecha_tienda(momento: datetime | date | None) -> date | None:
    """El día en la tienda de un momento que vino de la base.

    Sin zona = UTC (el SQLite de las pruebas guarda el `now()` en UTC pelón;
    Postgres lo trae con zona). Una `date` se queda como está."""
    if momento is None:
        return None
    if not isinstance(momento, datetime):
        return momento
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=timezone.utc)
    zona = _zona()
    return momento.astimezone(zona).date() if zona else momento.astimezone().date()


def fecha_corta(dia: date) -> str:
    """'lun 5 oct'."""
    return f"{_DIAS[dia.weekday()]} {dia.day} {_MESES[dia.month - 1]}"


def dia_mes(dia: date) -> str:
    """'22 sep'."""
    return f"{dia.day} {_MESES[dia.month - 1]}"


def dias_desde(momento: datetime | date | None, hoy: date | None = None) -> int | None:
    """Días de calendario (en la tienda) desde `momento` hasta hoy; None si no hay fecha."""
    dia = fecha_tienda(momento)
    if dia is None:
        return None
    return max(0, ((hoy or hoy_tienda()) - dia).days)


def hace_texto(dias: int) -> str:
    """'hoy' / 'ayer' / 'hace 41 días'."""
    if dias <= 0:
        return "hoy"
    if dias == 1:
        return "ayer"
    return f"hace {dias} días"


def cuando_se_conto(momento: datetime | date | None, hoy: date | None = None) -> str:
    """'lun 5 oct · hace 41 días' (o '' si la jornada no trae fecha)."""
    dia = fecha_tienda(momento)
    if dia is None:
        return ""
    return f"{fecha_corta(dia)} · {hace_texto(dias_desde(dia, hoy))}"


def aviso_conteo_viejo(dias: int | None) -> str:
    """El aviso ámbar; '' si el conteo es de hace menos de `DIAS_AVISO_VIEJO` días."""
    if dias is None or dias < DIAS_AVISO_VIEJO:
        return ""
    return f"Conteo de hace {dias} días: conviene recontar antes de corregir."


# --- qué hacer con cada talla -------------------------------------------------------

def se_acabo(linea) -> bool:
    """Contaron 0, no hay en cajas y nadie la compró ni la pidió.

    La regla la deja en NO_SE_MUEVE o SIN_DATOS porque no tiene ritmo; pero con
    0 piezas no se podía vender: lo cierto es que se acabó. (Con ventas o con
    «pidieron» la regla ya la marca URGENTE.)"""
    return linea.estado in (NO_SE_MUEVE, SIN_DATOS) and linea.conto <= 0 and linea.en_cajas <= 0


def etiqueta_sin_ritmo(linea) -> str:
    """'se acabó' / 'no se mueve' / 'sin datos'; '' si la talla sí tiene ritmo."""
    if se_acabo(linea):
        return "se acabó"
    if linea.estado == NO_SE_MUEVE:
        return "no se mueve"
    if linea.estado == SIN_DATOS:
        return "sin datos"
    return ""


def que_hacer(linea) -> str:
    """El texto de la columna «Qué hacer»."""
    etiqueta = etiqueta_sin_ritmo(linea)
    if etiqueta:
        return etiqueta
    partes = []
    if linea.sugerido:
        partes.append(f"pedir {linea.sugerido}")
    if linea.surtir:
        partes.append(f"surtir {linea.surtir}")
    texto = " · ".join(partes) if partes else "bien"
    return f"¡URGENTE! {texto}" if linea.estado == URGENTE else texto


def _tallas(n: int) -> str:
    return "1 talla" if n == 1 else f"{n} tallas"


def motivo_sin_accion(lineas: Iterable) -> str:
    """Por qué no hay nada que pedir ni surtir, con los estados reales.

    '' si alguna talla sí pide acción (o si no hay tallas)."""
    lineas = list(lineas)
    if not lineas or any(l.estado in ACCION for l in lineas):
        return ""
    bien = sum(1 for l in lineas if l.estado == BIEN)
    acabadas = sum(1 for l in lineas if se_acabo(l))
    sin_ventas = sum(1 for l in lineas if l.estado == NO_SE_MUEVE and not se_acabo(l))
    sin_datos = sum(1 for l in lineas if l.estado == SIN_DATOS and not se_acabo(l))
    partes = []
    if bien:
        partes.append(f"lo que hay alcanza ({_tallas(bien)})")
    if sin_ventas:
        partes.append(f"{_tallas(sin_ventas)} sin ventas")
    if acabadas:
        partes.append("1 se acabó y nadie la pidió" if acabadas == 1 else f"{acabadas} se acabaron y nadie las pidió")
    if sin_datos:
        partes.append(f"faltan días para saber el ritmo ({_tallas(sin_datos)})")
    return "Nada que pedir ni surtir: " + " · ".join(partes) + "."


# --- confirmaciones -----------------------------------------------------------------

def boton_corregir(dias: int | None) -> str:
    """El botón que confirma aplicar: dice la edad del conteo si ya es viejo."""
    if dias is not None and dias >= DIAS_BOTON_VIEJO:
        return f"Sí, corregir con un conteo de hace {dias} días"
    return "Sí, corregir"


def texto_confirmar_aplicar(
    *, quien: str, contado: datetime | date | None, diferencias: Iterable[int], hoy: date | None = None
) -> str:
    """Lo que de verdad hace Aplicar: suma la diferencia de aquel día a cada talla.

    `diferencias` son las de los renglones que todavía no se ajustan (ya
    guardadas al capturar: contado − lo que decía el sistema)."""
    difs = [int(d) for d in diferencias if int(d) != 0]
    dia = fecha_tienda(contado)
    el_dia = f"el {fecha_corta(dia)}" if dia else "en el conteo"
    quien = quien or "la empleada"
    if not difs:
        return (
            f"Ninguna talla tiene diferencia; solo se marca como revisado ({quien} contó {el_dia}).\n\n"
            "Tu pedido se guarda."
        )
    faltan = -sum(d for d in difs if d < 0)
    sobran = sum(d for d in difs if d > 0)
    texto = (
        f"A cada talla se le suma la diferencia que encontró {quien} {el_dia}. "
        f"Se corrigen {_tallas(len(difs))} (faltan {faltan}, sobran {sobran}).\n\n"
        "Tu pedido se guarda."
    )
    dias = dias_desde(dia, hoy)
    aviso = aviso_conteo_viejo(dias)
    return texto + (f"\n\n⚠ {aviso}" if aviso else "")


TEXTO_CONFIRMAR_DESCARTAR = (
    "El conteo se queda como historia, pero NO se corrige el inventario.\n\n¿No usar este conteo?"
)
BOTON_DESCARTAR = "Sí, no usar este conteo"
BOTON_VOLVER = "Volver"


# --- ya revisado --------------------------------------------------------------------

def texto_ya_revisada(*, revisada_at: datetime | date | None, aplicada: bool, por: str = "") -> str:
    """'Corregido el 22 sep por Daniel' / 'No se usó (22 sep)'; '' si no se ha revisado."""
    dia = fecha_tienda(revisada_at)
    if dia is None:
        return ""
    if aplicada:
        return f"Corregido el {dia_mes(dia)}" + (f" por {por}" if por else "")
    return f"No se usó ({dia_mes(dia)})"


def ya_revisada(jornada) -> bool:
    """La jornada ya se aplicó o se descartó: no se vuelve a decidir."""
    return getattr(jornada, "revisada_at", None) is not None
