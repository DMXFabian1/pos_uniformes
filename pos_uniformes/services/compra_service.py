"""Servicios base para compras a proveedores."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from pos_uniformes.database.models import Compra, CompraDetalle, EstadoCompra, Proveedor, RolUsuario, Usuario, Variante
from pos_uniformes.services.inventario_service import InventarioService


@dataclass(frozen=True)
class CompraItemInput:
    variante_id: int
    cantidad: int
    costo_unitario: Decimal


class CompraService:
    """Crea y confirma compras, generando entradas auditables de inventario."""

    @staticmethod
    def _validar_permiso(usuario: Usuario) -> None:
        if not usuario.activo:
            raise PermissionError("El usuario no esta activo.")
        if usuario.rol != RolUsuario.ADMIN:
            raise PermissionError("Solo un usuario ADMIN puede registrar o confirmar compras.")

    @staticmethod
    def _validar_items(items: list[CompraItemInput]) -> None:
        if not items:
            raise ValueError("La compra debe contener al menos una linea.")

        variantes: set[int] = set()
        for item in items:
            if item.variante_id in variantes:
                raise ValueError(f"La variante {item.variante_id} esta repetida en la compra.")
            variantes.add(item.variante_id)
            if item.cantidad <= 0:
                raise ValueError("La cantidad de compra debe ser mayor a cero.")
            if item.costo_unitario < 0:
                raise ValueError("El costo unitario no puede ser negativo.")

    @staticmethod
    def _obtener_variantes(session: Session, items: list[CompraItemInput]) -> dict[int, Variante]:
        variantes = session.query(Variante).filter(
            Variante.id.in_([item.variante_id for item in items]),
            Variante.activo.is_(True),
        ).all()
        variantes_by_id = {variante.id: variante for variante in variantes}

        faltantes = [str(item.variante_id) for item in items if item.variante_id not in variantes_by_id]
        if faltantes:
            raise ValueError(f"No existen variantes activas para los ids: {', '.join(faltantes)}.")

        return variantes_by_id

    @classmethod
    def crear_borrador(
        cls,
        session: Session,
        proveedor: Proveedor,
        usuario: Usuario,
        numero_documento: str,
        items: list[CompraItemInput],
        observacion: str | None = None,
    ) -> Compra:
        cls._validar_permiso(usuario)
        cls._validar_items(items)
        variantes_by_id = cls._obtener_variantes(session, items)

        compra = Compra(
            proveedor=proveedor,
            usuario=usuario,
            numero_documento=numero_documento,
            observacion=observacion,
            estado=EstadoCompra.BORRADOR,
        )

        total = Decimal("0.00")
        for item in items:
            subtotal_linea = Decimal(item.cantidad) * item.costo_unitario
            detalle = CompraDetalle(
                variante=variantes_by_id[item.variante_id],
                cantidad=item.cantidad,
                costo_unitario=item.costo_unitario,
                subtotal_linea=subtotal_linea,
            )
            compra.detalles.append(detalle)
            total += subtotal_linea

        compra.subtotal = total
        compra.total = total
        session.add(compra)
        return compra

    @staticmethod
    def confirmar_compra(session: Session, compra: Compra) -> Compra:
        CompraService._validar_permiso(compra.usuario)
        if compra.estado != EstadoCompra.BORRADOR:
            raise ValueError("Solo las compras en borrador pueden confirmarse.")

        if not compra.detalles:
            raise ValueError("No se puede confirmar una compra sin detalles.")

        for detalle in compra.detalles:
            detalle.variante.costo_referencia = detalle.costo_unitario
            InventarioService.registrar_ingreso_compra(
                session=session,
                variante=detalle.variante,
                cantidad=detalle.cantidad,
                referencia=compra.numero_documento,
                creado_por=compra.usuario.username,
            )

        compra.estado = EstadoCompra.CONFIRMADA
        compra.confirmada_at = datetime.now()
        session.add(compra)
        return compra
