"""Subir a cero lo que está en rojo, sin romper lo que se calcula solo.

Una talla en negativo es la tienda diciendo que se vendió más de lo que el
sistema creía. Subirla a cero deja de mentir hacia abajo; contarla es lo que la
arregla. Estos tests cuidan que la reconciliación no invente existencia ni
pise la de los conjuntos.
"""

from __future__ import annotations

import unittest

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import (
    Categoria,
    ConjuntoComponente,
    Escuela,
    Marca,
    MovimientoInventario,
    Producto,
    TipoMovimientoInventario,
    TipoPieza,
    TipoPrenda,
    Variante,
)
from pos_uniformes.scripts import revisar_stock_negativo as rsn


class _Base(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.s = Session(engine)
        self.cat = Categoria(nombre="Uniformes")
        self.marca = Marca(nombre="G")
        self.prenda = TipoPrenda(nombre="Deportivo")
        self.esc = Escuela(nombre="Justo Sierra")
        self.s.add_all([self.cat, self.marca, self.prenda, self.esc])
        self.piezas = {n: TipoPieza(nombre=n) for n in ("Calceta", "Pants 2pz", "Playera", "Chamarra")}
        self.s.add_all(list(self.piezas.values()))
        self.s.flush()

    def _prod(self, nombre, pieza="Calceta"):
        p = Producto(
            nombre=nombre, nombre_base=nombre,
            categoria_id=self.cat.id, marca_id=self.marca.id,
            escuela_id=self.esc.id, tipo_prenda_id=self.prenda.id,
            tipo_pieza_id=self.piezas[pieza].id,
        )
        self.s.add(p)
        self.s.flush()
        return p

    def _var(self, producto, talla, stock):
        v = Variante(
            producto_id=producto.id, sku=f"{producto.id}-{talla}", talla=talla,
            color="Blanco", precio_venta=50, stock_actual=stock,
        )
        self.s.add(v)
        self.s.flush()
        return v


class ListarNegativasTest(_Base):
    def test_solo_las_que_estan_en_rojo_y_la_peor_primero(self):
        p = self._prod("Calceta Escolar Blanca")
        self._var(p, "6-8", 5)
        self._var(p, "9-12", 0)
        floja = self._var(p, "13-18", -1)
        peor = self._var(p, "20-24", -4)
        self.assertEqual([v.id for v in rsn.listar_negativas(self.s)], [peor.id, floja.id])

    def test_la_prenda_dada_de_baja_no_estorba(self):
        p = self._prod("Calceta Vieja")
        self._var(p, "6-8", -3)
        p.activo = False
        self.s.flush()
        self.assertEqual(rsn.listar_negativas(self.s), [])


class ReconciliarTest(_Base):
    def test_sube_a_cero_y_deja_el_ajuste_firmado(self):
        p = self._prod("Calceta Escolar Blanca")
        v = self._var(p, "13-18", -4)

        ajustadas, recalculadas = rsn.reconciliar(self.s)
        self.assertEqual((ajustadas, recalculadas), (1, 0))
        self.assertEqual(v.stock_actual, 0, "deja de mentir hacia abajo")

        mov = self.s.scalars(
            select(MovimientoInventario).where(MovimientoInventario.variante_id == v.id)
        ).one()
        self.assertEqual(mov.tipo_movimiento, TipoMovimientoInventario.AJUSTE_ENTRADA)
        self.assertEqual(mov.cantidad, 4)
        self.assertEqual(mov.stock_anterior, -4)
        self.assertEqual(mov.stock_posterior, 0)
        self.assertEqual(mov.creado_por, rsn.FIRMA, "se puede auditar quién lo movió")

    def test_no_inventa_existencia_donde_ya_habia(self):
        p = self._prod("Calceta Escolar Blanca")
        sana = self._var(p, "6-8", 7)
        rsn.reconciliar(self.s)
        self.assertEqual(sana.stock_actual, 7)
        self.assertEqual(
            self.s.scalars(
                select(MovimientoInventario).where(MovimientoInventario.variante_id == sana.id)
            ).all(),
            [],
            "a la que está bien no se le toca nada",
        )

    def test_al_conjunto_no_se_le_ajusta_a_mano(self):
        """Su existencia es la de sus piezas: se recalcula, no se inventa."""
        pants = self._prod("Pants 2pz Liso", "Pants 2pz")
        playera = self._prod("Playera Lisa", "Playera")
        tres = self._prod("Pants 3pz Liso", "Chamarra")
        self._var(pants, "10", 4)
        self._var(playera, "10", 6)
        conjunto = self._var(tres, "10", -2)
        self.s.add_all([
            ConjuntoComponente(conjunto_id=tres.id, componente_id=pants.id, cantidad=1, grupo=0),
            ConjuntoComponente(conjunto_id=tres.id, componente_id=playera.id, cantidad=1, grupo=1),
        ])
        self.s.flush()

        ajustadas, _ = rsn.reconciliar(self.s)
        self.assertEqual(ajustadas, 0, "el conjunto no cuenta como talla ajustada")
        self.assertEqual(conjunto.stock_actual, 4, "lo que alcanzan sus piezas")

    def test_el_conjunto_se_recalcula_despues_de_sus_piezas(self):
        """En la tienda (22/09) un Pants 3pz quedó en -1 después de
        reconciliar: estaba menos en rojo que sus piezas, así que se recalculó
        antes de que ellas subieran a cero y se quedó con el número viejo."""
        pants = self._prod("Pants 2pz Liso", "Pants 2pz")
        playera = self._prod("Playera Lisa", "Playera")
        tres = self._prod("Pants 3pz Liso", "Chamarra")
        # Las piezas están MÁS en rojo que el conjunto: se atienden primero.
        self._var(pants, "10", -3)
        self._var(playera, "10", -2)
        conjunto = self._var(tres, "10", -1)
        self.s.add_all([
            ConjuntoComponente(conjunto_id=tres.id, componente_id=pants.id, cantidad=1, grupo=0),
            ConjuntoComponente(conjunto_id=tres.id, componente_id=playera.id, cantidad=1, grupo=1),
        ])
        self.s.flush()

        ajustadas, _ = rsn.reconciliar(self.s)
        self.assertEqual(ajustadas, 2, "las dos piezas")
        self.assertEqual(conjunto.stock_actual, 0, "una sola pasada tiene que bastar")
        self.assertEqual(rsn.listar_negativas(self.s), [], "no queda nada en rojo")

    def test_correrlo_dos_veces_no_hace_dano(self):
        p = self._prod("Calceta Escolar Blanca")
        v = self._var(p, "13-18", -2)
        rsn.reconciliar(self.s)
        ajustadas, _ = rsn.reconciliar(self.s)
        self.assertEqual(ajustadas, 0)
        self.assertEqual(v.stock_actual, 0)


if __name__ == "__main__":
    unittest.main()
