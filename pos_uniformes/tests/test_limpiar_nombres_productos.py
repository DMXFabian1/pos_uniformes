"""Fase 1 del rediseño del catálogo: el nombre va limpio."""

from __future__ import annotations

import unittest

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import Categoria, Escuela, Marca, Producto, TipoPieza, TipoPrenda
from pos_uniformes.scripts import limpiar_nombres_productos as lim
from pos_uniformes.services.catalog_service import CatalogService


class NombresLimpiosTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:"); Base.metadata.create_all(engine)
        self.s = Session(engine)
        self.cat = Categoria(nombre="Básico"); self.marca = Marca(nombre="Genérica")
        self.oficial = TipoPrenda(nombre="Oficial"); self.deportivo = TipoPrenda(nombre="Deportivo")
        self.camisa = TipoPieza(nombre="Camisa"); self.pants = TipoPieza(nombre="Pants 2pz")
        self.s.add_all([self.cat, self.marca, self.oficial, self.deportivo, self.camisa, self.pants]); self.s.flush()

    def _p(self, nombre, base=None, tp=None, tz=None, activo=True):
        p = Producto(nombre=nombre, nombre_base=base or nombre.split("|")[0].strip(), categoria_id=self.cat.id, marca_id=self.marca.id,
                     tipo_prenda_id=tp.id if tp else None, tipo_pieza_id=tz.id if tz else None, activo=activo)
        self.s.add(p); self.s.flush(); return p

    def test_crear_producto_ya_no_pega_el_sufijo(self) -> None:
        nombre = CatalogService._build_product_display_name(base_name="camisa cuello olan blanca", school=None, garment_type=self.oficial, piece_type=self.camisa)
        self.assertEqual(nombre, "Camisa Cuello Olan Blanca")

    def test_nombre_completo_lo_arma_desde_los_campos(self) -> None:
        p = self._p("Camisa Cuello olan Blanca | Oficial | Camisa", tp=self.oficial, tz=self.camisa)
        self.assertEqual(p.nombre_completo, "Camisa Cuello olan Blanca · Oficial · Camisa")
        p2 = self._p("Pants 2pz Liso Rojo", tz=self.pants)
        self.assertEqual(p2.nombre_completo, "Pants 2pz Liso Rojo · Pants 2pz")

    def test_mayusculas_en_cada_palabra_menos_conectores_y_siglas(self) -> None:
        # Daniel (2026-09-20): "¿puedes poner mayúscula en Olan?"
        self.assertEqual(lim.con_mayusculas("Camisa Cuello olan Blanca"), "Camisa Cuello Olan Blanca")
        self.assertEqual(lim.con_mayusculas("Boina Escolta Azul cielo"), "Boina Escolta Azul Cielo")
        self.assertEqual(lim.con_mayusculas("Pantalón Vestir Pata de gallo"), "Pantalón Vestir Pata de Gallo")
        self.assertEqual(lim.con_mayusculas("Playera Deportiva SABES"), "Playera Deportiva SABES")
        self.assertEqual(lim.con_mayusculas("Pants 2pz Liso Rojo CBTIS 148"), "Pants 2pz Liso Rojo CBTIS 148")
        self.assertEqual(lim.con_mayusculas("Suéter Cuello V H Verde"), "Suéter Cuello V H Verde")

    def test_la_prenda_dice_el_nombre_de_su_plantel_ya_separado(self) -> None:
        vg = Escuela(nombre="Vicente Guerrero"); vgp = Escuela(nombre="Vicente Guerrero Preescolar"); self.s.add_all([vg, vgp]); self.s.flush()
        pri = self._p("Pants 2pz Deportivo Vicente Guerrero | Deportivo | Pants 2pz", tz=self.pants); pri.escuela_id = vg.id
        pre = self._p("Pants 2pz Deportivo Vicente Guerrero | Deportivo | Pants 2pz #2", base="Pants 2pz Deportivo Vicente Guerrero", tz=self.pants); pre.escuela_id = vgp.id
        self.s.commit()
        plan = {x["producto"].id: x for x in lim.planear(self.s)}
        self.assertEqual(plan[pri.id]["nuevo"], "Pants 2pz Deportivo Vicente Guerrero")
        self.assertEqual(plan[pre.id]["nuevo"], "Pants 2pz Deportivo Vicente Guerrero Preescolar")   # ya no chocan
        self.assertIsNone(plan[pre.id]["choque"])
        lim.aplicar(self.s, list(plan.values())); self.s.commit(); self.s.refresh(pre)
        self.assertEqual(pre.nombre_base, "Pants 2pz Deportivo Vicente Guerrero Preescolar")

    def test_el_plan_limpia_recupera_campos_y_avisa_choques(self) -> None:
        a = self._p("Camisa Cuello olan Blanca | Oficial | Camisa", tp=self.oficial, tz=self.camisa)
        b = self._p("Camisa Cuello olan Blanca", tp=self.oficial, tz=self.camisa)                 # ya limpio: choca con a
        c = self._p("Pants 2pz Vicente Guerrero | Deportivo | Pants 2pz", tz=self.pants)          # sin tipo_prenda: se recupera
        d = self._p("Playera Deportiva Ad Hoc Zapata | Deportivo | Playera", base="Playera Deportiva Zapata", tp=self.deportivo)
        e = self._p("Pants 2pz Liso Rojo", tz=self.pants)                                          # nada que hacer
        viejo = self._p("Falda Vieja | Oficial | Falda", activo=False)
        self.s.commit()
        plan = {x["producto"].id: x for x in lim.planear(self.s)}
        self.assertNotIn(e.id, plan)
        self.assertEqual(plan[a.id]["nuevo"], "Camisa Cuello Olan Blanca"); self.assertIsNone(plan[a.id]["choque"])
        self.assertEqual(plan[b.id]["nuevo"], "Camisa Cuello Olan Blanca (2)"); self.assertEqual(plan[b.id]["choque"], a.id)
        self.assertEqual((plan[c.id]["nuevo"], plan[c.id]["tipo_prenda"].nombre), ("Pants 2pz Vicente Guerrero", "Deportivo"))
        self.assertEqual(plan[d.id]["nuevo"], "Playera Deportiva Zapata")      # manda nombre_base, el curado
        self.assertEqual(plan[viejo.id]["nuevo"], "Falda Vieja")               # los inactivos también se limpian, sin contar para choques
        lim.aplicar(self.s, list(plan.values())); self.s.commit()
        self.assertEqual({p.nombre for p in self.s.scalars(select(Producto)).all()},
                         {"Camisa Cuello Olan Blanca", "Camisa Cuello Olan Blanca (2)", "Pants 2pz Vicente Guerrero", "Playera Deportiva Zapata", "Pants 2pz Liso Rojo", "Falda Vieja"})
        self.s.refresh(c); self.assertEqual(c.tipo_prenda_id, self.deportivo.id)
        self.assertEqual(lim.planear(self.s), [])
