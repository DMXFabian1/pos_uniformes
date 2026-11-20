"""💼 Mi pago desde el celular: la cuenta del pago de Daniel en el bot.

Daniel, 2026-11-19: «¿puedes hacer que también lo gestione con mi bot de
Telegram?». Lo mismo que «💼 Mi pago» del kiosko (Libreta → 💼 Caja), sin
estar en la tienda:

    /mipago            cuál toca, cuánto, los 4 del mes y los días de más
    /mipago dic        otro mes (también /mipago 12)
    /mepagaron         registra el que toca (el atrasado más viejo primero)
    /mepagaron 2400 18/11 · /mepagaron 2 de 4 · /mepagaron pago 14/11
    /deshacermipago    deshace el último registrado (o /deshacermipago 21/11)
    /diasdemas         tus días de más: págamelo o guárdamelo
    /vino yo · /falta_yo · /descanso yo   tus días, como los de ellas

Aquí no se calcula nada: las reglas viven en `pago_dueno_service`. Lo que sí
vive aquí es el candado de siempre del bot: lo que mueve la cuenta pasa por
un segundo toque, el botón lleva lo que se enseñó (si ya cambió, se pregunta
otra vez) y un botón de otro día ya no hace nada (`boton_vencido`).

Es solo la cuenta: nada de esto sale del cajón ni toca el corte.
"""

from __future__ import annotations

import logging
import re
from datetime import date, timedelta
from decimal import Decimal

from pos_uniformes.services import pago_dueno_service as pd

logger = logging.getLogger(__name__)

#: Prefijo de los botones de esta pantalla (máx. 64 bytes por botón).
PREFIJO = "mp:"

#: Los comandos que atiende este servicio (nombre → qué hace).
COMANDOS = {
    "mipago": "ver",
    "mi_pago": "ver",
    "mispagos": "ver",
    "mepagaron": "pagar",
    "me_pagaron": "pagar",
    "yamepagaron": "pagar",
    "deshacermipago": "deshacer",
    "diasdemas": "dias",
    "dias_de_mas": "dias",
    "díasdemás": "dias",
}

#: Cómo se nombra Daniel a sí mismo en /vino, /falta y /descanso.
_YO = {"yo", "mi", "mí", "dueño", "dueno", "vend-1", "vend1"}
#: «yo» y «mi» también son el principio de un nombre (Yolanda, Miriam): con
#: una empleada así, no se adivina, se pregunta.
_YO_AMBIGUO = {"yo", "mi", "mí"}
#: «daniel» también, salvo que haya una empleada que empiece así.
_DANIEL = {"daniel"}

TEXTO_SIN_CUENTA = (
    "Tu cuenta de pago no está configurada: ábrela en el kiosko, "
    "Libreta → 💼 Caja → Mi pago."
)
TEXTO_SIN_TABLAS = (
    "La base de la tienda todavía no tiene la cuenta de tu pago: falta "
    "actualizar la caja (/version). Cuando esté, ábrela en el kiosko, "
    "Libreta → 💼 Caja → Mi pago."
)

_EMOJI = {
    pd.PAGADO: "✅",
    pd.TOCA_HOY: "🔔",
    pd.PENDIENTE: "⏳",
    pd.ATRASADO: "❗",
}
_ESTADO = {
    pd.PAGADO: "pagado",
    pd.TOCA_HOY: "toca hoy",
    pd.PENDIENTE: "pendiente",
    pd.ATRASADO: "atrasado",
}
_MESES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
          "septiembre", "octubre", "noviembre", "diciembre")
_MESES_CORTOS = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")


class SinCuenta(Exception):
    """La cuenta no está configurada/activa, o la base no tiene las tablas."""

    def __init__(self, texto: str) -> None:
        super().__init__(texto)
        self.texto = texto


# ─── Piezas ──────────────────────────────────────────────────────────────


def _teclado(filas):
    from pos_uniformes.services import telegram_service

    return telegram_service.teclado(filas)


def es_de_mi_pago(dato: str) -> bool:
    return str(dato or "").startswith(PREFIJO)


def _iso(f: date) -> str:
    return f"{f:%Y%m%d}"


def _de_iso(texto: str) -> date | None:
    try:
        return date(int(texto[:4]), int(texto[4:6]), int(texto[6:8])) if len(texto) == 8 else None
    except ValueError:
        return None


def _dias(n: int) -> str:
    return f"{n} día" if n == 1 else f"{n} días"


def _faltas(n: int) -> str:
    return f"{n} falta" if n == 1 else f"{n} faltas"


def _fechas(fechas) -> str:
    return ", ".join(pd.fecha_corta(f) for f in fechas)


def _cuando_te_pagaron(f: date, hoy: date) -> str:
    if f == hoy:
        return f"hoy, {pd.fecha_corta(f, con_dia=True)}"
    if f == hoy - timedelta(days=1):
        return f"ayer, {pd.fecha_corta(f, con_dia=True)}"
    texto = pd.fecha_corta(f, con_dia=True)
    # De otro año se dice: «lun 28-dic» a secas parecería de este.
    return texto if f.year == hoy.year else f"{texto} de {f.year}"


def es_sin_tablas(exc: BaseException) -> bool:
    """¿La base todavía no tiene las tablas del pago del dueño (kiosko o caja
    sin migrar)? Una base caída NO es esto: ésa la dice `error_legible`."""
    texto = f"{type(exc).__name__} {exc} {getattr(exc, 'orig', '')}".lower()
    return (
        "no such table" in texto
        or "undefinedtable" in texto
        or ("relation" in texto and "does not exist" in texto)
    )


def _cuenta(session) -> pd.ConfigPagoDueno:
    """La configuración vigente, o `SinCuenta` con el texto que lo explica."""
    try:
        config = pd.cargar_config(session)
    except Exception as exc:  # noqa: BLE001
        if es_sin_tablas(exc):
            try:
                session.rollback()
            except Exception:  # noqa: BLE001
                pass
            raise SinCuenta(TEXTO_SIN_TABLAS) from exc
        raise
    if config is None or not config.vigente:
        raise SinCuenta(TEXTO_SIN_CUENTA)
    return config


def _a_salvo(session, hacer, *, botones_si_falla: str = ""):
    """Corre `hacer()`; sin cuenta o sin tablas contesta claro en vez de
    tumbar el bot. Lo demás (base caída) sube a `error_legible`."""
    try:
        return hacer()
    except SinCuenta as aviso:
        return aviso.texto, botones_si_falla
    except Exception as exc:  # noqa: BLE001
        if es_sin_tablas(exc):
            try:
                session.rollback()
            except Exception:  # noqa: BLE001
                pass
            return TEXTO_SIN_TABLAS, botones_si_falla
        raise


def _volver(filas=None, *, mi_pago: bool = True) -> str:
    extra = [("‹ Mi pago", f"{PREFIJO}ver")] if mi_pago else []
    return _teclado(list(filas or []) + [extra + [("‹ Menú", "m:raiz")]])


def _monto_real(p: pd.DesglosePago) -> Decimal:
    """Lo que de verdad se pagó si ya está registrado; si no, lo calculado."""
    return p.registro.monto if p.registro is not None else p.monto


def ajustes(p: pd.DesglosePago) -> list[str]:
    """El desglose corto de un pago: solo lo que lo mueve o lo explica."""
    lineas = []
    if p.dias_extra_pagados:
        lineas.append(f"+ {_dias(len(p.dias_extra_pagados))} de más ({_fechas(p.dias_extra_pagados)}) "
                      f"+{pd.dinero_texto(p.monto_extra)}")
    if p.faltas_descontadas:
        lineas.append(f"− {_faltas(len(p.faltas_descontadas))} ({_fechas(p.faltas_descontadas)}) "
                      f"−{pd.dinero_texto(p.descuento_faltas)}")
    if p.faltas_cubiertas:
        lineas.append(f"falta cubierta con día a favor ({_fechas(p.faltas_cubiertas)})")
    guardados = [f for f in p.dias_extra_acumulados if f not in p.dias_extra_sin_decidir]
    if guardados:
        lineas.append(f"día de más guardado a favor ({_fechas(guardados)})")
    if p.dias_extra_sin_decidir:
        lineas.append(f"día de más sin decidir ({_fechas(p.dias_extra_sin_decidir)}), por ahora se guarda")
    if p.registro is not None and p.registro.monto != p.monto:
        lineas.append(f"calculado {pd.dinero_texto(p.monto)}, pagado {pd.dinero_texto(p.registro.monto)}")
    return lineas


def _etiqueta_boton_pagar(p: pd.DesglosePago) -> str:
    return f"💵 Ya me pagaron ({p.etiqueta} · {pd.dinero_texto(p.monto)})"


def _botones_dia(f: date, *, pagar: bool = True, guardar: bool = True) -> list[tuple[str, str]]:
    fila = []
    if pagar:
        fila.append((f"💵 Págamelo {pd.fecha_corta(f)}", f"{PREFIJO}dia:{_iso(f)}:p"))
    if guardar:
        fila.append((f"📦 Guárdamelo {pd.fecha_corta(f)}", f"{PREFIJO}dia:{_iso(f)}:a"))
    return fila


# ─── El mes que se quiere ver ────────────────────────────────────────────


def leer_mes(argumento: str, hoy: date) -> tuple[int, int]:
    """«», «dic», «diciembre», «12», «12/2026», «anterior», «siguiente» →
    (año, mes). Sin año, el más cercano a hoy. ValueError si no se entiende."""
    t = (argumento or "").strip().lower().rstrip(".")
    if not t or t in ("hoy", "este", "actual"):
        return hoy.year, hoy.month
    total = hoy.year * 12 + hoy.month - 1
    if t in ("anterior", "pasado", "antes"):
        total -= 1
        return total // 12, total % 12 + 1
    if t in ("siguiente", "próximo", "proximo", "que viene"):
        total += 1
        return total // 12, total % 12 + 1
    anio = None
    m = re.fullmatch(r"(\d{1,2})(?:[/-](\d{2,4}))?", t)
    if m:
        mes = int(m.group(1))
        if m.group(2):
            anio = int(m.group(2)) + (2000 if len(m.group(2)) == 2 else 0)
    else:
        partes = t.split()
        nombre = partes[0][:3]
        if nombre == "set":
            nombre = "sep"
        if nombre not in _MESES_CORTOS or len(partes) > 2:
            raise ValueError(f"No entendí «{argumento.strip()}» como mes. Por ejemplo: /mipago dic o /mipago 12")
        mes = _MESES_CORTOS.index(nombre) + 1
        if len(partes) == 2:
            if not partes[1].isdigit():
                raise ValueError(f"No entendí «{argumento.strip()}» como mes. Por ejemplo: /mipago dic 2026")
            anio = int(partes[1])
    if not 1 <= mes <= 12:
        raise ValueError(f"«{argumento.strip()}» no es un mes. Por ejemplo: /mipago dic o /mipago 12")
    if anio is None:
        # El más cercano: en noviembre, «ene» es el que viene, no el que pasó.
        anio = min((hoy.year - 1, hoy.year, hoy.year + 1),
                   key=lambda a: abs((a * 12 + mes - 1) - total))
    return anio, mes


def _mes_vecino(year: int, month: int, delta: int) -> tuple[int, int]:
    total = year * 12 + month - 1 + delta
    return total // 12, total % 12 + 1


# ─── /mipago ─────────────────────────────────────────────────────────────


def texto_y_botones(session, argumento: str = "", *, hoy: date | None = None) -> tuple[str, str]:
    """El resumen de la cuenta: el pago que toca, último pago, días a favor,
    atrasados, los 4 del mes y los días de más sin decidir."""
    hoy = hoy or date.today()

    def hacer():
        try:
            year, month = leer_mes(argumento, hoy)
        except ValueError as exc:
            return str(exc), _volver(mi_pago=False)
        config = _cuenta(session)
        return _pantalla(session, config, year, month, hoy)

    return _a_salvo(session, hacer, botones_si_falla=_volver(mi_pago=False))


def _pantalla(session, config, year: int, month: int, hoy: date) -> tuple[str, str]:
    datos = pd.cargar_datos(session, config)
    rec = pd.calcular_recordatorio(config, datos, hoy)
    objetivo = pd.pago_objetivo(rec)

    lineas = ["💼 MI PAGO (no sale del cajón)", ""]
    if objetivo.estado(hoy) == pd.ATRASADO:
        atraso = (hoy - objetivo.fecha_programada).days
        lineas.append(f"❗ PAGO ATRASADO: {objetivo.etiqueta} · {pd.fecha_corta(objetivo.fecha_programada, con_dia=True)}")
        lineas.append(f"   {pd.dinero_texto(objetivo.monto)} · cubre del {pd.fecha_corta(objetivo.desde)} "
                      f"al {pd.fecha_corta(objetivo.hasta)} · atrasado {_dias(max(1, atraso))}")
    else:
        lineas.append(f"💵 TOCA: {objetivo.etiqueta} · {pd.fecha_corta(objetivo.fecha_programada, con_dia=True)}")
        lineas.append(f"   {pd.dinero_texto(objetivo.monto)} · cubre del {pd.fecha_corta(objetivo.desde)} "
                      f"al {pd.fecha_corta(objetivo.hasta)} · {pd.cuando_toca((objetivo.fecha_programada - hoy).days)}")
    lineas.extend(f"   {a}" for a in ajustes(objetivo))
    lineas.append("")

    if datos.registros:
        r = max(datos.registros.values(), key=lambda x: (x.fecha_pago, x.fecha_programada))
        extra = f" (fue el pago del {pd.fecha_corta(r.fecha_programada)})" if r.fecha_pago != r.fecha_programada else ""
        lineas.append(f"Último pago: {pd.fecha_corta(r.fecha_pago)} · {pd.dinero_texto(r.monto)}{extra}")
    else:
        lineas.append("Último pago: ninguno registrado")
    lineas.append(f"Días a favor: {rec.dias_a_favor}")
    if rec.atrasados:
        lineas.append(f"Atrasados: {len(rec.atrasados)} ("
                      + ", ".join(f"{a.etiqueta} {pd.fecha_corta(a.fecha_programada)}" for a in rec.atrasados) + ")")
    else:
        lineas.append("Atrasados: ninguno")
    if not pd.tiene_descanso(datos.horario):
        lineas.append("⚠️ Tu descanso fijo no está guardado en el calendario: sin él no se cuentan días de más.")

    # Los pagos del mes, uno por renglón.
    lineas.append("")
    lineas.append(f"Pagos de {_MESES[month - 1]} {year}:")
    por_fecha = {p.fecha_programada: p for p in pd.pagos_del_mes(config, datos, year, month)}
    for i, dia in enumerate(sorted(config.dias_de_pago), start=1):
        f = date(year, month, dia)
        p = por_fecha.get(f)
        reg = datos.registros.get(f)
        etiqueta = f"{i} de {len(config.dias_de_pago)} · {pd.fecha_corta(f, con_dia=True)}"
        if p is not None:
            estado = p.estado(hoy)
            cola = f"pagado el {pd.fecha_corta(p.registro.fecha_pago)}" if estado == pd.PAGADO else _ESTADO[estado]
            lineas.append(f"{_EMOJI[estado]} {etiqueta} · {pd.dinero_texto(_monto_real(p))} · {cola}")
            if p.fecha_programada != objetivo.fecha_programada:
                lineas.extend(f"      {a}" for a in ajustes(p))
        elif reg is not None:
            # Uno de antes del inicio de la cuenta que sí se registró.
            lineas.append(f"✅ {etiqueta} · {pd.dinero_texto(reg.monto)} · pagado el {pd.fecha_corta(reg.fecha_pago)}")
        else:
            lineas.append(f"▫️ {etiqueta} · antes de tu cuenta")

    sin_decidir = [e.fecha for e in pd.dias_extra(config, datos, hoy) if e.sin_decidir]
    if sin_decidir:
        lineas.append("")
        lineas.append(f"📌 Días de más sin decidir (por ahora se guardan): {_fechas(sin_decidir)}")
        lineas.append(f"Págamelo suma {pd.dinero_texto(config.valor_dia)} a su pago; Guárdamelo lo deja a favor.")

    lineas.append("")
    lineas.append("Con otro monto o fecha: /mepagaron 2400 18/11 · Días de más: /diasdemas")

    filas = [[(_etiqueta_boton_pagar(objetivo), f"{PREFIJO}pagar:{_iso(objetivo.fecha_programada)}")]]
    for f in sin_decidir[-4:]:
        filas.append(_botones_dia(f))
    (ya, ma), (ys, ms) = _mes_vecino(year, month, -1), _mes_vecino(year, month, +1)
    filas.append([
        (f"‹ {_MESES_CORTOS[ma - 1]}", f"{PREFIJO}mes:{ya}{ma:02d}"),
        (f"{_MESES_CORTOS[ms - 1]} ›", f"{PREFIJO}mes:{ys}{ms:02d}"),
    ])
    return "\n".join(lineas), _volver(filas, mi_pago=False)


# ─── /mepagaron ──────────────────────────────────────────────────────────


#: Hasta cuántos días atrás un «dd/mm» sin año puede ser del año pasado
#: (a inicios de enero, un día de diciembre).
_DIAS_ATRAS_SIN_ANIO = 45


def _leer_dia(texto: str, hoy: date, *, hacia_atras: bool) -> date | None:
    """«18/11», «18/11/2026», «hoy», «ayer», «antier» → fecha (None si no lo es).

    `hacia_atras` (la fecha en que te pagaron): sin año es de este año, y si
    cae en el futuro se queda en el futuro para que se rechace. Solo a
    inicios de año un «28/12» es del año pasado (hasta ~6 semanas atrás):
    antes, «24/11» escrito el 19-nov se volvía 24-nov del año pasado y se
    registraba sin aviso (revisión 2026-11-19). Si no, el más cercano a hoy."""
    t = texto.strip().lower()
    if t == "hoy":
        return hoy
    if t == "ayer":
        return hoy - timedelta(days=1)
    if t in ("antier", "anteayer"):
        return hoy - timedelta(days=2)
    m = re.fullmatch(r"(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?", t)
    if not m:
        return None
    d, mes = int(m.group(1)), int(m.group(2))
    if m.group(3):
        anio = int(m.group(3)) + (2000 if len(m.group(3)) == 2 else 0)
        return date(anio, mes, d)
    if hacia_atras:
        f = date(hoy.year, mes, d)
        if f <= hoy:
            return f
        try:
            antes = date(hoy.year - 1, mes, d)
        except ValueError:        # un 29/02 que el año pasado no tuvo
            return f
        return antes if (hoy - antes).days <= _DIAS_ATRAS_SIN_ANIO else f
    return min((date(a, mes, d) for a in (hoy.year - 1, hoy.year, hoy.year + 1)),
               key=lambda f: abs((f - hoy).days))


_EJEMPLOS_PAGAR = (
    "Así:\n"
    "/mepagaron — el que toca, con el monto calculado y fecha de hoy\n"
    "/mepagaron 2400 — con otro monto\n"
    "/mepagaron 18/11 — te pagaron ese día (también ayer, antier)\n"
    "/mepagaron 2 de 4 — elige el pago de este mes · /mepagaron pago 14/11 — por su fecha"
)


def leer_pedido_pago(argumento: str, hoy: date, dias_de_pago) -> tuple[date | None, date, Decimal | None]:
    """(pago elegido o None = el que toca, fecha en que te pagaron, monto o
    None = el calculado). ValueError con el ejemplo si algo no se entiende."""
    t = " ".join((argumento or "").lower().split())
    programada = None
    m = re.search(r"\b(\d)\s*de\s*(\d)\b", t)
    if m:
        n = int(m.group(1))
        dias = sorted(dias_de_pago)
        if not 1 <= n <= len(dias):
            raise ValueError(f"No hay pago {n} de {len(dias)}.\n\n" + _EJEMPLOS_PAGAR)
        programada = date(hoy.year, hoy.month, dias[n - 1])
        t = (t[:m.start()] + " " + t[m.end():]).strip()
    m = re.search(r"\b(?:el\s+)?(?:pago|del)\s+(?:del\s+)?(\S+)", t)
    if m:
        if programada is not None:
            raise ValueError("Elige el pago una sola vez (o «2 de 4» o «pago 14/11»).\n\n" + _EJEMPLOS_PAGAR)
        try:
            programada = _leer_dia(m.group(1), hoy, hacia_atras=False)
        except ValueError:
            programada = None
        if programada is None:
            raise ValueError(f"No entendí «{m.group(1)}» como la fecha del pago.\n\n" + _EJEMPLOS_PAGAR)
        t = (t[:m.start()] + " " + t[m.end():]).strip()
    fecha_pago = None
    monto = None
    from pos_uniformes.services.telegram_bot_service import leer_cifra

    for palabra in t.split():
        if palabra in ("si", "sí", "el", "me", "pagaron"):
            continue
        try:
            dia = _leer_dia(palabra, hoy, hacia_atras=True)
        except ValueError:
            raise ValueError(f"«{palabra}» no es un día que exista.") from None
        if dia is not None:
            if fecha_pago is not None:
                raise ValueError("Van dos fechas y no sé cuál es la buena.\n\n" + _EJEMPLOS_PAGAR)
            fecha_pago = dia
            continue
        cifra = leer_cifra(palabra)
        if cifra is not None:
            if monto is not None:
                raise ValueError("Van dos cantidades y no sé cuál es la buena.\n\n" + _EJEMPLOS_PAGAR)
            monto = cifra
            continue
        raise ValueError(f"No entendí «{palabra}».\n\n" + _EJEMPLOS_PAGAR)
    return programada, fecha_pago or hoy, monto


def _boton_pagarok(programada: date, fecha_pago: date, monto: Decimal, calculado: bool) -> str:
    return f"{PREFIJO}pagarok:{_iso(programada)}:{_iso(fecha_pago)}:{'c' if calculado else 'm'}{monto:.2f}"


def _pregunta_pagar(config, datos, programada: date, fecha_pago: date, monto: Decimal | None,
                    hoy: date, *, aviso: str = "") -> tuple[str, str]:
    """El segundo paso: qué se va a registrar, con los botones Sí / No."""
    p = pd.desglose_de_pago(config, datos, programada)
    calculado = monto is None
    total = p.monto if calculado else monto
    lineas = ([aviso, ""] if aviso else []) + [
        "¿Registro este pago?",
        "",
        f"💵 {p.etiqueta} · {pd.fecha_corta(programada, con_dia=True)} "
        f"(cubre del {pd.fecha_corta(p.desde)} al {pd.fecha_corta(p.hasta)})",
        f"Monto: {pd.dinero_texto(total)}" + (" (el calculado)" if calculado
                                              else f" (el calculado es {pd.dinero_texto(p.monto)})"),
        f"Te pagaron: {_cuando_te_pagaron(fecha_pago, hoy)}",
    ]
    lineas.extend(f"   {a}" for a in ajustes(p))
    lineas.append("")
    lineas.append("Es solo la cuenta: no sale del cajón. Otro monto o fecha: /mepagaron 2400 18/11")
    filas = [[
        (f"✅ Sí, me pagaron {pd.dinero_texto(total)}", _boton_pagarok(programada, fecha_pago, total, calculado)),
        ("✖️ No", f"{PREFIJO}no"),
    ]]
    return "\n".join(lineas), _teclado(filas)


def preparar_pago(session, argumento: str = "", *, hoy: date | None = None) -> tuple[str, str]:
    """/mepagaron: enseña qué se registraría y pide el segundo toque. No escribe."""
    hoy = hoy or date.today()

    def hacer():
        config = _cuenta(session)
        try:
            programada, fecha_pago, monto = leer_pedido_pago(argumento, hoy, config.dias_de_pago)
        except ValueError as exc:
            return str(exc), _volver()
        datos = pd.cargar_datos(session, config)
        aviso = ""
        if programada is None:
            programada = pd.pago_objetivo(pd.calcular_recordatorio(config, datos, hoy)).fecha_programada
        elif programada > hoy and _numero_elegido(argumento):
            programada, aviso = _el_atrasado_con_ese_numero(config, datos, programada, hoy)
        return _validar_y_preguntar(config, datos, programada, fecha_pago, monto, hoy, aviso=aviso)

    return _a_salvo(session, hacer, botones_si_falla=_volver(mi_pago=False))


def _numero_elegido(argumento: str) -> bool:
    """¿El pago se eligió con «N de M»?"""
    return re.search(r"\b(\d)\s*de\s*(\d)\b", " ".join((argumento or "").lower().split())) is not None


def _el_atrasado_con_ese_numero(config, datos, programada: date, hoy: date) -> tuple[date, str]:
    """«/mepagaron 4 de 4» el 2-dic con el del 28-nov sin pagar: es el
    atrasado que el bot acaba de enseñar, no el 28-dic que aún no llega
    (revisión 2026-11-19). Sin atrasado con ese número, el de este mes."""
    rec = pd.calcular_recordatorio(config, datos, hoy)
    numero, _ = pd.numero_de_pago(config, programada)
    mismos = [a for a in (rec.atrasados if rec is not None else []) if a.numero == numero]
    if not mismos:
        return programada, ""
    atrasado = max(mismos, key=lambda a: a.fecha_programada).fecha_programada
    aviso = (f"Tomé el {numero} de {len(config.dias_de_pago)} de {_MESES[atrasado.month - 1]} "
             f"({pd.fecha_corta(atrasado)}), que está atrasado. Si era el de "
             f"{_MESES[programada.month - 1]}: /mepagaron pago {programada:%d/%m}")
    return atrasado, aviso


def _validar_y_preguntar(config, datos, programada, fecha_pago, monto, hoy, *, aviso: str = ""):
    if not pd.es_fecha_de_pago(config, programada):
        dias = ", ".join(str(d) for d in config.dias_de_pago)
        return (f"El {pd.fecha_corta(programada)} no es fecha de pago (son los días {dias}).\n\n"
                + _EJEMPLOS_PAGAR), _volver()
    ya = datos.registros.get(programada)
    if ya is not None:
        return (f"El pago {pd.desglose_de_pago(config, datos, programada).etiqueta} del "
                f"{pd.fecha_corta(programada)} ya está registrado: {pd.dinero_texto(ya.monto)}, "
                f"pagado el {pd.fecha_corta(ya.fecha_pago)}.\n\n"
                f"Si fue un error: /deshacermipago {programada:%d/%m}"), _volver()
    if fecha_pago > hoy:
        return "La fecha en que te pagaron no puede ser futura.", _volver()
    if monto is not None and monto < 0:
        return "El monto no puede ser negativo.", _volver()
    return _pregunta_pagar(config, datos, programada, fecha_pago, monto, hoy, aviso=aviso)


def _pagar_ok(session, crudo: str, *, quien: str, hoy: date) -> tuple[str, str, str]:
    """«mp:pagarok:20261121:20261119:c2500.00» ya confirmado: se registra."""
    partes = crudo.split(":")
    programada = _de_iso(partes[0]) if partes else None
    fecha_pago = _de_iso(partes[1]) if len(partes) > 1 else None
    if programada is None or fecha_pago is None or len(partes) < 3 or partes[2][:1] not in ("c", "m"):
        return "No conozco ese botón", "", ""
    from pos_uniformes.services.telegram_bot_service import leer_cifra

    calculado = partes[2][0] == "c"
    visto = leer_cifra(partes[2][1:])
    if visto is None:
        return "No conozco ese botón", "", ""
    config = _cuenta(session)
    datos = pd.cargar_datos(session, config)
    ya = datos.registros.get(programada)
    if ya is not None:
        # Doble toque o botón de un mensaje viejo: no se registra dos veces.
        return ("Ya estaba",
                f"Ese pago ya estaba registrado: {pd.dinero_texto(ya.monto)}, pagado el "
                f"{pd.fecha_corta(ya.fecha_pago)}. No registré nada otra vez.",
                _volver())
    if calculado:
        ahora_es = pd.desglose_de_pago(config, datos, programada).monto
        if ahora_es != visto:
            texto, botones = _validar_y_preguntar(
                config, datos, programada, fecha_pago, None, hoy,
                aviso=(f"El monto cambió desde que lo viste: era {pd.dinero_texto(visto)} y ahora es "
                       f"{pd.dinero_texto(ahora_es)}. No registré nada."),
            )
            return "Cambió el monto", texto, botones
    try:
        p = pd.registrar_pago(session, programada, fecha_pago, visto, quien, hoy=hoy)
    except (ValueError, PermissionError) as exc:
        session.rollback()
        return "No se pudo", f"No se pudo: {exc}", _volver()
    texto = (f"✅ Anotado: te pagaron el {p.etiqueta} ({pd.fecha_corta(programada, con_dia=True)}) · "
             f"{pd.dinero_texto(visto)}, el {pd.fecha_corta(fecha_pago)}.")
    try:
        rec = pd.calcular_recordatorio(config, pd.cargar_datos(session, config), hoy)
        sig = pd.pago_objetivo(rec)
        if sig.estado(hoy) == pd.ATRASADO:
            texto += (f"\n\nSigue atrasado: {sig.etiqueta} ({pd.fecha_corta(sig.fecha_programada)}) · "
                      f"{pd.dinero_texto(sig.monto)}.")
        else:
            texto += (f"\n\nEl que sigue: {sig.etiqueta} · {pd.fecha_corta(sig.fecha_programada, con_dia=True)} · "
                      f"{pd.dinero_texto(sig.monto)} ({pd.cuando_toca((sig.fecha_programada - hoy).days).lower()}).")
    except Exception:  # noqa: BLE001 — el pago ya quedó; esto es adorno
        logger.warning("Mi pago: no se pudo armar el siguiente", exc_info=True)
    texto += f"\n\nSi fue un error: /deshacermipago {programada:%d/%m}"
    return "Anotado", texto, _volver()


# ─── /deshacermipago ─────────────────────────────────────────────────────


def _boton_deshacerok(r: pd.RegistroPago) -> str:
    return f"{PREFIJO}deshacerok:{_iso(r.fecha_programada)}:{_iso(r.fecha_pago)}:{r.monto:.2f}"


def _ultimo_registrado(session) -> date | None:
    """La fecha programada del último pago que se registró (el más nuevo)."""
    from pos_uniformes.database.models import PagoDuenoRegistro

    fila = session.query(PagoDuenoRegistro).order_by(PagoDuenoRegistro.id.desc()).first()
    return fila.fecha_programada if fila is not None else None


def preparar_deshacer(session, argumento: str = "", *, hoy: date | None = None) -> tuple[str, str]:
    """/deshacermipago [dd/mm]: enseña qué se deshace y pide el segundo toque."""
    hoy = hoy or date.today()

    def hacer():
        config = _cuenta(session)
        datos = pd.cargar_datos(session, config)
        arg = (argumento or "").strip()
        if arg:
            try:
                programada = _leer_dia(arg, hoy, hacia_atras=False)
            except ValueError:
                programada = None
            if programada is None:
                return (f"No entendí «{arg}» como fecha. Es la fecha del pago (7, 14, 21 o 28): "
                        "/deshacermipago 21/11"), _volver()
        else:
            programada = _ultimo_registrado(session)
            if programada is None:
                return "No hay ningún pago tuyo registrado; nada que deshacer.", _volver()
        r = datos.registros.get(programada)
        if r is None:
            return (f"No tengo registrado el pago del {pd.fecha_corta(programada)}; nada que deshacer.\n"
                    "Mira /mipago para ver cuáles están pagados."), _volver()
        etiqueta = pd.desglose_de_pago(config, datos, programada).etiqueta
        texto = (
            "¿Deshago este pago?\n\n"
            f"↩️ {etiqueta} · {pd.fecha_corta(programada, con_dia=True)} · {pd.dinero_texto(r.monto)}, "
            f"pagado el {pd.fecha_corta(r.fecha_pago)}\n\n"
            "Vuelve a quedar pendiente (o atrasado, si su fecha ya pasó)."
        )
        filas = [[("↩️ Sí, deshacerlo", _boton_deshacerok(r)), ("✖️ No", f"{PREFIJO}no")]]
        return texto, _teclado(filas)

    return _a_salvo(session, hacer, botones_si_falla=_volver(mi_pago=False))


def _deshacer_ok(session, crudo: str, *, quien: str, hoy: date) -> tuple[str, str, str]:
    partes = crudo.split(":")
    programada = _de_iso(partes[0]) if partes else None
    fecha_pago = _de_iso(partes[1]) if len(partes) > 1 else None
    if programada is None or fecha_pago is None or len(partes) < 3:
        return "No conozco ese botón", "", ""
    from pos_uniformes.services.telegram_bot_service import leer_cifra

    monto = leer_cifra(partes[2])
    config = _cuenta(session)
    datos = pd.cargar_datos(session, config)
    r = datos.registros.get(programada)
    if r is None:
        return ("Ya no estaba",
                f"El pago del {pd.fecha_corta(programada)} ya no estaba registrado; nada que deshacer.",
                _volver())
    if r.fecha_pago != fecha_pago or monto is None or r.monto != monto:
        # Se deshizo y se volvió a registrar distinto desde que se enseñó.
        texto, botones = preparar_deshacer(session, f"{programada:%d/%m/%Y}", hoy=hoy)
        return ("Cambió",
                "Ese pago cambió desde que lo viste. No deshice nada.\n\n" + texto, botones)
    try:
        ok = pd.deshacer_pago(session, programada, quien)
    except (ValueError, PermissionError) as exc:
        session.rollback()
        return "No se pudo", f"No se pudo: {exc}", _volver()
    if not ok:
        return "Ya no estaba", "Ya no estaba registrado; nada que deshacer.", _volver()
    etiqueta = pd.desglose_de_pago(config, datos, programada).etiqueta
    estado = "atrasado" if programada < hoy else ("toca hoy" if programada == hoy else "pendiente")
    return ("Deshecho",
            f"↩️ Deshecho: el {etiqueta} ({pd.fecha_corta(programada, con_dia=True)}) vuelve a estar {estado}.",
            _volver())


# ─── /diasdemas ──────────────────────────────────────────────────────────


def _pago_que_cubre(config, f: date) -> date:
    return pd.siguiente_pago(config, f)


def _texto_dias(session, config, hoy: date) -> tuple[list[str], list]:
    datos = pd.cargar_datos(session, config)
    extras = pd.dias_extra(config, datos, hoy)
    if not extras:
        lineas = [
            f"No tienes días de más desde el inicio de tu cuenta ({pd.fecha_corta(config.fecha_inicio)}).",
            "Un día de más es trabajar en tu descanso sin moverlo: /vino yo ese día.",
        ]
        if not pd.tiene_descanso(datos.horario):
            lineas.append("⚠️ Tu descanso fijo no está guardado en el calendario: sin él no se cuentan.")
        return lineas, []
    lineas = ["📆 Tus días de más:", ""]
    filas = []
    for e in extras:
        pago = _pago_que_cubre(config, e.fecha)
        if e.sin_decidir:
            destino = "❔ sin decidir (por ahora se guarda)"
        elif e.destino == pd.PAGAR:
            destino = f"💵 se paga el {pd.fecha_corta(pago)}"
            if pago in datos.registros:
                destino += " (ese pago ya se registró)"
        else:
            destino = "📦 guardado a favor"
        lineas.append(f"· {pd.fecha_corta(e.fecha, con_dia=True)} — {destino}")
    for e in extras[-6:]:
        filas.append(_botones_dia(
            e.fecha,
            pagar=e.sin_decidir or e.destino != pd.PAGAR,
            guardar=e.sin_decidir or e.destino != pd.ACUMULAR,
        ))
    lineas.append("")
    lineas.append(f"Días a favor hoy: {pd.dias_a_favor(config, datos, hoy)}")
    lineas.append(f"Págamelo suma {pd.dinero_texto(config.valor_dia)} a su pago; "
                  "Guárdamelo lo deja a favor para cubrir una falta.")
    return lineas, filas


def dias_texto_y_botones(session, argumento: str = "", *, hoy: date | None = None) -> tuple[str, str]:
    """/diasdemas: la lista con su destino y botones para cambiarlo."""
    hoy = hoy or date.today()

    def hacer():
        config = _cuenta(session)
        lineas, filas = _texto_dias(session, config, hoy)
        aviso = f"(/diasdemas no lleva nada después; «{argumento.strip()}» no se usó)\n\n" if (argumento or "").strip() else ""
        return aviso + "\n".join(lineas), _volver(filas)

    return _a_salvo(session, hacer, botones_si_falla=_volver(mi_pago=False))


def _decidir(session, crudo: str, *, hoy: date) -> tuple[str, str, str]:
    fecha_txt, _, letra = crudo.partition(":")
    f = _de_iso(fecha_txt)
    destino = {"p": pd.PAGAR, "a": pd.ACUMULAR}.get(letra)
    if f is None or destino is None:
        return "No conozco ese botón", "", ""
    config = _cuenta(session)
    try:
        pd.decidir_dia_extra(session, f, destino)
    except ValueError:
        session.rollback()
        lineas, filas = _texto_dias(session, config, hoy)
        return ("Ya no es día de más",
                f"El {pd.fecha_corta(f, con_dia=True)} ya no es un día de más (se quitó la marca o se movió "
                "tu descanso). No cambié nada.\n\n" + "\n".join(lineas),
                _volver(filas))
    pago = _pago_que_cubre(config, f)
    datos = pd.cargar_datos(session, config)
    if destino == pd.PAGAR:
        hecho = (f"💵 Te lo pagamos: el {pd.fecha_corta(f)} suma {pd.dinero_texto(config.valor_dia)} "
                 f"a tu pago del {pd.fecha_corta(pago)}.")
        aviso = "Te lo pagamos"
    else:
        hecho = (f"📦 Te lo guardamos: el {pd.fecha_corta(f)} queda como día a favor "
                 f"(tienes {pd.dias_a_favor(config, datos, max(hoy, f))}).")
        aviso = "Te lo guardamos"
    reg = datos.registros.get(pago)
    if reg is not None:
        hecho += (f"\nOjo: el pago del {pd.fecha_corta(pago)} ya se registró con {pd.dinero_texto(reg.monto)}; "
                  f"esto no lo cambia. Si hay que corregirlo: /deshacermipago {pago:%d/%m} y regístralo otra vez.")
    lineas, filas = _texto_dias(session, config, hoy)
    return aviso, hecho + "\n\n" + "\n".join(lineas), _volver(filas)


# ─── /vino yo · /falta yo · /descanso yo ─────────────────────────────────


def _plano(texto: str) -> str:
    import unicodedata

    sin = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    return "".join(ch for ch in sin if ch.isalnum()).lower()


def empleadas_que_empiezan(session, argumento: str) -> list[str]:
    """Los nombres de las empleadas activas que «/vino <argumento>» podría
    marcar (mismo criterio que `asistencia_service.buscar_code`: gafete o
    principio del nombre). Sin el dueño, el encargado ni el automático."""
    from sqlalchemy import select

    from pos_uniformes.database.models import Empleada
    from pos_uniformes.services.nomina_service import QUIEN_PUEDE_PAGAR

    pista = _plano(argumento)
    if not pista:
        return []
    return [
        e.nombre_completo
        for e in session.scalars(select(Empleada).where(Empleada.activo.is_(True))).all()
        if e.codigo.upper() not in QUIEN_PUEDE_PAGAR
        and (_plano(e.codigo) == pista or _plano(e.nombre_completo).startswith(pista))
    ]


def es_el_dueno(argumento: str, *, session=None) -> bool:
    """¿«/vino yo», «/falta_yo», «/vino Daniel» hablan de Daniel?

    «yo», «mi» y «daniel» solo si ninguna empleada activa empieza así: con
    una Yolanda, una Miriam o una (o dos) Danielas, las empleadas siguen
    exactamente igual. Sin `session` es la primera criba, sin base."""
    t = (argumento or "").strip().lower()
    if t not in _YO and t not in _DANIEL:
        return False
    if session is None or t not in (_YO_AMBIGUO | _DANIEL):
        return True
    return not empleadas_que_empiezan(session, t)


def duda_del_dueno(argumento: str, accion: str, *, session) -> str:
    """«/vino yo» con una Yolanda en el equipo: el texto que pregunta a quién
    se refiere ('' si no hay duda). Antes marcaba a Daniel sin decir nada."""
    t = (argumento or "").strip().lower()
    if t not in _YO_AMBIGUO:
        return ""
    nombres = empleadas_que_empiezan(session, t)
    if not nombres:
        return ""
    ellas = " o ".join(nombres[:3])
    primera = nombres[0].split()[0]
    return (f"¿Tú o {ellas}? «{argumento.strip()}» también es el principio de su nombre; "
            "no marqué a nadie.\n\n"
            f"Para ti: /{accion} dueño · Para ella: /{accion} {primera}")


def _tipo(accion: str) -> str:
    from pos_uniformes.services.calendario_empleadas_service import DESCANSO, FALTA, TRABAJO

    return {"vino": TRABAJO, "falta": FALTA, "descanso": DESCANSO}[accion]


def marcar_dueno(session, accion: str, *, hoy: date | None = None, quien: str = pd.EMPLOYEE_CODE) -> tuple[str, str]:
    """Marca el día de Daniel como a las empleadas (`marcar_dia`, mismas
    reglas: un descanso en otro día mueve el fijo de esa semana, y el mismo
    comando dos veces quita la marca). Luego su cuenta: borra decisiones
    huérfanas y, si quedó día de más, pregunta Págamelo / Guárdamelo."""
    from pos_uniformes.services.asistencia_service import NOTA_TELEGRAM
    from pos_uniformes.services.calendario_empleadas_service import (
        DESCANSO,
        FALTA,
        TRABAJO,
        cargar_horario,
        marcar_dia,
        quitar_marca,
    )

    hoy = hoy or date.today()
    code = pd.EMPLOYEE_CODE
    tipo = _tipo(accion)
    dia = pd.fecha_corta(hoy, con_dia=True)
    antes = _dias_de_mas_de_la_semana(session, hoy)
    if cargar_horario(session, code).eventos.get(hoy) == tipo:
        quitar_marca(session, code, hoy, actor=quien, origen="telegram")
        lineas = [f"Tú: marca quitada ↩ ({dia})"]
    else:
        marcar_dia(session, code, hoy, tipo, nota=NOTA_TELEGRAM, actor=quien, origen="telegram")
        lineas = [{TRABAJO: f"Tú: viniste ✅ ({dia})", FALTA: f"Tú: falta ✗ ({dia})",
                   DESCANSO: f"Tú: descansas 🛌 ({dia})"}[tipo]]
        if tipo == DESCANSO:
            # `marcar_dia` deja el fijo de esa semana en TRABAJO con esta nota.
            from pos_uniformes.database.models import EmpleadaEvento

            movidos = session.query(EmpleadaEvento).filter(
                EmpleadaEvento.employee_code == code,
                EmpleadaEvento.tipo == TRABAJO,
                EmpleadaEvento.nota == f"descanso movido al {hoy:%d/%m}",
                EmpleadaEvento.fecha >= hoy - timedelta(days=6),
                EmpleadaEvento.fecha <= hoy + timedelta(days=6),
            ).all()
            for ev in sorted(movidos, key=lambda e: e.fecha):
                lineas.append(f"Tu descanso del {pd.fecha_corta(ev.fecha, con_dia=True)} pasa a trabajo "
                              "(se movió; no es día de más).")
    botones = ""
    try:
        extra, botones = _cuenta_tras_marcar(session, tipo, hoy, antes=antes)
        lineas.extend(extra)
    except Exception:  # noqa: BLE001 — la marca ya quedó; la cuenta es aparte
        logger.warning("Mi pago: no se pudo revisar la cuenta tras marcar", exc_info=True)
        try:
            session.rollback()
        except Exception:  # noqa: BLE001
            pass
    return "\n".join(lineas), botones


def _dias_de_mas_de_la_semana(session, hoy: date) -> set[date]:
    """Los días de más de la semana de `hoy` (vacío sin cuenta o sin tablas).
    En un savepoint: en PostgreSQL una tabla que falta aborta la transacción y
    la marca de después ya no se podría guardar."""
    lunes = hoy - timedelta(days=hoy.weekday())
    try:
        with session.begin_nested():
            return {f for f in (e.fecha for e in pd.lista_dias_extra(session, lunes + timedelta(days=6)))
                    if f >= lunes}
    except Exception:  # noqa: BLE001
        return set()


def _cuenta_tras_marcar(session, tipo: str, hoy: date, *, antes: set[date] = frozenset()) -> tuple[list[str], str]:
    from pos_uniformes.services.calendario_empleadas_service import FALTA, TRABAJO

    try:
        config = _cuenta(session)
    except SinCuenta:
        return [], ""   # sin cuenta, la marca es solo del calendario
    pd.limpiar_decisiones_huerfanas(session)
    perdidos = sorted(set(antes) - _dias_de_mas_de_la_semana(session, hoy) - {hoy})
    aviso = [f"El {pd.fecha_corta(f, con_dia=True)} ya no es día de más: esa semana ya quedó pareja con tu descanso."
             for f in perdidos]
    if aviso:
        aviso.insert(0, "")
    if tipo == TRABAJO and pd.es_dia_extra(session, hoy):
        pago = _pago_que_cubre(config, hoy)
        actual = pd.decision_dia_extra(session, hoy)
        lineas = [
            "",
            "Hoy es tu descanso: es un día de más. ¿Te lo pagamos o te lo guardamos?",
            f"💵 Págamelo: suma {pd.dinero_texto(config.valor_dia)} a tu pago del {pd.fecha_corta(pago)}.",
            "📦 Guárdamelo: queda como día a favor para cubrir una falta.",
        ]
        if actual is not None:
            lineas.append("Ahora está en: " + ("Págamelo" if actual == pd.PAGAR else "Guárdamelo") + ".")
        else:
            lineas.append("Si no eliges, se guarda.")
        return aviso + lineas, _teclado([_botones_dia(hoy), [("‹ Mi pago", f"{PREFIJO}ver")]])
    if tipo == FALTA:
        datos = pd.cargar_datos(session, config)
        p = pd.desglose_de_pago(config, datos, _pago_que_cubre(config, hoy))
        if hoy in p.faltas_cubiertas:
            return aviso + ["", f"Se cubre con un día a favor (te quedan {pd.dias_a_favor(config, datos, hoy)})."], ""
        if hoy in p.faltas_descontadas:
            return aviso + ["", f"Se descuenta {pd.dinero_texto(config.valor_dia)} de tu pago del "
                        f"{pd.fecha_corta(p.fecha_programada)} (queda en {pd.dinero_texto(p.monto)})."], ""
    return aviso, ""


# ─── Aviso del pago (resumen del día y menú de la mañana) ────────────────


def texto_aviso(rec: pd.Recordatorio | None, *, incluir_manana: bool = False) -> str:
    """Una línea si hoy toca el pago o hay atrasados ('' si no). Con
    `incluir_manana`, también si toca mañana (para el resumen de la tarde)."""
    if rec is None:
        return ""
    partes = []
    p = rec.proximo
    if p.registro is None and rec.dias_faltan == 0:
        partes.append(f"toca hoy el {p.etiqueta} · {pd.dinero_texto(p.monto)}")
    elif incluir_manana and p.registro is None and rec.dias_faltan == 1:
        partes.append(f"mañana toca el {p.etiqueta} · {pd.dinero_texto(p.monto)}")
    if rec.atrasados:
        viejo = min(rec.atrasados, key=lambda a: a.fecha_programada)
        texto = f"❗ atrasado el {viejo.etiqueta} ({pd.fecha_corta(viejo.fecha_programada)}) · {pd.dinero_texto(viejo.monto)}"
        if len(rec.atrasados) > 1:
            texto += f" y {len(rec.atrasados) - 1} más"
        partes.append(texto)
    if not partes:
        return ""
    return "💼 Tu pago: " + " · ".join(partes) + " → /mipago"


def aviso(session, hoy: date | None = None, *, incluir_manana: bool = False) -> str:
    """`texto_aviso` leyendo la base. Nunca truena: sin cuenta, sin tablas o
    con la base rara, ''."""
    try:
        return texto_aviso(pd.recordatorio(session, hoy), incluir_manana=incluir_manana)
    except Exception:  # noqa: BLE001
        logger.warning("Mi pago: sin aviso", exc_info=True)
        return ""


# ─── Despacho ────────────────────────────────────────────────────────────


def comando(nombre: str, argumento: str, *, session_factory, hoy: date | None = None) -> tuple[str, str]:
    """(texto, botones) de /mipago, /mepagaron, /deshacermipago o /diasdemas."""
    que = COMANDOS.get(nombre)
    hacer = {
        "ver": texto_y_botones,
        "pagar": preparar_pago,
        "deshacer": preparar_deshacer,
        "dias": dias_texto_y_botones,
    }.get(que)
    if hacer is None:
        return f"No conozco /{nombre}.", ""
    with session_factory() as session:
        return hacer(session, argumento, hoy=hoy)


def atender(dato: str, *, session_factory, hoy: date | None = None, quien: str = pd.EMPLOYEE_CODE) -> tuple[str, str, str]:
    """Un botón de Mi pago: (aviso corto, texto nuevo, botones nuevos)."""
    hoy = hoy or date.today()
    accion = str(dato or "")[len(PREFIJO):]
    que, _, crudo = accion.partition(":")
    with session_factory() as session:
        def hacer():
            if que == "ver":
                return ("",) + texto_y_botones(session, hoy=hoy)
            if que == "mes":
                if len(crudo) != 6 or not crudo.isdigit():
                    return "No conozco ese botón", "", ""
                return ("",) + texto_y_botones(session, f"{int(crudo[4:])}/{crudo[:4]}", hoy=hoy)
            if que == "dias":
                return ("",) + dias_texto_y_botones(session, hoy=hoy)
            if que == "no":
                return "Sin cambios", "Ok, no cambié nada.", _volver()
            if que == "pagar":
                f = _de_iso(crudo)
                if f is None:
                    return "No conozco ese botón", "", ""
                config = _cuenta(session)
                datos = pd.cargar_datos(session, config)
                return ("",) + _validar_y_preguntar(config, datos, f, hoy, None, hoy)
            if que == "pagarok":
                return _pagar_ok(session, crudo, quien=quien, hoy=hoy)
            if que == "deshacerok":
                return _deshacer_ok(session, crudo, quien=quien, hoy=hoy)
            if que == "dia":
                return _decidir(session, crudo, hoy=hoy)
            return "No conozco ese botón", "", ""

        try:
            return hacer()
        except SinCuenta as exc:
            return "Sin cuenta", exc.texto, _volver(mi_pago=False)
        except Exception as exc:  # noqa: BLE001
            if es_sin_tablas(exc):
                try:
                    session.rollback()
                except Exception:  # noqa: BLE001
                    pass
                return "Sin cuenta", TEXTO_SIN_TABLAS, _volver(mi_pago=False)
            raise
