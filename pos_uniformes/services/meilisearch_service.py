"""Servicio de indexación y búsqueda con Meilisearch."""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session, selectinload

from pos_uniformes.database.models import Producto, Variante

logger = logging.getLogger(__name__)

MEILI_URL = "http://127.0.0.1:7700"
MEILI_KEY = None
INDEX_NAME = "variantes"

_client = None


def _get_client():
    global _client
    if _client is not None:
        return _client
    try:
        import meilisearch
        _client = meilisearch.Client(MEILI_URL, MEILI_KEY)
        _client.health()
        return _client
    except Exception:
        _client = None
        return None


def _get_index():
    client = _get_client()
    if client is None:
        return None
    try:
        return client.index(INDEX_NAME)
    except Exception:
        return None


def configure_index() -> bool:
    client = _get_client()
    if client is None:
        return False
    try:
        client.create_index(INDEX_NAME, {"primaryKey": "id"})
    except Exception:
        pass
    try:
        index = client.index(INDEX_NAME)
        index.update_settings({
            "searchableAttributes": [
                "nombre_base",
                "nombre_producto",
                "sku",
                "talla",
                "color",
                "tipo_pieza",
                "tipo_prenda",
                "categoria",
                "escuela",
                "marca",
            ],
            "filterableAttributes": [
                "activo",
                "escuela_id",
                "tipo_pieza_id",
                "tipo_prenda_id",
                "modo",
            ],
            "sortableAttributes": ["nombre_base", "precio_venta"],
            "typoTolerance": {
                "enabled": True,
                "minWordSizeForTypos": {"oneTypo": 3, "twoTypos": 6},
            },
        })
        return True
    except Exception as exc:
        logger.warning("No se pudo configurar el indice Meilisearch: %s", exc)
        return False


def index_from_db(session: Session) -> int:
    index = _get_index()
    if index is None:
        return 0

    productos = session.scalars(
        session.query(Producto)
        .where(Producto.activo.is_(True))
        .options(
            selectinload(Producto.variantes),
            selectinload(Producto.categoria),
            selectinload(Producto.marca),
            selectinload(Producto.escuela),
            selectinload(Producto.tipo_pieza),
            selectinload(Producto.tipo_prenda),
        )
    ).all()

    docs: list[dict[str, Any]] = []
    for p in productos:
        for v in p.variantes:
            if not v.activo:
                continue
            tipo_pieza_nombre = p.tipo_pieza.nombre if p.tipo_pieza else "Sin pieza"
            docs.append({
                "id": v.id,
                "sku": v.sku,
                "talla": v.talla or "",
                "color": v.color or "",
                "precio_venta": float(v.precio_venta or 0),
                "stock_actual": v.stock_actual or 0,
                "producto_id": p.id,
                "nombre_base": p.nombre_base or p.nombre or "",
                "nombre_producto": p.nombre or "",
                "categoria": p.categoria.nombre if p.categoria else "",
                "marca": p.marca.nombre if p.marca else "",
                "escuela": p.escuela.nombre if p.escuela else "",
                "escuela_id": p.escuela_id,
                "tipo_pieza": tipo_pieza_nombre,
                "tipo_pieza_id": p.tipo_pieza_id,
                "tipo_prenda": p.tipo_prenda.nombre if p.tipo_prenda else "",
                "tipo_prenda_id": p.tipo_prenda_id,
                "genero": p.genero or "",
                "family_key": f"{tipo_pieza_nombre}||{p.nombre_base or p.nombre}",
                "modo": "school" if p.escuela_id else "basics",
                "activo": True,
            })

    if not docs:
        return 0

    try:
        index.delete_all_documents()
        index.add_documents(docs)
        return len(docs)
    except Exception as exc:
        logger.warning("Error indexando en Meilisearch: %s", exc)
        return 0


def search(query: str, *, limit: int = 40, mode: str | None = None) -> list[dict[str, Any]]:
    index = _get_index()
    if index is None:
        return []

    opts: dict[str, Any] = {
        "limit": limit,
        "attributesToRetrieve": [
            "id", "sku", "talla", "color", "precio_venta", "stock_actual",
            "producto_id", "nombre_base", "nombre_producto", "categoria",
            "marca", "escuela", "tipo_pieza", "tipo_pieza_id", "tipo_prenda",
            "genero", "family_key", "modo",
        ],
    }

    filters = ["activo = true"]
    if mode in ("school", "basics"):
        filters.append(f'modo = "{mode}"')
    if filters:
        opts["filter"] = " AND ".join(filters)

    try:
        result = index.search(query, opts)
        return result.get("hits", [])
    except Exception as exc:
        logger.warning("Error buscando en Meilisearch: %s", exc)
        return []


def search_as_families(query: str, *, limit: int = 40, mode: str | None = None) -> list[dict[str, Any]]:
    hits = search(query, limit=limit, mode=mode)
    if not hits:
        return []

    families: dict[str, dict[str, Any]] = {}
    for hit in hits:
        fk = hit.get("family_key", "")
        if not fk:
            continue
        if fk not in families:
            families[fk] = {
                "key": fk,
                "nombre_base": hit.get("nombre_base", ""),
                "tipo_pieza": hit.get("tipo_pieza"),
                "tipo_pieza_id": hit.get("tipo_pieza_id"),
                "precio_desde": hit.get("precio_venta", 0),
                "variantes": [],
            }
        fam = families[fk]
        fam["variantes"].append({
            "id": hit["id"],
            "sku": hit["sku"],
            "talla": hit.get("talla", ""),
            "color": hit.get("color", ""),
            "precio_venta": hit.get("precio_venta", 0),
            "stock_actual": hit.get("stock_actual", 0),
        })
        if hit.get("precio_venta", 0) < fam["precio_desde"]:
            fam["precio_desde"] = hit["precio_venta"]

    return list(families.values())


def is_available() -> bool:
    return _get_client() is not None
