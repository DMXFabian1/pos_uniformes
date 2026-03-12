"""Reglas de negocio para inventario y trazabilidad."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.orm import Session

from pos_uniformes.database.models import (
    AjusteInventarioLote,
    AjusteInventarioLoteDetalle,
    Apartado,
    ApartadoDetalle,
    EstadoApartado,
    MovimientoInventario,
    RolUsuario,
    TipoMovimientoInventario,
    Usuario,
    Variante,
)


@dataclass(frozen=True)
class AjusteMasivoFilaInput:
    variante_id: int
    valor_capturado: int


@dataclass(frozen=True)
class AjusteMasivoFilaPreview:
    variante_id: int
    sku: str
    producto_nombre: str
    talla: str
    color: str
    stock_anterior: int
    apartado_comprometido: int
    valor_capturado: int
    delta_aplicado: int
    stock_final: int
    estado: str
    mensaje: str


@dataclass(frozen=True)
class AjusteMasivoPreview:
    filas: list[AjusteMasivoFilaPreview]
    total_filas: int
    filas_validas: int
    filas_error: int
    unidades_positivas: int
    unidades_negativas: int


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

    @staticmethod
    def _apartados_comprometidos_por_variante(session: Session, variant_ids: list[int]) -> dict[int, int]:
        if not variant_ids:
            return {}
        rows = session.execute(
            select(
                ApartadoDetalle.variante_id,
                func.coalesce(func.sum(ApartadoDetalle.cantidad), 0),
            )
            .join(ApartadoDetalle.apartado)
            .where(
                ApartadoDetalle.variante_id.in_(variant_ids),
                Apartado.estado.in_([EstadoApartado.ACTIVO, EstadoApartado.LIQUIDADO]),
            )
            .group_by(ApartadoDetalle.variante_id)
        ).all()
        return {int(variante_id): int(cantidad) for variante_id, cantidad in rows}

    @classmethod
    def previsualizar_ajuste_masivo(
        cls,
        session: Session,
        filas_input: list[AjusteMasivoFilaInput],
        *,
        tipo_ajuste: str,
    ) -> AjusteMasivoPreview:
        if not filas_input:
            raise ValueError("No hay filas seleccionadas para ajustar.")
        tipo_normalizado = tipo_ajuste.strip().upper()
        if tipo_normalizado not in {"STOCK_FINAL", "DELTA"}:
            raise ValueError("Tipo de ajuste masivo invalido.")

        variant_ids = [int(row.variante_id) for row in filas_input]
        variantes = session.scalars(select(Variante).where(Variante.id.in_(variant_ids))).all()
        variantes_por_id = {int(variante.id): variante for variante in variantes}
        apartados_por_variante = cls._apartados_comprometidos_por_variante(session, variant_ids)

        filas_preview: list[AjusteMasivoFilaPreview] = []
        unidades_positivas = 0
        unidades_negativas = 0
        filas_validas = 0
        filas_error = 0

        for row in filas_input:
            variante = variantes_por_id.get(int(row.variante_id))
            if variante is None:
                filas_error += 1
                filas_preview.append(
                    AjusteMasivoFilaPreview(
                        variante_id=int(row.variante_id),
                        sku="N/D",
                        producto_nombre="Presentacion no encontrada",
                        talla="-",
                        color="-",
                        stock_anterior=0,
                        apartado_comprometido=0,
                        valor_capturado=int(row.valor_capturado),
                        delta_aplicado=0,
                        stock_final=0,
                        estado="ERROR",
                        mensaje="La presentacion ya no existe en la base de datos.",
                    )
                )
                continue

            stock_anterior = int(variante.stock_actual)
            apartado_comprometido = int(apartados_por_variante.get(int(variante.id), 0))
            valor_capturado = int(row.valor_capturado)
            if tipo_normalizado == "STOCK_FINAL":
                stock_final = valor_capturado
                delta_aplicado = stock_final - stock_anterior
            else:
                delta_aplicado = valor_capturado
                stock_final = stock_anterior + delta_aplicado

            estado = "VALIDO"
            mensaje = "Listo para aplicar."
            if stock_final < 0:
                estado = "ERROR"
                mensaje = "El ajuste deja stock negativo."
            elif delta_aplicado == 0:
                estado = "SIN_CAMBIOS"
                mensaje = "Sin cambios pendientes."
            elif stock_final < apartado_comprometido:
                estado = "ERROR"
                mensaje = "El stock final queda por debajo de lo comprometido en apartados."
            elif not variante.activo:
                mensaje = "Presentacion inactiva; el ajuste aun se puede aplicar."

            if estado == "VALIDO":
                filas_validas += 1
                if delta_aplicado > 0:
                    unidades_positivas += delta_aplicado
                elif delta_aplicado < 0:
                    unidades_negativas += abs(delta_aplicado)
            elif estado == "ERROR":
                filas_error += 1

            filas_preview.append(
                AjusteMasivoFilaPreview(
                    variante_id=int(variante.id),
                    sku=variante.sku,
                    producto_nombre=variante.producto.nombre_base,
                    talla=variante.talla,
                    color=variante.color,
                    stock_anterior=stock_anterior,
                    apartado_comprometido=apartado_comprometido,
                    valor_capturado=valor_capturado,
                    delta_aplicado=delta_aplicado,
                    stock_final=stock_final,
                    estado=estado,
                    mensaje=mensaje,
                )
            )

        return AjusteMasivoPreview(
            filas=filas_preview,
            total_filas=len(filas_preview),
            filas_validas=filas_validas,
            filas_error=filas_error,
            unidades_positivas=unidades_positivas,
            unidades_negativas=unidades_negativas,
        )

    @classmethod
    def aplicar_ajuste_masivo(
        cls,
        session: Session,
        *,
        usuario: Usuario,
        tipo_fuente: str,
        tipo_ajuste: str,
        referencia: str,
        motivo: str,
        observacion: str | None,
        filas_input: list[AjusteMasivoFilaInput],
    ) -> tuple[AjusteInventarioLote, AjusteMasivoPreview]:
        if not usuario.activo:
            raise PermissionError("El usuario no esta activo.")
        if usuario.rol != RolUsuario.ADMIN:
            raise PermissionError("Solo un usuario ADMIN puede aplicar ajustes masivos.")
        referencia = referencia.strip()
        motivo = motivo.strip()
        if not referencia:
            raise ValueError("La referencia del lote es obligatoria.")
        if not motivo:
            raise ValueError("El motivo del lote es obligatorio.")

        preview = cls.previsualizar_ajuste_masivo(
            session=session,
            filas_input=filas_input,
            tipo_ajuste=tipo_ajuste,
        )
        if preview.total_filas == 0:
            raise ValueError("No hay filas para aplicar en el lote.")
        if preview.filas_error > 0:
            raise ValueError("Corrige las filas con error antes de aplicar el lote.")

        lote = AjusteInventarioLote(
            usuario=usuario,
            tipo_fuente=tipo_fuente.strip().upper() or "SELECCION",
            tipo_ajuste=tipo_ajuste.strip().upper(),
            referencia=referencia,
            motivo=motivo,
            observacion=observacion or None,
            total_filas=preview.total_filas,
            filas_validas=preview.filas_validas,
            filas_error=preview.filas_error,
            unidades_positivas=preview.unidades_positivas,
            unidades_negativas=preview.unidades_negativas,
        )
        session.add(lote)
        session.flush()

        for fila in preview.filas:
            variante = session.get(Variante, fila.variante_id)
            if variante is None:
                raise ValueError(f"La presentacion {fila.sku} ya no existe.")
            detalle = AjusteInventarioLoteDetalle(
                lote=lote,
                variante=variante,
                sku_snapshot=fila.sku,
                stock_anterior=fila.stock_anterior,
                apartado_comprometido=fila.apartado_comprometido,
                valor_capturado=fila.valor_capturado,
                delta_aplicado=fila.delta_aplicado,
                stock_final=fila.stock_final,
                estado=fila.estado,
                mensaje=fila.mensaje,
            )
            session.add(detalle)
            if fila.estado != "VALIDO":
                continue
            cls.registrar_ajuste_manual(
                session=session,
                variante=variante,
                cantidad=fila.delta_aplicado,
                usuario=usuario,
                referencia=referencia,
                observacion=(
                    f"Lote {lote.id} | {motivo}. "
                    f"{observacion.strip()} " if observacion and observacion.strip() else f"Lote {lote.id} | {motivo}. "
                ).strip(),
            )
        session.flush()
        return lote, preview
