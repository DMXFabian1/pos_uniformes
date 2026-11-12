"""La "Libreta": registro digital de operaciones del mostrador.

Cada venta/apartado de venta rápida se anota aquí, ligado al gafete de la
empleada en sesión. Dos vistas:
- Empleada: SUS operaciones, una por una, con piezas — sin montos.
- Dueño: todas las empleadas, con piezas y montos.

Ventanas: "hoy" (día local) y "semana" (calendario, lunes a domingo).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select, true as sa_true

from pos_uniformes.database.models import LibretaVenta
from pos_uniformes.utils.date_format import local_day_window

logger = logging.getLogger(__name__)

# Tipos de operación que se llevan piezas del piso. El abono no mueve piezas.
TIPOS_QUE_DESCUENTAN = ("venta", "apartado")


def ventana_hoy(reference: date | None = None) -> tuple[datetime, datetime]:
    return local_day_window(reference or date.today())


def ventana_semana(reference: date | None = None) -> tuple[datetime, datetime]:
    """Semana calendario: lunes 00:00 a domingo 23:59 (hora local)."""
    reference = reference or date.today()
    monday = reference - timedelta(days=reference.weekday())
    inicio, _ = local_day_window(monday)
    _, fin = local_day_window(monday + timedelta(days=6))
    return inicio, fin


def ventana_semana_anterior(reference: date | None = None) -> tuple[datetime, datetime]:
    """La semana calendario ANTERIOR completa (para verificar comisiones el
    día de pago, cuando la semana actual ya se reinició)."""
    reference = reference or date.today()
    return ventana_semana(reference - timedelta(days=7))


def ventana_ciclo(fecha_ultimo_pago: date | None) -> tuple[datetime, datetime]:
    """Del día SIGUIENTE al último pago hasta hoy: el desglose que respalda
    el banner "Comisiones desde tu último pago" (la vista para pagar).
    Sin pago registrado aún: los últimos 90 días."""
    hoy = date.today()
    inicio_dia = (
        fecha_ultimo_pago + timedelta(days=1)
        if fecha_ultimo_pago is not None
        else hoy - timedelta(days=90)
    )
    inicio, _ = local_day_window(inicio_dia)
    _, fin = local_day_window(hoy)
    return inicio, fin


def ventana_rango(desde: date, hasta: date) -> tuple[datetime, datetime]:
    """Rango libre de fechas (inclusive); si vienen volteadas, se corrigen."""
    if hasta < desde:
        desde, hasta = hasta, desde
    inicio, _ = local_day_window(desde)
    _, fin = local_day_window(hasta)
    return inicio, fin


def filtrar_operaciones(
    rows: list,
    *,
    tipo: str | None = None,
    employee_code: str | None = None,
    solo_tarjeta: bool = False,
) -> list:
    """Filtros en memoria para la vista del dueño (tipo, empleada, tarjeta)."""
    result = list(rows)
    if tipo:
        result = [r for r in result if str(r.tipo) == tipo]
    if employee_code:
        code = str(employee_code).upper()
        result = [r for r in result if str(r.employee_code).upper() == code]
    if solo_tarjeta:
        result = [r for r in result if bool(getattr(r, "pago_tarjeta", False))]
    return result


def lineas_detalle(detalle: list[dict], *, con_precios: bool) -> list[list[str]]:
    """Filas [producto, talla, cantidad(, precio, subtotal)] para el diálogo
    de detalle de una operación. Sin precios para la vista de empleada."""
    filas: list[list[str]] = []
    for line in detalle or []:
        nombre = str(line.get("nombre", "")).strip() or str(line.get("sku", ""))
        talla = str(line.get("talla", "")).strip() or "-"
        cantidad = str(int(line.get("cantidad", 0) or 0))
        if con_precios:
            precio = Decimal(str(line.get("precio", 0) or 0)).quantize(Decimal("0.01"))
            subtotal = Decimal(str(line.get("subtotal", 0) or 0)).quantize(Decimal("0.01"))
            filas.append([nombre, talla, cantidad, f"${precio:,.2f}", f"${subtotal:,.2f}"])
        else:
            filas.append([nombre, talla, cantidad])
    return filas


# Comisión de la terminal bancaria (pagos con tarjeta): única fuente del
# porcentaje para venta rápida, abonos y la Libreta.
TERMINAL_COMMISSION_PERCENT = Decimal("4.5")


def aplicar_comision_terminal(monto: Decimal) -> Decimal:
    """Monto tras descontar la comisión de terminal, con la regla de
    redondeo de la tienda (sale_rounding_service)."""
    from pos_uniformes.services.sale_rounding_service import resolve_sale_rounding

    factor = (Decimal("100") - TERMINAL_COMMISSION_PERCENT) / Decimal("100")
    con_comision = (Decimal(str(monto)) * factor).quantize(Decimal("0.01"))
    return resolve_sale_rounding(con_comision).collected_total


# Regla de comisiones de Daniel: el conjunto 3pz vale 2 comisiones por
# unidad (corregido 2026-09-06: antes contaba 3); TODO lo demás (2pz
# incluido, prendas sueltas) vale 1 por unidad.
COMISIONES_3PZ = 2
_RE_3PZ = re.compile(r"3\s*pz", re.IGNORECASE)


def comisiones_de_linea(nombre: str, cantidad: int) -> int:
    factor = COMISIONES_3PZ if _RE_3PZ.search(str(nombre or "")) else 1
    return factor * int(cantidad or 0)


def comisiones_de_items(items: list[dict]) -> int:
    return sum(
        comisiones_de_linea(it.get("nombre", ""), int(it.get("cantidad", 0) or 0))
        for it in items or []
    )


def cuenta_como_operacion(row) -> bool:
    """¿Es una operación de la empleada? Su propia compra con precio especial
    no (Daniel, 2026-11-12: «tampoco quiero que le cuente como operación»)."""
    return not bool(getattr(row, "descuento_empleada", False))


def comisiones_de_operacion(items: list[dict], comisiones=None, descuento_empleada: bool = False) -> int:
    """Las comisiones que cuenta una operación.

    Una compra con precio especial (lo que compra una empleada) no paga
    comisión a nadie (Daniel, 2026-11-12: «no quiero que le cuente como
    comisión»): ni a la que la compró ni a la que la cobró."""
    if descuento_empleada:
        return 0
    return comisiones_de_items(items) if comisiones is None else int(comisiones)


def registrar_operacion(
    session,
    *,
    employee_code: str,
    employee_name: str,
    tipo: str,
    items: list[dict],
    monto_total: Decimal,
    descuento_empleada: bool = False,
    cliente: str | None = None,
    origen: str | None = None,
    created_at: datetime | None = None,
    pago_tarjeta: bool = False,
    monto_neto: Decimal | None = None,
    comisiones: int | None = None,
    cliente_id: int | None = None,
    operacion_uuid: str | None = None,
    acreditar_cashback: bool = True,
    descuento_programa: Decimal | None = None,
    compradora_code: str | None = None,
    calculo: dict | None = None,
    recalcular_calculo: bool = True,
) -> LibretaVenta:
    """Anota una operación. `items` = líneas del carrito de venta rápida.

    created_at explícito: las operaciones encoladas offline conservan la hora
    en que se hicieron, no la del drenado.
    comisiones None → se calculan de los items (3pz=2, resto 1/unidad); los
    abonos deben pasar comisiones=0 explícito.
    monto_neto None → igual a monto_total (efectivo).

    Monedero: con `cliente_id` (cliente identificado con su QR) una venta
    gana cashback. Si acreditarlo falla, la venta NO se pierde: se anota en
    el log y `monedero_service.acreditar_faltantes` lo repone después.
    Esta vía nunca usa saldo: el canje es `registrar_venta_con_monedero`."""
    detalle = [
        {
            "sku": str(it.get("sku", "")),
            "nombre": str(it.get("nombre", "")),
            "talla": str(it.get("talla", "")),
            "cantidad": int(it.get("cantidad", 0) or 0),
            "precio": str(it.get("precio", "0")),
            "subtotal": str(
                (Decimal(str(it.get("precio", 0) or 0)) * int(it.get("cantidad", 0) or 0)).quantize(
                    Decimal("0.01")
                )
            ),
            # M2 (D1): el renglón del carrito al que pertenece (la fotografía lo usa).
            **({"linea_uid": str(it["linea_uid"])} if it.get("linea_uid") else {}),
            # E5-A: solo cuando viene marcada; el descuento de programa no le aplica.
            **({"promo_3pz": True} if it.get("promo_3pz") else {}),
            # E7: Oferta o Liquidación, con su precio normal.
            **({"rebaja": str(it["rebaja"]), "precio_normal": str(it.get("precio_normal") or "")} if it.get("rebaja") else {}),
            # E6: el % de empleada de este renglón (su nivel o el 5 % base).
            **({"desc_empleada_pct": str(it["desc_empleada_pct"])} if it.get("desc_empleada_pct") not in (None, "") else {}),
        }
        for it in items
    ]
    monto_total = Decimal(str(monto_total)).quantize(Decimal("0.01"))
    entry = LibretaVenta(
        employee_code=str(employee_code).upper(),
        employee_name=employee_name or "",
        tipo=tipo,
        cliente=cliente,
        piezas=sum(line["cantidad"] for line in detalle),
        comisiones=comisiones_de_operacion(items, comisiones, descuento_empleada),
        monto_total=monto_total,
        monto_neto=(
            monto_total if monto_neto is None else Decimal(str(monto_neto)).quantize(Decimal("0.01"))
        ),
        pago_tarjeta=pago_tarjeta,
        descuento_empleada=descuento_empleada,
        detalle=detalle,
        origen=origen,
        cliente_id=(int(cliente_id) if cliente_id is not None else None),
        operacion_uuid=(str(operacion_uuid) if operacion_uuid else None),
        monto_monedero=Decimal("0.00"),
        descuento_programa=_pct_o_nada(descuento_programa),
        compradora_code=(str(compradora_code).upper() if compradora_code and descuento_empleada else None),
    )
    if calculo:
        foto = recalcular_en_servidor(session, calculo, cliente_id=cliente_id)[0] if recalcular_calculo else calculo
        entry.calculo = foto
        entry.version_reglas = str(foto.get("version_reglas") or "")[:20] or None
    if created_at is not None:
        entry.created_at = created_at
    session.add(entry)
    session.flush()
    descontar_stock(session, entry)
    if acreditar_cashback:
        acreditar_cashback_sin_bloquear(session, entry)
        subir_de_programa_sin_bloquear(session, entry)
    return entry


def recalcular_en_servidor(session, calculo: dict, *, cliente_id: int | None = None) -> tuple[dict, dict]:
    """M2 (T3): la fotografía del kiosko con lo que recalculó el servidor.

    Nunca tumba una venta de la cola (el cliente ya pagó): si el recálculo
    falla, la fotografía queda como la mandó el kiosko, con el error anotado.
    Devuelve (fotografía, diferencias en el cobro)."""
    from pos_uniformes.services import beneficios_servidor as servidor

    try:
        with session.begin_nested():
            foto, dif = servidor.recalcular(session, calculo, cliente_id=cliente_id)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Motor: el servidor no pudo recalcular la venta")
        return {**calculo, "servidor": {"error": f"{type(exc).__name__}: {exc}"[:300]}}, {}
    if foto["servidor"]["diferencias"]:
        logger.warning("Motor: el servidor calculó distinto que el kiosko: %s", foto["servidor"]["diferencias"])
    return foto, dif


def _pct_o_nada(valor) -> Decimal | None:
    if valor in (None, ""):
        return None
    pct = Decimal(str(valor)).quantize(Decimal("0.01"))
    return pct if pct > 0 else None


def acreditar_cashback_sin_bloquear(session, entry: LibretaVenta):
    """Cashback de la venta en su propio tramo: si falla, la venta sigue."""
    if entry.cliente_id is None or str(entry.tipo) != "venta":
        return None
    from pos_uniformes.services import monedero_service

    try:
        with session.begin_nested():
            return monedero_service.acreditar_cashback(session, libreta_venta=entry)
    except Exception:  # noqa: BLE001 — el cashback se repone; la venta no se pierde
        logger.exception("Monedero: no se acreditó el cashback de la venta %s", entry.id)
        return None


def subir_de_programa_sin_bloquear(session, entry: LibretaVenta):
    """E5-A: después del cashback, Club → Leal si ya juntó el gasto del año.
    Va después a propósito: la venta que cruza el umbral abona como Club."""
    if entry.cliente_id is None or str(entry.tipo) != "venta":
        return None
    from pos_uniformes.services.fidelizacion import subida_leal_service

    return subida_leal_service.subir_sin_bloquear(session, entry)


def registrar_venta_con_monedero(
    session,
    *,
    employee_code: str,
    employee_name: str,
    items: list[dict],
    monto_total: Decimal,
    monto_monedero: Decimal,
    cliente_id: int,
    operacion_uuid: str,
    pago_tarjeta: bool = False,
    monto_neto: Decimal | None = None,
    comisiones: int | None = None,
    descuento_empleada: bool = False,
    cliente: str | None = None,
    origen: str | None = None,
    descuento_programa: Decimal | None = None,
    compradora_code: str | None = None,
    calculo: dict | None = None,
) -> tuple[LibretaVenta, object, object]:
    """Venta pagada (en parte o toda) con saldo del monedero. EN LÍNEA.

    En una sola transacción: anota la venta, descuenta stock, cobra el saldo
    (con el monedero bloqueado) y acredita el cashback de lo pagado con
    dinero. Si algo falla se lanza y NO queda nada: quien llama hace rollback
    y la venta no se imprime. No hace commit (lo hace quien llama).

    Repetirla con el mismo `operacion_uuid` devuelve lo ya registrado.

    Devuelve (venta, canje, cashback|None)."""
    from pos_uniformes.services import monedero_service

    monto_total = Decimal(str(monto_total)).quantize(Decimal("0.01"))
    monto_monedero = Decimal(str(monto_monedero)).quantize(Decimal("0.01"))
    if not operacion_uuid:
        raise monedero_service.MonederoError("Falta la identidad de la venta (operacion_uuid).")
    if monto_monedero <= 0 or monto_monedero > monto_total:
        raise monedero_service.MonederoError("El saldo a usar debe ser mayor a cero y no pasar el total.")
    previa = session.scalars(
        select(LibretaVenta).where(LibretaVenta.operacion_uuid == str(operacion_uuid))
    ).first()
    if previa is not None:
        movs = {m.tipo: m for m in monedero_service.movimientos_de_operacion(session, previa.id)}
        return previa, movs.get(monedero_service.CANJE), movs.get(monedero_service.CASHBACK)
    if calculo:
        # T3: antes de cobrar el saldo, el servidor recalcula; si el cobro
        # cambia, no se cobra con el importe viejo (la empleada lo ve).
        from pos_uniformes.services.beneficios_servidor import CalculoCambio, recalcular

        calculo, dif = recalcular(session, calculo, cliente_id=cliente_id)
        if dif:
            raise CalculoCambio(dif)
    entry = registrar_operacion(
        session,
        employee_code=employee_code,
        employee_name=employee_name,
        tipo="venta",
        items=items,
        monto_total=monto_total,
        descuento_empleada=descuento_empleada,
        cliente=cliente,
        origen=origen,
        pago_tarjeta=pago_tarjeta,
        monto_neto=(
            neto_de_cobro(monto_total, monto_monedero, pago_tarjeta) if monto_neto is None else monto_neto
        ),
        comisiones=comisiones,
        cliente_id=cliente_id,
        operacion_uuid=operacion_uuid,
        acreditar_cashback=False,
        descuento_programa=descuento_programa,
        compradora_code=compradora_code,
        calculo=calculo,
        recalcular_calculo=False,
    )
    entry.monto_monedero = monto_monedero
    session.flush()
    canje = monedero_service.canjear(
        session, libreta_venta=entry, monto=monto_monedero, employee_code=entry.employee_code
    )
    cashback = acreditar_cashback_sin_bloquear(session, entry)
    subir_de_programa_sin_bloquear(session, entry)
    return entry, canje, cashback


# ─── Cómo se pagó una operación ──────────────────────────────────────────


@dataclass(frozen=True)
class PagosOperacion:
    """Reparto del cobro: monedero + (efectivo o tarjeta). Suman monto_total."""

    monedero: Decimal
    tarjeta: Decimal
    efectivo: Decimal


def pagos_de(row) -> PagosOperacion:
    """Lo pagado con saldo NO es efectivo ni tarjeta: no está en el cajón ni
    llega por la terminal. El resto va a un solo método (V1)."""
    total = Decimal(str(getattr(row, "monto_total", 0) or 0)).quantize(Decimal("0.01"))
    monedero = Decimal(str(getattr(row, "monto_monedero", 0) or 0)).quantize(Decimal("0.01"))
    monedero = min(max(monedero, Decimal("0.00")), total) if total >= 0 else Decimal("0.00")
    resto = (total - monedero).quantize(Decimal("0.01"))
    if bool(getattr(row, "pago_tarjeta", False)):
        return PagosOperacion(monedero, resto, Decimal("0.00"))
    return PagosOperacion(monedero, Decimal("0.00"), resto)


def neto_de_cobro(monto_total, monto_monedero, pago_tarjeta: bool) -> Decimal:
    """Dinero que de verdad entra: lo cobrado fuera del monedero, menos la
    comisión de terminal si fue con tarjeta."""
    resto = (Decimal(str(monto_total)) - Decimal(str(monto_monedero or 0))).quantize(Decimal("0.01"))
    if resto <= 0:
        return Decimal("0.00")
    return aplicar_comision_terminal(resto) if pago_tarjeta else resto


def _referencia(entry: LibretaVenta) -> str | None:
    entry_id = getattr(entry, "id", None)
    return f"libreta:{entry_id}" if entry_id is not None else None


def descontar_stock(session, entry: LibretaVenta) -> int:
    """La venta (o apartado) baja el stock de cada talla que se llevó.

    Desde 2026-09-14 (Daniel: "que la venta descuente stock"). Antes solo lo
    hacía el POS viejo y el número llevaba congelado desde el 16 de julio.

    - Va amarrado al id de la Libreta (`referencia = libreta:N`): si por lo
      que sea se vuelve a llamar, no descuenta dos veces.
    - Puede dejar negativo: un negativo es la lista de qué recontar.
    - NUNCA tumba la venta: cada talla va en un savepoint; si algo falla se
      anota en el log y la venta se guarda igual.
    Devuelve cuántas tallas se descontaron.
    """
    if getattr(entry, "tipo", None) not in TIPOS_QUE_DESCUENTAN:
        return 0
    from pos_uniformes.database.models import MovimientoInventario, TipoMovimientoInventario, Variante
    from pos_uniformes.services import conjunto_service
    from pos_uniformes.services.inventario_service import InventarioService

    referencia = _referencia(entry)
    if referencia is None:
        return 0
    ya = set(session.scalars(
        select(MovimientoInventario.variante_id).where(MovimientoInventario.referencia == referencia)
    ).all())
    tipo = TipoMovimientoInventario.SALIDA_VENTA if entry.tipo == "venta" else TipoMovimientoInventario.APARTADO_RESERVA
    hechas = 0
    for linea in entry.detalle or []:
        sku = str(linea.get("sku") or "").strip()
        try:
            cantidad = int(linea.get("cantidad") or 0)
        except (TypeError, ValueError):
            continue
        if not sku or cantidad <= 0:
            continue
        try:
            with session.begin_nested():
                variante = session.scalar(select(Variante).where(Variante.sku == sku))
                if variante is None or variante.id in ya:
                    continue
                # Un conjunto (3pz, chamarra) no se mueve él: se mueven sus
                # piezas (fase 3). Si alguna ya trae esta referencia, ya se hizo.
                if any(p.id in ya for p in conjunto_service.variantes_pieza_de(session, variante)):
                    continue
                InventarioService.registrar_movimiento(
                    session, variante, tipo, -cantidad,
                    referencia=referencia,
                    observacion=f"{entry.tipo} en el kiosko ({entry.employee_code})",
                    creado_por=str(entry.employee_code or "kiosko"),
                    allow_negative_stock=True,
                )
                hechas += 1
        except Exception:  # noqa: BLE001 — la venta vale más que el número
            logger.exception("Libreta %s: no se pudo descontar %s (sku %s)", entry.id, cantidad, sku)
    return hechas


def devolver_stock(session, entry: LibretaVenta) -> int:
    """Regresa al stock lo que descontó una operación (cuando el dueño la
    borra). Devuelve cuántas tallas regresaron."""
    from pos_uniformes.database.models import MovimientoInventario, TipoMovimientoInventario, Variante
    from pos_uniformes.services.inventario_service import InventarioService

    referencia = _referencia(entry)
    if referencia is None:
        return 0
    # Todo lo que la operación movió con su referencia: la salida de cada talla
    # y, si vendió una chamarra, el pants suelto que dejó (AJUSTE_ENTRADA).
    movimientos = list(session.scalars(
        select(MovimientoInventario).where(
            MovimientoInventario.referencia == referencia,
            MovimientoInventario.tipo_movimiento.in_((
                TipoMovimientoInventario.SALIDA_VENTA, TipoMovimientoInventario.APARTADO_RESERVA,
                TipoMovimientoInventario.AJUSTE_ENTRADA, TipoMovimientoInventario.AJUSTE_SALIDA,
            )),
        )
    ).all())
    hechas = 0
    for mov in movimientos:
        try:
            with session.begin_nested():
                variante = session.get(Variante, mov.variante_id)
                if variante is None:
                    continue
                regresa = -int(mov.cantidad)
                InventarioService.registrar_movimiento(
                    session, variante,
                    TipoMovimientoInventario.CANCELACION_VENTA if regresa > 0 else TipoMovimientoInventario.AJUSTE_SALIDA,
                    regresa,
                    referencia=f"{referencia}:borrada",
                    observacion="Operación borrada de la Libreta",
                    creado_por="dueno",
                    allow_negative_stock=True,
                )
                hechas += 1
        except Exception:  # noqa: BLE001
            logger.exception("Libreta %s: no se pudo devolver el stock de la variante %s", entry.id, mov.variante_id)
    return hechas


def listar_operaciones(
    session,
    *,
    desde: datetime,
    hasta: datetime,
    employee_code: str | None = None,
) -> list[LibretaVenta]:
    stmt = (
        select(LibretaVenta)
        .where(LibretaVenta.created_at >= desde, LibretaVenta.created_at <= hasta)
        .order_by(LibretaVenta.created_at.desc())
    )
    if employee_code:
        stmt = stmt.where(LibretaVenta.employee_code == str(employee_code).upper())
    return list(session.scalars(stmt).all())


@dataclass(frozen=True)
class ResumenEmpleada:
    employee_code: str
    employee_name: str
    operaciones: int
    piezas: int
    comisiones: int
    monto_total: Decimal


def resumir_por_empleada(rows: list[LibretaVenta]) -> list[ResumenEmpleada]:
    """Agregado para la vista del dueño, ordenado por comisiones desc."""
    acc: dict[str, dict] = {}
    for row in rows:
        bucket = acc.setdefault(
            row.employee_code,
            {
                "name": row.employee_name,
                "operaciones": 0,
                "piezas": 0,
                "comisiones": 0,
                "monto": Decimal("0.00"),
            },
        )
        bucket["comisiones"] += int(getattr(row, "comisiones", 0) or 0)
        if cuenta_como_operacion(row):
            # Su propia compra con precio especial no le suma operación, piezas
            # ni importe (Daniel, 2026-11-12).
            bucket["operaciones"] += 1
            bucket["piezas"] += int(row.piezas or 0)
            bucket["monto"] = (bucket["monto"] + Decimal(str(row.monto_total or 0))).quantize(
                Decimal("0.01")
            )
        if row.employee_name:
            bucket["name"] = row.employee_name
    return sorted(
        (
            ResumenEmpleada(
                employee_code=code,
                employee_name=data["name"],
                operaciones=data["operaciones"],
                piezas=data["piezas"],
                comisiones=data["comisiones"],
                monto_total=data["monto"],
            )
            for code, data in acc.items()
        ),
        key=lambda r: (r.comisiones, r.piezas),
        reverse=True,
    )


# %a depende del locale (daría "Mon"); nombres propios en español.
_DIAS_SEMANA = ("Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom")


@dataclass(frozen=True)
class CorteDia:
    dia: date
    dia_label: str
    operaciones: int
    piezas: int
    monto_ventas: Decimal
    monto_neto_ventas: Decimal
    monto_apartados: Decimal
    monto_abonos: Decimal
    # Efectivo que debe haber en el cajón: ventas + abonos pagados en
    # efectivo. Lo de tarjeta no está en caja (llega por la terminal) y el
    # apartado no es dinero recibido (su dinero entra vía abonos).
    monto_en_caja: Decimal


def resumir_por_dia(rows: list[LibretaVenta]) -> list[CorteDia]:
    """Corte diario para la vista del dueño: cuánto se vendió cada día.

    - Ventas: lo cobrado, y el neto tras la comisión de terminal (4.5% en
      pagos con tarjeta; igual al cobrado en efectivo).
    - Apartados: comprometido, no cobrado completo.
    - Abonos: dinero cobrado de apartados.
    Días ordenados del más reciente al más viejo (hora local)."""
    acc: dict[date, dict] = {}
    for row in rows:
        created = row.created_at
        local_dt = created.astimezone() if created.tzinfo is not None else created
        dia = local_dt.date()
        bucket = acc.setdefault(
            dia,
            {
                "operaciones": 0,
                "piezas": 0,
                "ventas": Decimal("0.00"),
                "neto": Decimal("0.00"),
                "apartados": Decimal("0.00"),
                "abonos": Decimal("0.00"),
                "en_caja": Decimal("0.00"),
            },
        )
        bucket["operaciones"] += 1
        bucket["piezas"] += int(row.piezas or 0)
        monto = Decimal(str(row.monto_total or 0))
        neto = Decimal(str(getattr(row, "monto_neto", None) or monto))
        tipo = str(row.tipo)
        # Lo pagado con monedero no está en el cajón.
        efectivo = pagos_de(row).efectivo
        if Decimal(str(getattr(row, "monto_monedero", 0) or 0)) > 0:
            neto = Decimal(str(getattr(row, "monto_neto", None) or 0))
        if tipo == "apartado":
            bucket["apartados"] = (bucket["apartados"] + monto).quantize(Decimal("0.01"))
        elif tipo == "abono":
            bucket["abonos"] = (bucket["abonos"] + neto).quantize(Decimal("0.01"))
            bucket["en_caja"] = (bucket["en_caja"] + efectivo).quantize(Decimal("0.01"))
        else:
            bucket["ventas"] = (bucket["ventas"] + monto).quantize(Decimal("0.01"))
            bucket["neto"] = (bucket["neto"] + neto).quantize(Decimal("0.01"))
            bucket["en_caja"] = (bucket["en_caja"] + efectivo).quantize(Decimal("0.01"))
    return [
        CorteDia(
            dia=dia,
            dia_label=f"{_DIAS_SEMANA[dia.weekday()]} {dia.strftime('%d/%m')}",
            operaciones=data["operaciones"],
            piezas=data["piezas"],
            monto_ventas=data["ventas"],
            monto_neto_ventas=data["neto"],
            monto_apartados=data["apartados"],
            monto_abonos=data["abonos"],
            monto_en_caja=data["en_caja"],
        )
        for dia, data in sorted(acc.items(), key=lambda kv: kv[0], reverse=True)
    ]


def eliminar_operacion(session, operacion_id: int) -> bool:
    """Borra un registro de la Libreta (corrección del dueño: se imprimió
    por error, venta que no se concretó). Devuelve True si existía.

    Una venta que movió el monedero (cashback o pago con saldo) NO se borra
    aquí: lanza `OperacionConMonedero`. Se anula desde el POS
    (`anular_operacion_con_monedero`), que compensa el saldo primero."""
    entry = session.get(LibretaVenta, int(operacion_id))
    if entry is None:
        return False
    _no_si_hay_cambios(session, entry)
    from pos_uniformes.services import monedero_service

    if monedero_service.tiene_movimientos(session, int(operacion_id)):
        raise monedero_service.OperacionConMonedero(
            "Esta venta movió el monedero del cliente: anúlala desde el POS "
            "(Monederos → Anular venta) para devolver el saldo correctamente."
        )
    return _borrar_operacion(session, entry, int(operacion_id))


def anular_operacion_con_monedero(session, operacion_id: int, *, usuario_id: int, motivo: str):
    """Anulación COMPLETA de una venta con monedero (solo ADMIN, con motivo).

    Compensa el monedero (reversa de cashback, devolución del saldo usado con
    su vencimiento original), suelta la liga y luego borra la operación y
    regresa el stock, como `eliminar_operacion`. Si el cashback ya se gastó
    se detiene sin tocar nada (`CashbackYaGastado`). No hace commit.

    Devuelve el `ResultadoAnulacion` o None si la operación no existe."""
    from pos_uniformes.services import monedero_service

    entry = session.get(LibretaVenta, int(operacion_id))
    if entry is None:
        return None
    _no_si_hay_cambios(session, entry)
    resultado = monedero_service.anular_operacion(session, entry, usuario_id=usuario_id, motivo=motivo)
    monedero_service.soltar_operacion(session, entry.id)
    _borrar_operacion(session, entry, int(operacion_id))
    session.flush()
    return resultado


def borrar_desde_libreta(session, operacion_id: int, *, actor: str):
    """El dueño borra un registro desde MOVIMIENTOS del kiosko (Daniel,
    2026-11-12: «¿esto podemos hacerlo en automático?»).

    Si la venta movió el Monedero, en vez de pedir ir al POS se anula aquí
    mismo con la anulación del POS: se revierte el abono y se le devuelve
    al cliente el saldo que usó, y luego se borra. La anulación queda a
    nombre del administrador, con el gafete de quien la hizo en el motivo.
    Si el cliente ya gastó el abono, se detiene (`CashbackYaGastado`).
    No hace commit.

    Devuelve (existía, ResultadoAnulacion | None)."""
    from pos_uniformes.database.models import RolUsuario, Usuario
    from pos_uniformes.services import monedero_service

    entry = session.get(LibretaVenta, int(operacion_id))
    if entry is None:
        return False, None
    _no_si_hay_cambios(session, entry)
    if not monedero_service.tiene_movimientos(session, int(operacion_id)):
        return _borrar_operacion(session, entry, int(operacion_id)), None
    admin = session.scalars(
        select(Usuario)
        .where(Usuario.activo.is_(True), Usuario.rol == RolUsuario.ADMIN)
        .order_by(Usuario.id)
    ).first()
    if admin is None:
        raise monedero_service.SinPermiso("No hay un administrador activo para anular la venta del monedero.")
    resultado = anular_operacion_con_monedero(
        session, int(operacion_id), usuario_id=admin.id,
        motivo=f"Borrada desde la Libreta del kiosko ({actor})",
    )
    return True, resultado


class OperacionConCambios(ValueError):
    """Un cambio, o una venta con cambios: no se borra (el texto se enseña)."""


def _no_si_hay_cambios(session, entry: LibretaVenta) -> None:
    from pos_uniformes.services.cambio_service import es_cambio_o_tiene_cambios

    motivo = es_cambio_o_tiene_cambios(session, entry)
    if motivo:
        raise OperacionConCambios(motivo)


def _borrar_operacion(session, entry: LibretaVenta, operacion_id: int) -> bool:
    try:
        devolver_stock(session, entry)   # lo que se llevó, regresa
    except Exception:  # noqa: BLE001 — borrar la operación vale más que el número
        logger.exception("Libreta %s: no se pudo devolver el stock", operacion_id)
    session.delete(entry)
    return True


# ─── Movimientos privados del dueño ──────────────────────────────────────
# El DINERO de un cobro con tarjeta que Daniel marca como privado desaparece
# de lo que ve el encargado: su ticket de corte, su pantalla y su modo del
# celular. Las comisiones y las piezas siguen contando (la empleada cobra lo
# que trabajó). Solo tarjeta: el efectivo está en el cajón y esconderlo
# descuadraría el corte.


class SoloElDueno(PermissionError):
    pass


def sin_privados(rows: list) -> list:
    """Las operaciones tal como las ve el encargado (sin las privadas)."""
    return [r for r in rows if not getattr(r, "privado", False)]


def hay_privados(rows: list) -> bool:
    return any(getattr(r, "privado", False) for r in rows)


def marcar_privado(session, operacion_id: int, *, privado: bool, creado_por: str):
    """Oculta (o vuelve a mostrar) un movimiento al encargado. Devuelve el
    registro; None si no existe."""
    from pos_uniformes.services.nomina_service import OWNER_CODE

    if str(creado_por or "").strip().upper() != OWNER_CODE:
        raise SoloElDueno("Solo el dueño puede ocultar movimientos.")
    entry = session.get(LibretaVenta, int(operacion_id))
    if entry is None:
        return None
    if privado and not bool(entry.pago_tarjeta):
        raise ValueError(
            "Solo se pueden ocultar cobros con tarjeta: el efectivo está en el "
            "cajón y esconderlo descuadraría el corte."
        )
    entry.privado = bool(privado)
    session.commit()
    return entry


def marcar_privadas_del_periodo(session, desde, hasta, *, creado_por: str) -> int:
    """Oculta de un golpe todos los cobros con tarjeta del periodo (la casilla
    del corte). Devuelve cuántos quedaron ocultos."""
    from pos_uniformes.services.nomina_service import OWNER_CODE

    if str(creado_por or "").strip().upper() != OWNER_CODE:
        raise SoloElDueno("Solo el dueño puede ocultar movimientos.")
    stmt = select(LibretaVenta).where(
        LibretaVenta.created_at > desde if desde is not None else sa_true(),
        LibretaVenta.created_at <= hasta,
        LibretaVenta.pago_tarjeta.is_(True),
    )
    cuantos = 0
    for entry in session.scalars(stmt).all():
        if not entry.privado:
            entry.privado = True
            cuantos += 1
    session.commit()
    return cuantos


def mostrar_tarjetas_del_periodo(session, desde, hasta, *, creado_por: str) -> int:
    """La reversa de `marcar_privadas_del_periodo`: vuelve visibles los cobros
    con tarjeta del periodo. Devuelve cuántos se destaparon.

    Existe porque /sintarjeta con un número equivocado escondía el periodo
    de otro corte y desde el celular no había camino de vuelta (2026-10-10)."""
    from pos_uniformes.services.nomina_service import OWNER_CODE

    if str(creado_por or "").strip().upper() != OWNER_CODE:
        raise SoloElDueno("Solo el dueño puede destapar movimientos.")
    stmt = select(LibretaVenta).where(
        LibretaVenta.created_at > desde if desde is not None else sa_true(),
        LibretaVenta.created_at <= hasta,
        LibretaVenta.pago_tarjeta.is_(True),
    )
    cuantos = 0
    for entry in session.scalars(stmt).all():
        if entry.privado:
            entry.privado = False
            cuantos += 1
    session.commit()
    return cuantos


def comisiones_ocultas(rows: list) -> int:
    """Comisiones que el encargado dejaría de ver (para avisar al ocultar)."""
    return sum(int(getattr(r, "comisiones", 0) or 0) for r in rows if getattr(r, "privado", False))


def cambiar_pago_tarjeta(session, operacion_id: int, tarjeta: bool):
    """Corrección del dueño: la empleada olvidó marcar "pagó con tarjeta"
    (o lo marcó de más). Cambia la bandera y RECALCULA el neto con la
    misma regla que la venta. T4 (M2): la comisión va una sola vez sobre lo
    cobrado con dinero (lo pagado con saldo no pasa por la terminal);
    efectivo → neto = lo cobrado. Devuelve el registro o None si no existe."""
    entry = session.get(LibretaVenta, int(operacion_id))
    if entry is None:
        return None
    total = Decimal(str(entry.monto_total or 0)).quantize(Decimal("0.01"))
    monedero = Decimal(str(getattr(entry, "monto_monedero", 0) or 0))
    neto = neto_de_cobro(total, monedero, bool(tarjeta))
    entry.pago_tarjeta = bool(tarjeta)
    entry.monto_neto = neto
    session.commit()
    return entry


class ReasignacionNoPermitida(ValueError):
    """La reasignación se bloqueó por una regla de negocio (el texto se le
    muestra tal cual al dueño)."""


def _fecha_local(momento: datetime) -> date:
    return momento.astimezone().date() if momento.tzinfo is not None else momento.date()


def reasignar_empleada(
    session,
    operacion_id: int,
    employee_code: str,
    employee_name: str | None = None,
    *,
    actor: str,
    hoy: date | None = None,
):
    """Corrección del dueño: la venta se registró con el gafete de OTRA
    empleada (una puso su código y la otra hizo la venta). Mueve el
    registro completo — y con él sus comisiones — a la empleada correcta.
    No toca montos, piezas ni fecha. Devuelve el registro o None si no existe.

    Reglas (Daniel, 2026-11-08; si una falla, NO se reasigna):
    - solo el dueño (VEND-1);
    - solo el mismo día de la venta;
    - la empleada destino existe, está activa y no es la misma;
    - la comisión no se le ha pagado a la empleada original;
    - la venta cae dentro de lo pendiente de la empleada destino (si a ella
      ya se le pagó después de esa venta, nadie la cobraría).
    Con las dos últimas no puede haber doble pago ni comisión perdida. El
    candado por empleada evita que un pago se cuele a la mitad.

    Deja constancia en la bitácora (quién, cuándo, de quién a quién y cuántas
    comisiones) en la MISMA transacción: o pasan las dos cosas o ninguna."""
    from pos_uniformes.database.models import Empleada
    from pos_uniformes.services import auditoria_ausencias_service
    from pos_uniformes.services.calendario_empleadas_service import bloquear_empleadas, corte_vigente
    from pos_uniformes.services.nomina_service import OWNER_CODE

    if str(actor or "").strip().upper() != OWNER_CODE:
        raise PermissionError("Solo Daniel puede reasignar ventas.")
    code = str(employee_code or "").strip().upper()
    if not code:
        raise ValueError("Falta el código de la empleada")
    entry = session.get(LibretaVenta, int(operacion_id))
    if entry is None:
        return None

    destino = session.scalar(select(Empleada).where(Empleada.codigo == code))
    if destino is None:
        raise ReasignacionNoPermitida(f"No existe la empleada {code}.")
    if not destino.activo:
        raise ReasignacionNoPermitida(f"{destino.nombre_completo or code} no está activa.")

    hoy = hoy or date.today()
    if _fecha_local(entry.created_at) != hoy:
        raise ReasignacionNoPermitida(
            "Solo se puede reasignar una venta el mismo día en que se hizo."
        )

    # Candado de las dos empleadas (en orden) y luego se vuelve a leer la
    # venta: lo que se valide abajo ya no lo puede cambiar un pago en curso.
    origen_bloqueado = str(entry.employee_code or "").strip().upper()
    bloquear_empleadas(session, [origen_bloqueado, code])
    entry = session.execute(
        select(LibretaVenta).where(LibretaVenta.id == int(operacion_id))
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if entry is None:
        session.rollback()
        return None
    anterior_code = str(entry.employee_code or "").strip().upper()
    if anterior_code != origen_bloqueado:
        # Otra reasignación la movió mientras esperábamos el candado (auditoría
        # 2026-11-08, M2). El candado tomado es el de otra empleada: no se
        # sigue, no se escribe bitácora y se suelta todo. Sin reintento
        # automático: el dueño vuelve a intentarlo viendo el estado nuevo.
        session.rollback()
        raise ReasignacionNoPermitida(
            "La venta cambió de empleada mientras se procesaba. Vuelve a intentarlo."
        )
    if anterior_code == code:
        raise ReasignacionNoPermitida("La venta ya es de esa empleada.")

    def _con_zona(momento: datetime) -> datetime:
        # Una hora sin zona (SQLite en pruebas) es hora local de la tienda.
        return momento.astimezone() if momento.tzinfo is None else momento

    def _ya_pagada_a(empleada: str) -> bool:
        # Misma regla que el pendiente: lo anterior al corte ya entró en un pago.
        corte = corte_vigente(session, empleada)
        return corte is not None and _con_zona(entry.created_at) < _con_zona(corte)

    nombre_anterior = entry.employee_name or anterior_code
    if _ya_pagada_a(anterior_code):
        raise ReasignacionNoPermitida(
            f"Esa venta ya se le pagó a {nombre_anterior}: no se puede reasignar."
        )
    nombre_nuevo = str(destino.nombre_completo or employee_name or code).strip()
    if _ya_pagada_a(code):
        raise ReasignacionNoPermitida(
            f"A {nombre_nuevo} ya se le pagó después de esa venta: no entraría en "
            "ningún pago. No se puede reasignar."
        )

    comisiones = int(entry.comisiones or 0)
    entry.employee_code = code
    entry.employee_name = nombre_nuevo
    auditoria_ausencias_service.registrar(
        session,
        actor=actor,
        origen="kiosko",
        operacion="reasignar_venta",
        entidad="libreta_venta",
        entidad_id=int(entry.id),
        employee_code=code,
        antes={"employee_code": anterior_code, "employee_name": nombre_anterior, "comisiones": comisiones},
        despues={"employee_code": code, "employee_name": nombre_nuevo, "comisiones": comisiones},
    )
    session.commit()
    return entry


def filtrar_de_hoy(rows: list, reference: date | None = None) -> list:
    """Deja solo las operaciones del día local dado (default: hoy).

    Permite consultar UNA vez la ventana de la semana y derivar la vista
    'Hoy' en memoria (la meta semanal necesita la semana completa)."""
    reference = reference or date.today()
    result = []
    for row in rows:
        created = row.created_at
        local_dt = created.astimezone() if created.tzinfo is not None else created
        if local_dt.date() == reference:
            result.append(row)
    return result


def hora_local(momento: datetime | None) -> datetime | None:
    """La hora en zona local y CON zona: se puede comparar con cualquier otra."""
    return momento.astimezone() if momento is not None else None


def desde_el_corte(rows: list, inicio_corte: datetime | None, reference: date | None = None) -> list:
    """El «Hoy» de la Libreta: lo vendido DESDE EL ÚLTIMO CORTE, no desde medianoche.

    Lo que importa es el dinero por entregar, y ese no se corta a medianoche
    sino en el corte. El 14/10 Daniel hizo el corte a las 16:56, después se
    vendieron $190 y $942, y al día siguiente no aparecían en «Hoy» aunque ese
    dinero se entregaba ese día (2026-10-15). Es la misma regla del corte
    (`corte_caja_service.inicio_periodo`): así la Libreta y el corte dan el
    mismo número.

    Sin ningún corte hecho, se queda como antes: el día de calendario."""
    if inicio_corte is None:
        return filtrar_de_hoy(rows, reference)
    inicio = hora_local(inicio_corte)
    return [r for r in rows if r.created_at is not None and hora_local(r.created_at) > inicio]


def etiqueta_desde_el_corte(inicio_corte: datetime | None, reference: date | None = None) -> str:
    """Cómo se dice el periodo: «desde el corte de ayer a las 16:56»."""
    if inicio_corte is None:
        return "hoy"
    inicio = hora_local(inicio_corte)
    hoy = reference or date.today()
    if inicio.date() == hoy:
        cuando = "de hoy"
    elif inicio.date() == hoy - timedelta(days=1):
        cuando = "de ayer"
    else:
        cuando = f"del {inicio:%d/%m}"
    return f"desde el corte {cuando} a las {inicio:%H:%M}"


def describir_detalle(detalle: list[dict]) -> str:
    """'Pants T:6 x2 · Playera T:M x1' — resumen legible de las líneas."""
    parts = []
    for line in detalle or []:
        nombre = str(line.get("nombre", "")).strip() or str(line.get("sku", ""))
        talla = str(line.get("talla", "")).strip()
        cantidad = int(line.get("cantidad", 0) or 0)
        talla_txt = f" T:{talla}" if talla and talla != "-" else ""
        parts.append(f"{nombre}{talla_txt} x{cantidad}")
    return " · ".join(parts)


def guardar_corte(
    session,
    *,
    fecha: date,
    monto_final: Decimal,
    operaciones: int,
    piezas: int,
    periodo_label: str = "HOY",
    nota: str = "",
    creado_por: str = "",
):
    """Registra el corte con SOLO la cifra final del dueño (sin esperado ni
    diferencia): el número oficial. Es lo que ve el encargado."""
    from pos_uniformes.database.models import LibretaCorte

    fila = LibretaCorte(
        fecha=fecha,
        periodo_label=periodo_label[:80],
        monto_final=monto_final,
        operaciones=int(operaciones),
        piezas=int(piezas),
        nota=(nota or None),
        creado_por=creado_por,
    )
    session.add(fila)
    session.commit()
    return fila


def listar_cortes(session, *, limit: int = 15):
    """Últimos cortes, el más reciente primero (vista del encargado)."""
    from pos_uniformes.database.models import LibretaCorte

    return (
        session.query(LibretaCorte)
        .order_by(LibretaCorte.fecha.desc(), LibretaCorte.id.desc())
        .limit(limit)
        .all()
    )
