"""Endpoints de autenticacion de empleadas para la API movil."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from pos_uniformes.api.dependencies import get_db, get_current_employee
from pos_uniformes.api.schemas.auth import (
    EmpleadaPublica,
    LoginRequest,
    LoginResponse,
    MeResponse,
)
from pos_uniformes.api.services.token_service import TokenService
from pos_uniformes.database.models import Empleada
from pos_uniformes.services.auth_service import AuthService
from pos_uniformes.services.employee_identity_service import EmployeeIdentityService
from pos_uniformes.utils.config import settings

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.get("/employees", response_model=list[EmpleadaPublica])
def list_active_employees(db: Session = Depends(get_db)) -> list[EmpleadaPublica]:
    """
    Lista publica de empleadas activas para el listbox de login.
    No requiere autenticacion.
    """
    empleadas = db.scalars(
        select(Empleada)
        .where(Empleada.activo.is_(True))
        .order_by(Empleada.nombre_completo.asc())
    ).all()

    return [
        EmpleadaPublica(
            id=e.id,
            nombre_completo=e.nombre_completo,
            nombre_visible=EmployeeIdentityService.build_visible_employee_name(e.nombre_completo),
            tiene_pin=EmployeeIdentityService.has_pin(e),
        )
        for e in empleadas
    ]


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    """
    Autentica una empleada con su ID y PIN.
    Devuelve un JWT de sesion y el device_id registrado.
    """
    empleada = db.scalar(
        select(Empleada).where(Empleada.id == body.employee_id, Empleada.activo.is_(True))
    )

    if empleada is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "credenciales_invalidas", "message": "Empleada no encontrada o inactiva."}},
        )

    if not EmployeeIdentityService.has_pin(empleada):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "sin_pin", "message": "Esta empleada no tiene PIN configurado. Contacta al administrador."}},
        )

    if not AuthService.verify_password(body.pin, empleada.pin_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "credenciales_invalidas", "message": "PIN incorrecto."}},
        )

    token, device_id = TokenService.create_token(
        employee_id=empleada.id,
        employee_name=EmployeeIdentityService.build_visible_employee_name(empleada.nombre_completo),
        device_id=body.device_id,
    )

    return LoginResponse(
        token=token,
        device_id=device_id,
        employee_id=empleada.id,
        employee_name=EmployeeIdentityService.build_visible_employee_name(empleada.nombre_completo),
        expires_in_hours=settings.api_token_expire_hours,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(auth=Depends(get_current_employee)) -> None:
    """
    Cierre de sesion. El cliente debe eliminar su token local.
    El JWT es stateless — la invalidacion es responsabilidad del cliente.
    """
    return None


@router.get("/me", response_model=MeResponse)
def me(auth=Depends(get_current_employee)) -> MeResponse:
    """Devuelve la identidad de la empleada autenticada."""
    _empleada, payload = auth
    return MeResponse(
        employee_id=payload.employee_id,
        employee_name=payload.employee_name,
        device_id=payload.device_id,
    )
