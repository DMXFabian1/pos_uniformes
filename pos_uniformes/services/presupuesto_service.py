"""Reglas de negocio para presupuestos/cotizaciones."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import desc, select
from sqlalchemy.orm import Session, joinedload

from pos_uniformes.database.models import (
    Cliente,
    EstadoPresupuesto,
    Presupuesto,
    PresupuestoDetalle,
    RolUsuario,
    Usuario,
    Variante,
)


@dataclass(frozen=True)
class PresupuestoItemInput:
    sku: str
    cantidad: int


class PresupuestoService:
    """Gestiona presupuestos sin afectar inventario ni ventas."""

    @staticmethod
    def _validar_operador(usuario: Usuario) -> None:
        if not usuario.activo:
            raise PermissionError("El usuario no esta activo.")
        if usuario.rol not in {RolUsuario.ADMIN, RolUsuario.CAJERO}:
            raise PermissionError("El usuario no puede gestionar presupuestos.")

    @staticmethod
    def obtener_variante_por_sku(session: Session, sku: str) -> Variante | None:
        statement = select(Variante).where(Variante.sku == sku, Variante.activo.is_(True))
        return session.scalar(statement)

    @staticmethod
    def _money(value: Decimal | str | float | int) -> Decimal:
        return Decimal(str(value)).quantize(Decimal("0.01"))

    @classmethod
    def _build_quote_details(
        cls,
        session: Session,
        *,
        items: list[PresupuestoItemInput],
    ) -> tuple[list[PresupuestoDetalle], Decimal]:
        if not items:
            raise ValueError("El presupuesto debe contener al menos una linea.")

        total = Decimal("0.00")
        skus: set[str] = set()
        detail_rows: list[PresupuestoDetalle] = []
        for item in items:
            sku = item.sku.strip().upper()
            if not sku:
                raise ValueError("Cada linea del presupuesto necesita SKU.")
            if sku in skus:
                raise ValueError(f"El SKU '{sku}' esta repetido en el presupuesto.")
            if item.cantidad <= 0:
                raise ValueError("La cantidad debe ser mayor a cero.")
            skus.add(sku)

            variante = cls.obtener_variante_por_sku(session, sku)
            if variante is None:
                raise ValueError(f"No existe una presentacion activa para el SKU '{sku}'.")

            precio_unitario = cls._money(variante.precio_venta)
            subtotal_linea = (precio_unitario * Decimal(item.cantidad)).quantize(Decimal("0.01"))
            detail_rows.append(
                PresupuestoDetalle(
                    variante=variante,
                    sku_snapshot=variante.sku,
                    descripcion_snapshot=variante.producto.nombre_base,
                    talla_snapshot=variante.talla,
                    color_snapshot=variante.color,
                    precio_unitario=precio_unitario,
                    cantidad=item.cantidad,
                    subtotal_linea=subtotal_linea,
                )
            )
            total += subtotal_linea

        return detail_rows, total

    @classmethod
    def _apply_quote_payload(
        cls,
        session: Session,
        presupuesto: Presupuesto,
        *,
        folio: str,
        items: list[PresupuestoItemInput],
        cliente: Cliente | None = None,
        cliente_nombre: str | None = None,
        cliente_telefono: str | None = None,
        vigencia_hasta: datetime | None = None,
        observacion: str | None = None,
        estado: EstadoPresupuesto,
    ) -> Presupuesto:
        normalized_folio = folio.strip()
        if not normalized_folio:
            raise ValueError("El folio del presupuesto no puede estar vacio.")

        detail_rows, total = cls._build_quote_details(session, items=items)

        presupuesto.folio = normalized_folio
        presupuesto.cliente = cliente
        presupuesto.cliente_nombre = (cliente_nombre or "").strip() or (cliente.nombre if cliente is not None else None)
        presupuesto.cliente_telefono = (
            (cliente_telefono or "").strip() or (cliente.telefono if cliente is not None else None)
        )
        presupuesto.vigencia_hasta = vigencia_hasta
        presupuesto.observacion = (observacion or "").strip() or None
        presupuesto.estado = estado
        if estado == EstadoPresupuesto.EMITIDO and presupuesto.emitido_at is None:
            presupuesto.emitido_at = datetime.now()
        if estado == EstadoPresupuesto.BORRADOR:
            presupuesto.emitido_at = None

        presupuesto.detalles.clear()
        presupuesto.detalles.extend(detail_rows)
        presupuesto.subtotal = total
        presupuesto.total = total
        session.add(presupuesto)
        return presupuesto

    @classmethod
    def crear_presupuesto(
        cls,
        session: Session,
        usuario: Usuario,
        *,
        folio: str,
        items: list[PresupuestoItemInput],
        cliente: Cliente | None = None,
        cliente_nombre: str | None = None,
        cliente_telefono: str | None = None,
        vigencia_hasta: datetime | None = None,
        observacion: str | None = None,
        estado: EstadoPresupuesto = EstadoPresupuesto.EMITIDO,
    ) -> Presupuesto:
        cls._validar_operador(usuario)
        presupuesto = Presupuesto(
            usuario=usuario,
        )
        return cls._apply_quote_payload(
            session,
            presupuesto,
            folio=folio,
            items=items,
            cliente=cliente,
            cliente_nombre=cliente_nombre,
            cliente_telefono=cliente_telefono,
            vigencia_hasta=vigencia_hasta,
            observacion=observacion,
            estado=estado,
        )

    @classmethod
    def actualizar_presupuesto(
        cls,
        session: Session,
        presupuesto: Presupuesto,
        usuario: Usuario,
        *,
        folio: str,
        items: list[PresupuestoItemInput],
        cliente: Cliente | None = None,
        cliente_nombre: str | None = None,
        cliente_telefono: str | None = None,
        vigencia_hasta: datetime | None = None,
        observacion: str | None = None,
        estado: EstadoPresupuesto = EstadoPresupuesto.BORRADOR,
    ) -> Presupuesto:
        cls._validar_operador(usuario)
        if presupuesto.estado != EstadoPresupuesto.BORRADOR:
            raise ValueError("Solo se pueden editar presupuestos en borrador.")
        if estado not in {EstadoPresupuesto.BORRADOR, EstadoPresupuesto.EMITIDO}:
            raise ValueError("La actualizacion solo soporta borrador o emitido.")

        return cls._apply_quote_payload(
            session,
            presupuesto,
            folio=folio,
            items=items,
            cliente=cliente,
            cliente_nombre=cliente_nombre,
            cliente_telefono=cliente_telefono,
            vigencia_hasta=vigencia_hasta,
            observacion=observacion,
            estado=estado,
        )

    @staticmethod
    def listar_presupuestos(session: Session, limit: int = 100) -> list[Presupuesto]:
        statement = (
            select(Presupuesto)
            .options(
                joinedload(Presupuesto.usuario),
                joinedload(Presupuesto.cliente),
                joinedload(Presupuesto.detalles).joinedload(PresupuestoDetalle.variante),
            )
            .order_by(desc(Presupuesto.created_at))
            .limit(limit)
        )
        return list(session.scalars(statement).unique().all())

    @staticmethod
    def obtener_presupuesto(session: Session, presupuesto_id: int) -> Presupuesto | None:
        statement = (
            select(Presupuesto)
            .options(
                joinedload(Presupuesto.usuario),
                joinedload(Presupuesto.cliente),
                joinedload(Presupuesto.detalles).joinedload(PresupuestoDetalle.variante),
            )
            .where(Presupuesto.id == presupuesto_id)
        )
        return session.scalar(statement)

    @classmethod
    def cancelar_presupuesto(
        cls,
        session: Session,
        presupuesto: Presupuesto,
        usuario: Usuario,
        observacion: str | None = None,
    ) -> Presupuesto:
        cls._validar_operador(usuario)
        if presupuesto.estado == EstadoPresupuesto.CANCELADO:
            raise ValueError("El presupuesto ya esta cancelado.")
        if presupuesto.estado == EstadoPresupuesto.CONVERTIDO:
            raise ValueError("No se puede cancelar un presupuesto ya convertido.")
        presupuesto.estado = EstadoPresupuesto.CANCELADO
        presupuesto.cancelado_at = datetime.now()
        if observacion:
            presupuesto.observacion = observacion.strip()
        session.add(presupuesto)
        return presupuesto

    @classmethod
    def emitir_presupuesto(
        cls,
        session: Session,
        presupuesto: Presupuesto,
        usuario: Usuario,
        observacion: str | None = None,
    ) -> Presupuesto:
        cls._validar_operador(usuario)
        if presupuesto.estado == EstadoPresupuesto.EMITIDO:
            raise ValueError("El presupuesto ya esta emitido.")
        if presupuesto.estado == EstadoPresupuesto.CANCELADO:
            raise ValueError("No se puede emitir un presupuesto cancelado.")
        if presupuesto.estado == EstadoPresupuesto.CONVERTIDO:
            raise ValueError("No se puede emitir un presupuesto ya convertido.")
        if presupuesto.estado != EstadoPresupuesto.BORRADOR:
            raise ValueError("Solo se pueden emitir presupuestos en borrador.")

        presupuesto.estado = EstadoPresupuesto.EMITIDO
        presupuesto.emitido_at = datetime.now()
        if observacion:
            presupuesto.observacion = observacion.strip()
        session.add(presupuesto)
        return presupuesto
