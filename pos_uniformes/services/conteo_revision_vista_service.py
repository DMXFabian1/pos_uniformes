"""Los textos de la ventana «Revisar conteo», sin Qt (2026-11-15).

La ventana (`ConteoRevisionDialog`) solo pinta; aquí se decide qué decir:

- **Cuándo se contó**: «lun 5 oct · hace 41 días», y el aviso ámbar si el
  conteo ya tiene `DIAS_AVISO_VIEJO` días o más.
- **Por qué no hay nada que pedir**: el motivo real según el estado de cada
  talla (lo que hay alcanza, sin ventas, se acabó, faltan días), en vez de un
  texto fijo.
- **Qué hacer con una talla**: «pedir 6 · surtir 2», «¡URGENTE! …», «se acabó»
  (contaron 0 y nadie la pidió en días suficientes), «no se mueve», «sin datos».
- **La confirmación de aplicar y de descartar**, con botones en español y lo
  que de verdad pasa: a cada talla se le SUMA la diferencia de aquel día.
- **Ya revisado**: «Corregido el 22 sep por Daniel» / «No se usó (22 sep)».

Las reglas de `revision_service.sugerir` no cambian: esto solo las cuenta.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime, timezone
from decimal import Decimal

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


def aviso_conteo_viejo(dias: int | None, resumen=None) -> str:
    """El aviso ámbar; '' si el conteo es de hace menos de `DIAS_AVISO_VIEJO` días.

    Con el `resumen` del ajuste (`conteo_resumen_service`) dice además lo vendido
    desde entonces y las tallas que tuvieron otro ajuste."""
    if dias is None or dias < DIAS_AVISO_VIEJO:
        return ""
    desde = texto_desde_entonces(resumen) if resumen is not None else ""
    if desde:
        return f"Conteo de hace {dias} días: {desde}. Conviene recontar antes de corregir."
    return f"Conteo de hace {dias} días: conviene recontar antes de corregir."


# --- qué hacer con cada talla -------------------------------------------------------

def se_acabo(linea) -> bool:
    """Contaron 0, no hay en cajas y nadie la compró ni la pidió en una ventana
    con días suficientes (NO_SE_MUEVE).

    Con 0 piezas no se podía vender: lo cierto es que se acabó. (Con ventas o
    con «pidieron» la regla ya la marca URGENTE.) Una talla SIN_DATOS en 0 NO
    cuenta: sin días observados no se sabe si se acabó ni si alguien la habría
    pedido; sigue diciendo «sin datos» y entra en «faltan días»."""
    return linea.estado == NO_SE_MUEVE and linea.conto <= 0 and linea.en_cajas <= 0


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

def boton_corregir(dias: int | None, diferencias: Iterable[int] | None = None) -> str:
    """El botón que confirma aplicar: dice la edad del conteo si ya es viejo.

    Si se pasan las `diferencias` y ninguna es distinta de 0, no se corrige
    nada: el botón dice «Sí, marcar como revisado» (sin alarmar por la edad)."""
    if diferencias is not None and not any(int(d) != 0 for d in diferencias):
        return BOTON_MARCAR_REVISADO
    if dias is not None and dias >= DIAS_BOTON_VIEJO:
        return f"Sí, corregir con un conteo de hace {dias} días"
    return "Sí, corregir"


BOTON_MARCAR_REVISADO = "Sí, marcar como revisado"


def texto_confirmar_aplicar(
    *, quien: str, contado: datetime | date | None, diferencias: Iterable[int], hoy: date | None = None,
    resumen=None,
) -> str:
    """Lo que de verdad hace Aplicar: suma la diferencia de aquel día a cada talla.

    `diferencias` son las de los renglones que todavía no se ajustan (ya
    guardadas al capturar: contado − lo que decía el sistema). Con el
    `resumen` del ajuste (tanda 2) dice además el dinero y avisa de las tallas
    que tuvieron otro ajuste después del conteo."""
    difs = [int(d) for d in diferencias if int(d) != 0]
    dia = fecha_tienda(contado)
    el_dia = f"el {fecha_corta(dia)}" if dia else "en el conteo"
    quien = quien or "la empleada"
    if not difs:
        return (
            f"Ninguna talla tiene diferencia; solo se marca como revisado ({quien} contó {el_dia}).\n\n"
            "Tu pedido se guarda."
        )
    if resumen is not None:
        texto = f"A cada talla se le suma la diferencia que encontró {quien} {el_dia}. {texto_resumen_ajuste(resumen)}"
        ojo = texto_ojo_ajuste_posterior(resumen)
        if ojo:
            texto += f"\n\n{ojo}"
        texto += "\n\nTu pedido se guarda."
    else:
        faltan = -sum(d for d in difs if d < 0)
        sobran = sum(d for d in difs if d > 0)
        texto = (
            f"A cada talla se le suma la diferencia que encontró {quien} {el_dia}. "
            f"Se corrigen {_tallas(len(difs))} (faltan {faltan}, sobran {sobran}).\n\n"
            "Tu pedido se guarda."
        )
    dias = dias_desde(dia, hoy)
    aviso = aviso_conteo_viejo(dias, resumen)
    return texto + (f"\n\n⚠ {aviso}" if aviso else "")


# --- el resumen del ajuste (tanda 2) ------------------------------------------------

_MENOS = "\u2212"   # «−», el signo de menos de verdad


def pesos(valor, *, signo: bool = False) -> str:
    """'$1,385' (con centavos solo si los hay); con `signo`: '−$1,385' / '+$300' / '$0'.

    Mismo formato que el resto del POS (`telegram_cortes_service._pesos`)."""
    monto = Decimal(str(valor or 0))
    absoluto = abs(monto)
    cifra = f"${absoluto:,.0f}" if absoluto == absoluto.to_integral_value() else f"${absoluto:,.2f}"
    if monto < 0:
        return f"{_MENOS}{cifra}" if signo else f"-{cifra}"
    if signo and monto > 0:
        return f"+{cifra}"
    return cifra


def _y(partes: list[str]) -> str:
    """'a', 'a y b', 'a, b y c'."""
    if len(partes) <= 1:
        return "".join(partes)
    return ", ".join(partes[:-1]) + " y " + partes[-1]


def _nombre_talla(t, varias_prendas: bool) -> str:
    """'36' o, si la jornada trae varias prendas, 'Playera Chazarilla 36'."""
    if not varias_prendas:
        return str(t.talla)
    from pos_uniformes.services.conteo_hoja_carta_service import nombre_para_hoja

    return f"{nombre_para_hoja(t.producto, '')} {t.talla}".strip()


def _varias_prendas(resumen) -> bool:
    return len({t.producto for t in resumen.tallas}) > 1


def texto_resumen_ajuste(resumen) -> str:
    """«Se corrigen 4 tallas: faltan 7, sobran 0 (−$1,385 a precio de venta).»"""
    n = resumen.tallas_a_corregir
    if n == 0:
        return "Ninguna talla cambia."
    verbo = "Se corrige" if n == 1 else "Se corrigen"
    dinero = f"{pesos(resumen.valor, signo=True)} a precio de venta"
    if resumen.tallas_sin_precio:
        sin = resumen.tallas_sin_precio
        dinero += "; 1 talla sin precio" if sin == 1 else f"; {sin} tallas sin precio"
    return f"{verbo} {_tallas(n)}: faltan {resumen.salen}, sobran {resumen.entran} ({dinero})."


_MAX_TALLAS_EN_TEXTO = 5


def _tallas_con_fecha(tallas, varias: bool) -> str:
    """'32 (18 oct) y 36 (20 oct)'; de 5 en adelante, '… y 3 más'."""
    nombres = [
        f"{_nombre_talla(t, varias)} ({dia_mes(fecha_tienda(t.ajuste_posterior))})"
        for t in tallas[:_MAX_TALLAS_EN_TEXTO]
    ]
    resto = len(tallas) - len(nombres)
    if resto > 0:
        nombres.append(f"{resto} más")
    return _y(nombres)


def texto_ojo_ajuste_posterior(resumen) -> str:
    """«Ojo: la talla 36 tuvo otro ajuste el 20 oct; se le suma la diferencia otra vez.»

    Solo las tallas que Aplicar todavía corrige; '' si ninguna tuvo otro ajuste."""
    tallas = list(resumen.a_corregir_con_ajuste_posterior)
    if not tallas:
        return ""
    varias = _varias_prendas(resumen)
    if len(tallas) == 1:
        t = tallas[0]
        nombre = f"la talla {t.talla}" if not varias else _nombre_talla(t, True)
        return (
            f"Ojo: {nombre} tuvo otro ajuste el {dia_mes(fecha_tienda(t.ajuste_posterior))}; "
            "se le suma la diferencia otra vez."
        )
    lista = _tallas_con_fecha(tallas, varias)
    sujeto = f"las tallas {lista}" if not varias else lista
    return f"Ojo: {sujeto} tuvieron otro ajuste después del conteo; se les suma la diferencia otra vez."


def texto_desde_entonces(resumen) -> str:
    """«desde entonces se vendieron 13 piezas y la talla 36 tuvo otro ajuste (20 oct)»; '' si nada."""
    partes = []
    n = resumen.vendidas_desde
    if n:
        partes.append("desde entonces se vendió 1 pieza" if n == 1 else f"desde entonces se vendieron {n} piezas")
    tallas = list(resumen.con_ajuste_posterior)
    if tallas:
        varias = _varias_prendas(resumen)
        lista = _tallas_con_fecha(tallas, varias)
        if len(tallas) == 1:
            sujeto = f"la talla {lista}" if not varias else lista
            ajuste = f"{sujeto} tuvo otro ajuste"
        else:
            sujeto = f"las tallas {lista}" if not varias else lista
            ajuste = f"{sujeto} tuvieron otro ajuste"
        partes.append(ajuste if partes else f"desde entonces {ajuste}")
    return " y ".join(partes)


def texto_talla_ajuste(t) -> str:
    """Una línea para el «por qué» de una talla: «el sistema decía 10, contó 6 (−4) ·
    vendidas desde el conteo 2 · queda hoy 4»."""
    dif = "cuadra" if t.diferencia == 0 else (f"{_MENOS}{-t.diferencia}" if t.diferencia < 0 else f"+{t.diferencia}")
    partes = [f"el sistema decía {t.stock_sistema}, contó {t.conto} ({dif})"]
    partes.append(f"vendidas desde el conteo {t.vendidas_desde}")
    if t.ajustado:
        partes.append(f"ya corregida; hoy hay {t.tienda_hoy}")
    elif t.diferencia:
        queda = f"queda hoy {t.queda_hoy}"
        partes.append(queda + (" (recontar)" if t.queda_hoy < 0 else ""))
    if t.ajuste_posterior is not None:
        partes.append(f"otro ajuste el {dia_mes(fecha_tienda(t.ajuste_posterior))}")
    return " · ".join(partes)


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
