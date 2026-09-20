"""Mapa de conteos: qué está contado y qué no, por capas."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import Variante
from pos_uniformes.services import conteo_mapa_service as m
from pos_uniformes.tests.test_conteo_jornada_service import _seed, _seed_basicos


class MapaTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:"); Base.metadata.create_all(engine)
        self.s = Session(engine)
        self.uno = _seed(self.s, "Uno", stock=3)     # 2 prendas × tallas 6 y 8
        self.dos = _seed(self.s, "Dos", stock=3)
        _seed_basicos(self.s, self.uno, "Pantalón")   # 2 prendas × 2 tallas
        vs = list(self.s.scalars(select(Variante).order_by(Variante.id)).all())
        uno = [v for v in vs if v.producto.escuela_id == self.uno.id]
        uno[0].ultimo_conteo_at = datetime.now() - timedelta(days=2)     # al día
        uno[1].ultimo_conteo_at = datetime.now() - timedelta(days=400)   # vieja
        # las otras dos de Uno: nunca; Dos: nunca; básicos: una al día
        basicos = [v for v in vs if v.producto.escuela_id is None]
        basicos[0].ultimo_conteo_at = datetime.now() - timedelta(days=1)
        self.s.commit()

    def test_resumen_por_escuela_y_basicos(self) -> None:
        r = m.resumen(self.s)
        uno = next(e for e in r["escuelas"] if e["nombre"] == "Uno")
        self.assertEqual((uno["tallas"], uno["al_dia"], uno["viejas"], uno["nunca"], uno["pct_al_dia"], uno["ultimo_dias"], uno["estado"]), (4, 1, 1, 2, 25, 2, "vieja"))
        dos = next(e for e in r["escuelas"] if e["nombre"] == "Dos")
        self.assertEqual((dos["nunca"], dos["estado"], dos["ultimo_dias"]), (4, "nunca", None))
        pant = next(b for b in r["basicos"] if b["tipo_pieza"] == "Pantalón")
        self.assertEqual((pant["tallas"], pant["al_dia"], pant["nunca"]), (4, 1, 3))
        self.assertEqual(r["total"]["tallas"], 12)

    def test_detalle_de_escuela_trae_prendas_y_tallas_con_semaforo(self) -> None:
        d = m.escuela(self.s, self.uno.id)
        self.assertEqual(d["titulo"], "Uno")
        self.assertEqual(len(d["prendas"]), 2)
        estados = {(p["nombre"], t["talla"]): t["estado"] for p in d["prendas"] for t in p["tallas_detalle"]}
        self.assertEqual(sorted(estados.values()), ["al_dia", "nunca", "nunca", "vieja"])
        self.assertTrue(all(t["dias"] is None for p in d["prendas"] for t in p["tallas_detalle"] if t["estado"] == "nunca"))

    def test_detalle_de_basicos_por_tipo(self) -> None:
        d = m.basicos(self.s, "Pantalón")
        self.assertEqual(d["titulo"], "Básicos · Pantalón")
        self.assertEqual([p["nombre"] for p in d["prendas"]], ["Pantalón Azul Escolar", "Pantalón Gris Escolar"])
        self.assertEqual(d["al_dia"] + d["nunca"], 4)
