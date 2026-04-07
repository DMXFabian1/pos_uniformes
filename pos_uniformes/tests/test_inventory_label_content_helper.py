from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
import unittest

from pos_uniformes.utils.inventory_label_content_helper import (
    build_inventory_label_price_line,
    resolve_inventory_label_profile,
)


def _build_variant(*, garment_type: str = "", school_name: str = "", level_name: str = "", shield: str = ""):
    school = SimpleNamespace(nombre=school_name) if school_name else None
    level = SimpleNamespace(nombre=level_name) if level_name else None
    return SimpleNamespace(
        precio_venta=Decimal("249.00"),
        producto=SimpleNamespace(
            escuela_id=1 if school_name else None,
            escuela=school,
            nivel_educativo_id=1 if level_name else None,
            nivel_educativo=level,
            escudo=shield,
            tipo_prenda=SimpleNamespace(nombre=garment_type) if garment_type else None,
        ),
    )


class InventoryLabelContentHelperTests(unittest.TestCase):
    def test_resolve_inventory_label_profile_marks_uniform_context(self) -> None:
        profile = resolve_inventory_label_profile(
            _build_variant(garment_type="Oficial", school_name="Patria", level_name="Primaria")
        )

        self.assertEqual(profile.family, "uniforme")
        self.assertFalse(profile.show_price)

    def test_resolve_inventory_label_profile_marks_ropa_normal_without_school_context(self) -> None:
        profile = resolve_inventory_label_profile(_build_variant(garment_type="Basico"))

        self.assertEqual(profile.family, "ropa_normal")
        self.assertTrue(profile.show_price)

    def test_build_inventory_label_price_line_formats_price(self) -> None:
        price_line = build_inventory_label_price_line(_build_variant())

        self.assertEqual(price_line, "Precio: $249.00")


if __name__ == "__main__":
    unittest.main()
