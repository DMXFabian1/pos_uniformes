"""Reglas de negocio para apartados y abonos."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import desc, select
from sqlalchemy.orm import Session, joinedload

from pos_uniformes.database.models import (
    Apartado,
    ApartadoAbono,
    ApartadoDetalle,
    Cliente,
    EstadoApartado,
    RolUsuario,
    Usuario,
    Variante,
)
from pos_uniformes.services.inventario_service import InventarioService
from pos_uniformes.services.layaway_pricing_service import (
    resolve_layaway_client_discount_percent,
    resolve_layaway_min_deposit,
    resolve_layaway_unit_price,
)


@dataclass(frozen=True)
class ApartadoItemInput:
    sku: str
    cantidad: int


class ApartadoService:
    """Crea, abona, entrega y cancela apartados con reserva de stock."""

    @staticmethod
    def _validar_operador(usuario: Usuario) -> None:
        if not usuario.activo:
            raise PermissionError("El usuario no esta activo.")
        if usuario.rol not in {RolUsuario.ADMIN, RolUsuario.CAJERO}:
            raise PermissionError("El usuario no puede gestionar apartados.")

    @staticmethod
    def _validar_admin(usuario: Usuario) -> None:
        ApartadoService._validar_operador(usuario)
        if usuario.rol != RolUsuario.ADMIN:
            raise PermissionError("Solo ADMIN puede cancelar apartados.")

    @staticmethod
    def obtener_variante_por_sku(session: Session, sku: str) -> Variante | None:
        statement = select(Variante).where(Variante.sku == sku, Variante.activo.is_(True))
        return session.scalar(statement)

    @staticmethod
    def _recalcular_estado(apartado: Apartado) -> None:
        if apartado.estado == EstadoApartado.CANCELADO:
            return
        if apartado.estado == EstadoApartado.ENTREGADO:
            return
        if apartado.saldo_pendiente <= Decimal("0.00"):
            apartado.saldo_pendiente = Decimal("0.00")
            apartado.estado = EstadoApartado.LIQUIDADO
            if apartado.liquidado_at is None:
                apartado.liquidado_at = datetime.now()
        else:
            apartado.estado = EstadoApartado.ACTIVO
            apartado.liquidado_at = None

    @classmethod
    def crear_apartado(
        cls,
        session: Session,
        usuario: Usuario,
        folio: str,
        cliente_nombre: str,
        cliente_telefono: str | None,
        items: list[ApartadoItemInput],
        anticipo: Decimal,
        fecha_compromiso: datetime | None = None,
        observacion: str | None = None,
        cliente: Cliente | None = None,
    ) -> Apartado:
        cls._validar_operador(usuario)
        if not cliente_nombre.strip():
            raise ValueError("Debes capturar el nombre del cliente.")
        if not items:
            raise ValueError("El apartado debe contener al menos una presentacion.")
        if anticipo <= Decimal("0.00"):
            raise ValueError("El apartado debe iniciar con un anticipo mayor a cero.")

        apartado = Apartado(
            usuario=usuario,
            cliente=cliente,
            folio=folio.strip(),
            cliente_nombre=cliente_nombre.strip(),
            cliente_telefono=(cliente_telefono or "").strip() or None,
            fecha_compromiso=fecha_compromiso,
            observacion=observacion,
            estado=EstadoApartado.ACTIVO,
        )

        total = Decimal("0.00")
        seen_skus: set[str] = set()
        client_discount_percent = resolve_layaway_client_discount_percent(
            session,
            selected_client_id=getattr(cliente, "id", None),
        )
        for item in items:
            sku = item.sku.strip().upper()
            if not sku:
                raise ValueError("Cada linea del apartado necesita SKU.")
            if sku in seen_skus:
                raise ValueError(f"El SKU '{sku}' esta repetido en el apartado.")
            seen_skus.add(sku)
            if item.cantidad <= 0:
                raise ValueError("La cantidad debe ser mayor a cero.")

            variante = cls.obtener_variante_por_sku(session, sku)
            if variante is None:
                raise ValueError(f"No existe una presentacion activa para el SKU '{sku}'.")

            InventarioService.validar_stock_disponible(variante, item.cantidad)
            precio_unitario = resolve_layaway_unit_price(
                variante.precio_venta,
                discount_percent=client_discount_percent,
            )
            subtotal_linea = Decimal(item.cantidad) * precio_unitario
            detalle = ApartadoDetalle(
                variante=variante,
                cantidad=item.cantidad,
                precio_unitario=precio_unitario,
                subtotal_linea=subtotal_linea,
            )
            apartado.detalles.append(detalle)
            total += subtotal_linea

        minimum_deposit = resolve_layaway_min_deposit(total)
        if anticipo < minimum_deposit:
            raise ValueError(
                f"El anticipo minimo para este apartado es ${minimum_deposit} (20% del total)."
            )
        if anticipo > total:
            raise ValueError("El anticipo no puede ser mayor al total del apartado.")

        apartado.subtotal = total
        apartado.total = total
        apartado.total_abonado = anticipo
        apartado.saldo_pendiente = total - anticipo

        session.add(apartado)
        session.flush()

        for detalle in apartado.detalles:
            InventarioService.registrar_reserva_apartado(
                session=session,
                variante=detalle.variante,
                cantidad=detalle.cantidad,
                referencia=apartado.folio,
                observacion=f"Apartado para {apartado.cliente_nombre}",
                creado_por=usuario.username,
            )

        if anticipo > Decimal("0.00"):
            session.add(
                ApartadoAbono(
                    apartado=apartado,
                    usuario=usuario,
                    monto=anticipo,
                    referencia="ANTICIPO",
                    observacion="Anticipo inicial del apartado.",
                )
            )

        cls._recalcular_estado(apartado)
        session.add(apartado)
        return apartado

    @classmethod
    def registrar_abono(
        cls,
        session: Session,
        apartado: Apartado,
        usuario: Usuario,
        monto: Decimal,
        metodo_pago: str = "Efectivo",
        monto_efectivo: Decimal | None = None,
        referencia: str | None = None,
        observacion: str | None = None,
    ) -> ApartadoAbono:
        cls._validar_operador(usuario)
        if apartado.estado in {EstadoApartado.CANCELADO, EstadoApartado.ENTREGADO}:
            raise ValueError("No puedes registrar abonos sobre un apartado cerrado.")
        if monto <= Decimal("0.00"):
            raise ValueError("El abono debe ser mayor a cero.")
        if monto > apartado.saldo_pendiente:
            raise ValueError("El abono no puede ser mayor al saldo pendiente.")
        metodo_pago_normalizado = metodo_pago.strip() or "Efectivo"
        if metodo_pago_normalizado not in {"Efectivo", "Transferencia", "Mixto"}:
            raise ValueError("Metodo de pago no valido para el abono.")

        if monto_efectivo is None:
            efectivo_real = monto if metodo_pago_normalizado == "Efectivo" else Decimal("0.00")
        else:
            efectivo_real = Decimal(monto_efectivo)
        if efectivo_real < Decimal("0.00"):
            raise ValueError("El efectivo del abono no puede ser negativo.")
        if metodo_pago_normalizado == "Efectivo" and efectivo_real != monto:
            raise ValueError("En abonos en efectivo, el monto en caja debe coincidir con el abono.")
        if metodo_pago_normalizado == "Transferencia" and efectivo_real != Decimal("0.00"):
            raise ValueError("En abonos por transferencia, el efectivo en caja debe ser cero.")
        if metodo_pago_normalizado == "Mixto" and efectivo_real > monto:
            raise ValueError("En abonos mixtos, el efectivo en caja no puede exceder el abono total.")

        abono = ApartadoAbono(
            apartado=apartado,
            usuario=usuario,
            monto=monto,
            metodo_pago=metodo_pago_normalizado,
            monto_efectivo=efectivo_real.quantize(Decimal("0.01")),
            referencia=(referencia or "").strip() or None,
            observacion=(observacion or "").strip() or None,
        )
        apartado.total_abonado = Decimal(apartado.total_abonado) + monto
        apartado.saldo_pendiente = Decimal(apartado.total) - Decimal(apartado.total_abonado)
        cls._recalcular_estado(apartado)
        session.add(abono)
        session.add(apartado)
        return abono

    @classmethod
    def entregar_apartado(cls, session: Session, apartado: Apartado, usuario: Usuario) -> Apartado:
        cls._validar_operador(usuario)
        if apartado.estado == EstadoApartado.CANCELADO:
            raise ValueError("No puedes entregar un apartado cancelado.")
        if apartado.estado == EstadoApartado.ENTREGADO:
            raise ValueError("El apartado ya fue entregado.")
        if apartado.saldo_pendiente > Decimal("0.00"):
            raise ValueError("No puedes entregar un apartado con saldo pendiente.")

        apartado.estado = EstadoApartado.ENTREGADO
        apartado.entregado_por = usuario
        apartado.entregado_at = datetime.now()
        session.add(apartado)
        return apartado

    @classmethod
    def cancelar_apartado(
        cls,
        session: Session,
        apartado: Apartado,
        usuario: Usuario,
        observacion: str | None = None,
    ) -> Apartado:
        cls._validar_admin(usuario)
        if apartado.estado == EstadoApartado.CANCELADO:
            raise ValueError("El apartado ya esta cancelado.")
        if apartado.estado == EstadoApartado.ENTREGADO:
            raise ValueError("No puedes cancelar un apartado ya entregado.")

        for detalle in apartado.detalles:
            InventarioService.registrar_liberacion_apartado(
                session=session,
                variante=detalle.variante,
                cantidad=detalle.cantidad,
                referencia=apartado.folio,
                observacion=(observacion or "").strip() or f"Cancelacion de apartado {apartado.folio}",
                creado_por=usuario.username,
            )

        apartado.estado = EstadoApartado.CANCELADO
        apartado.cancelado_por = usuario
        apartado.cancelado_at = datetime.now()
        if observacion:
            apartado.observacion = observacion
        session.add(apartado)
        return apartado

    @staticmethod
    def listar_apartados(session: Session) -> list[Apartado]:
        statement = (
            select(Apartado)
            .options(
                joinedload(Apartado.usuario),
                joinedload(Apartado.cliente),
                joinedload(Apartado.detalles).joinedload(ApartadoDetalle.variante).joinedload(Variante.producto),
                joinedload(Apartado.abonos).joinedload(ApartadoAbono.usuario),
            )
            .order_by(desc(Apartado.created_at))
        )
        return list(session.scalars(statement).unique())

    @staticmethod
    def obtener_apartado(session: Session, apartado_id: int) -> Apartado | None:
        statement = (
            select(Apartado)
            .where(Apartado.id == apartado_id)
            .options(
                joinedload(Apartado.usuario),
                joinedload(Apartado.cliente),
                joinedload(Apartado.detalles).joinedload(ApartadoDetalle.variante).joinedload(Variante.producto),
                joinedload(Apartado.abonos).joinedload(ApartadoAbono.usuario),
            )
        )
        return session.scalar(statement)
