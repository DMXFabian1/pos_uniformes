"""Las tarjetas de jornada y los diálogos de empezar / revisar."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone
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
from pos_uniformes.services import conteo_revision_pantalla_service as _P  # noqa: E402
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
    """El dueño ve qué cambia, decide qué pedir, y corrige o no usa el conteo."""

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
        # Talla 6: el sistema decía 10 y contaron 7 (−3). Talla 8: cuadra (10).
        registrar_conteos_lote(s, [ConteoInput(v[0].id, 7), ConteoInput(v[1].id, 10)], "x", jornada_id=j.id)
        jn.terminar_jornada(s, j, empleada_code="VEND-4")
        s.commit()
        s.refresh(j)
        self.foto = jn.ref(j)
        self.v_ids = [x.id for x in v]
        s.close()

    def _dialogo(self, quien="VEND-1", **kw):
        from pos_uniformes.ui.dialogs.conteo_jornada_dialogs import ConteoRevisionDialog

        d = ConteoRevisionDialog(jornada=self.foto, revisada_por=quien, session_factory=self.factory, **kw)
        self._dialogos.append(d)
        return d

    def tearDown(self) -> None:
        for d in self._dialogos:
            d.close()
            d.deleteLater()
        self._dialogos = []
        _APP.processEvents()

    def _fila(self, d, talla: str) -> int:
        for i in d._por_fila:
            if d._table.item(i, _P.COL_TALLA).text() == talla:
                return i
        raise AssertionError(f"no está la fila {talla}")

    def _celda(self, d, talla: str, col: int) -> str:
        return d._table.item(self._fila(d, talla), col).text()

    def _otra_por_revisar(self) -> int:
        """Otra jornada terminada y sin revisar (de otra escuela)."""
        from pos_uniformes.services.conteo_service import ConteoInput, registrar_conteos_lote
        from pos_uniformes.tests.test_conteo_jornada_service import _seed

        s = self.factory()
        e = _seed(s, "Dos", productos=1, tallas=("10",))
        s.flush()
        v = s.scalars(select(Variante).where(Variante.sku == "SDos010")).one()
        j = jn.abrir_jornada(s, escuela_id=e.id, empleada_code="VEND-5", empleada_nombre="Fanny")
        registrar_conteos_lote(s, [ConteoInput(v.id, 9)], "x", jornada_id=j.id)
        jn.terminar_jornada(s, j, empleada_code="VEND-5")
        s.commit()
        jid = j.id
        s.close()
        return jid

    # --- tanda 3 (2026-11-15): la pantalla nueva --------------------------------------
    def test_la_tabla_trae_las_tallas_con_diferencia_primero(self) -> None:
        # Reescrita (antes: test_muestra_solo_lo_que_hay_que_pedir_por_defecto, con tarjetas).
        d = self._dialogo()
        self.assertEqual(d._table.columnCount(), 8)
        self.assertEqual(d.COL_PEDIDO, 7)
        self.assertEqual(d._table.rowCount(), 3)                        # 6 · «sin diferencia (1)» · 8
        self.assertEqual(d._table.item(1, 0).text(), "— sin diferencia (1) —")
        fila = [self._celda(d, "6", c) for c in range(8)]
        # talla · el sistema decía · contó · dif · vendidas desde · queda hoy · qué hacer · pedir
        self.assertEqual(fila, ["6", "10", "7", "−3", "0", "7", "pedir 21", "21"])
        self.assertEqual(self._celda(d, "8", _P.COL_DIF), "·")
        self.assertEqual(self._celda(d, "8", _P.COL_QUE), "no se mueve")
        self.assertIn("<b>21</b> piezas", d._resumen_label.text())
        # Sin columna Prenda ni color repetido: la prenda va arriba, una vez.
        self.assertEqual(d._titulo_label.text(), "Prenda 0 · Azul · Uno")
        self.assertIn("Contó Stayce · ", d._cuando_label.text())
        self.assertTrue(d._cuando_label.text().endswith("· 2 tallas"))
        self.assertEqual(d._aplicar_btn.text(), "Corregir inventario (1 talla, −3 pz)")

    def test_los_chips_filtran_y_otro_toque_quita_el_filtro(self) -> None:
        # Reescrita (antes: las tarjetas URGENTE/PEDIR/SURTIR/OTRAS).
        d = self._dialogo()
        ajuste, urgente, pedir = d._chips["AJUSTE"], d._chips["URGENTE"], d._chips["PEDIR"]
        self.assertEqual(ajuste.text(), "Corrige 1 talla · faltan 3 · sobran 0 · −$300")
        self.assertEqual((pedir.text(), pedir.property("tono")), ("Pedir 1", "advertencia"))
        self.assertFalse(urgente.isEnabled())
        self.assertEqual(urgente.property("tono"), "cero")
        pedir.click()
        self.assertEqual(d._table.rowCount(), 1)
        self.assertEqual(pedir.property("activo"), "si")
        pedir.click()
        self.assertEqual(d._table.rowCount(), 3)
        ajuste.click()
        self.assertEqual([d._table.item(i, 0).text() for i in range(d._table.rowCount())], ["6"])

    def test_en_su_orden_quita_el_separador(self) -> None:
        d = self._dialogo()
        self.assertEqual(d._orden_btn.text(), "↕ En su orden")
        d._orden_btn.click()
        self.assertEqual([d._table.item(i, 0).text() for i in range(d._table.rowCount())], ["6", "8"])
        self.assertEqual(d._orden_btn.text(), "↕ Diferencias primero")

    def test_ver_todas_las_columnas_es_un_dialogo_aparte(self) -> None:
        from pos_uniformes.ui.dialogs.conteo_jornada_dialogs import ConteoColumnasDialog

        d = self._dialogo()
        with patch.object(ConteoColumnasDialog, "exec"):
            d._accion_todas.trigger()
        t = d._todas_dlg._tabla
        self._dialogos.append(d._todas_dlg)
        self.assertEqual(t.columnCount(), 17)
        self.assertEqual(t.rowCount(), 2)
        encabezados = [t.horizontalHeaderItem(c).text() for c in range(17)]
        fila = {encabezados[c]: t.item(0, c).text() for c in range(17)}
        self.assertEqual((fila["Talla"], fila["Vendidas"], fila["Pedido"], fila["Dif"]), ("6 Azul", "14 en 14 d", "21", "−3"))
        self.assertEqual(d._table.columnCount(), 8)      # la de Revisar no cambia

    def test_al_tocar_una_talla_dice_por_que(self) -> None:
        d = self._dialogo()
        self.assertIn("Toca una talla", d._por_que_label.text())
        d._table.selectRow(self._fila(d, "6"))
        self.assertIn("Talla 6", d._por_que_label.text())
        self.assertIn("vendidas <b>14</b> en 14 días", d._por_que_label.text())
        self.assertIn("primer conteo", d._por_que_label.text())
        d._table.clearSelection()
        self.assertIn("Toca una talla", d._por_que_label.text())

    def test_si_nada_hay_que_pedir_se_muestran_todas_y_lo_dice(self) -> None:
        from pos_uniformes.database.models import LibretaVenta

        s = self.factory()
        s.query(LibretaVenta).delete()   # sin Libreta: todo "sin datos"
        s.commit(); s.close()
        d = self._dialogo()
        self.assertEqual(d._table.rowCount(), 3)   # 6 · separador · 8, no una tabla vacía
        self.assertIn("Nada que pedir ni surtir", d._resumen_label.text())
        self.assertEqual(self._celda(d, "8", _P.COL_QUE), "sin datos")
        self.assertIsNone(d._filtro)
        self.assertFalse(d._chips["PEDIR"].isEnabled())

    def test_lo_de_las_cajas_se_ve_en_gris_con_su_nota(self) -> None:
        # Reescrita (antes: test_lo_de_las_cajas_se_ve_y_dice_surtir, con la tarjeta SURTIR).
        from pos_uniformes.database.models import BodegaCaja, BodegaContenido

        s = self.factory()
        caja = BodegaCaja(codigo="A-12")
        s.add(caja); s.flush()
        s.add(BodegaContenido(caja_id=caja.id, variante_id=self.v_ids[0], cantidad=30))
        s.commit(); s.close()
        d = self._dialogo()
        # 7/sem; a la mano 7, en cajas 30 → total 37 ≥ 28: no pedir; surtir 14 − 7 = 7.
        self.assertEqual(self._celda(d, "6", _P.COL_CONTO), "7")
        self.assertEqual(self._celda(d, "6", _P.COL_QUE), "surtir 7 de cajas*")
        ayuda = d._table.item(self._fila(d, "6"), _P.COL_QUE).toolTip()
        self.assertIn("A-12 ×30", ayuda)
        self.assertIn("sin recontar desde el 16-jul", ayuda)
        self.assertEqual(self._celda(d, "6", _P.COL_PEDIDO), "")
        surtir = d._chips["SURTIR"]
        self.assertEqual((surtir.text(), surtir.property("tono")), ("Surtir 1*", "neutro"))   # gris, no se prende
        self.assertIn("16-jul", surtir.toolTip())
        self.assertFalse(d._nota_cajas.isHidden())

    def test_editar_pedido_y_guardarlo(self) -> None:
        from pos_uniformes.database.models import ConteoInventario

        d = self._dialogo()
        fila = self._fila(d, "6")
        d._table.item(fila, d.COL_PEDIDO).setText("30")
        self.assertIn("<b>30</b> piezas", d._resumen_label.text())
        d._table.item(fila, d.COL_PEDIDO).setText("abc")   # no es número: vuelve a lo anterior
        self.assertEqual(d._table.item(fila, d.COL_PEDIDO).text(), "30")
        with patch("pos_uniformes.ui.dialogs.conteo_jornada_dialogs.QMessageBox.information"):
            self.assertTrue(d._guardar_pedidos())
        s = self.factory()
        c = s.scalars(select(ConteoInventario).where(ConteoInventario.variante_id == self.v_ids[0])).one()
        self.assertEqual((c.pedido, c.pedido_sugerido), (30, 21))
        # Al reabrir, trae lo decidido.
        d2 = self._dialogo()
        self.assertEqual(self._celda(d2, "6", d2.COL_PEDIDO), "30")

    def test_un_toque_en_pedir_abre_la_cajita(self) -> None:
        from PyQt6.QtWidgets import QAbstractItemView

        d = self._dialogo()
        d.show(); _APP.processEvents()
        d._table.cellClicked.emit(self._fila(d, "6"), d.COL_PEDIDO)
        self.assertEqual(d._table.state(), QAbstractItemView.State.EditingState)
        d._cerrar_editor_abierto()
        d._table.cellClicked.emit(self._fila(d, "6"), _P.COL_QUE)
        self.assertNotEqual(d._table.state(), QAbstractItemView.State.EditingState)
        d.hide()

    def test_la_hoja_de_pedido_lleva_lo_escrito_y_lo_guarda(self) -> None:
        from pos_uniformes.database.models import ConteoInventario
        from pos_uniformes.services.revision_service import texto_pedido

        d = self._dialogo()
        d._table.item(self._fila(d, "6"), d.COL_PEDIDO).setText("12")
        texto = texto_pedido(d._revision_con_pedidos())
        self.assertIn("Pedido Uno", texto)
        self.assertIn("6: 12", texto)
        self.assertIn("Total: 12 piezas", texto)
        # Ya no hay «Guardar pedido»: abrir la hoja lo guarda.
        with patch(f"{_D}.PedidoHojaDialog") as hoja:
            d._hoja_de_pedido()
        hoja.assert_called_once()
        s = self.factory()
        c = s.scalars(select(ConteoInventario).where(ConteoInventario.variante_id == self.v_ids[0])).one()
        self.assertEqual(c.pedido, 12)
        self.assertFalse(d._pedido_cambiado())

    def test_hoja_de_pedido_solo_si_hay_algo_pedido(self) -> None:
        d = self._dialogo()
        self.assertFalse(d._hoja_btn.isHidden())
        d._table.item(self._fila(d, "6"), d.COL_PEDIDO).setText("")
        self.assertTrue(d._hoja_btn.isHidden())

    def test_aplicar_guarda_el_pedido_y_cambia_el_stock(self) -> None:
        from pos_uniformes.database.models import ConteoInventario

        d = self._dialogo()
        with patch("pos_uniformes.ui.dialogs.conteo_jornada_dialogs._elegir", return_value="si"):
            d._aplicar()
        self.assertEqual(d.resultado, "aplicada")
        s = self.factory()
        v = list(s.scalars(select(Variante).order_by(Variante.id)).all())
        self.assertEqual(v[0].stock_actual, 7)
        self.assertEqual(v[1].stock_actual, 10)
        self.assertIsNotNone(s.get(ConteoJornada, self.foto.id).revisada_at)
        c = s.scalars(select(ConteoInventario).where(ConteoInventario.variante_id == self.v_ids[0])).one()
        self.assertEqual(c.pedido, 21)
        # «✓ Listo» en la misma ventana; no hay otra por revisar: solo Cerrar.
        self.assertEqual(d._paginas.currentIndex(), 1)
        self.assertEqual(d._listo_texto.text(), "Se corrigió 1 talla: faltaban 3, sobraban 0 (−$300 a precio de venta).")
        self.assertTrue(d._siguiente_btn.isHidden())
        self.assertEqual(d._listo_quedan.text(), "No queda ningún conteo por revisar.")
        d._cerrar_btn.click()
        self.assertIsNone(d.siguiente_jornada_id)

    def test_listo_ofrece_la_siguiente_por_revisar(self) -> None:
        otra = self._otra_por_revisar()
        d = self._dialogo()
        d.show(); _APP.processEvents()
        with patch(f"{_D}._elegir", return_value="si"):
            d._descartar()
        self.assertEqual(d.resultado, "descartada")
        self.assertEqual(d._paginas.currentIndex(), 1)
        self.assertIn("No se usó este conteo", d._listo_texto.text())
        self.assertFalse(d._siguiente_btn.isHidden())
        self.assertIn("Queda 1 conteo por revisar. Sigue: Dos (Fanny).", d._listo_quedan.text())
        d._siguiente_btn.click()
        self.assertEqual(d.siguiente_jornada_id, otra)
        self.assertEqual(d.siguiente_jornada.id, otra)
        self.assertFalse(d.isVisible())

    def _no_usar_con_pedido_escrito(self):
        """Escribe 30 en PEDIR de la talla 6 y elige «No usar»: queda en «✓ Listo»."""
        d = self._dialogo()
        d.show(); _APP.processEvents()
        d._table.item(self._fila(d, "6"), d.COL_PEDIDO).setText("30")
        with patch(f"{_D}._elegir", return_value="si"):
            d._descartar()
        self.assertEqual(d._paginas.currentIndex(), 1)
        return d

    def _pedido_de_la_6(self):
        from pos_uniformes.database.models import ConteoInventario

        s = self.factory()
        try:
            return s.scalars(select(ConteoInventario).where(ConteoInventario.variante_id == self.v_ids[0])).one().pedido
        finally:
            s.close()

    def test_no_usar_y_cerrar_desde_listo_pregunta_por_el_pedido(self) -> None:
        # «No usar» no guarda el pedido: [Cerrar] del «✓ Listo» pregunta como la ✕.
        d = self._no_usar_con_pedido_escrito()
        with patch(f"{_D}._elegir", return_value="volver") as preg:
            d._cerrar_btn.click()
        self.assertEqual(preg.call_args.args[2], "Cambiaste el pedido y no lo guardaste.")
        self.assertTrue(d.isVisible())                       # Volver: sigue en «Listo»
        with patch(f"{_D}._elegir", return_value="guardar"):
            d._cerrar_btn.click()
        self.assertFalse(d.isVisible())
        self.assertEqual(self._pedido_de_la_6(), 30)

    def test_no_usar_y_siguiente_tambien_pregunta_por_el_pedido(self) -> None:
        otra = self._otra_por_revisar()
        d = self._no_usar_con_pedido_escrito()
        with patch(f"{_D}._elegir", return_value="volver"):
            d._siguiente_btn.click()
        self.assertIsNone(d.siguiente_jornada_id)            # Volver: no se va a la siguiente
        self.assertTrue(d.isVisible())
        with patch(f"{_D}._elegir", return_value="guardar") as preg:
            d._siguiente_btn.click()
        preg.assert_called_once()
        self.assertEqual(d.siguiente_jornada_id, otra)
        self.assertEqual(self._pedido_de_la_6(), 30)

    def test_no_usar_y_no_guardar_sale_sin_el_pedido(self) -> None:
        d = self._no_usar_con_pedido_escrito()
        with patch(f"{_D}._elegir", return_value="no_guardar"):
            d._cerrar_btn.click()
        self.assertFalse(d.isVisible())
        self.assertIsNone(self._pedido_de_la_6())

    def test_desde_el_historial_no_se_ofrece_la_siguiente(self) -> None:
        self._otra_por_revisar()
        d = self._dialogo(ofrecer_siguiente=False)
        with patch(f"{_D}._elegir", return_value="si"):
            d._descartar()
        self.assertTrue(d._siguiente_btn.isHidden())
        self.assertTrue(d._listo_quedan.isHidden())

    def test_el_kiosko_abre_la_siguiente_por_revisar(self) -> None:
        from pos_uniformes.ui.quote_satellite_window import QuoteSatelliteWindow

        otra = _foto(id=2, titulo="Dos")
        abiertas = []

        class _Falsa:
            def __init__(self, _padre, *, jornada, revisada_por):
                abiertas.append((jornada.id, revisada_por))
                self.siguiente_jornada = otra if jornada.id == 1 else None

            def exec(self):
                return 1

        w = SimpleNamespace(
            _conteos_code="VEND-1", _set_status=lambda *_: None,
            _refresh_conteo_banner=lambda: None, _refresh_conteos_vista=lambda: None,
        )
        with patch(f"{_D}.ConteoRevisionDialog", _Falsa):
            QuoteSatelliteWindow._conteos_revisar(w, _foto(id=1))
        self.assertEqual(abiertas, [(1, "VEND-1"), (2, "VEND-1")])

    def test_el_kiosko_no_reabre_una_jornada_ya_vista(self) -> None:
        # Si la 2 ofreciera otra vez la 1 (1 → 2 → 1), el kiosko se detiene: sin ciclo.
        from pos_uniformes.ui.quote_satellite_window import QuoteSatelliteWindow

        fotos = {1: _foto(id=1), 2: _foto(id=2, titulo="Dos")}
        abiertas = []

        class _Falsa:
            def __init__(self, _padre, *, jornada, revisada_por):
                abiertas.append(jornada.id)
                self.siguiente_jornada = fotos[2 if jornada.id == 1 else 1]

            def exec(self):
                if len(abiertas) > 5:
                    raise AssertionError("ciclo: reabre jornadas ya vistas")
                return 1

        w = SimpleNamespace(
            _conteos_code="VEND-1", _set_status=lambda *_: None,
            _refresh_conteo_banner=lambda: None, _refresh_conteos_vista=lambda: None,
        )
        with patch(f"{_D}.ConteoRevisionDialog", _Falsa):
            QuoteSatelliteWindow._conteos_revisar(w, fotos[1])
        self.assertEqual(abiertas, [1, 2])

    def _jornada_de_dos_prendas(self):
        """«Tres»: Prenda 0 (6 y 8) y Prenda 1 (6 y 8). La 8 de Prenda 1 se vende
        (PEDIR) y la 6 de Prenda 0 tiene diferencia (−2)."""
        from datetime import timedelta

        from pos_uniformes.database.models import LibretaVenta
        from pos_uniformes.services.conteo_service import ConteoInput, registrar_conteos_lote
        from pos_uniformes.tests.test_conteo_jornada_service import _seed

        s = self.factory()
        e = _seed(s, "Tres")
        s.flush()
        v = {x.sku: x for x in s.scalars(select(Variante).where(Variante.sku.like("STres%"))).all()}
        s.add(LibretaVenta(
            employee_code="VEND-4", tipo="venta", piezas=14, monto_total=1400,
            detalle=[{"sku": "STres18", "talla": "8", "nombre": "x", "cantidad": 14, "precio": "100", "subtotal": "1400"}],
            created_at=datetime.now() - timedelta(days=14),
        ))
        j = jn.abrir_jornada(s, escuela_id=e.id, empleada_code="VEND-4", empleada_nombre="Stayce")
        registrar_conteos_lote(s, [
            ConteoInput(v["STres06"].id, 8), ConteoInput(v["STres08"].id, 10),
            ConteoInput(v["STres16"].id, 10), ConteoInput(v["STres18"].id, 10),
        ], "x", jornada_id=j.id)
        jn.terminar_jornada(s, j, empleada_code="VEND-4")
        s.commit()
        s.refresh(j)
        foto = jn.ref(j)
        ids = {sku: x.id for sku, x in v.items()}
        s.close()
        return foto, ids

    def test_varias_prendas_pinta_filas_de_grupo_y_pedir_va_al_conteo_correcto(self) -> None:
        from pos_uniformes.ui.dialogs.conteo_jornada_dialogs import ConteoRevisionDialog

        foto, _ids = self._jornada_de_dos_prendas()
        d = ConteoRevisionDialog(jornada=foto, revisada_por="VEND-1", session_factory=self.factory)
        self._dialogos.append(d)
        grupos = [f for f in range(d._table.rowCount()) if d._table.columnSpan(f, 0) == d._table.columnCount()]
        textos = [d._table.item(f, 0).text() for f in grupos]
        self.assertTrue(textos[0].startswith("Prenda 0 · Azul   —   1 con diferencia"), textos)
        self.assertTrue(any(t.startswith("Prenda 1 · Azul") and "pedir" in t for t in textos), textos)
        # Las filas de grupo y los separadores no son tallas: no están en _por_fila.
        self.assertFalse(set(grupos) & set(d._por_fila))
        self.assertEqual(len(d._por_fila), 4)
        # Con el chip Pedir prendido queda la Prenda 1 (su grupo y la 8); PEDIR va a su conteo.
        d._tocar_chip("PEDIR")
        self.assertEqual(d._table.columnSpan(0, 0), d._table.columnCount())
        self.assertEqual(list(d._por_fila), [1])
        cid = d._por_fila[1]
        linea = next(l for l in d._revision.lineas if l.conteo_id == cid)
        self.assertEqual((linea.producto.split(" | ")[0], linea.talla), ("Prenda 1 Tres", "8"))
        d._table.item(1, d.COL_PEDIDO).setText("0")
        self.assertEqual(d._pedidos[cid], 0)
        # El grupo deja de decir «pedir N»: dice lo escrito, no lo sugerido.
        self.assertNotIn("pedir", d._table.item(0, 0).text())
        d._table.item(1, d.COL_PEDIDO).setText("9")
        self.assertIn("pedir 9", d._table.item(0, 0).text())

    def test_la_fila_elegida_conserva_el_color_de_su_letra(self) -> None:
        # La hoja de estilo pintaba lo elegido en negro: se perdía el rojo de la diferencia.
        from PyQt6.QtGui import QPalette
        from PyQt6.QtWidgets import QStyleOptionViewItem

        from pos_uniformes.ui.styles import conteo_revision_styles as cr

        d = self._dialogo()
        fila = self._fila(d, "6")
        d._table.selectRow(fila)
        opcion = QStyleOptionViewItem()
        d._table.itemDelegate().initStyleOption(opcion, d._table.model().index(fila, _P.COL_DIF))
        self.assertEqual(opcion.palette.color(QPalette.ColorRole.HighlightedText).name(), cr.ROJO)
        self.assertNotIn("selection-color", cr.build_conteo_revision_stylesheet())

    def test_doble_clic_ya_no_abre_la_historia_y_consultar_si(self) -> None:
        # Reescrita (antes: test_doble_clic_en_una_fila_abre_la_historia): el doble
        # clic deja escribir en PEDIR; la historia está en «Consultar ▾».
        d = self._dialogo()
        fila = self._fila(d, "6")
        with patch("pos_uniformes.ui.dialogs.conteo_jornada_dialogs.TallaHistoriaDialog") as hist:
            d._table.itemDoubleClicked.emit(d._table.item(fila, _P.COL_CONTO))
            hist.assert_not_called()
            d._table.selectRow(fila)
            d._accion_historia.trigger()
            hist.assert_called_once()
            self.assertEqual(hist.call_args.kwargs["variante_id"], self.v_ids[0])
        textos = [a.text() for a in d._menu_consultar.actions() if not a.isSeparator()]
        self.assertEqual(
            [t.split("  ", 1)[-1] for t in textos],
            ["Historia de la talla", "Historia de la escuela", "Comparar con el anterior", "Ver todas las columnas"],
        )

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
        # Desde Revisar se abre con «Consultar ▾».
        d = self._dialogo()
        with patch("pos_uniformes.ui.dialogs.conteo_jornada_dialogs.EscuelaHistoriaDialog") as esc:
            d._accion_escuela.trigger()
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
        with patch("pos_uniformes.ui.dialogs.conteo_jornada_dialogs._elegir", return_value="si"):
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
        # Desde Revisar, en «Consultar ▾».
        with patch("pos_uniformes.ui.dialogs.conteo_jornada_dialogs.ConteoComparativoDialog") as comp:
            d._accion_comparar.trigger()
            comp.assert_called_once()

    def test_descartar_no_toca_el_stock(self) -> None:
        d = self._dialogo()
        with patch("pos_uniformes.ui.dialogs.conteo_jornada_dialogs._elegir", return_value="si"):
            d._descartar()
        self.assertEqual(d.resultado, "descartada")
        s = self.factory()
        self.assertEqual(s.scalars(select(Variante)).first().stock_actual, 10)
        self.assertIsNotNone(s.get(ConteoJornada, self.foto.id).revisada_at)

    def test_una_empleada_no_puede_aplicar_ni_pedir(self) -> None:
        d = self._dialogo(quien="VEND-4")
        with patch("pos_uniformes.ui.dialogs.conteo_jornada_dialogs._elegir", return_value="si"), \
             patch("pos_uniformes.ui.dialogs.conteo_jornada_dialogs.QMessageBox.critical") as err:
            d._aplicar()
        err.assert_called_once()
        self.assertEqual(d.resultado, "")
        self.assertEqual(d._paginas.currentIndex(), 0)


    # --- tanda 1 (2026-11-15): textos honestos, fecha, ya revisado, cerrar ---------
    def test_la_confirmacion_de_aplicar_es_en_espanol_y_dice_lo_que_pasa(self) -> None:
        d = self._dialogo()
        with patch(f"{_D}._elegir", return_value="no") as preg:
            d._aplicar()
        self.assertEqual(d.resultado, "")
        titulo, texto, opciones = preg.call_args.args[1:4]
        self.assertEqual([o[1] for o in opciones], ["Volver", "Sí, corregir"])
        self.assertIn("A cada talla se le suma la diferencia que encontró Stayce el ", texto)
        # Tanda 2: el resumen real, con el dinero a precio de venta (7 contra 10; la otra cuadra).
        self.assertIn("Se corrige 1 talla: faltan 3, sobran 0 (−$300 a precio de venta).", texto)
        self.assertNotIn("Ojo", texto)
        self.assertNotIn("quedará como lo contó", texto)
        s = self.factory()
        self.assertIsNone(s.get(ConteoJornada, self.foto.id).revisada_at)   # Volver no aplica

    def test_descartar_tambien_pregunta_en_espanol(self) -> None:
        d = self._dialogo()
        with patch(f"{_D}._elegir", return_value="no") as preg:
            d._descartar()
        self.assertEqual(d.resultado, "")
        self.assertEqual([o[1] for o in preg.call_args.args[3]], ["Volver", "Sí, no usar este conteo"])
        self.assertEqual(d._descartar_btn.text(), "No usar este conteo")

    def _envejecer(self, dias: int) -> None:
        from datetime import timedelta

        s = self.factory()
        j = s.get(ConteoJornada, self.foto.id)
        j.terminada_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=dias)   # SQLite: UTC sin zona
        s.commit(); s.close()

    def test_la_fecha_del_conteo_y_el_aviso_si_es_viejo(self) -> None:
        d = self._dialogo()
        self.assertIn("hoy", d._cuando_label.text())
        self.assertTrue(d._aviso_label.isHidden())
        self._envejecer(41)
        d = self._dialogo()
        self.assertIn("hace 41 días", d._cuando_label.text())
        self.assertFalse(d._aviso_label.isHidden())
        self.assertIn("Conteo de hace 41 días: conviene recontar antes de corregir", d._aviso_label.text())
        with patch(f"{_D}._elegir", return_value="no") as preg:
            d._aplicar()
        self.assertIn("Sí, corregir con un conteo de hace 41 días", [o[1] for o in preg.call_args.args[3]])

    def test_a_los_diez_dias_avisa_pero_el_boton_no_cambia(self) -> None:
        self._envejecer(10)
        d = self._dialogo()
        self.assertFalse(d._aviso_label.isHidden())
        with patch(f"{_D}._elegir", return_value="no") as preg:
            d._aplicar()
        self.assertEqual([o[1] for o in preg.call_args.args[3]], ["Volver", "Sí, corregir"])

    def test_ya_revisada_no_deja_aplicar_ni_descartar_pero_si_pedir(self) -> None:
        from pos_uniformes.database.models import ConteoInventario

        d = self._dialogo()
        with patch(f"{_D}._elegir", return_value="si"):
            d._aplicar()
        self.assertEqual(d.resultado, "aplicada")
        # Desde el Historial («Ver el pedido que decidiste») se abre la misma ventana.
        d2 = self._dialogo()
        self.assertTrue(d2._aplicar_btn.isHidden())
        self.assertTrue(d2._descartar_btn.isHidden())
        self.assertFalse(d2._hoja_btn.isHidden())                      # el pedido y la hoja siguen
        self.assertFalse(d2._revisada_label.isHidden())
        self.assertIn("Corregido el ", d2._revisada_label.text())
        self.assertTrue(d2._aviso_label.isHidden())
        self.assertEqual(d2._chips["AJUSTE"].text(), "Corrigió 1 talla · faltaban 3 · sobraban 0")
        self.assertEqual(self._celda(d2, "6", _P.COL_QUEDA), "7")       # ya corregida: lo de hoy
        with patch(f"{_D}._elegir") as preg:
            d2._aplicar(); d2._descartar()
        preg.assert_not_called()
        s = self.factory()
        self.assertEqual(jn.ref(s.get(ConteoJornada, self.foto.id)).estado, "Aplicada")
        s.close()
        # El pedido sigue editable y se guarda.
        fila = self._fila(d2, "6")
        d2._table.item(fila, d2.COL_PEDIDO).setText("5")
        with patch(f"{_D}.QMessageBox.information"):
            self.assertTrue(d2._guardar_pedidos())
        s = self.factory()
        c = s.scalars(select(ConteoInventario).where(ConteoInventario.variante_id == self.v_ids[0])).one()
        self.assertEqual(c.pedido, 5)

    # --- tanda 2 (2026-11-15): el resumen real del ajuste ---------------------------
    def _despues_del_conteo(self, dias: int = 3):
        from datetime import timedelta

        from pos_uniformes.database.models import ConteoInventario

        s = self.factory()
        c = s.scalars(select(ConteoInventario).where(ConteoInventario.variante_id == self.v_ids[0])).one()
        momento = c.contado_at + timedelta(days=dias)
        s.close()
        return momento

    def test_el_aviso_viejo_dice_lo_vendido_desde_el_conteo(self) -> None:
        from pos_uniformes.database.models import LibretaVenta

        s = self.factory()
        v6 = s.get(Variante, self.v_ids[0])
        s.add(LibretaVenta(
            employee_code="VEND-4", tipo="venta", piezas=2, monto_total=200,
            detalle=[{"sku": v6.sku, "talla": "6", "nombre": "x", "cantidad": 2, "precio": "100", "subtotal": "200"}],
            created_at=self._despues_del_conteo(),
        ))
        s.commit(); s.close()
        self._envejecer(41)
        d = self._dialogo()
        self.assertIn("Conteo de hace 41 días: desde entonces se vendieron 2 piezas.", d._aviso_label.text())
        # Tanda 3: el sistema decía / contó / vendidas desde ya son columnas (antes iban en el «por qué»).
        self.assertEqual(
            [self._celda(d, "6", c) for c in (_P.COL_SISTEMA, _P.COL_CONTO, _P.COL_VENDIDAS)], ["10", "7", "2"],
        )

    def test_la_confirmacion_avisa_de_otro_ajuste_despues_del_conteo(self) -> None:
        from pos_uniformes.database.models import MovimientoInventario, TipoMovimientoInventario

        s = self.factory()
        s.add(MovimientoInventario(
            variante_id=self.v_ids[0], tipo_movimiento=TipoMovimientoInventario.AJUSTE_SALIDA, cantidad=-1,
            stock_anterior=10, stock_posterior=9, referencia=None, creado_por="dueno",
            created_at=self._despues_del_conteo(),
        ))
        s.commit(); s.close()
        d = self._dialogo()
        # Tanda 3: la talla lleva el ⚠ en DIF (la fecha en el tooltip) y en su «por qué»;
        # «qué hacer» queda solo con la acción (antes el ⚠ iba ahí y la cortaba).
        fila = self._fila(d, "6")
        self.assertTrue(self._celda(d, "6", _P.COL_DIF).endswith(" ⚠"))
        self.assertIn("⚠ otro ajuste el ", d._table.item(fila, _P.COL_DIF).toolTip())
        self.assertFalse(self._celda(d, "6", _P.COL_QUE).startswith("⚠"))
        d._table.selectRow(self._fila(d, "6"))
        self.assertIn("⚠ otro ajuste el ", d._por_que_label.text())
        with patch(f"{_D}._elegir", return_value="no") as preg:
            d._aplicar()
        texto = preg.call_args.args[2]
        # Tanda 4: esa talla no se toca al corregir; hay que recontarla.
        self.assertIn("La talla 6 no se toca: tuvo otro ajuste el ", texto)
        self.assertIn("Recuéntala.", texto)
        self.assertNotIn("se le suma la diferencia otra vez", texto)

    # --- tanda 4 (2026-11-15): la talla con otro ajuste no se corrige -----------------
    def _otro_ajuste(self, indice: int = 0) -> None:
        from pos_uniformes.database.models import MovimientoInventario, TipoMovimientoInventario

        s = self.factory()
        s.add(MovimientoInventario(
            variante_id=self.v_ids[indice], tipo_movimiento=TipoMovimientoInventario.AJUSTE_SALIDA, cantidad=-1,
            stock_anterior=10, stock_posterior=9, referencia=None, creado_por="dueno",
            created_at=self._despues_del_conteo(),
        ))
        s.get(Variante, self.v_ids[indice]).stock_actual = 9
        s.commit(); s.close()

    def _con_otra_diferencia(self) -> None:
        """La talla 8 de la Prenda 1 también con diferencia (contó 12 de 10)."""
        from pos_uniformes.services.conteo_service import ConteoInput, registrar_conteos_lote

        s = self.factory()
        registrar_conteos_lote(s, [ConteoInput(self.v_ids[3], 12)], "x", jornada_id=self.foto.id)
        s.commit(); s.close()

    def test_la_talla_con_otro_ajuste_no_se_toca_y_las_demas_si(self) -> None:
        from pos_uniformes.database.models import ConteoInventario

        self._con_otra_diferencia()
        self._otro_ajuste(0)
        d = self._dialogo()
        self.assertEqual(d._chips["AJUSTE"].text(), "Corrige 1 talla · faltan 0 · sobran 2 · +$200 · 1 a recontar")
        self.assertEqual(d._aplicar_btn.text(), "Corregir inventario (1 talla, +2 pz)")
        fila = [self._celda(d, "6", c) for c in (_P.COL_DIF, _P.COL_QUEDA, _P.COL_QUE)]
        self.assertEqual(fila, ["−3 ⚠", "9", "no se toca · recontar"])        # queda hoy = tienda hoy
        self.assertIn("no se toca; hay que recontarla", d._resumen_label.text())
        d._table.selectRow(self._fila(d, "6"))
        self.assertIn(": no se toca, recontar", d._por_que_label.text())
        with patch(f"{_D}._elegir", return_value="si") as preg:
            d._aplicar()
        self.assertIn("Prenda 0 Uno 6 no se toca: tuvo otro ajuste el ", preg.call_args.args[2])   # dos prendas: dice cuál
        self.assertEqual(
            d._listo_texto.text(),
            "Se corrigió 1 talla: faltaban 0, sobraban 2 (+$200 a precio de venta). "
            "Prenda 0 Uno 6 no se tocó (tuvo otro ajuste): recuéntala.",
        )
        s = self.factory()
        self.assertEqual(s.get(Variante, self.v_ids[0]).stock_actual, 9)     # sin el −3 de aquel día
        self.assertEqual(s.get(Variante, self.v_ids[3]).stock_actual, 12)
        c6 = s.scalars(select(ConteoInventario).where(ConteoInventario.variante_id == self.v_ids[0])).one()
        self.assertFalse(c6.ajustado)
        self.assertIn("No se corrigió: otro ajuste el ", c6.notas)
        s.close()
        # Ya revisada (desde el Historial): se ve como no corregida, no como corregida.
        d2 = self._dialogo()
        self.assertEqual(self._celda(d2, "6", _P.COL_QUE), "no se corrigió (otro ajuste)")
        self.assertEqual(self._celda(d2, "6", _P.COL_QUEDA), "9")
        self.assertEqual(d2._chips["AJUSTE"].text(), "Corrigió 1 talla · faltaban 0 · sobraban 2 · 1 no se corrigió")
        d2._table.selectRow(self._fila(d2, "6"))
        self.assertIn(": no se corrigió, recontar", d2._por_que_label.text())
        # Y en la historia de la talla.
        from pos_uniformes.ui.dialogs.conteo_jornada_dialogs import TallaHistoriaDialog

        h = TallaHistoriaDialog(variante_id=self.v_ids[0], titulo="Uno", session_factory=self.factory)
        self._dialogos.append(h)
        self.assertEqual(h._tabla.item(0, 6).text(), "no se corrigió (otro ajuste)")
        h3 = TallaHistoriaDialog(variante_id=self.v_ids[3], titulo="Uno", session_factory=self.factory)
        self._dialogos.append(h3)
        self.assertEqual(h3._tabla.item(0, 6).text(), "se corrigió")

    def test_si_todas_tuvieron_otro_ajuste_solo_se_marca_revisado(self) -> None:
        self._otro_ajuste(0)
        d = self._dialogo()
        self.assertEqual(d._aplicar_btn.text(), "Marcar como revisado")
        self.assertIn("solo se marca como revisado", d._aplicar_btn.toolTip())
        self.assertIn("La talla con diferencia tuvo otro ajuste", d._resumen_label.text())
        self.assertEqual(d._chips["AJUSTE"].text(), "Nada que corregir · 1 a recontar")
        with patch(f"{_D}._elegir", return_value="si") as preg:
            d._aplicar()
        texto, opciones = preg.call_args.args[2], preg.call_args.args[3]
        self.assertTrue(texto.startswith("Ninguna talla se corrige (Stayce contó el "))
        self.assertIn("Solo se marca como revisado.", texto)
        self.assertEqual([o[1] for o in opciones], ["Volver", "Sí, marcar como revisado"])
        self.assertEqual(d.resultado, "aplicada")
        self.assertEqual(
            d._listo_texto.text(),
            "Quedó revisado: ninguna talla se corrigió. La talla 6 no se tocó (tuvo otro ajuste): recuéntala.",
        )
        s = self.factory()
        self.assertEqual(s.get(Variante, self.v_ids[0]).stock_actual, 9)
        self.assertIsNotNone(s.get(ConteoJornada, self.foto.id).revisada_at)
        s.close()
        # Ya revisada: no dice «Corregido» si no se corrigió ninguna talla.
        d2 = self._dialogo()
        self.assertIn("(no se corrigió nada)", d2._revisada_label.text())
        self.assertNotIn("Corregido", d2._revisada_label.text())

    def test_descartada_dice_que_no_se_uso(self) -> None:
        d = self._dialogo()
        with patch(f"{_D}._elegir", return_value="si"):
            d._descartar()
        d2 = self._dialogo()
        self.assertIn("No se usó (", d2._revisada_label.text())
        self.assertTrue(d2._aplicar_btn.isHidden())
        self.assertEqual(d2._chips["AJUSTE"].text(), "1 talla con diferencia · no se usó")

    def test_contada_en_cero_sin_demanda_dice_se_acabo(self) -> None:
        from pos_uniformes.database.models import ConteoInventario

        s = self.factory()
        c6 = s.scalars(select(ConteoInventario).where(ConteoInventario.variante_id == self.v_ids[0])).one()
        c6.stock_fisico = 40    # la 6 alcanza (7/sem × 4 = 28 < 40): bien
        c8 = s.scalars(select(ConteoInventario).where(ConteoInventario.variante_id == self.v_ids[1])).one()
        c8.stock_fisico = 0     # la 8 no se vende en 14 días y la contaron en 0
        s.commit(); s.close()
        d = self._dialogo()
        self.assertEqual(self._celda(d, "8", _P.COL_QUE), "se acabó")
        texto = d._resumen_label.text()
        self.assertIn("1 se acabó y nadie la pidió", texto)
        self.assertNotIn("faltan", texto)

    def test_en_cero_sin_dias_observados_sigue_sin_datos(self) -> None:
        # Sin Libreta no hay días observados: no se sabe si se acabó ni si la habrían pedido.
        from pos_uniformes.database.models import ConteoInventario, LibretaVenta

        s = self.factory()
        c = s.scalars(select(ConteoInventario).where(ConteoInventario.variante_id == self.v_ids[1])).one()
        c.stock_fisico = 0
        s.query(LibretaVenta).delete()
        s.commit(); s.close()
        d = self._dialogo()
        self.assertEqual(self._celda(d, "8", _P.COL_QUE), "sin datos")
        self.assertEqual(self._celda(d, "6", _P.COL_QUE), "sin datos")
        texto = d._resumen_label.text()
        self.assertNotIn("se acabó", texto)
        self.assertIn("faltan días para saber el ritmo (2 tallas)", texto)

    def test_el_motivo_real_cuando_lo_que_hay_alcanza(self) -> None:
        from pos_uniformes.database.models import ConteoInventario

        s = self.factory()
        c = s.scalars(select(ConteoInventario).where(ConteoInventario.variante_id == self.v_ids[0])).one()
        c.stock_fisico = 40     # 7/sem × 4 = 28 < 40: bien
        s.commit(); s.close()
        d = self._dialogo()
        texto = d._resumen_label.text()
        self.assertIn("lo que hay alcanza (1 talla)", texto)
        self.assertIn("1 talla sin ventas", texto)
        self.assertNotIn("faltan días", texto)

    def test_chip_en_cero_va_gris_y_sin_relleno(self) -> None:
        # Reescrita (antes: test_tarjeta_en_cero_se_apaga_aunque_este_prendida).
        from pos_uniformes.database.models import LibretaVenta

        s = self.factory()
        s.query(LibretaVenta).delete()
        s.commit(); s.close()
        d = self._dialogo()
        urgente = d._chips["URGENTE"]
        self.assertFalse(urgente.isEnabled())
        self.assertEqual(urgente.property("tono"), "cero")
        d.show(); _APP.processEvents()
        from PyQt6.QtCore import QPoint, QRect

        # El chip no tiene fondo propio: se ve lo de atrás (crema), no un rojo sólido.
        imagen = d.grab(QRect(urgente.mapTo(d, QPoint(0, 0)), urgente.size())).toImage()
        color = imagen.pixelColor(imagen.width() // 2, 3)
        self.assertGreater(color.red(), 230)       # crema, no rojo sólido
        self.assertGreater(color.green(), 225)
        urgente.click()
        self.assertIsNone(d._filtro)               # apagado: no filtra
        self.assertTrue(d._hoja_btn.isHidden())    # sin nada pedido no hay hoja
        d.hide()

    def test_cerrar_sin_cambios_no_pregunta(self) -> None:
        d = self._dialogo()     # el pedido arranca prellenado con el sugerido: eso no es un cambio
        with patch(f"{_D}._elegir") as preg:
            d.reject()
        preg.assert_not_called()

    def test_cerrar_con_el_pedido_cambiado_pregunta(self) -> None:
        from pos_uniformes.database.models import ConteoInventario

        d = self._dialogo()
        d.show(); _APP.processEvents()
        d._table.item(self._fila(d, "6"), d.COL_PEDIDO).setText("30")
        with patch(f"{_D}._elegir", return_value="volver") as preg:
            d.reject()
        self.assertTrue(d.isVisible())                       # Volver: sigue abierta
        self.assertEqual(preg.call_args.args[2], "Cambiaste el pedido y no lo guardaste.")
        self.assertEqual([o[1] for o in preg.call_args.args[3]], ["Guardar", "No guardar", "Volver"])
        with patch(f"{_D}._elegir", return_value="guardar"):
            d.close()                                        # la ✕ pasa por lo mismo
        self.assertFalse(d.isVisible())
        s = self.factory()
        c = s.scalars(select(ConteoInventario).where(ConteoInventario.variante_id == self.v_ids[0])).one()
        self.assertEqual(c.pedido, 30)

    def test_cerrar_con_la_x_mientras_escribes_pregunta(self) -> None:
        # Editor abierto en PEDIR (sin Enter) y se cierra con la ✕: lo escrito cuenta.
        from PyQt6.QtTest import QTest
        from PyQt6.QtWidgets import QAbstractItemView

        from pos_uniformes.database.models import ConteoInventario

        d = self._dialogo()
        d.show(); d.activateWindow(); _APP.processEvents()
        item = d._table.item(self._fila(d, "6"), d.COL_PEDIDO)
        d._table.setCurrentItem(item)
        d._table.editItem(item)
        _APP.processEvents()
        self.assertEqual(d._table.state(), QAbstractItemView.State.EditingState)
        editor = _APP.focusWidget() or next(
            w for w in d._table.viewport().children() if isinstance(w, QWidget) and w.isVisible()
        )
        editor.selectAll()
        QTest.keyClicks(editor, "30")
        with patch(f"{_D}._elegir", return_value="volver") as preg:
            d.close()
        preg.assert_called_once()
        self.assertTrue(d.isVisible())
        with patch(f"{_D}._elegir", return_value="guardar"):
            d.close()
        self.assertFalse(d.isVisible())
        s = self.factory()
        c = s.scalars(select(ConteoInventario).where(ConteoInventario.variante_id == self.v_ids[0])).one()
        self.assertEqual(c.pedido, 30)

    def test_no_guardar_cierra_sin_tocar_la_base(self) -> None:
        from pos_uniformes.database.models import ConteoInventario

        d = self._dialogo()
        d.show(); _APP.processEvents()
        d._table.item(self._fila(d, "6"), d.COL_PEDIDO).setText("30")
        with patch(f"{_D}._elegir", return_value="no_guardar"):
            d.reject()
        self.assertFalse(d.isVisible())
        s = self.factory()
        c = s.scalars(select(ConteoInventario).where(ConteoInventario.variante_id == self.v_ids[0])).one()
        self.assertIsNone(c.pedido)

    def test_despues_de_guardar_ya_no_pregunta(self) -> None:
        d = self._dialogo()
        d._table.item(self._fila(d, "6"), d.COL_PEDIDO).setText("30")
        with patch(f"{_D}.QMessageBox.information"):
            d._guardar_pedidos()
        with patch(f"{_D}._elegir") as preg:
            d.reject()
        preg.assert_not_called()

    def test_cabe_en_1366x768_al_100_y_al_125(self) -> None:
        from PyQt6.QtCore import QRect

        for area, esperado in ((QRect(0, 0, 1920, 1040), (1280, 700)), (QRect(0, 0, 1366, 728), (1280, 688)),
                               (QRect(0, 0, 1093, 574), (1077, 534))):
            with patch(f"{_D}._area_disponible", return_value=area):
                d = self._dialogo()
            self.assertEqual((d.width(), d.height()), esperado)
            self.assertLessEqual(d.minimumWidth(), esperado[0])
            self.assertLessEqual(d.minimumHeight(), esperado[1])


_D = "pos_uniformes.ui.dialogs.conteo_jornada_dialogs"

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
        from datetime import datetime, timedelta, timezone

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
        j.terminada_at = datetime.now(timezone.utc) - timedelta(days=2)
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
