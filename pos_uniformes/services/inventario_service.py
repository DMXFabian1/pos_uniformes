"""Reglas de negocio para inventario y trazabilidad."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from pos_uniformes.database.models import MovimientoInventario, RolUsuario, TipoMovimientoInventario, Usuario, Variante


class InventarioService:
    """Aplica movimientos auditables sin permitir stock negativo."""

    @staticmethod
    def obtener_variante_por_sku(session: Session, sku: str) -> Variante | None:
        return session.scalar(select(Variante).where(Variante.sku == sku, Variante.activo.is_(True)))

    @staticmethod
    def validar_stock_disponible(variante: Variante, cantidad: int) -> None:
        if cantidad <= 0:
            raise ValueError("La cantidad debe ser mayor a cero.")
        if variante.stock_actual < cantidad:
            raise ValueError("Stock insuficiente para completar la operacion.")

    @staticmethod
    def registrar_movimiento(
        session: Session,
        variante: Variante,
        tipo_movimiento: TipoMovimientoInventario,
        cantidad: int,
        referencia: str | None = None,
        observacion: str | None = None,
        creado_por: str = "SYSTEM",
    ) -> MovimientoInventario:
        if cantidad == 0:
            raise ValueError("La cantidad del movimiento no puede ser cero.")

        stock_anterior = variante.stock_actual
        stock_posterior = stock_anterior + cantidad

        if stock_posterior < 0:
            raise ValueError("No se puede registrar un movimiento que deje stock negativo.")

        variante.stock_actual = stock_posterior
        movimiento = MovimientoInventario(
            variante=variante,
            tipo_movimiento=tipo_movimiento,
            cantidad=cantidad,
            stock_anterior=stock_anterior,
            stock_posterior=stock_posterior,
            referencia=referencia,
            observacion=observacion,
            creado_por=creado_por,
        )

        session.add(movimiento)
        session.add(variante)
        return movimiento

    @classmethod
    def registrar_ingreso_compra(
        cls,
        session: Session,
        variante: Variante,
        cantidad: int,
        referencia: str | None = None,
        observacion: str | None = None,
        creado_por: str = "SYSTEM",
    ) -> MovimientoInventario:
        return cls.registrar_movimiento(
            session=session,
            variante=variante,
            tipo_movimiento=TipoMovimientoInventario.ENTRADA_COMPRA,
            cantidad=abs(cantidad),
            referencia=referencia,
            observacion=observacion,
            creado_por=creado_por,
        )

    @classmethod
    def registrar_salida_venta(
        cls,
        session: Session,
        variante: Variante,
        cantidad: int,
        referencia: str | None = None,
        observacion: str | None = None,
        creado_por: str = "SYSTEM",
    ) -> MovimientoInventario:
        return cls.registrar_movimiento(
            session=session,
            variante=variante,
            tipo_movimiento=TipoMovimientoInventario.SALIDA_VENTA,
            cantidad=-abs(cantidad),
            referencia=referencia,
            observacion=observacion,
            creado_por=creado_por,
        )

    @classmethod
    def registrar_cancelacion_venta(
        cls,
        session: Session,
        variante: Variante,
        cantidad: int,
        referencia: str | None = None,
        observacion: str | None = None,
        creado_por: str = "ADMIN",
    ) -> MovimientoInventario:
        return cls.registrar_movimiento(
            session=session,
            variante=variante,
            tipo_movimiento=TipoMovimientoInventario.CANCELACION_VENTA,
            cantidad=abs(cantidad),
            referencia=referencia,
            observacion=observacion,
            creado_por=creado_por,
        )

    @classmethod
    def registrar_reserva_apartado(
        cls,
        session: Session,
        variante: Variante,
        cantidad: int,
        referencia: str | None = None,
        observacion: str | None = None,
        creado_por: str = "SYSTEM",
    ) -> MovimientoInventario:
        cls.validar_stock_disponible(variante, cantidad)
        return cls.registrar_movimiento(
            session=session,
            variante=variante,
            tipo_movimiento=TipoMovimientoInventario.APARTADO_RESERVA,
            cantidad=-abs(cantidad),
            referencia=referencia,
            observacion=observacion,
            creado_por=creado_por,
        )

    @classmethod
    def registrar_liberacion_apartado(
        cls,
        session: Session,
        variante: Variante,
        cantidad: int,
        referencia: str | None = None,
        observacion: str | None = None,
        creado_por: str = "SYSTEM",
    ) -> MovimientoInventario:
        return cls.registrar_movimiento(
            session=session,
            variante=variante,
            tipo_movimiento=TipoMovimientoInventario.APARTADO_LIBERACION,
            cantidad=abs(cantidad),
            referencia=referencia,
            observacion=observacion,
            creado_por=creado_por,
        )

    @classmethod
    def registrar_ajuste_manual(
        cls,
        session: Session,
        variante: Variante,
        cantidad: int,
        usuario: Usuario,
        referencia: str | None = None,
        observacion: str | None = None,
    ) -> MovimientoInventario:
        if not usuario.activo:
            raise PermissionError("El usuario no esta activo.")
        if usuario.rol != RolUsuario.ADMIN:
            raise PermissionError("Solo un usuario ADMIN puede registrar ajustes manuales.")
        if cantidad == 0:
            raise ValueError("El ajuste manual no puede ser cero.")

        tipo = (
            TipoMovimientoInventario.AJUSTE_ENTRADA
            if cantidad > 0
            else TipoMovimientoInventario.AJUSTE_SALIDA
        )
        return cls.registrar_movimiento(
            session=session,
            variante=variante,
            tipo_movimiento=tipo,
            cantidad=cantidad,
            referencia=referencia,
            observacion=observacion,
            creado_por=usuario.username,
        )
