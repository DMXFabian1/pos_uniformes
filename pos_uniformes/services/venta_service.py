"""Servicios base para ventas, confirmacion y cancelaciones."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from pos_uniformes.database.models import (
    Apartado,
    Cliente,
    EstadoVenta,
    ModoOrigenVenta,
    RolUsuario,
    Usuario,
    Variante,
    Venta,
    VentaDetalle,
)
from pos_uniformes.services.inventario_service import InventarioService
from pos_uniformes.services.loyalty_service import LoyaltyService
from pos_uniformes.services.sale_stock_policy import sale_stock_guard_enabled
from pos_uniformes.utils.product_name import sanitize_product_display_name


@dataclass(frozen=True)
class VentaItemInput:
    sku: str
    cantidad: int
    precio_unitario: Decimal | None = None
    precio_base: Decimal | None = None
    pricing_rule_label: str = ""
    descripcion_snapshot: str | None = None
    is_manual: bool = False


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

        if not sale_stock_guard_enabled():
            return

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
        credit_mode: ModoOrigenVenta = ModoOrigenVenta.UNASSIGNED,
        seller_employee_code: str | None = None,
        seller_employee_display_name: str | None = None,
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
            credit_mode=credit_mode,
            seller_employee_code=(seller_employee_code or None),
            seller_employee_display_name=(seller_employee_display_name or None),
        )

        total = Decimal("0.00")
        cumulative_quantities: dict[str, int] = {}
        variants_by_sku: dict[str, Variante] = {}
        for item in items:
            if item.is_manual:
                continue
            variante = cls.obtener_variante_por_sku(session, item.sku)
            if variante is None:
                raise ValueError(f"No existe una variante activa para el SKU '{item.sku}'.")
            variants_by_sku[item.sku] = variante
            cumulative_quantities[item.sku] = cumulative_quantities.get(item.sku, 0) + int(item.cantidad)

        for sku, quantity in cumulative_quantities.items():
            cls.validar_stock_disponible(variants_by_sku[sku], quantity)

        for item in items:
            if item.is_manual:
                unit_price = Decimal(str(item.precio_unitario or Decimal("0.00"))).quantize(Decimal("0.01"))
                sku_snapshot = str(item.sku or "SIN-CODIGO").strip().upper() or "SIN-CODIGO"
                descripcion_snapshot = str(item.descripcion_snapshot or "Venta manual").strip() or "Venta manual"
                subtotal_linea = (Decimal(item.cantidad) * unit_price).quantize(Decimal("0.01"))
                detalle = VentaDetalle(
                    variante=None,
                    sku_snapshot=sku_snapshot,
                    descripcion_snapshot=descripcion_snapshot,
                    cantidad=item.cantidad,
                    precio_unitario=unit_price,
                    subtotal_linea=subtotal_linea,
                )
            else:
                variante = variants_by_sku[item.sku]
                unit_price = (
                    Decimal(str(item.precio_unitario)).quantize(Decimal("0.01"))
                    if item.precio_unitario is not None
                    else Decimal(variante.precio_venta).quantize(Decimal("0.01"))
                )
                subtotal_linea = (Decimal(item.cantidad) * unit_price).quantize(Decimal("0.01"))
                detalle = VentaDetalle(
                    variante=variante,
                    sku_snapshot=variante.sku,
                    descripcion_snapshot=sanitize_product_display_name(getattr(variante.producto, "nombre", "")),
                    cantidad=item.cantidad,
                    precio_unitario=unit_price,
                    subtotal_linea=subtotal_linea,
                )
            venta.detalles.append(detalle)
            total += subtotal_linea

        venta.subtotal = total
        venta.total = total
        session.add(venta)
        return venta

    @staticmethod
    def confirmar_venta(
        session: Session,
        venta: Venta,
        movement_observacion: str | None = None,
    ) -> Venta:
        VentaService._validar_usuario_venta(venta.usuario)
        if venta.estado != EstadoVenta.BORRADOR:
            raise ValueError("Las ventas confirmadas o canceladas no se pueden editar ni reconfirmar.")

        if not venta.detalles:
            raise ValueError("No se puede confirmar una venta sin detalles.")

        for detalle in venta.detalles:
            if detalle.variante is None:
                continue
            InventarioService.registrar_salida_venta(
                session=session,
                variante=detalle.variante,
                cantidad=detalle.cantidad,
                referencia=venta.folio,
                observacion=movement_observacion,
                creado_por=venta.usuario.username,
            )

        venta.estado = EstadoVenta.CONFIRMADA
        venta.confirmada_at = datetime.now(timezone.utc)
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
            confirmada_at=datetime.now(timezone.utc),
            credit_mode=ModoOrigenVenta.UNASSIGNED,
        )

        total = Decimal("0.00")
        for detalle_apartado in apartado.detalles:
            detalle = VentaDetalle(
                variante=detalle_apartado.variante,
                sku_snapshot=getattr(detalle_apartado.variante, "sku", None),
                descripcion_snapshot=sanitize_product_display_name(getattr(detalle_apartado.variante.producto, "nombre", "")),
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
            if detalle.variante is None:
                continue
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
        venta.cancelada_at = datetime.now(timezone.utc)
        if observacion:
            venta.observacion = observacion

        session.add(venta)
        session.flush()
        LoyaltyService.refresh_client_level_from_sales(
            session,
            venta.cliente,
            actor_user=admin_usuario,
            reason="venta_cancelada",
            reference_time=datetime.now(timezone.utc),
        )
        return venta
