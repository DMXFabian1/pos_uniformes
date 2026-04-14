"""Subflujo reutilizable de uniforme deportivo para Presupuestos."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from pos_uniformes.services.presupuesto_service import PresupuestoItemInput
from pos_uniformes.services.sale_cart_update_service import add_sale_cart_variants
from pos_uniformes.services.sports_uniform_pricing_service import (
    THREE_PIECE_PLAYERA_PRICING_KEY,
    THREE_PIECE_PLAYERA_PRICING_LABEL,
    THREE_PIECE_PLAYERA_PRICE,
    build_three_piece_playera_price_override,
)
from pos_uniformes.ui.helpers.sale_sports_uniform_helper import (
    SaleSportsUniformResolution,
    attach_sports_uniform_trace_to_cart_lines,
    build_sports_uniform_prototype_note,
    resolve_sale_scan_variants,
)


@dataclass(frozen=True)
class QuoteSportsUniformAddResult:
    resolution: SaleSportsUniformResolution
    feedback_message: str


def add_quote_scan_variants(
    parent,
    session,
    *,
    quote_cart: list[dict[str, object]],
    scanned_variant,
    quantity: int,
    variant_loader,
) -> QuoteSportsUniformAddResult | None:
    resolution = resolve_sale_scan_variants(
        parent,
        session,
        scanned_variant,
        variant_loader=variant_loader,
    )
    if resolution is None:
        return None

    playera_override_by_sku: dict[str, dict[str, object]] | None = None
    if resolution.composed_as_three_pieces and len(resolution.variants) >= 2:
        playera_variant = resolution.variants[1]
        playera_override_by_sku = {
            str(getattr(playera_variant, "sku", "") or "").strip().upper(): build_three_piece_playera_price_override(
                playera_variant
            )
        }

    updated_lines = add_sale_cart_variants(
        quote_cart,
        variants=list(resolution.variants),
        quantity=quantity,
        stock_validator=lambda _variant, _quantity: None,
        line_overrides_by_sku=playera_override_by_sku,
    )

    variant_by_sku = {
        str(getattr(variant, "sku", "") or "").strip().upper(): variant for variant in resolution.variants
    }
    for line_item in updated_lines:
        sku = str(line_item.get("sku") or "").strip().upper()
        variant = variant_by_sku.get(sku)
        if variant is None:
            continue
        _enrich_quote_line_item(line_item, variant=variant)

    feedback_message = f"{str(getattr(scanned_variant, 'sku', '') or '').strip().upper()} agregado al presupuesto."
    if resolution.composed_as_three_pieces and len(resolution.variants) >= 2:
        base_variant, playera_variant = resolution.variants[0], resolution.variants[1]
        trace_note = build_sports_uniform_prototype_note(base_variant, playera_variant)
        attach_sports_uniform_trace_to_cart_lines(
            updated_lines,
            trace_note=trace_note,
            base_sku=str(getattr(base_variant, "sku", "") or ""),
            playera_sku=str(getattr(playera_variant, "sku", "") or ""),
        )
        feedback_message = (
            "Presupuesto con conjunto deportivo 3pz: "
            f"{getattr(base_variant, 'sku', '')} + {getattr(playera_variant, 'sku', '')}. "
            f"Playera aplicada a ${THREE_PIECE_PLAYERA_PRICE}."
        )
        if resolution.size_hint:
            feedback_message = f"{feedback_message} {resolution.size_hint}"

    return QuoteSportsUniformAddResult(
        resolution=resolution,
        feedback_message=feedback_message,
    )


def build_quote_presupuesto_inputs(quote_cart: list[dict[str, object]]) -> list[PresupuestoItemInput]:
    inputs: list[PresupuestoItemInput] = []
    for item in quote_cart:
        producto_nombre = str(item.get("producto_nombre") or "").strip()
        pricing_rule_label = _resolve_line_pricing_rule_label(item)
        inputs.append(
            PresupuestoItemInput(
                sku=str(item["sku"]),
                cantidad=int(item["cantidad"]),
                precio_unitario=Decimal(str(item.get("precio_unitario") or "0.00")),
                descripcion_snapshot=producto_nombre or None,
                pricing_rule_key=_resolve_line_pricing_rule_key(item),
                pricing_rule_label=pricing_rule_label,
            )
        )
    return inputs


def build_three_piece_quote_description(base_name: str, *, school_name: str = "") -> str:
    normalized = str(base_name or "").strip()
    normalized_school = str(school_name or "").strip()
    visible_label = (
        f"{THREE_PIECE_PLAYERA_PRICING_LABEL} - {normalized_school}"
        if normalized_school
        else THREE_PIECE_PLAYERA_PRICING_LABEL
    )
    if not normalized:
        return visible_label
    if THREE_PIECE_PLAYERA_PRICING_LABEL.casefold() in normalized.casefold():
        return normalized
    return f"{normalized} ({visible_label})"


def _enrich_quote_line_item(line_item: dict[str, object], *, variant) -> None:
    product = getattr(variant, "producto", None)
    pricing_rule_label = _resolve_line_pricing_rule_label(line_item)
    school_name = str(getattr(getattr(product, "escuela", None), "nombre", "") or "General")

    base_name = str(getattr(product, "nombre_base", "") or getattr(product, "nombre", "") or "").strip()
    line_item["producto_nombre"] = (
        build_three_piece_quote_description(base_name, school_name=school_name)
        if pricing_rule_label == THREE_PIECE_PLAYERA_PRICING_LABEL
        else base_name
    )
    line_item["escuela_nombre"] = school_name
    line_item["nivel_educativo_nombre"] = str(
        getattr(getattr(product, "nivel_educativo", None), "nombre", "") or "Sin nivel"
    )


def _resolve_line_pricing_rule_label(line_item: dict[str, object]) -> str:
    explicit_label = str(line_item.get("pricing_rule_label") or "").strip()
    if explicit_label:
        return explicit_label
    product_name = str(line_item.get("producto_nombre") or "").strip()
    if THREE_PIECE_PLAYERA_PRICING_LABEL.casefold() in product_name.casefold():
        return THREE_PIECE_PLAYERA_PRICING_LABEL
    return ""


def _resolve_line_pricing_rule_key(line_item: dict[str, object]) -> str:
    explicit_key = str(line_item.get("pricing_rule_key") or "").strip()
    if explicit_key:
        return explicit_key
    if _resolve_line_pricing_rule_label(line_item) == THREE_PIECE_PLAYERA_PRICING_LABEL:
        return THREE_PIECE_PLAYERA_PRICING_KEY
    return ""
