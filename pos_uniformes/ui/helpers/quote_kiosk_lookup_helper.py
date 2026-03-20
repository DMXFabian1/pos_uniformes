"""Helpers visibles para la pantalla kiosko de Presupuestos."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from pos_uniformes.services.quote_kiosk_lookup_service import QuoteKioskLookupSnapshot
from pos_uniformes.utils.product_name import sanitize_product_display_name


@dataclass(frozen=True)
class QuoteKioskBadgeState:
    text: str
    tone: str


@dataclass(frozen=True)
class QuoteKioskLookupView:
    sku_label: str
    product_label: str
    price_label: str
    status_badge: QuoteKioskBadgeState
    detail_label: str
    context_label: str
    notes_label: str


@dataclass(frozen=True)
class QuoteKioskRecentScanRowView:
    sku: str
    values: tuple[object, ...]


def build_empty_quote_kiosk_lookup_view() -> QuoteKioskLookupView:
    return QuoteKioskLookupView(
        sku_label="Escanea un SKU",
        product_label="El producto aparecera aqui.",
        price_label="$0.00",
        status_badge=QuoteKioskBadgeState(text="Sin consulta", tone="neutral"),
        detail_label="Talla, color y tipo apareceran despues del escaneo.",
        context_label="Escuela y contexto del producto se mostraran aqui.",
        notes_label="",
    )


def build_error_quote_kiosk_lookup_view(error_message: str) -> QuoteKioskLookupView:
    return QuoteKioskLookupView(
        sku_label="No encontrado",
        product_label=error_message,
        price_label="$0.00",
        status_badge=QuoteKioskBadgeState(text="Revisar SKU", tone="danger"),
        detail_label="Verifica el codigo y vuelve a escanear.",
        context_label="Solo se muestran presentaciones activas del catalogo.",
        notes_label="",
    )


def build_quote_kiosk_lookup_view(snapshot: QuoteKioskLookupSnapshot) -> QuoteKioskLookupView:
    product_label = sanitize_product_display_name(snapshot.product_name)
    return QuoteKioskLookupView(
        sku_label=snapshot.sku,
        product_label=product_label,
        price_label=f"${Decimal(snapshot.price).quantize(Decimal('0.01'))}",
        status_badge=QuoteKioskBadgeState(text="Listo para cotizar", tone="positive"),
        detail_label=(
            f"Talla {snapshot.size_label} | Color {snapshot.color_label} | "
            f"{snapshot.garment_type_name} | {snapshot.piece_type_name}"
        ),
        context_label=(
            f"Escuela {snapshot.school_name} | Ubicacion {snapshot.location_label} | {snapshot.origin_label}"
        ),
        notes_label=snapshot.description_text.strip() or "Sin descripcion adicional.",
    )


def push_quote_kiosk_recent_scan(
    history: list[QuoteKioskLookupSnapshot],
    snapshot: QuoteKioskLookupSnapshot,
    *,
    limit: int = 8,
) -> list[QuoteKioskLookupSnapshot]:
    next_history = [entry for entry in history if entry.sku != snapshot.sku]
    next_history.insert(0, snapshot)
    return next_history[:limit]


def build_quote_kiosk_recent_scan_rows(
    history: list[QuoteKioskLookupSnapshot],
) -> tuple[QuoteKioskRecentScanRowView, ...]:
    rows: list[QuoteKioskRecentScanRowView] = []
    for snapshot in history:
        rows.append(
            QuoteKioskRecentScanRowView(
                sku=snapshot.sku,
                values=(
                    snapshot.sku,
                    sanitize_product_display_name(snapshot.product_name),
                    f"${Decimal(snapshot.price).quantize(Decimal('0.01'))}",
                    snapshot.school_name,
                    f"{snapshot.size_label} / {snapshot.color_label}",
                ),
            )
        )
    return tuple(rows)
