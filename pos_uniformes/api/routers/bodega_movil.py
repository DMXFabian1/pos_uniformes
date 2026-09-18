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
    imprimir_etiquetas: bool = False   # una etiqueta por pieza que llegó, a la Brother de la tienda


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
    etiquetas = _encolar_etiquetas(db, body.items, code) if body.imprimir_etiquetas else 0
    return {"ok": True, "etiquetas": etiquetas, **r}


def _encolar_etiquetas(db: Session, items, code: str) -> int:
    """Una etiqueta por pieza que llegó (lo que se pega en la prenda antes de
    colgarla). Va por la misma cola `trabajo` que el botón de Buscar. Si algo
    falla, la mercancía ya quedó guardada: se avisa y se pueden imprimir
    después desde Buscar."""
    from pathlib import Path

    from pos_uniformes.database.models import Variante
    from pos_uniformes.services import trabajos_service
    from pos_uniformes.services.inventory_label_service import render_inventory_label

    total = 0
    for it in items:
        n = int(it.cantidad or 0)
        if n <= 0:
            continue
        try:
            v = db.get(Variante, int(it.variante_id))
            r = render_inventory_label(db, int(it.variante_id), mode="standard", requested_copies=n)
            trabajos_service.enviar_etiqueta(
                db, Path(r.image_path).read_bytes(), sku=str(v.sku if v else ""), copies=r.effective_copies,
                paper_mode=r.mode, origen="pwa", creado_por=code,
            )
            total += r.effective_copies
        except Exception:  # noqa: BLE001 — la llegada ya está guardada
            db.rollback()
            continue
    db.commit()
    return total


@router.get("/llegadas")
def llegadas(current: tuple = Depends(get_current_employee), db: Session = Depends(get_db)) -> dict:
    """Lo que ha llegado en el último mes, para el dueño."""
    _dueno(current)
    return {"llegadas": bm.llegadas_recientes(db)}


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
