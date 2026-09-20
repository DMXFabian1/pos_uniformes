"""Cada talla a la jornada de su prenda (limpieza tras el bug del 20/09)."""

from __future__ import annotations

import unittest
from datetime import datetime

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import ConteoInventario, ConteoJornada, Variante
from pos_uniformes.scripts import reubicar_conteos_por_prenda as rc
from pos_uniformes.services import conteo_jornada_service as jn
from pos_uniformes.services.conteo_service import ConteoInput, registrar_conteos_lote
from pos_uniformes.tests.test_conteo_jornada_service import _seed, _seed_basicos


class ReubicarTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:"); Base.metadata.create_all(engine)
        self.s = Session(engine)
        esc = _seed(self.s, "Uno", stock=3)
        self.gris, self.azul = _seed_basicos(self.s, esc, "Pantalón")
        self.s.commit()
        vs = {v.producto.nombre: [] for v in self.s.scalars(select(Variante)).all() if v.producto.escuela_id is None}
        for v in self.s.scalars(select(Variante)).all():
            if v.producto.escuela_id is None: vs[v.producto.nombre].append(v)
        # Nayeli abrió la de la GRIS y, por el bug, capturó gris Y azul dentro; la de la azul quedó a medias con 0.
        self.j_gris = jn.abrir_jornada(self.s, escuela_id=None, tipo_pieza="Pantalón", prenda=self.gris, empleada_code="VEND-9", empleada_nombre="Nayeli")
        self.j_azul = jn.abrir_jornada(self.s, escuela_id=None, tipo_pieza="Pantalón", prenda=self.azul, empleada_code="VEND-9", empleada_nombre="Nayeli")
        registrar_conteos_lote(self.s, [ConteoInput(v.id, 2) for v in vs[self.gris] + vs[self.azul]], "Nayeli (VEND-9)", jornada_id=self.j_gris.id)
        jn.terminar_jornada(self.s, self.j_gris, empleada_code="VEND-9")
        jn.aplicar_jornada(self.s, self.j_gris, revisada_por="VEND-1")
        self.s.commit()

    def test_el_plan_ve_lo_ajeno_y_aplicar_lo_mueve_dejando_la_destino_igual_que_la_origen(self) -> None:
        plan = rc.planear(self.s)
        self.assertEqual(len(plan), 1)
        self.assertEqual((plan[0]["origen"].id, plan[0]["prenda"], len(plan[0]["renglones"]), plan[0]["destino"].id), (self.j_gris.id, self.azul, 2, self.j_azul.id))
        self.assertEqual(rc.aplicar(self.s, plan), 2)
        self.s.commit()
        en_gris = jn.capturado_en_jornada(self.s, self.j_gris.id); en_azul = jn.capturado_en_jornada(self.s, self.j_azul.id)
        self.assertEqual((len(en_gris), len(en_azul)), (2, 2))
        self.s.refresh(self.j_azul)
        self.assertIsNotNone(self.j_azul.terminada_at); self.assertIsNotNone(self.j_azul.revisada_at)
        self.assertEqual(self.j_azul.revisada_por, "VEND-1")
        self.assertEqual(rc.planear(self.s), [])   # ya no hay nada que mover
        # lo aplicado al inventario no se tocó
        self.assertTrue(all(c.ajustado for c in self.s.scalars(select(ConteoInventario)).all()))

    def test_sin_jornada_de_esa_prenda_se_crea_una_a_nombre_de_quien_conto(self) -> None:
        self.s.delete(self.j_azul); self.s.commit()
        plan = rc.planear(self.s)
        self.assertIsNone(plan[0]["destino"])
        rc.aplicar(self.s, plan); self.s.commit()
        nueva = self.s.scalars(select(ConteoJornada).where(ConteoJornada.prenda == self.azul)).one()
        self.assertEqual((nueva.empleada_code, nueva.titulo, nueva.total_tallas), ("VEND-9", "Básicos · Pantalón Azul Escolar", 2))
        self.assertEqual(nueva.iniciada_at, self.j_gris.iniciada_at)
        self.assertEqual(len(jn.capturado_en_jornada(self.s, nueva.id)), 2)
