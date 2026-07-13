"""Tests del armado de bytes ESC/POS para tickets/hojas."""

from __future__ import annotations

import unittest

from pos_uniformes.services.escpos_settings_cache_service import EscPosSettings
from pos_uniformes.ui.helpers.escpos_ticket_print_helper import build_escpos_bytes


class BuildEscPosBytesTests(unittest.TestCase):
    def test_prefijo_init_y_codepage(self) -> None:
        data = build_escpos_bytes("hola", EscPosSettings(codepage=2, feed_lines=0))
        self.assertTrue(data.startswith(b"\x1b@"))          # ESC @ (init)
        self.assertIn(b"\x1bt\x02", data)                   # ESC t 2 (CP850)

    def test_corte_total_al_final(self) -> None:
        data = build_escpos_bytes("x", EscPosSettings(full_cut=True, feed_lines=0))
        self.assertTrue(data.endswith(b"\x1dV\x00"))        # GS V 0 (corte total)

    def test_corte_parcial(self) -> None:
        data = build_escpos_bytes("x", EscPosSettings(full_cut=False, feed_lines=0))
        self.assertTrue(data.endswith(b"\x1dV\x01"))        # GS V 1 (corte parcial)

    def test_caja_y_acentos_en_cp850(self) -> None:
        # ┌ = 0xDA, Á = 0xB5, é = 0x82 en CP850 (no se pierden).
        data = build_escpos_bytes("┌ BÁSICOS Suéter", EscPosSettings(feed_lines=0))
        self.assertIn(b"\xda", data)   # ┌
        self.assertIn(b"\xb5", data)   # Á
        self.assertIn(b"\x82", data)   # é
        self.assertNotIn(b"?", data)   # nada se reemplazó

    def test_feed_antes_del_corte(self) -> None:
        data = build_escpos_bytes("x", EscPosSettings(feed_lines=3, full_cut=True))
        # 3 saltos de línea justo antes del comando de corte
        self.assertIn(b"\n\n\n\x1dV\x00", data)


if __name__ == "__main__":
    unittest.main()
