"""Retiros del cajón con motivo (lo que no es pago a empleada).

Solo el dueño (VEND-1) y el encargado (ENC-1). Se fechan al momento; el
corte del periodo los descuenta del esperado y el ticket los lista.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select

MOTIVOS_RAPIDOS = ("Proveedor", "Renta", "Cambio", "Comida", "Luz / agua", "Otro")
_CENT = Decimal("0.01")


def registrar_retiro(
    session,
    *,
    monto,
    motivo: str,
    creado_por: str,
    revisar_repetido: bool = True,
    prestamo_id: int | None = None,
    commit: bool = True,
):
    """`revisar_repetido=False`: quien llama ya sabe que no es un doble envío
    (aprobar un préstamo: cada uno tiene su id y solo se aprueba una vez). Dos
    préstamos iguales de la misma empleada en dos minutos contestaban «Falló:
    Ese retiro ya quedó apuntado» (auditoría 2026-11-07, #14).

    `prestamo_id` (2026-11-12): el préstamo que sacó este dinero; liga el
    retiro por columna y no por el texto del motivo.

    `commit=False` (2026-11-12): solo hace flush y NO encola el aviso (el
    aviso hace su propio commit): quien llama guarda todo junto y avisa
    después. Por default, como siempre: commit y aviso."""
    from pos_uniformes.database.models import CajaRetiro
    from pos_uniformes.services.nomina_service import puede_pagar

    if not puede_pagar(creado_por):
        raise PermissionError("Solo el dueño o el encargado apuntan retiros.")
    monto = Decimal(str(monto)).quantize(_CENT)
    if monto <= 0:
        raise ValueError("El monto debe ser mayor a cero.")
    motivo = (motivo or "").strip()[:120]
    if not motivo:
        raise ValueError("Escribe para qué fue el dinero.")
    # El mismo retiro (monto y motivo) dos veces en dos minutos es un doble
    # envío —Telegram reentregando, dos toques— y no dos retiros. Desde el
    # celular no hay confirmación, así que esta es la red (2026-10-10).
    from datetime import timedelta

    from sqlalchemy import select

    hace_poco = datetime.now().astimezone() - timedelta(minutes=2)
    repetido = None if not revisar_repetido else session.scalars(
        select(CajaRetiro).where(
            CajaRetiro.monto == monto,
            CajaRetiro.motivo == motivo,
            CajaRetiro.created_at >= hace_poco,
        ).limit(1)
    ).first()
    if repetido is not None:
        raise ValueError(
            f"Ese retiro (${monto:,.2f} para {motivo}) ya quedó apuntado hace un momento. "
            "Si de verdad son dos, espera dos minutos o cambia el motivo."
        )
    retiro = _nuevo_retiro(session, monto=monto, motivo=motivo, creado_por=creado_por, prestamo_id=prestamo_id)
    if not commit:
        return retiro
    session.commit()
    avisar_retiro(session, retiro)
    return retiro


def _nuevo_retiro(session, *, monto: Decimal, motivo: str, creado_por: str, prestamo_id: int | None):
    from pos_uniformes.database.models import CajaRetiro

    retiro = CajaRetiro(
        monto=monto,
        motivo=motivo,
        creado_por=str(creado_por).strip().upper(),
        created_at=datetime.now().astimezone(),
        prestamo_id=prestamo_id,
    )
    session.add(retiro)
    session.flush()
    return retiro


def avisar_retiro(session, retiro) -> None:
    """«💸 Retiro del cajón…» a la cola de Telegram. Hace su propio commit:
    se llama DESPUÉS de guardar el retiro."""
    try:
        from pos_uniformes.services.alertas_service import encolar, texto_alerta_retiro

        encolar(session, texto_alerta_retiro(retiro))
    except Exception:  # noqa: BLE001 — el retiro ya quedó guardado
        pass


def registrar_retiro_de_compra_a_cuenta(session, prestamo, *, creado_por: str):
    """El retiro de una compra a cuenta, apuntado desde el kiosko (2026-11-12).

    Es el permiso explícito de la compra a cuenta: antes el kiosko pasaba el
    código del dueño para brincar `puede_pagar`. Aquí quien lo apunta es el
    código real (la empleada o el kiosko), y solo se acepta para una compra a
    cuenta recién pedida que todavía no tiene retiro, por su mismo monto. No
    abre `registrar_retiro` a nadie más. Sin commit: va en la transacción de
    la compra."""
    from pos_uniformes.database.models import CajaRetiro
    from pos_uniformes.services import prestamos_service as pr

    code = str(creado_por or "").strip().upper()
    if not code:
        raise PermissionError("Hay que entrar con el gafete para dejar una compra a cuenta.")
    if getattr(prestamo, "id", None) is None or getattr(prestamo, "tipo", None) != pr.TIPO_COMPRA:
        raise PermissionError("Ese retiro solo se apunta para una compra a cuenta.")
    if prestamo.estado != pr.PEDIDO:
        raise PermissionError(f"Esa compra a cuenta ya está {prestamo.estado}.")
    ya = session.scalar(select(CajaRetiro.id).where(CajaRetiro.prestamo_id == prestamo.id).limit(1))
    if ya is not None:
        raise ValueError("Esa compra a cuenta ya tiene su retiro.")
    from pos_uniformes.services.compra_a_cuenta_service import motivo_retiro

    return _nuevo_retiro(
        session,
        monto=Decimal(str(prestamo.monto)).quantize(_CENT),
        motivo=motivo_retiro(prestamo),
        creado_por=code,
        prestamo_id=prestamo.id,
    )


def registrar_gasto(session, *, monto, motivo: str, employee_code: str):
    """Un gasto de la tienda apuntado por una empleada (no por el dueño).

    Es el mismo retiro del cajón de siempre —el corte lo cuenta en «Gastos»—,
    pero quien lo apunta no tiene que ser dueño ni encargado: es dinero que ya
    salió, y lo que importa es que quede escrito en el momento, no que alguien
    lo autorice después (Daniel, 2026-10-01: "un gasto relacionado a la
    tienda, no de ellas").

    A Daniel le llega el aviso al instante con el nombre de quien lo apuntó;
    si estuvo mal, se borra con `eliminar_retiro`.
    """
    from pos_uniformes.database.models import CajaRetiro

    code = str(employee_code or "").strip().upper()
    if not code:
        raise PermissionError("Hay que entrar con el gafete para apuntar un gasto.")
    monto = Decimal(str(monto)).quantize(_CENT)
    if monto <= 0:
        raise ValueError("El monto debe ser mayor a cero.")
    motivo = (motivo or "").strip()[:120]
    if not motivo:
        raise ValueError("Escribe en qué se gastó.")

    retiro = CajaRetiro(
        monto=monto,
        motivo=motivo,
        creado_por=code,
        created_at=datetime.now().astimezone(),
    )
    session.add(retiro)
    session.commit()
    try:
        from pos_uniformes.services.alertas_service import encolar
        from pos_uniformes.services.nombres_empleadas_service import mostrar

        encolar(
            session,
            f"🧾 Gasto de la tienda: ${monto:,.2f} — {motivo}\n"
            f"Lo apuntó {mostrar(code)}. Si estuvo mal, bórralo desde el corte.",
        )
    except Exception:  # noqa: BLE001 — el gasto ya quedó guardado
        pass
    return retiro


def _no_es_compra_a_cuenta(CajaRetiro):
    """El retiro de una compra a cuenta no es dinero que salió: no va al corte.

    (Daniel, 2026-11-12: «en el corte no quiero que aparezcan las compras a
    cuenta ni que se descuenten de la venta».) Su venta también sale del
    corte (`corte_caja_service.operaciones_del_periodo`): las dos se
    cancelaban, así que el esperado no cambia.

    Por columna (2026-11-12): sale SOLO el retiro cuyo `prestamo_id` es una
    compra a cuenta no rechazada Y ligada a su venta (`libreta_venta_id`):
    es la misma condición con la que `sin_compras_a_cuenta` quita la venta,
    así que nunca sale uno sin el otro. Antes era `motivo LIKE 'Compra a
    cuenta%'`: un retiro manual «Compra a cuenta de bolsas» desaparecía del
    corte, y una compra sin folio sacaba su retiro pero no su venta."""
    from sqlalchemy import or_

    from pos_uniformes.database.models import PrestamoEmpleada
    from pos_uniformes.services import prestamos_service as pr

    compras = select(PrestamoEmpleada.id).where(
        PrestamoEmpleada.tipo == pr.TIPO_COMPRA,
        PrestamoEmpleada.estado != pr.RECHAZADO,
        PrestamoEmpleada.libreta_venta_id.is_not(None),
    )
    return or_(CajaRetiro.prestamo_id.is_(None), ~CajaRetiro.prestamo_id.in_(compras))


def retiros_del_periodo(session, desde: datetime | None, hasta: datetime, *, solo_en_cajon: bool = True) -> list:
    from pos_uniformes.database.models import CajaRetiro

    stmt = select(CajaRetiro).where(CajaRetiro.created_at <= hasta, _no_es_compra_a_cuenta(CajaRetiro))
    if solo_en_cajon:
        stmt = stmt.where(CajaRetiro.en_cajon.is_(True))
    if desde is not None:
        stmt = stmt.where(CajaRetiro.created_at > desde)
    return list(session.scalars(stmt.order_by(CajaRetiro.id)).all())


def total_retiros(session, desde: datetime | None, hasta: datetime) -> Decimal:
    from pos_uniformes.database.models import CajaRetiro

    stmt = select(func.coalesce(func.sum(CajaRetiro.monto), 0)).where(
        CajaRetiro.created_at <= hasta, CajaRetiro.en_cajon.is_(True), _no_es_compra_a_cuenta(CajaRetiro)
    )
    if desde is not None:
        stmt = stmt.where(CajaRetiro.created_at > desde)
    return Decimal(str(session.scalar(stmt) or 0)).quantize(_CENT)


def eliminar_retiro(session, retiro_id: int, *, creado_por: str) -> bool:
    """Para el "me equivoqué": borra un retiro recién apuntado."""
    from pos_uniformes.database.models import CajaRetiro
    from pos_uniformes.services.nomina_service import puede_pagar

    if not puede_pagar(creado_por):
        raise PermissionError("Solo el dueño o el encargado.")
    retiro = session.get(CajaRetiro, int(retiro_id))
    if retiro is None:
        return False
    session.delete(retiro)
    session.commit()
    return True
