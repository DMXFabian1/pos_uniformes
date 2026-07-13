"""Tests del diálogo de orden de conteo pendiente (kiosko, Fase 2)."""

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
    TipoPieza,
    Variante,
)
from pos_uniformes.ui.dialogs.conteo_orden_dialog import ConteoOrdenDialog

_AHORA = datetime(2026, 7, 12, tzinfo=timezone.utc)


def _seed(session: Session, nombre: str, *, dias_vigencia=30, ultimo_hace=None) -> Escuela:
    e = Escuela(nombre=nombre)
    session.add(e)
    session.flush()
    session.add(ConfigConteoEscuela(escuela_id=e.id, dias_vigencia=dias_vigencia))
    cat = Categoria(nombre=f"C{nombre}")
    marca = Marca(nombre=f"M{nombre}")
    pieza = TipoPieza(nombre=f"Pieza{nombre}")
    session.add_all([cat, marca, pieza])
    session.flush()
    prod = Producto(
        nombre=f"P{nombre}", nombre_base=f"P{nombre}",
        categoria_id=cat.id, marca_id=marca.id, escuela_id=e.id, tipo_pieza_id=pieza.id,
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


class ConteoOrdenDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.factory = lambda: Session(self.engine)
        self.impreso: list[tuple[str, list[str]]] = []

    def _dialog(self) -> ConteoOrdenDialog:
        return ConteoOrdenDialog(
            session_factory=self.factory,
            print_sheets=lambda title, sheets: self.impreso.append((title, sheets)),
        )

    def test_lista_solo_vencidas(self) -> None:
        s = self.factory()
        _seed(s, "AlDia", ultimo_hace=1)
        _seed(s, "Vencida", ultimo_hace=60)
        _seed(s, "Nunca")
        s.commit()
        s.close()
        d = self._dialog()
        self.assertEqual(d._list.count(), 2)
        nombres = [n for (n, _det) in d._filas]
        detalles = [det for (_n, det) in d._filas]
        self.assertIn("Vencida", nombres)
        self.assertIn("Nunca", nombres)
        self.assertIn("nunca contada", detalles)

    def test_sin_vencidas_desactiva_boton(self) -> None:
        s = self.factory()
        _seed(s, "AlDia", ultimo_hace=1)
        s.commit()
        s.close()
        d = self._dialog()
        self.assertEqual(d._list.count(), 0)
        self.assertFalse(d._print_btn.isEnabled())

    def test_toggle_muestra_las_al_dia(self) -> None:
        s = self.factory()
        _seed(s, "AlDia", ultimo_hace=1)       # al día
        _seed(s, "Vencida", ultimo_hace=60)    # vencida
        s.commit()
        s.close()
        d = self._dialog()
        self.assertEqual(d._list.count(), 1)   # por defecto: solo la vencida
        d._mostrar_al_dia.setChecked(True)     # dispara refresh
        self.assertEqual(d._list.count(), 2)   # ahora incluye la que está al día
        nombres = [n for (n, _det) in d._filas]
        detalles = [det for (_n, det) in d._filas]
        self.assertIn("AlDia", nombres)
        self.assertTrue(any(det.startswith("en ") for det in detalles))

    def test_imprimir_una_al_dia(self) -> None:
        s = self.factory()
        _seed(s, "AlDia", ultimo_hace=1)
        s.commit()
        s.close()
        d = self._dialog()
        d._mostrar_al_dia.setChecked(True)
        d._list.setCurrentRow(0)
        d._imprimir()
        self.assertEqual(len(self.impreso), 1)
        self.assertIn("AlDia", self.impreso[0][0])

    def test_imprimir_genera_y_manda_hojas(self) -> None:
        s = self.factory()
        _seed(s, "Vencida", ultimo_hace=60)
        s.commit()
        s.close()
        d = self._dialog()
        d._list.setCurrentRow(0)
        d._imprimir()
        self.assertEqual(len(self.impreso), 1)
        title, sheets = self.impreso[0]
        self.assertIn("Vencida", title)
        self.assertTrue(len(sheets) >= 1)

    def test_imprimir_sin_hojas_avisa(self) -> None:
        # Escuela vencida por config pero sin variantes -> build_conteo_sheets vacío.
        s = self.factory()
        e = Escuela(nombre="SoloConfig")
        s.add(e)
        s.flush()
        s.add(ConfigConteoEscuela(escuela_id=e.id, dias_vigencia=30))
        s.commit()
        eid = e.id
        s.close()
        # Forzar que aparezca (sin productos no entra al calendario), así que
        # inyectamos el item a mano para probar la rama "sin hojas".
        d = self._dialog()
        from PyQt6.QtWidgets import QListWidgetItem
        from PyQt6.QtCore import Qt

        item = QListWidgetItem("SoloConfig · nunca contada")
        item.setData(Qt.ItemDataRole.UserRole, (eid, "SoloConfig"))
        d._list.addItem(item)
        d._list.setCurrentRow(d._list.count() - 1)
        with patch(
            "pos_uniformes.ui.dialogs.conteo_orden_dialog.QMessageBox.information"
        ) as info:
            d._imprimir()
        info.assert_called_once()
        self.assertEqual(self.impreso, [])  # no imprimió


if __name__ == "__main__":
    unittest.main()
