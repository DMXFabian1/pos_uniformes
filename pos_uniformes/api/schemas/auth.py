"""Schemas de autenticacion de empleadas."""

from __future__ import annotations

from pydantic import BaseModel


class EmpleadaPublica(BaseModel):
    """Empleada visible en el listbox de login (sin datos sensibles)."""
    id: int
    nombre_completo: str
    nombre_visible: str
    tiene_pin: bool

    model_config = {"from_attributes": True}


class LoginRequest(BaseModel):
    employee_id: int
    pin: str
    device_id: str | None = None


class LoginResponse(BaseModel):
    token: str
    device_id: str
    employee_id: int
    employee_name: str
    expires_in_hours: int


class MeResponse(BaseModel):
    employee_id: int
    employee_name: str
    device_id: str
