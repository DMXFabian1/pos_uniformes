"""Bodega desde el celular: llegó mercancía y pasar al piso. Solo el dueño.

Ver `services/bodega_movil_service.py`.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from pos_uniformes.api.dependencies import get_current_employee, get_db
from pos_uniformes.api.routers.movil import _solo_tienda
from pos_uniformes.services import bodega_movil_service as bm

router = APIRouter(prefix="/api/v1/movil/bodega", tags=["movil-bodega"])


class PiezaIn(BaseModel):
    variante_id: int
    cantidad: int = Field(default=0, ge=0, le=99999)
    a_caja: int = Field(default=0, ge=0, le=99999)   # solo en "llegó": cuántas de esas se guardan


class LlegoRequest(BaseModel):
    items: list[PiezaIn]
    caja_id: int | None = None
    caja_nueva: bool = False
    referencia: str = Field(default="", max_length=120)


class PisoRequest(BaseModel):
    caja_id: int
    items: list[PiezaIn]


def _dueno(current: tuple) -> tuple[str, str]:
    empleada, _p = current
    code = str(empleada.codigo).strip().upper()
    if code != bm.DUENO_CODE:
        raise HTTPException(status_code=403, detail={"error": {"code": "solo_dueno", "message": "Solo Daniel mueve la bodega."}})
    return code, str(empleada.nombre_completo or "")


@router.get("/cajas")
def cajas(current: tuple = Depends(get_current_employee), db: Session = Depends(get_db)) -> dict:
    _dueno(current)
    return {"cajas": bm.cajas_activas(db)}


@router.get("/cajas/{caja_id}")
def caja(caja_id: int, current: tuple = Depends(get_current_employee), db: Session = Depends(get_db)) -> dict:
    _dueno(current)
    return {"caja_id": caja_id, "contenido": bm.contenido_de_caja(db, caja_id)}


@router.get("/prendas")
def prendas(q: str = "", current: tuple = Depends(get_current_employee), db: Session = Depends(get_db)) -> dict:
    _dueno(current)
    return {"prendas": bm.buscar_prendas(db, q)}


@router.post("/llego")
def llego(body: LlegoRequest, current: tuple = Depends(get_current_employee), db: Session = Depends(get_db)) -> dict:
    _solo_tienda()
    code, nombre = _dueno(current)
    try:
        r = bm.llego_mercancia(
            db, items=[i.model_dump() for i in body.items], quien_code=code, quien=nombre,
            caja_id=body.caja_id, caja_nueva=body.caja_nueva, referencia=body.referencia.strip(),
        )
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail={"error": {"code": "invalido", "message": str(exc)}})
    return {"ok": True, **r}


@router.post("/piso")
def piso(body: PisoRequest, current: tuple = Depends(get_current_employee), db: Session = Depends(get_db)) -> dict:
    _solo_tienda()
    code, nombre = _dueno(current)
    try:
        r = bm.pasar_al_piso(db, caja_id=body.caja_id, items=[i.model_dump() for i in body.items], quien_code=code, quien=nombre)
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail={"error": {"code": "invalido", "message": str(exc)}})
    return {"ok": True, **r}


class CorregirRequest(BaseModel):
    caja_id: int
    items: list[PiezaIn]


@router.post("/corregir")
def corregir(body: CorregirRequest, current: tuple = Depends(get_current_employee), db: Session = Depends(get_db)) -> dict:
    _solo_tienda()
    code, nombre = _dueno(current)
    try:
        r = bm.corregir_caja(db, caja_id=body.caja_id, items=[i.model_dump() for i in body.items], quien_code=code, quien=nombre)
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail={"error": {"code": "invalido", "message": str(exc)}})
    return {"ok": True, **r}
