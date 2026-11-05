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
    """Las etiquetas chicas (tira de 4, rollo continuo, cuadrada)."""

    def test_ropa_normal_nombre_y_precio(self) -> None:
        variante = _con(_build_variant(
            product_name="Categoria Sudadera Premium Talla Chica",
            product_base_name="Sudadera Premium",
            talla="CH",
            price="349.00",
            garment_type="Basico",
        ))
        c = LabelGenerator.small_content(variante)
        self.assertEqual(c.nombre, "Sudadera Premium")
        self.assertEqual(c.precio, "$349")                 # sin «Precio:» ni centavos en ceros
        self.assertEqual(c.talla, "CH")                    # la talla va en su caja, no pegada al nombre
        self.assertEqual(c.encabezado, "")

    def test_uniforme_escuela_nombre_y_talla_sin_precio(self) -> None:
        variante = _con(_build_variant(
            product_name="Pants Deportivo Patria",
            talla="16",
            school_name="Patria",
            level_name="Primaria",
            garment_type="Deportivo",
        ), color="Vino")
        c = LabelGenerator.small_content(variante)
        self.assertEqual((c.encabezado, c.nombre, c.talla, c.precio), ("PATRIA · VINO", "Pants Deportivo", "16", ""))

    def test_un_basico_sin_escuela_tampoco_ensena_precio(self) -> None:
        variante = _con(_build_variant(
            product_name="Playera Basica",
            product_base_name="Playera Basica",
            talla="12",
            category_name="Básico",
            garment_type="Basico",
            price="199.00",
        ))
        c = LabelGenerator.small_content(variante)
        self.assertEqual((c.talla, c.precio), ("12", ""))

    def test_el_bloque_cabe_en_la_tira_aun_con_todo(self) -> None:
        from PIL import Image, ImageDraw

        from pos_uniformes.utils.label_generator import QR_SIZE_SPLIT, SPLIT_SECTION_WIDTH, SPLIT_SIZE, SmallLabelContent

        draw = ImageDraw.Draw(Image.new("1", SPLIT_SIZE, 1))
        libre = SPLIT_SIZE[1] - 6 - (6 + QR_SIZE_SPLIT + 4)
        for c in (
            SmallLabelContent("", "Conjunto Pijama de Niño", "Infantil", "$1,249.50"),
            SmallLabelContent("BLANCA VERÓNICA SOTO MARTÍNEZ PRÍNCIPES · VINO", "Pants 3pz Deportivo", "16", ""),
            SmallLabelContent("", "Suéter Claudia Cuello V H Azul Marino", "36", ""),
        ):
            piezas = LabelGenerator._piezas_chicas(draw, c, SPLIT_SECTION_WIDTH - 16, libre)
            self.assertLessEqual(sum(alto for *_r, alto in piezas), libre, c.nombre)
            for tipo, texto, fuente, _alto in piezas:
                if tipo == "texto":
                    self.assertLessEqual(LabelGenerator._text_width(draw, texto, fuente), SPLIT_SECTION_WIDTH - 16, texto)

    def test_la_cuadrada_de_23mm_qr_limpio_y_lo_que_decide_al_lado(self) -> None:
        """La de todos los días (2026-11-05): QR en la esquina, sin marco ni
        ícono; talla o precio grande a su lado y el nombre en negrita abajo."""
        import tempfile
        from pathlib import Path

        import qrcode
        from PIL import Image
        from qrcode.constants import ERROR_CORRECT_H

        from pos_uniformes.utils.label_generator import QR_MODULO_DK1221, QR_SIZE_DK1221

        self.assertEqual(QR_MODULO_DK1221, 5)                # el tamaño de módulo que se probó escaneando
        self.assertEqual(QR_SIZE_DK1221, 105)
        esperado = qrcode.QRCode(error_correction=ERROR_CORRECT_H, box_size=5, border=0)
        esperado.add_data("SKU000001")
        esperado.make(fit=True)
        limpio = esperado.make_image(fill_color="black", back_color="white").convert("1")
        self.assertEqual(limpio.size, (105, 105))            # 21 módulos: el SKU cabe en el QR más chico

        uniforme = _con(_build_variant(product_name="Pants 3pz Deportivo Patria", talla="6", school_name="Patria", garment_type="Deportivo"))
        ropa = _con(_build_variant(product_name="Conjunto Pijama de Niño", talla="Infantil", price="159.00"))
        with tempfile.TemporaryDirectory() as tmp:
            qr = Path(tmp) / "qr.png"
            Image.new("1", (324, 324), 0).save(qr)            # el de archivo (todo negro) NO debe usarse aquí
            for nombre, v in (("u", uniforme), ("r", ropa)):
                salida = Path(tmp) / f"{nombre}.png"
                LabelGenerator._render_dk1221(v, qr, salida)
                img = Image.open(salida)
                self.assertEqual(img.size, (202, 202))
                # El QR, intacto en la esquina, y dos módulos de aire a su derecha y abajo.
                self.assertEqual(img.crop((0, 0, 105, 105)).tobytes(), limpio.tobytes(), nombre)
                self.assertEqual(img.crop((105, 0, 115, 105)).histogram()[0], 0, nombre)
                self.assertEqual(img.crop((0, 105, 105, 113)).histogram()[0], 0, nombre)
                columna = img.crop((115, 0, 202, 105))
                pie = img.crop((0, 113, 202, 202))
                self.assertGreater(columna.histogram()[0], 400, nombre)     # talla / precio, grande
                self.assertGreater(pie.histogram()[0], 900, nombre)         # el nombre en negrita

    def test_la_cuadrada_del_uniforme_dice_de_que_escuela_es(self) -> None:
        """Sin la escuela, dos pants iguales de escuelas distintas solo se
        distinguían escaneándolos (Daniel, 2026-11-05)."""
        import tempfile
        from pathlib import Path

        from PIL import Image, ImageDraw

        def pie(variante) -> Image.Image:
            with tempfile.TemporaryDirectory() as tmp:
                salida = Path(tmp) / "e.png"
                LabelGenerator._render_dk1221(variante, Path(tmp) / "no_existe.png", salida)
                return Image.open(salida).crop((0, 113, 202, 202)).copy()

        con = pie(_con(_build_variant(product_name="Pants 3pz Deportivo", talla="4", school_name="Blanca Verónica Soto Martínez Príncipes")))
        sin = pie(_con(_build_variant(product_name="Pants 3pz Deportivo", talla="4", garment_type="Deportivo")))
        self.assertNotEqual(con.tobytes(), sin.tobytes())
        self.assertGreater(con.crop((0, 0, 202, 36)).histogram()[0], 300)        # la escuela, arriba del nombre
        self.assertGreater(con.crop((0, 44, 202, 89)).histogram()[0], 500)       # y el nombre sigue ahí, en negrita
        # La escuela más larga del catálogo cabe en dos renglones sin salirse.
        draw = ImageDraw.Draw(Image.new("1", (202, 202), 1))
        fuente, renglones = LabelGenerator._fit_lines(
            draw, "Blanca Verónica Soto Martínez Príncipes", 198, 40, base_size=21, min_size=13, max_renglones=2, bold=False)
        self.assertEqual(len(renglones), 2)
        self.assertFalse(any("…" in r for r in renglones))
        for r in renglones:
            self.assertLessEqual(LabelGenerator._text_width(draw, r, fuente), 198)

    def test_el_nombre_usa_hasta_tres_renglones_para_crecer(self) -> None:
        from PIL import Image, ImageDraw

        draw = ImageDraw.Draw(Image.new("1", (202, 202), 1))
        fuente, renglones = LabelGenerator._fit_lines(draw, "Suéter Navideño YMS226T", 198, 88, base_size=40, min_size=14, max_renglones=3)
        self.assertEqual(" ".join(renglones), "Suéter Navideño YMS226T")
        self.assertLessEqual(len(renglones), 3)
        self.assertGreaterEqual(fuente.size, 24)                              # antes salía a ~17
        for r in renglones:
            self.assertLessEqual(LabelGenerator._text_width(draw, r, fuente), 198)
        # Una palabra imposible no se sale: se recorta.
        _f, uno = LabelGenerator._fit_lines(draw, "Supercalifragilisticoespialidoso", 198, 88, base_size=40, min_size=14, max_renglones=3)
        self.assertEqual(len(uno), 1)

    def test_se_pintan_del_tamano_de_siempre(self) -> None:
        import tempfile
        from pathlib import Path

        from PIL import Image

        v = _con(_build_variant(product_name="Conjunto Pijama QS227", talla="Unitalla", price="179.00"), marca="Yamo")
        with tempfile.TemporaryDirectory() as tmp:
            qr = Path(tmp) / "qr.png"
            Image.new("1", (300, 300), 0).save(qr)
            LabelGenerator._render_split(v, qr, Path(tmp) / "s.png")
            LabelGenerator._render_dk1221(v, qr, Path(tmp) / "d.png")
            LabelGenerator._render_continuous(v, qr, Path(tmp) / "c.png")
            self.assertEqual(Image.open(Path(tmp) / "s.png").size, (976, 342))
            self.assertEqual(Image.open(Path(tmp) / "d.png").size, (202, 202))
            self.assertEqual(Image.open(Path(tmp) / "c.png").size[0], 244)
            # las cuatro secciones de la tira son idénticas
            tira = Image.open(Path(tmp) / "s.png")
            self.assertEqual(tira.crop((0, 0, 244, 342)).tobytes(), tira.crop((732, 0, 976, 342)).tobytes())


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

    def test_la_escuela_se_quita_del_nombre_aunque_venga_con_parentesis_o_acentos(self) -> None:
        """«Álvaro Obregón (El Carretón)» está en sus prendas sin paréntesis: la
        primera etiqueta de prueba salió con la escuela repetida (2026-11-05)."""
        v = _con(_build_variant(
            product_name="Suéter Cuello V H Azul Marino Álvaro Obregón El Carretón", talla="4",
            school_name="Álvaro Obregón (El Carretón)", level_name="Primaria",
        ), color="Azul Marino")
        c = LabelGenerator.standard_content(v)
        self.assertEqual(c.encabezado, "PRIMARIA · ÁLVARO OBREGÓN (EL CARRETÓN)")
        self.assertEqual(c.nombre, "Suéter Cuello V H Azul Marino")
        self.assertEqual(LabelGenerator._sin_escuela("Falda BENITO JUAREZ Escocesa", "Benito Juárez"), "Falda Escocesa")
        self.assertEqual(LabelGenerator._sin_escuela("Benito Juárez", "Benito Juárez"), "Benito Juárez")   # nunca queda vacío
        self.assertEqual(LabelGenerator._sin_escuela("Playera Polo", "Patria"), "Playera Polo")
        # La talla no se confunde con el final del número de la escuela.
        self.assertEqual(LabelGenerator._clean_name("Pants 2pz Deportivo Telesecundaria 512", "12"), "Pants 2pz Deportivo Telesecundaria 512")
        self.assertEqual(LabelGenerator._clean_name("Playera Polo 12", "12"), "Playera Polo")
        # Hay prendas con la escuela escrita dos veces.
        self.assertEqual(LabelGenerator._sin_escuela("Pants 2pz Deportivo Estv 154 ESTV 154", "ESTV 154"), "Pants 2pz Deportivo")

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
