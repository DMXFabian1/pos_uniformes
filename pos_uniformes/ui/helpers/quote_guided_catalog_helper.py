"""Helpers puros para el flujo guiado de presupuestos del kiosko."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from pos_uniformes.ui.helpers.catalog_product_form_mode_helper import REGULAR_CATEGORY_EXCLUSION_SET
from pos_uniformes.utils.text_normalization import normalize_text_unicode as _normalize_text


@dataclass(frozen=True)
class GuidedCatalogOption:
    key: str
    label: str
    count: int
    enabled: bool
    group_label: str = ""


@dataclass(frozen=True)
class GuidedCatalogProductCard:
    key: str
    sku: str
    title: str
    subtitle: str
    meta_label: str
    price_label: str
    gender_key: str
    tipo_pieza: str = ""


@dataclass(frozen=True)
class GuidedCatalogVariantOption:
    sku: str
    label: str
    detail_label: str
    price_label: str


@dataclass(frozen=True)
class GuidedCatalogView:
    level_options: tuple[GuidedCatalogOption, ...]
    school_options: tuple[GuidedCatalogOption, ...]
    gender_options: tuple[GuidedCatalogOption, ...]
    profile_options: tuple[GuidedCatalogOption, ...]
    bucket_options: tuple[GuidedCatalogOption, ...]
    piece_options: tuple[GuidedCatalogOption, ...]
    product_cards: tuple[GuidedCatalogProductCard, ...]
    variant_options: tuple[GuidedCatalogVariantOption, ...]
    selected_product_key: str
    selected_sku: str
    status_label: str
    path_label: str
    empty_label: str


def build_favorites_catalog_view(
    snapshot_rows: list[dict[str, object]],
    favorite_keys: set[str],
    selected_product_key: str = "",
) -> GuidedCatalogView:
    """Devuelve una vista con únicamente los productos marcados como favoritos.

    No filtra por modo ni jerarquía — incluye piezas de escuela y generales.
    """
    active_rows = [row for row in snapshot_rows if _is_active_row(row)]
    all_cards = _build_product_cards(active_rows, mode_key="basics")
    favorite_cards = tuple(card for card in all_cards if card.key in favorite_keys)
    resolved = _resolve_selected_product_key(favorite_cards, selected_product_key)
    variants = _build_variant_options(rows=active_rows, mode_key="basics", selected_product_key=resolved)
    resolved_sku = _resolve_selected_sku(variants, "")
    count = len(favorite_cards)
    return GuidedCatalogView(
        level_options=(),
        school_options=(),
        gender_options=(),
        profile_options=(),
        bucket_options=(),
        piece_options=(),
        product_cards=favorite_cards,
        variant_options=variants,
        selected_product_key=resolved,
        selected_sku=resolved_sku,
        status_label=f"{count} favorito(s) guardado(s)",
        path_label="Mis Favoritos",
        empty_label="No hay favoritos. Toca ♥ en las piezas del flujo guiado.",
    )


def build_guided_catalog_view(
    *,
    snapshot_rows: list[dict[str, object]],
    mode_key: str,
    level_filter: str,
    school_filter: str,
    gender_filter: str,
    profile_filter: str = "TODOS",
    bucket_filter: str = "TODOS",
    piece_filter: str = "",
    selected_product_key: str = "",
    selected_sku: str = "",
    school_links: list[dict] | None = None,
) -> GuidedCatalogView:
    active_rows = [row for row in snapshot_rows if _is_active_row(row)]
    normalized_mode = "basics" if mode_key == "basics" else "school"
    normalized_level = level_filter.strip()
    normalized_school = school_filter.strip()
    normalized_gender = _normalize_segment_filter(gender_filter)
    normalized_profile = _normalize_school_profile_filter(profile_filter)
    normalized_bucket = _normalize_bucket_filter(bucket_filter)
    normalized_piece = piece_filter.strip()

    mode_rows = [
        row for row in active_rows if _matches_mode(row=row, mode_key=normalized_mode)
    ]
    if normalized_mode == "school" and school_links:
        mode_rows = _inject_linked_products(mode_rows, active_rows, school_links)
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
    gender_options = (
        _build_school_line_options(gender_source_rows)
        if normalized_mode == "school"
        else _build_segment_options(gender_source_rows)
    )
    profile_options = (
        _build_school_profile_options(gender_source_rows)
        if normalized_mode == "school" and normalized_gender == "OFICIAL"
        else tuple()
    )
    bucket_source_rows = [row for row in gender_source_rows if _matches_segment_filter(normalized_gender, row)]
    if normalized_mode == "school" and normalized_gender == "OFICIAL" and normalized_profile != "TODOS":
        bucket_source_rows = [row for row in bucket_source_rows if _matches_school_profile_filter(normalized_profile, row)]
    bucket_options = _build_bucket_options(bucket_source_rows) if normalized_mode == "basics" else tuple()
    piece_source_rows = [row for row in bucket_source_rows if _matches_bucket_filter(normalized_bucket, row)]
    piece_options = _build_piece_options(piece_source_rows) if normalized_mode == "basics" else tuple()

    product_rows, empty_label = _filter_product_rows(
        rows=mode_rows,
        mode_key=normalized_mode,
        level_filter=normalized_level,
        school_filter=normalized_school,
        gender_filter=normalized_gender,
        profile_filter=normalized_profile,
        bucket_filter=normalized_bucket,
        piece_filter=normalized_piece,
    )

    product_cards = _build_product_cards(product_rows, mode_key=normalized_mode)
    resolved_product_key = _resolve_selected_product_key(product_cards, selected_product_key)
    variant_options = _build_variant_options(
        rows=product_rows,
        mode_key=normalized_mode,
        selected_product_key=resolved_product_key,
    )
    resolved_sku = _resolve_selected_sku(variant_options, selected_sku)
    status_label = _build_status_label(
        visible_count=len(product_cards),
        mode_key=normalized_mode,
        level_filter=normalized_level,
        school_filter=normalized_school,
        gender_filter=normalized_gender,
        profile_filter=normalized_profile,
        bucket_filter=normalized_bucket,
        piece_filter=normalized_piece,
    )
    path_label = _build_path_label(
        mode_key=normalized_mode,
        level_filter=normalized_level,
        school_filter=normalized_school,
        gender_filter=normalized_gender,
        profile_filter=normalized_profile,
        bucket_filter=normalized_bucket,
        piece_filter=normalized_piece,
    )
    return GuidedCatalogView(
        level_options=level_options,
        school_options=school_options,
        gender_options=gender_options,
        profile_options=profile_options,
        bucket_options=bucket_options,
        piece_options=piece_options,
        product_cards=product_cards,
        variant_options=variant_options,
        selected_product_key=resolved_product_key,
        selected_sku=resolved_sku,
        status_label=status_label,
        path_label=path_label,
        empty_label=empty_label,
    )


def _is_active_row(row: dict[str, object]) -> bool:
    return bool(row.get("producto_activo")) and bool(row.get("variante_activo"))


def _matches_mode(*, row: dict[str, object], mode_key: str) -> bool:
    school_name = str(row.get("escuela_nombre") or "General").strip() or "General"
    if mode_key == "basics":
        normalized_category_name = _normalize_text(row.get("categoria_nombre"))
        return school_name == "General" and normalized_category_name not in REGULAR_CATEGORY_EXCLUSION_SET
    return school_name != "General" and _classify_line_type(row) in {"DEPORTIVO", "OFICIAL"}


_LEVEL_ORDER = ["Preescolar", "Primaria", "Secundaria", "Bachillerato"]


def _level_sort_key(name: str) -> tuple[int, str]:
    try:
        return (_LEVEL_ORDER.index(name), name)
    except ValueError:
        return (len(_LEVEL_ORDER), name)


def _build_level_options(rows: list[dict[str, object]]) -> tuple[GuidedCatalogOption, ...]:
    counts: dict[str, int] = {}
    for row in rows:
        level_name = str(row.get("nivel_educativo_nombre") or "").strip()
        if not level_name or level_name == "Sin nivel":
            continue
        counts[level_name] = counts.get(level_name, 0) + 1
    return tuple(
        GuidedCatalogOption(key=level_name, label=level_name, count=counts[level_name], enabled=counts[level_name] > 0)
        for level_name in sorted(counts, key=_level_sort_key)
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
    profile_filter: str,
    bucket_filter: str,
    piece_filter: str,
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
    if mode_key == "school" and gender_filter == "OFICIAL" and profile_filter != "TODOS":
        filtered_rows = [row for row in filtered_rows if _matches_school_profile_filter(profile_filter, row)]
    filtered_rows = [row for row in filtered_rows if _matches_bucket_filter(bucket_filter, row)]
    if mode_key == "basics" and not piece_filter:
        return [], "Selecciona un tipo de pieza para ver modelos."
    if piece_filter:
        filtered_rows = [row for row in filtered_rows if _piece_label(row) == piece_filter]
    filtered_rows.sort(key=lambda row: _product_sort_key(row, prefer_deportivo=gender_filter == "DEPORTIVO"))
    if filtered_rows:
        return filtered_rows, ""
    if mode_key == "basics":
        bucket_label = _bucket_label(bucket_filter)
        return [], f"No hay {bucket_label.lower()} disponibles para ese filtro."
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


def _build_school_line_options(rows: list[dict[str, object]]) -> tuple[GuidedCatalogOption, ...]:
    options = (
        ("DEPORTIVO", "Deportivo"),
        ("OFICIAL", "Oficial"),
        ("TODOS", "Todos"),
    )
    built_options: list[GuidedCatalogOption] = []
    for key, label in options:
        count = sum(1 for row in rows if _matches_segment_filter(key, row))
        built_options.append(GuidedCatalogOption(key=key, label=label, count=count, enabled=count > 0))
    return tuple(built_options)


def _build_school_profile_options(rows: list[dict[str, object]]) -> tuple[GuidedCatalogOption, ...]:
    official_rows = [row for row in rows if _matches_segment_filter("OFICIAL", row)]
    options = (
        ("NINA", "Niña"),
        ("NINO", "Niño"),
        ("COMPARTIDO", "Compartido"),
        ("TODOS", "Todos"),
    )
    built_options: list[GuidedCatalogOption] = []
    for key, label in options:
        count = sum(1 for row in official_rows if _matches_school_profile_filter(key, row))
        built_options.append(GuidedCatalogOption(key=key, label=label, count=count, enabled=count > 0))
    return tuple(built_options)


def _build_bucket_options(rows: list[dict[str, object]]) -> tuple[GuidedCatalogOption, ...]:
    options = (
        ("BASICO", "Basicos"),
        ("EXTRA", "Extras"),
        ("TODOS", "Todos"),
    )
    built_options: list[GuidedCatalogOption] = []
    for key, label in options:
        count = sum(1 for row in rows if _matches_bucket_filter(key, row))
        built_options.append(GuidedCatalogOption(key=key, label=label, count=count, enabled=count > 0))
    return tuple(built_options)


def _build_piece_options(rows: list[dict[str, object]]) -> tuple[GuidedCatalogOption, ...]:
    counts: dict[str, int] = {}
    for row in rows:
        piece_label = _piece_label(row)
        if not piece_label:
            continue
        counts[piece_label] = counts.get(piece_label, 0) + 1
    ordered_labels = sorted(counts, key=_piece_group_sort_key)
    return tuple(
        GuidedCatalogOption(
            key=piece_label,
            label=piece_label,
            count=counts[piece_label],
            enabled=counts[piece_label] > 0,
            group_label=_piece_group_label(piece_label),
        )
        for piece_label in ordered_labels
    )


def _build_product_cards(rows: list[dict[str, object]], *, mode_key: str) -> tuple[GuidedCatalogProductCard, ...]:
    grouped: dict[str, list[dict[str, object]]] = {}
    for row in rows:
        grouped.setdefault(_build_family_key(row), []).append(row)

    cards: list[GuidedCatalogProductCard] = []
    for key, family_rows in grouped.items():
        representative = family_rows[0]
        cards.append(_to_grouped_product_card(key, family_rows, representative))
    from pos_uniformes.services.school_tariff_service import _tariff_product_sort_key
    cards.sort(key=lambda card: (*_tariff_product_sort_key(card.tipo_pieza), card.title.lower()))
    return tuple(cards)


def _to_grouped_product_card(
    key: str,
    family_rows: list[dict[str, object]],
    representative: dict[str, object],
) -> GuidedCatalogProductCard:
    price = Decimal(str(representative.get("precio_venta") or "0")).quantize(Decimal("0.01"))
    unique_sizes = []
    seen_sizes: set[str] = set()
    for row in family_rows:
        size_label = str(row.get("talla") or "").strip()
        if not size_label or size_label in seen_sizes:
            continue
        seen_sizes.add(size_label)
        unique_sizes.append(size_label)
    if not unique_sizes:
        subtitle = "Sin variantes disponibles"
    elif len(unique_sizes) <= 3:
        subtitle = "Tallas: " + ", ".join(unique_sizes)
    else:
        subtitle = f"{len(unique_sizes)} tallas disponibles"
    return GuidedCatalogProductCard(
        key=key,
        sku=str(representative.get("sku") or ""),
        title=str(representative.get("producto_nombre_base") or representative.get("producto_nombre") or "Producto"),
        subtitle=subtitle,
        meta_label="",
        price_label=f"${price}",
        gender_key=_classify_gender(representative.get("producto_genero")),
        tipo_pieza=str(representative.get("tipo_pieza_nombre") or ""),
    )


def _build_variant_options(
    *,
    rows: list[dict[str, object]],
    mode_key: str,
    selected_product_key: str,
) -> tuple[GuidedCatalogVariantOption, ...]:
    if not rows:
        return tuple()
    family_rows = [row for row in rows if _build_family_key(row) == selected_product_key]
    family_rows.sort(key=lambda row: _variant_sort_key(row))
    return tuple(_to_variant_option(row) for row in family_rows)


def _to_variant_option(row: dict[str, object]) -> GuidedCatalogVariantOption:
    price = Decimal(str(row.get("precio_venta") or "0")).quantize(Decimal("0.01"))
    size_label = str(row.get("talla") or "").strip()
    label_parts: list[str] = []
    if size_label:
        label_parts.append(f"Talla {size_label}")
    label_parts.append(f"${price}")
    label = " · ".join(label_parts) or str(row.get("sku") or "")
    return GuidedCatalogVariantOption(
        sku=str(row.get("sku") or ""),
        label=label,
        detail_label=label,
        price_label=f"${price}",
    )


def _resolve_selected_product_key(
    product_cards: tuple[GuidedCatalogProductCard, ...],
    selected_product_key: str,
) -> str:
    available = {card.key for card in product_cards}
    if selected_product_key in available:
        return selected_product_key
    return product_cards[0].key if product_cards else ""


def _resolve_selected_sku(
    variant_options: tuple[GuidedCatalogVariantOption, ...],
    selected_sku: str,
) -> str:
    available = {option.sku for option in variant_options}
    if selected_sku in available:
        return selected_sku
    return variant_options[0].sku if variant_options else ""


def _to_product_card(row: dict[str, object]) -> GuidedCatalogProductCard:
    price = Decimal(str(row.get("precio_venta") or "0")).quantize(Decimal("0.01"))
    size_label = str(row.get("talla") or "").strip()
    color_label = _display_color_label(row.get("color"))
    subtitle_parts: list[str] = []
    if size_label:
        subtitle_parts.append(f"Talla {size_label}")
    if color_label:
        subtitle_parts.append(color_label)
    subtitle = " · ".join(subtitle_parts) or "Sin talla ni color"
    return GuidedCatalogProductCard(
        key=str(row.get("sku") or ""),
        sku=str(row.get("sku") or ""),
        title=str(row.get("producto_nombre_base") or row.get("producto_nombre") or "Producto"),
        subtitle=subtitle,
        meta_label="",
        price_label=f"${price}",
        gender_key=_classify_gender(row.get("producto_genero")),
    )


def _display_color_label(raw_value: object) -> str:
    color_label = str(raw_value or "").strip()
    normalized = _normalize_text(color_label).replace(" ", "").replace("-", "")
    if not color_label or normalized in {"sincolor", "adhoc"}:
        return ""
    return color_label


def _build_status_label(
    *,
    visible_count: int,
    mode_key: str,
    level_filter: str,
    school_filter: str,
    gender_filter: str,
    profile_filter: str,
    bucket_filter: str,
    piece_filter: str,
) -> str:
    parts = [f"{visible_count} producto(s) sugeridos"]
    parts.append("Modo: Basicos" if mode_key == "basics" else "Modo: Uniformes")
    if level_filter:
        parts.append(f"Nivel: {level_filter}")
    if school_filter:
        parts.append(f"Escuela: {school_filter}")
    if gender_filter != "TODOS":
        parts.append(f"Linea: {_segment_label(gender_filter)}")
    if gender_filter == "OFICIAL" and profile_filter != "TODOS":
        parts.append(f"Perfil: {_school_profile_label(profile_filter)}")
    if mode_key == "basics" and bucket_filter != "TODOS":
        parts.append(f"Grupo: {_bucket_label(bucket_filter)}")
    if mode_key == "basics" and piece_filter:
        parts.append(f"Pieza: {piece_filter}")
    return " | ".join(parts)


def _build_path_label(
    *,
    mode_key: str,
    level_filter: str,
    school_filter: str,
    gender_filter: str,
    profile_filter: str,
    bucket_filter: str,
    piece_filter: str,
) -> str:
    if mode_key == "basics":
        path_parts = ["Basicos"]
    else:
        path_parts = ["Uniformes", level_filter or "sin nivel", school_filter or "sin escuela"]
    path_parts.append(_segment_label(gender_filter))
    if gender_filter == "OFICIAL" and profile_filter != "TODOS":
        path_parts.append(_school_profile_label(profile_filter))
    if mode_key == "basics" and bucket_filter != "TODOS":
        path_parts.append(_bucket_label(bucket_filter))
    if mode_key == "basics" and piece_filter:
        path_parts.append(piece_filter)
    return " > ".join(path_parts)


def _school_profile_label(profile_key: str) -> str:
    return {
        "NINA": "Niña",
        "NINO": "Niño",
        "COMPARTIDO": "Compartido",
        "TODOS": "Todos",
    }.get(profile_key, "Todos")


def _segment_label(gender_key: str) -> str:
    return {
        "DEPORTIVO": "Deportivo",
        "OFICIAL": "Oficial",
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
    if compact in {"oficial"}:
        return "OFICIAL"
    if compact in {"oficialnina", "nina", "femenino"}:
        return "OFICIAL_NINA"
    if compact in {"oficialnino", "nino", "masculino"}:
        return "OFICIAL_NINO"
    return "TODOS"


def _normalize_school_profile_filter(value: str) -> str:
    normalized = _normalize_text(value).replace(" ", "")
    if normalized in {"nina", "femenino"}:
        return "NINA"
    if normalized in {"nino", "masculino"}:
        return "NINO"
    if normalized in {"compartido", "unisex", "mixto"}:
        return "COMPARTIDO"
    return "TODOS"


def _normalize_bucket_filter(value: str) -> str:
    normalized = _normalize_text(value)
    if normalized in {"basico", "basicos"}:
        return "BASICO"
    if normalized in {"extra", "extras"}:
        return "EXTRA"
    return "TODOS"


def _bucket_label(bucket_key: str) -> str:
    return {
        "BASICO": "Basicos",
        "EXTRA": "Extras",
        "TODOS": "Todos",
    }.get(bucket_key, "Todos")


def _matches_bucket_filter(bucket_key: str, row: dict[str, object]) -> bool:
    if bucket_key == "TODOS":
        return True
    return _classify_basics_bucket(row) == bucket_key


def _matches_segment_filter(filter_key: str, row: dict[str, object]) -> bool:
    line_key = _classify_line_type(row)
    if filter_key == "DEPORTIVO":
        return line_key == "DEPORTIVO"
    if filter_key == "OFICIAL":
        return line_key == "OFICIAL"
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
        gender = _classify_gender(row.get("producto_genero"))
        if gender == "UNISEX":
            # Calceta y Malla sin género explícito son de niña — no incluir en niño
            piece = _normalize_text(row.get("tipo_pieza_nombre"))
            if piece in {"calceta", "malla"}:
                return False
        return gender in {"NINO", "UNISEX"}
    return True


def _matches_school_profile_filter(profile_key: str, row: dict[str, object]) -> bool:
    if profile_key == "TODOS":
        return True
    return _classify_school_profile(row) == profile_key


def _classify_school_profile(row: dict[str, object]) -> str:
    normalized_piece = _normalize_text(row.get("tipo_pieza_nombre"))
    if normalized_piece in {"pants", "pants 2pz", "pants suelto", "pantalon", "short"}:
        return "COMPARTIDO"
    if _is_shared_uniform_top(row):
        return "COMPARTIDO"
    gender_key = _classify_gender(row.get("producto_genero"))
    if gender_key == "NINA":
        return "NINA"
    if gender_key == "NINO":
        return "NINO"
    return "COMPARTIDO"


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


def _classify_basics_bucket(row: dict[str, object]) -> str:
    piece_name = _normalize_text(row.get("tipo_pieza_nombre"))
    garment_name = _normalize_text(row.get("tipo_prenda_nombre"))
    searchable = " ".join(
        [
            piece_name,
            garment_name,
            _normalize_text(row.get("producto_nombre_base")),
            _normalize_text(row.get("producto_nombre")),
            _normalize_text(row.get("producto_descripcion")),
        ]
    )
    if _contains_any(
        searchable,
        (
            "pantalon",
            "falda",
            "pants 2pz",
            "pants2pz",
            "pants suelto",
            "pantssuelto",
            "chamarra",
            "sueter",
            "chaleco",
            "camisa",
            "playera",
            "jumper",
            "short",
        ),
    ):
        return "BASICO"
    if garment_name == "accesorio" or _contains_any(
        searchable,
        ("calceta", "malla", "bata", "boina", "guante", "corbata", "corbatin", "mono", "moño"),
    ):
        return "EXTRA"
    return "BASICO"


def _piece_label(row: dict[str, object]) -> str:
    raw = str(row.get("tipo_pieza_nombre") or "").strip()
    if not raw or raw == "-":
        # Producto sin tipo de pieza — usar nombre base como etiqueta
        return str(row.get("producto_nombre_base") or row.get("producto_nombre") or "Sin pieza").strip() or "Sin pieza"
    return raw


def _build_family_key(row: dict[str, object]) -> str:
    return "||".join(
        [
            _piece_label(row),
            str(row.get("producto_nombre_base") or row.get("producto_nombre") or "").strip(),
        ]
    )


def _variant_sort_key(row: dict[str, object]) -> tuple[tuple[int, object], str, str]:
    return (
        _size_sort_key(row.get("talla")),
        str(row.get("color") or "").strip().lower(),
        str(row.get("sku") or "").strip().lower(),
    )


def _piece_group_sort_key(piece_label: str) -> tuple[int, int, str]:
    from pos_uniformes.services.school_tariff_service import _tariff_product_sort_key
    pieza_order, _ = _tariff_product_sort_key(piece_label.strip())
    return (_piece_group_rank(piece_label), pieza_order, piece_label.lower())


def _piece_group_label(piece_label: str) -> str:
    rank = _piece_group_rank(piece_label)
    if rank == 0:
        return "Prendas principales"
    if rank == 1:
        return "Complementos"
    if rank == 2:
        return "Accesorios"
    return "Especial"


def _piece_group_rank(piece_label: str) -> int:
    normalized = _normalize_text(piece_label)
    if normalized in {
        "camisa",
        "playera",
        "falda",
        "jumper",
        "pantalon",
        "pants 2pz",
        "pants 3pz",
    }:
        return 0
    if normalized in {
        "chaleco",
        "chamarra",
        "pants suelto",
        "short",
        "sueter",
    }:
        return 1
    if normalized in {
        "boina",
        "calceta",
        "corbata",
        "corbatin",
        "guante",
        "malla",
        "mono",
    }:
        return 2
    return 3


def _size_sort_key(raw_value: object) -> tuple[int, object]:
    size = str(raw_value or "").strip()
    normalized = _normalize_text(size).replace(" ", "")
    if not normalized:
        return (9, "")
    if normalized.isdigit():
        return (0, int(normalized))

    alpha_sizes = {
        "xxch": 0,
        "2ch": 0,
        "xch": 1,
        "ch": 2,
        "m": 3,
        "md": 3,
        "med": 3,
        "g": 4,
        "gd": 4,
        "l": 4,
        "xg": 5,
        "eg": 5,
        "exg": 5,
        "xl": 5,
        "xxg": 6,
        "2xg": 6,
        "xxl": 6,
        "3xg": 7,
        "xxxl": 7,
        "uni": 8,
        "u": 8,
    }
    if normalized in alpha_sizes:
        return (1, alpha_sizes[normalized])
    return (5, normalized)


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


def _inject_linked_products(
    school_mode_rows: list[dict[str, object]],
    all_active_rows: list[dict[str, object]],
    school_links: list[dict],
) -> list[dict[str, object]]:
    """Agrega filas sintéticas para productos generales ligados manualmente a escuelas.

    Los productos ligados aparecen junto a los productos propios de la escuela
    en el flujo guiado, sin modificar el catálogo original.
    Usa escuela_id como clave para manejar correctamente escuelas con el mismo nombre.
    """
    # Agrupar links por escuela_id para no confundir escuelas con mismo nombre
    links_by_id: dict[int, tuple[str, set[str]]] = {}
    for link in school_links:
        eid = link.get("escuela_id")
        school_name = str(link.get("escuela_nombre") or "").strip()
        nombre_base = _normalize_text(link.get("producto_nombre_base") or "")
        if eid is None or not school_name or not nombre_base:
            continue
        eid = int(eid)
        if eid not in links_by_id:
            links_by_id[eid] = (school_name, set())
        links_by_id[eid][1].add(nombre_base)

    if not links_by_id:
        return school_mode_rows

    # Nivel por escuela_id (primera ocurrencia no vacía)
    id_to_nivel: dict[int, str] = {}
    for row in all_active_rows:
        eid = row.get("escuela_id")
        nivel = str(row.get("nivel_educativo_nombre") or "").strip()
        if eid is not None and nivel and str(row.get("escuela_nombre") or "") not in ("", "General"):
            id_to_nivel.setdefault(int(eid), nivel)

    # Productos ya presentes en la escuela (por escuela_id)
    already_in_school: dict[int, set[str]] = {}
    for row in school_mode_rows:
        eid = row.get("escuela_id")
        school = str(row.get("escuela_nombre") or "").strip()
        nombre_base = _normalize_text(row.get("producto_nombre_base") or "")
        if eid is not None and school and school != "General":
            already_in_school.setdefault(int(eid), set()).add(nombre_base)

    general_rows = [
        row for row in all_active_rows
        if str(row.get("escuela_nombre") or "General").strip() == "General"
    ]

    injected: list[dict[str, object]] = []
    for escuela_id, (school_name, linked_names) in links_by_id.items():
        nivel = id_to_nivel.get(escuela_id, "")
        existing = already_in_school.get(escuela_id, set())
        for row in general_rows:
            nombre_base_normalized = _normalize_text(row.get("producto_nombre_base") or "")
            if nombre_base_normalized not in linked_names:
                continue
            if nombre_base_normalized in existing:
                continue
            synthetic = dict(row)
            synthetic["escuela_id"] = escuela_id
            synthetic["escuela_nombre"] = school_name
            synthetic["nivel_educativo_nombre"] = nivel
            synthetic["_linked"] = True
            injected.append(synthetic)

    return school_mode_rows + injected
