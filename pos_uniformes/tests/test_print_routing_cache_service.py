"""Tests del cache local de modo de impresión (ajuste por máquina)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pos_uniformes.services.print_routing_cache_service import (
    MODO_LOCAL,
    MODO_SATELITE,
    enviar_al_satelite_activo,
    load_print_routing,
    save_print_routing,
)

_MOD = "pos_uniformes.services.print_routing_cache_service.satellite_data_dir"


class PrintRoutingCacheTests(unittest.TestCase):
    def test_default_es_local(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            with patch(_MOD, return_value=Path(d)):
                self.assertEqual(load_print_routing(), (MODO_LOCAL, "principal"))
                self.assertFalse(enviar_al_satelite_activo())

    def test_roundtrip_satelite(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            with patch(_MOD, return_value=Path(d)):
                save_print_routing(MODO_SATELITE, "kiosko")
                self.assertEqual(load_print_routing(), (MODO_SATELITE, "kiosko"))
                self.assertTrue(enviar_al_satelite_activo())

    def test_origen_vacio_cae_a_principal(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            with patch(_MOD, return_value=Path(d)):
                save_print_routing(MODO_SATELITE, "   ")
                self.assertEqual(load_print_routing(), (MODO_SATELITE, "principal"))

    def test_modo_invalido_al_guardar_falla(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            with patch(_MOD, return_value=Path(d)):
                with self.assertRaises(ValueError):
                    save_print_routing("OTRO")

    def test_corrupto_cae_a_local(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            with patch(_MOD, return_value=Path(d)):
                cache = Path(d) / "data" / "print_routing.json"
                cache.parent.mkdir(parents=True, exist_ok=True)
                cache.write_text("{ no json", encoding="utf-8")
                self.assertEqual(load_print_routing(), (MODO_LOCAL, "principal"))

    def test_modo_desconocido_en_archivo_cae_a_local(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            with patch(_MOD, return_value=Path(d)):
                cache = Path(d) / "data" / "print_routing.json"
                cache.parent.mkdir(parents=True, exist_ok=True)
                cache.write_text('{"modo": "XYZ", "origen": "a"}', encoding="utf-8")
                self.assertEqual(load_print_routing()[0], MODO_LOCAL)


if __name__ == "__main__":
    unittest.main()
