"""Gestion base de empleadas comerciales y resolucion de QR EMP."""

from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from pos_uniformes.database.models import Empleada, RolUsuario, Usuario


class EmployeeIdentityService:
    """Reglas minimas para alta y resolucion de empleadas comerciales."""

    QR_PREFIX = "EMP:"

    @staticmethod
    def _validar_admin(admin_user: Usuario) -> None:
        if not admin_user.activo:
            raise PermissionError("El usuario administrador no esta activo.")
        if admin_user.rol != RolUsuario.ADMIN:
            raise PermissionError("Solo ADMIN puede gestionar empleadas.")

    @classmethod
    def normalize_employee_code(cls, raw_code: str) -> str:
        normalized = raw_code.strip().upper()
        if normalized.startswith(cls.QR_PREFIX):
            normalized = normalized[len(cls.QR_PREFIX) :].strip()
        if not normalized:
            raise ValueError("El codigo de empleada no puede estar vacio.")
        if any(char.isspace() for char in normalized):
            raise ValueError("El codigo de empleada no puede contener espacios.")
        return normalized

    @staticmethod
    def build_visible_employee_name(full_name: str) -> str:
        parts = [part for part in full_name.strip().split() if part]
        if not parts:
            return ""
        if len(parts) == 1:
            return parts[0]
        return f"{parts[0]} {parts[-1]}"

    @classmethod
    def list_employees(cls, session: Session, search_text: str = "") -> list[Empleada]:
        statement = select(Empleada).order_by(Empleada.nombre_completo.asc())
        normalized_search = search_text.strip().lower()
        if normalized_search:
            like_term = f"%{normalized_search}%"
            statement = statement.where(
                or_(
                    func.lower(Empleada.codigo).like(like_term),
                    func.lower(Empleada.nombre_completo).like(like_term),
                )
            )
        return session.scalars(statement).all()

    @classmethod
    def create_employee(
        cls,
        session: Session,
        *,
        admin_user: Usuario,
        codigo: str,
        nombre_completo: str,
    ) -> Empleada:
        cls._validar_admin(admin_user)
        normalized_code = cls.normalize_employee_code(codigo)
        normalized_name = nombre_completo.strip()
        if not normalized_name:
            raise ValueError("El nombre de la empleada no puede estar vacio.")
        existing = session.scalar(select(Empleada).where(func.upper(Empleada.codigo) == normalized_code))
        if existing is not None:
            raise ValueError(f"Ya existe una empleada con el codigo '{normalized_code}'.")
        employee = Empleada(
            codigo=normalized_code,
            nombre_completo=normalized_name,
            activo=True,
        )
        session.add(employee)
        return employee

    @classmethod
    def update_employee(
        cls,
        session: Session,
        *,
        admin_user: Usuario,
        employee: Empleada,
        codigo: str,
        nombre_completo: str,
    ) -> Empleada:
        cls._validar_admin(admin_user)
        normalized_code = cls.normalize_employee_code(codigo)
        normalized_name = nombre_completo.strip()
        if not normalized_name:
            raise ValueError("El nombre de la empleada no puede estar vacio.")
        existing = session.scalar(
            select(Empleada).where(
                func.upper(Empleada.codigo) == normalized_code,
                Empleada.id != employee.id,
            )
        )
        if existing is not None:
            raise ValueError(f"Ya existe una empleada con el codigo '{normalized_code}'.")
        employee.codigo = normalized_code
        employee.nombre_completo = normalized_name
        session.add(employee)
        return employee

    @classmethod
    def toggle_active(cls, session: Session, admin_user: Usuario, employee: Empleada) -> Empleada:
        cls._validar_admin(admin_user)
        employee.activo = not employee.activo
        session.add(employee)
        return employee

    @classmethod
    def resolve_employee_by_qr_code(cls, session: Session, scanned_code: str) -> Empleada | None:
        normalized_code = cls.normalize_employee_code(scanned_code)
        employee = session.scalar(select(Empleada).where(func.upper(Empleada.codigo) == normalized_code))
        if employee is None or not employee.activo:
            return None
        return employee
