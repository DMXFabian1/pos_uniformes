"""Todo lo que se imprime tiene que sobrevivir a CP850.

La térmica no recibe Unicode: `escpos_ticket_print_helper` codifica el ticket en
**cp850** con `errors="replace"`, así que cualquier carácter que no esté en esa
tabla sale como `?` en el papel — y en pantalla se sigue viendo perfecto. Por eso
no se notaba.

Así se descubrió (02/10) que el separador doble venía imprimiendo `?═══════?`
desde antes: `╞` y `╡` **no están en CP850**. La tabla tiene el juego doble
completo (╔╗╚╝║═) pero no las uniones simple↔doble.
"""

from __future__ import annotations

import os
import unittest
from decimal import Decimal
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from pos_uniformes.services.escpos_settings_cache_service import EscPosSettings
from pos_uniformes.ui.views.quick_sale_view import QuickSaleWidget

CODIFICACION = EscPosSettings().encoding   # la de verdad, no una inventada


def sobrevive(texto: str) -> list[str]:
    """Los caracteres que se perderían al imprimir."""
    return sorted(
        {c for c in texto if c.encode(CODIFICACION, errors="replace").decode(CODIFICACION) != c}
    )


class LoQueSeImprimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _widget(self) -> QuickSaleWidget:
        w = QuickSaleWidget(
            SimpleNamespace(offline_mode=True, _kiosk_lookup_from_cache=None)
        )
        w._employee_code, w._employee_name = "VEND-3", "Evelyn Ortiz"
        w._biz_info = ("MAXIMODA Uniformes", "656 123 4567", "Av. Juárez 123")
        w._items = [
            {"sku": "A", "nombre": "Pants 3pz Deportivo", "talla": "28", "color": "",
             "precio": Decimal("750.00"), "cantidad": 1},
            {"sku": "B", "nombre": "Playera Blanca", "talla": "12", "color": "",
             "precio": Decimal("185.00"), "cantidad": 3},
        ]
        return w

    def test_el_ticket_de_venta_entero(self) -> None:
        texto = self._widget()._build_venta_text(fecha_str="31/10/2026 13:40")
        self.assertEqual(sobrevive(texto), [], "saldrían como «?» en el papel")

    def test_la_copia_de_la_tienda(self) -> None:
        texto = self._widget()._build_venta_text(
            store_copy=True, fecha_str="31/10/2026 13:40"
        )
        self.assertEqual(sobrevive(texto), [])

    def test_los_dibujos_de_todas_las_temporadas(self) -> None:
        from datetime import date

        from pos_uniformes.services import temporada_service as temp

        for t in temp.TEMPORADAS:
            mes, dia = t.desde
            anio = 2026 if mes >= 2 else 2027
            renglones = temp.renglones_de_ticket(date(anio, mes, dia))
            self.assertEqual(sobrevive("\n".join(renglones)), [], t.nombre)

    def test_las_piezas_de_la_caja(self) -> None:
        from pos_uniformes.ui.helpers import ticket_print_layout_helper as h

        piezas = "".join(
            (
                h.tk_top(), h.tk_mid(), h.tk_bot(), h.tk_dbl(),
                h.tk_dbl_top(), h.tk_dbl_bot(), h.tk_dbl_row("TOTAL:", "$1.00"),
            )
        )
        self.assertEqual(sobrevive(piezas), [])

    def test_el_guard_de_verdad_atrapa_lo_que_no_cabe(self) -> None:
        # Que el test sirva: con los caracteres viejos tiene que quejarse.
        self.assertEqual(set(sobrevive("╞═══╡")), {"╞", "╡"})
        self.assertEqual(set(sobrevive("╘═══╛")), {"╘", "╛"})


if __name__ == "__main__":
    unittest.main()
