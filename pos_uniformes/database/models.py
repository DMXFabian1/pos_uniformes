"""Modelos ORM para catalogo, inventario, compras, ventas y seguridad."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import CheckConstraint, DateTime, Enum as SqlEnum
from sqlalchemy import Date, JSON, Boolean, ForeignKey, Integer, LargeBinary, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
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


class TipoMovimientoBodega(str, Enum):
    INGRESO = "INGRESO"
    RETIRO = "RETIRO"
    TRANSFERENCIA = "TRANSFERENCIA"
    MOVER_CAJA = "MOVER_CAJA"
    CREAR_CAJA = "CREAR_CAJA"
    AJUSTE = "AJUSTE"
    CORRECCION = "CORRECCION"


class CategoriaCaja(str, Enum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"


CATEGORIA_CAJA_LABELS: dict[str, str] = {
    "A": "Alta rotación",
    "B": "Excedentes escuelas",
    "C": "Temporada",
    "D": "Descatalogado",
}


class EstadoCaja(str, Enum):
    ACTIVA = "ACTIVA"
    VACIA = "VACIA"
    CERRADA = "CERRADA"


class RolUsuario(str, Enum):
    ADMIN = "ADMIN"
    CAJERO = "CAJERO"


class TipoCliente(str, Enum):
    GENERAL = "GENERAL"
    PROFESOR = "PROFESOR"
    MAYORISTA = "MAYORISTA"


class NivelLealtad(str, Enum):
    BASICO = "BASICO"
    LEAL = "LEAL"
    PROFESOR = "PROFESOR"
    MAYORISTA = "MAYORISTA"


class EstadoCompra(str, Enum):
    BORRADOR = "BORRADOR"
    CONFIRMADA = "CONFIRMADA"
    CANCELADA = "CANCELADA"


class EstadoVenta(str, Enum):
    BORRADOR = "BORRADOR"
    CONFIRMADA = "CONFIRMADA"
    CANCELADA = "CANCELADA"


class ModoOrigenVenta(str, Enum):
    UNASSIGNED = "UNASSIGNED"
    EMPLOYEE = "EMPLOYEE"
    OPERATOR_DIRECT = "OPERATOR_DIRECT"


class EstadoApartado(str, Enum):
    ACTIVO = "ACTIVO"
    LIQUIDADO = "LIQUIDADO"
    ENTREGADO = "ENTREGADO"
    CANCELADO = "CANCELADO"


class EstadoPresupuesto(str, Enum):
    BORRADOR = "BORRADOR"
    EMITIDO = "EMITIDO"
    CANCELADO = "CANCELADO"
    CONVERTIDO = "CONVERTIDO"


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
    apartados_abonos: Mapped[list["ApartadoAbono"]] = relationship(
        back_populates="usuario",
        foreign_keys="ApartadoAbono.usuario_id",
    )
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
    cambios_marketing: Mapped[list["CambioMarketingConfiguracion"]] = relationship(
        back_populates="usuario",
        foreign_keys="CambioMarketingConfiguracion.usuario_id",
        order_by="desc(CambioMarketingConfiguracion.created_at)",
    )
    promociones_manual_autorizadas: Mapped[list["AutorizacionPromocionManual"]] = relationship(
        back_populates="usuario",
        foreign_keys="AutorizacionPromocionManual.usuario_id",
        order_by="desc(AutorizacionPromocionManual.created_at)",
    )
    presupuestos: Mapped[list["Presupuesto"]] = relationship(back_populates="usuario")


class ConfiguracionNegocio(Base):
    __tablename__ = "configuracion_negocio"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre_negocio: Mapped[str] = mapped_column(String(160), nullable=False, default="POS Uniformes")
    logo_path: Mapped[str | None] = mapped_column(Text())
    loyalty_review_window_days: Mapped[int] = mapped_column(Integer, nullable=False, default=365)
    leal_spend_threshold: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("3000.00"))
    leal_purchase_count_threshold: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    leal_purchase_sum_threshold: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("2000.00"),
    )
    discount_basico: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=Decimal("5.00"))
    discount_leal: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=Decimal("10.00"))
    discount_profesor: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=Decimal("15.00"))
    discount_mayorista: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=Decimal("20.00"))
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
    impresora_tickets: Mapped[str | None] = mapped_column(String(200))
    copias_ticket: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # Frecuencia de conteo de "productos básicos" (sin escuela). NULL = usar el
    # default global. Es global porque los básicos no pertenecen a una escuela.
    dias_vigencia_basicos: Mapped[int | None] = mapped_column(Integer)
    promo_authorization_code_hash: Mapped[str | None] = mapped_column(String(255))
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
    tipo_cliente: Mapped[TipoCliente] = mapped_column(
        SqlEnum(TipoCliente, name="tipo_cliente"),
        default=TipoCliente.GENERAL,
        nullable=False,
        index=True,
    )
    descuento_preferente: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0.00"), nullable=False)
    nivel_lealtad: Mapped[NivelLealtad] = mapped_column(
        SqlEnum(NivelLealtad, name="nivel_lealtad"),
        default=NivelLealtad.BASICO,
        nullable=False,
        index=True,
    )
    telefono: Mapped[str | None] = mapped_column(String(40), index=True)
    cliente_desde: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    nivel_asignado_por_user_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"), index=True)
    nivel_asignado_por_rol: Mapped[str | None] = mapped_column(String(20))
    nivel_asignacion_motivo: Mapped[str | None] = mapped_column(String(255))
    card_image_path: Mapped[str | None] = mapped_column(Text())
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
    promociones_manual_autorizadas: Mapped[list["AutorizacionPromocionManual"]] = relationship(
        back_populates="cliente",
        order_by="desc(AutorizacionPromocionManual.created_at)",
    )
    presupuestos: Mapped[list["Presupuesto"]] = relationship(back_populates="cliente")


class Empleada(Base):
    __tablename__ = "empleada"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)
    nombre_completo: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    pin_hash: Mapped[str | None] = mapped_column(String(255))
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


class AutorizacionPromocionManual(Base):
    __tablename__ = "autorizacion_promocion_manual"

    id: Mapped[int] = mapped_column(primary_key=True)
    venta_id: Mapped[int | None] = mapped_column(
        ForeignKey("venta.id", ondelete="SET NULL"),
        index=True,
    )
    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuario.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    cliente_id: Mapped[int | None] = mapped_column(
        ForeignKey("cliente.id", ondelete="SET NULL"),
        index=True,
    )
    rol_usuario: Mapped[str | None] = mapped_column(String(20))
    folio_venta: Mapped[str | None] = mapped_column(String(40), index=True)
    porcentaje_lealtad: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=Decimal("0.00"))
    porcentaje_promocion: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),
    )
    porcentaje_aplicado: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=Decimal("0.00"))
    origen_aplicado: Mapped[str] = mapped_column(String(40), nullable=False, default="SIN_DESCUENTO")
    observacion: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    venta: Mapped["Venta | None"] = relationship(back_populates="promociones_manual_autorizadas")
    usuario: Mapped["Usuario"] = relationship(back_populates="promociones_manual_autorizadas")
    cliente: Mapped["Cliente | None"] = relationship(back_populates="promociones_manual_autorizadas")


class CambioMarketingConfiguracion(Base):
    __tablename__ = "cambio_marketing_configuracion"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuario.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    rol_usuario: Mapped[str | None] = mapped_column(String(20))
    seccion: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    campo: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    etiqueta_campo: Mapped[str] = mapped_column(String(120), nullable=False)
    valor_anterior: Mapped[str | None] = mapped_column(Text())
    valor_nuevo: Mapped[str | None] = mapped_column(Text())
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    usuario: Mapped["Usuario"] = relationship(back_populates="cambios_marketing")


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
        CheckConstraint("stock_actual >= -1", name="variante_stock_actual_no_negativo"),
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
    stock_minimo: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ultimo_conteo_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    disponibilidad_oculta: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    bodega_contenidos: Mapped[list["BodegaContenido"]] = relationship(
        "BodegaContenido", viewonly=True, lazy="noload",
    )

    @property
    def stock_piso(self) -> int:
        if not self.bodega_contenidos:
            return 0
        return sum(
            c.cantidad for c in self.bodega_contenidos
            if c.caja and c.caja.ubicacion and c.caja.ubicacion.rack.upper() == "PISO"
        )

    @property
    def stock_bodega(self) -> int:
        if not self.bodega_contenidos:
            return 0
        return sum(
            c.cantidad for c in self.bodega_contenidos
            if c.caja and c.caja.ubicacion and c.caja.ubicacion.rack.upper() != "PISO"
        )

    @property
    def stock_tienda(self) -> int:
        return self.stock_actual - self.stock_piso - self.stock_bodega
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
    presupuestos_detalle: Mapped[list["PresupuestoDetalle"]] = relationship(back_populates="variante")
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


class ImportacionCatalogo(Base):
    __tablename__ = "importacion_catalogo"

    id: Mapped[int] = mapped_column(primary_key=True)
    fuente_nombre: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    fuente_ruta: Mapped[str] = mapped_column(Text(), nullable=False)
    reporte_ruta: Mapped[str | None] = mapped_column(Text())
    filas_leidas: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    familias_creadas: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    variantes_creadas: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    assets_creados: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    movimientos_stock_creados: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duplicados_fallback: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_sku_legacy: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    observaciones: Mapped[str | None] = mapped_column(Text())
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    filas: Mapped[list["ImportacionCatalogoFila"]] = relationship(
        back_populates="importacion",
        cascade="all, delete-orphan",
    )
    incidencias: Mapped[list["ImportacionCatalogoIncidencia"]] = relationship(
        back_populates="importacion",
        cascade="all, delete-orphan",
    )


class ImportacionCatalogoFila(Base):
    __tablename__ = "importacion_catalogo_fila"
    __table_args__ = (
        UniqueConstraint("importacion_id", "legacy_sku", name="importacion_catalogo_fila_sku_unico"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    importacion_id: Mapped[int] = mapped_column(
        ForeignKey("importacion_catalogo.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    legacy_sku: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    legacy_nombre: Mapped[str] = mapped_column(String(220), nullable=False)
    legacy_nombre_base: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    legacy_talla: Mapped[str] = mapped_column(String(30), nullable=False)
    legacy_color: Mapped[str] = mapped_column(String(50), nullable=False)
    legacy_precio: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    legacy_inventario: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    legacy_last_modified: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    producto_id: Mapped[int | None] = mapped_column(ForeignKey("producto.id", ondelete="SET NULL"), index=True)
    variante_id: Mapped[int | None] = mapped_column(ForeignKey("variante.id", ondelete="SET NULL"), index=True)
    producto_fallback: Mapped[bool] = mapped_column(default=False, nullable=False, index=True)
    clave_familia: Mapped[str | None] = mapped_column(Text())
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    importacion: Mapped["ImportacionCatalogo"] = relationship(back_populates="filas")


class ImportacionCatalogoIncidencia(Base):
    __tablename__ = "importacion_catalogo_incidencia"
    __table_args__ = (
        CheckConstraint(
            "severidad IN ('INFO', 'WARNING', 'ERROR')",
            name="importacion_catalogo_incidencia_severidad_valida",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    importacion_id: Mapped[int] = mapped_column(
        ForeignKey("importacion_catalogo.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    fila_id: Mapped[int | None] = mapped_column(
        ForeignKey("importacion_catalogo_fila.id", ondelete="SET NULL"),
        index=True,
    )
    producto_id: Mapped[int | None] = mapped_column(ForeignKey("producto.id", ondelete="SET NULL"), index=True)
    variante_id: Mapped[int | None] = mapped_column(ForeignKey("variante.id", ondelete="SET NULL"), index=True)
    severidad: Mapped[str] = mapped_column(String(20), nullable=False, default="WARNING", index=True)
    tipo: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    legacy_sku: Mapped[str | None] = mapped_column(String(64), index=True)
    descripcion: Mapped[str] = mapped_column(Text(), nullable=False)
    detalle_json: Mapped[str | None] = mapped_column(Text())
    resuelta: Mapped[bool] = mapped_column(default=False, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    importacion: Mapped["ImportacionCatalogo"] = relationship(back_populates="incidencias")


class AjusteInventarioLote(Base):
    __tablename__ = "ajuste_inventario_lote"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuario.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    tipo_fuente: Mapped[str] = mapped_column(String(30), nullable=False, default="SELECCION")
    tipo_ajuste: Mapped[str] = mapped_column(String(30), nullable=False, default="STOCK_FINAL")
    referencia: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    motivo: Mapped[str] = mapped_column(String(160), nullable=False)
    observacion: Mapped[str | None] = mapped_column(Text())
    total_filas: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    filas_validas: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    filas_error: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unidades_positivas: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unidades_negativas: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    usuario: Mapped["Usuario"] = relationship()
    detalles: Mapped[list["AjusteInventarioLoteDetalle"]] = relationship(
        back_populates="lote",
        cascade="all, delete-orphan",
    )


class AjusteInventarioLoteDetalle(Base):
    __tablename__ = "ajuste_inventario_lote_detalle"
    __table_args__ = (
        CheckConstraint(
            "estado IN ('VALIDO', 'ERROR', 'SIN_CAMBIOS')",
            name="ajuste_inventario_lote_detalle_estado_valido",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    lote_id: Mapped[int] = mapped_column(
        ForeignKey("ajuste_inventario_lote.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    variante_id: Mapped[int] = mapped_column(
        ForeignKey("variante.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    sku_snapshot: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    stock_anterior: Mapped[int] = mapped_column(Integer, nullable=False)
    apartado_comprometido: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    valor_capturado: Mapped[int] = mapped_column(Integer, nullable=False)
    delta_aplicado: Mapped[int] = mapped_column(Integer, nullable=False)
    stock_final: Mapped[int] = mapped_column(Integer, nullable=False)
    estado: Mapped[str] = mapped_column(String(20), nullable=False, default="VALIDO", index=True)
    mensaje: Mapped[str | None] = mapped_column(Text())
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    lote: Mapped["AjusteInventarioLote"] = relationship(back_populates="detalles")
    variante: Mapped["Variante"] = relationship()


class ConteoInventario(Base):
    """Registro de cada conteo físico de inventario por variante."""

    __tablename__ = "conteo_inventario"

    id: Mapped[int] = mapped_column(primary_key=True)
    variante_id: Mapped[int] = mapped_column(
        ForeignKey("variante.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    escuela_id: Mapped[int | None] = mapped_column(
        ForeignKey("escuela.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    stock_sistema: Mapped[int] = mapped_column(Integer, nullable=False)
    stock_fisico: Mapped[int] = mapped_column(Integer, nullable=False)
    diferencia: Mapped[int] = mapped_column(Integer, nullable=False)
    ajustado: Mapped[bool] = mapped_column(default=False, nullable=False, index=True)
    ajuste_lote_id: Mapped[int | None] = mapped_column(
        ForeignKey("ajuste_inventario_lote.id", ondelete="SET NULL"),
        nullable=True,
    )
    contado_por: Mapped[str] = mapped_column(String(100), nullable=False)
    contado_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    notas: Mapped[str | None] = mapped_column(Text())
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    variante: Mapped["Variante"] = relationship()
    escuela: Mapped["Escuela"] = relationship()
    ajuste_lote: Mapped["AjusteInventarioLote"] = relationship()


class ConfigConteoEscuela(Base):
    """Configuración de frecuencia de conteo por escuela."""

    __tablename__ = "config_conteo_escuela"
    __table_args__ = (
        UniqueConstraint("escuela_id", name="config_conteo_escuela_escuela_unico"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    escuela_id: Mapped[int] = mapped_column(
        ForeignKey("escuela.id", ondelete="CASCADE"),
        nullable=False,
    )
    dias_vigencia: Mapped[int] = mapped_column(Integer, nullable=False, default=90)
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

    escuela: Mapped["Escuela"] = relationship()


class Recordatorio(Base):
    """Recordatorio del calendario: pagos, descansos o notas.

    Puede ser en una fecha específica (recurrencia='unica') o repetirse cada mes
    (día del mes) o cada semana (día de la semana). Compartido entre todas las PCs.
    """

    __tablename__ = "recordatorio"

    id: Mapped[int] = mapped_column(primary_key=True)
    # "pago" | "descanso" | "nota" (validado en el servicio, no como enum de PG).
    tipo: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    titulo: Mapped[str] = mapped_column(String(160), nullable=False)
    monto: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))  # opcional, para pagos
    # "unica" | "mensual" | "semanal"
    recurrencia: Mapped[str] = mapped_column(String(20), nullable=False, default="unica")
    fecha: Mapped[date | None] = mapped_column(Date, index=True)   # para 'unica'
    dia_mes: Mapped[int | None] = mapped_column(Integer)           # 1..31 para 'mensual'
    dia_semana: Mapped[int | None] = mapped_column(Integer)        # 0=lun..6=dom para 'semanal'
    notas: Mapped[str | None] = mapped_column(Text())
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class RecordatorioCompletado(Base):
    """Marca de que una ocurrencia de un recordatorio ya se hizo/pagó.

    `fecha` es la fecha de la ocurrencia marcada (ej. un pago mensual del día 1
    de junio → 2026-06-01). Un par (recordatorio, fecha) es único.
    """

    __tablename__ = "recordatorio_completado"
    __table_args__ = (
        UniqueConstraint("recordatorio_id", "fecha", name="uq_recordatorio_completado"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    recordatorio_id: Mapped[int] = mapped_column(
        ForeignKey("recordatorio.id", ondelete="CASCADE"), nullable=False, index=True
    )
    fecha: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class MovimientoInventario(Base):
    __tablename__ = "movimiento_inventario"
    __table_args__ = (
        CheckConstraint("cantidad <> 0", name="movimiento_inventario_cantidad_no_cero"),
        CheckConstraint("stock_posterior >= -1", name="movimiento_inventario_stock_posterior_no_negativo"),
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
    descuento_porcentaje: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0.00"), nullable=False)
    descuento_monto: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
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
    credit_mode: Mapped[ModoOrigenVenta] = mapped_column(
        SqlEnum(ModoOrigenVenta, name="credit_mode_venta"),
        default=ModoOrigenVenta.UNASSIGNED,
        nullable=False,
        index=True,
    )
    seller_employee_code: Mapped[str | None] = mapped_column(String(40), index=True)
    seller_employee_display_name: Mapped[str | None] = mapped_column(String(120))
    folio: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)
    estado: Mapped[EstadoVenta] = mapped_column(
        SqlEnum(EstadoVenta, name="estado_venta"),
        default=EstadoVenta.BORRADOR,
        nullable=False,
        index=True,
    )
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    descuento_porcentaje: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0.00"), nullable=False)
    descuento_monto: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
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
    promociones_manual_autorizadas: Mapped[list["AutorizacionPromocionManual"]] = relationship(
        back_populates="venta",
        order_by="desc(AutorizacionPromocionManual.created_at)",
    )


class Presupuesto(Base):
    __tablename__ = "presupuesto"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuario.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    cliente_id: Mapped[int | None] = mapped_column(
        ForeignKey("cliente.id", ondelete="SET NULL"),
        index=True,
    )
    folio: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)
    cliente_nombre: Mapped[str | None] = mapped_column(String(150), index=True)
    cliente_telefono: Mapped[str | None] = mapped_column(String(40))
    estado: Mapped[EstadoPresupuesto] = mapped_column(
        SqlEnum(EstadoPresupuesto, name="estado_presupuesto"),
        default=EstadoPresupuesto.BORRADOR,
        nullable=False,
        index=True,
    )
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    vigencia_hasta: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    observacion: Mapped[str | None] = mapped_column(Text())
    emitido_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelado_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    convertido_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    usuario: Mapped["Usuario"] = relationship(back_populates="presupuestos")
    cliente: Mapped["Cliente | None"] = relationship(back_populates="presupuestos")
    detalles: Mapped[list["PresupuestoDetalle"]] = relationship(
        back_populates="presupuesto",
        cascade="all, delete-orphan",
    )


class PresupuestoDetalle(Base):
    __tablename__ = "presupuesto_detalle"
    __table_args__ = (
        CheckConstraint("cantidad > 0", name="presupuesto_detalle_cantidad_positiva"),
        CheckConstraint("precio_unitario >= 0", name="presupuesto_detalle_precio_unitario_no_negativo"),
        UniqueConstraint("presupuesto_id", "sku_snapshot", name="presupuesto_detalle_sku_unico"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    presupuesto_id: Mapped[int] = mapped_column(
        ForeignKey("presupuesto.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    variante_id: Mapped[int | None] = mapped_column(
        ForeignKey("variante.id", ondelete="SET NULL"),
        index=True,
    )
    sku_snapshot: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    descripcion_snapshot: Mapped[str] = mapped_column(String(220), nullable=False)
    talla_snapshot: Mapped[str | None] = mapped_column(String(30))
    color_snapshot: Mapped[str | None] = mapped_column(String(50))
    precio_unitario: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)
    subtotal_linea: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    presupuesto: Mapped["Presupuesto"] = relationship(back_populates="detalles")
    variante: Mapped["Variante | None"] = relationship(back_populates="presupuestos_detalle")


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
    variante_id: Mapped[int | None] = mapped_column(
        ForeignKey("variante.id", ondelete="RESTRICT"),
        index=True,
    )
    sku_snapshot: Mapped[str | None] = mapped_column(String(64), index=True)
    descripcion_snapshot: Mapped[str | None] = mapped_column(String(220))
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)
    precio_unitario: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    subtotal_linea: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    venta: Mapped["Venta"] = relationship(back_populates="detalles")
    variante: Mapped["Variante | None"] = relationship(back_populates="ventas_detalle")


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
    seller_employee_code: Mapped[str | None] = mapped_column(String(40), index=True)
    seller_employee_display_name: Mapped[str | None] = mapped_column(String(120))
    delivery_employee_code: Mapped[str | None] = mapped_column(String(40), index=True)
    delivery_employee_display_name: Mapped[str | None] = mapped_column(String(120))
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


class CatalogSchoolProductLink(Base):
    """Liga manual entre un producto general y una escuela para el catálogo guiado."""

    __tablename__ = "catalog_school_product_link"
    __table_args__ = (
        UniqueConstraint("escuela_id", "producto_id", name="uq_school_product_link"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    escuela_id: Mapped[int] = mapped_column(
        ForeignKey("escuela.id", ondelete="CASCADE"), nullable=False, index=True
    )
    producto_id: Mapped[int] = mapped_column(
        ForeignKey("producto.id", ondelete="CASCADE"), nullable=False, index=True
    )
    activo: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    escuela: Mapped["Escuela"] = relationship()
    producto: Mapped["Producto"] = relationship()


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
    seller_employee_code: Mapped[str | None] = mapped_column(String(40), index=True)
    seller_employee_display_name: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    anulado: Mapped[bool] = mapped_column(default=False, server_default="false", nullable=False)
    anulado_por_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuario.id", ondelete="RESTRICT"),
        nullable=True,
    )
    anulado_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    anulado_observacion: Mapped[str | None] = mapped_column(Text(), nullable=True)

    apartado: Mapped["Apartado"] = relationship(back_populates="abonos")
    usuario: Mapped["Usuario"] = relationship(back_populates="apartados_abonos", foreign_keys=[usuario_id])
    anulado_por: Mapped["Usuario | None"] = relationship(foreign_keys=[anulado_por_id])


# ═══════════════════════════════════════════════════════════════════════════════
# BODEGA / WAREHOUSE
# ══════���═══════════════��════════════════════════════════════════════════════════


class BodegaUbicacion(Base):
    __tablename__ = "bodega_ubicacion"
    __table_args__ = (
        UniqueConstraint("rack", "nivel", name="bodega_ubicacion_rack_nivel_unico"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(30), unique=True, nullable=False, index=True)
    rack: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    nivel: Mapped[int] = mapped_column(Integer, nullable=False)
    descripcion: Mapped[str | None] = mapped_column(String(120))
    activo: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    cajas: Mapped[list["BodegaCaja"]] = relationship(back_populates="ubicacion")


class BodegaCaja(Base):
    __tablename__ = "bodega_caja"
    __table_args__ = (
        CheckConstraint(
            "estado IN ('ACTIVA', 'VACIA', 'CERRADA')",
            name="bodega_caja_estado_valido",
        ),
        CheckConstraint(
            "categoria IN ('A', 'B', 'C', 'D')",
            name="bodega_caja_categoria_valida",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(30), unique=True, nullable=False, index=True)
    categoria: Mapped[str] = mapped_column(
        String(1), nullable=False, default=CategoriaCaja.A.value, index=True
    )
    ubicacion_id: Mapped[int | None] = mapped_column(
        ForeignKey("bodega_ubicacion.id", ondelete="SET NULL"),
        index=True,
    )
    estado: Mapped[str] = mapped_column(
        String(20), nullable=False, default=EstadoCaja.ACTIVA.value
    )
    qr_data: Mapped[str | None] = mapped_column(Text())
    notas: Mapped[str | None] = mapped_column(Text())
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

    ubicacion: Mapped["BodegaUbicacion | None"] = relationship(back_populates="cajas")
    contenido: Mapped[list["BodegaContenido"]] = relationship(
        back_populates="caja",
        cascade="all, delete-orphan",
    )
    movimientos: Mapped[list["BodegaMovimiento"]] = relationship(
        back_populates="caja",
        foreign_keys="BodegaMovimiento.caja_id",
        order_by="BodegaMovimiento.created_at.desc()",
    )


class BodegaContenido(Base):
    __tablename__ = "bodega_contenido"
    __table_args__ = (
        UniqueConstraint("caja_id", "variante_id", name="bodega_contenido_caja_variante_unico"),
        CheckConstraint("cantidad > 0", name="bodega_contenido_cantidad_positiva"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    caja_id: Mapped[int] = mapped_column(
        ForeignKey("bodega_caja.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    variante_id: Mapped[int] = mapped_column(
        ForeignKey("variante.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)

    caja: Mapped["BodegaCaja"] = relationship(back_populates="contenido")
    variante: Mapped["Variante"] = relationship()


class BodegaMovimiento(Base):
    __tablename__ = "bodega_movimiento"
    __table_args__ = (
        CheckConstraint(
            "tipo IN ('INGRESO', 'RETIRO', 'TRANSFERENCIA', 'MOVER_CAJA', 'CREAR_CAJA', 'AJUSTE', 'CORRECCION')",
            name="bodega_movimiento_tipo_valido",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    caja_id: Mapped[int] = mapped_column(
        ForeignKey("bodega_caja.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    variante_id: Mapped[int | None] = mapped_column(
        ForeignKey("variante.id", ondelete="RESTRICT"),
        index=True,
    )
    tipo: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    cantidad: Mapped[int | None] = mapped_column(Integer)
    caja_destino_id: Mapped[int | None] = mapped_column(
        ForeignKey("bodega_caja.id", ondelete="RESTRICT"),
    )
    ubicacion_anterior_id: Mapped[int | None] = mapped_column(
        ForeignKey("bodega_ubicacion.id", ondelete="SET NULL"),
    )
    ubicacion_nueva_id: Mapped[int | None] = mapped_column(
        ForeignKey("bodega_ubicacion.id", ondelete="SET NULL"),
    )
    observacion: Mapped[str | None] = mapped_column(Text())
    creado_por: Mapped[str] = mapped_column(String(60), default="SYSTEM", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    caja: Mapped["BodegaCaja"] = relationship(
        back_populates="movimientos",
        foreign_keys=[caja_id],
    )
    variante: Mapped["Variante | None"] = relationship()
    caja_destino: Mapped["BodegaCaja | None"] = relationship(foreign_keys=[caja_destino_id])


class TipoTrabajo(str, Enum):
    """Qué clase de trabajo se despacha al satélite."""

    TICKET = "TICKET"
    ETIQUETA = "ETIQUETA"
    CONTEO = "CONTEO"
    PEDIDO = "PEDIDO"


class EstadoTrabajo(str, Enum):
    """Ciclo de vida genérico de un trabajo.

    Es intencionalmente compartido por todos los tipos para que el esquema
    no cambie fase a fase. La GUI etiqueta cada estado según el tipo:
    EN_PROCESO -> "imprimiendo" (ticket/etiqueta/conteo) o "preparando" (pedido);
    HECHO -> "impreso" o "listo".
    """

    PENDIENTE = "PENDIENTE"
    EN_PROCESO = "EN_PROCESO"
    HECHO = "HECHO"
    ERROR = "ERROR"
    CANCELADO = "CANCELADO"


class Trabajo(Base):
    """Cola de trabajos que el POS/kiosko envían al satélite para imprimir o atender.

    El emisor (principal/kiosko) solo hace INSERT; el despachador del satélite
    toma los PENDIENTE por (prioridad, created_at) y actualiza su estado.
    `contenido` guarda el payload específico del tipo (texto del ticket, datos de
    la etiqueta, hojas de conteo, etc.) como JSON, para no acoplar el esquema a
    cada formato de impresión.
    """

    __tablename__ = "trabajo"

    id: Mapped[int] = mapped_column(primary_key=True)
    tipo: Mapped[TipoTrabajo] = mapped_column(
        SqlEnum(TipoTrabajo, name="tipo_trabajo"),
        nullable=False,
        index=True,
    )
    estado: Mapped[EstadoTrabajo] = mapped_column(
        SqlEnum(EstadoTrabajo, name="estado_trabajo"),
        nullable=False,
        default=EstadoTrabajo.PENDIENTE,
        server_default=EstadoTrabajo.PENDIENTE.value,
        index=True,
    )
    origen: Mapped[str] = mapped_column(String(60), nullable=False, default="principal", index=True)
    prioridad: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    contenido: Mapped[dict] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=False,
    )
    error_msg: Mapped[str | None] = mapped_column(Text())
    creado_por: Mapped[str] = mapped_column(String(60), default="SYSTEM", nullable=False)
    procesado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Reintentos automáticos: cuántas veces se intentó y desde cuándo vuelve a
    # estar disponible (backoff). disponible_en NULL = disponible ya.
    intentos: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    disponible_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class Anuncio(Base):
    """Anuncio/imagen que se difunde a TODOS los satélites (cartelera + aviso).

    A diferencia de `Trabajo` (una máquina reclama y consume cada trabajo), un
    anuncio es *broadcast*: cada satélite lee los que están `activo=True` y los
    muestra. Membresía en la cartelera = `activo`; el aviso inmediato lo dispara
    un NOTIFY al canal 'anuncio' (no un estado persistente). Se crea desde el
    menú admin del propio satélite y se replica al resto vía la DB central.

    El contenido es texto (`titulo`/`mensaje`) y/o una imagen embebida (`imagen`,
    JPEG/PNG ya reducido). Se embebe en la DB para que los satélites la reciban
    por la misma conexión que ya usan, sin carpetas compartidas.
    """

    __tablename__ = "anuncio"

    id: Mapped[int] = mapped_column(primary_key=True)
    titulo: Mapped[str | None] = mapped_column(String(120))
    mensaje: Mapped[str | None] = mapped_column(Text())
    imagen: Mapped[bytes | None] = mapped_column(LargeBinary())
    imagen_mime: Mapped[str | None] = mapped_column(String(40))
    # A qué satélites va dirigido: lista de `identificador`. NULL o vacío = TODOS.
    destinos: Mapped[list | None] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql")
    )
    activo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true", index=True
    )
    prioridad: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    # Segundos que se muestra en la rotación de cartelera antes de pasar al siguiente.
    duracion_seg: Mapped[int] = mapped_column(Integer, nullable=False, default=8, server_default="8")
    creado_por: Mapped[str] = mapped_column(String(60), nullable=False, default="satelite")
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class Satelite(Base):
    """Registro de satélites conocidos, para presencia y para dirigir anuncios.

    Cada satélite se autoregistra al arrancar y late (`ultimo_visto`) cada
    minuto. "Encendido" = latió hace poco. `identificador` es el id estable que
    guarda cada máquina localmente; `nombre` es la etiqueta legible editable.
    La misma tabla la puede leer la PWA para mostrar el estado.
    """

    __tablename__ = "satelite"

    id: Mapped[int] = mapped_column(primary_key=True)
    identificador: Mapped[str] = mapped_column(String(40), nullable=False, unique=True, index=True)
    nombre: Mapped[str] = mapped_column(String(60), nullable=False, default="satelite")
    ultimo_visto: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class LibretaVenta(Base):
    """Registro digital de operaciones del mostrador (la "Libreta").

    Cada venta/apartado de venta rápida se anota aquí automáticamente, ligado
    al gafete de la empleada en sesión. Sustituye la libreta física y la copia
    de ticket que se imprimía solo para registrar. Las empleadas ven sus
    piezas (sin montos); los montos son para la vista del dueño.
    """

    __tablename__ = "libreta_venta"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_code: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    employee_name: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    # "venta" | "apartado" | "abono"
    tipo: Mapped[str] = mapped_column(String(20), nullable=False, default="venta", index=True)
    cliente: Mapped[str | None] = mapped_column(String(120))
    piezas: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Comisiones para la empleada: 3pz vale 3, lo demás 1 por unidad;
    # los abonos no dan comisión (0).
    comisiones: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    monto_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    # Lo que realmente entra tras la comisión de terminal (4.5% por producto
    # si fue pago con tarjeta); igual a monto_total en efectivo.
    monto_neto: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    pago_tarjeta: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    descuento_empleada: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Líneas de la operación: [{sku, nombre, talla, cantidad, precio, subtotal}]
    detalle: Mapped[list] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=False,
        default=list,
    )
    # Identificador del satélite/PC donde se registró (presencia/auditoría).
    origen: Mapped[str | None] = mapped_column(String(60), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )


class EmpleadaHorario(Base):
    """Reglas de calendario de una empleada (Libreta → Calendario).

    El descanso es un día fijo de la semana; el pago es cada N días de
    CALENDARIO (7 = semanal, cobran siempre el mismo día; la falta no
    mueve la fecha — se descuenta al pagar).
    """

    __tablename__ = "empleada_horario"

    employee_code: Mapped[str] = mapped_column(String(40), primary_key=True)
    # 0=lunes .. 6=domingo; None = sin descanso fijo configurado.
    descanso_weekday: Mapped[int | None] = mapped_column(Integer)
    ciclo_dias_pago: Mapped[int] = mapped_column(Integer, nullable=False, default=7, server_default="7")
    fecha_ultimo_pago: Mapped[date | None] = mapped_column(Date)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class EmpleadaEvento(Base):
    """Excepciones y hechos del calendario de empleadas.

    tipo: "falta" | "descanso" (descanso extra o movido) | "trabajo"
    (trabajó en su día de descanso fijo) | "pago" (se le pagó ese día).
    Un evento explícito le gana al patrón fijo del horario.
    """

    __tablename__ = "empleada_evento"
    __table_args__ = (
        UniqueConstraint("employee_code", "fecha", "tipo", name="uq_empleada_evento_dia"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_code: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    fecha: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)
    nota: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
