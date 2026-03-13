from __future__ import annotations

import importlib
import unittest

from pos_uniformes.database.connection import engine
from pos_uniformes.database.preflight import assert_database_ready


class StartupSmokeTests(unittest.TestCase):
    @classmethod
    def tearDownClass(cls) -> None:
        engine.dispose()
        super().tearDownClass()

    def test_database_preflight_passes(self) -> None:
        status = assert_database_ready()
        self.assertTrue(status.is_up_to_date)
        self.assertTrue(status.current_heads)
        self.assertEqual(status.current_heads, status.expected_heads)

    def test_critical_modules_import(self) -> None:
        modules = (
            "pos_uniformes.main",
            "pos_uniformes.ui.main_window",
            "pos_uniformes.services.business_settings_service",
            "pos_uniformes.services.manual_promo_service",
            "pos_uniformes.services.marketing_audit_service",
            "pos_uniformes.utils.label_generator",
            "pos_uniformes.utils.product_templates",
        )
        for module_name in modules:
            with self.subTest(module=module_name):
                module = importlib.import_module(module_name)
                self.assertIsNotNone(module)
