"""«📝 Más datos» de la prenda, la pantalla (tanda 5, 2026-11-15). Offscreen sobre la mini caja."""

from __future__ import annotations

import os
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QEvent
from PyQt6.QtWidgets import QApplication
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from pos_uniformes.database.models import CambioCatalogo, Marca, Producto
from pos_uniformes.services.catalog_service import CatalogService
from pos_uniformes.ui.dialogs.datos_prenda_dialog import SIN_VALOR, DatosPrendaDialog
from pos_uniformes.ui.helpers import inventario_ficha_prenda as ifp
from tests._ayuda_mini_caja import MiniCaja


class DatosPrendaDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.engine = create_engine("sqlite://")
        self.caja = MiniCaja(self.engine)
        self.s = self.caja.s
        self.s.add(Marca(nombre="Claudia"))
        self.s.commit()
        quieto = patch.object(CatalogService, "_avisar_busqueda")
        quieto.start()
        self.addCleanup(quieto.stop)
        self.sueter = self.caja.productos[("Ignacio Allende", "Suéter")]

    def abrir(self, usuario=None) -> DatosPrendaDialog:
        d = DatosPrendaDialog(None, session_factory=lambda: Session(self.engine, expire_on_commit=False),
                              usuario_id=(usuario or self.caja.admin).id, producto_id=self.sueter.id)
        self.addCleanup(self._cerrar, d)
        return d

    @staticmethod
    def _cerrar(d) -> None:
        d.close()
        d.deleteLater()
        QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)

    def elegir(self, d: DatosPrendaDialog, campo: str, valor: str) -> None:
        combo = d.combos[campo]
        combo.setCurrentIndex(combo.findData(valor))

    def cambios_en_bitacora(self) -> int:
        self.s.expire_all()
        return int(self.s.scalar(select(func.count()).select_from(CambioCatalogo)))

    def test_listas_cerradas_con_lo_de_la_prenda(self) -> None:
        d = self.abrir()
        self.assertFalse(d.principal.isEnabled())  # sin cambios
        for combo in d.combos.values():
            self.assertFalse(combo.isEditable())
        self.assertEqual(d.combos["marca"].currentText(), "Sin marca")
        self.assertEqual(d.combos["escuela"].currentText(), "Ignacio Allende")
        self.assertEqual(d.combos["atributo"].currentText(), SIN_VALOR)
        self.assertEqual(d.combos["genero"].currentText(), "Unisex")

    def test_guarda_marca_y_genero_sin_tocar_el_nombre(self) -> None:
        d = self.abrir()
        self.elegir(d, "marca", "Claudia")
        self.elegir(d, "genero", "Mujer")
        self.assertTrue(d.principal.isEnabled(), d.bloqueo.text())
        self.assertIn("Marca: Sin marca → Claudia", d.frase.text())
        d.principal.click()
        self.assertEqual(d.result(), d.DialogCode.Accepted)
        self.s.expire_all()
        p = self.s.get(Producto, self.sueter.id)
        self.assertEqual((p.marca.nombre, p.genero, p.nombre),
                         ("Claudia", "Mujer", "Suéter Botones M Rojo Ignacio Allende"))

    def test_cancelar_no_cambia_nada(self) -> None:
        antes = self.cambios_en_bitacora()
        d = self.abrir()
        self.elegir(d, "marca", "Claudia")
        d.cancelar.click()
        self.assertEqual(self.cambios_en_bitacora(), antes)

    def test_costo_que_no_es_numero_bloquea(self) -> None:
        d = self.abrir()
        d.costo.setText("abc")
        d.replanear()
        self.assertFalse(d.principal.isEnabled())
        self.assertIn("no es un número", d.bloqueo.text())

    def test_solo_admin(self) -> None:
        d = self.abrir(self.caja.cajera)
        self.elegir(d, "marca", "Claudia")
        d.principal.click()
        self.assertIsNone(d.resultado)
        self.assertIn("ADMIN", d.error.text())
        self.s.expire_all()
        self.assertEqual(self.s.get(Producto, self.sueter.id).marca.nombre, "Sin marca")

    def test_cabe_en_la_caja(self) -> None:
        d = self.abrir()
        d.show()
        QApplication.processEvents()
        self.assertLessEqual(d.width(), 1366)
        self.assertLessEqual(d.height(), 700)

    def test_la_ficha_abre_mas_datos_solo_para_admin(self) -> None:
        seccion = ifp.SeccionPrenda()
        self.addCleanup(seccion.deleteLater)
        self.assertEqual(seccion.boton_datos.text(), "📝 Más datos")
        ventana = Mock(current_role=None)
        with patch.object(ifp.QMessageBox, "warning") as aviso:
            self.assertIsNone(ifp.editar_datos(ventana, lambda: None, self.sueter.id))
        aviso.assert_called_once()


if __name__ == "__main__":
    unittest.main()
