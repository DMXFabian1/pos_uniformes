"""Servicio para consultar tarifarios de precios por escuela."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from pos_uniformes.database.models import Escuela, Producto, Variante


def list_schools_for_tariff(session) -> list[dict]:
    """Devuelve escuelas activas que tengan al menos un producto con variantes."""
    schools = session.scalars(
        select(Escuela).where(Escuela.activo == True).order_by(Escuela.nombre)  # noqa: E712
    ).all()
    result: list[dict] = []
    for s in schools:
        count = session.scalar(
            select(Producto.id)
            .where(Producto.escuela_id == s.id, Producto.activo == True)  # noqa: E712
            .limit(1)
        )
        if count is not None:
            result.append({"escuela_id": int(s.id), "escuela_nombre": str(s.nombre)})
    return result


def build_school_tariff(session, escuela_id: int) -> dict:
    """Construye el tarifario completo de una escuela.

    Retorna::

        {
            "escuela_nombre": "CBTIS 168",
            "productos": [
                {
                    "nombre": "Playera Deportiva",
                    "tallas": [
                        {"talla": "CH", "precio": Decimal("199.00")},
                        {"talla": "M", "precio": Decimal("199.00")},
                    ],
                },
                ...
            ],
        }
    """
    escuela = session.get(Escuela, int(escuela_id))
    if escuela is None:
        return {"escuela_nombre": "", "productos": []}

    productos = session.scalars(
        select(Producto)
        .options(joinedload(Producto.variantes))
        .where(
            Producto.escuela_id == int(escuela_id),
            Producto.activo == True,  # noqa: E712
        )
        .order_by(Producto.nombre_base)
    ).unique().all()

    escuela_nombre = str(escuela.nombre)

    result_products: list[dict] = []
    for prod in productos:
        variantes = sorted(
            [v for v in prod.variantes if getattr(v, "activo", True)],
            key=lambda v: _talla_sort_key(str(v.talla or "")),
        )
        if not variantes:
            continue
        tallas = [
            {"talla": str(v.talla or "U"), "precio": Decimal(str(v.precio_venta))}
            for v in variantes
        ]
        raw_name = str(prod.nombre_base or prod.nombre)
        clean_name = _clean_tariff_product_name(raw_name, escuela_nombre)
        result_products.append({
            "nombre": clean_name,
            "tallas": tallas,
        })

    return {
        "escuela_nombre": str(escuela.nombre),
        "productos": result_products,
    }


def _clean_tariff_product_name(name: str, school_name: str) -> str:
    """Limpia el nombre del producto para el tarifario: quita escuela y 'Ad hoc'."""
    import re
    cleaned = name
    # Quitar nombre de escuela del nombre del producto
    if school_name:
        cleaned = re.sub(re.escape(school_name), "", cleaned, flags=re.IGNORECASE).strip()
    # Quitar "Ad hoc" / "Ad Hoc"
    cleaned = re.sub(r"\bAd\s+hoc\b", "", cleaned, flags=re.IGNORECASE).strip()
    # Limpiar espacios dobles y trailing separators
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    return cleaned or name


_TALLA_ORDER = {
    "2": 1, "4": 2, "6": 3, "8": 4, "10": 5, "12": 6, "14": 7, "16": 8,
    "18": 9, "20": 10,
    "XCH": 20, "CH": 21, "M": 22, "G": 23, "XG": 24,
    "S": 21, "L": 23, "XL": 24, "XXL": 25,
    "U": 50, "Unica": 50,
}


def _talla_sort_key(talla: str) -> tuple[int, str]:
    return (_TALLA_ORDER.get(talla.strip(), 99), talla)
