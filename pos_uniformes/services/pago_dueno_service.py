"""El pago del dueño (VEND-1), calendarizado (Daniel, 2026-11-19).

Su papá le da $10,000 al mes en 4 pagos de $2,500, los días 7, 14, 21 y 28
(«1 de 4» … «4 de 4»). Cada pago cubre desde el día siguiente al pago
anterior hasta su fecha (el del 7 va del 29 del mes anterior al 7).

Reglas de Daniel:

- Un día vale `valor_dia` ($385): se paga un día de más o se descuenta una falta.
- Descanso fijo: martes (o el de su `empleada_horario`), y se mueve con las
  mismas reglas que las empleadas. Día de más = trabajó en su descanso sin
  moverlo, contado por semana igual que `dias_extra_en_rango`.
- Cada día de más se «paga» (suma un día al pago de su periodo) o se
  «acumula» (un día a favor). Sin decisión cuenta como acumulado, que no
  mueve dinero, y se muestra «sin decidir».
- Las faltas, en orden desde el inicio de la cuenta, se cubren primero con un
  día a favor si en ese momento hay; si no, se descuentan del pago de su
  periodo. Las vacaciones (receso del dueño) no son faltas.
- Monto = base + días de más pagados − faltas no cubiertas, nunca menos de 0.
- Es SOLO la cuenta: no usa `empleada_pago`, no sale del cajón y no toca el
  esperado del corte. El corte solo lo recuerda.
- Antes de `fecha_inicio` no hay pagos programados y las marcas no cuentan.

El núcleo es puro (sin base). Abajo, una capa delgada lee y escribe.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from pos_uniformes.services.calendario_empleadas_service import (
    _NOTA_DESCANSO_MOVIDO,
    FALTA,
    TRABAJO,
    HorarioEmpleada,
    _semana_de,
    dias_extra_en_rango,
)

logger = logging.getLogger(__name__)

EMPLOYEE_CODE = "VEND-1"
DIAS_DE_PAGO_DEFAULT = (7, 14, 21, 28)
MONTO_DEFAULT = Decimal("2500.00")
VALOR_DIA_DEFAULT = Decimal("385.00")
#: Martes. Si VEND-1 no tiene descanso en su horario, es este.
DESCANSO_DEFAULT = 1

PAGAR = "pagar"
ACUMULAR = "acumular"
DESTINOS = (PAGAR, ACUMULAR)

# Estados de un pago programado.
PAGADO = "pagado"
TOCA_HOY = "toca_hoy"
PENDIENTE = "pendiente"
ATRASADO = "atrasado"

_DIAS_CORTOS = ("lun", "mar", "mié", "jue", "vie", "sáb", "dom")
_MESES_CORTOS = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")
_CENTAVO = Decimal("0.01")


# ─── Datos ───────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ConfigPagoDueno:
    fecha_inicio: date | None
    monto_por_pago: Decimal = MONTO_DEFAULT
    valor_dia: Decimal = VALOR_DIA_DEFAULT
    dias_de_pago: tuple[int, ...] = DIAS_DE_PAGO_DEFAULT
    activo: bool = True
    employee_code: str = EMPLOYEE_CODE

    @property
    def vigente(self) -> bool:
        """Se lleva la cuenta: activa, con inicio y con fechas de pago."""
        return bool(self.activo and self.fecha_inicio is not None and self.dias_de_pago)


@dataclass(frozen=True)
class RegistroPago:
    """Un pago que ya le hicieron."""

    fecha_programada: date
    fecha_pago: date
    monto: Decimal
    creado_por: str = ""


@dataclass
class DatosPagoDueno:
    """Lo que el núcleo necesita leer de la base.

    `horario`: el de VEND-1 con sus eventos (falta/descanso/trabajo/
    vacaciones) y descansos anteriores, como lo arma `cargar_horario`.
    `notas`: {fecha: nota} de sus eventos (para reconocer «descanso movido»).
    `decisiones`: {fecha: 'pagar' | 'acumular'} de los días de más.
    `registros`: {fecha_programada: RegistroPago}.
    """

    horario: HorarioEmpleada
    notas: dict[date, str] = field(default_factory=dict)
    decisiones: dict[date, str] = field(default_factory=dict)
    registros: dict[date, RegistroPago] = field(default_factory=dict)


@dataclass(frozen=True)
class DiaExtra:
    fecha: date
    destino: str          # 'pagar' | 'acumular' (sin decisión = acumular)
    decidido: bool

    @property
    def sin_decidir(self) -> bool:
        return not self.decidido


@dataclass
class DesglosePago:
    """Un pago programado con su periodo y cómo sale el monto."""

    fecha_programada: date
    numero: int           # 3 en «3 de 4»
    de: int               # 4 en «3 de 4»
    desde: date           # primer día que cuenta (el inicio si cae a medio periodo)
    hasta: date           # = fecha_programada
    base: Decimal
    valor_dia: Decimal
    dias_extra_pagados: list[date] = field(default_factory=list)
    dias_extra_acumulados: list[date] = field(default_factory=list)
    dias_extra_sin_decidir: list[date] = field(default_factory=list)   # dentro de los acumulados
    faltas_cubiertas: list[date] = field(default_factory=list)
    faltas_descontadas: list[date] = field(default_factory=list)
    registro: RegistroPago | None = None

    @property
    def monto_extra(self) -> Decimal:
        return _dinero(self.valor_dia * len(self.dias_extra_pagados))

    @property
    def descuento_faltas(self) -> Decimal:
        return _dinero(self.valor_dia * len(self.faltas_descontadas))

    @property
    def monto(self) -> Decimal:
        """Base + días de más pagados − faltas no cubiertas; nunca menos de 0."""
        return max(Decimal("0.00"), _dinero(self.base + self.monto_extra - self.descuento_faltas))

    @property
    def pagado(self) -> bool:
        return self.registro is not None

    @property
    def etiqueta(self) -> str:
        return f"{self.numero} de {self.de}"

    def estado(self, hoy: date) -> str:
        if self.registro is not None:
            return PAGADO
        if self.fecha_programada == hoy:
            return TOCA_HOY
        if self.fecha_programada < hoy:
            return ATRASADO
        return PENDIENTE

    def a_dict(self) -> dict:
        """Para guardarlo en `pago_dueno_registro.desglose` (JSON)."""
        iso = lambda fechas: [f.isoformat() for f in fechas]  # noqa: E731
        return {
            "numero": self.numero,
            "de": self.de,
            "desde": self.desde.isoformat(),
            "hasta": self.hasta.isoformat(),
            "base": str(self.base),
            "valor_dia": str(self.valor_dia),
            "dias_extra_pagados": iso(self.dias_extra_pagados),
            "dias_extra_acumulados": iso(self.dias_extra_acumulados),
            "dias_extra_sin_decidir": iso(self.dias_extra_sin_decidir),
            "faltas_cubiertas": iso(self.faltas_cubiertas),
            "faltas_descontadas": iso(self.faltas_descontadas),
            "monto": str(self.monto),
        }


@dataclass
class Recordatorio:
    """Lo que el corte le recuerda al dueño. No descuenta nada."""

    hoy: date
    proximo: DesglosePago
    dias_faltan: int                      # 0 = toca hoy
    atrasados: list[DesglosePago]
    ultimo_pago: date | None              # la última fecha en que de verdad le pagaron
    dias_a_favor: int


# ─── Núcleo puro ─────────────────────────────────────────────────────────


def _dinero(valor) -> Decimal:
    return Decimal(valor).quantize(_CENTAVO, rounding=ROUND_HALF_UP)


def dias_de_pago_validos(dias) -> tuple[int, ...]:
    """Ordena y valida las fechas del mes: del 1 al 28 (así existen en todos
    los meses, febrero incluido), sin repetir y al menos una."""
    try:
        limpios = sorted({int(d) for d in dias})
    except (TypeError, ValueError) as exc:
        raise ValueError("Las fechas de pago deben ser números de día.") from exc
    if not limpios:
        raise ValueError("Pon al menos una fecha de pago.")
    if limpios[0] < 1 or limpios[-1] > 28:
        raise ValueError("Las fechas de pago van del 1 al 28 (para que existan en todos los meses).")
    return tuple(limpios)


def es_fecha_de_pago(config: ConfigPagoDueno, fecha: date) -> bool:
    return fecha.day in config.dias_de_pago


def numero_de_pago(config: ConfigPagoDueno, fecha: date) -> tuple[int, int]:
    """(N, total) de «N de total» para una fecha de pago."""
    dias = tuple(config.dias_de_pago)
    if fecha.day not in dias:
        raise ValueError(f"El {fecha:%d/%m/%Y} no es fecha de pago.")
    return dias.index(fecha.day) + 1, len(dias)


def _mes_anterior(year: int, month: int) -> tuple[int, int]:
    return (year - 1, 12) if month == 1 else (year, month - 1)


def _mes_siguiente(year: int, month: int) -> tuple[int, int]:
    return (year + 1, 1) if month == 12 else (year, month + 1)


def pago_anterior(config: ConfigPagoDueno, fecha: date) -> date:
    """La fecha de pago anterior a `fecha` (aunque caiga antes del inicio)."""
    dias = tuple(config.dias_de_pago)
    previos = [d for d in dias if d < fecha.day]
    if previos:
        return fecha.replace(day=previos[-1])
    y, m = _mes_anterior(fecha.year, fecha.month)
    return date(y, m, dias[-1])


def siguiente_pago(config: ConfigPagoDueno, fecha: date) -> date:
    """La primera fecha de pago en `fecha` o después."""
    dias = tuple(config.dias_de_pago)
    for d in dias:
        if d >= fecha.day:
            return fecha.replace(day=d)
    y, m = _mes_siguiente(fecha.year, fecha.month)
    return date(y, m, dias[0])


def periodo_de(config: ConfigPagoDueno, fecha_programada: date) -> tuple[date, date]:
    """(desde, hasta) que cubre un pago: del día siguiente al pago anterior a
    su fecha. Si el inicio de la cuenta cae dentro, desde el inicio."""
    numero_de_pago(config, fecha_programada)  # valida
    desde = pago_anterior(config, fecha_programada) + timedelta(days=1)
    inicio = config.fecha_inicio
    if inicio is not None and desde < inicio <= fecha_programada:
        desde = inicio
    return desde, fecha_programada


def calendario_pagos(config: ConfigPagoDueno, hasta: date, desde: date | None = None) -> list[date]:
    """Fechas de pago programadas desde el inicio de la cuenta (o `desde`,
    si es posterior) hasta `hasta`, inclusive."""
    if not config.dias_de_pago or config.fecha_inicio is None:
        return []
    inicio = max(config.fecha_inicio, desde) if desde else config.fecha_inicio
    fechas: list[date] = []
    f = siguiente_pago(config, inicio)
    while f <= hasta:
        fechas.append(f)
        f = siguiente_pago(config, f + timedelta(days=1))
    return fechas


def _con_descanso(horario: HorarioEmpleada) -> HorarioEmpleada:
    """Sin descanso configurado, el del dueño es el martes."""
    if horario.descanso_weekday is None and not horario.descansos_anteriores:
        return HorarioEmpleada(
            employee_code=horario.employee_code,
            descanso_weekday=DESCANSO_DEFAULT,
            ciclo_dias_pago=horario.ciclo_dias_pago,
            fecha_ultimo_pago=horario.fecha_ultimo_pago,
            eventos=horario.eventos,
            modo_pago=horario.modo_pago,
            dias_trabajo=horario.dias_trabajo,
            pagos=horario.pagos,
            descansos_anteriores=horario.descansos_anteriores,
        )
    return horario


def _dias_extra_de_la_semana(
    horario: HorarioEmpleada, notas: dict[date, str], lunes: date, inicio: date
) -> list[date]:
    """Las fechas de los días de más de una semana (lunes a domingo).

    Cuántos: `dias_extra_en_rango` (trabajos en el descanso fijo menos
    descansos tomados en otro día). Cuáles: primero los trabajos en el fijo
    que NO son «descanso movido» (esos los compensa el descanso que se movió)."""
    desde = max(lunes, inicio)
    domingo = lunes + timedelta(days=6)
    if desde > domingo:
        return []
    cuantos = dias_extra_en_rango(horario, desde, domingo)
    if cuantos <= 0:
        return []
    candidatos = sorted(
        f for f, t in horario.eventos.items()
        if desde <= f <= domingo and t == TRABAJO and horario.descanso_fijo_en(f) == f.weekday()
    )
    movido = lambda f: (notas.get(f) or "").startswith(_NOTA_DESCANSO_MOVIDO)  # noqa: E731
    orden = [f for f in candidatos if not movido(f)] + [f for f in candidatos if movido(f)]
    return orden[:cuantos]


@dataclass
class _Libro:
    """Todo lo que pasó desde el inicio, en orden."""

    extras: list[DiaExtra]
    faltas_cubiertas: set[date]
    faltas_descontadas: set[date]
    # [(fecha, +1/-1)] para el saldo de días a favor
    movimientos: list[tuple[date, int]]


def _libro(config: ConfigPagoDueno, datos: DatosPagoDueno, hasta: date) -> _Libro:
    """Recorre semana por semana desde el inicio hasta el domingo de `hasta`
    (semanas completas: un descanso movido al domingo compensa el martes)."""
    inicio = config.fecha_inicio
    if inicio is None:
        return _Libro([], set(), set(), [])
    horario = _con_descanso(datos.horario)
    _, fin = _semana_de(max(hasta, inicio))
    extras: list[DiaExtra] = []
    lunes = _semana_de(inicio)[0]
    while lunes <= fin:
        for f in _dias_extra_de_la_semana(horario, datos.notas, lunes, inicio):
            destino = datos.decisiones.get(f)
            decidido = destino in DESTINOS
            extras.append(DiaExtra(f, destino if decidido else ACUMULAR, decidido))
        lunes += timedelta(days=7)
    faltas = sorted(f for f, t in horario.eventos.items() if t == FALTA and inicio <= f <= fin)

    # Orden cronológico: los días a favor ganados antes de una falta la cubren.
    sucesos = [(e.fecha, "extra") for e in extras if e.destino == ACUMULAR]
    sucesos += [(f, "falta") for f in faltas]
    sucesos.sort()
    saldo = 0
    cubiertas: set[date] = set()
    descontadas: set[date] = set()
    movimientos: list[tuple[date, int]] = []
    for f, tipo in sucesos:
        if tipo == "extra":
            saldo += 1
            movimientos.append((f, +1))
        elif saldo > 0:
            saldo -= 1
            cubiertas.add(f)
            movimientos.append((f, -1))
        else:
            descontadas.add(f)
    return _Libro(extras, cubiertas, descontadas, movimientos)


def _desglose(config: ConfigPagoDueno, datos: DatosPagoDueno, libro: _Libro, fecha: date) -> DesglosePago:
    numero, de = numero_de_pago(config, fecha)
    desde, hasta = periodo_de(config, fecha)
    en = lambda f: desde <= f <= hasta  # noqa: E731
    pagados = [e.fecha for e in libro.extras if e.destino == PAGAR and en(e.fecha)]
    acumulados = [e.fecha for e in libro.extras if e.destino == ACUMULAR and en(e.fecha)]
    sin_decidir = [e.fecha for e in libro.extras if e.sin_decidir and en(e.fecha)]
    return DesglosePago(
        fecha_programada=fecha, numero=numero, de=de, desde=desde, hasta=hasta,
        base=_dinero(config.monto_por_pago), valor_dia=_dinero(config.valor_dia),
        dias_extra_pagados=pagados, dias_extra_acumulados=acumulados,
        dias_extra_sin_decidir=sin_decidir,
        faltas_cubiertas=sorted(f for f in libro.faltas_cubiertas if en(f)),
        faltas_descontadas=sorted(f for f in libro.faltas_descontadas if en(f)),
        registro=datos.registros.get(fecha),
    )


def desglose_de_pago(config: ConfigPagoDueno, datos: DatosPagoDueno, fecha_programada: date) -> DesglosePago:
    """El desglose de un pago programado (también uno anterior al inicio:
    ahí no cuenta ninguna marca y sale la base)."""
    libro = _libro(config, datos, fecha_programada)
    return _desglose(config, datos, libro, fecha_programada)


def pagos_programados(config: ConfigPagoDueno, datos: DatosPagoDueno, hasta: date,
                      desde: date | None = None) -> list[DesglosePago]:
    """Los pagos programados desde el inicio (o `desde`) hasta `hasta`, con su desglose."""
    fechas = calendario_pagos(config, hasta, desde)
    if not fechas:
        return []
    libro = _libro(config, datos, fechas[-1])
    return [_desglose(config, datos, libro, f) for f in fechas]


def pagos_del_mes(config: ConfigPagoDueno, datos: DatosPagoDueno, year: int, month: int) -> list[DesglosePago]:
    """Los pagos de un mes (los que caen desde el inicio de la cuenta)."""
    primero = date(year, month, 1)
    y, m = _mes_siguiente(year, month)
    ultimo = date(y, m, 1) - timedelta(days=1)
    return pagos_programados(config, datos, ultimo, desde=primero)


def dias_extra(config: ConfigPagoDueno, datos: DatosPagoDueno, hasta: date) -> list[DiaExtra]:
    """Los días de más desde el inicio hasta `hasta`, con su destino."""
    return [e for e in _libro(config, datos, hasta).extras if e.fecha <= hasta]


def dias_a_favor(config: ConfigPagoDueno, datos: DatosPagoDueno, fecha: date) -> int:
    """Saldo de días a favor al cierre de `fecha`."""
    libro = _libro(config, datos, fecha)
    return sum(delta for f, delta in libro.movimientos if f <= fecha)


def ultimo_pago(datos: DatosPagoDueno) -> date | None:
    """La última fecha en que de verdad le pagaron."""
    if not datos.registros:
        return None
    return max(r.fecha_pago for r in datos.registros.values())


def calcular_recordatorio(config: ConfigPagoDueno, datos: DatosPagoDueno, hoy: date) -> Recordatorio | None:
    """Próximo pago (hoy o después, sin registrar), los atrasados, el último
    pago y el saldo de días a favor. None si la cuenta no está vigente."""
    if not config.vigente:
        return None
    # El próximo: el primero sin registrar en hoy o después (y desde el inicio).
    f = siguiente_pago(config, max(hoy, config.fecha_inicio))
    for _ in range(len(config.dias_de_pago) * 24 + 1):
        if f not in datos.registros:
            break
        f = siguiente_pago(config, f + timedelta(days=1))
    pagos = pagos_programados(config, datos, f)
    por_fecha = {p.fecha_programada: p for p in pagos}
    proximo = por_fecha.get(f) or desglose_de_pago(config, datos, f)
    atrasados = [p for p in pagos if p.fecha_programada < hoy and p.registro is None]
    return Recordatorio(
        hoy=hoy,
        proximo=proximo,
        dias_faltan=max(0, (f - hoy).days),
        atrasados=atrasados,
        ultimo_pago=ultimo_pago(datos),
        dias_a_favor=dias_a_favor(config, datos, hoy),
    )


# ─── Texto ───────────────────────────────────────────────────────────────


def fecha_corta(f: date, *, con_dia: bool = False) -> str:
    """'21-nov' o 'vie 21-nov'."""
    texto = f"{f.day:02d}-{_MESES_CORTOS[f.month - 1]}"
    return f"{_DIAS_CORTOS[f.weekday()]} {texto}" if con_dia else texto


def dinero_texto(monto: Decimal) -> str:
    """'$2,500' o '$2,115.50'."""
    monto = _dinero(monto)
    if monto == monto.to_integral_value():
        return f"${int(monto):,}"
    return f"${monto:,.2f}"


def cuando_toca(dias: int) -> str:
    if dias <= 0:
        return "Toca hoy"
    if dias == 1:
        return "Toca mañana"
    return f"Toca en {dias} días"


def lineas_recordatorio(rec: Recordatorio, nombre: str = "Daniel") -> list[str]:
    """Las líneas para el corte y su ticket. Siempre dicen «N de 4» y el
    último pago. Es un recordatorio: no sale del cajón."""
    p = rec.proximo
    ultimo = fecha_corta(rec.ultimo_pago) if rec.ultimo_pago else "ninguno"
    lineas = [
        f"PAGO DE {nombre.upper()} (no sale del cajón)",
        f"  {p.etiqueta} · {fecha_corta(p.fecha_programada, con_dia=True)} · {dinero_texto(p.monto)}",
        f"  {cuando_toca(rec.dias_faltan)} · Último pago: {ultimo}",
    ]
    for a in rec.atrasados:
        lineas.append(f"  Atrasado: {a.etiqueta} ({fecha_corta(a.fecha_programada)}) · {dinero_texto(a.monto)}")
    lineas.append(f"  Días a favor: {rec.dias_a_favor}")
    return lineas


# ─── Acceso a datos (capa delgada) ───────────────────────────────────────


def _config_de_fila(fila) -> ConfigPagoDueno:
    try:
        dias = dias_de_pago_validos(fila.dias_de_pago or DIAS_DE_PAGO_DEFAULT)
    except ValueError:
        dias = DIAS_DE_PAGO_DEFAULT
    return ConfigPagoDueno(
        fecha_inicio=fila.fecha_inicio,
        monto_por_pago=_dinero(fila.monto_por_pago if fila.monto_por_pago is not None else MONTO_DEFAULT),
        valor_dia=_dinero(fila.valor_dia if fila.valor_dia is not None else VALOR_DIA_DEFAULT),
        dias_de_pago=dias,
        activo=bool(fila.activo),
        employee_code=(fila.employee_code or EMPLOYEE_CODE).strip().upper(),
    )


def _fila_config(session):
    from pos_uniformes.database.models import PagoDuenoConfig

    return session.query(PagoDuenoConfig).order_by(PagoDuenoConfig.id).first()


def cargar_config(session) -> ConfigPagoDueno | None:
    """La configuración guardada (activa o no). None si nunca se configuró."""
    fila = _fila_config(session)
    return _config_de_fila(fila) if fila is not None else None


def guardar_config(
    session,
    *,
    fecha_inicio: date,
    monto_por_pago: Decimal | int | str = MONTO_DEFAULT,
    valor_dia: Decimal | int | str = VALOR_DIA_DEFAULT,
    dias_de_pago=DIAS_DE_PAGO_DEFAULT,
    activo: bool = True,
    employee_code: str = EMPLOYEE_CODE,
) -> ConfigPagoDueno:
    """Crea o actualiza la fila única de configuración y hace commit."""
    from pos_uniformes.database.models import PagoDuenoConfig

    if fecha_inicio is None:
        raise ValueError("Falta la fecha de inicio de la cuenta.")
    monto = _dinero(monto_por_pago)
    dia = _dinero(valor_dia)
    if monto < 0 or dia < 0:
        raise ValueError("El monto y el valor del día no pueden ser negativos.")
    dias = dias_de_pago_validos(dias_de_pago)
    fila = _fila_config(session)
    if fila is None:
        fila = PagoDuenoConfig()
        session.add(fila)
    fila.employee_code = str(employee_code or EMPLOYEE_CODE).strip().upper()
    fila.monto_por_pago = monto
    fila.valor_dia = dia
    fila.dias_de_pago = list(dias)
    fila.fecha_inicio = fecha_inicio
    fila.activo = bool(activo)
    session.commit()
    return _config_de_fila(fila)


def cargar_datos(session, config: ConfigPagoDueno) -> DatosPagoDueno:
    """Horario y marcas del dueño, decisiones de días de más y pagos hechos."""
    from pos_uniformes.database.models import EmpleadaEvento, PagoDuenoDiaExtra, PagoDuenoRegistro
    from pos_uniformes.services.calendario_empleadas_service import cargar_horario

    code = config.employee_code
    horario = cargar_horario(session, code)
    notas = {
        ev.fecha: ev.nota
        for ev in session.query(EmpleadaEvento)
        .filter(EmpleadaEvento.employee_code == code, EmpleadaEvento.tipo == TRABAJO)
        .all()
        if ev.nota
    }
    decisiones = {f.fecha: f.destino for f in session.query(PagoDuenoDiaExtra).all()}
    registros = {
        r.fecha_programada: RegistroPago(
            fecha_programada=r.fecha_programada, fecha_pago=r.fecha_pago,
            monto=_dinero(r.monto), creado_por=r.creado_por or "",
        )
        for r in session.query(PagoDuenoRegistro).all()
    }
    return DatosPagoDueno(horario=horario, notas=notas, decisiones=decisiones, registros=registros)


def _config_vigente(session) -> ConfigPagoDueno:
    config = cargar_config(session)
    if config is None or not config.vigente:
        raise ValueError("La cuenta del pago del dueño no está configurada.")
    return config


def recordatorio(session, hoy: date | None = None) -> Recordatorio | None:
    """El recordatorio para el corte. None si no hay configuración activa, o
    si la base todavía no tiene las tablas (un kiosko antes de la migración):
    el corte sigue exactamente igual."""
    hoy = hoy or date.today()
    try:
        with session.begin_nested():
            config = cargar_config(session)
            if config is None or not config.vigente:
                return None
            return calcular_recordatorio(config, cargar_datos(session, config), hoy)
    except Exception as exc:  # noqa: BLE001 — el corte nunca se cae por el recordatorio
        logger.warning("Sin recordatorio del pago del dueño: %s", exc)
        return None


def lineas_recordatorio_corte(session, hoy: date | None = None) -> list[str]:
    """Las líneas para el corte, o [] si no hay nada que recordar."""
    rec = recordatorio(session, hoy)
    return lineas_recordatorio(rec) if rec is not None else []


def _solo_el_dueno(config: ConfigPagoDueno, quien: str) -> None:
    if str(quien or "").strip().upper() != config.employee_code:
        raise PermissionError("Solo el dueño puede llevar la cuenta de su pago.")


def registrar_pago(
    session,
    fecha_programada: date,
    fecha_pago: date,
    monto: Decimal | int | str | None,
    creado_por: str,
    *,
    hoy: date | None = None,
) -> DesglosePago:
    """Marca como hecho el pago de `fecha_programada`, pagado el `fecha_pago`.

    Solo VEND-1. `monto` None = el calculado. Rechaza una fecha que no es de
    pago, un pago ya registrado y una fecha de pago en el futuro. Puede ser
    un pago anterior al inicio de la cuenta (el «2 de 4 del 14-nov pagado el
    19-nov» con la cuenta arrancando el 19). Hace commit."""
    from pos_uniformes.database.models import PagoDuenoRegistro

    hoy = hoy or date.today()
    config = _config_vigente(session)
    _solo_el_dueno(config, creado_por)
    if not es_fecha_de_pago(config, fecha_programada):
        raise ValueError(f"El {fecha_programada:%d/%m/%Y} no es fecha de pago.")
    if fecha_pago > hoy:
        raise ValueError("La fecha en que te pagaron no puede ser futura.")
    ya = session.query(PagoDuenoRegistro).filter(PagoDuenoRegistro.fecha_programada == fecha_programada).first()
    if ya is not None:
        raise ValueError(
            f"El pago del {fecha_corta(fecha_programada)} ya está registrado "
            f"(pagado el {fecha_corta(ya.fecha_pago)})."
        )
    datos = cargar_datos(session, config)
    desglose = desglose_de_pago(config, datos, fecha_programada)
    total = desglose.monto if monto is None else _dinero(monto)
    if total < 0:
        raise ValueError("El monto no puede ser negativo.")
    session.add(PagoDuenoRegistro(
        fecha_programada=fecha_programada, fecha_pago=fecha_pago, monto=total,
        desglose=desglose.a_dict(), creado_por=str(creado_por).strip().upper()[:40],
    ))
    session.commit()
    desglose.registro = RegistroPago(fecha_programada, fecha_pago, total, str(creado_por).strip().upper())
    return desglose


def deshacer_pago(session, fecha_programada: date, creado_por: str) -> bool:
    """Borra el registro de ese pago (vuelve a pendiente o atrasado). Solo
    VEND-1. False si no había. Hace commit."""
    from pos_uniformes.database.models import PagoDuenoRegistro

    config = _config_vigente(session)
    _solo_el_dueno(config, creado_por)
    fila = session.query(PagoDuenoRegistro).filter(PagoDuenoRegistro.fecha_programada == fecha_programada).first()
    if fila is None:
        return False
    session.delete(fila)
    session.commit()
    return True


def es_dia_extra(session, fecha: date) -> bool:
    """¿Ese día el dueño trabajó de más (en su descanso sin moverlo)?"""
    config = cargar_config(session)
    if config is None or not config.vigente:
        return False
    datos = cargar_datos(session, config)
    return any(e.fecha == fecha for e in dias_extra(config, datos, fecha))


def decidir_dia_extra(session, fecha: date, destino: str) -> None:
    """Guarda si el día de más se paga o se acumula (reemplaza la decisión
    anterior). Rechaza un día que no es de más. Hace commit."""
    from pos_uniformes.database.models import PagoDuenoDiaExtra

    if destino not in DESTINOS:
        raise ValueError(f"destino inválido: {destino!r}")
    if not es_dia_extra(session, fecha):
        raise ValueError(f"El {fecha:%d/%m/%Y} no es un día de más.")
    fila = session.get(PagoDuenoDiaExtra, fecha)
    if fila is None:
        session.add(PagoDuenoDiaExtra(fecha=fecha, destino=destino))
    else:
        fila.destino = destino
    session.commit()


def lista_dias_extra(session, hasta: date | None = None) -> list[DiaExtra]:
    """Los días de más desde el inicio de la cuenta hasta `hasta` (hoy)."""
    config = cargar_config(session)
    if config is None or not config.vigente:
        return []
    return dias_extra(config, cargar_datos(session, config), hasta or date.today())


def dias_extra_sin_decidir(session, hasta: date | None = None) -> list[date]:
    """Los días de más que nadie ha decidido (cuentan como acumulados)."""
    return [e.fecha for e in lista_dias_extra(session, hasta) if e.sin_decidir]


def pagos_del_mes_db(session, year: int, month: int) -> list[DesglosePago]:
    """Los pagos programados de ese mes con su desglose y su registro."""
    config = cargar_config(session)
    if config is None or not config.vigente:
        return []
    return pagos_del_mes(config, cargar_datos(session, config), year, month)
