"""Reglas de negocio para bodega: cajas, ubicaciones y distribución física."""

from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from pos_uniformes.database.models import (
    BodegaCaja,
    BodegaContenido,
    BodegaMovimiento,
    BodegaUbicacion,
    EstadoCaja,
    Producto,
    TipoMovimientoBodega,
    Variante,
)


class BodegaService:

    # ─── Ubicaciones ─────────────────────────────────────────────────────

    @staticmethod
    def crear_ubicacion(
        session: Session,
        rack: str,
        nivel: int,
        codigo: str | None = None,
        descripcion: str | None = None,
    ) -> BodegaUbicacion:
        if not codigo:
            codigo = f"{rack}-N{nivel}"
        ubicacion = BodegaUbicacion(
            codigo=codigo,
            rack=rack.strip().upper(),
            nivel=nivel,
            descripcion=descripcion,
        )
        session.add(ubicacion)
        session.flush()
        return ubicacion

    @staticmethod
    def listar_ubicaciones(session: Session, *, activas: bool = True) -> list[BodegaUbicacion]:
        stmt = select(BodegaUbicacion).order_by(BodegaUbicacion.rack, BodegaUbicacion.nivel)
        if activas:
            stmt = stmt.where(BodegaUbicacion.activo.is_(True))
        return list(session.scalars(stmt).all())

    @staticmethod
    def desactivar_ubicacion(session: Session, ubicacion_id: int) -> None:
        ub = session.get(BodegaUbicacion, ubicacion_id)
        if not ub:
            raise ValueError("Ubicación no encontrada.")
        ub.activo = False
        session.flush()

    # ─── Cajas ───────────────────────────────────────────────────────────

    @staticmethod
    def crear_caja(
        session: Session,
        codigo: str,
        ubicacion_id: int | None = None,
        notas: str | None = None,
        creado_por: str = "SYSTEM",
    ) -> BodegaCaja:
        caja = BodegaCaja(
            codigo=codigo.strip().upper(),
            ubicacion_id=ubicacion_id,
            estado=EstadoCaja.ACTIVA.value,
            notas=notas,
        )
        session.add(caja)
        session.flush()

        mov = BodegaMovimiento(
            caja_id=caja.id,
            tipo=TipoMovimientoBodega.CREAR_CAJA.value,
            ubicacion_nueva_id=ubicacion_id,
            creado_por=creado_por,
        )
        session.add(mov)
        session.flush()
        return caja

    @staticmethod
    def mover_caja(
        session: Session,
        caja_id: int,
        nueva_ubicacion_id: int | None,
        creado_por: str = "SYSTEM",
    ) -> BodegaCaja:
        caja = session.get(BodegaCaja, caja_id)
        if not caja:
            raise ValueError("Caja no encontrada.")

        anterior_id = caja.ubicacion_id
        caja.ubicacion_id = nueva_ubicacion_id

        mov = BodegaMovimiento(
            caja_id=caja.id,
            tipo=TipoMovimientoBodega.MOVER_CAJA.value,
            ubicacion_anterior_id=anterior_id,
            ubicacion_nueva_id=nueva_ubicacion_id,
            creado_por=creado_por,
        )
        session.add(mov)
        session.flush()
        return caja

    @staticmethod
    def cambiar_estado_caja(session: Session, caja_id: int, nuevo_estado: EstadoCaja) -> BodegaCaja:
        caja = session.get(BodegaCaja, caja_id)
        if not caja:
            raise ValueError("Caja no encontrada.")
        caja.estado = nuevo_estado.value
        session.flush()
        return caja

    @staticmethod
    def listar_cajas(
        session: Session,
        *,
        ubicacion_id: int | None = None,
        estado: EstadoCaja | None = None,
        query: str | None = None,
    ) -> list[BodegaCaja]:
        stmt = (
            select(BodegaCaja)
            .options(joinedload(BodegaCaja.ubicacion))
            .order_by(BodegaCaja.codigo)
        )
        if ubicacion_id is not None:
            stmt = stmt.where(BodegaCaja.ubicacion_id == ubicacion_id)
        if estado is not None:
            stmt = stmt.where(BodegaCaja.estado == estado.value)
        if query:
            stmt = stmt.where(BodegaCaja.codigo.ilike(f"%{query}%"))
        return list(session.scalars(stmt).unique().all())

    @staticmethod
    def obtener_caja_detalle(session: Session, caja_id: int) -> BodegaCaja | None:
        stmt = (
            select(BodegaCaja)
            .options(
                joinedload(BodegaCaja.ubicacion),
                joinedload(BodegaCaja.contenido).joinedload(BodegaContenido.variante).joinedload(Variante.producto),
            )
            .where(BodegaCaja.id == caja_id)
        )
        return session.scalar(stmt)

    # ─── Contenido ───────────────────────────────────────────────────────

    @classmethod
    def _total_en_bodega_para_variante(cls, session: Session, variante_id: int) -> int:
        result = session.scalar(
            select(func.coalesce(func.sum(BodegaContenido.cantidad), 0))
            .where(BodegaContenido.variante_id == variante_id)
        )
        return int(result)

    @classmethod
    def stock_disponible_tienda(cls, session: Session, variante_id: int) -> int:
        variante = session.get(Variante, variante_id)
        if not variante:
            raise ValueError("Variante no encontrada.")
        return variante.stock_actual - cls._total_en_bodega_para_variante(session, variante_id)

    @classmethod
    def ingresar_producto(
        cls,
        session: Session,
        caja_id: int,
        variante_id: int,
        cantidad: int,
        creado_por: str = "SYSTEM",
        observacion: str | None = None,
    ) -> BodegaContenido:
        if cantidad <= 0:
            raise ValueError("La cantidad debe ser mayor a cero.")

        variante = session.get(Variante, variante_id)
        if not variante:
            raise ValueError("Variante no encontrada.")

        total_en_bodega = cls._total_en_bodega_para_variante(session, variante_id)
        if total_en_bodega + cantidad > variante.stock_actual:
            raise ValueError(
                f"No se puede asignar {cantidad} a bodega. "
                f"Stock total: {variante.stock_actual}, ya en bodega: {total_en_bodega}."
            )

        contenido = session.scalar(
            select(BodegaContenido).where(
                BodegaContenido.caja_id == caja_id,
                BodegaContenido.variante_id == variante_id,
            )
        )
        if contenido:
            contenido.cantidad += cantidad
        else:
            contenido = BodegaContenido(
                caja_id=caja_id,
                variante_id=variante_id,
                cantidad=cantidad,
            )
            session.add(contenido)

        mov = BodegaMovimiento(
            caja_id=caja_id,
            variante_id=variante_id,
            tipo=TipoMovimientoBodega.INGRESO.value,
            cantidad=cantidad,
            observacion=observacion,
            creado_por=creado_por,
        )
        session.add(mov)
        session.flush()
        return contenido

    @classmethod
    def retirar_producto(
        cls,
        session: Session,
        caja_id: int,
        variante_id: int,
        cantidad: int,
        creado_por: str = "SYSTEM",
        observacion: str | None = None,
    ) -> BodegaContenido | None:
        if cantidad <= 0:
            raise ValueError("La cantidad debe ser mayor a cero.")

        contenido = session.scalar(
            select(BodegaContenido).where(
                BodegaContenido.caja_id == caja_id,
                BodegaContenido.variante_id == variante_id,
            )
        )
        if not contenido:
            raise ValueError("La variante no existe en esta caja.")
        if contenido.cantidad < cantidad:
            raise ValueError(
                f"Solo hay {contenido.cantidad} unidades en la caja."
            )

        contenido.cantidad -= cantidad
        if contenido.cantidad == 0:
            session.delete(contenido)
            contenido = None

        mov = BodegaMovimiento(
            caja_id=caja_id,
            variante_id=variante_id,
            tipo=TipoMovimientoBodega.RETIRO.value,
            cantidad=cantidad,
            observacion=observacion,
            creado_por=creado_por,
        )
        session.add(mov)
        session.flush()
        return contenido

    @classmethod
    def transferir_producto(
        cls,
        session: Session,
        caja_origen_id: int,
        caja_destino_id: int,
        variante_id: int,
        cantidad: int,
        creado_por: str = "SYSTEM",
    ) -> None:
        if cantidad <= 0:
            raise ValueError("La cantidad debe ser mayor a cero.")

        contenido_origen = session.scalar(
            select(BodegaContenido).where(
                BodegaContenido.caja_id == caja_origen_id,
                BodegaContenido.variante_id == variante_id,
            )
        )
        if not contenido_origen:
            raise ValueError("La variante no existe en la caja origen.")
        if contenido_origen.cantidad < cantidad:
            raise ValueError(f"Solo hay {contenido_origen.cantidad} unidades en caja origen.")

        contenido_origen.cantidad -= cantidad
        if contenido_origen.cantidad == 0:
            session.delete(contenido_origen)

        contenido_destino = session.scalar(
            select(BodegaContenido).where(
                BodegaContenido.caja_id == caja_destino_id,
                BodegaContenido.variante_id == variante_id,
            )
        )
        if contenido_destino:
            contenido_destino.cantidad += cantidad
        else:
            contenido_destino = BodegaContenido(
                caja_id=caja_destino_id,
                variante_id=variante_id,
                cantidad=cantidad,
            )
            session.add(contenido_destino)

        mov = BodegaMovimiento(
            caja_id=caja_origen_id,
            variante_id=variante_id,
            tipo=TipoMovimientoBodega.TRANSFERENCIA.value,
            cantidad=cantidad,
            caja_destino_id=caja_destino_id,
            creado_por=creado_por,
        )
        session.add(mov)
        session.flush()

    @classmethod
    def ingreso_masivo(
        cls,
        session: Session,
        caja_id: int,
        items: list[dict],
        creado_por: str = "SYSTEM",
    ) -> int:
        """Ingresa múltiples variantes a una caja. items: [{variante_id, cantidad}]. Retorna total ingresado."""
        total = 0
        for item in items:
            variante_id = item["variante_id"]
            cantidad = item["cantidad"]
            if cantidad > 0:
                cls.ingresar_producto(session, caja_id, variante_id, cantidad, creado_por)
                total += cantidad
        return total

    # ─── Búsqueda ────────────────────────────────────────────────────────

    @staticmethod
    def buscar_variante_en_bodega(session: Session, variante_id: int) -> list[dict]:
        stmt = (
            select(BodegaContenido)
            .options(joinedload(BodegaContenido.caja).joinedload(BodegaCaja.ubicacion))
            .where(BodegaContenido.variante_id == variante_id)
            .order_by(BodegaContenido.cantidad.desc())
        )
        resultados = []
        for c in session.scalars(stmt).unique().all():
            resultados.append({
                "caja_id": c.caja_id,
                "caja_codigo": c.caja.codigo,
                "ubicacion": c.caja.ubicacion.codigo if c.caja.ubicacion else None,
                "cantidad": c.cantidad,
            })
        return resultados

    @staticmethod
    def buscar_por_texto(session: Session, query: str) -> list[dict]:
        pattern = f"%{query}%"
        stmt = (
            select(BodegaContenido)
            .join(BodegaContenido.variante)
            .join(Variante.producto)
            .join(BodegaContenido.caja)
            .outerjoin(BodegaCaja.ubicacion)
            .options(
                joinedload(BodegaContenido.variante).joinedload(Variante.producto),
                joinedload(BodegaContenido.caja).joinedload(BodegaCaja.ubicacion),
            )
            .where(
                or_(
                    Variante.sku.ilike(pattern),
                    Producto.nombre.ilike(pattern),
                    Variante.talla.ilike(pattern),
                    BodegaCaja.codigo.ilike(pattern),
                )
            )
            .order_by(Producto.nombre, Variante.talla)
        )
        resultados = []
        for c in session.scalars(stmt).unique().all():
            resultados.append({
                "variante_id": c.variante_id,
                "sku": c.variante.sku,
                "producto": c.variante.producto.nombre,
                "talla": c.variante.talla,
                "color": c.variante.color,
                "caja_codigo": c.caja.codigo,
                "ubicacion": c.caja.ubicacion.codigo if c.caja.ubicacion else None,
                "cantidad": c.cantidad,
            })
        return resultados

    # ─── Historial ───────────────────────────────────────────────────────

    @staticmethod
    def historial_caja(session: Session, caja_id: int, limit: int = 50) -> list[BodegaMovimiento]:
        stmt = (
            select(BodegaMovimiento)
            .where(BodegaMovimiento.caja_id == caja_id)
            .order_by(BodegaMovimiento.created_at.desc())
            .limit(limit)
        )
        return list(session.scalars(stmt).all())

    # ─── QR ──────────────────────────────────────────────────────────────

    @staticmethod
    def generar_qr_data(caja: BodegaCaja) -> str:
        return f"BODEGA:CAJA:{caja.codigo}"

    @staticmethod
    def total_prendas_en_bodega(session: Session) -> int:
        result = session.scalar(
            select(func.coalesce(func.sum(BodegaContenido.cantidad), 0))
        )
        return int(result)

    @staticmethod
    def total_cajas_activas(session: Session) -> int:
        result = session.scalar(
            select(func.count(BodegaCaja.id)).where(BodegaCaja.estado != EstadoCaja.CERRADA.value)
        )
        return int(result)
