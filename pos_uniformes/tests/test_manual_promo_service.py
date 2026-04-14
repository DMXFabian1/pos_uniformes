from __future__ import annotations

from types import SimpleNamespace
import unittest

from pos_uniformes.services.manual_promo_service import (
    DEFAULT_PROMO_AUTHORIZATION_CODE,
    ManualPromoService,
)
from pos_uniformes.services.auth_service import AuthService


class ManualPromoServiceTests(unittest.TestCase):
    def test_ensure_code_hash_uses_new_default_for_empty_hash(self) -> None:
        config = SimpleNamespace(promo_authorization_code_hash=None)

        code_hash = ManualPromoService._ensure_code_hash(config)

        self.assertTrue(AuthService.verify_password(DEFAULT_PROMO_AUTHORIZATION_CODE, code_hash))

    def test_ensure_code_hash_rotates_legacy_default_to_new_default(self) -> None:
        config = SimpleNamespace(
            promo_authorization_code_hash=AuthService.hash_password("PROMO2026")
        )

        code_hash = ManualPromoService._ensure_code_hash(config)

        self.assertTrue(AuthService.verify_password(DEFAULT_PROMO_AUTHORIZATION_CODE, code_hash))
        self.assertFalse(AuthService.verify_password("PROMO2026", code_hash))

    def test_ensure_code_hash_preserves_custom_existing_code(self) -> None:
        config = SimpleNamespace(
            promo_authorization_code_hash=AuthService.hash_password("555999")
        )

        code_hash = ManualPromoService._ensure_code_hash(config)

        self.assertTrue(AuthService.verify_password("555999", code_hash))
        self.assertFalse(AuthService.verify_password(DEFAULT_PROMO_AUTHORIZATION_CODE, code_hash))


if __name__ == "__main__":
    unittest.main()
