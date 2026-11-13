"""Cambios de prenda desde la venta (folio del ticket).

Daniel (2026-11-12): «para registrar cambios y salidas, y si hay diferencia
que se vaya a Monedero, o en caso de que el cliente deba pagar diferencia;
también para que los inventarios cuadren, porque entra ropa y sale otra».

Reglas que eligió Daniel (2026-11-12):

1. Lo que regresa vale **lo que pagó** en esa venta (con sus descuentos y
   redondeo), no el precio de hoy.
2. El Monedero que ganó por lo que regresa **se le quita**: se descuenta de
   lo que se le reconoce (si ya lo gastó, igual se descuenta de aquí).
3. Si queda **a favor del cliente**, va a su Monedero. Sin cliente registrado
   hay que identificarlo o darlo de alta antes de cerrar el cambio.
4. **15 días** (lo que dice el ticket). Después, solo si el dueño lo autoriza.
5. (2026-11-12, Daniel: «solucionemos estos») Lo vendido en **Liquidación**
   no se regresa: el ticket dice «sin cambios ni devoluciones» y ahora el
   sistema hace lo mismo. Solo el dueño lo puede autorizar (p. ej. una prenda
   defectuosa), con la misma autorización que el plazo vencido. Lo de Oferta
   sí se cambia, y llevarse algo en Liquidación en un cambio sí se puede.
   Ventas viejas sin el tipo de rebaja (`"rebaja"` vacío o `true`): no se
   sabe si fue Liquidación, así que se dejan cambiar.

Lo que se lleva vale el precio de hoy (con su Oferta o Liquidación si la
tiene). Lo que paga de diferencia se redondea como cualquier cobro (R1).

6. (2026-11-12, Daniel: «Sí, que no aplique») Promo 3pz y E7: la playera a
   $100 solo va con un pants base que no está rebajado. Si en el cambio se
   regresa el pants base de la promo y se lleva un Pants 2pz deportivo en
   Oferta o Liquidación, la playera que se queda pierde la promo: se cobra la
   diferencia contra su precio normal (`cargo_promo_3pz`).

En la Libreta queda una operación tipo «cambio»: su monto es la diferencia
que entró al cajón (el corte la cuenta como dinero de venta), sin piezas ni
comisiones (no es una venta nueva). El stock se mueve con su referencia: lo
que regresa entra (CANCELACION_VENTA) y lo que se lleva sale (SALIDA_VENTA).
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import ROUND_DOWN, Decimal

from sqlalchemy import select

from pos_uniformes.database.models import LibretaVenta

logger = logging.getLogger(__name__)

TIPO = "cambio"
PLAZO_DIAS = 15
ENTRA, SALE = "entra", "sale"
_CENT = Decimal("0.01")
_CERO = Decimal("0.00")


class CambioError(ValueError):
    """El cambio no se puede hacer así (el texto se le enseña a la empleada)."""


class FueraDePlazo(CambioError):
    """Pasaron más de 15 días: solo con autorización del dueño."""


class EnLiquidacion(CambioError):
    """Regresa una prenda vendida en Liquidación: solo con autorización del dueño."""


MENSAJE_LIQUIDACION = "Las prendas en Liquidación no tienen cambio ni devolución. Solo el dueño lo puede autorizar."


class NecesitaCliente(CambioError):
    """Queda saldo a favor y la venta no tiene cliente: hay que identificarlo."""


def _d(valor) -> Decimal:
    return Decimal(str(valor if valor not in (None, "") else 0))


# ─── Lo que se vendió y cuánto vale cada pieza ───────────────────────────


@dataclass(frozen=True)
class RenglonVendido:
    renglon: int            # posición en el detalle de la venta
    sku: str
    nombre: str
    talla: str
    vendidas: int
    ya_cambiadas: int
    valor_pieza: Decimal    # lo que pagó por pieza (con descuentos y redondeo)
    rebajada: bool          # Oferta/Liquidación: no generó Monedero
    liquidacion: bool = False   # vendida en Liquidación: sin cambio (salvo el dueño)
    rol_3pz: str = ""           # "base" | "playera" de la promo 3pz, o vacío
    precio_normal: Decimal | None = None   # de la playera en promo: su precio de hoy

    @property
    def disponibles(self) -> int:
        return max(self.vendidas - self.ya_cambiadas, 0)


def vendida_en_liquidacion(linea: dict) -> bool:
    """¿Este renglón de la venta se vendió en Liquidación? (2026-11-12)

    Solo cuenta si el detalle lo dice («liquidacion»). Si dice «oferta», o
    es una venta vieja que solo trae `true` o nada, no se sabe: se permite."""
    from pos_uniformes.services.rebaja_service import LIQUIDACION

    return str(linea.get("rebaja") or "").strip().lower() == LIQUIDACION


def liquidacion_que_regresa(renglones: list[RenglonVendido], regresa: dict[int, int]) -> list[RenglonVendido]:
    """Los renglones en Liquidación que se intentan regresar (regla pura)."""
    return [renglones[int(i)] for i, q in regresa.items()
            if int(q) > 0 and 0 <= int(i) < len(renglones) and renglones[int(i)].liquidacion]


def _precio_cobrado(linea: dict, venta) -> Decimal:
    """El precio por pieza ya con su descuento (antes del redondeo)."""
    precio = _d(linea.get("precio"))
    pct = linea.get("desc_empleada_pct")
    if pct in (None, "") and getattr(venta, "descuento_programa", None) and not linea.get("rebaja") \
            and not linea.get("promo_3pz"):
        pct = venta.descuento_programa
    if pct not in (None, ""):
        precio = precio * (Decimal(100) - _d(pct)) / Decimal(100)
    return precio


def valores_por_pieza(venta) -> list[Decimal]:
    """Lo que pagó por pieza en cada renglón. Se reparte el total cobrado
    (con redondeo) en proporción, así la suma cuadra con lo que pagó."""
    detalle = list(venta.detalle or [])
    brutos = [_precio_cobrado(l, venta) for l in detalle]
    cantidades = [int(l.get("cantidad", 0) or 0) for l in detalle]
    suma = sum((b * q for b, q in zip(brutos, cantidades)), Decimal(0))
    total = _d(venta.monto_total)
    if suma <= 0:
        return [_CERO for _ in detalle]
    factor = total / suma
    return [b * factor for b in brutos]


def cambios_de_venta(session, venta) -> list[LibretaVenta]:
    """Los cambios que ya se hicieron sobre esta venta."""
    filas = session.scalars(
        select(LibretaVenta).where(LibretaVenta.tipo == TIPO, LibretaVenta.created_at >= venta.created_at)
    ).all()
    return [f for f in filas if ((f.calculo or {}).get("cambio") or {}).get("venta_id") == venta.id]


# ─── Promo 3pz en el cambio (E7, 2026-11-12: «Sí, que no aplique») ───────

#: La marca que el kiosko le pone a lo que se lleva cuando es un Pants 2pz
#: deportivo (el que puede ser base de la promo 3pz).
LLAVE_PANTS_3PZ = "pants_2pz_deportivo"
BASE_3PZ, PLAYERA_3PZ = "base", "playera"
MENSAJE_PROMO_3PZ = "La playera iba en promo con ese pants: el pants nuevo está en {}, la playera se cobra a precio normal."


def roles_promo_3pz(detalle: list[dict], calculo: dict | None) -> list[str]:
    """Qué renglón de la venta fue el pants base y cuál la playera de la promo.

    La Libreta marca `promo_3pz` solo con mayoreo; la fotografía del motor
    (`calculo.entrada.lineas`) lo trae siempre, ligado por `linea_uid`. La
    playera se reconoce por su nombre («… (promo 3pz)»). Sin ninguna de las
    dos marcas, el renglón no es de la promo."""
    from pos_uniformes.services.sports_uniform_pricing_service import PROMO_NAME_SUFFIX

    lineas = (((calculo or {}).get("entrada") or {}).get("lineas")) or []
    uids_3pz = {str(l.get("linea_uid")) for l in lineas if isinstance(l, dict) and l.get("promo_3pz")}
    roles = []
    for l in detalle:
        playera = str(l.get("nombre") or "").endswith(PROMO_NAME_SUFFIX)
        es_3pz = playera or bool(l.get("promo_3pz")) or (bool(l.get("linea_uid")) and str(l["linea_uid"]) in uids_3pz)
        roles.append(PLAYERA_3PZ if playera else BASE_3PZ if es_3pz else "")
    return roles


def _pants_rebajados_que_lleva(lleva: list[dict]) -> int:
    from pos_uniformes.services.rebaja_service import es_rebajado

    return sum(int(it.get("cantidad", 0) or 0) for it in lleva if it.get(LLAVE_PANTS_3PZ) and es_rebajado(it))


def cargo_promo_3pz(renglones: list[RenglonVendido], regresa: dict[int, int], lleva: list[dict]) -> Decimal:
    """Lo que se cobra porque la playera de la promo pierde la promo (pura).

    Por cada pants base que regresa y se cambia por un Pants 2pz deportivo
    rebajado, una playera en promo que se queda se cobra a su precio normal:
    la diferencia contra lo que pagó por ella. Si se regresa el pants por uno
    a precio normal (o la playera también regresa), no cambia nada."""
    bases = sum(int(q) for i, q in regresa.items()
                if 0 <= int(i) < len(renglones) and renglones[int(i)].rol_3pz == BASE_3PZ)
    piezas = min(bases, _pants_rebajados_que_lleva(lleva))
    cargo = _CERO
    for r in renglones:
        if piezas <= 0:
            break
        if r.rol_3pz != PLAYERA_3PZ or r.precio_normal is None:
            continue
        k = min(piezas, max(r.disponibles - int(regresa.get(r.renglon, 0)), 0))
        piezas -= k
        cargo += max(r.precio_normal - r.valor_pieza, _CERO) * k
    return cargo.quantize(_CENT)


def aviso_promo_3pz(renglones: list[RenglonVendido], regresa: dict[int, int], lleva: list[dict]) -> str:
    """El texto corto para la empleada cuando hay cargo de la promo 3pz."""
    from pos_uniformes.services.rebaja_service import ETIQUETAS, LLAVE, es_rebajado

    if cargo_promo_3pz(renglones, regresa, lleva) <= 0:
        return ""
    pants = next(it for it in lleva if it.get(LLAVE_PANTS_3PZ) and es_rebajado(it))
    return MENSAJE_PROMO_3PZ.format(ETIQUETAS.get(str(pants.get(LLAVE) or ""), "Oferta"))


def _precios_normales(session, skus: set[str]) -> dict[str, Decimal]:
    from pos_uniformes.database.models import Variante

    if not skus:
        return {}
    filas = session.execute(select(Variante.sku, Variante.precio_venta).where(Variante.sku.in_(skus))).all()
    return {str(sku): _d(precio) for sku, precio in filas}


def renglones_vendidos(session, venta) -> list[RenglonVendido]:
    ya: dict[int, int] = {}
    for c in cambios_de_venta(session, venta):
        for l in c.detalle or []:
            if l.get("cambio") == ENTRA:
                r = int(l.get("renglon", -1))
                ya[r] = ya.get(r, 0) + int(l.get("cantidad", 0) or 0)
    valores = valores_por_pieza(venta)
    detalle = list(venta.detalle or [])
    roles = roles_promo_3pz(detalle, venta.calculo if isinstance(venta.calculo, dict) else None)
    normales = _precios_normales(
        session, {str(l.get("sku", "")) for l, rol in zip(detalle, roles) if rol == PLAYERA_3PZ}
    )
    return [
        RenglonVendido(
            renglon=i, sku=str(l.get("sku", "")), nombre=str(l.get("nombre", "")), talla=str(l.get("talla", "")),
            vendidas=int(l.get("cantidad", 0) or 0), ya_cambiadas=ya.get(i, 0), valor_pieza=valores[i],
            rebajada=bool(l.get("rebaja")), liquidacion=vendida_en_liquidacion(l),
            rol_3pz=roles[i], precio_normal=normales.get(str(l.get("sku", ""))) if roles[i] == PLAYERA_3PZ else None,
        )
        for i, l in enumerate(detalle)
    ]


# ─── La cuenta del cambio (pura) ─────────────────────────────────────────


@dataclass(frozen=True)
class Cuenta:
    valor_regresa: Decimal       # lo que pagó por lo que regresa
    cashback_quitado: Decimal    # el Monedero que había ganado por eso
    reconocido: Decimal          # valor_regresa − cashback_quitado
    valor_lleva: Decimal         # lo nuevo, a precio de hoy
    a_pagar: Decimal             # lo que paga de diferencia (redondeado)
    a_favor: Decimal             # lo que va a su Monedero
    cargo_promo_3pz: Decimal = _CERO   # la playera que pierde la promo 3pz (E7)


def cuenta(valor_regresa: Decimal, cashback_quitado: Decimal, valor_lleva: Decimal,
           cargo_promo_3pz: Decimal = _CERO) -> Cuenta:
    from pos_uniformes.services.beneficios.reparto import redondeo_tienda

    valor_regresa = valor_regresa.quantize(_CENT)
    cashback_quitado = min(cashback_quitado.quantize(_CENT), valor_regresa)
    reconocido = valor_regresa - cashback_quitado
    valor_lleva = valor_lleva.quantize(_CENT)
    cargo_promo_3pz = max(cargo_promo_3pz.quantize(_CENT), _CERO)
    diferencia = valor_lleva + cargo_promo_3pz - reconocido
    a_pagar = redondeo_tienda(diferencia) if diferencia > 0 else _CERO
    a_favor = -diferencia if diferencia < 0 else _CERO
    return Cuenta(valor_regresa, cashback_quitado, reconocido, valor_lleva, max(a_pagar, _CERO), a_favor,
                  cargo_promo_3pz)


def cashback_proporcional(abono: Decimal, ya_quitado: Decimal, renglones: list[RenglonVendido],
                          regresa: dict[int, int]) -> Decimal:
    """La parte del Monedero que ganó la venta por lo que regresa: el abono
    repartido entre lo que sí lo generó (sin Oferta/Liquidación), truncado
    al centavo. Nunca más de lo que queda sin quitar en cambios anteriores."""
    if abono <= 0:
        return _CERO
    elegible_total = sum((r.valor_pieza * r.vendidas for r in renglones if not r.rebajada), Decimal(0))
    if elegible_total <= 0:
        return _CERO
    elegible = sum((renglones[i].valor_pieza * q for i, q in regresa.items() if not renglones[i].rebajada), Decimal(0))
    quitar = (abono * elegible / elegible_total).quantize(_CENT, rounding=ROUND_DOWN)
    return max(min(quitar, abono - ya_quitado), _CERO)


def contexto_cashback(session, venta) -> tuple[Decimal, Decimal]:
    """(Monedero que ganó la venta, lo que ya se le quitó en otros cambios)."""
    from pos_uniformes.services import monedero_service as mon

    abono = sum((_d(m.monto) for m in mon.movimientos_de_operacion(session, venta.id) if m.tipo == mon.CASHBACK), _CERO)
    ya = sum((_d(((c.calculo or {}).get("cambio") or {}).get("cashback_quitado")) for c in cambios_de_venta(session, venta)), _CERO)
    return abono, ya


def cashback_a_quitar(session, venta, renglones: list[RenglonVendido], regresa: dict[int, int]) -> Decimal:
    abono, ya = contexto_cashback(session, venta)
    return cashback_proporcional(abono, ya, renglones, regresa)


def _valor_lleva(lleva: list[dict]) -> Decimal:
    return sum((_d(it.get("precio")) * int(it.get("cantidad", 0) or 0) for it in lleva), _CERO)


def preparar(session, venta, regresa: dict[int, int], lleva: list[dict]) -> tuple[list[RenglonVendido], Cuenta]:
    """Valida lo que regresa y calcula la cuenta (no escribe nada)."""
    if venta is None or str(venta.tipo) != "venta":
        raise CambioError("Solo se puede cambiar lo de una venta.")
    regresa = {int(i): int(q) for i, q in regresa.items() if int(q) > 0}
    if not regresa:
        raise CambioError("Elige qué prenda regresa el cliente.")
    renglones = renglones_vendidos(session, venta)
    for i, q in regresa.items():
        if i < 0 or i >= len(renglones):
            raise CambioError("Esa prenda no está en la venta.")
        if q > renglones[i].disponibles:
            r = renglones[i]
            raise CambioError(
                f"De «{r.nombre} T:{r.talla}» se vendieron {r.vendidas} y ya se cambiaron {r.ya_cambiadas}: "
                f"quedan {r.disponibles} para cambio."
            )
    valor_regresa = sum((renglones[i].valor_pieza * q for i, q in regresa.items()), Decimal(0))
    quitar = cashback_a_quitar(session, venta, renglones, regresa)
    cargo = cargo_promo_3pz(renglones, regresa, lleva)
    return renglones, cuenta(valor_regresa, quitar, _valor_lleva(lleva), cargo)


def dias_desde(venta, momento: datetime | None = None) -> int:
    momento = momento or datetime.now(timezone.utc)
    creada = venta.created_at if venta.created_at.tzinfo else venta.created_at.replace(tzinfo=timezone.utc)
    return (momento - creada).days


# ─── Registrar ───────────────────────────────────────────────────────────


@dataclass
class ResultadoCambio:
    cambio: LibretaVenta
    cuenta: Cuenta
    folio_venta: str
    regresa: list[dict] = field(default_factory=list)
    lleva: list[dict] = field(default_factory=list)


def _admin_id(session) -> int:
    from pos_uniformes.database.models import RolUsuario, Usuario
    from pos_uniformes.services.monedero_service import SinPermiso

    admin = session.scalars(
        select(Usuario).where(Usuario.activo.is_(True), Usuario.rol == RolUsuario.ADMIN).order_by(Usuario.id)
    ).first()
    if admin is None:
        raise SinPermiso("No hay un administrador activo para abonar el saldo del cambio.")
    return admin.id


def _mover_stock(session, cambio: LibretaVenta, renglones: list[dict]) -> None:
    from pos_uniformes.database.models import TipoMovimientoInventario, Variante
    from pos_uniformes.services.inventario_service import InventarioService

    referencia = f"libreta:{cambio.id}"
    for r in renglones:
        sku = str(r.get("sku") or "").strip()
        cantidad = int(r.get("cantidad", 0) or 0)
        if not sku or cantidad <= 0:
            continue
        entra = r.get("cambio") == ENTRA
        try:
            with session.begin_nested():
                variante = session.scalar(select(Variante).where(Variante.sku == sku))
                if variante is None:
                    continue
                InventarioService.registrar_movimiento(
                    session, variante,
                    TipoMovimientoInventario.CANCELACION_VENTA if entra else TipoMovimientoInventario.SALIDA_VENTA,
                    cantidad if entra else -cantidad,
                    referencia=referencia,
                    observacion=f"cambio en el kiosko ({cambio.employee_code}): {'regresa' if entra else 'se lleva'}",
                    creado_por=str(cambio.employee_code or "kiosko"),
                    allow_negative_stock=True,
                )
        except Exception:  # noqa: BLE001 — el cambio vale más que el número; queda en el log
            logger.exception("Cambio %s: no se pudo mover el stock de %s (sku %s)", cambio.id, cantidad, sku)


def registrar_cambio(
    session,
    *,
    venta_id: int,
    regresa: dict[int, int],
    lleva: list[dict],
    employee_code: str,
    employee_name: str = "",
    cliente_id: int | None = None,
    pago_tarjeta: bool = False,
    autorizo_dueno: bool = False,
    origen: str | None = None,
    momento: datetime | None = None,
) -> ResultadoCambio:
    """Registra el cambio completo: Libreta, stock y Monedero. No hace commit.

    `regresa` = {renglón de la venta: piezas}; `lleva` = renglones del
    carrito (sku, nombre, talla, cantidad, precio y, si aplica, rebaja)."""
    from pos_uniformes.database.models import Cliente
    from pos_uniformes.services import monedero_service as mon
    from pos_uniformes.services.folio_venta_service import folio_corto
    from pos_uniformes.services.libreta_service import neto_de_cobro

    momento = momento or datetime.now(timezone.utc)
    venta = session.scalars(select(LibretaVenta).where(LibretaVenta.id == int(venta_id)).with_for_update()).first()
    if venta is None:
        raise CambioError("No encontré la venta.")
    if dias_desde(venta, momento) > PLAZO_DIAS and not autorizo_dueno:
        raise FueraDePlazo(
            f"Esta venta tiene {dias_desde(venta, momento)} días: el plazo de cambio es de {PLAZO_DIAS}. "
            "Solo el dueño lo puede autorizar."
        )
    renglones, c = preparar(session, venta, regresa, lleva)
    if liquidacion_que_regresa(renglones, regresa) and not autorizo_dueno:
        raise EnLiquidacion(MENSAJE_LIQUIDACION)
    cliente_id = cliente_id or venta.cliente_id
    if c.a_favor > 0 and cliente_id is None:
        raise NecesitaCliente(
            f"Le quedan ${c.a_favor:,.2f} a favor y la venta no tiene cliente: "
            "identifícalo o dalo de alta para abonarlo a su Monedero."
        )
    folio = folio_corto(venta.operacion_uuid) if venta.operacion_uuid else f"#{venta.id}"
    renglones_regresa = [
        {
            "cambio": ENTRA, "renglon": i, "sku": renglones[i].sku,
            "nombre": f"↩ Regresa: {renglones[i].nombre}", "talla": renglones[i].talla, "cantidad": q,
            "precio": str(renglones[i].valor_pieza.quantize(_CENT)),
        }
        for i, q in sorted({int(k): int(v) for k, v in regresa.items() if int(v) > 0}.items())
    ]
    renglones_lleva = [
        {
            "cambio": SALE, "sku": str(it.get("sku", "")), "nombre": f"→ Se lleva: {it.get('nombre', '')}",
            "talla": str(it.get("talla", "")), "cantidad": int(it.get("cantidad", 0) or 0),
            "precio": str(_d(it.get("precio")).quantize(_CENT)),
            **({"rebaja": str(it["rebaja"]), "precio_normal": str(it.get("precio_normal") or "")} if it.get("rebaja") else {}),
        }
        for it in lleva if int(it.get("cantidad", 0) or 0) > 0
    ]
    nombre_cliente = venta.cliente
    if cliente_id and cliente_id != venta.cliente_id:
        cli = session.get(Cliente, int(cliente_id))
        nombre_cliente = getattr(cli, "nombre", None) or nombre_cliente
    cambio = LibretaVenta(
        employee_code=str(employee_code).upper(),
        employee_name=employee_name or "",
        tipo=TIPO,
        cliente=nombre_cliente,
        cliente_id=int(cliente_id) if cliente_id else None,
        piezas=0,
        comisiones=0,
        monto_total=c.a_pagar,
        monto_neto=neto_de_cobro(c.a_pagar, _CERO, bool(pago_tarjeta)),
        pago_tarjeta=bool(pago_tarjeta) and c.a_pagar > 0,
        descuento_empleada=False,
        detalle=renglones_regresa + renglones_lleva,
        origen=origen,
        operacion_uuid=str(uuid.uuid4()),
        monto_monedero=_CERO,
        calculo={"cambio": {
            "venta_id": venta.id,
            "venta_uuid": venta.operacion_uuid,
            "folio_venta": folio,
            "valor_regresa": str(c.valor_regresa),
            "cashback_quitado": str(c.cashback_quitado),
            "valor_lleva": str(c.valor_lleva),
            "a_pagar": str(c.a_pagar),
            "a_favor": str(c.a_favor),
            "autorizo_dueno": bool(autorizo_dueno),
            **({"cargo_promo_3pz": str(c.cargo_promo_3pz)} if c.cargo_promo_3pz > 0 else {}),
        }},
        created_at=momento,
    )
    session.add(cambio)
    session.flush()
    _mover_stock(session, cambio, renglones_regresa + renglones_lleva)
    if c.a_favor > 0:
        mov = mon.ajustar(
            session, cliente_id=int(cliente_id), monto=c.a_favor, usuario_id=_admin_id(session),
            motivo=f"Saldo a favor por cambio de la venta {folio} ({cambio.employee_code})",
            llave=f"cambio:{cambio.operacion_uuid}", momento=momento,
        )
        mov.libreta_venta_id = cambio.id
        mov.operacion_uuid = cambio.operacion_uuid
        session.flush()
    return ResultadoCambio(cambio, c, folio, renglones_regresa, renglones_lleva)


def es_cambio_o_tiene_cambios(session, entry) -> str | None:
    """Por qué no se puede borrar así esta operación (o None si se puede).
    Borrar un cambio, o una venta que ya tuvo cambios, descuadraría el stock
    y el Monedero."""
    if str(getattr(entry, "tipo", "")) == TIPO:
        return "Un cambio no se borra: si se hizo mal, haz otro cambio que lo regrese."
    if str(getattr(entry, "tipo", "")) == "venta" and cambios_de_venta(session, entry):
        return "Esta venta ya tuvo cambios: no se puede borrar (descuadraría el stock y el Monedero)."
    return None
