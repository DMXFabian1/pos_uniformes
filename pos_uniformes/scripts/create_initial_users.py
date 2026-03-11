"""Crea usuarios iniciales para POS Uniformes si no existen."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sqlalchemy import select

from pos_uniformes.database.connection import get_session
from pos_uniformes.database.models import RolUsuario, Usuario
from pos_uniformes.services.auth_service import AuthService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Crea usuarios iniciales para POS Uniformes.")
    parser.add_argument("--admin-user", default="admin", help="Username del administrador inicial.")
    parser.add_argument("--admin-password", default="admin123", help="Password del administrador inicial.")
    parser.add_argument("--admin-name", default="Administrador POS Uniformes", help="Nombre del administrador.")
    parser.add_argument("--cashier-user", default="cajero", help="Username del cajero inicial.")
    parser.add_argument("--cashier-password", default="cajero123", help="Password del cajero inicial.")
    parser.add_argument("--cashier-name", default="Cajero POS Uniformes", help="Nombre del cajero.")
    return parser.parse_args()


def _get_or_create_user(
    *,
    username: str,
    password: str,
    nombre_completo: str,
    rol: RolUsuario,
) -> tuple[Usuario, bool]:
    normalized_username = username.strip().lower()
    if not normalized_username:
        raise ValueError("El username no puede estar vacio.")
    if not password:
        raise ValueError("El password no puede estar vacio.")

    with get_session() as session:
        existing = session.scalar(select(Usuario).where(Usuario.username == normalized_username))
        if existing is not None:
            if not existing.password_hash.startswith("pbkdf2_sha256$"):
                existing.password_hash = AuthService.hash_password(password)
                session.add(existing)
                session.commit()
            return existing, False

        user = Usuario(
            username=normalized_username,
            nombre_completo=nombre_completo.strip(),
            rol=rol,
            activo=True,
            password_hash=AuthService.hash_password(password),
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user, True


def main() -> int:
    args = parse_args()
    admin_user, admin_created = _get_or_create_user(
        username=args.admin_user,
        password=args.admin_password,
        nombre_completo=args.admin_name,
        rol=RolUsuario.ADMIN,
    )
    cashier_user, cashier_created = _get_or_create_user(
        username=args.cashier_user,
        password=args.cashier_password,
        nombre_completo=args.cashier_name,
        rol=RolUsuario.CAJERO,
    )

    print(
        f"ADMIN: {admin_user.username} | creado={str(admin_created).lower()} | activo={str(admin_user.activo).lower()}"
    )
    print(
        f"CAJERO: {cashier_user.username} | creado={str(cashier_created).lower()} | activo={str(cashier_user.activo).lower()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
