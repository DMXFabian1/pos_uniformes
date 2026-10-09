"""La dirección de la tienda cabe en el papel.

Al llenarla por primera vez (2026-10-07) resultó medir 54 caracteres y el
ticket tiene 38 columnas: `center` no recorta ni parte, así que la línea salía
del papel. Pasa en los tres documentos que llevan encabezado de tienda.
"""

from __future__ import annotations

import unittest

from pos_uniformes.ui.helpers.ticket_print_layout_helper import TICKET_CHAR_WIDTH

DIRECCION = "Belisario Domínguez 117, Col. Centro, San Felipe, Gto."


def _lineas_largas(texto: str) -> list[str]:
    return [l for l in texto.split("\n") if len(l) > TICKET_CHAR_WIDTH]


class DireccionLargaTests(unittest.TestCase):
    def test_la_direccion_de_verdad_no_cabe_en_una_linea(self) -> None:
        """Si esto deja de ser cierto, el resto de la prueba no prueba nada."""
        self.assertGreater(len(DIRECCION), TICKET_CHAR_WIDTH)

    def test_el_ticket_de_venta_no_se_sale_del_papel(self) -> None:
        from types import SimpleNamespace

        from pos_uniformes.services.sale_ticket_text_service import build_sale_ticket_text

        venta = SimpleNamespace(
            folio="V-1042", created_at=None, observacion="", detalles=[],
            cliente=None, total="635.00", subtotal="635.00",
        )
        texto = build_sale_ticket_text(
            sale=venta, business_name="MAXIMODA", business_phone="4731518099",
            business_address=DIRECCION,
        )
        self.assertIn("Belisario", texto)
        self.assertEqual(_lineas_largas(texto), [])

    def test_ningun_encabezado_se_sale_del_papel(self) -> None:
        """Antes esto miraba el `textwrap` dentro de cada archivo.

        Dejó de servir cuando el encabezado se juntó en uno solo (09/10): la
        línea ya no está en esos archivos y los tests fallaban aunque el
        ticket saliera bien. Ahora se mira lo que de verdad se imprime.
        """
        from pos_uniformes.services.sale_ticket_text_service import (
            encabezado_de_ticket,
        )

        lineas = encabezado_de_ticket("MAXIMODA", DIRECCION, "4731518099")
        self.assertEqual([l for l in lineas if len(l) > TICKET_CHAR_WIDTH], [])
        self.assertIn("Belisario", "\n".join(lineas))

    def test_el_presupuesto_usa_ese_encabezado(self) -> None:
        import inspect

        from pos_uniformes.services import quote_text_service

        self.assertIn("encabezado_de_ticket", inspect.getsource(quote_text_service))

    def test_el_recibo_de_apartado_tambien(self) -> None:
        import inspect

        from pos_uniformes.services import layaway_receipt_text_service

        self.assertIn("encabezado_de_ticket",
                      inspect.getsource(layaway_receipt_text_service))

    def test_una_direccion_corta_se_queda_en_un_renglon(self) -> None:
        from types import SimpleNamespace

        from pos_uniformes.services.sale_ticket_text_service import build_sale_ticket_text

        venta = SimpleNamespace(
            folio="V-1", created_at=None, observacion="", detalles=[],
            cliente=None, total="10.00", subtotal="10.00",
        )
        texto = build_sale_ticket_text(
            sale=venta, business_name="MAXIMODA", business_address="Centro 5",
        )
        self.assertEqual(sum(1 for l in texto.split("\n") if "Centro 5" in l), 1)


if __name__ == "__main__":
    unittest.main()
