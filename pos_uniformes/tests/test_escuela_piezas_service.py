"""Qué prendas tiene cada escuela se contesta en un solo lugar.

Lo importante de estos tests no es la matriz en sí, sino de **dónde** salen las
prendas generales: el POS ya decide por el uniforme armado, y el panel se había
quedado en las ligas. Hoy coinciden; el día que las ligas se retiren, solo pasa
quien pregunte al servicio.
"""

from __future__ import annotations

import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import (
    Categoria,
    CatalogSchoolProductLink,
    Escuela,
    Marca,
    NivelEducativo,
    Producto,
    TipoPieza,
    TipoPrenda,
    Uniforme,
    UniformePieza,
)
from pos_uniformes.services import escuela_piezas_service as eps


class _Base(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.s = Session(engine)
        self.cat = Categoria(nombre="Uniformes")
        self.marca = Marca(nombre="G")
        self.prenda = TipoPrenda(nombre="Deportivo")
        self.primaria = NivelEducativo(nombre="Primaria")
        self.secundaria = NivelEducativo(nombre="Secundaria")
        self.s.add_all([self.cat, self.marca, self.prenda, self.primaria, self.secundaria])
        self.piezas = {n: TipoPieza(nombre=n) for n in ("Playera", "Pants 2pz", "Suéter")}
        self.s.add_all(list(self.piezas.values()))
        self.s.flush()

    def _escuela(self, nombre):
        e = Escuela(nombre=nombre)
        self.s.add(e)
        self.s.flush()
        return e

    def _prod(self, nombre, pieza, *, escuela=None, nivel=None, activo=True):
        p = Producto(
            nombre=nombre,
            nombre_base=nombre,
            categoria_id=self.cat.id,
            marca_id=self.marca.id,
            escuela_id=escuela.id if escuela else None,
            nivel_educativo_id=(nivel or self.primaria).id,
            tipo_prenda_id=self.prenda.id,
            tipo_pieza_id=self.piezas[pieza].id,
            activo=activo,
        )
        self.s.add(p)
        self.s.flush()
        return p

    def celdas(self):
        return {(e, n, p): c for e, n, p, c in eps.matriz_de_piezas(self.s)}


class MatrizDePiezasTest(_Base):
    def test_cuenta_las_prendas_propias_de_la_escuela(self):
        esc = self._escuela("Justo Sierra")
        self._prod("Playera JS", "Playera", escuela=esc)
        self._prod("Playera JS Manga Larga", "Playera", escuela=esc)
        self._prod("Pants JS", "Pants 2pz", escuela=esc)
        celdas = self.celdas()
        self.assertEqual(celdas[(esc.id, "Primaria", "Playera")], 2)
        self.assertEqual(celdas[(esc.id, "Primaria", "Pants 2pz")], 1)

    def test_la_general_ligada_vale_en_todos_los_niveles_de_la_escuela(self):
        esc = self._escuela("Vicente Guerrero")
        self._prod("Playera VG", "Playera", escuela=esc, nivel=self.primaria)
        self._prod("Playera VG Sec", "Playera", escuela=esc, nivel=self.secundaria)
        general = self._prod("Suéter Vino", "Suéter")
        self.s.add(CatalogSchoolProductLink(escuela_id=esc.id, producto_id=general.id))
        self.s.flush()

        celdas = self.celdas()
        self.assertEqual(celdas[(esc.id, "Primaria", "Suéter")], 1)
        self.assertEqual(celdas[(esc.id, "Secundaria", "Suéter")], 1, "un suéter liso sirve en los dos")

    def test_la_general_dada_de_baja_no_cuenta(self):
        esc = self._escuela("Justo Sierra")
        self._prod("Playera JS", "Playera", escuela=esc)
        muerta = self._prod("Suéter Fundido", "Suéter", activo=False)
        self.s.add(CatalogSchoolProductLink(escuela_id=esc.id, producto_id=muerta.id))
        self.s.flush()
        self.assertNotIn((esc.id, "Primaria", "Suéter"), self.celdas())

    def test_el_uniforme_armado_manda_sobre_las_ligas(self):
        """El caso que hoy no se ve y por el que existe este servicio."""
        esc = self._escuela("Justo Sierra")
        self._prod("Playera JS", "Playera", escuela=esc)
        vieja = self._prod("Suéter Rojo", "Suéter")
        nueva = self._prod("Pants Liso", "Pants 2pz")
        self.s.add(CatalogSchoolProductLink(escuela_id=esc.id, producto_id=vieja.id))
        self.s.flush()
        self.assertIn((esc.id, "Primaria", "Suéter"), self.celdas())

        # La escuela arma su uniforme y ahí su general es otro.
        uni = Uniforme(escuela_id=esc.id, nombre="Uniforme")
        self.s.add(uni)
        self.s.flush()
        self.s.add(UniformePieza(uniforme_id=uni.id, producto_id=nueva.id, orden=1))
        self.s.flush()

        celdas = self.celdas()
        self.assertIn((esc.id, "Primaria", "Pants 2pz"), celdas, "manda el uniforme")
        self.assertNotIn((esc.id, "Primaria", "Suéter"), celdas, "la liga vieja ya no manda")


class EscuelasConNivelesTest(_Base):
    def test_multinivel_lleva_el_nivel_en_el_nombre(self):
        una = self._escuela("Frida Kahlo")
        dos = self._escuela("Álvaro Obregón")
        self._prod("Playera FK", "Playera", escuela=una)
        self._prod("Playera AO", "Playera", escuela=dos, nivel=self.primaria)
        self._prod("Playera AO Sec", "Playera", escuela=dos, nivel=self.secundaria)

        self.assertEqual(eps.escuelas_multinivel(self.s), {dos.id})
        nombres = {e["display_name"] for e in eps.escuelas_con_niveles(self.s)}
        self.assertIn("Frida Kahlo", nombres)
        self.assertIn("Álvaro Obregón Primaria", nombres)
        self.assertIn("Álvaro Obregón Secundaria", nombres)

    def test_los_acentos_no_mandan_la_escuela_al_final(self):
        for nombre in ("Zaragoza", "Álvaro Obregón", "Benito Juárez"):
            self._prod(f"Playera {nombre}", "Playera", escuela=self._escuela(nombre))
        orden = [e["escuela_nombre"] for e in eps.escuelas_con_niveles(self.s)]
        self.assertEqual(orden, ["Álvaro Obregón", "Benito Juárez", "Zaragoza"])


class CatalogoPorEscuelaTest(_Base):
    def _variante(self, producto, talla, *, color="Rojo", stock=0, precio=100, activo=True):
        from pos_uniformes.database.models import Variante

        v = Variante(
            producto_id=producto.id,
            sku=f"{producto.id}-{talla}-{color}",
            talla=talla,
            color=color,
            precio_venta=precio,
            stock_actual=stock,
            activo=activo,
        )
        self.s.add(v)
        self.s.flush()
        return v

    def _fila(self, filas, sku):
        i = eps.CATALOGO_COLUMNAS.index("sku")
        return next(f for f in filas if f[i] == sku)

    def _campo(self, fila, nombre):
        return fila[eps.CATALOGO_COLUMNAS.index(nombre)]

    def test_una_fila_por_talla_con_su_escuela(self):
        esc = self._escuela("Justo Sierra")
        p = self._prod("Playera JS", "Playera", escuela=esc)
        self._variante(p, "10")
        self._variante(p, "12")
        filas = eps.catalogo_por_escuela(self.s)
        self.assertEqual(len(filas), 2)
        self.assertEqual(self._campo(filas[0], "escuela"), "Justo Sierra")
        self.assertEqual(self._campo(filas[0], "tipo_pieza"), "Playera")

    def test_la_prenda_sin_tallas_igual_aparece(self):
        esc = self._escuela("Justo Sierra")
        self._prod("Playera JS", "Playera", escuela=esc)
        fila = eps.catalogo_por_escuela(self.s)[0]
        self.assertIsNone(self._campo(fila, "variante_id"))
        self.assertIsNone(self._campo(fila, "talla"))
        self.assertEqual(self._campo(fila, "stock_bodega"), 0)

    def test_la_general_sale_bajo_cada_escuela_que_la_lleva(self):
        una = self._escuela("Justo Sierra")
        otra = self._escuela("Frida Kahlo")
        self._prod("Playera JS", "Playera", escuela=una)
        self._prod("Playera FK", "Playera", escuela=otra)
        general = self._prod("Suéter Vino", "Suéter")
        self._variante(general, "10")
        for e in (una, otra):
            self.s.add(CatalogSchoolProductLink(escuela_id=e.id, producto_id=general.id))
        self.s.flush()

        filas = eps.catalogo_por_escuela(self.s)
        suyas = [f for f in filas if self._campo(f, "producto_id") == general.id]
        self.assertEqual({self._campo(f, "escuela") for f in suyas}, {"Justo Sierra", "Frida Kahlo"})
        for f in suyas:
            self.assertIsNone(self._campo(f, "producto_escuela_id"), "sigue siendo general")

    def test_lo_guardado_viene_partido_en_piso_y_bodega(self):
        from pos_uniformes.database.models import BodegaCaja, BodegaContenido, BodegaUbicacion

        esc = self._escuela("Justo Sierra")
        p = self._prod("Playera JS", "Playera", escuela=esc)
        v = self._variante(p, "10", stock=10)
        for rack, cantidad in (("A", 3), ("PISO", 2)):
            ubi = BodegaUbicacion(codigo=f"{rack}-1", rack=rack, nivel=1)
            self.s.add(ubi)
            self.s.flush()
            caja = BodegaCaja(codigo=f"C-{rack}", ubicacion_id=ubi.id)
            self.s.add(caja)
            self.s.flush()
            self.s.add(BodegaContenido(caja_id=caja.id, variante_id=v.id, cantidad=cantidad))
        self.s.flush()

        fila = self._fila(eps.catalogo_por_escuela(self.s), v.sku)
        self.assertEqual(self._campo(fila, "stock_actual"), 10)
        self.assertEqual(self._campo(fila, "stock_bodega"), 3)
        self.assertEqual(self._campo(fila, "stock_piso"), 2)

    def test_el_orden_es_el_de_la_base(self):
        z = self._escuela("Zaragoza")
        a = self._escuela("Álvaro Obregón")
        for esc in (z, a):
            p = self._prod(f"Playera {esc.nombre}", "Playera", escuela=esc)
            self._variante(p, "10")
        orden = [self._campo(f, "escuela") for f in eps.catalogo_por_escuela(self.s)]
        self.assertEqual(orden, ["Álvaro Obregón", "Zaragoza"])


class ConteosTest(_Base):
    def test_escuelas_por_nivel_cuenta_escuelas_no_prendas(self):
        una = self._escuela("Justo Sierra")
        otra = self._escuela("Frida Kahlo")
        self._prod("Playera JS", "Playera", escuela=una)
        self._prod("Pants JS", "Pants 2pz", escuela=una)
        self._prod("Playera FK", "Playera", escuela=otra, nivel=self.secundaria)
        self.assertEqual(eps.escuelas_por_nivel(self.s), {"Primaria": 1, "Secundaria": 1})


class GeneradorNoEscribeSQLDePiezasTest(unittest.TestCase):
    def setUp(self) -> None:
        from pathlib import Path

        ruta = Path(__file__).resolve().parent.parent / "scripts" / "generar_panel_uniformes.py"
        self.fuente = ruta.read_text(encoding="utf-8")

    def test_el_generador_ya_no_escribe_SQL(self):
        """Fase 2 cerrada para el panel: pregunta, no calcula."""
        for rastro in ("cur.execute", "SELECT ", "catalog_school_product_link",
                       "bodega_contenido", "conjunto_componente"):
            self.assertNotIn(
                rastro,
                self.fuente,
                f"'{rastro}' volvió al generador: la regla tiene que vivir en un servicio",
            )

    def test_pide_el_catalogo_al_servicio(self):
        self.assertIn("escuela_piezas_service.catalogo_por_escuela", self.fuente)

    def test_pide_la_matriz_al_servicio(self):
        self.assertIn("escuela_piezas_service.matriz_de_piezas", self.fuente)
        self.assertIn("escuela_piezas_service.escuelas_con_niveles", self.fuente)
        self.assertIn("escuela_piezas_service.escuelas_multinivel", self.fuente)


if __name__ == "__main__":
    unittest.main()
