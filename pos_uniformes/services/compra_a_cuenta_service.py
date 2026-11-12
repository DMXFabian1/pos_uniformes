"""Compras de empleadas a cuenta de su pago (Daniel, 2026-11-12).

«Un beneficio más: la posibilidad de decidir: pagan al momento, se les
descuenta esa semana de su paga o de la siguiente, siempre y cuando aún
conserve el descuento que se ganó.»

Las decisiones:

- **Solo con su nivel.** Se le ofrece mientras le quede tope de su nivel del
  mes; si ya se lo acabó (o no tiene nivel), paga al momento.
- **Mismo tope que los préstamos.** Compras a cuenta y préstamos suman juntos
  y no pasan del 70 % de lo que lleva ganado: así siempre cabe en su pago.
- **El bot le avisa y él la autoriza** (Daniel, 2026-11-12: «de esta clase
  de movimientos el bot me debe avisar, y los debo autorizar»).

Por dentro es un préstamo PEDIDO: la venta se anota como siempre (en
efectivo) y en ese momento sale un retiro del cajón por el mismo monto —la
mercancía ya se fue sin que entrara dinero—, así el corte cuadra mientras
Daniel decide. Si la autoriza queda APROBADA y se descuenta del pago que ella
eligió; si no, el retiro se quita y ella la paga en caja (mientras no la
pague, el corte marca ese faltante). «Del pago siguiente» guarda
`cobrar_desde`, y la nómina se salta los pagos anteriores a ese día.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone  # noqa: F401
from decimal import Decimal

from pos_uniformes.services import prestamos_service as pr

ESTE, SIGUIENTE = "este", "siguiente"
#: Así empieza el motivo de una compra a cuenta (lo distingue de un préstamo).
PREFIJO_MOTIVO = "Compra a cuenta"
_DIAS = ("lun", "mar", "mié", "jue", "vie", "sáb", "dom")
_MESES = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")
_CENT = Decimal("0.01")


def fecha_corta(d: date) -> str:
    return f"{_DIAS[d.weekday()]} {d.day} {_MESES[d.month - 1]}"


@dataclass(frozen=True)
class OpcionCuenta:
    clave: str                  # ESTE | SIGUIENTE
    fecha_pago: date            # el pago del que se descuenta
    cobrar_desde: date | None   # None = en el siguiente pago

    @property
    def texto(self) -> str:
        return f"📅  Pago del {fecha_corta(self.fecha_pago)}"


def opciones_de_pago(proximo: date | None, ciclo_dias: int) -> list[OpcionCuenta]:
    """Sus dos pagos que vienen: el próximo y el que le sigue.

    «Del siguiente» se descuenta a partir de la mitad del ciclo después del
    próximo pago: si el próximo se le paga un par de días tarde, la compra
    no se cuela en ese."""
    if proximo is None:
        return []
    ciclo = int(ciclo_dias) if int(ciclo_dias or 0) > 0 else 7
    siguiente = proximo + timedelta(days=ciclo)
    return [
        OpcionCuenta(ESTE, proximo, None),
        OpcionCuenta(SIGUIENTE, siguiente, proximo + timedelta(days=max(1, ciclo // 2))),
    ]


def por_que_no(compradora, monto, disponible) -> str | None:
    """None si se le puede dejar a cuenta; si no, por qué (para decírselo)."""
    if compradora is None:
        return "Sin compradora: paga al momento."
    if not getattr(compradora, "tiene_nivel", False):
        return "Sin descuento de nivel este mes: paga al momento."
    restante = compradora.restante
    if restante is not None and restante <= 0:
        return "Ya usó todo su descuento de nivel este mes: paga al momento."
    monto = Decimal(str(monto))
    disponible = Decimal(str(disponible or 0))
    if monto > disponible:
        if disponible <= 0:
            return "Todavía no le cabe nada a cuenta (va con lo que lleva ganado): paga al momento."
        return f"A cuenta le caben ${disponible:,.2f} (el 70 % de lo que lleva ganado): paga al momento."
    return None


def opciones_para(session, employee_code: str, hoy: date | None = None) -> tuple[list[OpcionCuenta], Decimal]:
    """Sus opciones y cuánto le cabe a cuenta hoy."""
    from pos_uniformes.services.calendario_empleadas_service import fecha_proximo_pago
    from pos_uniformes.services.nomina_service import cargar_horario

    hoy = hoy or date.today()
    horario = cargar_horario(session, employee_code)
    proximo = fecha_proximo_pago(horario, hoy)
    ciclo = 7 if getattr(horario, "por_dia", False) else int(getattr(horario, "ciclo_dias_pago", 7) or 7)
    return opciones_de_pago(proximo, ciclo), pr.disponible_para(session, employee_code, hoy)


def es_compra(prestamo) -> bool:
    return str(getattr(prestamo, "motivo", "") or "").startswith(PREFIJO_MOTIVO)


#: Cómo va la compra, tal como se ve en la Libreta del dueño.
POR_AUTORIZAR, AUTORIZADA, DESCONTADA = "por autorizar", "autorizada", "descontada"
_RE_TICKET = re.compile(r"ticket\s+([0-9a-fA-F]{8})")


def estados_en_libreta(session, filas) -> dict[int, str]:
    """De las ventas dadas, cuáles son compras a cuenta y cómo van.

    (Daniel, 2026-11-12: «este dinero no entró… ¿puede verse de otro color
    para saber que no es venta?») La venta se liga con su compra por el folio
    del ticket que lleva el motivo («… · ticket 9e9ad282»). Una compra que
    Daniel no autorizó ya no sale: ella la pagó en caja y es una venta normal.

    Devuelve {id de la venta: POR_AUTORIZAR | AUTORIZADA | DESCONTADA}."""
    from sqlalchemy import select

    from pos_uniformes.database.models import PrestamoEmpleada

    candidatas: dict[str, int] = {}
    fechas = []
    for f in filas or []:
        folio = str(getattr(f, "operacion_uuid", "") or "")
        if str(getattr(f, "tipo", "")) == "venta" and getattr(f, "descuento_empleada", False) and folio:
            candidatas[folio[:8].lower()] = int(f.id)
            if getattr(f, "created_at", None) is not None:
                fechas.append(f.created_at)
    if not candidatas:
        return {}
    consulta = select(PrestamoEmpleada).where(
        PrestamoEmpleada.motivo.like(f"{PREFIJO_MOTIVO}%"),
        PrestamoEmpleada.estado != pr.RECHAZADO,
    )
    if fechas:
        # La compra se anota en el mismo momento que la venta.
        consulta = consulta.where(
            PrestamoEmpleada.created_at >= min(fechas) - timedelta(days=1),
            PrestamoEmpleada.created_at <= max(fechas) + timedelta(days=1),
        )
    estados: dict[int, str] = {}
    for p in session.scalars(consulta):
        m = _RE_TICKET.search(str(p.motivo or ""))
        venta_id = candidatas.get(m.group(1).lower()) if m else None
        if venta_id is None:
            continue
        estado = str(p.estado)
        estados[venta_id] = (
            DESCONTADA if estado == pr.COBRADO else AUTORIZADA if estado == pr.APROBADO else POR_AUTORIZAR
        )
    return estados


def etiqueta_libreta(estado: str) -> str:
    """«📅 A cuenta · por autorizar»: lo que dice la columna Tipo."""
    return f"📅 A cuenta · {estado}"


def motivo_retiro(prestamo) -> str:
    """El retiro de una compra lleva el número de la compra para poder
    quitarlo si Daniel no la autoriza."""
    nombre = prestamo.employee_name or prestamo.employee_code
    return f"{PREFIJO_MOTIVO} de {nombre} · #{prestamo.id}"[:120]


def registrar(session, *, employee_code: str, nombre: str, monto, opcion: OpcionCuenta, quien: str,
              folio: str | None = None):
    """Deja la compra a cuenta por autorizar, con su retiro del cajón."""
    from pos_uniformes.database.models import PrestamoEmpleada
    from pos_uniformes.services.retiros_service import registrar_retiro

    monto = Decimal(str(monto)).quantize(_CENT)
    if monto <= 0:
        raise pr.NoSePuede("La compra tiene que ser mayor a cero.")
    disponible = pr.disponible_para(session, employee_code)
    if monto > disponible:
        raise pr.NoSePuede(f"A cuenta le caben ${disponible:,.2f}: cóbrale al momento.")
    motivo = f"{PREFIJO_MOTIVO} · pago del {fecha_corta(opcion.fecha_pago)}"
    if folio:
        motivo += f" · ticket {str(folio)[:8]}"
    prestamo = PrestamoEmpleada(
        employee_code=str(employee_code), employee_name=str(nombre or ""), monto=monto,
        motivo=motivo[:200], estado=pr.PEDIDO, cobrar_desde=opcion.cobrar_desde,
    )
    session.add(prestamo)
    session.flush()
    registrar_retiro(
        session, monto=monto, motivo=motivo_retiro(prestamo), creado_por=str(quien), revisar_repetido=False,
    )
    session.flush()
    return prestamo


def al_aprobar(session, prestamo) -> bool:
    """True si es una compra: su retiro ya salió al venderla, no otro."""
    return es_compra(prestamo)


def al_rechazar(session, prestamo) -> None:
    """Sin autorizar, la compra se paga en caja: se quita su retiro, así el
    corte espera ese dinero."""
    if not es_compra(prestamo):
        return
    from sqlalchemy import select

    from pos_uniformes.database.models import CajaRetiro

    retiro = session.scalars(
        select(CajaRetiro).where(CajaRetiro.motivo == motivo_retiro(prestamo)).order_by(CajaRetiro.id.desc())
    ).first()
    if retiro is not None:
        session.delete(retiro)
        session.flush()


def rechazadas_recientes(session, employee_code: str, *, dias: int = 3) -> list:
    """Sus compras a cuenta que Daniel no autorizó estos días (para que las pague)."""
    from datetime import timedelta as _td

    from sqlalchemy import select

    from pos_uniformes.database.models import PrestamoEmpleada

    desde = datetime.now(timezone.utc) - _td(days=dias)
    filas = session.scalars(
        select(PrestamoEmpleada).where(
            PrestamoEmpleada.employee_code == str(employee_code),
            PrestamoEmpleada.estado == pr.RECHAZADO,
            PrestamoEmpleada.motivo.like(f"{PREFIJO_MOTIVO}%"),
            PrestamoEmpleada.resuelto_at >= desde,
        ).order_by(PrestamoEmpleada.id)
    ).all()
    return list(filas)


def avisar_a_daniel(session, prestamo) -> None:
    """Le llega al instante con sus botones; si no hay señal, queda en la
    cola de alertas (texto sin botones: se contesta con /prestamos)."""
    import logging

    from pos_uniformes.services import telegram_prestamos_service as prs

    texto = prs.aviso_de_solicitud(prestamo, session=session)
    try:
        from pos_uniformes.services.telegram_service import enviar_mensaje

        enviar_mensaje(texto, botones=prs.botones_de(prestamo))
    except Exception:  # noqa: BLE001
        try:
            from pos_uniformes.services.alertas_service import encolar

            encolar(session, texto + "\n\nPara responder: /prestamos")
            session.commit()
        except Exception:  # noqa: BLE001
            logging.getLogger(__name__).exception("Compra a cuenta: no se pudo avisar")
