"""Gestion de proveedores para compras e inventario."""

from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from pos_uniformes.database.models import Proveedor, RolUsuario, Usuario


class SupplierService:
    """Reglas de negocio para administracion de proveedores."""

    @staticmethod
    def _validar_admin(admin_user: Usuario) -> None:
        if not admin_user.activo:
            raise PermissionError("El usuario administrador no esta activo.")
        if admin_user.rol != RolUsuario.ADMIN:
            raise PermissionError("Solo ADMIN puede gestionar proveedores.")

    @staticmethod
    def list_suppliers(session: Session, search_text: str = "") -> list[Proveedor]:
        statement = select(Proveedor).order_by(Proveedor.nombre.asc())
        normalized_search = search_text.strip().lower()
        if normalized_search:
            like_term = f"%{normalized_search}%"
            statement = statement.where(
                or_(
                    func.lower(Proveedor.nombre).like(like_term),
                    func.lower(func.coalesce(Proveedor.telefono, "")).like(like_term),
                    func.lower(func.coalesce(Proveedor.email, "")).like(like_term),
                    func.lower(func.coalesce(Proveedor.direccion, "")).like(like_term),
                )
            )
        return session.scalars(statement).all()

    @classmethod
    def create_supplier(
        cls,
        session: Session,
        admin_user: Usuario,
        nombre: str,
        telefono: str = "",
        email: str = "",
        direccion: str = "",
    ) -> Proveedor:
        cls._validar_admin(admin_user)
        normalized_name = nombre.strip()
        if not normalized_name:
            raise ValueError("El nombre del proveedor no puede estar vacio.")
        existing = session.scalar(
            select(Proveedor).where(func.lower(Proveedor.nombre) == normalized_name.lower())
        )
        if existing is not None:
            raise ValueError(f"Ya existe un proveedor llamado '{normalized_name}'.")

        supplier = Proveedor(
            nombre=normalized_name,
            telefono=telefono.strip() or None,
            email=email.strip() or None,
            direccion=direccion.strip() or None,
            activo=True,
        )
        session.add(supplier)
        return supplier

    @classmethod
    def update_supplier(
        cls,
        session: Session,
        admin_user: Usuario,
        supplier: Proveedor,
        nombre: str,
        telefono: str = "",
        email: str = "",
        direccion: str = "",
    ) -> Proveedor:
        cls._validar_admin(admin_user)
        normalized_name = nombre.strip()
        if not normalized_name:
            raise ValueError("El nombre del proveedor no puede estar vacio.")
        existing = session.scalar(
            select(Proveedor).where(
                func.lower(Proveedor.nombre) == normalized_name.lower(),
                Proveedor.id != supplier.id,
            )
        )
        if existing is not None:
            raise ValueError(f"Ya existe un proveedor llamado '{normalized_name}'.")

        supplier.nombre = normalized_name
        supplier.telefono = telefono.strip() or None
        supplier.email = email.strip() or None
        supplier.direccion = direccion.strip() or None
        session.add(supplier)
        return supplier

    @classmethod
    def toggle_active(
        cls,
        session: Session,
        admin_user: Usuario,
        supplier: Proveedor,
    ) -> Proveedor:
        cls._validar_admin(admin_user)
        supplier.activo = not supplier.activo
        session.add(supplier)
        return supplier
