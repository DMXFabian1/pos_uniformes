"""Tarifarios por escuela: la lista de escuelas sale en UNA consulta."""

from __future__ import annotations

import unittest

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import Categoria, Escuela, Marca, NivelEducativo, Producto
from pos_uniformes.services.school_tariff_service import list_schools_for_tariff


class ListSchoolsForTariffTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.s = Session(engine)
        self.consultas = 0
        event.listen(engine, "before_cursor_execute", lambda *a, **k: setattr(self, "consultas", self.consultas + 1))
        cat = Categoria(nombre="Uniformes"); marca = Marca(nombre="Genérica")
        self.prim = NivelEducativo(nombre="Primaria"); self.sec = NivelEducativo(nombre="Secundaria")
        self.s.add_all([cat, marca, self.prim, self.sec]); self.s.flush()
        self.cat, self.marca = cat, marca

    def _escuela(self, nombre: str, niveles: list, *, activa: bool = True, productos: bool = True) -> Escuela:
        e = Escuela(nombre=nombre, activo=activa); self.s.add(e); self.s.flush()
        if productos:
            for n in niveles or [None]:
                self.s.add(Producto(nombre=f"Playera {nombre} {n.nombre if n else ''}", nombre_base="Playera",
                                    categoria_id=self.cat.id, marca_id=self.marca.id, escuela_id=e.id,
                                    nivel_educativo_id=n.id if n else None))
        self.s.flush()
        return e

    def test_una_entrada_por_nivel_y_una_sola_consulta_para_todas(self) -> None:
        self._escuela("Benito Juárez", [self.prim])
        self._escuela("Práxedis", [self.prim, self.sec])
        self._escuela("Sin nivel", [])
        self._escuela("Sin productos", [], productos=False)
        self._escuela("Inactiva", [self.prim], activa=False)
        self.consultas = 0
        filas = list_schools_for_tariff(self.s)
        self.assertEqual(self.consultas, 2)   # escuelas + niveles de todas; antes 1 + 1–2 por escuela
        self.assertEqual(
            [(f["display_name"], f["nivel_nombre"]) for f in filas],
            [("Benito Juárez", "Primaria"), ("Práxedis — Primaria", "Primaria"), ("Práxedis — Secundaria", "Secundaria"), ("Sin nivel", None)],
        )

    def test_producto_inactivo_no_cuenta(self) -> None:
        e = self._escuela("Solo inactivos", [self.prim])
        for p in self.s.query(Producto).filter_by(escuela_id=e.id):
            p.activo = False
        self.s.flush()
        self.assertEqual(list_schools_for_tariff(self.s), [])
