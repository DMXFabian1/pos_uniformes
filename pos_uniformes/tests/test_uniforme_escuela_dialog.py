"""Pantalla POS "Uniformes por escuela" (catálogo fase 2) sobre sqlite en memoria."""

from __future__ import annotations

import unittest

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from PyQt6.QtWidgets import QApplication, QCheckBox, QComboBox, QLineEdit

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import Categoria, Escuela, Marca, Producto, TipoPieza, TipoPrenda
from pos_uniformes.services import uniforme_service as us
from pos_uniformes.ui.dialogs import uniforme_escuela_dialog as ued


class UniformeEscuelaDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from sqlalchemy.pool import StaticPool
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
        self.factory = sessionmaker(bind=engine)
        s: Session = self.factory()
        cat = Categoria(nombre="Uniformes"); marca = Marca(nombre="G"); s.add_all([cat, marca]); s.flush()
        tp = TipoPrenda(nombre="Oficial"); dep = TipoPrenda(nombre="Deportivo"); tz = TipoPieza(nombre="Camisa"); tzp = TipoPieza(nombre="Pants Suelto")
        s.add_all([tp, dep, tz, tzp]); s.flush()
        self.vg = Escuela(nombre="Vicente Guerrero"); self.js = Escuela(nombre="Justo Sierra"); s.add_all([self.vg, self.js]); s.flush()
        def prod(nombre, escuela=None, prenda=tp, pieza=tz):
            p = Producto(nombre=nombre, nombre_base=nombre, categoria_id=cat.id, marca_id=marca.id, escuela_id=escuela.id if escuela else None, tipo_prenda_id=prenda.id, tipo_pieza_id=pieza.id)
            s.add(p); s.flush(); return p
        self.camisa = prod("Camisa Vicente Guerrero", self.vg)
        self.pants_vg = prod("Pants Suelto Vicente Guerrero", self.vg, dep, tzp)
        self.pants_rojo = prod("Pants Suelto Liso Rojo", None, dep, tzp)
        self.olan = prod("Camisa Cuello Olan Blanca")
        s.commit()
        self.vg_id, self.js_id, self.pants_rojo_id = self.vg.id, self.js.id, self.pants_rojo.id
        s.close()
        self.d = ued.UniformeEscuelaDialog(session_factory=self.factory)

    def tearDown(self) -> None:
        self.d.close(); self.d.deleteLater()

    def _elegir(self, nombre: str) -> None:
        items = self.d._escuela_list.findItems(nombre, __import__("PyQt6.QtCore", fromlist=["Qt"]).Qt.MatchFlag.MatchExactly)
        self.d._escuela_list.setCurrentItem(items[0])

    def test_escuela_sin_uniforme_muestra_vacio_y_proponer_lo_arma(self) -> None:
        self._elegir("Vicente Guerrero")
        self.assertTrue(self.d._vacio.isVisibleTo(self.d)); self.assertEqual(self.d._tabla.rowCount(), 0)
        self.assertEqual(self.d._proponer_btn.text(), "Proponer desde catálogo")
        self.d._proponer()
        self.assertEqual(self.d._tabla.rowCount(), 2)
        self.assertEqual([self.d._tabla.item(i, ued._COL_PIEZA).text() for i in range(2)], ["Pants Suelto Vicente Guerrero", "Camisa Vicente Guerrero"])
        self.assertEqual(self.d._tabla.cellWidget(0, ued._COL_GRUPO).currentText(), "Deportivo")
        self.assertEqual(self.d._tabla.item(0, ued._COL_ORIGEN).text(), "con escudo")
        self.assertIn("2 piezas nuevas", self.d._status.text())
        self.assertEqual(self.d._proponer_btn.text(), "Completar desde catálogo")

    def test_agregar_general_y_editar_guarda_al_momento(self) -> None:
        self._elegir("Justo Sierra"); self.d._proponer()
        # el general aparece en la lista de abajo y al agregarlo desaparece de ahí
        self.d._buscar.setText("rojo")
        self.assertEqual([self.d._generales_list.item(i).text() for i in range(self.d._generales_list.count())], ["Pants Suelto Liso Rojo"])
        self.d._generales_list.setCurrentRow(0); self.d._agregar_general()
        self.assertEqual(self.d._generales_list.count(), 0)
        self.assertEqual(self.d._tabla.rowCount(), 1)
        self.assertEqual(self.d._tabla.item(0, ued._COL_ORIGEN).text(), "general")
        # editar grupo, color y obligatoria
        self.d._tabla.cellWidget(0, ued._COL_GRUPO).setCurrentText("Diario")
        color: QLineEdit = self.d._tabla.cellWidget(0, ued._COL_COLOR); color.setText("Rojo"); color.editingFinished.emit()
        chk: QCheckBox = self.d._tabla.cellWidget(0, ued._COL_OBLIG).findChild(QCheckBox); chk.setChecked(False)
        with self.factory() as s:
            fila = us.piezas_de(s, us.uniforme_de(s, self.js_id).id)[0]
            self.assertEqual((fila["grupo"], fila["color"], fila["obligatoria"]), ("Diario", "Rojo", False))
            from pos_uniformes.database.models import CatalogSchoolProductLink
            self.assertEqual(s.query(CatalogSchoolProductLink).filter_by(escuela_id=self.js_id, producto_id=self.pants_rojo_id).count(), 1)

    def test_mover_y_quitar(self) -> None:
        self._elegir("Vicente Guerrero"); self.d._proponer()
        self.d._mover(self.d._piezas[1]["pieza_id"], -1)
        self.assertEqual(self.d._tabla.item(0, ued._COL_PIEZA).text(), "Camisa Vicente Guerrero")
        self.d._quitar(self.d._piezas[0]["pieza_id"], "Camisa Vicente Guerrero")
        self.assertEqual([self.d._tabla.item(i, ued._COL_PIEZA).text() for i in range(self.d._tabla.rowCount())], ["Pants Suelto Vicente Guerrero"])
        self.assertIn("Quitada", self.d._status.text())

    def test_pintar_no_dispara_guardados(self) -> None:
        self._elegir("Vicente Guerrero"); self.d._proponer()
        llamadas = []
        self.d._cambiar = lambda *a, **k: llamadas.append((a, k))
        self.d._pintar_tabla()
        self.assertEqual(llamadas, [])


class RecetaDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from sqlalchemy.pool import StaticPool
        from pos_uniformes.database.models import Variante
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
        self.factory = sessionmaker(bind=engine)
        s = self.factory()
        cat = Categoria(nombre="U"); marca = Marca(nombre="G"); s.add_all([cat, marca]); s.flush()
        dep = TipoPrenda(nombre="Deportivo"); s.add(dep)
        tz = {n: TipoPieza(nombre=n) for n in ("Pants 3pz", "Pants 2pz", "Playera", "Chamarra", "Pants Suelto")}
        s.add_all(tz.values()); s.flush()
        esc = Escuela(nombre="Justo Sierra"); s.add(esc); s.flush()
        def prod(nombre, pieza, stock):
            p = Producto(nombre=nombre, nombre_base=nombre, categoria_id=cat.id, marca_id=marca.id, escuela_id=esc.id, tipo_prenda_id=dep.id, tipo_pieza_id=tz[pieza].id)
            s.add(p); s.flush(); s.add(Variante(producto_id=p.id, sku=f"{p.id}-10", talla="10", color="R", precio_venta=1, stock_actual=stock)); return p
        self.p3 = prod("Pants 3pz Deportivo JS", "Pants 3pz", 0); self.p2 = prod("Pants 2pz Deportivo JS", "Pants 2pz", 4)
        self.play = prod("Playera Deportiva JS", "Playera", 9); self.polo = prod("Playera Polo JS", "Playera", 2)
        s.commit(); self.esc_id = esc.id; self.ids = (self.p3.id, self.p2.id, self.play.id, self.polo.id); s.close()
        self.d = ued.UniformeEscuelaDialog(session_factory=self.factory)
        self.d._escuela_list.setCurrentItem(self.d._escuela_list.findItems("Justo Sierra", __import__("PyQt6.QtCore", fromlist=["Qt"]).Qt.MatchFlag.MatchExactly)[0])
        self.d._proponer()

    def tearDown(self) -> None:
        self.d.close(); self.d.deleteLater()

    def test_el_conjunto_avisa_sin_receta_y_el_dialogo_la_guarda(self) -> None:
        fila = next(i for i, p in enumerate(self.d._piezas) if p["nombre"] == "Pants 3pz Deportivo JS")
        boton = self.d._tabla.cellWidget(fila, ued._COL_RECETA)
        self.assertEqual(boton.text(), "⚠ sin receta")
        self.assertIsNone(self.d._tabla.cellWidget(fila + 1, ued._COL_RECETA))  # el 2pz no es conjunto
        p3_id, p2_id, play_id, polo_id = self.ids
        dlg = ued.RecetaDialog(self.d, session_factory=self.factory, conjunto_id=p3_id, nombre="Pants 3pz Deportivo JS", piezas=self.d._piezas)
        # el 2pz se preselecciona (solo hay uno); la playera no (hay dos): Daniel elige la polo
        self.assertEqual(dlg._combos[0][2].currentData(), p2_id)
        self.assertIsNone(dlg._combos[1][2].currentData())
        dlg._combos[1][2].setCurrentIndex(dlg._combos[1][2].findData(polo_id))
        dlg._guardar()
        with self.factory() as s:
            from pos_uniformes.services import conjunto_service as cs
            self.assertEqual([(c.componente_id, c.cantidad) for c in cs.receta_de(s, p3_id)], [(p2_id, 1), (polo_id, 1)])
            from pos_uniformes.database.models import Variante
            self.assertEqual(s.scalar(select(Variante.stock_actual).where(Variante.producto_id == p3_id)), 2)  # min(4, 2)
        self.d._recargar()
        self.assertEqual(self.d._tabla.cellWidget(fila, ued._COL_RECETA).text(), "2pz JS + Playera Polo JS")
