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
        if not items:
            raise ValueError("El presupuesto debe contener al menos una linea.")

        presupuesto = Presupuesto(
            usuario=usuario,
            cliente=cliente,
            folio=folio.strip(),
            cliente_nombre=(cliente_nombre or "").strip() or (cliente.nombre if cliente is not None else None),
            cliente_telefono=(cliente_telefono or "").strip() or (cliente.telefono if cliente is not None else None),
            vigencia_hasta=vigencia_hasta,
            observacion=(observacion or "").strip() or None,
            estado=estado,
            emitido_at=datetime.now() if estado == EstadoPresupuesto.EMITIDO else None,
        )

        total = Decimal("0.00")
        skus: set[str] = set()
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
            detalle = PresupuestoDetalle(
                variante=variante,
                sku_snapshot=variante.sku,
                descripcion_snapshot=variante.producto.nombre_base,
                talla_snapshot=variante.talla,
                color_snapshot=variante.color,
                precio_unitario=precio_unitario,
                cantidad=item.cantidad,
                subtotal_linea=subtotal_linea,
            )
            presupuesto.detalles.append(detalle)
            total += subtotal_linea

        presupuesto.subtotal = total
        presupuesto.total = total
        session.add(presupuesto)
        return presupuesto

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
