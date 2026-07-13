"""Tests de conteo de 'productos básicos' (sin escuela, ligados por catálogo)."""

from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import (
    CatalogSchoolProductLink,
    Categoria,
    Escuela,
    Marca,
    Producto,
    TipoPieza,
    Variante,
)
from pos_uniformes.services.conteo_calendario_service import obtener_calendario_conteo
from pos_uniformes.services.conteo_service import (
    DIAS_VIGENCIA_DEFAULT,
    ESCUELA_ID_BASICOS,
    NOMBRE_BASICOS,
    guardar_dias_vigencia_basicos,
    obtener_dias_vigencia_basicos,
    obtener_estado_conteo_basicos,
)


def _seed_basico(session: Session, tipo_nombre: str = "Playera") -> None:
    """Un producto básico: sin escuela, ligado por catálogo a una escuela."""
    esc = Escuela(nombre="EscuelaLink")
    cat = Categoria(nombre="CatB")
    marca = Marca(nombre="MarcaB")
    pieza = TipoPieza(nombre=tipo_nombre)
    session.add_all([esc, cat, marca, pieza])
    session.flush()
    prod = Producto(
        nombre="Playera Básica", nombre_base="Playera Básica",
        categoria_id=cat.id, marca_id=marca.id, escuela_id=None,  # básico
        tipo_pieza_id=pieza.id,
    )
    session.add(prod)
    session.flush()
    session.add(Variante(
        producto_id=prod.id, sku="BAS1", talla="CH", color="BLANCO",
        precio_venta=80, stock_actual=3,
    ))
    session.add(CatalogSchoolProductLink(escuela_id=esc.id, producto_id=prod.id, activo=True))
    session.commit()


class ConteoBasicosTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)

    def test_dias_vigencia_default_y_setter(self) -> None:
        with Session(self.engine) as s:
            self.assertEqual(obtener_dias_vigencia_basicos(s), DIAS_VIGENCIA_DEFAULT)
            guardar_dias_vigencia_basicos(s, 15)
            s.commit()
        with Session(self.engine) as s:
            self.assertEqual(obtener_dias_vigencia_basicos(s), 15)

    def test_estado_basicos_nunca_contado(self) -> None:
        with Session(self.engine) as s:
            _seed_basico(s)
            estado = obtener_estado_conteo_basicos(s)
            self.assertEqual(estado.escuela_id, ESCUELA_ID_BASICOS)
            self.assertEqual(estado.escuela_nombre, NOMBRE_BASICOS)
            self.assertEqual(estado.total_variantes, 1)
            self.assertIsNone(estado.ultimo_conteo)

    def test_basicos_aparece_en_calendario(self) -> None:
        with Session(self.engine) as s:
            _seed_basico(s)
            cal = obtener_calendario_conteo(s)
            basicos = [e for e in cal if e.escuela_id == ESCUELA_ID_BASICOS]
            self.assertEqual(len(basicos), 1)
            self.assertTrue(basicos[0].vencida)  # nunca contado -> vencido
            self.assertTrue(basicos[0].nunca_contada)

    def test_basicos_sin_productos_no_aparece(self) -> None:
        with Session(self.engine) as s:
            cal = obtener_calendario_conteo(s)  # sin básicos sembrados
            self.assertEqual([e for e in cal if e.escuela_id == ESCUELA_ID_BASICOS], [])


class ConteoBasicosDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        with Session(self.engine) as s:
            _seed_basico(s)
        self.factory = lambda: Session(self.engine)

    def test_orden_imprime_hoja_de_basicos(self) -> None:
        from pos_uniformes.ui.dialogs.conteo_orden_dialog import ConteoOrdenDialog

        impreso: list = []
        d = ConteoOrdenDialog(
            session_factory=self.factory,
            print_sheets=lambda title, sheets: impreso.append((title, sheets)),
        )
        # Básicos nunca contados → aparece vencido por defecto. Seleccionarlo.
        fila = next(
            r for r in range(d._list.count())
            if d._list.item(r).data(Qt.ItemDataRole.UserRole)[0] == ESCUELA_ID_BASICOS
        )
        d._list.setCurrentRow(fila)
        d._imprimir()
        self.assertEqual(len(impreso), 1)
        title, sheets = impreso[0]
        self.assertIn(NOMBRE_BASICOS, title)
        self.assertTrue(any("PRODUCTOS BÁSICOS" in s for s in sheets))

    def test_subir_carga_variantes_de_basicos(self) -> None:
        from pos_uniformes.ui.dialogs.conteo_subir_dialog import ConteoSubirDialog

        d = ConteoSubirDialog(session_factory=self.factory)
        idx = d._escuela_combo.findData(ESCUELA_ID_BASICOS)
        self.assertGreaterEqual(idx, 0)
        d._escuela_combo.setCurrentIndex(idx)
        d._cargar_piezas()
        self.assertEqual(len(d._fisico_inputs), 1)  # la única variante básica

    def test_orden_filtro_tipo_para_basicos(self) -> None:
        from pos_uniformes.ui.dialogs.conteo_orden_dialog import ConteoOrdenDialog

        d = ConteoOrdenDialog(
            session_factory=self.factory, print_sheets=lambda t, s: None
        )
        fila = next(
            r for r in range(d._list.count())
            if d._list.item(r).data(Qt.ItemDataRole.UserRole)[0] == ESCUELA_ID_BASICOS
        )
        d._list.setCurrentRow(fila)
        # Al elegir básicos, aparece el filtro de tipo con el tipo sembrado.
        self.assertFalse(d._tipo_row.isHidden())
        self.assertGreaterEqual(d._tipo_combo.findText("Playera"), 0)

    def test_subir_filtro_tipo_para_basicos(self) -> None:
        from pos_uniformes.ui.dialogs.conteo_subir_dialog import ConteoSubirDialog

        d = ConteoSubirDialog(session_factory=self.factory)
        idx = d._escuela_combo.findData(ESCUELA_ID_BASICOS)
        d._escuela_combo.setCurrentIndex(idx)
        self.assertFalse(d._tipo_combo.isHidden())
        self.assertGreaterEqual(d._tipo_combo.findText("Playera"), 0)

    def test_panel_guarda_frecuencia_de_basicos(self) -> None:
        from unittest.mock import patch

        from pos_uniformes.ui.dialogs.conteo_calendario_panel import ConteoCalendarioPanel

        panel = ConteoCalendarioPanel(session_factory=self.factory)
        # La fila de básicos aparece con su spin (id-centinela).
        self.assertIn(ESCUELA_ID_BASICOS, panel._spins)
        panel._spins[ESCUELA_ID_BASICOS].setValue(20)
        with patch(
            "pos_uniformes.ui.dialogs.conteo_calendario_panel.QMessageBox.information"
        ):
            panel._guardar()
        with Session(self.engine) as s:
            self.assertEqual(obtener_dias_vigencia_basicos(s), 20)


if __name__ == "__main__":
    unittest.main()
