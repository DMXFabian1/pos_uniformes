"""Dos planteles con el mismo nombre: se separan por nivel sin tocar SKUs."""

from __future__ import annotations

import unittest

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import CatalogSchoolProductLink, ConteoInventario, ConteoJornada, Escuela, NivelEducativo, Producto, Variante
from pos_uniformes.scripts import separar_escuela_por_nivel as sep
from pos_uniformes.services import conteo_jornada_service as jn
from pos_uniformes.services.conteo_service import ConteoInput, registrar_conteos_lote
from pos_uniformes.tests.test_conteo_jornada_service import _seed, _seed_basicos


class SepararTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:"); Base.metadata.create_all(engine)
        self.s = Session(engine)
        self.esc = _seed(self.s, "Vicente Guerrero", stock=3)   # 2 prendas × 2 tallas
        pre, pri = NivelEducativo(nombre="Preescolar"), NivelEducativo(nombre="Primaria")
        self.s.add_all([pre, pri]); self.s.flush()
        prods = list(self.s.scalars(select(Producto).where(Producto.escuela_id == self.esc.id).order_by(Producto.id)).all())
        prods[0].nivel_educativo_id, prods[1].nivel_educativo_id = pre.id, pri.id
        _seed_basicos(self.s, self.esc, "Pantalón")               # liga de catálogo que debe copiarse
        # una jornada con tallas de los dos niveles, ya aplicada
        j = jn.abrir_jornada(self.s, escuela_id=self.esc.id, empleada_code="VEND-9", empleada_nombre="Nayeli")
        vs = [v for p in prods for v in p.variantes]
        registrar_conteos_lote(self.s, [ConteoInput(v.id, 1) for v in vs], "Nayeli (VEND-9)", jornada_id=j.id)
        jn.terminar_jornada(self.s, j, empleada_code="VEND-9"); jn.aplicar_jornada(self.s, j, revisada_por="VEND-1")
        self.s.commit()
        self.j, self.prods = j, prods

    def test_se_lleva_el_nivel_con_sus_skus_ligas_y_parte_la_jornada(self) -> None:
        plan = sep.planear(self.s, escuela_id=self.esc.id, nivel="Preescolar", nombre_nueva="Vicente Guerrero Preescolar")
        self.assertEqual([p.id for p in plan["productos"]], [self.prods[0].id])
        self.assertEqual(len(plan["jornadas"][0]["mueven"]), 2)
        skus_antes = sorted(v.sku for v in self.prods[0].variantes)
        nueva = sep.aplicar(self.s, plan, nombre_nueva="Vicente Guerrero Preescolar", renombrar_vieja="Vicente Guerrero Primaria")
        self.s.commit()
        self.assertEqual(self.s.get(Producto, self.prods[0].id).escuela_id, nueva.id)
        self.assertEqual(self.s.get(Producto, self.prods[1].id).escuela_id, self.esc.id)
        self.assertEqual(sorted(v.sku for v in self.s.get(Producto, self.prods[0].id).variantes), skus_antes)
        self.assertEqual(self.s.get(Escuela, self.esc.id).nombre, "Vicente Guerrero Primaria")
        self.assertEqual(self.s.scalar(select(CatalogSchoolProductLink).where(CatalogSchoolProductLink.escuela_id == nueva.id)).activo, True)
        js = {x.escuela_id: x for x in self.s.scalars(select(ConteoJornada)).all()}
        self.assertEqual((js[nueva.id].total_tallas, js[self.esc.id].total_tallas), (2, 2))
        self.assertIsNotNone(js[nueva.id].revisada_at)                          # partida con los mismos datos
        self.assertEqual(len(jn.capturado_en_jornada(self.s, js[nueva.id].id)), 2)
        self.assertTrue(all(c.escuela_id == nueva.id for c in self.s.scalars(select(ConteoInventario).where(ConteoInventario.jornada_id == js[nueva.id].id))))
        self.assertEqual(sep.planear(self.s, escuela_id=self.esc.id, nivel="Preescolar", nombre_nueva="Otra")["productos"], [])
