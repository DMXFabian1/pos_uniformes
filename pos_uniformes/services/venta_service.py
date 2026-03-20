"""Servicios base para ventas, confirmacion y cancelaciones."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from pos_uniformes.database.models import Apartado, Cliente, EstadoVenta, RolUsuario, Usuario, Variante, Venta, VentaDetalle
from pos_uniformes.services.inventario_service import InventarioService
from pos_uniformes.services.loyalty_service import LoyaltyService


@dataclass(frozen=True)
class VentaItemInput:
    sku: str
    cantidad: int


class VentaService:
    """Gestiona borradores, confirmacion y cancelaciones de ventas."""

    @staticmethod
    def _validar_usuario_venta(usuario: Usuario) -> None:
        if not usuario.activo:
            raise PermissionError("El usuario no esta activo.")
        if usuario.rol not in {RolUsuario.ADMIN, RolUsuario.CAJERO}:
            raise PermissionError("El usuario no tiene permisos para registrar ventas.")

    @staticmethod
    def obtener_variante_por_sku(session: Session, sku: str) -> Variante | None:
        statement = select(Variante).where(Variante.sku == sku, Variante.activo.is_(True))
        return session.scalar(statement)

    @staticmethod
    def validar_stock_disponible(variante: Variante, cantidad: int) -> None:
        if cantidad <= 0:
            raise ValueError("La cantidad de venta debe ser mayor a cero.")

        if variante.stock_actual < cantidad:
            raise ValueError("Stock insuficiente para confirmar la venta.")

    @classmethod
    def crear_borrador(
        cls,
        session: Session,
        usuario: Usuario,
        folio: str,
        items: list[VentaItemInput],
        observacion: str | None = None,
        cliente: Cliente | None = None,
    ) -> Venta:
        cls._validar_usuario_venta(usuario)
        if not items:
            raise ValueError("La venta debe contener al menos una linea.")

        venta = Venta(
            usuario=usuario,
            cliente=cliente,
            folio=folio,
            observacion=observacion,
            estado=EstadoVenta.BORRADOR,
        )

        total = Decimal("0.00")
        skus: set[str] = set()
        for item in items:
            if item.sku in skus:
                raise ValueError(f"El SKU '{item.sku}' esta repetido en la venta.")
            skus.add(item.sku)

            variante = cls.obtener_variante_por_sku(session, item.sku)
            if variante is None:
                raise ValueError(f"No existe una variante activa para el SKU '{item.sku}'.")

            cls.validar_stock_disponible(variante, item.cantidad)
            subtotal_linea = Decimal(item.cantidad) * variante.precio_venta
            detalle = VentaDetalle(
                variante=variante,
                cantidad=item.cantidad,
                precio_unitario=variante.precio_venta,
                subtotal_linea=subtotal_linea,
            )
            venta.detalles.append(detalle)
            total += subtotal_linea

        venta.subtotal = total
        venta.total = total
        session.add(venta)
        return venta

    @staticmethod
    def confirmar_venta(session: Session, venta: Venta) -> Venta:
        VentaService._validar_usuario_venta(venta.usuario)
        if venta.estado != EstadoVenta.BORRADOR:
            raise ValueError("Las ventas confirmadas o canceladas no se pueden editar ni reconfirmar.")

        if not venta.detalles:
            raise ValueError("No se puede confirmar una venta sin detalles.")

        for detalle in venta.detalles:
            InventarioService.registrar_salida_venta(
                session=session,
                variante=detalle.variante,
                cantidad=detalle.cantidad,
                referencia=venta.folio,
                creado_por=venta.usuario.username,
            )

        venta.estado = EstadoVenta.CONFIRMADA
        venta.confirmada_at = datetime.now()
        session.add(venta)
        session.flush()
        LoyaltyService.refresh_client_level_from_sales(
            session,
            venta.cliente,
            actor_user=venta.usuario,
            reason="venta_confirmada",
            reference_time=venta.confirmada_at,
        )
        return venta

    @staticmethod
    def crear_confirmada_desde_apartado(
        session: Session,
        usuario: Usuario,
        apartado: Apartado,
        folio: str,
        observacion: str | None = None,
    ) -> Venta:
        VentaService._validar_usuario_venta(usuario)
        if not apartado.detalles:
            raise ValueError("No se puede generar una venta desde un apartado sin detalles.")

        venta = Venta(
            usuario=usuario,
            cliente=apartado.cliente,
            folio=folio,
            observacion=observacion,
            estado=EstadoVenta.CONFIRMADA,
            confirmada_at=datetime.now(),
        )

        total = Decimal("0.00")
        for detalle_apartado in apartado.detalles:
            detalle = VentaDetalle(
                variante=detalle_apartado.variante,
                cantidad=detalle_apartado.cantidad,
                precio_unitario=detalle_apartado.precio_unitario,
                subtotal_linea=detalle_apartado.subtotal_linea,
            )
            venta.detalles.append(detalle)
            total += Decimal(detalle_apartado.subtotal_linea)

        venta.subtotal = total
        layaway_total = Decimal(getattr(apartado, "total", total) or total).quantize(Decimal("0.01"))
        venta.total = layaway_total
        rounding_adjustment = (layaway_total - total).quantize(Decimal("0.01"))
        if rounding_adjustment != Decimal("0.00"):
            adjustment_note = f"Ajuste redondeo: {rounding_adjustment}"
            if observacion and observacion.strip():
                venta.observacion = f"{observacion} | {adjustment_note}"
            else:
                venta.observacion = adjustment_note
        session.add(venta)
        session.flush()
        LoyaltyService.refresh_client_level_from_sales(
            session,
            venta.cliente,
            actor_user=usuario,
            reason="venta_confirmada_apartado",
            reference_time=venta.confirmada_at,
        )
        return venta

    @staticmethod
    def cancelar_venta(
        session: Session,
        venta: Venta,
        admin_usuario: Usuario,
        observacion: str | None = None,
    ) -> Venta:
        if not admin_usuario.activo:
            raise PermissionError("El usuario no esta activo.")
        if admin_usuario.rol != RolUsuario.ADMIN:
            raise PermissionError("Solo un usuario ADMIN puede cancelar ventas.")

        if venta.estado != EstadoVenta.CONFIRMADA:
            raise ValueError("Solo se pueden cancelar ventas confirmadas.")

        for detalle in venta.detalles:
            InventarioService.registrar_cancelacion_venta(
                session=session,
                variante=detalle.variante,
                cantidad=detalle.cantidad,
                referencia=venta.folio,
                creado_por=admin_usuario.username,
                observacion=observacion,
            )

        venta.estado = EstadoVenta.CANCELADA
        venta.cancelado_por = admin_usuario
        venta.cancelada_at = datetime.now()
        if observacion:
            venta.observacion = observacion

        session.add(venta)
        session.flush()
        LoyaltyService.refresh_client_level_from_sales(
            session,
            venta.cliente,
            actor_user=admin_usuario,
            reason="venta_cancelada",
            reference_time=datetime.now(),
        )
        return venta
