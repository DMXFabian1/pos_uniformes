"""Mapa de conteos: qué está contado y qué no, de un vistazo y por capas.

Daniel (2026-09-20): "una guía visual para ver qué está contado y qué no…
como el panel de uniformes, pero estructurado para que no sea megalítico".

Tres capas, cada una un dict listo para pintar:
  1. `resumen(session)`      → escuelas (con su nivel) y tipos de básicos, cada
                                uno con cuántas tallas están al día / viejas / nunca.
  2. `escuela(session, id)`  /  `basicos(session, tipo)` → sus prendas, mismas cifras.
  3. dentro de cada prenda   → sus tallas con días desde el último conteo.

"Al día" = contada hace menos de la vigencia de esa escuela (ConfigConteoEscuela
o el default); "vieja" = contada pero ya venció; "nunca" = sin conteo.
"""

from __future__ import annotations

from collections import Counter, defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from pos_uniformes.database.models import Escuela, NivelEducativo, Producto
from pos_uniformes.services.conteo_service import (
    _TIPOS_VIRTUALES,
    _talla_sort_key,
    agrupar_variantes_por_producto,
    obtener_variantes_basicos_para_conteo,
    obtener_variantes_para_conteo_varias,
)

AL_DIA, VIEJA, NUNCA = "al_dia", "vieja", "nunca"


def estado_talla(v) -> str:
    if v.dias_desde_conteo is None:
        return NUNCA
    return VIEJA if v.requiere_conteo else AL_DIA


def _cifras(variantes) -> dict:
    c = Counter(estado_talla(v) for v in variantes)
    total = sum(c.values())
    dias = [v.dias_desde_conteo for v in variantes if v.dias_desde_conteo is not None]
    return {
        "tallas": total, "al_dia": c[AL_DIA], "viejas": c[VIEJA], "nunca": c[NUNCA],
        "pct_al_dia": round(100 * c[AL_DIA] / total) if total else 0,
        "ultimo_dias": min(dias) if dias else None,   # el conteo más reciente que la tocó
        "estado": AL_DIA if total and c[AL_DIA] == total else (NUNCA if total and c[NUNCA] == total else (VIEJA if total else NUNCA)),
    }


def _prendas(grupos) -> list[dict]:
    out = []
    for g in grupos:
        if g.get("virtual") or g["tipo_pieza"] in _TIPOS_VIRTUALES:
            continue
        vs = sorted(g["variantes"], key=_talla_sort_key)
        out.append({
            "nombre": str(g["producto_nombre"]).split("|")[0].strip(),
            "tipo_pieza": g["tipo_pieza"],
            **_cifras(vs),
            "tallas_detalle": [
                {"talla": v.talla, "color": v.color or "", "estado": estado_talla(v), "dias": v.dias_desde_conteo,
                 "stock": int(v.stock_actual)}
                for v in vs
            ],
        })
    return out


def _niveles_por_escuela(session: Session) -> dict[int, str]:
    filas = session.execute(
        select(Producto.escuela_id, NivelEducativo.nombre)
        .join(NivelEducativo, NivelEducativo.id == Producto.nivel_educativo_id)
        .where(Producto.escuela_id.is_not(None), Producto.activo.is_(True))
        .distinct()
    ).all()
    por_escuela: dict[int, set[str]] = defaultdict(set)
    for eid, nivel in filas:
        por_escuela[int(eid)].add(str(nivel))
    return {eid: (next(iter(ns)) if len(ns) == 1 else "Varios niveles") for eid, ns in por_escuela.items()}


def resumen(session: Session) -> dict:
    escuelas = list(session.scalars(select(Escuela).where(Escuela.activo.is_(True)).order_by(Escuela.nombre)).all())
    por_escuela = obtener_variantes_para_conteo_varias(session, [int(e.id) for e in escuelas])
    niveles = _niveles_por_escuela(session)
    filas = []
    for e in escuelas:
        vs = [v for v in por_escuela.get(int(e.id), []) if v.tipo_pieza not in _TIPOS_VIRTUALES]
        if not vs:
            continue
        filas.append({"escuela_id": int(e.id), "nombre": str(e.nombre), "nivel": niveles.get(int(e.id), "Sin nivel"), **_cifras(vs)})
    basicos_vs = [v for v in obtener_variantes_basicos_para_conteo(session) if v.tipo_pieza not in _TIPOS_VIRTUALES]
    por_tipo: dict[str, list] = defaultdict(list)
    for v in basicos_vs:
        por_tipo[v.tipo_pieza or "Sin tipo"].append(v)
    basicos = [{"tipo_pieza": t, **_cifras(vs)} for t, vs in sorted(por_tipo.items())]
    todo = [v for vs in por_escuela.values() for v in vs if v.tipo_pieza not in _TIPOS_VIRTUALES] + basicos_vs
    return {"total": _cifras(todo), "escuelas": filas, "basicos": basicos}


def escuela(session: Session, escuela_id: int) -> dict:
    e = session.get(Escuela, int(escuela_id))
    vs = obtener_variantes_para_conteo_varias(session, [int(escuela_id)]).get(int(escuela_id), [])
    prendas = _prendas(agrupar_variantes_por_producto(vs))
    return {"titulo": str(e.nombre) if e else f"Escuela {escuela_id}", "prendas": prendas,
            **_cifras([v for v in vs if v.tipo_pieza not in _TIPOS_VIRTUALES])}


def basicos(session: Session, tipo_pieza: str) -> dict:
    vs = [v for v in obtener_variantes_basicos_para_conteo(session) if (v.tipo_pieza or "Sin tipo") == tipo_pieza]
    prendas = _prendas(agrupar_variantes_por_producto(vs))
    return {"titulo": f"Básicos · {tipo_pieza}", "prendas": prendas, **_cifras([v for v in vs if v.tipo_pieza not in _TIPOS_VIRTUALES])}
