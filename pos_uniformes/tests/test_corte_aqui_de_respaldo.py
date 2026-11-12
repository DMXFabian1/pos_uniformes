"""El corte sale aquí si la PC de cortes está apagada.

Daniel, 2026-11-12: «en este momento cada PC tiene su propia impresora,
debería poder imprimir aunque el kiosko esté apagado». Con la PC de cortes
encendida, se sigue mandando allá (privacidad, 2026-10-07).
"""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QDialog, QPushButton

from pos_uniformes.database.models import TipoTrabajo
from pos_uniformes.services import print_routing_cache_service as ruteo
from pos_uniformes.ui.helpers import ticket_routing_helper as rt

APAGADO = [{"identificador": "kiosko", "nombre": "Kiosko Principal", "online": False}]
PRENDIDO = [{"identificador": "kiosko", "nombre": "Kiosko Principal", "online": True}]


class LaReglaTests(unittest.TestCase):
    def _con(self, tipos, tipo, otras) -> bool:
        with patch.object(ruteo, "impresoras_de_esta_pc", lambda: list(tipos)):
            return ruteo.imprimir_aqui_de_respaldo(tipo, otras)

    def test_kiosko_apagado_y_aqui_hay_impresora_sale_aqui(self) -> None:
        self.assertTrue(self._con(["TICKET"], TipoTrabajo.CORTE, APAGADO))

    def test_sin_ninguna_otra_pc_tambien_sale_aqui(self) -> None:
        self.assertTrue(self._con(["TICKET"], TipoTrabajo.CORTE, []))

    def test_con_el_kiosko_prendido_se_manda_alla(self) -> None:
        self.assertFalse(self._con(["TICKET"], TipoTrabajo.CORTE, PRENDIDO))

    def test_una_pc_sin_impresoras_no_puede(self) -> None:
        self.assertFalse(self._con([], TipoTrabajo.CORTE, APAGADO))

    def test_solo_el_corte(self) -> None:
        self.assertFalse(self._con(["CORTE"], TipoTrabajo.TICKET, APAGADO))


class LaVentanaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _abrir_corte(self, otras):
        visto: dict = {}
        with patch("pos_uniformes.services.print_routing_cache_service.load_print_routing", lambda: ("LOCAL", "principal")), \
                patch("pos_uniformes.services.print_routing_cache_service.puede_imprimir", lambda t: False), \
                patch("pos_uniformes.services.print_routing_cache_service.impresoras_de_esta_pc", lambda: ["TICKET"]), \
                patch.object(rt, "otras_impresoras_de_tickets", lambda t=None: otras), \
                patch("pos_uniformes.ui.dialogs.printable_text_dialog.open_tickets_print_dialog",
                      lambda p, title, tickets, **kw: visto.update(kw)), \
                patch.object(rt, "_enviar_al_satelite", lambda *a, **k: self.fail("se fue a la cola")):
            rt.route_tickets(None, "Corte de caja", ["CORTE"], tipo=TipoTrabajo.CORTE)
        return visto

    def test_kiosko_apagado_abre_con_aqui_de_respaldo(self) -> None:
        visto = self._abrir_corte(APAGADO)
        self.assertTrue(visto["aqui_respaldo"])
        self.assertNotIn("aqui_imprime", visto)       # «Aquí» sí aparece
        self.assertEqual(visto["destinos"], APAGADO)  # el kiosko se ve, en gris

    def test_kiosko_prendido_sigue_sin_aqui(self) -> None:
        visto = self._abrir_corte(PRENDIDO)
        self.assertIs(visto["aqui_imprime"], False)
        self.assertNotIn("aqui_respaldo", visto)

    def test_la_ficha_dice_que_es_de_respaldo_y_va_marcada(self) -> None:
        from pos_uniformes.ui.dialogs import printable_text_dialog as ventana

        vistos: dict = {}

        def exec_falso(dlg):
            aqui = dlg.destino_botones[""]
            vistos.update(texto=aqui.text(), marcada=aqui.isChecked(),
                          kiosko=dlg.destino_botones["kiosko"].isEnabled())
            return 0

        with patch.object(QDialog, "exec", exec_falso):
            ventana.open_tickets_print_dialog(
                None, "Corte", ["CORTE"], print_fn=lambda t: True, destinos=APAGADO,
                aqui_respaldo=True, enviar_a=lambda d, t: len(t),
            )
        self.assertIn("de respaldo", vistos["texto"])
        self.assertTrue(vistos["marcada"])
        self.assertFalse(vistos["kiosko"])


if __name__ == "__main__":
    unittest.main()
