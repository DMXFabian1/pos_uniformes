"""La ventana de historial de conteos (la del dueño para auditar): sus conteos
uno por renglón, con comparar / pedido / hoja a un clic (Daniel, 2026-09-22)."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from PyQt6.QtWidgets import QApplication
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import (
    Categoria, ConteoInventario, ConteoJornada, Escuela, Marca, Producto, Variante,
)
from pos_uniformes.services import conteo_jornada_service as jn
from pos_uniformes.ui.dialogs import conteo_historial_dialog as hist


class _Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
        self.factory = sessionmaker(bind=engine)
        s: Session = self.factory()
        cat = Categoria(nombre="U"); marca = Marca(nombre="G"); s.add_all([cat, marca]); s.flush()
        self.esc = Escuela(nombre="Justo Sierra"); s.add(self.esc); s.flush()
        p = Producto(nombre="Camisa JS", nombre_base="Camisa JS", categoria_id=cat.id, marca_id=marca.id, escuela_id=self.esc.id)
        s.add(p); s.flush()
        self.v = Variante(producto_id=p.id, sku="S1", talla="10", color="X", precio_venta=100, stock_actual=5)
        s.add(self.v); s.flush()
        ahora = datetime.now(timezone.utc)
        # dos conteos: el viejo dejó pedido, el nuevo no se ha revisado
        self.viejo = ConteoJornada(
            titulo="Justo Sierra", escuela_id=self.esc.id, empleada_code="VEND-3", empleada_nombre="Evelyn",
            iniciada_at=ahora - timedelta(days=40), terminada_at=ahora - timedelta(days=40),
            revisada_at=ahora - timedelta(days=39), revisada_por="VEND-1", total_tallas=1,
        )
        self.nuevo = ConteoJornada(
            titulo="Justo Sierra", escuela_id=self.esc.id, empleada_code="VEND-4", empleada_nombre="Fanny",
            iniciada_at=ahora - timedelta(days=1), terminada_at=ahora - timedelta(days=1), total_tallas=1,
        )
        s.add_all([self.viejo, self.nuevo]); s.flush()
        s.add_all([
            ConteoInventario(jornada_id=self.viejo.id, variante_id=self.v.id, escuela_id=self.esc.id,
                             stock_sistema=10, stock_fisico=7, diferencia=-3, pedido=12, contado_por="VEND-3"),
            ConteoInventario(jornada_id=self.nuevo.id, variante_id=self.v.id, escuela_id=self.esc.id,
                             stock_sistema=5, stock_fisico=9, diferencia=4, contado_por="VEND-4"),
        ])
        s.commit()
        self.esc_id = self.esc.id
        s.close()


class HistorialDeAlcanceTests(_Base):
    def test_trae_los_conteos_del_mas_nuevo_al_mas_viejo_con_sus_cifras(self) -> None:
        with self.factory() as s:
            filas = jn.historial_de_alcance(s, self.esc_id)
        self.assertEqual([f.quien for f in filas], ["Fanny", "Evelyn"])
        nuevo, viejo = filas
        self.assertEqual((nuevo.tallas, nuevo.faltaron, nuevo.sobraron, nuevo.pedido_piezas), (1, 0, 4, 0))
        self.assertEqual((viejo.tallas, viejo.faltaron, viejo.sobraron, viejo.pedido_piezas), (1, 3, 0, 12))
        self.assertEqual((nuevo.estado, viejo.estado), ("Por revisar", "Aplicada"))
        self.assertEqual(nuevo.diferencia, 4)

    def test_otra_escuela_no_se_mezcla(self) -> None:
        with self.factory() as s:
            otra = Escuela(nombre="Patria"); s.add(otra); s.commit()
            self.assertEqual(jn.historial_de_alcance(s, otra.id), [])
            self.assertEqual(jn.historial_de_alcance(s, None, "Bata"), [])   # básicos, tampoco


class VentanaTests(_Base):
    def setUp(self) -> None:
        super().setUp()
        self.d = hist.ConteoHistorialDialog(session_factory=self.factory)

    def tearDown(self) -> None:
        self.d.close(); self.d.deleteLater()

    def _elegir_escuela(self) -> None:
        self.d._buscar.setText("Justo")
        self.d._lista.setCurrentRow(0)

    def test_lista_las_escuelas_y_al_elegir_una_muestra_sus_conteos(self) -> None:
        self.assertGreater(self.d._lista.count(), 0)
        self._elegir_escuela()
        self.assertEqual(self.d._titulo_alcance.text(), "Justo Sierra")
        self.assertEqual(self.d._tabla.rowCount(), 2)
        self.assertEqual(self.d._tabla.item(0, hist._COL_QUIEN).text(), "Fanny")
        self.assertEqual(self.d._tabla.item(0, hist._COL_SOBRARON).text(), "+4")
        self.assertEqual(self.d._tabla.item(1, hist._COL_FALTARON).text(), "−3")
        self.assertEqual(self.d._tabla.item(1, hist._COL_PEDIDO).text(), "12")
        self.assertIn("2 conteos", self.d._resumen.text())
        self.assertIn("12 piezas pedidas", self.d._resumen.text())

    def test_los_botones_dependen_del_conteo_elegido(self) -> None:
        self._elegir_escuela()
        self.d._tabla.selectRow(0)      # el nuevo: sin pedido todavía
        self.assertTrue(self.d._comparar_btn.isEnabled())
        self.assertTrue(self.d._revisar_btn.isEnabled())
        self.assertFalse(self.d._hoja_btn.isEnabled())
        self.assertEqual(self.d._revisar_btn.text(), "Revisar / decidir el pedido")
        self.d._tabla.selectRow(1)      # el viejo: ya revisado y con pedido
        self.assertTrue(self.d._hoja_btn.isEnabled())
        self.assertEqual(self.d._revisar_btn.text(), "Ver el pedido que decidiste")

    def test_sin_elegir_nada_no_hay_botones_prendidos(self) -> None:
        for b in (self.d._comparar_btn, self.d._revisar_btn, self.d._hoja_btn, self.d._evolucion_btn):
            self.assertFalse(b.isEnabled())

    def test_el_buscador_filtra(self) -> None:
        self.d._buscar.setText("no existe tal escuela")
        self.assertEqual(self.d._lista.count(), 0)
