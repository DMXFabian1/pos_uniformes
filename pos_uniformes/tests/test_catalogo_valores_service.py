"""Valores del catálogo: una sola forma y «¿Quisiste decir…?» (tanda 1, 2026-11-13)."""

from __future__ import annotations

import unittest
from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import (
    AtributoProducto,
    Categoria,
    Escuela,
    Marca,
    Producto,
    RolUsuario,
    TipoPieza,
    TipoPrenda,
    Usuario,
    Variante,
)
from pos_uniformes.services import catalogo_valores_service as cv


class NormalizarTests(unittest.TestCase):
    def test_ignora_mayusculas_acentos_espacios_y_signos(self) -> None:
        self.assertEqual(cv.normalizar("  Álvaro  Obregón (El Carretón) "), "alvaro obregon el carreton")
        self.assertEqual(cv.normalizar("Básico"), cv.normalizar("basico"))

    def test_el_guion_de_las_tallas_se_conserva(self) -> None:
        self.assertNotEqual(cv.normalizar("3-5"), cv.normalizar("35"))

    def test_formas_oficiales_de_talla(self) -> None:
        for escrito, oficial in [
            ("Uni", "Unitalla"), ("NT", "Unitalla"), ("Ch", "CH"), ("ch", "CH"),
            ("M", "MD"), ("G", "GD"), ("XL", "EXG"), ("XXL", "EXG"), ("12", "12"), ("3-5", "3-5"),
        ]:
            self.assertEqual(cv.forma_oficial_talla(escrito), oficial, escrito)

    def test_formas_oficiales_de_color(self) -> None:
        self.assertEqual(cv.forma_oficial_color("Blanca"), "Blanco")
        self.assertEqual(cv.forma_oficial_color("Multicolor"), "Surtido")
        self.assertEqual(cv.forma_oficial_color("Gris"), "Gris")

    def test_depurar_opciones_deja_una_sola_forma(self) -> None:
        self.assertEqual(
            cv.depurar_opciones(cv.CAMPO_TALLA, ["CH", "Ch", "Uni", "Unitalla", "MD", "M"]),
            ["CH", "Unitalla", "MD"],
        )
        self.assertEqual(
            cv.depurar_opciones(cv.CAMPO_TIPO_PRENDA, ["Deportivo", "Basico", "Oficial"], ["Básico"]),
            ["Deportivo", "Básico", "Oficial"],
        )
        self.assertNotIn("Blanca", cv.depurar_opciones(cv.CAMPO_COLOR, ["Blanca", "Negro"]))

    def test_las_listas_sugeridas_no_traen_formas_viejas(self) -> None:
        self.assertNotIn("XL", cv.TALLAS_SUGERIDAS)
        self.assertNotIn("Uni", cv.TALLAS_SUGERIDAS)
        self.assertIn("Unitalla", cv.TALLAS_SUGERIDAS)
        self.assertNotIn("Multicolor", cv.COLORES_SUGERIDOS)
        self.assertIn("Surtido", cv.COLORES_SUGERIDOS)


class RevisarValorTests(unittest.TestCase):
    COLORES = {"Blanca": 306, "Blanco": 125, "Gris": 80, "Azul Marino": 40}
    TALLAS = {"Uni": 66, "Unitalla": 23, "CH": 256, "Ch": 1, "8": 100}

    def test_blanca_se_parece_a_blanco_con_sus_tallas(self) -> None:
        r = cv.revisar_valor(cv.CAMPO_COLOR, "Blanca", self.COLORES)
        self.assertEqual(r.estado, cv.ESTADO_PARECIDO)
        self.assertEqual(r.valor, "Blanco")
        self.assertTrue(r.existe)
        self.assertEqual(r.texto_pregunta(), "«Blanca» se parece a «Blanco» (125 tallas).")

    def test_uni_se_parece_a_unitalla(self) -> None:
        r = cv.revisar_valor(cv.CAMPO_TALLA, "Uni", self.TALLAS)
        self.assertEqual((r.estado, r.valor), (cv.ESTADO_PARECIDO, "Unitalla"))

    def test_solo_mayusculas_se_corrige_sin_preguntar(self) -> None:
        r = cv.revisar_valor(cv.CAMPO_TALLA, "Ch", self.TALLAS)
        self.assertEqual((r.estado, r.valor), (cv.ESTADO_OK, "CH"))
        r = cv.revisar_valor(cv.CAMPO_COLOR, "gris", self.COLORES)
        self.assertEqual((r.estado, r.valor), (cv.ESTADO_OK, "Gris"))

    def test_lo_que_existe_y_es_oficial_pasa(self) -> None:
        self.assertFalse(cv.revisar_valor(cv.CAMPO_TALLA, "CH", self.TALLAS).necesita_pregunta)
        self.assertFalse(cv.revisar_valor(cv.CAMPO_COLOR, "Gris", self.COLORES).necesita_pregunta)

    def test_talla_numerica_nueva_es_oficial(self) -> None:
        r = cv.revisar_valor(cv.CAMPO_TALLA, "46", self.TALLAS)
        self.assertEqual((r.estado, r.valor), (cv.ESTADO_OK, "46"))

    def test_basico_sin_acento_propone_basico(self) -> None:
        usos = {"Basico": 0, "Básico": 128, "Deportivo": 235}
        r = cv.revisar_valor(cv.CAMPO_TIPO_PRENDA, "Basico", usos)
        self.assertEqual((r.estado, r.valor), (cv.ESTADO_PARECIDO, "Básico"))

    def test_acentos_sobre_algo_que_no_existe_se_usa_el_existente(self) -> None:
        r = cv.revisar_valor(cv.CAMPO_TIPO_PIEZA, "sueter", {"Suéter": 86})
        self.assertEqual((r.estado, r.valor), (cv.ESTADO_OK, "Suéter"))

    def test_deportiva_propone_deportivo(self) -> None:
        r = cv.revisar_valor(cv.CAMPO_ATRIBUTO, "Deportiva", {"Deportivo": 101, "Deportiva": 75})
        self.assertEqual((r.estado, r.valor), (cv.ESTADO_PARECIDO, "Deportivo"))
        self.assertTrue(r.existe)

    def test_sinonimo_de_taxonomia_sin_la_forma_oficial_no_inventa(self) -> None:
        r = cv.revisar_valor(cv.CAMPO_ATRIBUTO, "Deportiva", {"Deportiva": 75})
        self.assertEqual(r.estado, cv.ESTADO_OK)

    def test_errata_ofrece_el_parecido(self) -> None:
        r = cv.revisar_valor(cv.CAMPO_TIPO_PIEZA, "Chamara", {"Chamarra": 68, "Camisa": 14})
        self.assertEqual(r.estado, cv.ESTADO_PARECIDO)
        self.assertEqual(r.sugerencias[0], cv.Parecido("Chamarra", 68))
        self.assertFalse(r.existe)

    def test_algo_nuevo_de_verdad(self) -> None:
        r = cv.revisar_valor(cv.CAMPO_TIPO_PIEZA, "Overol", {"Chamarra": 68, "Camisa": 14})
        self.assertEqual(r.estado, cv.ESTADO_NUEVO)
        self.assertIn("no existe todavía", r.texto_pregunta())

    def test_escuela_pregunta_si_es_la_misma(self) -> None:
        usos = {"Ignacio Allende": 9, "Ignacio Allende (Jaral)": 7, "Miguel Hidalgo": 12}
        r = cv.revisar_valor(cv.CAMPO_ESCUELA, "Ignacio Allende Jaral de Berrios", usos)
        self.assertEqual(r.estado, cv.ESTADO_PARECIDO)
        self.assertIn("Ignacio Allende (Jaral)", [s.valor for s in r.sugerencias])
        self.assertIn("¿Es la misma que", r.texto_pregunta())

    def test_escuela_sin_acento_usa_la_que_existe(self) -> None:
        r = cv.revisar_valor(cv.CAMPO_ESCUELA, "ignacio ramirez lopez", {"Ignacio Ramírez López": 4})
        self.assertEqual((r.estado, r.valor), (cv.ESTADO_OK, "Ignacio Ramírez López"))

    def test_vacio_no_pregunta(self) -> None:
        self.assertFalse(cv.revisar_valor(cv.CAMPO_ATRIBUTO, "  ", {}).necesita_pregunta)


class _Base(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.s = Session(engine)
        self.admin = Usuario(username="admin", nombre_completo="Admin", rol=RolUsuario.ADMIN, password_hash="x")
        self.cajera = Usuario(username="caja", nombre_completo="Caja", rol=RolUsuario.CAJERO, password_hash="x")
        cat = Categoria(nombre="Uniformes")
        marca = Marca(nombre="Sin marca")
        self.s.add_all([self.admin, self.cajera, cat, marca])
        self.basico_sin = TipoPrenda(nombre="Basico")
        self.basico = TipoPrenda(nombre="Básico")
        self.escuela = Escuela(nombre="Ignacio Ramírez López")
        self.s.add_all([self.basico_sin, self.basico, self.escuela, AtributoProducto(nombre="Deportivo")])
        self.s.flush()
        p = Producto(nombre="Playera X", nombre_base="Playera X", categoria_id=cat.id, marca_id=marca.id,
                     tipo_prenda_id=self.basico.id, escuela_id=self.escuela.id)
        self.s.add(p)
        self.s.flush()
        for i, (talla, color) in enumerate([("CH", "Blanco"), ("MD", "Blanco"), ("Uni", "Blanca")]):
            self.s.add(Variante(producto_id=p.id, sku=f"SKU{i:06d}", talla=talla, color=color,
                                precio_venta=Decimal("100")))
        self.s.commit()


class ContarUsosTests(_Base):
    def test_cuenta_prendas_por_taxonomia(self) -> None:
        usos = cv.contar_usos(self.s, cv.CAMPO_TIPO_PRENDA)
        self.assertEqual(usos, {"Basico": 0, "Básico": 1})

    def test_cuenta_tallas_por_color(self) -> None:
        self.assertEqual(cv.contar_usos(self.s, cv.CAMPO_COLOR), {"Blanco": 2, "Blanca": 1})
        self.assertEqual(cv.contar_usos(self.s, cv.CAMPO_TALLA), {"CH": 1, "MD": 1, "Uni": 1})


class ResolverOCrearTests(_Base):
    def test_igual_letra_por_letra(self) -> None:
        self.assertIs(cv.resolver_o_crear(self.s, TipoPrenda, "Basico"), self.basico_sin)

    def test_sin_acentos_prefiere_la_acentuada(self) -> None:
        self.assertIs(cv.resolver_o_crear(self.s, TipoPrenda, "BASICO "), self.basico)
        self.assertIs(cv.resolver_o_crear(self.s, Escuela, "Ignacio Ramirez Lopez"), self.escuela)

    def test_no_crea_lo_que_no_se_confirmo(self) -> None:
        with self.assertRaises(cv.ValorNoConfirmado):
            cv.resolver_o_crear(self.s, TipoPieza, "Overol")
        self.assertIsNone(self.s.scalar(select(TipoPieza).where(TipoPieza.nombre == "Overol")))

    def test_crea_lo_confirmado(self) -> None:
        nueva = cv.resolver_o_crear(self.s, TipoPieza, "Overol", confirmados=["Overol"])
        self.assertEqual(nueva.nombre, "Overol")
        self.assertIsNotNone(nueva.id)

    def test_escuela_nueva_solo_admin(self) -> None:
        with self.assertRaises(PermissionError):
            cv.resolver_o_crear(self.s, Escuela, "Rancho Nuevo", confirmados=["Rancho Nuevo"], usuario=self.cajera)
        with self.assertRaises(PermissionError):
            cv.resolver_o_crear(self.s, Escuela, "Rancho Nuevo", confirmados=["Rancho Nuevo"])
        nueva = cv.resolver_o_crear(self.s, Escuela, "Rancho Nuevo", confirmados=["Rancho Nuevo"], usuario=self.admin)
        self.assertEqual(nueva.nombre, "Rancho Nuevo")

    def test_vacio_es_none(self) -> None:
        self.assertIsNone(cv.resolver_o_crear(self.s, AtributoProducto, ""))


if __name__ == "__main__":
    unittest.main()
