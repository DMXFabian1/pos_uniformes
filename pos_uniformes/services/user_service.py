"""Gestion de usuarios, roles y contrasenas para el POS."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pos_uniformes.database.models import RolUsuario, Usuario
from pos_uniformes.services.auth_service import AuthService


class UserService:
    """Reglas de negocio para administracion de usuarios."""

    @staticmethod
    def _validar_admin(admin_user: Usuario) -> None:
        if not admin_user.activo:
            raise PermissionError("El usuario administrador no esta activo.")
        if admin_user.rol != RolUsuario.ADMIN:
            raise PermissionError("Solo ADMIN puede gestionar usuarios.")

    @staticmethod
    def _active_admin_count(session: Session) -> int:
        session.flush()
        return session.scalar(
            select(func.count(Usuario.id)).where(
                Usuario.rol == RolUsuario.ADMIN,
                Usuario.activo.is_(True),
            )
        ) or 0

    @classmethod
    def list_users(cls, session: Session) -> list[Usuario]:
        return session.scalars(select(Usuario).order_by(Usuario.username.asc())).all()

    @classmethod
    def create_user(
        cls,
        session: Session,
        admin_user: Usuario,
        username: str,
        nombre_completo: str,
        rol: RolUsuario,
        password: str,
    ) -> Usuario:
        cls._validar_admin(admin_user)
        normalized_username = username.strip().lower()
        if not normalized_username:
            raise ValueError("El username no puede estar vacio.")
        if len(normalized_username) < 3:
            raise ValueError("El username debe tener al menos 3 caracteres.")
        if not nombre_completo.strip():
            raise ValueError("El nombre completo no puede estar vacio.")
        if session.scalar(select(Usuario).where(Usuario.username == normalized_username)) is not None:
            raise ValueError(f"Ya existe el usuario '{normalized_username}'.")

        user = Usuario(
            username=normalized_username,
            nombre_completo=nombre_completo.strip(),
            rol=rol,
            activo=True,
            password_hash=AuthService.hash_password(password),
        )
        session.add(user)
        return user

    @classmethod
    def toggle_active(cls, session: Session, admin_user: Usuario, target_user: Usuario) -> Usuario:
        cls._validar_admin(admin_user)
        if target_user.id == admin_user.id and target_user.activo:
            raise ValueError("No puedes desactivarte a ti mismo desde esta pantalla.")
        if target_user.activo and target_user.rol == RolUsuario.ADMIN and cls._active_admin_count(session) <= 1:
            raise ValueError("No puedes desactivar al ultimo ADMIN activo.")

        target_user.activo = not target_user.activo
        session.add(target_user)
        return target_user

    @classmethod
    def change_role(
        cls,
        session: Session,
        admin_user: Usuario,
        target_user: Usuario,
        new_role: RolUsuario,
    ) -> Usuario:
        cls._validar_admin(admin_user)
        if target_user.rol == new_role:
            return target_user
        if target_user.rol == RolUsuario.ADMIN and new_role != RolUsuario.ADMIN and target_user.activo:
            if cls._active_admin_count(session) <= 1:
                raise ValueError("No puedes quitar el rol al ultimo ADMIN activo.")
        if target_user.id == admin_user.id and new_role != RolUsuario.ADMIN:
            raise ValueError("No puedes quitarte tu propio rol ADMIN desde esta pantalla.")

        target_user.rol = new_role
        session.add(target_user)
        return target_user

    @classmethod
    def change_password(
        cls,
        session: Session,
        admin_user: Usuario,
        target_user: Usuario,
        new_password: str,
    ) -> Usuario:
        cls._validar_admin(admin_user)
        target_user.password_hash = AuthService.hash_password(new_password)
        session.add(target_user)
        return target_user

    @classmethod
    def update_user(
        cls,
        session: Session,
        admin_user: Usuario,
        target_user: Usuario,
        username: str,
        nombre_completo: str,
        rol: RolUsuario,
    ) -> Usuario:
        cls._validar_admin(admin_user)
        normalized_username = username.strip().lower()
        if not normalized_username:
            raise ValueError("El username no puede estar vacio.")
        if len(normalized_username) < 3:
            raise ValueError("El username debe tener al menos 3 caracteres.")
        if not nombre_completo.strip():
            raise ValueError("El nombre completo no puede estar vacio.")
        existing = session.scalar(
            select(Usuario).where(
                Usuario.username == normalized_username,
                Usuario.id != target_user.id,
            )
        )
        if existing is not None:
            raise ValueError(f"Ya existe el usuario '{normalized_username}'.")
        if target_user.id == admin_user.id and rol != RolUsuario.ADMIN:
            raise ValueError("No puedes quitarte tu propio rol ADMIN desde esta pantalla.")
        if target_user.rol == RolUsuario.ADMIN and rol != RolUsuario.ADMIN and target_user.activo:
            if cls._active_admin_count(session) <= 1:
                raise ValueError("No puedes quitar el rol al ultimo ADMIN activo.")

        target_user.username = normalized_username
        target_user.nombre_completo = nombre_completo.strip()
        target_user.rol = rol
        session.add(target_user)
        return target_user
