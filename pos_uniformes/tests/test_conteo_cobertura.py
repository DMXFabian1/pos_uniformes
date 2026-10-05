"""Contar UNA talla no debe esconder el alcance entero.

Pasó en la tienda el 2026-10-05: una muchacha contó una playera de Chazarilla
—un solo color— y la escuela desapareció del menú de conteo, así que la que
seguía ya no pudo registrar lo demás. La causa: "cuándo se contó esto" salía
del MÁXIMO de las fechas de sus tallas, así que una sola talla ponía el
alcance como contado hoy y el menú lo escondía por recién contado.
"""

from __future__ import annotations

import unittest
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import (
    Categoria,
    Escuela,
    Marca,
    Producto,
    TipoPieza,
    Variante,
)
from pos_uniformes.services import conteo_jornada_service as cj

HOY = date(2026, 10, 5)


class _Base(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.s = Session(engine)
        self.escuela = Escuela(nombre="Chazarilla", activo=True)
        self.tipo = TipoPieza(nombre="Playeras", activo=True)
        self.categoria = Categoria(nombre="Playeras", activo=True)
        self.marca = Marca(nombre="Genérica", activo=True)
        self.s.add_all([self.escuela, self.tipo, self.categoria, self.marca])
        self.s.flush()

    def _producto(self, nombre, *, escuela=True):
        p = Producto(
            nombre=nombre, nombre_base=nombre, tipo_pieza_id=self.tipo.id, activo=True,
            categoria_id=self.categoria.id, marca_id=self.marca.id,
            escuela_id=self.escuela.id if escuela else None,
        )
        self.s.add(p)
        self.s.flush()
        return p

    def _tallas(self, producto, cuantas, *, contadas=0, hace_dias=0):
        cuando = datetime.combine(HOY - timedelta(days=hace_dias), datetime.min.time()).astimezone()
        for i in range(cuantas):
            self.s.add(Variante(
                producto_id=producto.id, sku=f"{producto.nombre[:4]}-{producto.id}-{i}",
                talla=str(4 + i), color="Blanco", precio_venta=Decimal("100.00"),
                stock_actual=0, ultimo_conteo_at=cuando if i < contadas else None,
            ))
        self.s.flush()


class CoberturaDeEscuelaTests(_Base):
    def test_una_talla_contada_no_es_la_escuela_contada(self) -> None:
        p = self._producto("Playera Chazarilla")
        self._tallas(p, 10, contadas=1)
        cob = cj.cobertura_de(cj.coberturas(self.s, hoy=HOY), self.escuela.id)
        self.assertEqual((cob.contadas, cob.total), (1, 10))
        self.assertTrue(cob.a_medias)
        self.assertFalse(cob.completa)

    def test_todas_contadas_si_es_completa(self) -> None:
        p = self._producto("Playera Chazarilla")
        self._tallas(p, 6, contadas=6)
        cob = cj.cobertura_de(cj.coberturas(self.s, hoy=HOY), self.escuela.id)
        self.assertTrue(cob.completa)
        self.assertFalse(cob.a_medias)

    def test_un_color_contado_deja_el_otro_a_medias(self) -> None:
        """El caso exacto de la tienda: dos colores, se contó uno."""
        blanca = self._producto("Playera Chazarilla Blanca")
        roja = self._producto("Playera Chazarilla Roja")
        self._tallas(blanca, 5, contadas=5)
        self._tallas(roja, 5, contadas=0)
        cob = cj.cobertura_de(cj.coberturas(self.s, hoy=HOY), self.escuela.id)
        self.assertEqual((cob.contadas, cob.total, cob.faltan), (5, 10, 5))
        self.assertTrue(cob.a_medias)

    def test_lo_contado_hace_mucho_no_cuenta_para_esta_vuelta(self) -> None:
        p = self._producto("Playera Chazarilla")
        self._tallas(p, 4, contadas=4, hace_dias=cj.DIAS_RECIEN_CONTADA + 5)
        cob = cj.cobertura_de(cj.coberturas(self.s, hoy=HOY), self.escuela.id)
        self.assertEqual(cob.contadas, 0)
        self.assertFalse(cob.a_medias)   # nada empezado: no está "a medias"

    def test_sin_contar_nada_no_esta_a_medias(self) -> None:
        p = self._producto("Playera Chazarilla")
        self._tallas(p, 4)
        cob = cj.cobertura_de(cj.coberturas(self.s, hoy=HOY), self.escuela.id)
        self.assertFalse(cob.a_medias)
        self.assertFalse(cob.completa)

    def test_el_texto_dice_cuanto_lleva(self) -> None:
        p = self._producto("Playera Chazarilla")
        self._tallas(p, 40, contadas=3)
        cob = cj.cobertura_de(cj.coberturas(self.s, hoy=HOY), self.escuela.id)
        self.assertIn("3 de 40", cob.texto())


class CoberturaDeBasicosTests(_Base):
    def test_por_prenda_y_por_tipo(self) -> None:
        una = self._producto("Playera Lisa Blanca", escuela=False)
        otra = self._producto("Playera Lisa Negra", escuela=False)
        self._tallas(una, 5, contadas=5)
        self._tallas(otra, 5, contadas=0)
        cobs = cj.coberturas(self.s, hoy=HOY)
        self.assertTrue(cj.cobertura_de(cobs, None, "Playeras", "Playera Lisa Blanca").completa)
        self.assertFalse(cj.cobertura_de(cobs, None, "Playeras", "Playera Lisa Negra").completa)
        # El tipo entero va a medias: media prenda contada no es el tipo listo.
        del_tipo = cj.cobertura_de(cobs, None, "Playeras")
        self.assertEqual((del_tipo.contadas, del_tipo.total), (5, 10))
        self.assertTrue(del_tipo.a_medias)


class SinDatoTests(_Base):
    def test_un_alcance_que_no_existe_devuelve_vacio(self) -> None:
        cob = cj.cobertura_de({}, 999)
        self.assertEqual((cob.contadas, cob.total), (0, 0))
        self.assertFalse(cob.a_medias)
        self.assertFalse(cob.completa)
        self.assertEqual(cob.texto(), "")


if __name__ == "__main__":
    unittest.main()


class UnaSolaPrendaDeUnaEscuelaTests(_Base):
    """Antes una escuela se contaba entera o nada, así que dos personas no
    podían repartirse los colores de la misma playera: la primera abría la
    jornada de toda la escuela y la segunda chocaba con ella
    (Daniel, 2026-10-05: "hazlo para las escuelas también")."""

    def setUp(self) -> None:
        super().setUp()
        self.blanca = self._producto("Playera Chazarilla Blanca")
        self.roja = self._producto("Playera Chazarilla Roja")
        self._tallas(self.blanca, 5)
        self._tallas(self.roja, 4)

    def test_el_alcance_de_una_prenda_trae_solo_esa(self) -> None:
        grupos = cj.alcance(self.s, self.escuela.id, "", "Playera Chazarilla Roja")
        self.assertEqual([g["producto_nombre"] for g in grupos], ["Playera Chazarilla Roja"])
        self.assertEqual(sum(len(g["variantes"]) for g in grupos), 4)

    def test_sin_prenda_sigue_trayendo_toda_la_escuela(self) -> None:
        grupos = cj.alcance(self.s, self.escuela.id)
        self.assertEqual(sum(len(g["variantes"]) for g in grupos), 9)

    def test_la_llave_distingue_la_prenda(self) -> None:
        self.assertEqual(cj.clave_alcance(7), 7)
        self.assertEqual(cj.clave_alcance(7, "", "Playera Roja"), (7, "Playera Roja"))

    def test_dos_colores_a_la_vez_no_se_pisan(self) -> None:
        cj.abrir_jornada(self.s, escuela_id=self.escuela.id,
                         prenda="Playera Chazarilla Blanca",
                         empleada_code="VEND-5", empleada_nombre="Cristal")
        otra = cj.abrir_jornada(self.s, escuela_id=self.escuela.id,
                                prenda="Playera Chazarilla Roja",
                                empleada_code="VEND-3", empleada_nombre="Evelyn")
        self.assertIsNotNone(otra.id)
        self.assertEqual(otra.prenda, "Playera Chazarilla Roja")

    def test_el_mismo_color_si_choca(self) -> None:
        """Dos contando lo mismo es el error que las jornadas vinieron a evitar."""
        cj.abrir_jornada(self.s, escuela_id=self.escuela.id,
                         prenda="Playera Chazarilla Blanca",
                         empleada_code="VEND-5", empleada_nombre="Cristal")
        with self.assertRaises(cj.JornadaEnProceso):
            cj.abrir_jornada(self.s, escuela_id=self.escuela.id,
                             prenda="Playera Chazarilla Blanca",
                             empleada_code="VEND-3", empleada_nombre="Evelyn")

    def test_toda_la_escuela_choca_con_una_prenda_ya_abierta(self) -> None:
        cj.abrir_jornada(self.s, escuela_id=self.escuela.id,
                         prenda="Playera Chazarilla Blanca",
                         empleada_code="VEND-5", empleada_nombre="Cristal")
        with self.assertRaises(cj.JornadaEnProceso):
            cj.abrir_jornada(self.s, escuela_id=self.escuela.id,
                             empleada_code="VEND-3", empleada_nombre="Evelyn")

    def test_una_prenda_choca_con_la_de_toda_la_escuela(self) -> None:
        cj.abrir_jornada(self.s, escuela_id=self.escuela.id,
                         empleada_code="VEND-5", empleada_nombre="Cristal")
        with self.assertRaises(cj.JornadaEnProceso):
            cj.abrir_jornada(self.s, escuela_id=self.escuela.id,
                             prenda="Playera Chazarilla Roja",
                             empleada_code="VEND-3", empleada_nombre="Evelyn")

    def test_el_titulo_dice_que_prenda_es(self) -> None:
        """Si no, la hoja impresa y el tablero no se distinguen de la de toda
        la escuela."""
        j = cj.abrir_jornada(self.s, escuela_id=self.escuela.id,
                             prenda="Playera Chazarilla Roja",
                             empleada_code="VEND-5", empleada_nombre="Cristal")
        self.assertIn("Chazarilla", j.titulo)
        self.assertIn("Roja", j.titulo)

    def test_cuenta_solo_las_tallas_de_esa_prenda(self) -> None:
        j = cj.abrir_jornada(self.s, escuela_id=self.escuela.id,
                             prenda="Playera Chazarilla Roja",
                             empleada_code="VEND-5", empleada_nombre="Cristal")
        self.assertEqual(j.total_tallas, 4)

    def test_las_prendas_de_la_escuela_se_pueden_listar(self) -> None:
        self.assertEqual(
            sorted(cj.prendas_de_escuela(self.s, self.escuela.id)),
            ["Playera Chazarilla Blanca", "Playera Chazarilla Roja"],
        )

    def test_la_cobertura_se_lleva_por_prenda(self) -> None:
        self._tallas(self._producto("Short Chazarilla"), 3, contadas=3)
        cobs = cj.coberturas(self.s, hoy=HOY)
        self.assertTrue(cj.cobertura_de(cobs, self.escuela.id, "", "Short Chazarilla").completa)
        self.assertFalse(
            cj.cobertura_de(cobs, self.escuela.id, "", "Playera Chazarilla Roja").completa
        )
        # Y la escuela entera va a medias: 3 de 12.
        de_la_escuela = cj.cobertura_de(cobs, self.escuela.id)
        self.assertEqual((de_la_escuela.contadas, de_la_escuela.total), (3, 12))
        self.assertTrue(de_la_escuela.a_medias)
