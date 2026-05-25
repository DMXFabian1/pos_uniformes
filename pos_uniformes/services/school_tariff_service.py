"""Servicio para consultar tarifarios de precios por escuela."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from pos_uniformes.database.models import CatalogSchoolProductLink, Escuela, NivelEducativo, Producto, Variante


def list_schools_for_tariff(session) -> list[dict]:
    """Devuelve entradas de tarifario por escuela (y nivel cuando hay varios).

    Escuelas con productos en un solo nivel → una entrada.
    Escuelas con productos en múltiples niveles (ej. Primaria + Secundaria) →
    una entrada por nivel, con display_name = "Escuela — Nivel".
    Cada entrada incluye: escuela_id, escuela_nombre, nivel_id (None si no aplica),
    nivel_nombre (None si no aplica), display_name.
    """
    schools = session.scalars(
        select(Escuela).where(Escuela.activo == True).order_by(Escuela.nombre)  # noqa: E712
    ).all()

    result: list[dict] = []
    for s in schools:
        # Obtener los niveles distintos que tiene esta escuela
        nivel_rows = session.execute(
            select(NivelEducativo.id, NivelEducativo.nombre)
            .join(Producto, Producto.nivel_educativo_id == NivelEducativo.id)
            .where(Producto.escuela_id == s.id, Producto.activo == True)  # noqa: E712
            .distinct()
            .order_by(NivelEducativo.id)
        ).all()

        if not nivel_rows:
            # Escuela sin nivel asignado — verificar que tenga productos
            count = session.scalar(
                select(Producto.id)
                .where(Producto.escuela_id == s.id, Producto.activo == True)  # noqa: E712
                .limit(1)
            )
            if count is not None:
                result.append({
                    "escuela_id": int(s.id),
                    "escuela_nombre": str(s.nombre),
                    "nivel_id": None,
                    "nivel_nombre": None,
                    "display_name": str(s.nombre),
                })
        elif len(nivel_rows) == 1:
            # Un solo nivel — entrada simple sin sufijo
            result.append({
                "escuela_id": int(s.id),
                "escuela_nombre": str(s.nombre),
                "nivel_id": int(nivel_rows[0][0]),
                "nivel_nombre": str(nivel_rows[0][1]),
                "display_name": str(s.nombre),
            })
        else:
            # Varios niveles — una entrada por nivel con sufijo
            for nivel_id, nivel_nombre in nivel_rows:
                result.append({
                    "escuela_id": int(s.id),
                    "escuela_nombre": str(s.nombre),
                    "nivel_id": int(nivel_id),
                    "nivel_nombre": str(nivel_nombre),
                    "display_name": f"{s.nombre} — {nivel_nombre}",
                })

    return result


def build_school_tariff(session, escuela_id: int, *, nivel_id: int | None = None) -> dict:
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

    # Productos directos de la escuela (con filtro de nivel si aplica)
    direct_where = [Producto.escuela_id == int(escuela_id), Producto.activo == True]  # noqa: E712
    if nivel_id is not None:
        direct_where.append(Producto.nivel_educativo_id == int(nivel_id))
    directos = session.scalars(
        select(Producto)
        .options(joinedload(Producto.variantes))
        .where(*direct_where)
        .order_by(Producto.nombre_base)
    ).unique().all()

    # Productos ligados via catalog_school_product_link
    ligados = session.scalars(
        select(Producto)
        .join(CatalogSchoolProductLink, CatalogSchoolProductLink.producto_id == Producto.id)
        .options(joinedload(Producto.variantes))
        .where(
            CatalogSchoolProductLink.escuela_id == int(escuela_id),
            CatalogSchoolProductLink.activo == True,  # noqa: E712
            Producto.activo == True,  # noqa: E712
        )
        .order_by(Producto.nombre_base)
    ).unique().all()

    # Unión sin duplicados (un producto puede estar directo Y ligado)
    seen_ids: set[int] = {p.id for p in directos}
    todos_productos = list(directos) + [p for p in ligados if p.id not in seen_ids]

    escuela_nombre = str(escuela.nombre)

    result_products: list[dict] = []
    for prod in todos_productos:
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
        tipo_pieza = prod.tipo_pieza.nombre if prod.tipo_pieza else ""
        tipo_prenda = prod.tipo_prenda.nombre if prod.tipo_prenda else ""
        genero = str(prod.genero or "").strip().upper()
        result_products.append({
            "nombre": clean_name,
            "tipo_pieza": tipo_pieza,
            "tipo_prenda": tipo_prenda,
            "tallas": tallas,
            "genero": genero,
        })

    result_products.sort(key=lambda p: (
        _tariff_section_sort_key(p.get("tipo_prenda", "")),
        _tariff_product_sort_key(p.get("tipo_pieza", "")),
    ))
    merged = _merge_same_price_products(result_products)

    # Nombre de display: con sufijo de nivel si se filtró por él
    nivel_nombre = None
    if nivel_id is not None:
        ne = session.get(NivelEducativo, nivel_id)
        nivel_nombre = str(ne.nombre) if ne else None
    display_nombre = f"{escuela.nombre} — {nivel_nombre}" if nivel_nombre else str(escuela.nombre)

    return {
        "escuela_nombre": display_nombre,
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
            if prices_a == prices_b and a.get("tipo_prenda") == products[j].get("tipo_prenda"):
                group.append(products[j])
                used.add(j)
        if len(group) == 1:
            merged.append(a)
        else:
            names = [g["nombre"] for g in group]
            # Preservar género solo si todos coinciden; si hay mezcla → vacío (UNISEX/ambos)
            generos = {g.get("genero", "") for g in group}
            merged_genero = list(generos)[0] if len(generos) == 1 else ""
            tipo_prendas = {g.get("tipo_prenda", "") for g in group}
            merged_tipo_prenda = list(tipo_prendas)[0] if len(tipo_prendas) == 1 else ""
            merged.append({
                "nombre": _build_merged_name(names),
                "tipo_prenda": merged_tipo_prenda,
                "tallas": a["tallas"],
                "genero": merged_genero,
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


# Orden de piezas en el tarifario (de arriba a abajo)
_PIEZA_ORDER = {
    "Pants 3pz": 1,
    "Pants 2pz": 2,
    "Chamarra": 3,
    "Pants Suelto": 4,
    "Playera": 5,
    "Suéter": 6,
    "Camisa": 7,
    "Chaleco": 8,
    "Falda": 9,
    "Jumper": 10,
    "Blusa": 11,
    "Short": 12,
    "Pantalón": 13,
    "Malla": 14,
    "Calceta": 15,
    "Corbata": 16,
    "Corbatín": 17,
    "Moño": 18,
    "Mascada": 19,
    "Boina": 20,
    "Guante": 21,
    "Bata": 22,
    "Jeans": 23,
}


def _tariff_product_sort_key(tipo_pieza: str) -> tuple[int, str]:
    return (_PIEZA_ORDER.get(tipo_pieza.strip(), 50), tipo_pieza)


# Orden de secciones en el tarifario
_SECCION_ORDER = {
    "Oficial": 1,
    "Básico": 2,
    "Basico": 2,
    "Deportivo": 3,
    "Deportivo casual": 4,
    "Escolta": 5,
    "Casual": 6,
    "Accesorio": 7,
    "Temporada": 8,
}


def _tariff_section_sort_key(tipo_prenda: str) -> int:
    return _SECCION_ORDER.get(tipo_prenda.strip(), 9)
