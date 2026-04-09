from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from pos_uniformes.services.employee_card_service import EmployeeCardService


class EmployeeCardServiceTests(unittest.TestCase):
    def test_build_render_input_uses_visible_name_and_existing_qr(self) -> None:
        employee = SimpleNamespace(codigo="VEND-1", nombre_completo="Lupita Gomez Ruiz")
        with tempfile.TemporaryDirectory() as temp_dir:
            qr_path = Path(temp_dir) / "vend-1.png"
            Image.new("RGBA", (40, 40), (255, 255, 255, 255)).save(qr_path)
            with patch("pos_uniformes.services.employee_card_service.QrGenerator.path_for_employee", return_value=qr_path):
                payload = EmployeeCardService.build_render_input(employee)

        self.assertEqual(payload.visible_name, "Lupita Ruiz")
        self.assertEqual(payload.employee_code, "VEND-1")
        self.assertEqual(payload.qr_path, str(qr_path))

    def test_render_for_employee_creates_png_card(self) -> None:
        employee = SimpleNamespace(codigo="VEND-1", nombre_completo="Lupita Gomez Ruiz")
        with tempfile.TemporaryDirectory() as temp_dir:
            qr_path = Path(temp_dir) / "vend-1.png"
            output_path = Path(temp_dir) / "vend-1-card.png"
            Image.new("RGBA", (200, 200), (255, 255, 255, 255)).save(qr_path)
            with (
                patch("pos_uniformes.services.employee_card_service.QrGenerator.path_for_employee", return_value=qr_path),
                patch.object(EmployeeCardService, "path_for_employee", return_value=output_path),
            ):
                generated = EmployeeCardService.render_for_employee(employee)

            self.assertEqual(generated, output_path)
            self.assertTrue(output_path.exists())
            with Image.open(output_path) as image:
                self.assertEqual(image.size, (1080, 1350))


if __name__ == "__main__":
    unittest.main()
