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


def _con(variante, *, sku="SKU000001", color="", marca=""):
    """Le pone al variante de prueba lo que la etiqueta Label también lee."""
    variante.sku = sku
    variante.color = color
    variante.producto.marca = SimpleNamespace(nombre=marca) if marca else None
    return variante


class EtiquetaLabelTests(unittest.TestCase):
    """La etiqueta Label (29 × 90 mm) rediseñada el 2026-11-05: el nombre en
    grande, y lo que decide la venta —talla en uniformes, precio en ropa
    normal— a la vista. Daniel: «que se vea mejor el nombre del producto y en
    las prendas normales se vea el precio de manera clara»."""

    def test_uniforme_escuela_arriba_nombre_sin_repetirla_y_talla(self) -> None:
        v = _con(_build_variant(
            product_name="Pants 3pz Deportivo Vicente Guerrero", talla="6",
            school_name="Vicente Guerrero", level_name="Primaria", garment_type="Deportivo",
        ), color="Vino")
        c = LabelGenerator.standard_content(v)
        self.assertEqual(c.familia, "uniforme")
        self.assertEqual(c.encabezado, "PRIMARIA · VICENTE GUERRERO")
        self.assertEqual(c.nombre, "Pants 3pz Deportivo")          # la escuela ya va arriba
        self.assertEqual((c.talla, c.color, c.precio), ("6", "Vino", ""))

    def test_uniforme_nunca_ensena_precio_aunque_se_pida(self) -> None:
        v = _con(_build_variant(product_name="Falda Escocesa", talla="10", school_name="Benito Juárez"))
        self.assertEqual(LabelGenerator.standard_content(v, show_price=True).precio, "")

    def test_ropa_normal_precio_claro_y_marca_arriba(self) -> None:
        v = _con(_build_variant(product_name="Conjunto Pijama QS227", talla="Unitalla", price="179.00"),
                 color="Surtido", marca="Yamo")
        c = LabelGenerator.standard_content(v)
        self.assertEqual(c.familia, "ropa_normal")
        self.assertEqual(c.encabezado, "YAMO · SURTIDO · UNITALLA")
        self.assertEqual(c.nombre, "Conjunto Pijama QS227")
        self.assertEqual(c.precio, "$179")                          # sin «Precio:» ni centavos en ceros
        self.assertEqual(c.talla, "")                               # unitalla no ocupa caja

    def test_ropa_normal_con_talla_y_con_centavos(self) -> None:
        v = _con(_build_variant(product_name="Bóxer", talla="Adulto", price="1249.50"), color="Surtido", marca="Sin marca")
        c = LabelGenerator.standard_content(v)
        self.assertEqual(c.talla, "Adulto")
        self.assertEqual(c.precio, "$1,249.50")
        self.assertEqual(c.encabezado, "SURTIDO")                   # «Sin marca» no se imprime

    def test_se_puede_ocultar_el_precio_de_la_ropa(self) -> None:
        v = _con(_build_variant(product_name="Pijama CN", talla="Unitalla", price="99.00"))
        self.assertEqual(LabelGenerator.standard_content(v, show_price=False).precio, "")

    def test_el_color_no_se_repite_si_ya_va_en_el_nombre(self) -> None:
        v = _con(_build_variant(product_name="Playera Tortuga Blanca", talla="8", garment_type="Deportivo"), color="Blanca")
        c = LabelGenerator.standard_content(v)
        self.assertEqual((c.nombre, c.color), ("Playera Tortuga Blanca", ""))

    def test_un_nombre_que_cabe_va_en_un_renglon_y_uno_largo_se_parte(self) -> None:
        from PIL import Image, ImageDraw

        draw = ImageDraw.Draw(Image.new("1", (992, 271), 1))
        _f, corto = LabelGenerator._fit_wrapped(draw, "Conjunto Pijama QS227", 665, 130, base_size=66, min_size=28)
        self.assertEqual(corto, ["Conjunto Pijama QS227"])
        fuente, largo = LabelGenerator._fit_wrapped(draw, "Suéter Claudia Cuello V H Azul Marino", 665, 150, base_size=66, min_size=28)
        self.assertEqual(len(largo), 2)
        self.assertEqual(" ".join(largo), "Suéter Claudia Cuello V H Azul Marino")
        for renglon in largo:
            self.assertLessEqual(LabelGenerator._text_width(draw, renglon, fuente), 665)

    def test_se_pinta_del_tamano_de_siempre_y_con_tinta_donde_va_el_precio(self) -> None:
        import tempfile
        from pathlib import Path

        from PIL import Image

        v = _con(_build_variant(product_name="Conjunto Pijama QS227", talla="Unitalla", price="179.00"), color="Surtido", marca="Yamo")
        with tempfile.TemporaryDirectory() as tmp:
            qr = Path(tmp) / "qr.png"
            Image.new("1", (300, 300), 0).save(qr)
            salida = Path(tmp) / "label.png"
            LabelGenerator._render_standard(v, qr, salida)
            img = Image.open(salida)
            self.assertEqual(img.size, (992, 271))                  # la impresora no cambia
            precio = img.crop((24, 187, 300, 257))                  # abajo a la izquierda
            negros = precio.histogram()[0]
            self.assertGreater(negros, 2500)                        # «$179» en negrita, no un renglón chico
            margen = img.crop((0, 0, 20, 271))
            self.assertEqual(margen.histogram()[0], 0)               # nada pegado a la orilla
