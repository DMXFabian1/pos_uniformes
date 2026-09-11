"""Las tarjetas de jornada y los diálogos de empezar / revisar."""

from __future__ import annotations

import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

import pytest

pytest.importorskip("PyQt6.QtWidgets")

from PyQt6.QtWidgets import QApplication, QLabel, QMessageBox, QVBoxLayout, QWidget  # noqa: E402
from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from pos_uniformes.database.connection import Base  # noqa: E402
from pos_uniformes.database.models import ConteoJornada, Variante  # noqa: E402
from pos_uniformes.services import conteo_jornada_service as jn  # noqa: E402
from pos_uniformes.ui.helpers import conteos_jornadas_helper as tarjetas  # noqa: E402

_APP = QApplication.instance() or QApplication([])


def _foto(**k):
    base = dict(id=1, titulo="Práxedis Guerrero", escuela_id=5, tipo_pieza="",
                empleada_code="VEND-4", empleada_nombre="Stayce", total_tallas=128,
                iniciada_at=datetime.now(), terminada_at=None)
    base.update(k)
    return jn.JornadaRef(**base)


def _avance(hechas=4, total=14, t_hechas=31, t_total=128):
    return jn.Avance(tallas_hechas=t_hechas, tallas_total=t_total,
                     prendas_hechas=hechas, prendas_total=total)


class TarjetasTests(unittest.TestCase):
    def setUp(self) -> None:
        self.padre = QWidget()
        self.w = SimpleNamespace(
            conteos_jornadas_box=QVBoxLayout(), conteos_revisar_box=QVBoxLayout(),
            conteos_revisar_titulo=QLabel(self.padre), conteos_quien_label=QLabel(self.padre),
            _conteos_capturar=lambda f: self.capturadas.append(f),
            _conteos_revisar=lambda f: self.revisadas.append(f),
        )
        self.capturadas, self.revisadas = [], []

    def tearDown(self) -> None:
        self.padre.deleteLater()
        _APP.processEvents()

    def test_el_avance_se_lee_como_persona(self) -> None:
        self.assertEqual(tarjetas.texto_avance(_avance()), "4 de 14 prendas  ·  31 de 128 tallas")

    def test_sin_jornadas_lo_dice(self) -> None:
        tarjetas.pintar_jornadas(self.w, abiertas=[], por_revisar=[], code="VEND-4")
        self.assertEqual(self.w.conteos_jornadas_box.count(), 1)
        self.assertIn("No hay conteos a medias", self.w.conteos_jornadas_box.itemAt(0).widget().text())
        self.assertFalse(self.w.conteos_revisar_titulo.isVisibleTo(self.padre))

    def test_la_propia_se_puede_seguir_y_la_ajena_no(self) -> None:
        tarjetas.pintar_jornadas(
            self.w,
            abiertas=[(_foto(), _avance(), True), (_foto(id=2, empleada_code="VEND-5", empleada_nombre="Fanny"), _avance(), False)],
            por_revisar=[], code="VEND-4",
        )
        self.assertEqual(self.w.conteos_jornadas_box.count(), 2)
        propia = self.w.conteos_jornadas_box.itemAt(0).widget()
        ajena = self.w.conteos_jornadas_box.itemAt(1).widget()
        from PyQt6.QtWidgets import QPushButton

        b1 = propia.findChild(QPushButton)
        b2 = ajena.findChild(QPushButton)
        self.assertEqual(b1.text(), "Seguir")
        self.assertTrue(b1.isEnabled())
        self.assertEqual(b2.text(), "Es de otra")
        self.assertFalse(b2.isEnabled())
        b1.click()
        self.assertEqual([f.id for f in self.capturadas], [1])

    def test_lo_por_revisar_solo_aparece_si_llega_y_abre_la_revision(self) -> None:
        from PyQt6.QtWidgets import QPushButton

        tarjetas.pintar_jornadas(
            self.w, abiertas=[], por_revisar=[(_foto(id=9, terminada_at=datetime.now()), _avance(14, 14, 128, 128))],
            code="VEND-1",
        )
        self.assertTrue(self.w.conteos_revisar_titulo.isVisibleTo(self.padre))
        card = self.w.conteos_revisar_box.itemAt(0).widget()
        btn = card.findChild(QPushButton)
        self.assertEqual(btn.text(), "Revisar")
        btn.click()
        self.assertEqual([f.id for f in self.revisadas], [9])


    def test_el_subtitulo_resume_como_en_la_libreta(self) -> None:
        tarjetas.pintar_jornadas(
            self.w, abiertas=[(_foto(), _avance(), True), (_foto(id=2, empleada_code="VEND-5"), _avance(), False)],
            por_revisar=[(_foto(id=3, terminada_at=datetime.now()), _avance())], code="VEND-4",
        )
        self.assertEqual(self.w.conteos_quien_label.text(), "2 a medias (1 tuya)  ·  1 por revisar")
        tarjetas.pintar_jornadas(self.w, abiertas=[], por_revisar=[], code="VEND-4")
        self.assertEqual(self.w.conteos_quien_label.text(), "Nada a medias")

    def test_el_historial_pinta_estado_con_color(self) -> None:
        from dataclasses import replace

        from PyQt6.QtWidgets import QTableWidget

        tabla = QTableWidget(0, 5, self.padre)
        ahora = datetime.now()
        recientes = [
            (_foto(id=1, terminada_at=ahora), _avance(14, 14, 128, 128)),                      # por revisar
            (replace(_foto(id=2, terminada_at=ahora), revisada_at=ahora), _avance()),          # aplicada
            (replace(_foto(id=3, terminada_at=ahora), revisada_at=ahora, aplicada=False), _avance()),  # descartada
        ]
        tarjetas.pintar_historial(tabla, recientes)
        self.assertEqual(tabla.rowCount(), 3)
        self.assertEqual([tabla.item(i, 4).text() for i in range(3)], ["Por revisar", "Aplicada", "Descartada"])
        self.assertEqual(tabla.item(0, 3).text(), "128 de 128")
        tarjetas.pintar_historial(tabla, [])
        self.assertIn("Todavía no hay", tabla.item(0, 0).text())


class RevisionDialogTests(unittest.TestCase):
    """El dueño ve las diferencias y aplica o descarta."""

    def setUp(self) -> None:
        from pos_uniformes.services.conteo_service import ConteoInput, registrar_conteos_lote
        from pos_uniformes.tests.test_conteo_jornada_service import _seed

        self._dialogos = []
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.factory = lambda: Session(self.engine)
        s = self.factory()
        e = _seed(s, "Uno")
        s.commit()
        j = jn.abrir_jornada(s, escuela_id=e.id, empleada_code="VEND-4", empleada_nombre="Stayce")
        v = list(s.scalars(select(Variante).order_by(Variante.id)).all())
        registrar_conteos_lote(s, [ConteoInput(v[0].id, 7), ConteoInput(v[1].id, 10)], "x", jornada_id=j.id)
        jn.terminar_jornada(s, j, empleada_code="VEND-4")
        s.commit()
        s.refresh(j)
        self.foto = jn.ref(j)
        s.close()

    def _dialogo(self, quien="VEND-1"):
        from pos_uniformes.ui.dialogs.conteo_jornada_dialogs import ConteoRevisionDialog

        d = ConteoRevisionDialog(jornada=self.foto, revisada_por=quien, session_factory=self.factory)
        self._dialogos.append(d)
        return d

    def tearDown(self) -> None:
        for d in self._dialogos:
            d.close()
            d.deleteLater()
        self._dialogos = []
        _APP.processEvents()

    def test_muestra_solo_las_que_difieren_por_defecto(self) -> None:
        d = self._dialogo()
        self.assertEqual(d._table.rowCount(), 1)
        self.assertEqual(d._table.item(0, 4).text(), "-3")
        self.assertIn("Stayce", d._resumen_label.text())
        d._solo_dif.setChecked(False)
        self.assertEqual(d._table.rowCount(), 2)

    def test_aplicar_cambia_el_stock_y_cierra_la_jornada(self) -> None:
        d = self._dialogo()
        with patch("pos_uniformes.ui.dialogs.conteo_jornada_dialogs.QMessageBox.question",
                   return_value=QMessageBox.StandardButton.Yes), \
             patch("pos_uniformes.ui.dialogs.conteo_jornada_dialogs.QMessageBox.information"):
            d._aplicar()
        self.assertEqual(d.resultado, "aplicada")
        s = self.factory()
        v = list(s.scalars(select(Variante).order_by(Variante.id)).all())
        self.assertEqual(v[0].stock_actual, 7)
        self.assertEqual(v[1].stock_actual, 10)
        self.assertIsNotNone(s.get(ConteoJornada, self.foto.id).revisada_at)

    def test_descartar_no_toca_el_stock(self) -> None:
        d = self._dialogo()
        with patch("pos_uniformes.ui.dialogs.conteo_jornada_dialogs.QMessageBox.question",
                   return_value=QMessageBox.StandardButton.Yes):
            d._descartar()
        self.assertEqual(d.resultado, "descartada")
        s = self.factory()
        self.assertEqual(s.scalars(select(Variante)).first().stock_actual, 10)
        self.assertIsNotNone(s.get(ConteoJornada, self.foto.id).revisada_at)

    def test_una_empleada_no_puede_aplicar(self) -> None:
        d = self._dialogo(quien="VEND-4")
        with patch("pos_uniformes.ui.dialogs.conteo_jornada_dialogs.QMessageBox.question",
                   return_value=QMessageBox.StandardButton.Yes), \
             patch("pos_uniformes.ui.dialogs.conteo_jornada_dialogs.QMessageBox.critical") as err:
            d._aplicar()
        err.assert_called_once()
        self.assertEqual(d.resultado, "")


if __name__ == "__main__":
    unittest.main()
