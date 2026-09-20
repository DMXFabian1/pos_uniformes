"""Fundir dos fichas de la misma prenda sin perder SKUs."""

from __future__ import annotations

import unittest

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import Categoria, Marca, Producto, Variante
from pos_uniformes.scripts import fundir_productos as fu


class FundirTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:"); Base.metadata.create_all(engine)
        self.s = Session(engine)
        cat = Categoria(nombre="Básico"); marca = Marca(nombre="Genérica"); self.s.add_all([cat, marca]); self.s.flush()
        self.a = Producto(nombre="Camisa Olan Blanca", nombre_base="Camisa Olan Blanca", categoria_id=cat.id, marca_id=marca.id)
        self.b = Producto(nombre="Camisa Olan Blanca (2)", nombre_base="Camisa Olan Blanca", categoria_id=cat.id, marca_id=marca.id)
        self.s.add_all([self.a, self.b]); self.s.flush()
        for prod, tallas in ((self.a, [("4", 15), ("6", 19)]), (self.b, [("6", 3), ("12", 12), ("CH", 14)])):
            for t, st in tallas:
                self.s.add(Variante(producto_id=prod.id, sku=f"S{prod.id}-{t}", talla=t, color="Blanca", precio_venta=139, stock_actual=st))
        self.s.commit()

    def test_las_tallas_pasan_con_su_sku_y_la_repetida_suma_existencia(self) -> None:
        plan = fu.planear(self.s, de=self.b.id, en=self.a.id)
        self.assertEqual(sorted(v.talla for v, _ in plan["mover"]), ["12", "CH"])
        self.assertEqual([v.talla for v, _ in plan["sumar"]], ["6"])
        fu.aplicar(self.s, plan); self.s.commit()
        vs = {v.sku: v for v in self.s.scalars(select(Variante)).all()}
        self.assertEqual({sku: v.producto_id for sku, v in vs.items() if v.activo}, {f"S{self.a.id}-4": self.a.id, f"S{self.a.id}-6": self.a.id, f"S{self.b.id}-12": self.a.id, f"S{self.b.id}-CH": self.a.id})
        self.assertEqual((vs[f"S{self.a.id}-6"].stock_actual, vs[f"S{self.b.id}-6"].stock_actual), (22, 0))
        self.assertFalse(vs[f"S{self.b.id}-6"].activo); self.assertTrue(vs[f"S{self.b.id}-12"].activo)
        self.s.refresh(self.b); self.assertFalse(self.b.activo); self.assertIn(f"fundido en #{self.a.id}", self.b.descripcion)
        from pos_uniformes.database.models import MovimientoInventario
        self.assertEqual(self.s.query(MovimientoInventario).filter_by(variante_id=vs[f"S{self.a.id}-6"].id).count(), 1)
