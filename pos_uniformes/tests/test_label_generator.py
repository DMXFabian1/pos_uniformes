from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
import unittest

from pos_uniformes.utils.label_generator import LabelGenerator


def _build_variant(
    *,
    product_name: str,
    product_base_name: str = "",
    talla: str = "",
    price: str = "249.00",
    category_name: str = "",
    school_name: str = "",
    level_name: str = "",
    garment_type: str = "",
):
    school = SimpleNamespace(nombre=school_name) if school_name else None
    level = SimpleNamespace(nombre=level_name) if level_name else None
    category = SimpleNamespace(nombre=category_name) if category_name else None
    return SimpleNamespace(
        talla=talla,
        precio_venta=Decimal(price),
        producto=SimpleNamespace(
            nombre=product_name,
            nombre_base=product_base_name,
            categoria=category,
            escuela_id=1 if school_name else None,
            escuela=school,
            nivel_educativo_id=1 if level_name else None,
            nivel_educativo=level,
            escudo="",
            tipo_prenda=SimpleNamespace(nombre=garment_type) if garment_type else None,
        ),
    )


class LabelGeneratorTests(unittest.TestCase):
    def test_split_label_for_ropa_normal_shows_only_name_and_price(self) -> None:
        variante = _build_variant(
            product_name="Categoria Sudadera Premium Talla Chica",
            product_base_name="Sudadera Premium",
            talla="CH",
            price="349.00",
            garment_type="Basico",
        )

        lines = LabelGenerator._split_label_lines(variante)

        self.assertGreaterEqual(len(lines), 2)
        self.assertEqual(lines[-1].text, "$349.00")
        self.assertNotIn("Precio:", " ".join(line.text for line in lines))
        self.assertNotIn("T:", " ".join(line.text for line in lines))
        self.assertEqual(lines[0].text, "Sudadera Premium")

    def test_split_label_for_uniform_keeps_name_and_size_without_price(self) -> None:
        variante = _build_variant(
            product_name="Pants Deportivo",
            talla="16",
            school_name="Patria",
            level_name="Primaria",
            garment_type="Deportivo",
        )

        lines = LabelGenerator._split_label_lines(variante)

        rendered = " ".join(line.text for line in lines)
        self.assertIn("T: 16", rendered)
        self.assertNotIn("$", rendered)

    def test_split_label_hides_price_for_uniform_category_without_school_context(self) -> None:
        variante = _build_variant(
            product_name="Playera Basica",
            product_base_name="Playera Basica",
            talla="12",
            category_name="Básico",
            garment_type="Basico",
            price="199.00",
        )

        lines = LabelGenerator._split_label_lines(variante)

        rendered = " ".join(line.text for line in lines)
        self.assertIn("T: 12", rendered)
        self.assertNotIn("$", rendered)


if __name__ == "__main__":
    unittest.main()
