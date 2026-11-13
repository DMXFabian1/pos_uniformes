"""Lo que queda del contexto de descuento de la Caja antigua (2026-11-12).

Solo la validación del código: el corte administrativo pide el mismo PIN.
"""

from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pos_uniformes.services.sale_discount_context_service import verify_sale_manual_promo_code


class SaleDiscountContextServiceTests(unittest.TestCase):
    def test_verify_sale_manual_promo_code_raises_on_invalid_code(self) -> None:
        fake_service = SimpleNamespace(verify_authorization_code=lambda session, code: False)
        with patch(
            "pos_uniformes.services.sale_discount_context_service._resolve_sale_manual_promo_dependencies",
            return_value=fake_service,
        ):
            with self.assertRaisesRegex(ValueError, "Codigo invalido"):
                verify_sale_manual_promo_code(object(), "bad")

    def test_verify_sale_manual_promo_code_accepts_valid_code(self) -> None:
        fake_service = SimpleNamespace(verify_authorization_code=lambda session, code: code == "ok")
        with patch(
            "pos_uniformes.services.sale_discount_context_service._resolve_sale_manual_promo_dependencies",
            return_value=fake_service,
        ):
            self.assertIsNone(verify_sale_manual_promo_code(object(), "ok"))

    def test_lo_de_la_caja_ya_no_existe(self) -> None:
        from pos_uniformes.services import sale_discount_context_service as mod

        for nombre in (
            "load_sale_discount_presets",
            "build_sale_discount_context",
            "calculate_sale_discount_pricing",
            "resolve_sale_manual_discount_transition",
        ):
            self.assertFalse(hasattr(mod, nombre), nombre)


if __name__ == "__main__":
    unittest.main()
