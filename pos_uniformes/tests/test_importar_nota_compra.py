from __future__ import annotations

import unittest
from decimal import Decimal
from pathlib import Path

from pos_uniformes.scripts.importar_nota_compra import parsear_nota

CABECERA = "# proveedor: Mios\n# documento: MIOS-1\n"


class ParsearNotaTests(unittest.TestCase):
    def test_lee_metadatos_y_aplica_defaults(self) -> None:
        nota = parsear_nota(CABECERA + "nombre,marca,cantidad,costo,precio\nLeggings S01,Showey,288,$34,89\n")
        self.assertEqual(nota.proveedor, "Mios")
        self.assertEqual(nota.documento, "MIOS-1")
        linea = nota.lineas[0]
        self.assertEqual((linea.nombre, linea.marca, linea.cantidad), ("Leggings S01", "Showey", 288))
        self.assertEqual((linea.costo, linea.precio), (Decimal("34"), Decimal("89")))
        self.assertEqual((linea.categoria, linea.talla, linea.color), ("Ropa casual", "Unitalla", "Surtido"))

    def test_respeta_columnas_opcionales(self) -> None:
        nota = parsear_nota(
            CABECERA + "nombre,marca,cantidad,costo,precio,talla,color\nPants J969R,ABC,8.00,109,199,GD,Negro\n"
        )
        self.assertEqual((nota.lineas[0].cantidad, nota.lineas[0].talla, nota.lineas[0].color), (8, "GD", "Negro"))

    def test_requiere_proveedor_y_documento(self) -> None:
        with self.assertRaisesRegex(ValueError, "proveedor"):
            parsear_nota("nombre,marca,cantidad,costo,precio\nA,B,1,1,1\n")

    def test_rechaza_columnas_faltantes(self) -> None:
        with self.assertRaisesRegex(ValueError, "precio"):
            parsear_nota(CABECERA + "nombre,marca,cantidad,costo\nA,B,1,1\n")

    def test_rechaza_numeros_invalidos(self) -> None:
        with self.assertRaisesRegex(ValueError, "Fila 2: 'costo'"):
            parsear_nota(CABECERA + "nombre,marca,cantidad,costo,precio\nA,B,1,abc,1\n")
        with self.assertRaisesRegex(ValueError, "mayor a cero"):
            parsear_nota(CABECERA + "nombre,marca,cantidad,costo,precio\nA,B,0,1,1\n")

    def test_rechaza_lineas_repetidas(self) -> None:
        with self.assertRaisesRegex(ValueError, "repetido"):
            parsear_nota(CABECERA + "nombre,marca,cantidad,costo,precio\nA,B,1,1,1\na,b,2,1,1\n")

    def test_nota_mios_0008952_cuadra_con_el_ticket(self) -> None:
        ruta = Path(__file__).resolve().parents[1] / "data" / "notas_compra" / "mios_0008952.csv"
        nota = parsear_nota(ruta.read_text(encoding="utf-8-sig"))
        self.assertEqual(len(nota.lineas), 10)
        self.assertEqual(sum(l.cantidad for l in nota.lineas), 570)
        self.assertEqual(sum(l.cantidad * l.costo for l in nota.lineas), Decimal("25124"))

    def test_lee_la_ficha_de_ropa_normal(self) -> None:
        nota = parsear_nota(
            CABECERA + "nombre,marca,cantidad,costo,precio,linea,pieza,detalle,genero\n"
            "Leggings S01,Showey,288,34,89,Casual,Leggings,,Mujer\n"
        )
        linea = nota.lineas[0]
        self.assertEqual((linea.linea, linea.pieza, linea.detalle, linea.genero), ("Casual", "Leggings", "", "Mujer"))


class PiezaSinDuplicarTests(unittest.TestCase):
    def setUp(self) -> None:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session

        from pos_uniformes.database.connection import Base

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.s = Session(engine)

    def test_reusa_la_que_existe_sin_importar_acentos_y_prefiere_la_acentuada(self) -> None:
        from pos_uniformes.database.models import TipoPrenda
        from pos_uniformes.scripts.importar_nota_compra import _get_or_create_por_nombre

        self.s.add_all([TipoPrenda(nombre="Basico"), TipoPrenda(nombre="Básico")])
        self.s.flush()
        self.assertEqual(_get_or_create_por_nombre(self.s, TipoPrenda, "basico").nombre, "Básico")
        self.assertEqual(self.s.query(TipoPrenda).count(), 2)

    def test_crea_la_que_falta_una_sola_vez(self) -> None:
        from pos_uniformes.database.models import TipoPieza
        from pos_uniformes.scripts.importar_nota_compra import _get_or_create_por_nombre

        a = _get_or_create_por_nombre(self.s, TipoPieza, "Sudadera")
        b = _get_or_create_por_nombre(self.s, TipoPieza, "  sudadera ")
        self.assertIs(a, b)
        self.assertIsNone(_get_or_create_por_nombre(self.s, TipoPieza, ""))


if __name__ == "__main__":
    unittest.main()
