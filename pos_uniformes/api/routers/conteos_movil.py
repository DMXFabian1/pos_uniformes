"""Contar desde el celular: la misma hoja de siempre, sin papel.

Cinco puertas bajo `/api/v1/movil/conteos`, todas con JWT y con el candado
de "solo en tienda" (en casa el snapshot es de solo lectura):

    GET  /                    mis jornadas a medias + qué se puede empezar
    POST /                    abrir una jornada (escuela o prenda básica)
    GET  /{id}                la hoja: prendas numeradas, tallas y lo capturado
    POST /{id}/tallas         guardar (corregible; vacío = no la conté)
    POST /{id}/terminar       cerrar; queda pendiente de la revisión de Daniel

Reglas que se conservan del kiosko: no viaja el stock del sistema, vacío no
es cero, y nada toca el inventario hasta que Daniel aplique.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from pos_uniformes.api.dependencies import get_current_employee, get_db
from pos_uniformes.api.routers.movil import _solo_tienda

router = APIRouter(prefix="/api/v1/movil/conteos", tags=["movil-conteos"])


class AbrirRequest(BaseModel):
    escuela_id: int | None = None
    tipo_pieza: str = ""


class TallaIn(BaseModel):
    variante_id: int
    fisico: int | None = Field(default=None, ge=0, le=999999)
    pedido: int | None = Field(default=None, ge=0, le=999999)


class TallasRequest(BaseModel):
    items: list[TallaIn]


def _quien(empleada) -> tuple[str, str]:
    code = str(empleada.codigo).strip().upper()
    nombre = str(empleada.nombre_completo or "")
    return code, f"{nombre} ({code})" if nombre else code


def _jornada_mia(db: Session, jornada_id: int, code: str):
    from pos_uniformes.database.models import ConteoJornada
    from pos_uniformes.services.conteo_jornada_service import puede_seguirla

    j = db.get(ConteoJornada, jornada_id)
    if j is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "no_existe", "message": "Esa jornada no existe."}})
    if not puede_seguirla(j, code):
        raise HTTPException(status_code=403, detail={"error": {
            "code": "jornada_ajena",
            "message": f"Esa jornada la abrió {j.empleada_nombre or j.empleada_code}."}})
    return j


@router.get("")
def listar(current: tuple = Depends(get_current_employee), db: Session = Depends(get_db)) -> dict:
    """Mis jornadas a medias (y las de otras, marcadas) + qué escuelas tocan."""
    from pos_uniformes.services import conteo_jornada_service as jn

    empleada, _p = current
    code, _ = _quien(empleada)
    abiertas = []
    for j in jn.jornadas_abiertas(db):
        a = jn.avance(db, j)
        d = jn._dict_ref(jn.ref(j))
        d.update({
            "mia": jn.puede_seguirla(j, code),
            "avance": {"tallas_hechas": a.tallas_hechas, "tallas_total": a.tallas_total,
                       "prendas_hechas": a.prendas_hechas, "prendas_total": a.prendas_total},
        })
        abiertas.append(d)

    escuelas: list[dict] = []
    vencidas_ids: set[int] = set()
    try:
        from pos_uniformes.services.conteo_calendario_service import escuelas_con_conteo_vencido

        vencidas = escuelas_con_conteo_vencido(db)
        vencidas_ids = {int(v.escuela_id) for v in vencidas if getattr(v, "escuela_id", None)}
    except Exception:  # noqa: BLE001 — sin calendario igual se puede contar
        db.rollback()
    from pos_uniformes.services.catalog_school_link_service import list_all_schools

    # Cuándo se contó cada una: para no contar la misma escuela a cada rato.
    try:
        ultimos = jn.ultimos_conteos(db)
    except Exception:  # noqa: BLE001
        db.rollback()
        ultimos = {}

    def _ultimo(escuela_id, tipo_pieza=""):
        u = jn.ultimo_conteo_de(ultimos, escuela_id, tipo_pieza)
        dias = None
        if u.fecha is not None:
            f = u.fecha.astimezone().date() if u.fecha.tzinfo else u.fecha.date()
            dias = (date.today() - f).days
        return {"texto": u.texto(), "dias": dias, "quien": u.quien}

    for e in list_all_schools(db):
        escuelas.append({
            "escuela_id": int(e["escuela_id"]), "nombre": str(e["escuela_nombre"]),
            "toca": int(e["escuela_id"]) in vencidas_ids,
            "ultimo": _ultimo(int(e["escuela_id"])),
        })
    escuelas.sort(key=lambda x: (not x["toca"], x["nombre"]))

    from pos_uniformes.services.conteo_service import obtener_variantes_basicos_agrupadas

    try:
        grupos = obtener_variantes_basicos_agrupadas(db)
        tipos = sorted({g["tipo_pieza"] for g in grupos if not g.get("virtual") and g["tipo_pieza"]})
    except Exception:  # noqa: BLE001
        db.rollback()
        tipos = []
    basicos = [{"tipo_pieza": t, "ultimo": _ultimo(None, t)} for t in tipos]
    return {"modo": "tienda" if _es_tienda() else "casa", "abiertas": abiertas, "escuelas": escuelas, "basicos": basicos}


def _es_tienda() -> bool:
    try:
        _solo_tienda()
        return True
    except HTTPException:
        return False


@router.post("")
def abrir(body: AbrirRequest, current: tuple = Depends(get_current_employee), db: Session = Depends(get_db)) -> dict:
    _solo_tienda()
    from pos_uniformes.services import conteo_jornada_service as jn

    empleada, _p = current
    code, _ = _quien(empleada)
    if body.escuela_id is None and not body.tipo_pieza.strip():
        raise HTTPException(status_code=422, detail={"error": {
            "code": "sin_alcance", "message": "Elige una escuela o una prenda de básicos."}})
    j = jn.abrir_jornada(
        db, escuela_id=body.escuela_id, tipo_pieza=body.tipo_pieza.strip(),
        empleada_code=code, empleada_nombre=str(empleada.nombre_completo or ""),
    )
    db.commit()
    db.refresh(j)
    return jn.hoja_de_jornada(db, j)


@router.get("/{jornada_id}")
def hoja(jornada_id: int, current: tuple = Depends(get_current_employee), db: Session = Depends(get_db)) -> dict:
    from pos_uniformes.services import conteo_jornada_service as jn

    empleada, _p = current
    code, _ = _quien(empleada)
    j = _jornada_mia(db, jornada_id, code)
    return jn.hoja_de_jornada(db, j)


@router.post("/{jornada_id}/tallas")
def guardar(jornada_id: int, body: TallasRequest, current: tuple = Depends(get_current_employee), db: Session = Depends(get_db)) -> dict:
    _solo_tienda()
    from pos_uniformes.services import conteo_jornada_service as jn

    empleada, _p = current
    code, contado_por = _quien(empleada)
    j = _jornada_mia(db, jornada_id, code)
    if j.terminada_at is not None:
        raise HTTPException(status_code=409, detail={"error": {
            "code": "terminada", "message": "Esa jornada ya se terminó."}})
    guardadas = jn.guardar_tallas(db, j, [i.model_dump() for i in body.items], contado_por=contado_por)
    db.commit()
    a = jn.avance(db, j)
    return {"ok": True, "guardadas": guardadas, "avance": {
        "tallas_hechas": a.tallas_hechas, "tallas_total": a.tallas_total,
        "prendas_hechas": a.prendas_hechas, "prendas_total": a.prendas_total}}


@router.post("/{jornada_id}/terminar")
def terminar(jornada_id: int, current: tuple = Depends(get_current_employee), db: Session = Depends(get_db)) -> dict:
    _solo_tienda()
    from pos_uniformes.services import conteo_jornada_service as jn

    empleada, _p = current
    code, _ = _quien(empleada)
    j = _jornada_mia(db, jornada_id, code)
    if j.terminada_at is None:
        jn.terminar_jornada(db, j, empleada_code=code)
        db.commit()
    a = jn.avance(db, j)
    return {"ok": True, "tallas": a.tallas_hechas, "de": a.tallas_total,
            "mensaje": f"Listo. {a.tallas_hechas} tallas quedaron pendientes de que Daniel las revise."}
