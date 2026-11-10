"""La franja «Programa» del kiosko se entera sola cuando Daniel aprueba o
rechaza una propuesta (2026-11-10: «ya aprobé y no hubo cambios inmediatos»).

Sin base: la lectura del programa es falsa.
"""

from __future__ import annotations

import os
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from pos_uniformes.ui.helpers import quick_sale_programa_helper as ph
from pos_uniformes.ui.helpers.quick_sale_programa_helper import _Leido, aviso_de_respuesta
from pos_uniformes.ui.views.quick_sale_view import QuickSaleWidget

ESPERANDO = _Leido(7, "Maximoda Club", "CLUB", "Maximoda Profesional")
APROBADO = _Leido(7, "Maximoda Profesional", "PROFESIONAL", None)
RECHAZADO = _Leido(7, "Maximoda Club", "CLUB", None)


class AvisoTests(unittest.TestCase):
    def test_aprobado(self) -> None:
        self.assertEqual(aviso_de_respuesta("Ana", ESPERANDO, APROBADO), "✅ Aprobado: Ana ya es miembro de Maximoda Profesional")

    def test_no_aprobado(self) -> None:
        self.assertIn("no se aprobó", aviso_de_respuesta("Ana", ESPERANDO, RECHAZADO))

    def test_sigue_esperando_no_dice_nada(self) -> None:
        self.assertIsNone(aviso_de_respuesta("Ana", ESPERANDO, ESPERANDO))
        self.assertIsNone(aviso_de_respuesta("Ana", RECHAZADO, RECHAZADO))

    def test_sin_porcentajes(self) -> None:
        for despues in (APROBADO, RECHAZADO):
            self.assertNotIn("%", aviso_de_respuesta("Ana", ESPERANDO, despues))


class FranjaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _kiosko(self, lecturas):
        w = QuickSaleWidget(SimpleNamespace(offline_mode=False, _kiosk_lookup_from_cache=None, _db_online=True))
        w._employee_code = "VEND-2"
        w._cliente = {"id": 7, "codigo": "CLI-000007", "nombre": "Ana López", "en_linea": True}
        cola = list(lecturas)

        def leer(_cliente_id):
            w._programa_leido = cola.pop(0) if len(cola) > 1 else cola[0]
            return w._programa_leido

        w._leer_programa = leer
        w._flash_scan_hint = MagicMock()
        return w

    def test_mientras_espera_vigila_y_al_aprobar_cambia_solo(self) -> None:
        w = self._kiosko([ESPERANDO, APROBADO])
        w._pintar_programa_bar()
        self.assertIn("esperando aprobación", w._programa_label.text())
        self.assertTrue(w._programa_timer.isActive())
        self.assertEqual(w._programa_timer.interval(), ph.REVISAR_PROPUESTA_MS)

        w._programa_timer.timeout.emit()
        self.assertEqual(w._programa_label.text(), "★ Miembro Maximoda Profesional")
        w._flash_scan_hint.assert_called_once_with("✅ Aprobado: Ana López ya es miembro de Maximoda Profesional")
        self.assertFalse(w._programa_timer.isActive(), "ya no hay nada que esperar")

    def test_sin_propuesta_no_vigila(self) -> None:
        w = self._kiosko([RECHAZADO])
        w._pintar_programa_bar()
        self.assertFalse(w._programa_timer.isActive())

    def test_si_quitan_al_cliente_deja_de_vigilar(self) -> None:
        w = self._kiosko([ESPERANDO])
        w._pintar_programa_bar()
        w._cliente = None
        w._pintar_programa_bar()
        self.assertFalse(w._programa_timer.isActive())

    def test_si_cambian_de_cliente_no_avisa_del_anterior(self) -> None:
        w = self._kiosko([ESPERANDO, APROBADO])
        w._pintar_programa_bar()
        w._cliente = {"id": 8, "codigo": "CLI-000008", "nombre": "Otra", "en_linea": True}
        with patch.object(w, "_leer_programa") as leer:
            w._revisar_propuesta()
        leer.assert_not_called()
        w._flash_scan_hint.assert_not_called()
        self.assertFalse(w._programa_timer.isActive())


if __name__ == "__main__":
    unittest.main()
