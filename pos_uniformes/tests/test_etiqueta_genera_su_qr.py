"""La etiqueta genera su QR sola (tanda 2 de Inventario, 2026-11-13).

El QR salió de la pestaña Inventario (columna, filtro, chip, vista previa y
la pregunta tras cada alta) porque la impresión no depende de que alguien lo
haya generado antes: `LabelGenerator.ensure_qr` lo crea si falta.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from pos_uniformes.utils.label_generator import LabelGenerator


class EtiquetaGeneraSuQrTests(unittest.TestCase):
    def test_si_falta_el_qr_la_etiqueta_lo_genera(self) -> None:
        variante = SimpleNamespace(sku="SKU-QR-1")
        with tempfile.TemporaryDirectory() as carpeta:
            faltante = Path(carpeta) / "SKU-QR-1.png"
            generado = Path(carpeta) / "nuevo.png"
            with patch(
                "pos_uniformes.utils.label_generator.QrGenerator.path_for_variant", return_value=faltante
            ), patch(
                "pos_uniformes.utils.label_generator.QrGenerator.generate_for_variant", return_value=generado
            ) as generar:
                ruta = LabelGenerator.ensure_qr(variante)
        generar.assert_called_once_with(variante)
        self.assertEqual(ruta, generado)

    def test_si_ya_existe_no_lo_vuelve_a_generar(self) -> None:
        variante = SimpleNamespace(sku="SKU-QR-2")
        with tempfile.TemporaryDirectory() as carpeta:
            existente = Path(carpeta) / "SKU-QR-2.png"
            existente.write_bytes(b"png")
            with patch(
                "pos_uniformes.utils.label_generator.QrGenerator.path_for_variant", return_value=existente
            ), patch("pos_uniformes.utils.label_generator.QrGenerator.generate_for_variant") as generar:
                ruta = LabelGenerator.ensure_qr(variante)
        generar.assert_not_called()
        self.assertEqual(ruta, existente)


if __name__ == "__main__":
    unittest.main()
