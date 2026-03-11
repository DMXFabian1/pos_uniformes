"""Gestion de clientes para ventas, apartados y fidelizacion futura."""

from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from pos_uniformes.database.models import Cliente, RolUsuario, Usuario


class ClientService:
    """Reglas de negocio para administracion de clientes."""

    @staticmethod
    def _validar_admin(admin_user: Usuario) -> None:
        if not admin_user.activo:
            raise PermissionError("El usuario administrador no esta activo.")
        if admin_user.rol != RolUsuario.ADMIN:
            raise PermissionError("Solo ADMIN puede gestionar clientes.")

    @staticmethod
    def list_clients(session: Session, search_text: str = "") -> list[Cliente]:
        statement = select(Cliente).order_by(Cliente.nombre.asc())
        normalized_search = search_text.strip().lower()
        if normalized_search:
            like_term = f"%{normalized_search}%"
            statement = statement.where(
                or_(
                    func.lower(Cliente.codigo_cliente).like(like_term),
                    func.lower(Cliente.nombre).like(like_term),
                    func.lower(func.coalesce(Cliente.telefono, "")).like(like_term),
                    func.lower(func.coalesce(Cliente.email, "")).like(like_term),
                    func.lower(func.coalesce(Cliente.direccion, "")).like(like_term),
                    func.lower(func.coalesce(Cliente.notas, "")).like(like_term),
                )
            )
        return session.scalars(statement).all()

    @staticmethod
    def _generate_client_code(session: Session) -> str:
        next_id = (session.scalar(select(func.coalesce(func.max(Cliente.id), 0))) or 0) + 1
        return f"CLI-{int(next_id):06d}"

    @classmethod
    def create_client(
        cls,
        session: Session,
        admin_user: Usuario,
        nombre: str,
        telefono: str = "",
        email: str = "",
        direccion: str = "",
        notas: str = "",
    ) -> Cliente:
        cls._validar_admin(admin_user)
        normalized_name = nombre.strip()
        if not normalized_name:
            raise ValueError("El nombre del cliente no puede estar vacio.")
        client = Cliente(
            codigo_cliente=cls._generate_client_code(session),
            nombre=normalized_name,
            telefono=telefono.strip() or None,
            email=email.strip() or None,
            direccion=direccion.strip() or None,
            notas=notas.strip() or None,
            activo=True,
        )
        session.add(client)
        return client

    @classmethod
    def update_client(
        cls,
        session: Session,
        admin_user: Usuario,
        client: Cliente,
        nombre: str,
        telefono: str = "",
        email: str = "",
        direccion: str = "",
        notas: str = "",
    ) -> Cliente:
        cls._validar_admin(admin_user)
        normalized_name = nombre.strip()
        if not normalized_name:
            raise ValueError("El nombre del cliente no puede estar vacio.")
        client.nombre = normalized_name
        client.telefono = telefono.strip() or None
        client.email = email.strip() or None
        client.direccion = direccion.strip() or None
        client.notas = notas.strip() or None
        session.add(client)
        return client

    @classmethod
    def toggle_active(
        cls,
        session: Session,
        admin_user: Usuario,
        client: Cliente,
    ) -> Cliente:
        cls._validar_admin(admin_user)
        client.activo = not client.activo
        session.add(client)
        return client
