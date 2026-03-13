"""Servicios de catalogo para categorias, marcas, productos y variantes."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pos_uniformes.database.models import (
    AtributoProducto,
    Categoria,
    CompraDetalle,
    Escuela,
    Marca,
    MovimientoInventario,
    NivelEducativo,
    Producto,
    RolUsuario,
    SkuSequence,
    TipoPieza,
    TipoCambioCatalogo,
    TipoEntidadCatalogo,
    TipoPrenda,
    Usuario,
    Variante,
    VentaDetalle,
)
from pos_uniformes.services.catalog_audit_service import CatalogAuditService
from pos_uniformes.services.inventario_service import InventarioService


class CatalogService:
    """Gestiona altas del catalogo con reglas basicas de negocio."""

    SKU_SEQUENCE_CODE = "VARIANTE"
    SKU_PREFIX = "SKU"
    SKU_PADDING = 6

    @staticmethod
    def _optional_name(value: object | None) -> str | None:
        return getattr(value, "nombre", None) if value is not None else None

    @classmethod
    def _build_product_display_name(
        cls,
        *,
        base_name: str,
        school: Escuela | None = None,
        garment_type: TipoPrenda | None = None,
        piece_type: TipoPieza | None = None,
    ) -> str:
        suffix_parts = [
            part
            for part in (
                cls._optional_name(school),
                cls._optional_name(garment_type),
                cls._optional_name(piece_type),
            )
            if part
        ]
        if not suffix_parts:
            return base_name
        return f"{base_name} | {' | '.join(suffix_parts)}"

    @staticmethod
    def _descripcion_categoria(categoria: Categoria) -> str:
        return categoria.nombre

    @staticmethod
    def _descripcion_marca(marca: Marca) -> str:
        return marca.nombre

    @staticmethod
    def _descripcion_producto(producto: Producto) -> str:
        return f"{producto.marca.nombre} | {producto.nombre}"

    @staticmethod
    def _descripcion_presentacion(variante: Variante) -> str:
        return f"{variante.sku} | {variante.producto.nombre}"

    @classmethod
    def _registrar_creacion(
        cls,
        session: Session,
        usuario: Usuario,
        entidad_tipo: TipoEntidadCatalogo,
        entidad_id: int,
        descripcion_entidad: str,
        observacion: str,
    ) -> None:
        CatalogAuditService.registrar_cambio(
            session=session,
            usuario=usuario,
            entidad_tipo=entidad_tipo,
            entidad_id=entidad_id,
            accion=TipoCambioCatalogo.CREACION,
            campo="registro",
            valor_anterior=None,
            valor_nuevo=descripcion_entidad,
            descripcion_entidad=descripcion_entidad,
            observacion=observacion,
        )

    @classmethod
    def _registrar_eliminacion(
        cls,
        session: Session,
        usuario: Usuario,
        entidad_tipo: TipoEntidadCatalogo,
        entidad_id: int,
        descripcion_entidad: str,
        observacion: str,
    ) -> None:
        CatalogAuditService.registrar_cambio(
            session=session,
            usuario=usuario,
            entidad_tipo=entidad_tipo,
            entidad_id=entidad_id,
            accion=TipoCambioCatalogo.ELIMINACION,
            campo="registro",
            valor_anterior=descripcion_entidad,
            valor_nuevo=None,
            descripcion_entidad=descripcion_entidad,
            observacion=observacion,
        )

    @classmethod
    def _registrar_cambios(
        cls,
        session: Session,
        usuario: Usuario,
        entidad_tipo: TipoEntidadCatalogo,
        entidad_id: int,
        descripcion_entidad: str,
        valores_anteriores: dict[str, object | None],
        valores_nuevos: dict[str, object | None],
        accion_por_campo: dict[str, TipoCambioCatalogo] | None = None,
        observacion: str | None = None,
    ) -> None:
        for campo, valor_anterior in valores_anteriores.items():
            valor_nuevo = valores_nuevos.get(campo)
            if valor_anterior == valor_nuevo:
                continue
            accion = (accion_por_campo or {}).get(campo, TipoCambioCatalogo.ACTUALIZACION)
            CatalogAuditService.registrar_cambio(
                session=session,
                usuario=usuario,
                entidad_tipo=entidad_tipo,
                entidad_id=entidad_id,
                accion=accion,
                campo=campo,
                valor_anterior=valor_anterior,
                valor_nuevo=valor_nuevo,
                descripcion_entidad=descripcion_entidad,
                observacion=observacion,
            )

    @staticmethod
    def _money(value: Decimal | int | float | str | None) -> Decimal:
        normalized = Decimal("0.00") if value is None else Decimal(str(value))
        return normalized.quantize(Decimal("0.01"))

    @staticmethod
    def _parse_legacy_sku_number(sku: str) -> int | None:
        normalized = (sku or "").strip().upper()
        if not normalized.startswith(CatalogService.SKU_PREFIX):
            return None
        numeric = normalized[len(CatalogService.SKU_PREFIX) :]
        if not numeric.isdigit():
            return None
        return int(numeric)

    @classmethod
    def _get_or_create_sku_sequence(cls, session: Session) -> SkuSequence:
        sequence = session.scalar(
            select(SkuSequence).where(SkuSequence.codigo == cls.SKU_SEQUENCE_CODE)
        )
        if sequence is not None:
            return sequence

        max_existing = 0
        existing_skus = session.scalars(
            select(Variante.sku).where(Variante.sku.like(f"{cls.SKU_PREFIX}%"))
        )
        for existing_sku in existing_skus:
            parsed = cls._parse_legacy_sku_number(existing_sku)
            if parsed is not None and parsed > max_existing:
                max_existing = parsed

        sequence = SkuSequence(
            codigo=cls.SKU_SEQUENCE_CODE,
            prefijo=cls.SKU_PREFIX,
            padding=cls.SKU_PADDING,
            ultimo_numero=max_existing,
        )
        session.add(sequence)
        session.flush()
        return sequence

    @classmethod
    def _sync_sequence_with_manual_sku(cls, session: Session, sku: str) -> None:
        parsed = cls._parse_legacy_sku_number(sku)
        if parsed is None:
            return
        sequence = cls._get_or_create_sku_sequence(session)
        if parsed > int(sequence.ultimo_numero):
            sequence.ultimo_numero = parsed
            session.add(sequence)

    @classmethod
    def generar_sku_sugerido(
        cls,
        session: Session,
        producto: Producto,
        talla: str,
        color: str,
        excluding_variant_id: int | None = None,
    ) -> str:
        del producto, talla, color

        sequence = cls._get_or_create_sku_sequence(session)
        next_number = int(sequence.ultimo_numero) + 1
        while True:
            candidate = f"{sequence.prefijo}{next_number:0{sequence.padding}d}"
            statement = select(Variante).where(Variante.sku == candidate)
            if excluding_variant_id is not None:
                statement = statement.where(Variante.id != excluding_variant_id)
            existing = session.scalar(statement)
            if existing is None:
                return candidate
            next_number += 1

    @classmethod
    def normalizar_o_generar_sku(
        cls,
        session: Session,
        producto: Producto,
        sku: str | None,
        talla: str,
        color: str,
        excluding_variant_id: int | None = None,
    ) -> str:
        normalized = (sku or "").strip().upper()
        if normalized:
            cls._sync_sequence_with_manual_sku(session, normalized)
            return normalized
        generated = cls.generar_sku_sugerido(
            session=session,
            producto=producto,
            talla=talla,
            color=color,
            excluding_variant_id=excluding_variant_id,
        )
        cls._sync_sequence_with_manual_sku(session, generated)
        return generated

    @classmethod
    def preview_next_skus(cls, session: Session, count: int) -> list[str]:
        normalized_count = max(0, int(count))
        if normalized_count == 0:
            return []
        sequence = cls._get_or_create_sku_sequence(session)
        start_number = int(sequence.ultimo_numero) + 1
        return [
            f"{sequence.prefijo}{number:0{sequence.padding}d}"
            for number in range(start_number, start_number + normalized_count)
        ]

    @staticmethod
    def _validar_admin(usuario: Usuario) -> None:
        if not usuario.activo:
            raise PermissionError("El usuario no esta activo.")
        if usuario.rol != RolUsuario.ADMIN:
            raise PermissionError("Solo ADMIN puede modificar el catalogo.")

    @classmethod
    def crear_categoria(
        cls,
        session: Session,
        usuario: Usuario,
        nombre: str,
        descripcion: str | None = None,
    ) -> Categoria:
        cls._validar_admin(usuario)
        nombre = nombre.strip()
        if not nombre:
            raise ValueError("El nombre de la categoria es obligatorio.")

        existente = session.scalar(select(Categoria).where(Categoria.nombre == nombre))
        if existente is not None:
            raise ValueError("Ya existe una categoria con ese nombre.")

        categoria = Categoria(nombre=nombre, descripcion=descripcion or None)
        session.add(categoria)
        session.flush()
        cls._registrar_creacion(
            session,
            usuario,
            TipoEntidadCatalogo.CATEGORIA,
            categoria.id,
            cls._descripcion_categoria(categoria),
            "Categoria creada.",
        )
        return categoria

    @classmethod
    def crear_marca(
        cls,
        session: Session,
        usuario: Usuario,
        nombre: str,
        descripcion: str | None = None,
    ) -> Marca:
        cls._validar_admin(usuario)
        nombre = nombre.strip()
        if not nombre:
            raise ValueError("El nombre de la marca es obligatorio.")

        existente = session.scalar(select(Marca).where(Marca.nombre == nombre))
        if existente is not None:
            raise ValueError("Ya existe una marca con ese nombre.")

        marca = Marca(nombre=nombre, descripcion=descripcion or None)
        session.add(marca)
        session.flush()
        cls._registrar_creacion(
            session,
            usuario,
            TipoEntidadCatalogo.MARCA,
            marca.id,
            cls._descripcion_marca(marca),
            "Marca creada.",
        )
        return marca

    @classmethod
    def crear_producto(
        cls,
        session: Session,
        usuario: Usuario,
        categoria: Categoria,
        marca: Marca,
        nombre: str,
        descripcion: str | None = None,
        escuela: Escuela | None = None,
        tipo_prenda: TipoPrenda | None = None,
        tipo_pieza: TipoPieza | None = None,
        nivel_educativo: NivelEducativo | None = None,
        atributo: AtributoProducto | None = None,
        genero: str | None = None,
        escudo: str | None = None,
        ubicacion: str | None = None,
    ) -> Producto:
        cls._validar_admin(usuario)
        nombre_base = nombre.strip()
        if not nombre_base:
            raise ValueError("El nombre del producto es obligatorio.")
        display_name = cls._build_product_display_name(
            base_name=nombre_base,
            school=escuela,
            garment_type=tipo_prenda,
            piece_type=tipo_pieza,
        )

        existente = session.scalar(
            select(Producto).where(
                Producto.nombre == display_name,
                Producto.marca_id == marca.id,
            )
        )
        if existente is not None:
            raise ValueError("Ya existe un producto con ese nombre para la marca seleccionada.")

        producto = Producto(
            categoria=categoria,
            marca=marca,
            nombre=display_name,
            nombre_base=nombre_base,
            escuela=escuela,
            tipo_prenda=tipo_prenda,
            tipo_pieza=tipo_pieza,
            nivel_educativo=nivel_educativo,
            atributo=atributo,
            genero=(genero or "").strip() or None,
            escudo=(escudo or "").strip() or None,
            ubicacion=(ubicacion or "").strip() or None,
            descripcion=descripcion or None,
        )
        session.add(producto)
        session.flush()
        cls._registrar_creacion(
            session,
            usuario,
            TipoEntidadCatalogo.PRODUCTO,
            producto.id,
            cls._descripcion_producto(producto),
            "Producto creado.",
        )
        return producto

    @classmethod
    def actualizar_producto(
        cls,
        session: Session,
        usuario: Usuario,
        producto: Producto,
        categoria: Categoria,
        marca: Marca,
        nombre: str,
        descripcion: str | None = None,
        escuela: Escuela | None = None,
        tipo_prenda: TipoPrenda | None = None,
        tipo_pieza: TipoPieza | None = None,
        nivel_educativo: NivelEducativo | None = None,
        atributo: AtributoProducto | None = None,
        genero: str | None = None,
        escudo: str | None = None,
        ubicacion: str | None = None,
    ) -> Producto:
        cls._validar_admin(usuario)
        nombre_base = nombre.strip()
        if not nombre_base:
            raise ValueError("El nombre del producto es obligatorio.")
        display_name = cls._build_product_display_name(
            base_name=nombre_base,
            school=escuela,
            garment_type=tipo_prenda,
            piece_type=tipo_pieza,
        )

        existente = session.scalar(
            select(Producto).where(
                Producto.id != producto.id,
                Producto.nombre == display_name,
                Producto.marca_id == marca.id,
            )
        )
        if existente is not None:
            raise ValueError("Ya existe otro producto con ese nombre para la marca seleccionada.")

        valores_anteriores = {
            "categoria": producto.categoria.nombre,
            "marca": producto.marca.nombre,
            "nombre_base": producto.nombre_base,
            "nombre": producto.nombre,
            "descripcion": producto.descripcion,
            "escuela": cls._optional_name(producto.escuela),
            "tipo_prenda": cls._optional_name(producto.tipo_prenda),
            "tipo_pieza": cls._optional_name(producto.tipo_pieza),
            "nivel_educativo": cls._optional_name(producto.nivel_educativo),
            "atributo": cls._optional_name(producto.atributo),
            "genero": producto.genero,
            "escudo": producto.escudo,
            "ubicacion": producto.ubicacion,
        }
        producto.categoria = categoria
        producto.marca = marca
        producto.nombre = display_name
        producto.nombre_base = nombre_base
        producto.escuela = escuela
        producto.tipo_prenda = tipo_prenda
        producto.tipo_pieza = tipo_pieza
        producto.nivel_educativo = nivel_educativo
        producto.atributo = atributo
        producto.genero = (genero or "").strip() or None
        producto.escudo = (escudo or "").strip() or None
        producto.ubicacion = (ubicacion or "").strip() or None
        producto.descripcion = descripcion or None
        session.add(producto)
        cls._registrar_cambios(
            session=session,
            usuario=usuario,
            entidad_tipo=TipoEntidadCatalogo.PRODUCTO,
            entidad_id=producto.id,
            descripcion_entidad=cls._descripcion_producto(producto),
            valores_anteriores=valores_anteriores,
            valores_nuevos={
                "categoria": producto.categoria.nombre,
                "marca": producto.marca.nombre,
                "nombre_base": producto.nombre_base,
                "nombre": producto.nombre,
                "descripcion": producto.descripcion,
                "escuela": cls._optional_name(producto.escuela),
                "tipo_prenda": cls._optional_name(producto.tipo_prenda),
                "tipo_pieza": cls._optional_name(producto.tipo_pieza),
                "nivel_educativo": cls._optional_name(producto.nivel_educativo),
                "atributo": cls._optional_name(producto.atributo),
                "genero": producto.genero,
                "escudo": producto.escudo,
                "ubicacion": producto.ubicacion,
            },
        )
        return producto

    @classmethod
    def crear_variante(
        cls,
        session: Session,
        usuario: Usuario,
        producto: Producto,
        sku: str | None,
        talla: str,
        color: str,
        precio_venta: Decimal,
        costo_referencia: Decimal | None = None,
        stock_inicial: int = 0,
    ) -> Variante:
        cls._validar_admin(usuario)
        talla = talla.strip()
        color = color.strip() or "Sin color"
        sku = cls.normalizar_o_generar_sku(session, producto, sku, talla, color)

        if not sku or not talla or not color:
            raise ValueError("SKU, talla y color son obligatorios.")
        if precio_venta < 0:
            raise ValueError("El precio de venta no puede ser negativo.")
        if costo_referencia is not None and costo_referencia < 0:
            raise ValueError("El costo de referencia no puede ser negativo.")
        if stock_inicial < 0:
            raise ValueError("El stock inicial no puede ser negativo.")

        existente_sku = session.scalar(select(Variante).where(Variante.sku == sku))
        if existente_sku is not None:
            raise ValueError("Ya existe una variante con ese SKU.")

        existente_variante = session.scalar(
            select(Variante).where(
                Variante.producto_id == producto.id,
                Variante.talla == talla,
                Variante.color == color,
            )
        )
        if existente_variante is not None:
            raise ValueError("Ya existe una variante con esa talla y color para el producto.")

        variante = Variante(
            producto=producto,
            sku=sku,
            talla=talla,
            color=color,
            nombre_legacy=None,
            origen_legacy=False,
            precio_venta=precio_venta,
            costo_referencia=costo_referencia,
            stock_actual=0,
        )
        session.add(variante)
        session.flush()
        cls._registrar_creacion(
            session,
            usuario,
            TipoEntidadCatalogo.PRESENTACION,
            variante.id,
            cls._descripcion_presentacion(variante),
            "Presentacion creada.",
        )

        if stock_inicial > 0:
            InventarioService.registrar_ajuste_manual(
                session=session,
                variante=variante,
                cantidad=stock_inicial,
                usuario=usuario,
                referencia="ALTA-VARIANTE",
                observacion="Stock inicial al crear variante.",
            )

        return variante

    @classmethod
    def actualizar_variante(
        cls,
        session: Session,
        usuario: Usuario,
        variante: Variante,
        producto: Producto,
        sku: str | None,
        talla: str,
        color: str,
        precio_venta: Decimal,
        costo_referencia: Decimal | None = None,
    ) -> Variante:
        cls._validar_admin(usuario)
        talla = talla.strip()
        color = color.strip() or "Sin color"
        sku = cls.normalizar_o_generar_sku(
            session=session,
            producto=producto,
            sku=sku,
            talla=talla,
            color=color,
            excluding_variant_id=variante.id,
        )

        if not sku or not talla or not color:
            raise ValueError("SKU, talla y color son obligatorios.")
        if precio_venta < 0:
            raise ValueError("El precio de venta no puede ser negativo.")
        if costo_referencia is not None and costo_referencia < 0:
            raise ValueError("El costo de referencia no puede ser negativo.")
        if variante.origen_legacy and sku != variante.sku:
            raise ValueError("No se puede cambiar el SKU de una presentacion importada del legacy.")

        existente_sku = session.scalar(select(Variante).where(Variante.id != variante.id, Variante.sku == sku))
        if existente_sku is not None:
            raise ValueError("Ya existe otra variante con ese SKU.")

        existente_variante = session.scalar(
            select(Variante).where(
                Variante.id != variante.id,
                Variante.producto_id == producto.id,
                Variante.talla == talla,
                Variante.color == color,
            )
        )
        if existente_variante is not None:
            raise ValueError("Ya existe otra variante con esa talla y color para el producto seleccionado.")

        valores_anteriores = {
            "producto": variante.producto.nombre,
            "sku": variante.sku,
            "talla": variante.talla,
            "color": variante.color,
            "precio_venta": variante.precio_venta,
            "costo_referencia": variante.costo_referencia,
        }
        variante.producto = producto
        variante.sku = sku
        variante.talla = talla
        variante.color = color
        variante.precio_venta = precio_venta
        variante.costo_referencia = costo_referencia
        session.add(variante)
        cls._registrar_cambios(
            session=session,
            usuario=usuario,
            entidad_tipo=TipoEntidadCatalogo.PRESENTACION,
            entidad_id=variante.id,
            descripcion_entidad=cls._descripcion_presentacion(variante),
            valores_anteriores=valores_anteriores,
            valores_nuevos={
                "producto": variante.producto.nombre,
                "sku": variante.sku,
                "talla": variante.talla,
                "color": variante.color,
                "precio_venta": variante.precio_venta,
                "costo_referencia": variante.costo_referencia,
            },
        )
        return variante

    @classmethod
    def cambiar_estado_producto(
        cls,
        session: Session,
        usuario: Usuario,
        producto: Producto,
        activo: bool,
    ) -> Producto:
        cls._validar_admin(usuario)
        valor_anterior = producto.activo
        producto.activo = activo
        for variante in producto.variantes:
            variante_anterior = variante.activo
            variante.activo = activo
            session.add(variante)
            cls._registrar_cambios(
                session=session,
                usuario=usuario,
                entidad_tipo=TipoEntidadCatalogo.PRESENTACION,
                entidad_id=variante.id,
                descripcion_entidad=cls._descripcion_presentacion(variante),
                valores_anteriores={"activo": variante_anterior},
                valores_nuevos={"activo": variante.activo},
                accion_por_campo={"activo": TipoCambioCatalogo.ESTADO},
            )
        session.add(producto)
        cls._registrar_cambios(
            session=session,
            usuario=usuario,
            entidad_tipo=TipoEntidadCatalogo.PRODUCTO,
            entidad_id=producto.id,
            descripcion_entidad=cls._descripcion_producto(producto),
            valores_anteriores={"activo": valor_anterior},
            valores_nuevos={"activo": producto.activo},
            accion_por_campo={"activo": TipoCambioCatalogo.ESTADO},
        )
        return producto

    @classmethod
    def cambiar_estado_variante(
        cls,
        session: Session,
        usuario: Usuario,
        variante: Variante,
        activo: bool,
    ) -> Variante:
        cls._validar_admin(usuario)
        valor_anterior = variante.activo
        variante.activo = activo
        session.add(variante)
        cls._registrar_cambios(
            session=session,
            usuario=usuario,
            entidad_tipo=TipoEntidadCatalogo.PRESENTACION,
            entidad_id=variante.id,
            descripcion_entidad=cls._descripcion_presentacion(variante),
            valores_anteriores={"activo": valor_anterior},
            valores_nuevos={"activo": variante.activo},
            accion_por_campo={"activo": TipoCambioCatalogo.ESTADO},
        )
        return variante

    @classmethod
    def aplicar_cambio_masivo_precio(
        cls,
        session: Session,
        usuario: Usuario,
        *,
        referencia: str,
        motivo: str,
        observacion: str | None,
        precios_por_variante: list[tuple[int, Decimal]],
    ) -> dict[str, int]:
        cls._validar_admin(usuario)
        if not precios_por_variante:
            raise ValueError("No hay presentaciones para actualizar precio.")

        resumen = {
            "total_filas": len(precios_por_variante),
            "aplicadas": 0,
            "sin_cambios": 0,
            "suben": 0,
            "bajan": 0,
        }
        audit_note_parts = [f"Lote {referencia}"]
        motive_text = motivo.strip()
        if motive_text:
            audit_note_parts.append(motive_text)
        note_text = (observacion or "").strip()
        if note_text:
            audit_note_parts.append(note_text)
        audit_note = " | ".join(audit_note_parts)

        for variante_id, nuevo_precio in precios_por_variante:
            variante = session.get(Variante, int(variante_id))
            if variante is None:
                raise ValueError(f"La presentacion {variante_id} ya no existe.")
            precio_anterior = cls._money(variante.precio_venta)
            precio_nuevo = cls._money(nuevo_precio)
            if precio_nuevo < Decimal("0.00"):
                raise ValueError(f"El precio de {variante.sku} no puede ser negativo.")
            if precio_nuevo == precio_anterior:
                resumen["sin_cambios"] += 1
                continue

            variante.precio_venta = precio_nuevo
            session.add(variante)
            cls._registrar_cambios(
                session=session,
                usuario=usuario,
                entidad_tipo=TipoEntidadCatalogo.PRESENTACION,
                entidad_id=variante.id,
                descripcion_entidad=cls._descripcion_presentacion(variante),
                valores_anteriores={"precio_venta": precio_anterior},
                valores_nuevos={"precio_venta": precio_nuevo},
                observacion=audit_note,
            )
            resumen["aplicadas"] += 1
            if precio_nuevo > precio_anterior:
                resumen["suben"] += 1
            else:
                resumen["bajan"] += 1

        if resumen["aplicadas"] == 0:
            raise ValueError("El lote no genera cambios efectivos de precio.")
        return resumen

    @staticmethod
    def _validar_variante_eliminable(session: Session, variante: Variante) -> None:
        if variante.stock_actual != 0:
            raise ValueError("No se puede eliminar una presentacion con stock. Primero deja el stock en 0.")

        movimientos = session.scalar(
            select(func.count(MovimientoInventario.id)).where(MovimientoInventario.variante_id == variante.id)
        ) or 0
        if movimientos:
            raise ValueError("No se puede eliminar una presentacion con movimientos de inventario. Desactiva en su lugar.")

        compras = session.scalar(
            select(func.count(CompraDetalle.id)).where(CompraDetalle.variante_id == variante.id)
        ) or 0
        if compras:
            raise ValueError("No se puede eliminar una presentacion con historial de compras. Desactiva en su lugar.")

        ventas = session.scalar(
            select(func.count(VentaDetalle.id)).where(VentaDetalle.variante_id == variante.id)
        ) or 0
        if ventas:
            raise ValueError("No se puede eliminar una presentacion con historial de ventas. Desactiva en su lugar.")

    @classmethod
    def eliminar_variante(cls, session: Session, usuario: Usuario, variante: Variante) -> None:
        cls._validar_admin(usuario)
        cls._validar_variante_eliminable(session, variante)
        cls._registrar_eliminacion(
            session,
            usuario,
            TipoEntidadCatalogo.PRESENTACION,
            variante.id,
            cls._descripcion_presentacion(variante),
            "Presentacion eliminada.",
        )
        session.delete(variante)

    @classmethod
    def eliminar_producto(cls, session: Session, usuario: Usuario, producto: Producto) -> None:
        cls._validar_admin(usuario)
        session.refresh(producto)
        variantes = list(producto.variantes)
        if not variantes:
            session.delete(producto)
            return

        for variante in variantes:
            cls._validar_variante_eliminable(session, variante)
            cls._registrar_eliminacion(
                session,
                usuario,
                TipoEntidadCatalogo.PRESENTACION,
                variante.id,
                cls._descripcion_presentacion(variante),
                "Presentacion eliminada junto con su producto.",
            )

        cls._registrar_eliminacion(
            session,
            usuario,
            TipoEntidadCatalogo.PRODUCTO,
            producto.id,
            cls._descripcion_producto(producto),
            "Producto eliminado.",
        )
        session.delete(producto)
