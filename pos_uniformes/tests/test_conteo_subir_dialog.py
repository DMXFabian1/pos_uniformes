"""Tests del formulario de subir conteo (satélite admin)."""

from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from unittest.mock import patch

from PyQt6.QtWidgets import QApplication, QMessageBox
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import (
    Categoria,
    ConteoInventario,
    Escuela,
    Marca,
    Producto,
    TipoPieza,
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
        self._dialogos = []
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.factory = lambda: Session(self.engine)

    def _dialog(self) -> ConteoSubirDialog:
        d = ConteoSubirDialog(session_factory=self.factory)
        self._dialogos.append(d)
        return d

    def tearDown(self) -> None:
        # Ventanas vivas de otras pruebas estorban a las que dependen del foco.
        for d in self._dialogos:
            d.close()
            d.deleteLater()
        self._dialogos = []
        self.app.processEvents()

    def test_carga_escuelas(self) -> None:
        s = self.factory()
        _seed(s, "Uno")
        _seed(s, "Dos")
        s.commit()
        s.close()
        d = self._dialog()
        # 2 escuelas + la entrada especial "Productos básicos".
        self.assertEqual(d._escuela_combo.count(), 3)
        self.assertGreaterEqual(d._escuela_combo.findText("Uno"), 0)
        self.assertGreaterEqual(d._escuela_combo.findText("Dos"), 0)

    def test_cargar_piezas_llena_tabla(self) -> None:
        s = self.factory()
        _seed(s, "Uno", stock=10)
        s.commit()
        s.close()
        d = self._dialog()
        d._escuela_combo.setCurrentIndex(d._escuela_combo.findText("Uno"))
        d._cargar_piezas()
        # 1 fila-encabezado del producto + 2 variantes
        self.assertEqual(d._table.rowCount(), 3)
        self.assertEqual(len(d._fisico_inputs), 2)
        # Nada que registrar todavía: el botón espera al primer número.
        self.assertFalse(d._registrar_btn.isEnabled())
        # Campo limpio: sin el esperado como pista. Si lo ve, lo copia.
        self.assertEqual(d._fisico_inputs[0].text(), "")
        self.assertEqual(d._fisico_inputs[0].placeholderText(), "")
        # Y la columna con el stock del sistema ya no existe.
        encabezados = [d._table.horizontalHeaderItem(c).text() for c in range(d._table.columnCount())]
        self.assertEqual(encabezados, ["Talla", "Color", "Cuántas hay"])

    def test_excluye_productos_virtuales(self) -> None:
        # Pants 3pz y Chamarra son virtuales: no se cuentan (se arman de otros).
        s = self.factory()
        e = Escuela(nombre="EscV")
        s.add(e)
        s.flush()
        cat = Categoria(nombre="CV")
        marca = Marca(nombre="MV")
        pieza_real = TipoPieza(nombre="Playera")
        pieza_virtual = TipoPieza(nombre="Pants 3pz")
        s.add_all([cat, marca, pieza_real, pieza_virtual])
        s.flush()
        p_real = Producto(
            nombre="Playera Real", nombre_base="Playera Real",
            categoria_id=cat.id, marca_id=marca.id, escuela_id=e.id,
            tipo_pieza_id=pieza_real.id,
        )
        p_virt = Producto(
            nombre="Pants 3pz Combo", nombre_base="Pants 3pz Combo",
            categoria_id=cat.id, marca_id=marca.id, escuela_id=e.id,
            tipo_pieza_id=pieza_virtual.id,
        )
        s.add_all([p_real, p_virt])
        s.flush()
        s.add(Variante(producto_id=p_real.id, sku="R1", talla="CH", color="A",
                       precio_venta=100, stock_actual=5))
        s.add(Variante(producto_id=p_virt.id, sku="V1", talla="CH", color="A",
                       precio_venta=200, stock_actual=5))
        s.commit()
        s.close()
        d = self._dialog()
        d._escuela_combo.setCurrentIndex(d._escuela_combo.findText("EscV"))
        d._cargar_piezas()
        # Solo la variante real aparece; la virtual (Pants 3pz) se excluye.
        self.assertEqual(len(d._fisico_inputs), 1)

    def test_el_avance_se_cuenta_sin_revelar_diferencias(self) -> None:
        """Antes esto pintaba la diferencia contra lo esperado en vivo.

        Se quitó a propósito: decirle a quien captura cuál era la respuesta
        "correcta" convierte el conteo en una confirmación de lo que el
        sistema ya creía. Ahora solo se le dice cuánto lleva.
        """
        s = self.factory()
        _seed(s, "Uno", stock=10)
        s.commit()
        s.close()
        d = self._dialog()
        d._escuela_combo.setCurrentIndex(d._escuela_combo.findText("Uno"))
        d._cargar_piezas()

        self.assertIn("0 de 2", d._hint.text())
        self.assertFalse(d._registrar_btn.isEnabled())

        d._fisico_inputs[0].setText("8")
        self.assertIn("1 de 2", d._hint.text())
        self.assertIn("sin contar", d._hint.text())
        self.assertTrue(d._registrar_btn.isEnabled())
        # Ni rastro del esperado: el campo no cambia de color al diferir.
        self.assertFalse(d._fisico_inputs[0].styleSheet())

        d._fisico_inputs[1].setText("3")
        self.assertIn("2 de 2", d._hint.text())
        self.assertNotIn("sin contar", d._hint.text())

    def test_registrar_guarda_conteos(self) -> None:
        s = self.factory()
        e = _seed(s, "Uno", stock=10)
        s.commit()
        eid = e.id
        s.close()
        d = self._dialog()
        d._escuela_combo.setCurrentIndex(d._escuela_combo.findText("Uno"))
        d._cargar_piezas()
        # Una talla contada (8, esperado 10); la otra se deja vacía porque
        # nadie la contó.
        d._fisico_inputs[0].setText("8")
        with patch(
            "pos_uniformes.ui.dialogs.conteo_subir_dialog.QMessageBox.information"
        ), patch(
            "pos_uniformes.ui.dialogs.conteo_subir_dialog.QMessageBox.question",
            return_value=QMessageBox.StandardButton.Yes,
        ):
            d._registrar()

        s = self.factory()
        conteos = s.scalars(
            select(ConteoInventario).where(ConteoInventario.escuela_id == eid)
        ).all()
        # SOLO la que se capturó. La vacía no se inventa.
        self.assertEqual(len(conteos), 1)
        self.assertEqual(conteos[0].diferencia, -2)
        # Y la que nadie contó sigue sin fecha de conteo: no se le pone cara
        # de nueva a un dato que nadie miró.
        variantes = s.scalars(select(Variante)).all()
        con_fecha = [v for v in variantes if v.ultimo_conteo_at is not None]
        self.assertEqual(len(con_fecha), 1)
        s.close()


if __name__ == "__main__":
    unittest.main()


class ConteoConJornadaTests(unittest.TestCase):
    """Con jornada: amarrado a la escuela, se puede pausar y retomar."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self._dialogos = []
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.factory = lambda: Session(self.engine)
        s = self.factory()
        self.escuela = _seed(s, "Uno", stock=10)
        s.commit()
        from pos_uniformes.services.conteo_jornada_service import abrir_jornada, ref

        j = abrir_jornada(
            s, escuela_id=self.escuela.id, empleada_code="VEND-4", empleada_nombre="Stayce"
        )
        s.commit()
        s.refresh(j)
        self.jornada = ref(j)   # la UI trabaja con la foto, nunca con el objeto vivo
        s.close()

    def _dialog(self):
        d = ConteoSubirDialog(
            session_factory=self.factory, contado_por="Stayce (VEND-4)",
            jornada=self.jornada, empleada_code="VEND-4",
        )
        self._dialogos.append(d)
        return d

    def tearDown(self) -> None:
        for d in getattr(self, "_dialogos", []):
            d.close()
            d.deleteLater()
        self._dialogos = []
        self.app.processEvents()

    def test_abre_amarrado_a_la_jornada_sin_elegir_escuela(self) -> None:
        d = self._dialog()
        self.assertFalse(d._escuela_combo.isVisibleTo(d))
        self.assertEqual(len(d._fisico_inputs), 2)  # cargó solo
        self.assertEqual(d._registrar_btn.text(), "Terminar conteo")
        self.assertTrue(d._pausar_btn.isVisibleTo(d))
        self.assertFalse(d._pausar_btn.isEnabled())  # nada nuevo todavía

    def test_pausar_guarda_lo_que_va_y_deja_la_jornada_abierta(self) -> None:
        from pos_uniformes.database.models import ConteoJornada

        d = self._dialog()
        d._fisico_inputs[0].setText("7")
        self.assertTrue(d._pausar_btn.isEnabled())
        with patch("pos_uniformes.ui.dialogs.conteo_subir_dialog.QMessageBox.information"):
            d._pausar()

        s = self.factory()
        conteos = s.scalars(select(ConteoInventario)).all()
        self.assertEqual(len(conteos), 1)
        self.assertEqual(conteos[0].jornada_id, self.jornada.id)
        self.assertIsNone(s.get(ConteoJornada, self.jornada.id).terminada_at)

    def test_al_retomar_lo_capturado_aparece_puesto_y_bloqueado(self) -> None:
        d = self._dialog()
        d._fisico_inputs[0].setText("7")
        with patch("pos_uniformes.ui.dialogs.conteo_subir_dialog.QMessageBox.information"):
            d._pausar()

        d2 = self._dialog()
        self.assertEqual(d2._fisico_inputs[0].text(), "7")   # SU número, no el del sistema
        self.assertTrue(d2._fisico_inputs[0].isReadOnly())
        self.assertEqual(d2._fisico_inputs[1].text(), "")
        self.assertIn("1 de 2", d2._hint.text())

    def test_retomar_y_terminar_no_duplica_lo_de_antes(self) -> None:
        from pos_uniformes.database.models import ConteoJornada

        d = self._dialog()
        d._fisico_inputs[0].setText("7")
        with patch("pos_uniformes.ui.dialogs.conteo_subir_dialog.QMessageBox.information"):
            d._pausar()

        d2 = self._dialog()
        d2._fisico_inputs[1].setText("10")
        with patch("pos_uniformes.ui.dialogs.conteo_subir_dialog.QMessageBox.information"):
            d2._registrar()

        s = self.factory()
        conteos = s.scalars(select(ConteoInventario)).all()
        self.assertEqual(len(conteos), 2)  # una de cada sesión, ninguna repetida
        self.assertIsNotNone(s.get(ConteoJornada, self.jornada.id).terminada_at)
        # Y sigue sin tocar el inventario.
        self.assertTrue(all(v.stock_actual == 10 for v in s.scalars(select(Variante)).all()))

    def test_terminar_con_huecos_avisa_y_respeta_un_no(self) -> None:
        from pos_uniformes.database.models import ConteoJornada

        d = self._dialog()
        d._fisico_inputs[0].setText("7")
        with patch(
            "pos_uniformes.ui.dialogs.conteo_subir_dialog.QMessageBox.question",
            return_value=QMessageBox.StandardButton.No,
        ) as pregunta:
            d._registrar()
        pregunta.assert_called_once()
        s = self.factory()
        self.assertEqual(len(s.scalars(select(ConteoInventario)).all()), 0)
        self.assertIsNone(s.get(ConteoJornada, self.jornada.id).terminada_at)
