"""Validación del código de autorización (PIN) que usaba la promo manual de Caja.

2026-11-12: la Caja antigua se retiró del POS. Daniel: «la caja antigua ya no
es de utilidad, todo lo demás corre en libreta y kioskos y es lo único que
importa, es donde vive nuestra operación». De este módulo solo queda la
validación del código, porque el corte administrativo de main_window pide el
mismo PIN. El contexto de descuento, la promo manual, los presets y los
cálculos del carrito se fueron con la Caja.
"""

from __future__ import annotations


def verify_sale_manual_promo_code(session, code: str) -> None:
    manual_promo_service = _resolve_sale_manual_promo_dependencies()
    if not manual_promo_service.verify_authorization_code(session, code):
        raise ValueError("Codigo invalido.")


def _resolve_sale_manual_promo_dependencies():
    from pos_uniformes.services.manual_promo_service import ManualPromoService

    return ManualPromoService
