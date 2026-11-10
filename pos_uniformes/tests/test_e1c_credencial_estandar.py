"""E1-C2: credencial estándar para todos los clientes.

No escribe en `data/`: el render PIL va a una carpeta temporal y el QR se
simula.
"""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from pos_uniformes.database.models import Cliente, NivelLealtad, TipoCliente
from pos_uniformes.services.customer_card_service import (
    COLOR_ESTANDAR_PRIMARIO,
    COLOR_ESTANDAR_SECUNDARIO,
    TEMPLATE_CSS_PATH,
    TEMPLATE_HTML_PATH,
    CustomerCardService,
)


def _cliente(nivel, descuento="0.00") -> Cliente:
    return Cliente(id=9, codigo_cliente="CLI-000009", nombre="Rosa Pérez", tipo_cliente=TipoCliente.PROFESOR,
                   descuento_preferente=Decimal(descuento), nivel_lealtad=nivel, telefono="6671234567",
                   cliente_desde=datetime(2026, 3, 4), activo=True)


class CredencialEstandarTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="e1c2-")
        self.addCleanup(self.tmp.cleanup)
        self.qr = Path(self.tmp.name) / "qr.png"
        Image.new("RGB", (120, 120), "white").save(self.qr)

    def _entrada(self, cliente):
        with patch("pos_uniformes.services.customer_card_service.QrGenerator.path_for_client", return_value=self.qr), \
                patch.object(CustomerCardService, "_business_name", return_value="Maximoda"):
            return CustomerCardService.build_render_input(cliente)

    def test_misma_credencial_con_o_sin_nivel(self) -> None:
        sin = self._entrada(_cliente(None))
        con = self._entrada(_cliente(NivelLealtad.MAYORISTA, "20.00"))
        self.assertEqual(sin, con)
        self.assertEqual(sin.client_code, "CLI-000009")
        self.assertEqual((sin.primary_color, sin.secondary_color), (COLOR_ESTANDAR_PRIMARIO, COLOR_ESTANDAR_SECUNDARIO))
        self.assertEqual((sin.loyalty_level, sin.level_label), ("", ""))

    def test_html_muestra_codigo_y_no_nivel_ni_beneficios(self) -> None:
        entrada = self._entrada(_cliente(NivelLealtad.LEAL))
        html = CustomerCardService._build_html_document(
            entrada, TEMPLATE_HTML_PATH.read_text(encoding="utf-8"), TEMPLATE_CSS_PATH.read_text(encoding="utf-8")
        )
        self.assertIn("CLI-000009", html)
        self.assertIn("Presenta este codigo al visitarnos", html)
        self.assertNotIn("{{", html)
        for prohibido in ("Nivel", "Leal", "beneficios", "Descuento"):
            with self.subTest(texto=prohibido):
                cuerpo = html.split("<body>", 1)[1]
                self.assertNotIn(prohibido, cuerpo)

    def test_respaldo_pil_genera_png(self) -> None:
        entrada = self._entrada(_cliente(None))
        destino = Path(self.tmp.name) / "card.png"
        CustomerCardService._render_card_with_pil(entrada, destino)
        self.assertTrue(destino.exists())

    def test_render_for_client_no_escribe_en_la_ficha(self) -> None:
        cliente = _cliente(None)
        with patch.object(CustomerCardService, "output_dir", return_value=Path(self.tmp.name)), \
                patch.object(CustomerCardService, "build_render_input", return_value=self._entrada(cliente)), \
                patch.object(CustomerCardService, "render_card", side_effect=lambda payload, out: Path(out)):
            ruta = CustomerCardService.render_for_client(cliente)
        self.assertEqual(ruta, Path(self.tmp.name) / "CLI-000009_card.png")
        self.assertIsNone(cliente.card_image_path)


if __name__ == "__main__":
    unittest.main()
