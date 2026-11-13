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

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone  # noqa: F401
from decimal import Decimal

from pos_uniformes.services import prestamos_service as pr

ESTE, SIGUIENTE = "este", "siguiente"
#: Así empieza el motivo de una compra a cuenta. Desde 2026-11-12 solo es
#: texto para leer: la compra se reconoce por `prestamo_empleada.tipo`.
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
    """Por la columna `tipo` (2026-11-12), ya no por el texto del motivo."""
    return getattr(prestamo, "tipo", None) == pr.TIPO_COMPRA


#: Cómo va la compra, tal como se ve en la Libreta del dueño.
POR_AUTORIZAR, AUTORIZADA, DESCONTADA = "por autorizar", "autorizada", "descontada"
#: Con varias filas de la misma compra (un pago parcial la parte en dos), gana
#: la que menos avanzó: mientras algo se deba, sigue «autorizada».
_PRIORIDAD = {POR_AUTORIZAR: 0, AUTORIZADA: 1, DESCONTADA: 2}
_LOTE = 500


def _estado_de(prestamo) -> str:
    estado = str(prestamo.estado)
    return DESCONTADA if estado == pr.COBRADO else AUTORIZADA if estado == pr.APROBADO else POR_AUTORIZAR


def estados_en_libreta(session, filas) -> dict[int, str]:
    """De las ventas dadas, cuáles son compras a cuenta y cómo van.

    (Daniel, 2026-11-12: «este dinero no entró… ¿puede verse de otro color
    para saber que no es venta?») La venta se liga con su compra por la
    columna `libreta_venta_id` (antes: el folio dentro del motivo, con una
    ventana de fechas). Una compra que Daniel no autorizó ya no sale: ella la
    pagó en caja y es una venta normal.

    Determinista: si un pago parcial partió la compra en dos filas (una
    cobrada y otra que sigue debiéndose), la etiqueta es la del estado menos
    avanzado, sin importar el orden en que lleguen.

    Devuelve {id de la venta: POR_AUTORIZAR | AUTORIZADA | DESCONTADA}."""
    from sqlalchemy import select

    from pos_uniformes.database.models import PrestamoEmpleada

    ids = sorted({int(f.id) for f in filas or [] if getattr(f, "id", None) is not None})
    estados: dict[int, str] = {}
    for i in range(0, len(ids), _LOTE):
        consulta = select(PrestamoEmpleada).where(
            PrestamoEmpleada.libreta_venta_id.in_(ids[i:i + _LOTE]),
            PrestamoEmpleada.tipo == pr.TIPO_COMPRA,
            PrestamoEmpleada.estado != pr.RECHAZADO,
        ).order_by(PrestamoEmpleada.id)
        for p in session.scalars(consulta):
            venta_id, estado = int(p.libreta_venta_id), _estado_de(p)
            previo = estados.get(venta_id)
            if previo is None or _PRIORIDAD[estado] < _PRIORIDAD[previo]:
                estados[venta_id] = estado
    return estados


def etiqueta_libreta(estado: str) -> str:
    """«📅 A cuenta · por autorizar»: lo que dice la columna Tipo."""
    return f"📅 A cuenta · {estado}"


def motivo_retiro(prestamo) -> str:
    """El texto del retiro de una compra (se lee en el corte y en el aviso).
    Se liga por `caja_retiro.prestamo_id`, no por este texto (2026-11-12)."""
    nombre = prestamo.employee_name or prestamo.employee_code
    return f"{PREFIJO_MOTIVO} de {nombre} · #{prestamo.id}"[:120]


def registrar(session, *, employee_code: str, nombre: str, monto, opcion: OpcionCuenta, quien: str,
              folio: str | None = None, libreta_venta=None):
    """Deja la compra a cuenta por autorizar, con su retiro del cajón. Sin
    commit: lo hace quien llama (el kiosko usa `registrar_venta_a_cuenta`).

    `quien` es el código real de quien la apunta (la empleada o el kiosko):
    el retiro se apunta con el permiso propio de la compra a cuenta
    (`retiros_service.registrar_retiro_de_compra_a_cuenta`), ya no con el
    código del dueño para brincar `puede_pagar` (2026-11-12).

    La venta se liga por columna: `libreta_venta` si se tiene; si no, la
    venta cuyo `operacion_uuid` es exactamente `folio`. Una compra sin venta
    ligada no saca ni su retiro ni nada del corte (los dos cuentan y se
    cancelan): nunca queda un retiro huérfano fuera del corte."""
    from sqlalchemy import select

    from pos_uniformes.database.models import LibretaVenta, PrestamoEmpleada
    from pos_uniformes.services.retiros_service import registrar_retiro_de_compra_a_cuenta

    monto = Decimal(str(monto)).quantize(_CENT)
    if monto <= 0:
        raise pr.NoSePuede("La compra tiene que ser mayor a cero.")
    disponible = pr.disponible_para(session, employee_code)
    if monto > disponible:
        raise pr.NoSePuede(f"A cuenta le caben ${disponible:,.2f}: cóbrale al momento.")
    if libreta_venta is None and folio:
        libreta_venta = session.scalars(
            select(LibretaVenta).where(LibretaVenta.operacion_uuid == str(folio)).limit(1)
        ).first()
    motivo = f"{PREFIJO_MOTIVO} · pago del {fecha_corta(opcion.fecha_pago)}"
    if folio:
        motivo += f" · ticket {str(folio)[:8]}"
    prestamo = PrestamoEmpleada(
        employee_code=str(employee_code), employee_name=str(nombre or ""), monto=monto,
        motivo=motivo[:200], estado=pr.PEDIDO, cobrar_desde=opcion.cobrar_desde,
        tipo=pr.TIPO_COMPRA, libreta_venta_id=(libreta_venta.id if libreta_venta is not None else None),
    )
    session.add(prestamo)
    session.flush()
    registrar_retiro_de_compra_a_cuenta(session, prestamo, creado_por=quien)
    session.flush()
    return prestamo


def registrar_venta_a_cuenta(session, *, entrada: dict, employee_code: str, nombre: str,
                             opcion: OpcionCuenta, creado_por: str):
    """La venta de la Libreta, la compra a cuenta y su retiro, en UNA
    transacción con UN commit (2026-11-12).

    Antes eran dos: el kiosko guardaba la compra y el retiro (commit) y
    DESPUÉS encolaba la venta; si la venta no llegaba —o caía fuera de la
    ventana con la que se buscaba—, el retiro salía del corte y la venta no:
    un faltante falso. Ahora quedan las tres o ninguna (rollback, y el error
    sube para que el kiosko avise).

    `entrada` es la foto de la venta tal como la arma el kiosko para la cola
    de la Libreta (`_armar_anotacion`); se sube con la misma función que el
    drenado, así que la cola la reconoce después por su `operacion_uuid`.
    Devuelve la compra. Después del commit encola el aviso del retiro, como
    antes."""
    from sqlalchemy import select

    from pos_uniformes.database.models import CajaRetiro, LibretaVenta, PrestamoEmpleada
    from pos_uniformes.services import libreta_local_queue_service as cola

    if str(entrada.get("tipo", "venta")) != "venta" or not entrada.get("descuento_empleada"):
        raise pr.NoSePuede("Solo una venta con descuento de empleada se deja a cuenta.")
    compradora = str(entrada.get("compradora_code") or employee_code).upper()
    if compradora != str(employee_code).upper():
        raise pr.NoSePuede("La compra a cuenta es de quien compra, no de otra empleada.")
    folio = entrada.get("operacion_uuid") or None
    try:
        venta = None
        if folio:
            venta = session.scalars(
                select(LibretaVenta).where(LibretaVenta.operacion_uuid == str(folio)).limit(1)
            ).first()
            if venta is not None:
                ya = session.scalars(
                    select(PrestamoEmpleada).where(PrestamoEmpleada.libreta_venta_id == venta.id,
                                                   PrestamoEmpleada.tipo == pr.TIPO_COMPRA)
                ).first()
                if ya is not None:
                    return ya   # un reintento: ya había quedado todo
        if venta is None:
            venta = cola.registrar_entrada(session, entrada)
        compra = registrar(
            session, employee_code=employee_code, nombre=nombre, monto=venta.monto_total,
            opcion=opcion, quien=creado_por, folio=folio, libreta_venta=venta,
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    from pos_uniformes.services.retiros_service import avisar_retiro

    retiro = session.scalars(select(CajaRetiro).where(CajaRetiro.prestamo_id == compra.id)).first()
    if retiro is not None:
        avisar_retiro(session, retiro)
    return compra


def puede_dejarse_a_cuenta(session, employee_code: str, monto) -> str | None:
    """Revisión justo antes de imprimir (2026-11-12): None si cabe; si no,
    por qué. Así no sale un ticket que diga «a cuenta» que no lo va a ser."""
    disponible = pr.disponible_para(session, employee_code)
    if Decimal(str(monto)).quantize(_CENT) > disponible:
        return f"A cuenta le caben ${disponible:,.2f}: cóbrale al momento."
    return None


def al_aprobar(session, prestamo) -> bool:
    """True si es una compra: su retiro ya salió al venderla, no otro."""
    return es_compra(prestamo)


def al_rechazar(session, prestamo) -> None:
    """Sin autorizar, la compra se paga en caja: se quita su retiro, así el
    corte espera ese dinero. Se encuentra por `prestamo_id` (2026-11-12)."""
    if not es_compra(prestamo):
        return
    from sqlalchemy import select

    from pos_uniformes.database.models import CajaRetiro

    for retiro in session.scalars(select(CajaRetiro).where(CajaRetiro.prestamo_id == prestamo.id)).all():
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
            PrestamoEmpleada.tipo == pr.TIPO_COMPRA,
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
