from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from pos_uniformes.utils.qr_generator import QrGenerator


class QrGeneratorTests(unittest.TestCase):
    def test_normalize_icon_key_removes_accents_and_symbols(self) -> None:
        self.assertEqual(QrGenerator._normalize_icon_key("Moño Azul"), "mono_azul")
        self.assertEqual(QrGenerator._normalize_icon_key("Pants 2 pz"), "pants_2_pz")

    def test_icon_path_for_variant_prefers_tipo_prenda(self) -> None:
        variant = SimpleNamespace(
            sku="SKU-001",
            producto=SimpleNamespace(
                tipo_prenda=SimpleNamespace(nombre="Camisa"),
                categoria=SimpleNamespace(nombre="Uniforme"),
                tipo_pieza=None,
                atributo=None,
                nombre_base="Camisa Escolar",
                nombre="Camisa Escolar Azul",
            ),
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            icon_dir = Path(temp_dir)
            (icon_dir / "camisa.png").write_bytes(b"icon")
            (icon_dir / "default.png").write_bytes(b"default")
            with patch("pos_uniformes.utils.qr_generator.QR_ICON_DIR", icon_dir):
                icon_path = QrGenerator.icon_path_for_variant(variant)

        self.assertEqual(icon_path, icon_dir / "camisa.png")

    def test_icon_path_for_variant_falls_back_to_default(self) -> None:
        variant = SimpleNamespace(
            sku="SKU-009",
            producto=SimpleNamespace(
                tipo_prenda=None,
                categoria=None,
                tipo_pieza=None,
                atributo=None,
                nombre_base="Prenda Rara",
                nombre="Prenda Rara Deluxe",
            ),
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            icon_dir = Path(temp_dir)
            (icon_dir / "default.png").write_bytes(b"default")
            with patch("pos_uniformes.utils.qr_generator.QR_ICON_DIR", icon_dir):
                icon_path = QrGenerator.icon_path_for_variant(variant)

        self.assertEqual(icon_path, icon_dir / "default.png")

    def test_generate_for_variant_embeds_center_icon(self) -> None:
        variant = SimpleNamespace(
            sku="SKU-555",
            producto=SimpleNamespace(
                tipo_prenda=SimpleNamespace(nombre="Camisa"),
                categoria=None,
                tipo_pieza=None,
                atributo=None,
                nombre_base="Camisa Escolar",
                nombre="Camisa Escolar Blanca",
            ),
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            output_path = temp_path / "SKU-555.png"
            icon_dir = temp_path / "icons"
            icon_dir.mkdir()
            Image.new("RGBA", (120, 120), (210, 40, 40, 255)).save(icon_dir / "camisa.png")
            Image.new("RGBA", (120, 120), (120, 120, 120, 255)).save(icon_dir / "default.png")

            with (
                patch("pos_uniformes.utils.qr_generator.QR_ICON_DIR", icon_dir),
                patch.object(QrGenerator, "path_for_variant", return_value=output_path),
            ):
                generated = QrGenerator.generate_for_variant(variant)

            self.assertEqual(generated, output_path)
            self.assertTrue(output_path.exists())
            image = Image.open(output_path).convert("RGBA")
            center_pixel = image.getpixel((image.width // 2, image.height // 2))
            self.assertNotEqual(center_pixel[:3], (255, 255, 255))
            self.assertNotEqual(center_pixel[:3], (0, 0, 0))


if __name__ == "__main__":
    unittest.main()
