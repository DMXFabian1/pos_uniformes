"""Reglas de negocio para bodega: cajas, ubicaciones y distribución física."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from pos_uniformes.ui.helpers.size_option_sort_helper import (
    _size_sort_key as _talla_sort_key,
)

from pos_uniformes.database.models import (
    CATEGORIA_CAJA_LABELS,
    BodegaCaja,
    BodegaContenido,
    BodegaMovimiento,
    BodegaUbicacion,
    CategoriaCaja,
    EstadoCaja,
    Producto,
    TipoMovimientoBodega,
    Variante,
)


class BodegaService:

    # ─── Ubicaciones (fijas: PISO y ALMACEN) ────────────────────────────

    RACKS_PERMITIDOS = {"PISO", "ALMACEN"}

    @staticmethod
    def listar_ubicaciones(session: Session, *, activas: bool = True) -> list[BodegaUbicacion]:
        stmt = select(BodegaUbicacion).order_by(BodegaUbicacion.rack, BodegaUbicacion.nivel)
        if activas:
            stmt = stmt.where(BodegaUbicacion.activo.is_(True))
        return list(session.scalars(stmt).all())

    # ─── Cajas ───────────────────────────────────────────────────────────

    @staticmethod
    def _abrev_ubicacion(ubicacion: BodegaUbicacion | None) -> str:
        """PISO N1 → P1, ALMACEN N1 → A1, sin ubicación → XX."""
        if not ubicacion:
            return "XX"
        return f"{ubicacion.rack[0]}{ubicacion.nivel}"

    @classmethod
    def _siguiente_codigo(cls, session: Session, categoria: CategoriaCaja,
                          ubicacion: BodegaUbicacion | None = None) -> str:
        abrev = cls._abrev_ubicacion(ubicacion)
        prefix = f"{categoria.value}-{abrev}"
        # Extraer el número secuencial — excluir sufijos de cajas adjuntas (007B, etc.)
        suffix_expr = func.substr(BodegaCaja.codigo, len(prefix) + 2)
        max_num = session.scalar(
            select(func.max(
                func.cast(suffix_expr, sa.Integer)
            )).where(
                BodegaCaja.codigo.like(f"{prefix}-%"),
                suffix_expr.regexp_match(r"^\d+$"),
            )
        )
        return f"{prefix}-{(max_num or 0) + 1:03d}"

    @classmethod
    def _regenerar_codigo(cls, session: Session, caja: BodegaCaja) -> str:
        """Genera nuevo código para una caja existente (reclasificar/mover)."""
        ubicacion = caja.ubicacion
        cat = CategoriaCaja(caja.categoria)
        nuevo = cls._siguiente_codigo(session, cat, ubicacion)
        caja.codigo = nuevo
        caja.qr_data = f"BODEGA:CAJA:{nuevo}"
        return nuevo

    @classmethod
    def crear_caja(
        cls,
        session: Session,
        categoria: CategoriaCaja,
        ubicacion_id: int | None = None,
        notas: str | None = None,
        creado_por: str = "SYSTEM",
    ) -> BodegaCaja:
        ubicacion = session.get(BodegaUbicacion, ubicacion_id) if ubicacion_id else None
        codigo = cls._siguiente_codigo(session, categoria, ubicacion)
        caja = BodegaCaja(
            codigo=codigo,
            categoria=categoria.value,
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

    @classmethod
    def mover_caja(
        cls,
        session: Session,
        caja_id: int,
        nueva_ubicacion_id: int | None,
        creado_por: str = "SYSTEM",
    ) -> BodegaCaja:
        caja = session.scalar(
            select(BodegaCaja)
            .options(joinedload(BodegaCaja.ubicacion), joinedload(BodegaCaja.contenido))
            .where(BodegaCaja.id == caja_id)
        )
        if not caja:
            raise ValueError("Caja no encontrada.")

        anterior_id = caja.ubicacion_id
        codigo_anterior = caja.codigo
        caja.ubicacion_id = nueva_ubicacion_id
        # Recargar la nueva ubicación para regenerar código
        if nueva_ubicacion_id:
            caja.ubicacion = session.get(BodegaUbicacion, nueva_ubicacion_id)
        else:
            caja.ubicacion = None
        nuevo_codigo = cls._regenerar_codigo(session, caja)

        mov = BodegaMovimiento(
            caja_id=caja.id,
            tipo=TipoMovimientoBodega.MOVER_CAJA.value,
            ubicacion_anterior_id=anterior_id,
            ubicacion_nueva_id=nueva_ubicacion_id,
            observacion=f"{codigo_anterior} → {nuevo_codigo}" if codigo_anterior != nuevo_codigo else None,
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
        categoria: CategoriaCaja | None = None,
        query: str | None = None,
    ) -> list[BodegaCaja]:
        stmt = (
            select(BodegaCaja)
            .options(joinedload(BodegaCaja.ubicacion))
            .order_by(BodegaCaja.categoria, BodegaCaja.codigo)
        )
        if ubicacion_id is not None:
            stmt = stmt.where(BodegaCaja.ubicacion_id == ubicacion_id)
        if estado is not None:
            stmt = stmt.where(BodegaCaja.estado == estado.value)
        if categoria is not None:
            stmt = stmt.where(BodegaCaja.categoria == categoria.value)
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

        caja = session.scalar(
            select(BodegaCaja).options(joinedload(BodegaCaja.ubicacion)).where(BodegaCaja.id == caja_id)
        )
        if not caja:
            raise ValueError("Caja no encontrada.")

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

        caja = session.scalar(
            select(BodegaCaja).options(joinedload(BodegaCaja.ubicacion)).where(BodegaCaja.id == caja_id)
        )
        if not caja:
            raise ValueError("Caja no encontrada.")

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
    def corregir_producto(
        cls,
        session: Session,
        caja_id: int,
        variante_id: int,
        cantidad: int,
        creado_por: str = "SYSTEM",
        observacion: str | None = None,
    ) -> BodegaContenido | None:
        """Elimina piezas de la caja Y descuenta stock_actual (error humano)."""
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
            raise ValueError(f"Solo hay {contenido.cantidad} unidades en la caja.")

        variante = session.get(Variante, variante_id)
        if not variante:
            raise ValueError("Variante no encontrada.")

        contenido.cantidad -= cantidad
        if contenido.cantidad == 0:
            session.delete(contenido)
            contenido = None

        variante.stock_actual = max(0, variante.stock_actual - cantidad)

        mov = BodegaMovimiento(
            caja_id=caja_id,
            variante_id=variante_id,
            tipo=TipoMovimientoBodega.CORRECCION.value,
            cantidad=cantidad,
            observacion=observacion or "Corrección por error humano",
            creado_por=creado_por,
        )
        session.add(mov)
        session.flush()
        return contenido

    @classmethod
    def crear_caja_adjunta(
        cls,
        session: Session,
        caja_base_id: int,
        notas: str | None = None,
        creado_por: str = "SYSTEM",
    ) -> BodegaCaja:
        """Crea una caja con sufijo (B, C, D...) junto a la caja base."""
        caja_base = session.scalar(
            select(BodegaCaja)
            .options(joinedload(BodegaCaja.ubicacion))
            .where(BodegaCaja.id == caja_base_id)
        )
        if not caja_base:
            raise ValueError("Caja base no encontrada.")

        codigo_raiz = caja_base.codigo.rstrip("BCDEFGHIJKLMNOPQRSTUVWXYZ")
        sufijo = "B"
        while session.scalar(
            select(BodegaCaja.id).where(BodegaCaja.codigo == f"{codigo_raiz}{sufijo}")
        ):
            sufijo = chr(ord(sufijo) + 1)
            if sufijo > "Z":
                raise ValueError("Se alcanzó el límite de cajas adjuntas.")

        codigo = f"{codigo_raiz}{sufijo}"
        caja = BodegaCaja(
            codigo=codigo,
            categoria=caja_base.categoria,
            ubicacion_id=caja_base.ubicacion_id,
            estado=EstadoCaja.ACTIVA.value,
            notas=notas,
        )
        session.add(caja)
        session.flush()

        mov = BodegaMovimiento(
            caja_id=caja.id,
            tipo=TipoMovimientoBodega.CREAR_CAJA.value,
            ubicacion_nueva_id=caja_base.ubicacion_id,
            observacion=f"Adjunta a {caja_base.codigo}",
            creado_por=creado_por,
        )
        session.add(mov)
        session.flush()
        return caja

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

        caja_origen = session.scalar(
            select(BodegaCaja).options(joinedload(BodegaCaja.ubicacion)).where(BodegaCaja.id == caja_origen_id)
        )
        caja_destino = session.scalar(
            select(BodegaCaja).options(joinedload(BodegaCaja.ubicacion)).where(BodegaCaja.id == caja_destino_id)
        )

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
            .options(
                joinedload(BodegaMovimiento.variante).joinedload(Variante.producto),
            )
            .where(BodegaMovimiento.caja_id == caja_id)
            .order_by(BodegaMovimiento.created_at.desc())
            .limit(limit)
        )
        return list(session.scalars(stmt).unique().all())

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

    @classmethod
    def reclasificar_caja(
        cls,
        session: Session,
        caja_id: int,
        nueva_categoria: CategoriaCaja,
        creado_por: str = "SYSTEM",
    ) -> BodegaCaja:
        caja = session.scalar(
            select(BodegaCaja)
            .options(joinedload(BodegaCaja.ubicacion))
            .where(BodegaCaja.id == caja_id)
        )
        if not caja:
            raise ValueError("Caja no encontrada.")
        codigo_anterior = caja.codigo
        anterior = caja.categoria
        caja.categoria = nueva_categoria.value
        nuevo_codigo = cls._regenerar_codigo(session, caja)
        mov = BodegaMovimiento(
            caja_id=caja.id,
            tipo=TipoMovimientoBodega.AJUSTE.value,
            observacion=f"Reclasificada de {anterior} a {nueva_categoria.value} ({codigo_anterior} → {nuevo_codigo})",
            creado_por=creado_por,
        )
        session.add(mov)
        session.flush()
        return caja

    @staticmethod
    def resumen_por_categoria(session: Session) -> list[dict]:
        stmt = (
            select(
                BodegaCaja.categoria,
                func.count(BodegaCaja.id).label("cajas"),
                func.coalesce(func.sum(
                    select(func.coalesce(func.sum(BodegaContenido.cantidad), 0))
                    .where(BodegaContenido.caja_id == BodegaCaja.id)
                    .correlate(BodegaCaja)
                    .scalar_subquery()
                ), 0).label("prendas"),
            )
            .where(BodegaCaja.estado != EstadoCaja.CERRADA.value)
            .group_by(BodegaCaja.categoria)
            .order_by(BodegaCaja.categoria)
        )
        return [
            {
                "categoria": row.categoria,
                "label": CATEGORIA_CAJA_LABELS.get(row.categoria, row.categoria),
                "cajas": row.cajas,
                "prendas": int(row.prendas),
            }
            for row in session.execute(stmt).all()
        ]

    @staticmethod
    def desglose_contenido_caja(session: Session, caja_id: int) -> list[dict]:
        """Contenido agrupado por producto con desglose de tallas."""
        stmt = (
            select(BodegaContenido)
            .options(
                joinedload(BodegaContenido.variante).joinedload(Variante.producto),
            )
            .where(BodegaContenido.caja_id == caja_id)
        )
        por_producto: dict[int, dict] = {}
        for c in session.scalars(stmt).unique().all():
            prod = c.variante.producto
            if prod.id not in por_producto:
                por_producto[prod.id] = {
                    "producto_id": prod.id,
                    "producto": prod.nombre,
                    "tallas": [],
                    "total": 0,
                }
            por_producto[prod.id]["tallas"].append({
                "talla": c.variante.talla,
                "color": c.variante.color,
                "cantidad": c.cantidad,
                "variante_id": c.variante_id,
            })
            por_producto[prod.id]["total"] += c.cantidad
        for grupo in por_producto.values():
            grupo["tallas"].sort(key=lambda t: _talla_sort_key(t["talla"]))
        return list(por_producto.values())

    @staticmethod
    def desglose_contenido_cajas(
        session: Session, caja_ids: list[int]
    ) -> dict[int, list[dict]]:
        """Como desglose_contenido_caja pero para varias cajas en UNA query.

        Llamar el desglose por caja dentro de un loop era un N+1 que pagaba
        una query de red por cada caja al pintar la tabla de bodega."""
        if not caja_ids:
            return {}
        stmt = (
            select(BodegaContenido)
            .options(
                joinedload(BodegaContenido.variante).joinedload(Variante.producto),
            )
            .where(BodegaContenido.caja_id.in_(caja_ids))
        )
        por_caja: dict[int, dict[int, dict]] = {}
        for c in session.scalars(stmt).unique().all():
            por_producto = por_caja.setdefault(int(c.caja_id), {})
            prod = c.variante.producto
            if prod.id not in por_producto:
                por_producto[prod.id] = {
                    "producto_id": prod.id,
                    "producto": prod.nombre,
                    "tallas": [],
                    "total": 0,
                }
            por_producto[prod.id]["tallas"].append({
                "talla": c.variante.talla,
                "color": c.variante.color,
                "cantidad": c.cantidad,
                "variante_id": c.variante_id,
            })
            por_producto[prod.id]["total"] += c.cantidad
        result: dict[int, list[dict]] = {}
        for caja_id in caja_ids:
            grupos = por_caja.get(int(caja_id), {})
            for grupo in grupos.values():
                grupo["tallas"].sort(key=lambda t: _talla_sort_key(t["talla"]))
            result[int(caja_id)] = list(grupos.values())
        return result

    @staticmethod
    def buscar_por_texto_agrupado(session: Session, query: str) -> list[dict]:
        """Búsqueda agrupada por producto con tallas y stock en tienda."""
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
        por_producto: dict[int, dict] = {}
        for c in session.scalars(stmt).unique().all():
            prod = c.variante.producto
            if prod.id not in por_producto:
                por_producto[prod.id] = {
                    "producto_id": prod.id,
                    "producto": prod.nombre,
                    "variantes": {},
                }
            v_id = c.variante_id
            if v_id not in por_producto[prod.id]["variantes"]:
                por_producto[prod.id]["variantes"][v_id] = {
                    "variante_id": v_id,
                    "sku": c.variante.sku,
                    "talla": c.variante.talla,
                    "color": c.variante.color,
                    "stock_actual": c.variante.stock_actual,
                    "en_bodega": 0,
                    "cajas": [],
                }
            entry = por_producto[prod.id]["variantes"][v_id]
            entry["en_bodega"] += c.cantidad
            entry["cajas"].append({
                "caja_codigo": c.caja.codigo,
                "categoria": c.caja.categoria,
                "ubicacion": c.caja.ubicacion.codigo if c.caja.ubicacion else None,
                "cantidad": c.cantidad,
            })

        result = []
        for grupo in por_producto.values():
            variantes = sorted(grupo["variantes"].values(), key=lambda v: _talla_sort_key(v["talla"]))
            for v in variantes:
                v["en_tienda"] = v["stock_actual"] - v["en_bodega"]
            result.append({
                "producto_id": grupo["producto_id"],
                "producto": grupo["producto"],
                "variantes": variantes,
            })
        return result
