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


class PreflightBaseAdelanteTests(unittest.TestCase):
    """El satélite viejo contra una base ya migrada: arranca igual. Antes decía
    "la base está desactualizada", que era justo al revés (Daniel, 2026-09-22)."""

    def test_base_mas_nueva_que_el_programa_no_bloquea(self) -> None:
        from unittest.mock import patch
        from pos_uniformes.database import preflight

        status = preflight.DatabasePreflightStatus(
            current_heads=("4f5a6b7c8d9e",), expected_heads=("3e4f5a6b7c8d",), base_adelante=True,
        )
        with patch.object(preflight, "inspect_database_status", return_value=status):
            self.assertIs(preflight.assert_database_ready(), status)

    def test_base_atrasada_sigue_bloqueando(self) -> None:
        from unittest.mock import patch
        from pos_uniformes.database import preflight

        status = preflight.DatabasePreflightStatus(
            current_heads=("3e4f5a6b7c8d",), expected_heads=("4f5a6b7c8d9e",), base_adelante=False,
        )
        with patch.object(preflight, "inspect_database_status", return_value=status):
            with self.assertRaises(preflight.DatabasePreflightError):
                preflight.assert_database_ready()

    def test_reconoce_una_base_descendiente_como_adelantada(self) -> None:
        from pos_uniformes.database import preflight

        config = preflight._build_alembic_config()
        from alembic.script import ScriptDirectory

        heads = tuple(ScriptDirectory.from_config(config).get_heads())
        # La cabeza real contra una revisión anterior: la base va adelante.
        self.assertTrue(preflight._base_va_adelante(config, heads, ("3e4f5a6b7c8d",)))
        # Al revés, no.
        self.assertFalse(preflight._base_va_adelante(config, ("3e4f5a6b7c8d",), heads))
