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
        data = build_escpos_bytes("x", EscPosSettings(full_cut=True))
        self.assertTrue(data.endswith(b"\x1dVA\x00"))       # GS V 65 n (avanza y corta)

    def test_corte_parcial(self) -> None:
        data = build_escpos_bytes("x", EscPosSettings(full_cut=False))
        self.assertTrue(data.endswith(b"\x1dVB\x00"))       # GS V 66 n

    def test_caja_y_acentos_en_cp850(self) -> None:
        # ┌ = 0xDA, Á = 0xB5, é = 0x82 en CP850 (no se pierden).
        data = build_escpos_bytes("┌ BÁSICOS Suéter", EscPosSettings(feed_lines=0))
        self.assertIn(b"\xda", data)   # ┌
        self.assertIn(b"\xb5", data)   # Á
        self.assertIn(b"\x82", data)   # é
        self.assertNotIn(b"?", data)   # nada se reemplazó

    def test_el_avance_lo_calcula_la_impresora_y_no_nosotros(self) -> None:
        """Antes se empujaban 3 renglones a ciegas antes de `GS V 0`.

        La cuchilla está ~1.5 cm por encima del cabezal, así que tres no
        alcanzaban: el último renglón del ticket salía partido y el sobrante
        encabezaba el siguiente (Daniel, 2026-10-07). `GS V 65` avanza hasta
        la posición de corte de ESA impresora, que ella sí conoce.
        """
        data = build_escpos_bytes("x", EscPosSettings(feed_lines=3, full_cut=True))
        self.assertNotIn(b"\n\n\n", data)
        self.assertTrue(data.endswith(b"\x1dVA\x00"))

    def test_se_puede_volver_al_avance_a_mano(self) -> None:
        """Por si alguna impresora vieja no entendiera `GS V 65`."""
        data = build_escpos_bytes(
            "x", EscPosSettings(feed_lines=3, full_cut=True, corte_calculado=False)
        )
        self.assertTrue(data.endswith(b"\n\n\n\x1dV\x00"))


if __name__ == "__main__":
    unittest.main()
