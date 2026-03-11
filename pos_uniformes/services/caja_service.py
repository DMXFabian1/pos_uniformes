"""Gestion de apertura y corte de caja."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone, time
from decimal import Decimal, InvalidOperation
import re

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session, joinedload

from pos_uniformes.database.models import (
    ApartadoAbono,
    EstadoVenta,
    MovimientoCaja,
    RolUsuario,
    SesionCaja,
    TipoMovimientoCaja,
    Usuario,
    Venta,
)


@dataclass(frozen=True)
class ResumenCaja:
    ventas_efectivo_count: int
    efectivo_ventas: Decimal
    abonos_efectivo_count: int
    efectivo_abonos: Decimal
    reactivo_count: int
    reactivo_total: Decimal
    ingresos_count: int
    ingresos_total: Decimal
    retiros_count: int
    retiros_total: Decimal
    esperado_en_caja: Decimal


class CajaService:
    """Administra la apertura y el corte de caja del equipo."""

    @staticmethod
    def _validate_cash_user(user: Usuario) -> None:
        if not user.activo:
            raise PermissionError("El usuario no esta activo.")
        if user.rol not in {RolUsuario.ADMIN, RolUsuario.CAJERO}:
            raise PermissionError("Este usuario no puede operar la caja.")

    @staticmethod
    def obtener_sesion_activa(session: Session) -> SesionCaja | None:
        return session.scalar(
            select(SesionCaja).where(SesionCaja.cerrada_at.is_(None)).order_by(SesionCaja.abierta_at.desc()).limit(1)
        )

    @staticmethod
    def listar_sesiones(
        session: Session,
        estado: str = "todas",
        fecha_desde: date | None = None,
        fecha_hasta: date | None = None,
    ) -> list[SesionCaja]:
        query = (
            select(SesionCaja)
            .options(
                joinedload(SesionCaja.abierta_por),
                joinedload(SesionCaja.cerrada_por),
                joinedload(SesionCaja.movimientos).joinedload(MovimientoCaja.usuario),
            )
            .order_by(SesionCaja.abierta_at.desc())
        )
        normalized = estado.strip().lower()
        if normalized == "abiertas":
            query = query.where(SesionCaja.cerrada_at.is_(None))
        elif normalized == "cerradas":
            query = query.where(SesionCaja.cerrada_at.is_not(None))
        if fecha_desde is not None or fecha_hasta is not None:
            start_dt = (
                datetime.combine(fecha_desde, time.min)
                if fecha_desde is not None
                else datetime.min
            )
            end_dt = (
                datetime.combine(fecha_hasta, time.max)
                if fecha_hasta is not None
                else datetime.max
            )
            query = query.where(
                or_(
                    and_(SesionCaja.abierta_at >= start_dt, SesionCaja.abierta_at <= end_dt),
                    and_(
                        SesionCaja.cerrada_at.is_not(None),
                        SesionCaja.cerrada_at >= start_dt,
                        SesionCaja.cerrada_at <= end_dt,
                    ),
                )
            )
        return session.scalars(query).all()

    @staticmethod
    def obtener_ultimo_reactivo_sugerido(session: Session) -> Decimal | None:
        last_session = session.scalar(
            select(SesionCaja).order_by(SesionCaja.abierta_at.desc()).limit(1)
        )
        if last_session is None:
            return None
        if last_session.monto_cierre_declarado is not None:
            return Decimal(last_session.monto_cierre_declarado).quantize(Decimal("0.01"))
        return Decimal(last_session.monto_apertura).quantize(Decimal("0.01"))

    @classmethod
    def abrir_sesion(
        cls,
        session: Session,
        usuario: Usuario,
        monto_apertura: Decimal,
        observacion: str | None = None,
    ) -> SesionCaja:
        cls._validate_cash_user(usuario)
        if monto_apertura < Decimal("0.00"):
            raise ValueError("El monto de apertura no puede ser negativo.")
        active = cls.obtener_sesion_activa(session)
        if active is not None:
            raise ValueError("Ya existe una caja abierta. Debes cerrarla antes de abrir otra.")

        cash_session = SesionCaja(
            abierta_por=usuario,
            monto_apertura=monto_apertura.quantize(Decimal("0.01")),
            observacion_apertura=observacion.strip() if observacion else None,
        )
        session.add(cash_session)
        session.flush()
        return cash_session

    @classmethod
    def corregir_apertura(
        cls,
        session: Session,
        cash_session: SesionCaja,
        usuario: Usuario,
        nuevo_monto_apertura: Decimal,
        observacion: str | None = None,
    ) -> SesionCaja:
        cls._validate_cash_user(usuario)
        if cash_session.cerrada_at is not None:
            raise ValueError("La caja seleccionada ya esta cerrada.")
        if nuevo_monto_apertura < Decimal("0.00"):
            raise ValueError("El reactivo inicial no puede ser negativo.")

        monto_anterior = Decimal(cash_session.monto_apertura).quantize(Decimal("0.01"))
        monto_nuevo = nuevo_monto_apertura.quantize(Decimal("0.01"))
        if monto_anterior == monto_nuevo:
            raise ValueError("El reactivo inicial ya tiene ese valor.")

        marca_tiempo = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M")
        nota_correccion = (
            f"Correccion de apertura {marca_tiempo} por {usuario.nombre_completo}: "
            f"${monto_anterior} -> ${monto_nuevo}"
        )
        if observacion:
            nota_correccion = f"{nota_correccion}. Motivo: {observacion.strip()}"

        cash_session.monto_apertura = monto_nuevo
        notas_previas = [cash_session.observacion_apertura.strip()] if cash_session.observacion_apertura else []
        notas_previas.append(nota_correccion)
        cash_session.observacion_apertura = " | ".join(filter(None, notas_previas))
        session.flush()
        return cash_session

    @staticmethod
    def _extract_note_value(observacion: str, prefix: str) -> Decimal | None:
        for part in observacion.split("|"):
            token = part.strip()
            if token.startswith(prefix):
                raw = token.replace(prefix, "", 1).strip().replace("$", "")
                try:
                    return Decimal(raw).quantize(Decimal("0.01"))
                except (InvalidOperation, ValueError):
                    return None
        return None

    @classmethod
    def registrar_movimiento(
        cls,
        session: Session,
        cash_session: SesionCaja,
        usuario: Usuario,
        tipo: TipoMovimientoCaja,
        monto: Decimal,
        concepto: str | None = None,
    ) -> MovimientoCaja:
        cls._validate_cash_user(usuario)
        if cash_session.cerrada_at is not None:
            raise ValueError("La caja seleccionada ya esta cerrada.")
        if tipo == TipoMovimientoCaja.REACTIVO:
            if monto == Decimal("0.00"):
                raise ValueError("El ajuste de reactivo no puede ser cero.")
        elif monto <= Decimal("0.00"):
            raise ValueError("El monto del movimiento debe ser mayor a cero.")
        movement = MovimientoCaja(
            sesion_caja=cash_session,
            usuario=usuario,
            tipo=tipo,
            monto=monto.quantize(Decimal("0.01")),
            concepto=concepto.strip() if concepto else None,
        )
        session.add(movement)
        session.flush()
        return movement

    @classmethod
    def _cash_amount_for_sale(cls, sale: Venta) -> Decimal:
        observacion = sale.observacion or ""
        metodo = ""
        match = re.search(r"Metodo de pago:\s*([^|]+)", observacion)
        if match:
            metodo = match.group(1).strip()
        total = Decimal(sale.total).quantize(Decimal("0.01"))
        if metodo == "Efectivo":
            return total
        if metodo == "Mixto":
            transferencia = cls._extract_note_value(observacion, "Transferencia:")
            if transferencia is None:
                return Decimal("0.00")
            cash_amount = total - transferencia
            if cash_amount < Decimal("0.00"):
                return Decimal("0.00")
            return cash_amount.quantize(Decimal("0.01"))
        return Decimal("0.00")

    @classmethod
    def resumir_sesion(cls, session: Session, cash_session: SesionCaja) -> ResumenCaja:
        start = cash_session.abierta_at
        end = cash_session.cerrada_at or datetime.now(tz=start.tzinfo if start else None)
        sales = session.scalars(
            select(Venta).where(
                Venta.estado == EstadoVenta.CONFIRMADA,
                Venta.created_at >= start,
                Venta.created_at <= end,
            )
        ).all()
        efectivo_total = Decimal("0.00")
        ventas_count = 0
        for sale in sales:
            cash_amount = cls._cash_amount_for_sale(sale)
            if cash_amount > Decimal("0.00"):
                ventas_count += 1
                efectivo_total += cash_amount
        payments = session.scalars(
            select(ApartadoAbono).where(
                ApartadoAbono.created_at >= start,
                ApartadoAbono.created_at <= end,
            )
        ).all()
        abonos_efectivo_total = Decimal("0.00")
        abonos_count = 0
        for payment in payments:
            cash_amount = (
                Decimal(payment.monto_efectivo).quantize(Decimal("0.01"))
                if payment.monto_efectivo is not None
                else Decimal(payment.monto).quantize(Decimal("0.01"))
            )
            if cash_amount > Decimal("0.00"):
                abonos_count += 1
                abonos_efectivo_total += cash_amount

        movements = session.scalars(
            select(MovimientoCaja).where(
                MovimientoCaja.sesion_caja_id == cash_session.id,
                MovimientoCaja.created_at >= start,
                MovimientoCaja.created_at <= end,
            )
        ).all()
        reactivo_total = Decimal("0.00")
        ingresos_total = Decimal("0.00")
        retiros_total = Decimal("0.00")
        reactivo_count = 0
        ingresos_count = 0
        retiros_count = 0
        for movement in movements:
            amount = Decimal(movement.monto).quantize(Decimal("0.01"))
            if movement.tipo == TipoMovimientoCaja.REACTIVO:
                reactivo_count += 1
                reactivo_total += amount
            elif movement.tipo == TipoMovimientoCaja.INGRESO:
                ingresos_count += 1
                ingresos_total += amount
            elif movement.tipo == TipoMovimientoCaja.RETIRO:
                retiros_count += 1
                retiros_total += amount

        esperado = (
            Decimal(cash_session.monto_apertura).quantize(Decimal("0.01"))
            + reactivo_total
            + ingresos_total
            + efectivo_total
            + abonos_efectivo_total
            - retiros_total
        )
        return ResumenCaja(
            ventas_efectivo_count=ventas_count,
            efectivo_ventas=efectivo_total.quantize(Decimal("0.01")),
            abonos_efectivo_count=abonos_count,
            efectivo_abonos=abonos_efectivo_total.quantize(Decimal("0.01")),
            reactivo_count=reactivo_count,
            reactivo_total=reactivo_total.quantize(Decimal("0.01")),
            ingresos_count=ingresos_count,
            ingresos_total=ingresos_total.quantize(Decimal("0.01")),
            retiros_count=retiros_count,
            retiros_total=retiros_total.quantize(Decimal("0.01")),
            esperado_en_caja=esperado.quantize(Decimal("0.01")),
        )

    @classmethod
    def cerrar_sesion(
        cls,
        session: Session,
        cash_session: SesionCaja,
        usuario: Usuario,
        monto_contado: Decimal,
        observacion: str | None = None,
    ) -> SesionCaja:
        cls._validate_cash_user(usuario)
        if cash_session.cerrada_at is not None:
            raise ValueError("La caja seleccionada ya esta cerrada.")
        if monto_contado < Decimal("0.00"):
            raise ValueError("El monto contado no puede ser negativo.")

        resumen = cls.resumir_sesion(session, cash_session)
        cash_session.cerrada_por = usuario
        cash_session.cerrada_at = datetime.now(tz=cash_session.abierta_at.tzinfo if cash_session.abierta_at else None)
        cash_session.monto_cierre_declarado = monto_contado.quantize(Decimal("0.01"))
        cash_session.monto_esperado_cierre = resumen.esperado_en_caja
        cash_session.diferencia_cierre = (monto_contado - resumen.esperado_en_caja).quantize(Decimal("0.01"))
        cash_session.observacion_cierre = observacion.strip() if observacion else None
        session.add(cash_session)
        return cash_session
