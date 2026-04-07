"""Reglas de precio para composiciones de uniforme deportivo."""

from __future__ import annotations

from decimal import Decimal

THREE_PIECE_PLAYERA_PRICE = Decimal("100.00")
THREE_PIECE_PLAYERA_PRICING_KEY = "SPORTS_UNIFORM_3PZ_PLAYERA"
THREE_PIECE_PLAYERA_PRICING_LABEL = "Conjunto deportivo 3pz"


def build_three_piece_playera_price_override(playera_variant) -> dict[str, object]:
    base_price = Decimal(str(getattr(playera_variant, "precio_venta", "0.00") or "0.00")).quantize(Decimal("0.01"))
    return {
        "precio_unitario": THREE_PIECE_PLAYERA_PRICE,
        "precio_base": base_price,
        "pricing_rule_key": THREE_PIECE_PLAYERA_PRICING_KEY,
        "pricing_rule_label": THREE_PIECE_PLAYERA_PRICING_LABEL,
    }


def build_three_piece_playera_price_note(playera_variant) -> str:
    base_price = Decimal(str(getattr(playera_variant, "precio_venta", "0.00") or "0.00")).quantize(Decimal("0.01"))
    return f"Playera en conjunto 3pz a 100.00 (precio normal {base_price})."
