"""El encabezado es el MISMO en todos los tickets al cliente.

Daniel, 2026-10-09: «el logo sigue sin aparecer en la parte superior del
ticket». Y era cierto — pero no en el ticket que yo había tocado. El POS
principal tenía logo y dirección partida; Venta Rápida del kiosko, que arma
el suyo aparte, seguía escribiendo el nombre a secas con la dirección
saliéndose del papel. Se vio en el trabajo #1505: 54 caracteres en 38
columnas.
"""

from __future__ import annotations

import unittest

from pos_uniformes.services.sale_ticket_text_service import encabezado_de_ticket
from pos_uniformes.services.temporada_service import marcador_de
from pos_uniformes.ui.helpers.ticket_print_layout_helper import TICKET_CHAR_WIDTH

DIRECCION = "Belisario Dominguez 117, Colonia Centro, San Felipe Guanajuato"


class ElEncabezadoTests(unittest.TestCase):
    def test_pide_el_logo(self) -> None:
        self.assertIn(marcador_de("logo", "MAXIMODA"),
                      encabezado_de_ticket("MAXIMODA"))

    def test_el_nombre_no_se_dice_dos_veces(self) -> None:
        lineas = encabezado_de_ticket("MAXIMODA")
        self.assertEqual("\n".join(lineas).count("MAXIMODA"), 1)

    def test_la_direccion_se_parte(self) -> None:
        """54 caracteres en 38 columnas: `center` no recorta, se sale."""
        lineas = encabezado_de_ticket("MAXIMODA", DIRECCION)
        self.assertGreater(len(lineas), 2)
        for l in lineas:
            with self.subTest(linea=l):
                self.assertLessEqual(len(l), TICKET_CHAR_WIDTH)

    def test_sin_direccion_ni_telefono_no_deja_huecos(self) -> None:
        self.assertEqual(len(encabezado_de_ticket("MAXIMODA")), 1)

    def test_el_telefono_va_al_final(self) -> None:
        lineas = encabezado_de_ticket("MAXIMODA", DIRECCION, "4731518099")
        self.assertIn("4731518099", lineas[-1])


class TodoSLosTicketsUsanElMismoTests(unittest.TestCase):
    """Lo que vuelve a separarlos es escribir `biz_name.center(...)` a mano."""

    def _codigo(self, ruta):
        from pathlib import Path

        return Path(__file__).resolve().parents[1].joinpath(ruta).read_text(
            encoding="utf-8"
        )

    def test_el_kiosko_no_arma_su_propio_encabezado(self) -> None:
        codigo = self._codigo("ui/views/quick_sale_view.py")
        self.assertNotIn("biz_name.center(", codigo)
        self.assertEqual(codigo.count("encabezado_de_ticket"), 4)   # 2 import + 2 uso

    def test_el_pos_tampoco(self) -> None:
        codigo = self._codigo("services/sale_ticket_text_service.py")
        self.assertNotIn("business_name.center(", codigo)

    def test_no_queda_ninguna_direccion_sin_partir(self) -> None:
        """Lo que salió mal: 54 caracteres en 38 columnas.

        Se mira el código y no el ticket armado: levantar la Venta Rápida
        entera pide media aplicación y tumba Qt —lo intenté—. Lo que de
        verdad importa es que nadie vuelva a centrar la dirección a mano, y
        eso sí se puede ver aquí.
        """
        for ruta in ("ui/views/quick_sale_view.py",
                     "services/sale_ticket_text_service.py"):
            with self.subTest(archivo=ruta):
                codigo = self._codigo(ruta)
                self.assertNotIn("biz_addr.center(", codigo)
                self.assertNotIn("business_address.center(", codigo)

    def test_la_copia_de_la_tienda_no_lleva_logo(self) -> None:
        """Se archiva; el encabezado del negocio es para el cliente."""
        from pathlib import Path

        codigo = Path(__file__).resolve().parents[1].joinpath(
            "ui/views/quick_sale_view.py"
        ).read_text(encoding="utf-8")
        self.assertIn('"COPIA TIENDA".center(_TW)', codigo)


if __name__ == "__main__":
    unittest.main()
