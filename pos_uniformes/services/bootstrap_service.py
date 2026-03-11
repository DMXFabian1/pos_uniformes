"""Carga de datos iniciales idempotente para el POS."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from pos_uniformes.database.models import (
    Categoria,
    Marca,
    Producto,
    Proveedor,
    RolUsuario,
    Usuario,
    Variante,
)
from pos_uniformes.services.auth_service import AuthService
from pos_uniformes.services.inventario_service import InventarioService


class BootstrapService:
    """Crea datos base para desarrollo y demostracion."""

    @staticmethod
    def _get_or_create_categoria(session: Session, nombre: str, descripcion: str) -> Categoria:
        categoria = session.scalar(select(Categoria).where(Categoria.nombre == nombre))
        if categoria is None:
            categoria = Categoria(nombre=nombre, descripcion=descripcion)
            session.add(categoria)
            session.flush()
        return categoria

    @staticmethod
    def _get_or_create_marca(session: Session, nombre: str) -> Marca:
        marca = session.scalar(select(Marca).where(Marca.nombre == nombre))
        if marca is None:
            marca = Marca(nombre=nombre)
            session.add(marca)
            session.flush()
        return marca

    @staticmethod
    def _get_or_create_producto(
        session: Session,
        categoria: Categoria,
        marca: Marca,
        nombre: str,
        descripcion: str,
    ) -> Producto:
        producto = session.scalar(
            select(Producto).where(
                Producto.nombre == nombre,
                Producto.marca_id == marca.id,
            )
        )
        if producto is None:
            producto = Producto(
                categoria=categoria,
                marca=marca,
                nombre=nombre,
                nombre_base=nombre,
                descripcion=descripcion,
            )
            session.add(producto)
            session.flush()
        return producto

    @staticmethod
    def _get_or_create_variante(
        session: Session,
        producto: Producto,
        sku: str,
        talla: str,
        color: str,
        precio_venta: Decimal,
        costo_referencia: Decimal,
        stock_actual: int,
    ) -> Variante:
        variante = session.scalar(select(Variante).where(Variante.sku == sku))
        if variante is None:
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
            if stock_actual > 0:
                InventarioService.registrar_ingreso_compra(
                    session=session,
                    variante=variante,
                    cantidad=stock_actual,
                    referencia="SEED-INITIAL",
                    creado_por="SYSTEM",
                )
        return variante

    @staticmethod
    def _get_or_create_usuario(
        session: Session,
        username: str,
        nombre_completo: str,
        rol: RolUsuario,
        password_hash: str,
    ) -> Usuario:
        usuario = session.scalar(select(Usuario).where(Usuario.username == username))
        if usuario is None:
            usuario = Usuario(
                username=username,
                nombre_completo=nombre_completo,
                rol=rol,
                password_hash=AuthService.hash_password(password_hash),
            )
            session.add(usuario)
            session.flush()
        elif not usuario.password_hash.startswith("pbkdf2_sha256$"):
            usuario.password_hash = AuthService.hash_password(password_hash)
            session.add(usuario)
        return usuario

    @staticmethod
    def _get_or_create_proveedor(session: Session, nombre: str, telefono: str, email: str) -> Proveedor:
        proveedor = session.scalar(select(Proveedor).where(Proveedor.nombre == nombre))
        if proveedor is None:
            proveedor = Proveedor(
                nombre=nombre,
                telefono=telefono,
                email=email,
            )
            session.add(proveedor)
            session.flush()
        return proveedor

    @classmethod
    def seed_initial_data(cls, session: Session) -> dict[str, int]:
        cls._get_or_create_usuario(
            session=session,
            username="admin",
            nombre_completo="Administrador Principal",
            rol=RolUsuario.ADMIN,
            password_hash="admin123",
        )
        cls._get_or_create_usuario(
            session=session,
            username="cajero",
            nombre_completo="Cajero General",
            rol=RolUsuario.CAJERO,
            password_hash="cajero123",
        )
        cls._get_or_create_proveedor(
            session=session,
            nombre="Proveedor Demo",
            telefono="555-0101",
            email="proveedor@example.com",
        )

        categoria_calzado = cls._get_or_create_categoria(session, "Calzado", "Calzado casual y deportivo.")
        categoria_ropa = cls._get_or_create_categoria(session, "Ropa", "Ropa urbana y basicos.")
        marca_nike = cls._get_or_create_marca(session, "Nike")
        marca_levi = cls._get_or_create_marca(session, "Levi's")

        producto_1 = cls._get_or_create_producto(
            session=session,
            categoria=categoria_calzado,
            marca=marca_nike,
            nombre="Air Runner",
            descripcion="Tenis ligeros para uso diario.",
        )
        producto_2 = cls._get_or_create_producto(
            session=session,
            categoria=categoria_ropa,
            marca=marca_levi,
            nombre="Jeans 511",
            descripcion="Pantalon corte slim.",
        )

        cls._get_or_create_variante(
            session=session,
            producto=producto_1,
            sku="NIK-AIR-RUN-BLK-26",
            talla="26",
            color="Negro",
            precio_venta=Decimal("1499.00"),
            costo_referencia=Decimal("980.00"),
            stock_actual=8,
        )
        cls._get_or_create_variante(
            session=session,
            producto=producto_1,
            sku="NIK-AIR-RUN-WHT-27",
            talla="27",
            color="Blanco",
            precio_venta=Decimal("1499.00"),
            costo_referencia=Decimal("980.00"),
            stock_actual=5,
        )
        cls._get_or_create_variante(
            session=session,
            producto=producto_2,
            sku="LEV-511-BLU-32",
            talla="32",
            color="Azul",
            precio_venta=Decimal("899.00"),
            costo_referencia=Decimal("550.00"),
            stock_actual=12,
        )
        cls._get_or_create_variante(
            session=session,
            producto=producto_2,
            sku="LEV-511-BLK-34",
            talla="34",
            color="Negro",
            precio_venta=Decimal("899.00"),
            costo_referencia=Decimal("550.00"),
            stock_actual=9,
        )

        session.flush()
        return {
            "usuarios": session.query(Usuario).count(),
            "proveedores": session.query(Proveedor).count(),
            "categorias": session.query(Categoria).count(),
            "marcas": session.query(Marca).count(),
            "productos": session.query(Producto).count(),
            "variantes": session.query(Variante).count(),
        }
