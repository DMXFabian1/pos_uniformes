"""Helpers puros para el flujo guiado de presupuestos del kiosko."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import unicodedata


@dataclass(frozen=True)
class GuidedCatalogOption:
    key: str
    label: str
    count: int
    enabled: bool


@dataclass(frozen=True)
class GuidedCatalogProductCard:
    sku: str
    title: str
    subtitle: str
    meta_label: str
    price_label: str
    gender_key: str


@dataclass(frozen=True)
class GuidedCatalogView:
    level_options: tuple[GuidedCatalogOption, ...]
    school_options: tuple[GuidedCatalogOption, ...]
    gender_options: tuple[GuidedCatalogOption, ...]
    product_cards: tuple[GuidedCatalogProductCard, ...]
    status_label: str
    path_label: str
    empty_label: str


def build_guided_catalog_view(
    *,
    snapshot_rows: list[dict[str, object]],
    mode_key: str,
    level_filter: str,
    school_filter: str,
    gender_filter: str,
) -> GuidedCatalogView:
    active_rows = [row for row in snapshot_rows if _is_active_row(row)]
    normalized_mode = "basics" if mode_key == "basics" else "school"
    normalized_level = level_filter.strip()
    normalized_school = school_filter.strip()
    normalized_gender = _normalize_segment_filter(gender_filter)

    mode_rows = [
        row for row in active_rows if _matches_mode(row=row, mode_key=normalized_mode)
    ]
    level_options = _build_level_options(mode_rows) if normalized_mode == "school" else tuple()
    school_options = (
        _build_school_options(mode_rows, level_filter=normalized_level) if normalized_mode == "school" else tuple()
    )

    gender_source_rows = _filter_for_gender_stage(
        rows=mode_rows,
        mode_key=normalized_mode,
        level_filter=normalized_level,
        school_filter=normalized_school,
    )
    gender_options = _build_segment_options(gender_source_rows)

    product_rows, empty_label = _filter_product_rows(
        rows=mode_rows,
        mode_key=normalized_mode,
        level_filter=normalized_level,
        school_filter=normalized_school,
        gender_filter=normalized_gender,
    )

    product_cards = tuple(_to_product_card(row) for row in product_rows)
    status_label = _build_status_label(
        visible_count=len(product_cards),
        mode_key=normalized_mode,
        level_filter=normalized_level,
        school_filter=normalized_school,
        gender_filter=normalized_gender,
    )
    path_label = _build_path_label(
        mode_key=normalized_mode,
        level_filter=normalized_level,
        school_filter=normalized_school,
        gender_filter=normalized_gender,
    )
    return GuidedCatalogView(
        level_options=level_options,
        school_options=school_options,
        gender_options=gender_options,
        product_cards=product_cards,
        status_label=status_label,
        path_label=path_label,
        empty_label=empty_label,
    )


def _is_active_row(row: dict[str, object]) -> bool:
    return bool(row.get("producto_activo")) and bool(row.get("variante_activo"))


def _matches_mode(*, row: dict[str, object], mode_key: str) -> bool:
    school_name = str(row.get("escuela_nombre") or "General").strip() or "General"
    if mode_key == "basics":
        return school_name == "General"
    return school_name != "General"


def _build_level_options(rows: list[dict[str, object]]) -> tuple[GuidedCatalogOption, ...]:
    counts: dict[str, int] = {}
    for row in rows:
        level_name = str(row.get("nivel_educativo_nombre") or "").strip()
        if not level_name or level_name == "Sin nivel":
            continue
        counts[level_name] = counts.get(level_name, 0) + 1
    return tuple(
        GuidedCatalogOption(key=level_name, label=level_name, count=counts[level_name], enabled=counts[level_name] > 0)
        for level_name in sorted(counts)
    )


def _build_school_options(
    rows: list[dict[str, object]],
    *,
    level_filter: str,
) -> tuple[GuidedCatalogOption, ...]:
    counts: dict[str, int] = {}
    for row in rows:
        level_name = str(row.get("nivel_educativo_nombre") or "").strip()
        school_name = str(row.get("escuela_nombre") or "").strip()
        if level_filter and level_name != level_filter:
            continue
        if not school_name or school_name == "General":
            continue
        counts[school_name] = counts.get(school_name, 0) + 1
    return tuple(
        GuidedCatalogOption(
            key=school_name,
            label=school_name,
            count=counts[school_name],
            enabled=counts[school_name] > 0,
        )
        for school_name in sorted(counts)
    )


def _filter_for_gender_stage(
    *,
    rows: list[dict[str, object]],
    mode_key: str,
    level_filter: str,
    school_filter: str,
) -> list[dict[str, object]]:
    filtered_rows = list(rows)
    if mode_key == "school":
        if not level_filter:
            return []
        filtered_rows = [
            row
            for row in filtered_rows
            if str(row.get("nivel_educativo_nombre") or "").strip() == level_filter
        ]
        if not school_filter:
            return []
        filtered_rows = [
            row
            for row in filtered_rows
            if str(row.get("escuela_nombre") or "").strip() == school_filter
        ]
    return filtered_rows


def _filter_product_rows(
    *,
    rows: list[dict[str, object]],
    mode_key: str,
    level_filter: str,
    school_filter: str,
    gender_filter: str,
) -> tuple[list[dict[str, object]], str]:
    if mode_key == "school" and not level_filter:
        return [], "Selecciona un nivel para ver las escuelas disponibles."
    if mode_key == "school" and not school_filter:
        return [], "Selecciona una escuela para ver productos sugeridos."

    filtered_rows = _filter_for_gender_stage(
        rows=rows,
        mode_key=mode_key,
        level_filter=level_filter,
        school_filter=school_filter,
    )
    filtered_rows = [row for row in filtered_rows if _matches_segment_filter(gender_filter, row)]
    filtered_rows.sort(key=lambda row: _product_sort_key(row, prefer_deportivo=gender_filter == "DEPORTIVO"))
    if filtered_rows:
        return filtered_rows, ""
    if mode_key == "basics":
        return [], "No hay basicos disponibles para ese genero."
    return [], "No hay productos disponibles para esa combinacion."


def _build_segment_options(rows: list[dict[str, object]]) -> tuple[GuidedCatalogOption, ...]:
    options = (
        ("DEPORTIVO", "Deportivo"),
        ("OFICIAL_NINA", "Oficial Niña"),
        ("OFICIAL_NINO", "Oficial Niño"),
        ("TODOS", "Todos"),
    )
    built_options: list[GuidedCatalogOption] = []
    for key, label in options:
        count = sum(1 for row in rows if _matches_segment_filter(key, row))
        built_options.append(GuidedCatalogOption(key=key, label=label, count=count, enabled=count > 0))
    return tuple(built_options)


def _to_product_card(row: dict[str, object]) -> GuidedCatalogProductCard:
    price = Decimal(str(row.get("precio_venta") or "0")).quantize(Decimal("0.01"))
    school_name = str(row.get("escuela_nombre") or "General").strip() or "General"
    level_name = str(row.get("nivel_educativo_nombre") or "Sin nivel").strip() or "Sin nivel"
    segment_key = _classify_product_segment(row)
    gender_key = _classify_gender(row.get("producto_genero"))
    segment_label = _segment_row_label(segment_key, gender_key)
    return GuidedCatalogProductCard(
        sku=str(row.get("sku") or ""),
        title=str(row.get("producto_nombre_base") or row.get("producto_nombre") or "Producto"),
        subtitle=(
            f"{row.get('tipo_prenda_nombre') or '-'} · Talla {row.get('talla') or '-'} · "
            f"{row.get('color') or 'Sin color'}"
        ),
        meta_label=f"{school_name} · {level_name} · {segment_label}",
        price_label=f"${price}",
        gender_key=gender_key,
    )


def _build_status_label(
    *,
    visible_count: int,
    mode_key: str,
    level_filter: str,
    school_filter: str,
    gender_filter: str,
) -> str:
    parts = [f"{visible_count} producto(s) sugeridos"]
    parts.append("Modo: Basicos" if mode_key == "basics" else "Modo: Uniformes")
    if level_filter:
        parts.append(f"Nivel: {level_filter}")
    if school_filter:
        parts.append(f"Escuela: {school_filter}")
    if gender_filter != "TODOS":
        parts.append(f"Linea: {_segment_label(gender_filter)}")
    return " | ".join(parts)


def _build_path_label(
    *,
    mode_key: str,
    level_filter: str,
    school_filter: str,
    gender_filter: str,
) -> str:
    if mode_key == "basics":
        path_parts = ["Basicos"]
    else:
        path_parts = ["Uniformes", level_filter or "sin nivel", school_filter or "sin escuela"]
    path_parts.append(_segment_label(gender_filter))
    return " > ".join(path_parts)


def _segment_label(gender_key: str) -> str:
    return {
        "DEPORTIVO": "Deportivo",
        "OFICIAL_NINA": "Oficial Niña",
        "OFICIAL_NINO": "Oficial Niño",
        "TODOS": "Todos",
        "OFICIAL_UNISEX": "Oficial",
    }.get(gender_key, "Todos")


def _normalize_segment_filter(value: str) -> str:
    normalized = _normalize_text(value)
    compact = normalized.replace(" ", "")
    if compact in {"deportivo", "deporte"}:
        return "DEPORTIVO"
    if compact in {"oficialnina", "nina", "femenino"}:
        return "OFICIAL_NINA"
    if compact in {"oficialnino", "nino", "masculino"}:
        return "OFICIAL_NINO"
    return "TODOS"


def _matches_segment_filter(filter_key: str, row: dict[str, object]) -> bool:
    line_key = _classify_line_type(row)
    if filter_key == "DEPORTIVO":
        return line_key == "DEPORTIVO"
    if filter_key == "OFICIAL_NINA":
        if line_key != "OFICIAL":
            return False
        if _is_shared_uniform_top(row):
            return True
        return _classify_gender(row.get("producto_genero")) in {"NINA", "UNISEX"}
    if filter_key == "OFICIAL_NINO":
        if line_key != "OFICIAL":
            return False
        if _is_shared_uniform_top(row):
            return True
        return _classify_gender(row.get("producto_genero")) in {"NINO", "UNISEX"}
    return True


def _classify_gender(raw_value: object) -> str:
    normalized = _normalize_text(raw_value)
    if not normalized:
        return "UNISEX"
    if "unisex" in normalized:
        return "UNISEX"
    if "nina" in normalized or "femen" in normalized or "dama" in normalized or "mujer" in normalized:
        if "nino" in normalized:
            return "UNISEX"
        return "NINA"
    if "nino" in normalized or "mascul" in normalized or "caballero" in normalized or "hombre" in normalized:
        return "NINO"
    return "UNISEX"


def _classify_product_segment(row: dict[str, object]) -> str:
    line_key = _classify_line_type(row)
    gender_key = _classify_gender(row.get("producto_genero"))
    if line_key == "DEPORTIVO":
        return "DEPORTIVO"
    if _is_shared_uniform_top(row):
        return "OFICIAL_UNISEX"
    if gender_key == "NINA":
        return "OFICIAL_NINA"
    if gender_key == "NINO":
        return "OFICIAL_NINO"
    return "OFICIAL_UNISEX"


def _segment_row_label(segment_key: str, gender_key: str) -> str:
    if segment_key == "DEPORTIVO":
        return "Deportivo"
    if segment_key == "OFICIAL_NINA":
        return "Oficial Niña"
    if segment_key == "OFICIAL_NINO":
        return "Oficial Niño"
    if gender_key == "UNISEX":
        return "Oficial"
    return _segment_label(segment_key)


def _normalize_text(value: object) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or "").strip().lower())
    return "".join(character for character in normalized if not unicodedata.combining(character))


def _classify_line_type(row: dict[str, object]) -> str:
    garment_type = _normalize_text(row.get("tipo_prenda_nombre"))
    if garment_type == "deportivo":
        return "DEPORTIVO"
    if garment_type == "oficial":
        return "OFICIAL"
    searchable = " ".join(
        [
            _normalize_text(row.get("tipo_pieza_nombre")),
            _normalize_text(row.get("producto_nombre_base")),
            _normalize_text(row.get("producto_nombre")),
            _normalize_text(row.get("producto_descripcion")),
        ]
    )
    if "deport" in searchable:
        return "DEPORTIVO"
    if "oficial" in searchable:
        return "OFICIAL"
    return "OTRO"


def _is_shared_uniform_top(row: dict[str, object]) -> bool:
    searchable = " ".join(
        [
            _normalize_text(row.get("tipo_pieza_nombre")),
            _normalize_text(row.get("producto_nombre_base")),
            _normalize_text(row.get("producto_nombre")),
        ]
    )
    return _contains_any(searchable, ("camisa", "playera"))


def _product_sort_key(row: dict[str, object], *, prefer_deportivo: bool) -> tuple[object, ...]:
    if prefer_deportivo:
        return (
            _deportivo_priority(row),
            str(row.get("producto_nombre_base") or "").lower(),
            str(row.get("tipo_prenda_nombre") or "").lower(),
            str(row.get("talla") or "").lower(),
            str(row.get("color") or "").lower(),
            str(row.get("sku") or "").lower(),
        )
    return (
        str(row.get("producto_nombre_base") or "").lower(),
        str(row.get("tipo_prenda_nombre") or "").lower(),
        str(row.get("talla") or "").lower(),
        str(row.get("color") or "").lower(),
        str(row.get("sku") or "").lower(),
    )


def _deportivo_priority(row: dict[str, object]) -> int:
    searchable = " ".join(
        [
            _normalize_text(row.get("producto_nombre_base")),
            _normalize_text(row.get("producto_nombre")),
            _normalize_text(row.get("tipo_prenda_nombre")),
            _normalize_text(row.get("tipo_pieza_nombre")),
            _normalize_text(row.get("producto_descripcion")),
        ]
    )
    if _contains_any(searchable, ("3pz", "3 pz", "3 piezas", "tres piezas", "conjunto 3", "set 3")):
        return 0
    if _contains_any(searchable, ("2pz", "2 pz", "2 piezas", "dos piezas", "conjunto 2", "set 2")):
        return 1
    if _contains_any(searchable, ("chamarra", "chaqueta", "jacket", "sudadera")):
        return 2
    if _contains_any(searchable, ("pants", "pantalon", "pantalones", "jogger")):
        return 3
    if _contains_any(searchable, ("playera", "camiseta", "jersey", "camisa deportiva")):
        return 4
    return 5


def _contains_any(text: str, patterns: tuple[str, ...]) -> bool:
    return any(pattern in text for pattern in patterns)
