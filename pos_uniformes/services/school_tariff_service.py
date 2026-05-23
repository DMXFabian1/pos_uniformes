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

    merged = _merge_same_price_products(result_products)

    return {
        "escuela_nombre": str(escuela.nombre),
        "productos": merged,
    }


def _merge_same_price_products(products: list[dict]) -> list[dict]:
    """Fusiona productos con precios idénticos en una sola entrada.

    Ej: 'Suéter Botones M Rojo' y 'Suéter Cuello V H Rojo' con mismos
    precios → 'Suéter (Botones M / Cuello V H) Rojo'.
    """
    merged: list[dict] = []
    used: set[int] = set()
    for i, a in enumerate(products):
        if i in used:
            continue
        prices_a = [(t["talla"], t["precio"]) for t in a["tallas"]]
        group = [a]
        for j in range(i + 1, len(products)):
            if j in used:
                continue
            prices_b = [(t["talla"], t["precio"]) for t in products[j]["tallas"]]
            if prices_a == prices_b:
                group.append(products[j])
                used.add(j)
        if len(group) == 1:
            merged.append(a)
        else:
            names = [g["nombre"] for g in group]
            merged.append({
                "nombre": _build_merged_name(names),
                "tallas": a["tallas"],
            })
    return merged


def _build_merged_name(names: list[str]) -> str:
    """Construye nombre fusionado buscando prefijo/sufijo comunes.

    Ej: ['Suéter Botones M Rojo', 'Suéter Cuello V H Rojo']
      → 'Suéter (Botones M / Cuello V H) Rojo'
    """
    if len(names) == 1:
        return names[0]
    words = [n.split() for n in names]
    # Prefijo común
    prefix: list[str] = []
    for parts in zip(*words):
        if len(set(parts)) == 1:
            prefix.append(parts[0])
        else:
            break
    # Sufijo común
    suffix: list[str] = []
    for parts in zip(*(w[::-1] for w in words)):
        if len(set(parts)) == 1:
            suffix.append(parts[0])
        else:
            break
    suffix.reverse()
    plen = len(prefix)
    slen = len(suffix)
    # Partes diferentes
    diffs = []
    for w in words:
        end = len(w) - slen if slen else len(w)
        diff = w[plen:end]
        diffs.append(" ".join(diff) if diff else "")
    diff_str = " / ".join(d for d in diffs if d)
    parts = []
    if prefix:
        parts.append(" ".join(prefix))
    if diff_str:
        parts.append(f"({diff_str})")
    if suffix:
        parts.append(" ".join(suffix))
    return " ".join(parts) if parts else " / ".join(names)


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
    "2": 1, "3": 2, "4": 3, "5": 4, "6": 5, "7": 6, "8": 7, "9": 8,
    "10": 9, "11": 10, "12": 11, "13": 12, "14": 13, "16": 14, "18": 15, "20": 16,
    "28": 17, "30": 18, "32": 19, "34": 20, "36": 21, "38": 22, "40": 23, "42": 24, "44": 25, "46": 26,
    "XCH": 30, "CH": 31, "CH-MD": 32, "MD": 33, "GD": 34, "GD-EXG": 35, "EXG": 36, "XXL": 37,
    "S": 31, "M": 33, "L": 34, "XL": 36, "G": 34, "XG": 36,
    "NT": 40, "ESP": 41, "Dama": 42,
    "U": 50, "Uni": 50, "Unica": 50, "Unitalla": 50,
}


def _talla_sort_key(talla: str) -> tuple[int, str]:
    return (_TALLA_ORDER.get(talla.strip(), 99), talla)
