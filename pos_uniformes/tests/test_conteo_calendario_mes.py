"""Tests del calendario visual de conteos por mes (Fase 4)."""

from __future__ import annotations

import os
import unittest
from datetime import date, datetime, timedelta, timezone

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import (
    Categoria,
    ConfigConteoEscuela,
    ConteoInventario,
    Escuela,
    Marca,
    Producto,
    Variante,
)
from pos_uniformes.services.conteo_calendario_service import (
    EstadoCalendarioConteo,
    agrupar_calendario_por_dia,
)
from pos_uniformes.ui.dialogs.conteo_calendario_mes_panel import ConteoCalendarioMesPanel

_AHORA = datetime(2026, 7, 12, tzinfo=timezone.utc)


def _estado(nombre: str, proxima: date | None, *, vencida=False) -> EstadoCalendarioConteo:
    return EstadoCalendarioConteo(
        escuela_id=hash(nombre) % 1000,
        escuela_nombre=nombre,
        dias_vigencia=30,
        total_variantes=1,
        ultimo_conteo=None if proxima is None else datetime(2026, 1, 1, tzinfo=timezone.utc),
        proxima_fecha=proxima,
        vencida=vencida,
        dias_para_vencer=None if proxima is None else 5,
        nunca_contada=proxima is None,
    )


class AgruparPorDiaTests(unittest.TestCase):
    def test_agrupa_solo_del_mes(self) -> None:
        estados = [
            _estado("A", date(2026, 7, 10)),
            _estado("B", date(2026, 7, 10)),
            _estado("C", date(2026, 8, 3)),   # otro mes
            _estado("Nunca", None),           # sin fecha
        ]
        por_dia = agrupar_calendario_por_dia(estados, 2026, 7)
        self.assertEqual(set(por_dia.keys()), {10})
        self.assertEqual({e.escuela_nombre for e in por_dia[10]}, {"A", "B"})

    def test_mes_vacio(self) -> None:
        estados = [_estado("A", date(2026, 7, 10))]
        self.assertEqual(agrupar_calendario_por_dia(estados, 2026, 12), {})


def _seed(session: Session, nombre: str, *, dias_vigencia=30, ultimo_hace=None) -> None:
    e = Escuela(nombre=nombre)
    session.add(e)
    session.flush()
    session.add(ConfigConteoEscuela(escuela_id=e.id, dias_vigencia=dias_vigencia))
    cat = Categoria(nombre=f"C{nombre}")
    marca = Marca(nombre=f"M{nombre}")
    session.add_all([cat, marca])
    session.flush()
    prod = Producto(nombre=f"P{nombre}", nombre_base=f"P{nombre}",
                    categoria_id=cat.id, marca_id=marca.id, escuela_id=e.id)
    session.add(prod)
    session.flush()
    v = Variante(producto_id=prod.id, sku=f"S{nombre}", talla="12", color="AZUL",
                 precio_venta=100, stock_actual=5)
    session.add(v)
    session.flush()
    if ultimo_hace is not None:
        session.add(ConteoInventario(
            variante_id=v.id, escuela_id=e.id, stock_sistema=5, stock_fisico=5,
            diferencia=0, contado_por="t", contado_at=_AHORA - timedelta(days=ultimo_hace),
        ))
    session.flush()


class MesDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.factory = lambda: Session(self.engine)

    def test_dialogo_arranca_en_el_mes_de_hoy(self) -> None:
        s = self.factory()
        _seed(s, "X", ultimo_hace=1)
        s.commit()
        s.close()
        d = ConteoCalendarioMesPanel(session_factory=self.factory, hoy=date(2026, 7, 12))
        self.assertIn("Julio 2026", d._mes_label.text())

    def test_navegacion_de_mes(self) -> None:
        s = self.factory()
        _seed(s, "X", ultimo_hace=1)
        s.commit()
        s.close()
        d = ConteoCalendarioMesPanel(session_factory=self.factory, hoy=date(2026, 7, 12))
        d._cambiar_mes(1)
        self.assertIn("Agosto 2026", d._mes_label.text())
        d._cambiar_mes(-2)
        self.assertIn("Junio 2026", d._mes_label.text())

    def test_muestra_vencidas(self) -> None:
        s = self.factory()
        _seed(s, "Atrasada", ultimo_hace=60)
        s.commit()
        s.close()
        d = ConteoCalendarioMesPanel(session_factory=self.factory, hoy=date(2026, 7, 12))
        self.assertIn("1", d._chip_vencidas.text())
        self.assertIn("requieren conteo", d._chip_vencidas.text())


if __name__ == "__main__":
    unittest.main()
