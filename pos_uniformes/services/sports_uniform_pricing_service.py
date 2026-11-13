"""Reglas de precio para composiciones de uniforme deportivo."""

from __future__ import annotations

from decimal import Decimal
from typing import Mapping

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


# ─── Promo 3pz con el pants rebajado (E7) ───────────────────────────────
#
# Daniel (2026-11-12): «Sí, que no aplique». Una prenda en Oferta o
# Liquidación no lleva ningún otro descuento ni Monedero, y la playera a
# $100 es un descuento que cuelga del pants. Si el pants base está rebajado,
# la promo 3pz no aplica: la playera se cobra a su precio normal y, como
# prenda normal, lleva sus descuentos y Monedero de siempre (la playera
# misma no está rebajada).

#: Lo que se le agrega al nombre de la playera en el carrito del kiosko.
PROMO_NAME_SUFFIX = " (promo 3pz)"

_LLAVES_PROMO_PLAYERA = ("precio_base", "sports_uniform_role", "sports_uniform_base_sku", "promo_3pz")
_LLAVES_PROMO_BASE = ("sports_uniform_role", "sports_uniform_playera_sku", "promo_3pz")


def _sku(valor) -> str:
    return str(valor or "").strip().upper()


def promo_3pz_aplica(base_item: Mapping | None) -> bool:
    """La promo 3pz aplica solo si el pants base no está rebajado."""
    from pos_uniformes.services.rebaja_service import es_rebajado

    return base_item is None or not es_rebajado(base_item)


def aviso_promo_3pz_no_aplica(base_item: Mapping | None) -> str:
    """«La playera va a precio normal: el pants ya está en Oferta.»"""
    from pos_uniformes.services.rebaja_service import ETIQUETAS, LLAVE

    etiqueta = ETIQUETAS.get(str((base_item or {}).get(LLAVE) or ""), ETIQUETAS["oferta"])
    return f"La playera va a precio normal: el pants ya está en {etiqueta}."


def regresar_playera_a_precio_normal(item: dict) -> bool:
    """Quita la promo de un renglón de playera del kiosko. True si la tenía."""
    if str(item.get("sports_uniform_role") or "") != "playera" or "precio_base" not in item:
        return False
    item["precio"] = item["precio_base"]
    nombre = str(item.get("nombre") or "")
    if nombre.endswith(PROMO_NAME_SUFFIX):
        item["nombre"] = nombre[: -len(PROMO_NAME_SUFFIX)]
    for llave in _LLAVES_PROMO_PLAYERA:
        item.pop(llave, None)
    return True


def _playera_de(base: Mapping, item: Mapping) -> bool:
    if item is base or str(item.get("sports_uniform_role") or "") != "playera":
        return False
    base_de_la_playera = _sku(item.get("sports_uniform_base_sku"))
    if base_de_la_playera:
        return base_de_la_playera == _sku(base.get("sku"))
    playera_sku = _sku(base.get("sports_uniform_playera_sku"))
    return bool(playera_sku) and _sku(item.get("sku")) == playera_sku


def quitar_promo_3pz_de_pants_rebajados(items: list[dict]) -> tuple[list[str], list[dict]]:
    """Revisa el carrito del kiosko: cada pants base rebajado pierde la promo.

    Sus playeras regresan a su precio normal y el pants deja de ser base de
    la promo. Devuelve (avisos para la empleada, playeras que se regresaron)
    para que el kiosko les busque su propia rebaja, si la tienen. Sin pants
    rebajados no cambia nada."""
    avisos: list[str] = []
    regresadas: list[dict] = []
    for base in items:
        if str(base.get("sports_uniform_role") or "") != "base" or promo_3pz_aplica(base):
            continue
        suyas = [it for it in items if _playera_de(base, it) and regresar_playera_a_precio_normal(it)]
        for llave in _LLAVES_PROMO_BASE:
            base.pop(llave, None)
        regresadas.extend(suyas)
        aviso = aviso_promo_3pz_no_aplica(base)
        if suyas and aviso not in avisos:
            avisos.append(aviso)
    return avisos, regresadas
