"""La Libreta de la empleada, agrupada en recuadros (Daniel, 2026-11-12)."""

from __future__ import annotations

import os
import unittest
from datetime import date

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication


class LibretaAgrupadaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _ventana(self, code="VEND-3"):
        from pos_uniformes.ui.quote_satellite_window import QuoteSatelliteWindow

        win = QuoteSatelliteWindow(user_id=1, offline_mode=True)
        win._gafete_libreta_valido = lambda c: True
        win._refresh_libreta_view = lambda: None
        win.libreta_gate_input.setText(code)
        win._on_libreta_gate_scan()
        self.addCleanup(win.close)
        return win

    def _marco(self, win, nombre):
        return win._libreta_grupos[nombre][0]

    def test_cada_cosa_en_su_recuadro(self):
        win = self._ventana()
        grupos = win._libreta_grupos
        self.assertTrue(grupos["ventas"][0].isAncestorOf(win.libreta_emp_list))
        self.assertTrue(grupos["pago"][0].isAncestorOf(win.libreta_prestamo_button))
        self.assertTrue(grupos["descansos"][0].isAncestorOf(win.libreta_descanso_button))
        self.assertTrue(grupos["avisos"][0].isAncestorOf(win.libreta_descanso_respuesta))
        self.assertTrue(win.libreta_emp_cuerpo.isAncestorOf(win.libreta_nivel_tarjeta))
        # La tarjeta naranja del ciclo ya no está en la pantalla: sus datos sí.
        self.assertFalse(win.libreta_view.isAncestorOf(win.libreta_ciclo_banner))
        self.assertTrue(grupos["pago"][0].isAncestorOf(win._libreta_ciclo_tiles[0][0]))

    def test_un_recuadro_sin_nada_no_se_ve(self):
        win = self._ventana()
        self.assertTrue(self._marco(win, "avisos").isHidden())
        win.libreta_descanso_respuesta.setText("✅ Daniel aprobó tu descanso.")
        win.libreta_descanso_respuesta.setVisible(True)
        self.assertFalse(self._marco(win, "avisos").isHidden())
        win.libreta_descanso_respuesta.setVisible(False)
        self.assertTrue(self._marco(win, "avisos").isHidden())

    def test_el_pago_sale_con_el_ciclo_y_se_va_sin_el(self):
        win = self._ventana()
        self.assertTrue(self._marco(win, "pago").isHidden())
        win.libreta_ciclo_banner.setVisible(True)
        win._pintar_ciclo_libreta({"comisiones": 73, "proximo_pago": date(2026, 11, 14), "faltan": 2,
                                   "hoy": date(2026, 11, 12), "descanso": date(2026, 11, 15)})
        self.assertFalse(self._marco(win, "pago").isHidden())
        self.assertFalse(self._marco(win, "descansos").isHidden())
        win.libreta_ciclo_banner.setVisible(False)
        self.assertTrue(all(t.isHidden() for t, _v, _c in win._libreta_ciclo_tiles))
        self.assertTrue(self._marco(win, "pago").isHidden())

    def test_el_dueno_no_ve_lo_de_la_empleada(self):
        win = self._ventana("VEND-1")
        self.assertTrue(self._marco(win, "ventas").isHidden())
        self.assertTrue(self._marco(win, "pago").isHidden())
        self.assertTrue(self._marco(win, "avisos").isHidden())


if __name__ == "__main__":
    unittest.main()
