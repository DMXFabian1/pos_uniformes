"""Tests del diálogo admin del calendario de conteos (Fase 1)."""

from __future__ import annotations

import os
import unittest
from datetime import datetime, timedelta, timezone

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from unittest.mock import patch

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
from pos_uniformes.services.conteo_service import obtener_estado_conteo_escuela
from pos_uniformes.ui.dialogs.conteo_calendario_dialog import ConteoCalendarioDialog

_AHORA = datetime(2026, 7, 12, tzinfo=timezone.utc)


def _seed(session: Session, nombre: str, *, dias_vigencia=None, ultimo_hace=None) -> Escuela:
    e = Escuela(nombre=nombre)
    session.add(e)
    session.flush()
    if dias_vigencia is not None:
        session.add(ConfigConteoEscuela(escuela_id=e.id, dias_vigencia=dias_vigencia))
    cat = Categoria(nombre=f"C{nombre}")
    marca = Marca(nombre=f"M{nombre}")
    session.add_all([cat, marca])
    session.flush()
    prod = Producto(
        nombre=f"P{nombre}", nombre_base=f"P{nombre}",
        categoria_id=cat.id, marca_id=marca.id, escuela_id=e.id,
    )
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
    return e


class ConteoCalendarioDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.factory = lambda: Session(self.engine)

    def _dialog(self) -> ConteoCalendarioDialog:
        return ConteoCalendarioDialog(session_factory=self.factory)

    def test_tabla_lista_escuelas(self) -> None:
        s = self.factory()
        _seed(s, "AlDia", dias_vigencia=30, ultimo_hace=1)
        _seed(s, "Vencida", dias_vigencia=30, ultimo_hace=60)
        s.commit()
        s.close()
        d = self._dialog()
        self.assertEqual(d._table.rowCount(), 2)
        # Ordenadas por urgencia: vencida primero.
        self.assertEqual(d._table.item(0, 0).text(), "Vencida")

    def test_spin_refleja_vigencia(self) -> None:
        s = self.factory()
        e = _seed(s, "X", dias_vigencia=45, ultimo_hace=5)
        s.commit()
        eid = e.id
        s.close()
        d = self._dialog()
        self.assertEqual(d._spins[eid].value(), 45)

    def test_guardar_persiste_nueva_frecuencia(self) -> None:
        s = self.factory()
        e = _seed(s, "X", dias_vigencia=90, ultimo_hace=5)
        s.commit()
        eid = e.id
        s.close()
        d = self._dialog()
        d._spins[eid].setValue(15)
        with patch(
            "pos_uniformes.ui.dialogs.conteo_calendario_dialog.QMessageBox.information"
        ):
            d._guardar()
        s = self.factory()
        estado = obtener_estado_conteo_escuela(s, eid)
        self.assertEqual(estado.dias_vigencia, 15)
        s.close()

    def test_resumen_cuenta_vencidas(self) -> None:
        s = self.factory()
        _seed(s, "AlDia", dias_vigencia=30, ultimo_hace=1)
        _seed(s, "Vencida", dias_vigencia=30, ultimo_hace=60)
        _seed(s, "Nunca", dias_vigencia=30)
        s.commit()
        s.close()
        d = self._dialog()
        self.assertIn("2 requieren conteo", d._resumen_label.text())


if __name__ == "__main__":
    unittest.main()
