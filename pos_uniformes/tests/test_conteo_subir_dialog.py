"""Tests del formulario de subir conteo (satélite admin)."""

from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from unittest.mock import patch

from PyQt6.QtWidgets import QApplication
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import (
    Categoria,
    ConteoInventario,
    Escuela,
    Marca,
    Producto,
    Variante,
)
from pos_uniformes.ui.dialogs.conteo_subir_dialog import ConteoSubirDialog


def _seed(session: Session, nombre: str, *, stock: int = 10) -> Escuela:
    e = Escuela(nombre=nombre)
    session.add(e)
    session.flush()
    cat = Categoria(nombre=f"C{nombre}")
    marca = Marca(nombre=f"M{nombre}")
    session.add_all([cat, marca])
    session.flush()
    prod = Producto(
        nombre=f"Pants {nombre}", nombre_base=f"Pants {nombre}",
        categoria_id=cat.id, marca_id=marca.id, escuela_id=e.id,
    )
    session.add(prod)
    session.flush()
    for talla in ("6", "8"):
        session.add(Variante(
            producto_id=prod.id, sku=f"S{nombre}{talla}", talla=talla, color="AZUL",
            precio_venta=100, stock_actual=stock,
        ))
    session.flush()
    return e


class ConteoSubirDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.factory = lambda: Session(self.engine)

    def _dialog(self) -> ConteoSubirDialog:
        return ConteoSubirDialog(session_factory=self.factory)

    def test_carga_escuelas(self) -> None:
        s = self.factory()
        _seed(s, "Uno")
        _seed(s, "Dos")
        s.commit()
        s.close()
        d = self._dialog()
        self.assertEqual(d._escuela_combo.count(), 2)

    def test_cargar_piezas_llena_tabla(self) -> None:
        s = self.factory()
        _seed(s, "Uno", stock=10)
        s.commit()
        s.close()
        d = self._dialog()
        d._escuela_combo.setCurrentIndex(0)
        d._cargar_piezas()
        self.assertEqual(d._table.rowCount(), 2)  # 2 variantes
        self.assertTrue(d._registrar_btn.isEnabled())
        # Físico default = stock de tienda (10)
        self.assertEqual(d._fisico_spins[0].value(), 10)

    def test_registrar_guarda_conteos(self) -> None:
        s = self.factory()
        e = _seed(s, "Uno", stock=10)
        s.commit()
        eid = e.id
        s.close()
        d = self._dialog()
        d._escuela_combo.setCurrentIndex(0)
        d._cargar_piezas()
        # Capturar una diferencia: una pieza con físico 8 (sistema 10)
        d._fisico_spins[0].setValue(8)
        with patch("pos_uniformes.ui.dialogs.conteo_subir_dialog.QMessageBox.information"):
            d._registrar()

        s = self.factory()
        conteos = s.scalars(
            select(ConteoInventario).where(ConteoInventario.escuela_id == eid)
        ).all()
        # Se registraron las 2 piezas; una con diferencia -2.
        self.assertEqual(len(conteos), 2)
        difs = sorted(c.diferencia for c in conteos)
        self.assertEqual(difs, [-2, 0])
        # ultimo_conteo_at quedó marcado (reinicia el ciclo del calendario).
        variantes = s.scalars(select(Variante)).all()
        self.assertTrue(all(v.ultimo_conteo_at is not None for v in variantes))
        s.close()


if __name__ == "__main__":
    unittest.main()
