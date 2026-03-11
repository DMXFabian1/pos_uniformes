"""Modelos ORM para catalogo, inventario, compras, ventas y seguridad."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import CheckConstraint, DateTime, Enum as SqlEnum
from sqlalchemy import ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pos_uniformes.database.connection import Base


class TipoMovimientoInventario(str, Enum):
    ENTRADA_COMPRA = "ENTRADA_COMPRA"
    SALIDA_VENTA = "SALIDA_VENTA"
    AJUSTE_ENTRADA = "AJUSTE_ENTRADA"
    AJUSTE_SALIDA = "AJUSTE_SALIDA"
    CANCELACION_VENTA = "CANCELACION_VENTA"
    APARTADO_RESERVA = "APARTADO_RESERVA"
    APARTADO_LIBERACION = "APARTADO_LIBERACION"


class RolUsuario(str, Enum):
    ADMIN = "ADMIN"
    CAJERO = "CAJERO"


class EstadoCompra(str, Enum):
    BORRADOR = "BORRADOR"
    CONFIRMADA = "CONFIRMADA"
    CANCELADA = "CANCELADA"


class EstadoVenta(str, Enum):
    BORRADOR = "BORRADOR"
    CONFIRMADA = "CONFIRMADA"
    CANCELADA = "CANCELADA"


class EstadoApartado(str, Enum):
    ACTIVO = "ACTIVO"
    LIQUIDADO = "LIQUIDADO"
    ENTREGADO = "ENTREGADO"
    CANCELADO = "CANCELADO"


class TipoEntidadCatalogo(str, Enum):
    CATEGORIA = "CATEGORIA"
    MARCA = "MARCA"
    PRODUCTO = "PRODUCTO"
    PRESENTACION = "PRESENTACION"


class TipoCambioCatalogo(str, Enum):
    CREACION = "CREACION"
    ACTUALIZACION = "ACTUALIZACION"
    ESTADO = "ESTADO"
    ELIMINACION = "ELIMINACION"


class TipoMovimientoCaja(str, Enum):
    REACTIVO = "REACTIVO"
    INGRESO = "INGRESO"
    RETIRO = "RETIRO"


class Usuario(Base):
    __tablename__ = "usuario"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(60), unique=True, nullable=False, index=True)
    nombre_completo: Mapped[str] = mapped_column(String(150), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    rol: Mapped[RolUsuario] = mapped_column(
        SqlEnum(RolUsuario, name="rol_usuario"),
        nullable=False,
        index=True,
    )
    activo: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    compras: Mapped[list["Compra"]] = relationship(back_populates="usuario")
    ventas: Mapped[list["Venta"]] = relationship(
        back_populates="usuario",
        foreign_keys="Venta.usuario_id",
    )
    ventas_canceladas: Mapped[list["Venta"]] = relationship(
        back_populates="cancelado_por",
        foreign_keys="Venta.cancelado_por_id",
    )
    apartados: Mapped[list["Apartado"]] = relationship(
        back_populates="usuario",
        foreign_keys="Apartado.usuario_id",
    )
    apartados_cancelados: Mapped[list["Apartado"]] = relationship(
        back_populates="cancelado_por",
        foreign_keys="Apartado.cancelado_por_id",
    )
    apartados_entregados: Mapped[list["Apartado"]] = relationship(
        back_populates="entregado_por",
        foreign_keys="Apartado.entregado_por_id",
    )
    apartados_abonos: Mapped[list["ApartadoAbono"]] = relationship(back_populates="usuario")
    cajas_abiertas: Mapped[list["SesionCaja"]] = relationship(
        back_populates="abierta_por",
        foreign_keys="SesionCaja.abierta_por_id",
    )
    cajas_cerradas: Mapped[list["SesionCaja"]] = relationship(
        back_populates="cerrada_por",
        foreign_keys="SesionCaja.cerrada_por_id",
    )
    movimientos_caja: Mapped[list["MovimientoCaja"]] = relationship(back_populates="usuario")
    cambios_catalogo: Mapped[list["CambioCatalogo"]] = relationship(back_populates="usuario")


class ConfiguracionNegocio(Base):
    __tablename__ = "configuracion_negocio"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre_negocio: Mapped[str] = mapped_column(String(160), nullable=False, default="POS Uniformes")
    telefono: Mapped[str | None] = mapped_column(String(40))
    direccion: Mapped[str | None] = mapped_column(Text())
    pie_ticket: Mapped[str | None] = mapped_column(Text())
    transferencia_banco: Mapped[str | None] = mapped_column(String(120))
    transferencia_beneficiario: Mapped[str | None] = mapped_column(String(160))
    transferencia_clabe: Mapped[str | None] = mapped_column(String(40))
    transferencia_instrucciones: Mapped[str | None] = mapped_column(Text())
    whatsapp_apartado_recordatorio: Mapped[str | None] = mapped_column(Text())
    whatsapp_apartado_liquidado: Mapped[str | None] = mapped_column(Text())
    whatsapp_cliente_promocion: Mapped[str | None] = mapped_column(Text())
    whatsapp_cliente_seguimiento: Mapped[str | None] = mapped_column(Text())
    whatsapp_cliente_saludo: Mapped[str | None] = mapped_column(Text())
    impresora_preferida: Mapped[str | None] = mapped_column(String(200))
    copias_ticket: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class SesionCaja(Base):
    __tablename__ = "sesion_caja"

    id: Mapped[int] = mapped_column(primary_key=True)
    abierta_por_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"), nullable=False, index=True)
    cerrada_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"), index=True)
    monto_apertura: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    monto_cierre_declarado: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    monto_esperado_cierre: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    diferencia_cierre: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    observacion_apertura: Mapped[str | None] = mapped_column(Text())
    observacion_cierre: Mapped[str | None] = mapped_column(Text())
    abierta_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    cerrada_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    abierta_por: Mapped["Usuario"] = relationship(
        back_populates="cajas_abiertas",
        foreign_keys=[abierta_por_id],
    )
    cerrada_por: Mapped["Usuario | None"] = relationship(
        back_populates="cajas_cerradas",
        foreign_keys=[cerrada_por_id],
    )
    movimientos: Mapped[list["MovimientoCaja"]] = relationship(
        back_populates="sesion_caja",
        cascade="all, delete-orphan",
        order_by="MovimientoCaja.created_at.desc()",
    )


class MovimientoCaja(Base):
    __tablename__ = "movimiento_caja"

    id: Mapped[int] = mapped_column(primary_key=True)
    sesion_caja_id: Mapped[int] = mapped_column(ForeignKey("sesion_caja.id"), nullable=False, index=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"), nullable=False, index=True)
    tipo: Mapped[TipoMovimientoCaja] = mapped_column(
        SqlEnum(TipoMovimientoCaja, name="tipo_movimiento_caja"),
        nullable=False,
        index=True,
    )
    monto: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    concepto: Mapped[str | None] = mapped_column(Text())
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    sesion_caja: Mapped["SesionCaja"] = relationship(back_populates="movimientos")
    usuario: Mapped["Usuario"] = relationship(back_populates="movimientos_caja")


class Proveedor(Base):
    __tablename__ = "proveedor"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(150), unique=True, nullable=False, index=True)
    telefono: Mapped[str | None] = mapped_column(String(30))
    email: Mapped[str | None] = mapped_column(String(120))
    direccion: Mapped[str | None] = mapped_column(Text())
    activo: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    compras: Mapped[list["Compra"]] = relationship(back_populates="proveedor")


class Cliente(Base):
    __tablename__ = "cliente"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo_cliente: Mapped[str] = mapped_column(String(30), nullable=False, unique=True, index=True)
    nombre: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    telefono: Mapped[str | None] = mapped_column(String(40), index=True)
    email: Mapped[str | None] = mapped_column(String(120))
    direccion: Mapped[str | None] = mapped_column(Text())
    notas: Mapped[str | None] = mapped_column(Text())
    activo: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    apartados: Mapped[list["Apartado"]] = relationship(back_populates="cliente")
    ventas: Mapped[list["Venta"]] = relationship(back_populates="cliente")


class Categoria(Base):
    __tablename__ = "categoria"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    descripcion: Mapped[str | None] = mapped_column(Text())
    activo: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    productos: Mapped[list["Producto"]] = relationship(back_populates="categoria")


class Marca(Base):
    __tablename__ = "marca"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    descripcion: Mapped[str | None] = mapped_column(Text())
    activo: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    productos: Mapped[list["Producto"]] = relationship(back_populates="marca")


class Escuela(Base):
    __tablename__ = "escuela"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(150), unique=True, nullable=False, index=True)
    activo: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    productos: Mapped[list["Producto"]] = relationship(back_populates="escuela")


class TipoPrenda(Base):
    __tablename__ = "tipo_prenda"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    activo: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    productos: Mapped[list["Producto"]] = relationship(back_populates="tipo_prenda")


class TipoPieza(Base):
    __tablename__ = "tipo_pieza"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    activo: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    productos: Mapped[list["Producto"]] = relationship(back_populates="tipo_pieza")


class NivelEducativo(Base):
    __tablename__ = "nivel_educativo"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    activo: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    productos: Mapped[list["Producto"]] = relationship(back_populates="nivel_educativo")


class AtributoProducto(Base):
    __tablename__ = "atributo_producto"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    activo: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    productos: Mapped[list["Producto"]] = relationship(back_populates="atributo")


class SkuSequence(Base):
    __tablename__ = "sku_sequence"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    prefijo: Mapped[str] = mapped_column(String(20), nullable=False, default="SKU")
    padding: Mapped[int] = mapped_column(Integer, nullable=False, default=6)
    ultimo_numero: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class CambioCatalogo(Base):
    __tablename__ = "cambio_catalogo"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuario.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    entidad_tipo: Mapped[TipoEntidadCatalogo] = mapped_column(
        SqlEnum(TipoEntidadCatalogo, name="tipo_entidad_catalogo"),
        nullable=False,
        index=True,
    )
    entidad_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    accion: Mapped[TipoCambioCatalogo] = mapped_column(
        SqlEnum(TipoCambioCatalogo, name="tipo_cambio_catalogo"),
        nullable=False,
        index=True,
    )
    campo: Mapped[str] = mapped_column(String(80), nullable=False)
    valor_anterior: Mapped[str | None] = mapped_column(Text())
    valor_nuevo: Mapped[str | None] = mapped_column(Text())
    descripcion_entidad: Mapped[str] = mapped_column(String(200), nullable=False)
    observacion: Mapped[str | None] = mapped_column(Text())
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    usuario: Mapped["Usuario"] = relationship(back_populates="cambios_catalogo")


class Producto(Base):
    __tablename__ = "producto"
    __table_args__ = (
        UniqueConstraint("marca_id", "nombre", name="producto_nombre_marca_unico"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    categoria_id: Mapped[int] = mapped_column(
        ForeignKey("categoria.id", ondelete="RESTRICT"),
        nullable=False,
    )
    marca_id: Mapped[int] = mapped_column(
        ForeignKey("marca.id", ondelete="RESTRICT"),
        nullable=False,
    )
    nombre: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    nombre_base: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    escuela_id: Mapped[int | None] = mapped_column(
        ForeignKey("escuela.id", ondelete="RESTRICT"),
        index=True,
    )
    tipo_prenda_id: Mapped[int | None] = mapped_column(
        ForeignKey("tipo_prenda.id", ondelete="RESTRICT"),
        index=True,
    )
    tipo_pieza_id: Mapped[int | None] = mapped_column(
        ForeignKey("tipo_pieza.id", ondelete="RESTRICT"),
        index=True,
    )
    nivel_educativo_id: Mapped[int | None] = mapped_column(
        ForeignKey("nivel_educativo.id", ondelete="RESTRICT"),
        index=True,
    )
    atributo_id: Mapped[int | None] = mapped_column(
        ForeignKey("atributo_producto.id", ondelete="RESTRICT"),
        index=True,
    )
    genero: Mapped[str | None] = mapped_column(String(50), index=True)
    escudo: Mapped[str | None] = mapped_column(String(120))
    ubicacion: Mapped[str | None] = mapped_column(String(120))
    descripcion: Mapped[str | None] = mapped_column(Text())
    activo: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    categoria: Mapped["Categoria"] = relationship(back_populates="productos")
    marca: Mapped["Marca"] = relationship(back_populates="productos")
    escuela: Mapped["Escuela | None"] = relationship(back_populates="productos")
    tipo_prenda: Mapped["TipoPrenda | None"] = relationship(back_populates="productos")
    tipo_pieza: Mapped["TipoPieza | None"] = relationship(back_populates="productos")
    nivel_educativo: Mapped["NivelEducativo | None"] = relationship(back_populates="productos")
    atributo: Mapped["AtributoProducto | None"] = relationship(back_populates="productos")
    variantes: Mapped[list["Variante"]] = relationship(
        back_populates="producto",
        cascade="all, delete-orphan",
    )


class Variante(Base):
    __tablename__ = "variante"
    __table_args__ = (
        UniqueConstraint("producto_id", "talla", "color", name="producto_talla_color_unico"),
        CheckConstraint("stock_actual >= 0", name="variante_stock_actual_no_negativo"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    producto_id: Mapped[int] = mapped_column(
        ForeignKey("producto.id", ondelete="CASCADE"),
        nullable=False,
    )
    sku: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    talla: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    color: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    nombre_legacy: Mapped[str | None] = mapped_column(String(220), index=True)
    origen_legacy: Mapped[bool] = mapped_column(default=False, nullable=False)
    legacy_last_modified: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    precio_venta: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    costo_referencia: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    stock_actual: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    activo: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    producto: Mapped["Producto"] = relationship(back_populates="variantes")
    movimientos_inventario: Mapped[list["MovimientoInventario"]] = relationship(
        back_populates="variante",
        cascade="all, delete-orphan",
        order_by="MovimientoInventario.created_at.desc()",
    )
    compras_detalle: Mapped[list["CompraDetalle"]] = relationship(back_populates="variante")
    ventas_detalle: Mapped[list["VentaDetalle"]] = relationship(back_populates="variante")
    apartados_detalle: Mapped[list["ApartadoDetalle"]] = relationship(back_populates="variante")
    assets: Mapped[list["ProductoAsset"]] = relationship(
        back_populates="variante",
        cascade="all, delete-orphan",
    )


class ProductoAsset(Base):
    __tablename__ = "producto_asset"
    __table_args__ = (
        UniqueConstraint(
            "variante_id",
            "tipo",
            "es_legacy",
            "ruta",
            name="producto_asset_variante_tipo_ruta_unico",
        ),
        CheckConstraint(
            "tipo IN ('QR', 'LABEL_SPLIT', 'IMAGE')",
            name="producto_asset_tipo_valido",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    variante_id: Mapped[int] = mapped_column(
        ForeignKey("variante.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tipo: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    ruta: Mapped[str] = mapped_column(Text(), nullable=False)
    es_legacy: Mapped[bool] = mapped_column(default=False, nullable=False, index=True)
    checksum: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    variante: Mapped["Variante"] = relationship(back_populates="assets")


class MovimientoInventario(Base):
    __tablename__ = "movimiento_inventario"
    __table_args__ = (
        CheckConstraint("cantidad <> 0", name="movimiento_inventario_cantidad_no_cero"),
        CheckConstraint("stock_posterior >= 0", name="movimiento_inventario_stock_posterior_no_negativo"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    variante_id: Mapped[int] = mapped_column(
        ForeignKey("variante.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    tipo_movimiento: Mapped[TipoMovimientoInventario] = mapped_column(
        SqlEnum(TipoMovimientoInventario, name="tipo_movimiento_inventario"),
        nullable=False,
        index=True,
    )
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)
    stock_anterior: Mapped[int] = mapped_column(Integer, nullable=False)
    stock_posterior: Mapped[int] = mapped_column(Integer, nullable=False)
    referencia: Mapped[str | None] = mapped_column(String(120))
    observacion: Mapped[str | None] = mapped_column(Text())
    creado_por: Mapped[str] = mapped_column(String(60), default="SYSTEM", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    variante: Mapped["Variante"] = relationship(back_populates="movimientos_inventario")


class Compra(Base):
    __tablename__ = "compra"

    id: Mapped[int] = mapped_column(primary_key=True)
    proveedor_id: Mapped[int] = mapped_column(
        ForeignKey("proveedor.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuario.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    numero_documento: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)
    estado: Mapped[EstadoCompra] = mapped_column(
        SqlEnum(EstadoCompra, name="estado_compra"),
        default=EstadoCompra.BORRADOR,
        nullable=False,
        index=True,
    )
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    observacion: Mapped[str | None] = mapped_column(Text())
    confirmada_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    proveedor: Mapped["Proveedor"] = relationship(back_populates="compras")
    usuario: Mapped["Usuario"] = relationship(back_populates="compras")
    detalles: Mapped[list["CompraDetalle"]] = relationship(
        back_populates="compra",
        cascade="all, delete-orphan",
    )


class CompraDetalle(Base):
    __tablename__ = "compra_detalle"
    __table_args__ = (
        CheckConstraint("cantidad > 0", name="compra_detalle_cantidad_positiva"),
        CheckConstraint("costo_unitario >= 0", name="compra_detalle_costo_unitario_no_negativo"),
        UniqueConstraint("compra_id", "variante_id", name="compra_detalle_variante_unica"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    compra_id: Mapped[int] = mapped_column(
        ForeignKey("compra.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    variante_id: Mapped[int] = mapped_column(
        ForeignKey("variante.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)
    costo_unitario: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    subtotal_linea: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    compra: Mapped["Compra"] = relationship(back_populates="detalles")
    variante: Mapped["Variante"] = relationship(back_populates="compras_detalle")


class Venta(Base):
    __tablename__ = "venta"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuario.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    cancelado_por_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuario.id", ondelete="RESTRICT"),
        index=True,
    )
    cliente_id: Mapped[int | None] = mapped_column(
        ForeignKey("cliente.id", ondelete="SET NULL"),
        index=True,
    )
    folio: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)
    estado: Mapped[EstadoVenta] = mapped_column(
        SqlEnum(EstadoVenta, name="estado_venta"),
        default=EstadoVenta.BORRADOR,
        nullable=False,
        index=True,
    )
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    observacion: Mapped[str | None] = mapped_column(Text())
    confirmada_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelada_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    usuario: Mapped["Usuario"] = relationship(
        back_populates="ventas",
        foreign_keys=[usuario_id],
    )
    cancelado_por: Mapped["Usuario | None"] = relationship(
        back_populates="ventas_canceladas",
        foreign_keys=[cancelado_por_id],
    )
    cliente: Mapped["Cliente | None"] = relationship(back_populates="ventas")
    detalles: Mapped[list["VentaDetalle"]] = relationship(
        back_populates="venta",
        cascade="all, delete-orphan",
    )


class VentaDetalle(Base):
    __tablename__ = "venta_detalle"
    __table_args__ = (
        CheckConstraint("cantidad > 0", name="venta_detalle_cantidad_positiva"),
        CheckConstraint("precio_unitario >= 0", name="venta_detalle_precio_unitario_no_negativo"),
        UniqueConstraint("venta_id", "variante_id", name="venta_detalle_variante_unica"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    venta_id: Mapped[int] = mapped_column(
        ForeignKey("venta.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    variante_id: Mapped[int] = mapped_column(
        ForeignKey("variante.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)
    precio_unitario: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    subtotal_linea: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    venta: Mapped["Venta"] = relationship(back_populates="detalles")
    variante: Mapped["Variante"] = relationship(back_populates="ventas_detalle")


class Apartado(Base):
    __tablename__ = "apartado"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuario.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    cancelado_por_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuario.id", ondelete="RESTRICT"),
        index=True,
    )
    entregado_por_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuario.id", ondelete="RESTRICT"),
        index=True,
    )
    cliente_id: Mapped[int | None] = mapped_column(
        ForeignKey("cliente.id", ondelete="SET NULL"),
        index=True,
    )
    folio: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)
    cliente_nombre: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    cliente_telefono: Mapped[str | None] = mapped_column(String(40))
    estado: Mapped[EstadoApartado] = mapped_column(
        SqlEnum(EstadoApartado, name="estado_apartado"),
        default=EstadoApartado.ACTIVO,
        nullable=False,
        index=True,
    )
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    total_abonado: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    saldo_pendiente: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    fecha_compromiso: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    observacion: Mapped[str | None] = mapped_column(Text())
    liquidado_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    entregado_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelado_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    usuario: Mapped["Usuario"] = relationship(
        back_populates="apartados",
        foreign_keys=[usuario_id],
    )
    cancelado_por: Mapped["Usuario | None"] = relationship(
        back_populates="apartados_cancelados",
        foreign_keys=[cancelado_por_id],
    )
    entregado_por: Mapped["Usuario | None"] = relationship(
        back_populates="apartados_entregados",
        foreign_keys=[entregado_por_id],
    )
    cliente: Mapped["Cliente | None"] = relationship(back_populates="apartados")
    detalles: Mapped[list["ApartadoDetalle"]] = relationship(
        back_populates="apartado",
        cascade="all, delete-orphan",
    )
    abonos: Mapped[list["ApartadoAbono"]] = relationship(
        back_populates="apartado",
        cascade="all, delete-orphan",
        order_by="desc(ApartadoAbono.created_at)",
    )


class ApartadoDetalle(Base):
    __tablename__ = "apartado_detalle"
    __table_args__ = (
        CheckConstraint("cantidad > 0", name="apartado_detalle_cantidad_positiva"),
        CheckConstraint("precio_unitario >= 0", name="apartado_detalle_precio_unitario_no_negativo"),
        UniqueConstraint("apartado_id", "variante_id", name="apartado_detalle_variante_unica"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    apartado_id: Mapped[int] = mapped_column(
        ForeignKey("apartado.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    variante_id: Mapped[int] = mapped_column(
        ForeignKey("variante.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)
    precio_unitario: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    subtotal_linea: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    apartado: Mapped["Apartado"] = relationship(back_populates="detalles")
    variante: Mapped["Variante"] = relationship(back_populates="apartados_detalle")


class ApartadoAbono(Base):
    __tablename__ = "apartado_abono"
    __table_args__ = (
        CheckConstraint("monto > 0", name="apartado_abono_monto_positivo"),
        CheckConstraint(
            "monto_efectivo IS NULL OR monto_efectivo >= 0",
            name="apartado_abono_monto_efectivo_no_negativo",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    apartado_id: Mapped[int] = mapped_column(
        ForeignKey("apartado.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuario.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    monto: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    metodo_pago: Mapped[str | None] = mapped_column(String(30))
    monto_efectivo: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    referencia: Mapped[str | None] = mapped_column(String(120))
    observacion: Mapped[str | None] = mapped_column(Text())
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    apartado: Mapped["Apartado"] = relationship(back_populates="abonos")
    usuario: Mapped["Usuario"] = relationship(back_populates="apartados_abonos")
