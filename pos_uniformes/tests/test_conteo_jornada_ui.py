"""Las tarjetas de jornada y los diálogos de empezar / revisar."""

from __future__ import annotations

import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

import pytest

pytest.importorskip("PyQt6.QtWidgets")

from PyQt6.QtCore import Qt  # noqa: E402
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
            conteos_jornadas_titulo=QLabel(self.padre), conteos_jornadas_panel=QLabel(self.padre),
            _conteos_capturar=lambda f: self.capturadas.append(f),
            _conteos_revisar=lambda f: self.revisadas.append(f),
        )
        self.capturadas, self.revisadas = [], []

    def tearDown(self) -> None:
        self.padre.deleteLater()
        _APP.processEvents()

    def test_el_avance_se_lee_como_persona(self) -> None:
        self.assertEqual(tarjetas.texto_avance(_avance()), "4 de 14 prendas  ·  31 de 128 tallas")

    def test_sin_jornadas_la_seccion_desaparece(self) -> None:
        # Antes decía "no hay conteos a medias" en una caja de media pantalla;
        # desde el 2026-09-22 simplemente no se muestra.
        tarjetas.pintar_jornadas(self.w, abiertas=[], por_revisar=[], code="VEND-4")
        self.assertEqual(self.w.conteos_jornadas_box.count(), 0)
        self.assertFalse(self.w.conteos_jornadas_titulo.isVisibleTo(self.padre))
        self.assertFalse(self.w.conteos_jornadas_panel.isVisibleTo(self.padre))
        self.assertFalse(self.w.conteos_revisar_titulo.isVisibleTo(self.padre))

    def test_con_jornadas_la_seccion_vuelve(self) -> None:
        tarjetas.pintar_jornadas(self.w, abiertas=[(_foto(), _avance(), True)], por_revisar=[], code="VEND-4")
        self.assertTrue(self.w.conteos_jornadas_titulo.isVisibleTo(self.padre))
        self.assertEqual(self.w.conteos_jornadas_box.count(), 1)

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

    def test_eliminar_y_reasignar_segun_quien_mira(self) -> None:
        from PyQt6.QtWidgets import QPushButton

        eliminadas, reasignadas = [], []
        self.w._conteos_eliminar = lambda f: eliminadas.append(f.id)
        self.w._conteos_reasignar = lambda f: reasignadas.append(f.id)
        propia = _foto(id=1, empleada_code="VEND-4")
        ajena = _foto(id=2, empleada_code="VEND-5", empleada_nombre="Fanny")

        # Una empleada: puede eliminar la suya, no la ajena; reasignar nunca.
        tarjetas.pintar_jornadas(self.w, abiertas=[(propia, _avance(), True), (ajena, _avance(), True)], por_revisar=[], code="VEND-4")
        textos = lambda i: [b.text() for b in self.w.conteos_jornadas_box.itemAt(i).widget().findChildren(QPushButton)]  # noqa: E731
        self.assertEqual(textos(0), ["Eliminar", "Seguir"])
        self.assertEqual(textos(1), ["Seguir"])
        next(b for b in self.w.conteos_jornadas_box.itemAt(0).widget().findChildren(QPushButton) if b.text() == "Eliminar").click()
        self.assertEqual(eliminadas, [1])

        # El dueño: reasignar y eliminar en todas.
        tarjetas.pintar_jornadas(self.w, abiertas=[(propia, _avance(), True), (ajena, _avance(), True)], por_revisar=[], code="VEND-1")
        self.assertEqual(textos(0), ["Reasignar", "Eliminar", "Seguir"])
        self.assertEqual(textos(1), ["Reasignar", "Eliminar", "Seguir"])
        next(b for b in self.w.conteos_jornadas_box.itemAt(1).widget().findChildren(QPushButton) if b.text() == "Reasignar").click()
        self.assertEqual(reasignadas, [2])

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

        tabla = QTableWidget(0, 6, self.padre)
        ahora = datetime.now()
        recientes = [
            (_foto(id=1, terminada_at=ahora), _avance(14, 14, 128, 128)),                      # por revisar
            (replace(_foto(id=2, terminada_at=ahora), revisada_at=ahora), _avance()),          # aplicada
            (replace(_foto(id=3, terminada_at=ahora), revisada_at=ahora, aplicada=False), _avance()),  # descartada
        ]
        tarjetas.pintar_historial(tabla, recientes)
        self.assertEqual(tabla.rowCount(), 3)
        self.assertEqual([tabla.item(i, 5).text() for i in range(3)], ["Por revisar", "Aplicada", "Descartada"])
        self.assertEqual(tabla.item(0, 4).text(), "128 de 128")
        tarjetas.pintar_historial(tabla, [])
        self.assertIn("Todavía no hay", tabla.item(0, 0).text())

    def test_el_tablero_pinta_todas_las_escuelas(self) -> None:
        from datetime import timedelta

        from PyQt6.QtWidgets import QTableWidget

        tabla = QTableWidget(0, 6, self.padre)
        ahora = datetime.now()
        filas = [
            jn.FilaTablero("Bicentenario", 3, "", jn.UltimoConteo(None), "", "En proceso", "Fanny Ortiz"),
            jn.FilaTablero("Práxedis Guerrero", 1, "", jn.UltimoConteo(ahora - timedelta(days=1), "Stayce Chavarria"), "94 de 94", "Aplicada", ""),
            jn.FilaTablero("CECYTE", 2, "", jn.UltimoConteo(ahora - timedelta(days=40), ""), "", "Conteo viejo", ""),
            jn.FilaTablero("Básicos · Playera", None, "Playera", jn.UltimoConteo(None), "", "Nunca", ""),
        ]
        tarjetas.pintar_historial(tabla, filas)
        self.assertEqual(tabla.rowCount(), 4)
        self.assertEqual([tabla.item(i, 0).text() for i in range(4)], ["Bicentenario", "Práxedis Guerrero", "CECYTE", "Básicos · Playera"])
        self.assertEqual(tabla.item(0, 5).text(), "En proceso · Fanny Ortiz")
        self.assertEqual((tabla.item(1, 1).text(), tabla.item(1, 3).text(), tabla.item(1, 4).text(), tabla.item(1, 5).text()), ("ayer", "Stayce Chavarria", "94 de 94", "Aplicada"))
        self.assertEqual(tabla.item(2, 1).text(), "hace 1 mes")
        self.assertEqual((tabla.item(3, 1).text(), tabla.item(3, 5).text()), ("nunca", "Nunca"))

    def test_doble_clic_en_el_tablero_abre_el_comparativo(self) -> None:
        from PyQt6.QtWidgets import QTableWidget

        from pos_uniformes.ui.quote_satellite_window import QuoteSatelliteWindow

        tabla = QTableWidget(0, 6, self.padre)
        tarjetas.pintar_historial(tabla, [
            jn.FilaTablero("Práxedis Guerrero", 1, "", jn.UltimoConteo(datetime.now(), "Stayce"), "94 de 94", "Aplicada", "", jornada_id=77),
            jn.FilaTablero("CECYTE", 2, "", jn.UltimoConteo(None), "", "Nunca", ""),
        ])
        self.assertEqual(tabla.item(0, 0).data(Qt.ItemDataRole.UserRole), 77)
        avisos = []
        w = SimpleNamespace(conteos_historial_table=tabla, _set_status=avisos.append)
        with patch("pos_uniformes.ui.dialogs.conteo_jornada_dialogs.ConteoComparativoDialog") as comp:
            QuoteSatelliteWindow._conteos_comparar_fila(w, 0)
            comp.assert_called_once()
            self.assertEqual(comp.call_args.kwargs["jornada_id"], 77)
            QuoteSatelliteWindow._conteos_comparar_fila(w, 1)
            comp.assert_called_once()   # la nunca contada no abre nada
        self.assertTrue(avisos and "todavía" in avisos[0])


class RevisionDialogTests(unittest.TestCase):
    """El dueño ve qué pedir por talla, decide, y aplica o descarta."""

    def setUp(self) -> None:
        from datetime import timedelta

        from pos_uniformes.database.models import LibretaVenta
        from pos_uniformes.services.conteo_service import ConteoInput, registrar_conteos_lote
        from pos_uniformes.tests.test_conteo_jornada_service import _seed

        self._dialogos = []
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.factory = lambda: Session(self.engine)
        s = self.factory()
        e = _seed(s, "Uno")
        s.commit()
        v = list(s.scalars(select(Variante).order_by(Variante.id)).all())
        # La talla 0 se vende: 14 en dos semanas (7/sem → 4 semanas = 28). La 1 no.
        s.add(LibretaVenta(
            employee_code="VEND-4", tipo="venta", piezas=14, monto_total=1400,
            detalle=[{"sku": v[0].sku, "talla": "6", "nombre": "x", "cantidad": 14, "precio": "100", "subtotal": "1400"}],
            created_at=datetime.now() - timedelta(days=14),
        ))
        j = jn.abrir_jornada(s, escuela_id=e.id, empleada_code="VEND-4", empleada_nombre="Stayce")
        registrar_conteos_lote(s, [ConteoInput(v[0].id, 7), ConteoInput(v[1].id, 10)], "x", jornada_id=j.id)
        jn.terminar_jornada(s, j, empleada_code="VEND-4")
        s.commit()
        s.refresh(j)
        self.foto = jn.ref(j)
        self.v_ids = [x.id for x in v]
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

    def _fila(self, d, talla_col_texto: str) -> int:
        for i in range(d._table.rowCount()):
            if d._table.item(i, 1).text().startswith(talla_col_texto):
                return i
        raise AssertionError(f"no está la fila {talla_col_texto}")

    def test_muestra_solo_lo_que_hay_que_pedir_por_defecto(self) -> None:
        # Compacto: fila de prenda + la talla que pide acción. Primero la decisión.
        d = self._dialogo()
        self.assertEqual(d._table.rowCount(), 2)                        # "Prenda 0" + talla 6
        self.assertIn("pedir 21", d._table.item(0, 0).text())           # la prenda resume
        fila = self._fila(d, "6")
        self.assertEqual(d._table.item(fila, 2).text(), "7")            # hay
        self.assertEqual(d._table.item(fila, 3).text(), "pedir 21")     # qué hacer: 28 − 7
        self.assertEqual(d._table.item(fila, 4).text(), "21")           # pedido arranca en lo sugerido
        self.assertIn("Stayce", d._resumen_label.text())
        self.assertIn("<b>21</b> piezas", d._resumen_label.text())
        # Las tarjetas: PEDIR prendida con 1; URGENTE y SURTIR apagadas (no hay); BIEN apagada.
        self.assertTrue(d._tarjetas["PEDIR"].isChecked())
        self.assertEqual(d._tarjetas["PEDIR"]._valor.text(), "1")
        self.assertFalse(d._tarjetas["URGENTE"].isEnabled())
        self.assertFalse(d._tarjetas["OTRAS"].isChecked())
        # Prender BIEN trae la talla 8 ("no se mueve").
        d._tarjetas["OTRAS"].setChecked(True)
        self.assertEqual(d._table.rowCount(), 3)
        self.assertEqual(d._table.item(self._fila(d, "8"), 3).text(), "no se mueve")
        # Ver todas las columnas: la tabla completa de antes, sin filas de prenda.
        d._completo.setChecked(True)
        self.assertEqual(d._table.columnCount(), 13)
        self.assertEqual(d._table.rowCount(), 2)
        self.assertEqual(d._table.item(self._fila(d, "6"), 4).text(), "14 en 14 d")   # vendidas
        self.assertEqual(d._table.item(self._fila(d, "6"), 11).text(), "21")          # pedido

    def test_al_tocar_una_talla_dice_por_que(self) -> None:
        d = self._dialogo()
        self.assertIn("Toca una talla", d._por_que_label.text())
        d._table.selectRow(self._fila(d, "6"))
        self.assertIn("vendidas <b>14</b> en 14 días", d._por_que_label.text())
        self.assertIn("primer conteo", d._por_que_label.text())
        d._table.selectRow(0)   # la fila de prenda no es una talla
        self.assertIn("Toca una talla", d._por_que_label.text())

    def test_si_nada_hay_que_pedir_se_muestran_todas_y_lo_dice(self) -> None:
        from pos_uniformes.database.models import LibretaVenta

        s = self.factory()
        s.query(LibretaVenta).delete()   # sin Libreta: todo "sin datos"
        s.commit(); s.close()
        d = self._dialogo()
        self.assertEqual(d._table.rowCount(), 3)   # prenda + 2 tallas, no una tabla vacía
        self.assertIn("Nada que pedir ni surtir", d._resumen_label.text())
        self.assertEqual(d._table.item(1, 3).text(), "sin datos")
        self.assertTrue(d._tarjetas["OTRAS"].isChecked())

    def test_lo_de_las_cajas_se_ve_y_dice_surtir(self) -> None:
        from pos_uniformes.database.models import BodegaCaja, BodegaContenido

        s = self.factory()
        caja = BodegaCaja(codigo="A-12")
        s.add(caja); s.flush()
        s.add(BodegaContenido(caja_id=caja.id, variante_id=self.v_ids[0], cantidad=30))
        s.commit(); s.close()
        d = self._dialogo()
        fila = self._fila(d, "6")
        # 7/sem; a la mano 7, en cajas 30 → total 37 ≥ 28: no pedir; surtir 14 − 7 = 7.
        self.assertEqual(d._table.item(fila, 2).text(), "7  + 30 en cajas")
        self.assertIn("A-12 ×30", d._table.item(fila, 2).toolTip())
        self.assertEqual(d._table.item(fila, 3).text(), "surtir 7")
        self.assertEqual(d._table.item(fila, 4).text(), "")
        self.assertTrue(d._tarjetas["SURTIR"].isChecked())
        self.assertIn("7 piezas de las cajas", d._tarjetas["SURTIR"]._sub.text())

    def test_editar_pedido_y_guardarlo(self) -> None:
        from pos_uniformes.database.models import ConteoInventario

        d = self._dialogo()
        fila = self._fila(d, "6")
        d._table.item(fila, 4).setText("30")
        self.assertIn("<b>30</b> piezas", d._resumen_label.text())
        d._table.item(fila, 4).setText("abc")   # no es número: vuelve a lo anterior
        self.assertEqual(d._table.item(fila, 4).text(), "30")
        with patch("pos_uniformes.ui.dialogs.conteo_jornada_dialogs.QMessageBox.information"):
            self.assertTrue(d._guardar_pedidos())
        s = self.factory()
        c = s.scalars(select(ConteoInventario).where(ConteoInventario.variante_id == self.v_ids[0])).one()
        self.assertEqual((c.pedido, c.pedido_sugerido), (30, 21))
        # Al reabrir, trae lo decidido.
        d2 = self._dialogo()
        self.assertEqual(d2._table.item(self._fila(d2, "6"), 4).text(), "30")

    def test_la_hoja_de_pedido_lleva_lo_escrito(self) -> None:
        from pos_uniformes.services.revision_service import texto_pedido

        d = self._dialogo()
        d._table.item(self._fila(d, "6"), 4).setText("12")
        texto = texto_pedido(d._revision_con_pedidos())
        self.assertIn("Pedido Uno", texto)
        self.assertIn("6: 12", texto)
        self.assertIn("Total: 12 piezas", texto)

    def test_aplicar_guarda_el_pedido_y_cambia_el_stock(self) -> None:
        from pos_uniformes.database.models import ConteoInventario

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
        c = s.scalars(select(ConteoInventario).where(ConteoInventario.variante_id == self.v_ids[0])).one()
        self.assertEqual(c.pedido, 21)

    def test_doble_clic_en_una_fila_abre_la_historia(self) -> None:
        d = self._dialogo()
        fila = self._fila(d, "6")
        with patch("pos_uniformes.ui.dialogs.conteo_jornada_dialogs.TallaHistoriaDialog") as hist:
            d._doble_clic(d._table.item(fila, 2))      # cualquier columna menos Pedido
            hist.assert_called_once()
            self.assertEqual(hist.call_args.kwargs["variante_id"], self.v_ids[0])
            hist.reset_mock()
            d._doble_clic(d._table.item(fila, 4))      # Pedido: ahí el doble clic edita
            hist.assert_not_called()

    def test_la_historia_muestra_conteos_y_semanas(self) -> None:
        from pos_uniformes.ui.dialogs.conteo_jornada_dialogs import TallaHistoriaDialog

        h = TallaHistoriaDialog(variante_id=self.v_ids[0], titulo="Uno", session_factory=self.factory)
        self._dialogos.append(h)
        self.assertIn("talla 6", h._encabezado.text())
        self.assertIn("<b>14</b> vendidas", h._resumen.text())
        self.assertEqual(h._tabla.rowCount(), 1)
        self.assertEqual(h._tabla.item(0, 1).text(), "7")
        self.assertEqual(h._tabla.item(0, 5).text(), "0")   # el conteo fue después de la venta
        self.assertEqual(len(h._grafica.semanas), 12)
        self.assertEqual(sum(s.vendidas for s in h._grafica.semanas), 14)

    def test_la_historia_de_la_escuela_ordena_lo_que_mas_se_vende(self) -> None:
        from pos_uniformes.ui.dialogs.conteo_jornada_dialogs import EscuelaHistoriaDialog

        h = EscuelaHistoriaDialog(escuela_id=self.foto.escuela_id, session_factory=self.factory)
        self._dialogos.append(h)
        self.assertEqual(h._encabezado.text(), "Uno")
        self.assertIn("<b>14</b> piezas vendidas", h._resumen.text())
        self.assertEqual(h._tabla.rowCount(), 2)                       # solo prendas
        self.assertEqual(h._tabla.item(0, 2).text(), "14")             # la que vende va primero
        self.assertEqual(h._tabla.item(0, 3).text(), "100 %")
        h._solo_prendas.setChecked(True)
        self.assertEqual(h._tabla.rowCount(), 6)                       # 2 prendas + 4 tallas
        self.assertEqual(h._tabla.item(1, 1).text(), "6 AZUL")         # talla 6 es la vendida
        self.assertEqual(h._tabla.item(1, 2).text(), "14")
        # Desde Revisar se abre con un botón.
        d = self._dialogo()
        with patch("pos_uniformes.ui.dialogs.conteo_jornada_dialogs.EscuelaHistoriaDialog") as esc:
            d._historia_escuela()
            esc.assert_called_once()
            self.assertEqual(esc.call_args.kwargs["escuela_id"], self.foto.escuela_id)

    def test_el_comparativo_se_abre_aunque_este_aplicada(self) -> None:
        from pos_uniformes.ui.dialogs.conteo_jornada_dialogs import ConteoComparativoDialog

        # Un conteo anterior de la talla 6 con 20; ahora contaron 7 y se vendieron 14.
        from datetime import timedelta

        from pos_uniformes.database.models import ConteoInventario

        s = self.factory()
        s.add(ConteoInventario(variante_id=self.v_ids[0], escuela_id=self.foto.escuela_id, stock_sistema=0, stock_fisico=20,
                               diferencia=0, contado_por="x", contado_at=datetime.now() - timedelta(days=20)))
        s.commit()
        d = self._dialogo()
        with patch("pos_uniformes.ui.dialogs.conteo_jornada_dialogs.QMessageBox.question", return_value=QMessageBox.StandardButton.Yes), \
             patch("pos_uniformes.ui.dialogs.conteo_jornada_dialogs.QMessageBox.information"):
            d._aplicar()
        self.assertEqual(d.resultado, "aplicada")
        c = ConteoComparativoDialog(jornada_id=self.foto.id, session_factory=self.factory)
        self._dialogos.append(c)
        self.assertIn("Uno", c._encabezado.text())
        self.assertEqual(c._cards["ANTES"]._valor.text(), "20")
        self.assertEqual(c._cards["AHORA"]._valor.text(), "17")     # 7 + 10
        self.assertEqual(c._cards["VENDIDAS"]._valor.text(), "14")
        self.assertEqual(c._cards["SOBRAN"]._valor.text(), "1")     # 20 − 14 − 7 = −1
        self.assertEqual(c._tabla.rowCount(), 1)                    # solo lo que cambió
        self.assertEqual([c._tabla.item(0, i).text() for i in (1, 2, 3, 4, 5, 6)], ["6 AZUL", "20", "7", "-13", "14", "sobran 1"])
        c._solo_cambios.setChecked(False)
        self.assertEqual(c._tabla.rowCount(), 2)
        self.assertEqual(c._tabla.item(1, 4).text(), "primer conteo")
        # Desde Revisar hay botón.
        with patch("pos_uniformes.ui.dialogs.conteo_jornada_dialogs.ConteoComparativoDialog") as comp:
            d._comparar()
            comp.assert_called_once()

    def test_descartar_no_toca_el_stock(self) -> None:
        d = self._dialogo()
        with patch("pos_uniformes.ui.dialogs.conteo_jornada_dialogs.QMessageBox.question",
                   return_value=QMessageBox.StandardButton.Yes):
            d._descartar()
        self.assertEqual(d.resultado, "descartada")
        s = self.factory()
        self.assertEqual(s.scalars(select(Variante)).first().stock_actual, 10)
        self.assertIsNotNone(s.get(ConteoJornada, self.foto.id).revisada_at)

    def test_una_empleada_no_puede_aplicar_ni_pedir(self) -> None:
        d = self._dialogo(quien="VEND-4")
        with patch("pos_uniformes.ui.dialogs.conteo_jornada_dialogs.QMessageBox.question",
                   return_value=QMessageBox.StandardButton.Yes), \
             patch("pos_uniformes.ui.dialogs.conteo_jornada_dialogs.QMessageBox.critical") as err:
            d._aplicar()
        err.assert_called_once()
        self.assertEqual(d.resultado, "")


if __name__ == "__main__":
    unittest.main()


class DestinoDialogTests(unittest.TestCase):
    """Quien imprime decide: carta (HP) o tira (tickets)."""

    def test_carta_y_tira_son_las_dos_salidas(self) -> None:
        from PyQt6.QtWidgets import QPushButton

        from pos_uniformes.ui.dialogs.conteo_jornada_dialogs import ConteoDestinoDialog

        d = ConteoDestinoDialog(titulo="Práxedis Guerrero")
        self.assertEqual(d.destino, "")
        textos = [b.text() for b in d.findChildren(QPushButton)]
        self.assertTrue(any("carta" in t.lower() for t in textos))
        self.assertTrue(any("tira" in t.lower() for t in textos))
        carta = next(b for b in d.findChildren(QPushButton) if "carta" in b.text().lower())
        carta.click()
        self.assertEqual(d.destino, ConteoDestinoDialog.CARTA)
        d.deleteLater()

    def test_la_tira_es_una_opcion_real(self) -> None:
        from PyQt6.QtWidgets import QPushButton

        from pos_uniformes.ui.dialogs.conteo_jornada_dialogs import ConteoDestinoDialog

        d = ConteoDestinoDialog()
        tira = next(b for b in d.findChildren(QPushButton) if "tira" in b.text().lower())
        tira.click()
        self.assertEqual(d.destino, ConteoDestinoDialog.TIRA)
        d.deleteLater()

    def test_la_ventana_manda_la_tira_por_el_camino_de_siempre(self) -> None:
        """La tira usa el mismo generador y la misma salida que el admin."""
        import inspect

        from pos_uniformes.ui.quote_satellite_window import QuoteSatelliteWindow

        fuente = inspect.getsource(QuoteSatelliteWindow._conteos_imprimir_tira)
        self.assertIn("build_conteo_sheets", fuente)
        self.assertIn("open_conteo_print_dialog", fuente)
        fuente_hoja = inspect.getsource(QuoteSatelliteWindow._conteos_imprimir_hoja)
        self.assertIn("ConteoDestinoDialog", fuente_hoja)


class SelectorConFechaTests(unittest.TestCase):
    """El selector del kiosko dice cuándo se contó cada escuela."""

    def setUp(self) -> None:
        from datetime import datetime, timedelta

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.factory = lambda: Session(engine)
        s = self.factory()
        from pos_uniformes.tests.test_conteo_jornada_service import _seed

        a = _seed(s, "Alfa")
        b = _seed(s, "Beta")
        s.commit()
        self.a_id, self.b_id = a.id, b.id   # ids, no objetos: la sesión se cierra
        j = jn.abrir_jornada(s, escuela_id=a.id, empleada_code="VEND-4", empleada_nombre="Stayce Chavarria")
        jn.terminar_jornada(s, j, empleada_code="VEND-4")
        s.commit()
        j.terminada_at = datetime.now() - timedelta(days=2)
        s.commit()
        s.close()
        self._dialogos = []

    def tearDown(self) -> None:
        for d in self._dialogos:
            d.close(); d.deleteLater()
        _APP.processEvents()

    def _dialogo(self):
        from pos_uniformes.ui.dialogs.conteo_jornada_dialogs import ConteoNuevaJornadaDialog

        d = ConteoNuevaJornadaDialog(session_factory=self.factory)
        self._dialogos.append(d)
        return d

    def _textos(self, d):
        return [d._escuela_combo.itemText(i) for i in range(d._escuela_combo.count())]

    def test_las_contadas_hace_poco_no_salen_salvo_ver_todas(self) -> None:
        # Las empleadas pidieron que una escuela ya contada no aparezca en el
        # menú de impresión. Alfa se contó hace 2 días: fuera, hasta "Ver todas".
        d = self._dialogo()
        textos = self._textos(d)
        self.assertFalse(any(t.startswith("Alfa") for t in textos), textos)
        self.assertTrue(any(t.startswith("Beta") and "nunca" in t for t in textos), textos)
        self.assertEqual(d._ocultas_label.text(), "1 escuela contada hace poco no se muestra.")
        d._ver_todas.setChecked(True)
        textos = self._textos(d)
        self.assertTrue(any(t.startswith("Alfa") and "hace 2 días (Stayce)" in t for t in textos), textos)
        self.assertEqual(d._ocultas_label.text(), "")

    def test_avisa_si_fue_hace_poco_y_el_titulo_queda_limpio(self) -> None:
        d = self._dialogo()
        d._ver_todas.setChecked(True)
        idx = next(i for i in range(d._escuela_combo.count()) if d._escuela_combo.itemText(i).startswith("Alfa"))
        d._escuela_combo.setCurrentIndex(idx)
        self.assertIn("Ojo", d._ultimo_label.text())
        d._aceptar()
        self.assertEqual(d.titulo, "Alfa")            # sin la fecha pegada
        self.assertEqual(d.escuela_id, self.a_id)

    def test_nunca_contada_lo_dice_sin_regano(self) -> None:
        d = self._dialogo()
        idx = next(i for i in range(d._escuela_combo.count()) if d._escuela_combo.itemText(i).startswith("Beta"))
        d._escuela_combo.setCurrentIndex(idx)
        self.assertEqual(d._ultimo_label.text(), "Nunca se ha contado.")

    def test_la_que_esta_en_proceso_lo_dice_y_ofrece_seguirla(self) -> None:
        s = self.factory()
        jn.abrir_jornada(s, escuela_id=self.b_id, empleada_code="VEND-5", empleada_nombre="Fanny Ortiz")
        s.commit(); s.close()
        d = self._dialogo()
        d._ver_todas.setChecked(True)   # para que Alfa también esté
        idx = next(i for i in range(d._escuela_combo.count()) if d._escuela_combo.itemText(i).startswith("Beta"))
        self.assertIn("EN PROCESO (Fanny Ortiz)", d._escuela_combo.itemText(idx))
        d._escuela_combo.setCurrentIndex(idx)
        self.assertIn("Fanny Ortiz", d._ultimo_label.text())
        self.assertIn("seguirla", d._ultimo_label.text())
        self.assertEqual(d.abierta_elegida().empleada_code, "VEND-5")
        d._aceptar()
        self.assertEqual(d.titulo, "Beta")
        # Alfa no está en proceso.
        idx = next(i for i in range(d._escuela_combo.count()) if d._escuela_combo.itemText(i).startswith("Alfa"))
        d._escuela_combo.setCurrentIndex(idx)
        self.assertIsNone(d.abierta_elegida())

    def test_la_que_esta_en_proceso_se_ve_aunque_se_haya_contado_hace_poco(self) -> None:
        s = self.factory()
        jn.abrir_jornada(s, escuela_id=self.a_id, empleada_code="VEND-5", empleada_nombre="Fanny Ortiz")
        s.commit(); s.close()
        d = self._dialogo()
        textos = self._textos(d)
        self.assertTrue(any(t.startswith("Alfa") and "EN PROCESO" in t for t in textos), textos)
        self.assertEqual(d._ocultas_label.text(), "")


class SelectorBasicosPorPrendaTests(unittest.TestCase):
    """Básicos: tipo → todas o una sola prenda, cada una con su última fecha."""

    def setUp(self) -> None:
        from pos_uniformes.tests.test_conteo_jornada_service import _seed, _seed_basicos

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.factory = lambda: Session(engine)
        s = self.factory()
        e = _seed(s, "Alfa")
        self.gris, self.azul = _seed_basicos(s, e, "Pantalón")
        s.commit()
        j = jn.abrir_jornada(s, escuela_id=None, tipo_pieza="Pantalón", prenda=self.gris, empleada_code="VEND-4", empleada_nombre="Stayce Chavarria")
        jn.terminar_jornada(s, j, empleada_code="VEND-4")
        s.commit()
        s.close()
        self._dialogos = []

    def tearDown(self) -> None:
        for d in self._dialogos:
            d.close(); d.deleteLater()
        _APP.processEvents()

    def _dialogo(self):
        from pos_uniformes.ui.dialogs.conteo_jornada_dialogs import ConteoNuevaJornadaDialog

        d = ConteoNuevaJornadaDialog(session_factory=self.factory)
        self._dialogos.append(d)
        d._ver_todas.setChecked(True)
        d._escuela_combo.setCurrentIndex(0)   # básicos
        return d

    def test_tipo_y_prendas_con_su_fecha(self) -> None:
        d = self._dialogo()
        tipos = [d._tipo_combo.itemText(i) for i in range(d._tipo_combo.count())]
        self.assertTrue(any(t.startswith("Pantalón") and "hoy (Stayce)" in t for t in tipos), tipos)
        prendas = [d._prenda_combo.itemText(i) for i in range(d._prenda_combo.count())]
        self.assertEqual(len(prendas), 3)   # todas + 2
        self.assertTrue(prendas[0].startswith("Todas las de Pantalón"))
        self.assertTrue(any(p.startswith("Pantalón Gris Escolar") and "hoy (Stayce)" in p for p in prendas), prendas)
        self.assertTrue(any(p.startswith("Pantalón Azul Escolar") and "nunca" in p for p in prendas), prendas)

    def test_elegir_una_prenda_la_lleva_al_resultado(self) -> None:
        d = self._dialogo()
        idx = next(i for i in range(d._prenda_combo.count()) if d._prenda_combo.itemData(i) == self.azul)
        d._prenda_combo.setCurrentIndex(idx)
        self.assertEqual(d._ultimo_label.text(), "Nunca se ha contado.")
        d._aceptar()
        self.assertEqual((d.escuela_id, d.tipo_pieza, d.prenda, d.titulo), (None, "Pantalón", self.azul, "Básicos · Pantalón Azul Escolar"))

    def test_todas_las_del_tipo_deja_prenda_vacia(self) -> None:
        d = self._dialogo()
        d._prenda_combo.setCurrentIndex(0)
        self.assertIn("Ojo", d._ultimo_label.text())   # el tipo se contó hoy (una prenda)
        d._aceptar()
        self.assertEqual((d.prenda, d.titulo), ("", "Básicos · Pantalón"))


class OfrecerSeguirTests(unittest.TestCase):
    """En el kiosko, elegir una escuela ya abierta ofrece seguirla o imprimir otra hoja."""

    def _ventana(self):
        from pos_uniformes.ui.quote_satellite_window import QuoteSatelliteWindow

        return SimpleNamespace(
            capturadas=[], hojas=[],
            _conteos_capturar=lambda self_, foto: self_.capturadas.append(foto),
            _conteos_imprimir_hoja=lambda self_, **kw: self_.hojas.append(kw),
            _conteos_ofrecer_seguir=QuoteSatelliteWindow._conteos_ofrecer_seguir,
        )

    def _correr(self, boton_texto: str):
        from unittest.mock import MagicMock

        w = self._ventana()
        w._conteos_capturar = w._conteos_capturar.__get__(w)
        w._conteos_imprimir_hoja = w._conteos_imprimir_hoja.__get__(w)
        foto = _foto(escuela_id=7, titulo="Beta", empleada_nombre="Fanny")
        botones = {}
        caja = MagicMock()
        caja.addButton.side_effect = lambda texto, *a: botones.setdefault(texto, object()) if isinstance(texto, str) else object()
        caja.clickedButton.side_effect = lambda: botones.get(boton_texto)
        with patch("pos_uniformes.ui.quote_satellite_window.QMessageBox", return_value=caja):
            w._conteos_ofrecer_seguir(w, foto)
        return w, foto

    def test_seguirla_abre_la_captura_en_esa_jornada(self) -> None:
        w, foto = self._correr("Seguirla")
        self.assertEqual(w.capturadas, [foto])
        self.assertEqual(w.hojas, [])

    def test_otra_hoja_imprime_sin_volver_a_preguntar(self) -> None:
        w, foto = self._correr("Imprimir otra hoja")
        self.assertEqual(w.capturadas, [])
        self.assertEqual(w.hojas, [{"escuela_id": 7, "tipo_pieza": "", "titulo": "Beta", "prenda": ""}])

    def test_cancelar_no_hace_nada(self) -> None:
        w, _ = self._correr("Cancelar")
        self.assertEqual((w.capturadas, w.hojas), ([], []))


class ImprimirDejaHuellaTests(unittest.TestCase):
    """Imprimir la hoja abre la jornada (o se pega a la abierta) y, si ya
    había una, avisa fuerte antes de gastar papel (2026-09-18)."""

    def _ventana(self):
        from pos_uniformes.ui.quote_satellite_window import QuoteSatelliteWindow

        w = SimpleNamespace(estados=[], refrescos=0, _conteos_code="VEND-3", _conteos_nombre="Ana")
        w._set_status = lambda t: w.estados.append(t)
        w._refresh_conteos_vista = lambda: setattr(w, "refrescos", w.refrescos + 1)
        for m in ("_conteos_confirmar_otra_hoja", "_conteos_anotar_impresion"):
            setattr(w, m, getattr(QuoteSatelliteWindow, m).__get__(w))
        return w

    def test_la_hoja_impresa_abre_la_jornada_a_nombre_de_quien_imprimio(self) -> None:
        w = self._ventana()
        jornada = SimpleNamespace(titulo="Beta", empleada_nombre="Ana", empleada_code="VEND-3")
        llamadas = []
        with patch("pos_uniformes.services.conteo_jornada_service.registrar_impresion", side_effect=lambda s, **kw: (llamadas.append(kw), (jornada, False))[1]), patch(
            "pos_uniformes.ui.quote_satellite_window.get_session"
        ):
            w._conteos_anotar_impresion(7, "", "")
        self.assertEqual(llamadas[0]["empleada_code"], "VEND-3")
        self.assertEqual(llamadas[0]["escuela_id"], 7)
        self.assertIn("queda en proceso a nombre de Ana", w.estados[-1])
        self.assertEqual(w.refrescos, 1)

    def test_si_ya_habia_jornada_la_hoja_se_anota_ahi(self) -> None:
        w = self._ventana()
        jornada = SimpleNamespace(titulo="Beta", empleada_nombre="Fanny", empleada_code="VEND-5")
        with patch("pos_uniformes.services.conteo_jornada_service.registrar_impresion", return_value=(jornada, True)), patch(
            "pos_uniformes.ui.quote_satellite_window.get_session"
        ):
            w._conteos_anotar_impresion(7, "", "")
        self.assertIn("otra hoja para la jornada de Fanny", w.estados[-1])

    def test_el_aviso_dice_quien_y_cuando_y_por_defecto_no_imprime(self) -> None:
        from datetime import datetime
        from unittest.mock import MagicMock

        w = self._ventana()
        foto = _foto(escuela_id=7, titulo="Beta", empleada_nombre="Fanny")
        foto = foto.__class__(**{**foto.__dict__, "hojas_impresas": 1, "impresa_at": datetime(2026, 9, 18, 10, 32)})
        botones = {}
        caja = MagicMock()
        caja.addButton.side_effect = lambda texto, *a: botones.setdefault(texto, object())
        caja.buttons.return_value = [object(), botones.get("No imprimir")]
        caja.clickedButton.side_effect = lambda: botones.get("No imprimir")
        with patch("pos_uniformes.ui.quote_satellite_window.QMessageBox", return_value=caja):
            self.assertFalse(w._conteos_confirmar_otra_hoja(foto))
        texto = caja.setText.call_args.args[0]
        self.assertIn("Fanny", texto)
        self.assertIn("hoja impresa 10:32", texto)
        caja.clickedButton.side_effect = lambda: botones.get("Sí, imprimir otra hoja")
        with patch("pos_uniformes.ui.quote_satellite_window.QMessageBox", return_value=caja):
            self.assertTrue(w._conteos_confirmar_otra_hoja(foto))

    def test_imprimir_pide_gafete_y_pregunta_si_ya_esta_abierta(self) -> None:
        import inspect

        from pos_uniformes.ui.quote_satellite_window import QuoteSatelliteWindow

        fuente = inspect.getsource(QuoteSatelliteWindow._conteos_imprimir_hoja)
        self.assertIn("_conteos_contado_por() is None", fuente)
        self.assertIn("_conteos_confirmar_otra_hoja(abierta)", fuente)
        self.assertEqual(fuente.count("_conteos_anotar_impresion("), 2)   # carta y tira


class PorRevisarDeAPocasTests(unittest.TestCase):
    """35 tarjetas de golpe eran una pared: se pintan 8 y las demás detrás de
    "ver las otras N" (2026-09-22)."""

    def setUp(self) -> None:
        self.padre = QWidget()
        self.w = SimpleNamespace(
            conteos_jornadas_box=QVBoxLayout(), conteos_revisar_box=QVBoxLayout(),
            conteos_revisar_titulo=QLabel(self.padre), conteos_quien_label=QLabel(self.padre),
            conteos_jornadas_titulo=QLabel(self.padre), conteos_jornadas_panel=QLabel(self.padre),
            conteos_revisar_panel=QLabel(self.padre),
            _conteos_capturar=lambda f: None, _conteos_revisar=lambda f: None,
        )

    def tearDown(self) -> None:
        self.padre.deleteLater()
        _APP.processEvents()

    def test_muestra_ocho_y_el_resto_tras_un_boton(self) -> None:
        from PyQt6.QtWidgets import QPushButton

        pendientes = [(_foto(id=i), _avance()) for i in range(12)]
        tarjetas.pintar_jornadas(self.w, abiertas=[], por_revisar=pendientes, code="VEND-1")
        self.assertEqual(self.w.conteos_revisar_box.count(), 9)   # 8 tarjetas + el botón
        boton = self.w.conteos_revisar_box.itemAt(8).widget()
        self.assertIsInstance(boton, QPushButton)
        self.assertIn("ver las otras 4", boton.text())
        boton.click()
        self.assertEqual(self.w.conteos_revisar_box.count(), 12)  # ya sin botón

    def test_con_pocas_no_hay_boton(self) -> None:
        tarjetas.pintar_jornadas(self.w, abiertas=[], por_revisar=[(_foto(), _avance())], code="VEND-1")
        self.assertEqual(self.w.conteos_revisar_box.count(), 1)
