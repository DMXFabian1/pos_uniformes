"""Las ventanitas de la ficha: talla que falta, otro color y corregir prenda (tanda 4, 2026-11-15).

Sobre la caja en miniatura (SQLite) con la pantalla de verdad (offscreen).
"""

from __future__ import annotations

import os
import unittest
from decimal import Decimal
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QEvent
from PyQt6.QtWidgets import QApplication
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from pos_uniformes.database.models import CambioCatalogo, Producto, Variante
from pos_uniformes.services import alta_ficha_service as af
from pos_uniformes.services.catalog_service import CatalogService
from pos_uniformes.ui.dialogs import ficha_prenda_dialogs as fpd
from pos_uniformes.ui.dialogs.quisiste_decir_dialog import ACCION_USAR, Eleccion
from pos_uniformes.ui.helpers.inventario_ficha_prenda import SeccionPrenda
from tests._ayuda_mini_caja import MiniCaja

D = Decimal


class _Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.engine = create_engine("sqlite://")
        self.caja = MiniCaja(self.engine)
        self.s = self.caja.s
        quieto = patch.object(CatalogService, "_avisar_busqueda")
        quieto.start()
        self.addCleanup(quieto.stop)

    def fabrica(self):
        return lambda: Session(self.engine, expire_on_commit=False)

    def abrir(self, clase, usuario=None, **kw):
        d = clase(None, session_factory=self.fabrica(), usuario_id=(usuario or self.caja.admin).id, **kw)
        self.addCleanup(self._cerrar, d)
        return d

    @staticmethod
    def _cerrar(d) -> None:
        d.close()
        d.deleteLater()
        QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)

    def contar(self, modelo) -> int:
        self.s.expire_all()
        return int(self.s.scalar(select(func.count()).select_from(modelo)))

    def foto(self) -> dict:
        return {m.__name__: self.contar(m) for m in (Producto, Variante, CambioCatalogo)}

    def tallas_de(self, producto_id: int, color: str | None = None) -> dict:
        self.s.expire_all()
        filtro = [Variante.producto_id == producto_id]
        if color:
            filtro.append(Variante.color == color)
        return {v.talla: v.precio_venta for v in self.s.scalars(select(Variante).where(*filtro)).all()}

    def prod(self, escuela: str, pieza: str) -> Producto:
        return self.caja.productos[(escuela, pieza)]


class TallaQueFaltaTests(_Base):
    def test_crea_exactamente_esa_talla_con_su_precio(self) -> None:
        pants = self.prod("Miguel Hidalgo", "Pants Suelto")
        antes = self.tallas_de(pants.id)
        d = self.abrir(fpd.TallaNuevaDialog, producto_id=pants.id, talla="EXG")
        self.assertEqual(d.precio.text(), "305")
        self.assertEqual(d.principal.text(), "Agregar talla EXG")
        self.assertTrue(d.principal.isEnabled())
        self.assertFalse(d.error.isVisible())
        d.principal.click()
        self.assertEqual(d.result(), d.DialogCode.Accepted)
        despues = self.tallas_de(pants.id)
        self.assertEqual(set(despues) - set(antes), {"EXG"})
        self.assertEqual(despues["EXG"], D(305))
        self.s.expire_all()
        notas = self.s.scalars(select(CambioCatalogo.observacion)).all()
        self.assertTrue(any(str(n or "").startswith(af.ORIGEN_FICHA) for n in notas), notas)

    def test_cancelar_no_crea_nada(self) -> None:
        pants = self.prod("Miguel Hidalgo", "Pants Suelto")
        antes = self.foto()
        d = self.abrir(fpd.TallaNuevaDialog, producto_id=pants.id, talla="EXG")
        d.cancelar.click()
        self.assertEqual(self.foto(), antes)
        self.assertIsNone(d.resultado)

    def test_precio_en_cero_bloquea(self) -> None:
        pants = self.prod("Miguel Hidalgo", "Pants Suelto")
        d = self.abrir(fpd.TallaNuevaDialog, producto_id=pants.id, talla="EXG")
        d.precio.setText("0")
        d.replanear()
        self.assertFalse(d.principal.isEnabled())
        self.assertTrue(d.bloqueo.text())

    def test_solo_admin(self) -> None:
        pants = self.prod("Miguel Hidalgo", "Pants Suelto")
        antes = self.foto()
        d = self.abrir(fpd.TallaNuevaDialog, usuario=self.caja.cajera, producto_id=pants.id, talla="EXG")
        d.principal.click()
        self.assertIsNone(d.resultado)
        self.assertIn("No se guardó nada", d.error.text())
        self.assertEqual(self.foto(), antes)


class OtroColorTests(_Base):
    def test_copia_todas_las_tallas_con_sus_precios(self) -> None:
        pants = self.prod("Miguel Hidalgo", "Pants Suelto")
        antes = self.tallas_de(pants.id)
        d = self.abrir(fpd.OtroColorDialog, producto_id=pants.id)
        self.assertFalse(d.principal.isEnabled())  # sin color elegido
        d.elegir("Gris")
        self.assertTrue(d.principal.isEnabled(), d.bloqueo.text())
        self.assertEqual(d.principal.text(), f"Crear {len(antes)} tallas en Gris")
        d.principal.click()
        self.assertEqual(d.result(), d.DialogCode.Accepted)
        self.assertEqual(self.tallas_de(pants.id, "Gris"), antes)

    def test_color_en_el_nombre_crea_otra_prenda(self) -> None:
        sueter = self.prod("Ignacio Allende", "Suéter")
        productos = self.contar(Producto)
        d = self.abrir(fpd.OtroColorDialog, producto_id=sueter.id)
        d.elegir("Azul Marino")
        d.principal.click()
        self.assertEqual(self.contar(Producto), productos + 1)
        self.s.expire_all()
        nuevo = self.s.scalar(select(Producto).order_by(Producto.id.desc()))
        self.assertIn("Azul Marino", nuevo.nombre.title())

    def test_cancelar_no_crea_nada(self) -> None:
        pants = self.prod("Miguel Hidalgo", "Pants Suelto")
        antes = self.foto()
        d = self.abrir(fpd.OtroColorDialog, producto_id=pants.id)
        d.elegir("Gris")
        d.cancelar.click()
        self.assertEqual(self.foto(), antes)

    def test_color_escrito_parecido_pregunta(self) -> None:
        pants = self.prod("Miguel Hidalgo", "Pants Suelto")
        d = self.abrir(fpd.OtroColorDialog, producto_id=pants.id)
        preguntas = []
        d.preguntar = lambda _p, rev, _c: preguntas.append(rev) or Eleccion(ACCION_USAR, "Gris")
        d.color.setEditText("gris")
        d.color.lineEdit().editingFinished.emit()
        self.assertEqual(d.color_elegido, "Gris")


class CorregirTests(_Base):
    def test_cambia_nombre_y_color_y_guarda_sku_y_precio(self) -> None:
        sueter = self.prod("Ignacio Allende", "Suéter")
        self.s.expire_all()
        antes = {v.sku: v.precio_venta for v in self.s.scalars(select(Variante).where(Variante.producto_id == sueter.id))}
        d = self.abrir(fpd.CorregirPrendaDialog, producto_id=sueter.id)
        self.assertFalse(d.principal.isEnabled())  # sin cambios
        self.assertEqual(d.nombre.text(), "Suéter Botones M Rojo")
        d.cambiar_color("Azul")
        d.replanear()
        self.assertEqual(d.nombre.text(), "Suéter Botones M Azul")
        self.assertIn("Suéter Botones M Azul Ignacio Allende", d.vista_previa.text())
        self.assertTrue(d.etiquetas.text())
        self.assertFalse(d.bajan.isVisible())
        d.principal.click()
        self.assertEqual(d.result(), d.DialogCode.Accepted)
        self.s.expire_all()
        variantes = self.s.scalars(select(Variante).where(Variante.producto_id == sueter.id)).all()
        self.assertEqual({v.sku: v.precio_venta for v in variantes}, antes)
        self.assertEqual({v.color for v in variantes}, {"Azul"})

    def test_precio_que_baja_pide_el_aviso_rojo_y_cancelar_no_cambia(self) -> None:
        sueter = self.prod("Ignacio Allende", "Suéter")
        confirmar = Mock(return_value=False)
        d = self.abrir(fpd.CorregirPrendaDialog, producto_id=sueter.id, confirmar_bajas=confirmar)
        vid, campo = next(iter(d.campos_precio.items()))
        campo.setText("289")
        d.replanear()
        self.assertIn("🔻 1 precio baja", d.bajan.text())
        d.principal.click()
        confirmar.assert_called_once()
        self.assertIsNone(d.resultado)
        self.assertEqual(self.s.get(Variante, vid).precio_venta, D(299))
        # Con el sí del aviso rojo, baja.
        confirmar.return_value = True
        d.principal.click()
        self.s.expire_all()
        self.assertEqual(self.s.get(Variante, vid).precio_venta, D(289))

    def test_solo_admin(self) -> None:
        sueter = self.prod("Ignacio Allende", "Suéter")
        d = self.abrir(fpd.CorregirPrendaDialog, usuario=self.caja.cajera, producto_id=sueter.id)
        d.nombre.setText("Suéter Botones Mujer Rojo")
        d.replanear()
        d.principal.click()
        self.assertIsNone(d.resultado)
        self.s.expire_all()
        self.assertEqual(self.s.get(Producto, sueter.id).nombre, "Suéter Botones M Rojo Ignacio Allende")

    # ── Revisión 2026-11-15 ────────────────────────────────────────────────

    def test_subtitulo_no_promete_que_los_precios_se_quedan(self) -> None:
        sueter = self.prod("Ignacio Allende", "Suéter")
        d = self.abrir(fpd.CorregirPrendaDialog, producto_id=sueter.id)
        self.assertEqual(d.sub.text(), fpd.SUB_CORREGIR)
        self.assertIn("los precios, solo si los cambias", d.sub.text())

    def test_precio_que_otra_caja_subio_no_se_regresa(self) -> None:
        sueter = self.prod("Ignacio Allende", "Suéter")
        confirmar = Mock(return_value=False)
        d = self.abrir(fpd.CorregirPrendaDialog, producto_id=sueter.id, confirmar_bajas=confirmar)
        vid = next(iter(d.campos_precio))
        self.s.get(Variante, vid).precio_venta = D(325)  # otra caja, con la ventanita abierta
        self.s.commit()
        d.cambiar_color("Azul")
        self.assertEqual(d.campos_precio[vid].text(), "325")  # el campo que no se tocó se pone al día
        self.assertFalse(d.bajan.isVisible())
        d.principal.click()
        confirmar.assert_not_called()
        self.assertEqual(d.result(), d.DialogCode.Accepted)
        self.s.expire_all()
        v = self.s.get(Variante, vid)
        self.assertEqual((v.color, v.precio_venta), ("Azul", D(325)))

    def test_varios_colores_rotula_talla_y_color(self) -> None:
        sueter = self.prod("Ignacio Allende", "Suéter")
        self.s.add(Variante(producto_id=sueter.id, sku="SKUAZUL04", talla="4", color="Azul",
                            precio_venta=D(270), stock_actual=0))
        self.s.commit()
        d = self.abrir(fpd.CorregirPrendaDialog, producto_id=sueter.id)
        rotulos = [w.text() for w in d.panel.widget().findChildren(fpd.QLabel)]
        self.assertIn("4 · Rojo", rotulos)
        self.assertIn("4 · Azul", rotulos)
        azul = self.s.scalar(select(Variante.id).where(Variante.sku == "SKUAZUL04"))
        self.assertEqual(d.campos_precio[azul].accessibleName(), "Precio 4 · Azul")

    def test_el_rojo_espera_a_que_termines_de_escribir(self) -> None:
        sueter = self.prod("Ignacio Allende", "Suéter")
        d = self.abrir(fpd.CorregirPrendaDialog, producto_id=sueter.id)
        d.plegable.setChecked(True)
        campo = next(iter(d.campos_precio.values()))
        campo.setText("3")
        campo.textEdited.emit("3")  # a medio escribir «315»
        d.replanear()  # lo que hace el rebote
        self.assertTrue(d.bajan.isHidden())
        campo.setText("289")
        campo.editingFinished.emit()  # terminó de escribir: ahora sí baja
        self.assertIn("🔻 1 precio baja", d.bajan.text())
        self.assertFalse(d.bajan.isHidden())

    def test_talla_nueva_sin_rojo_mientras_se_teclea(self) -> None:
        pants = self.prod("Miguel Hidalgo", "Pants Suelto")
        d = self.abrir(fpd.TallaNuevaDialog, producto_id=pants.id, talla="EXG")
        d.precio.setText("0")
        d.precio.textEdited.emit("0")
        d.replanear()
        self.assertEqual(d.donde.property("tono"), "")
        self.assertFalse(d.principal.isEnabled())
        d.precio.editingFinished.emit()
        self.assertEqual(d.donde.property("tono"), "danger")


class SeccionPrendaTests(_Base):
    def test_escalera_con_las_tallas_que_faltan_en_gris(self) -> None:
        pants = self.prod("Miguel Hidalgo", "Pants Suelto")
        ficha = af.leer_ficha(self.s, pants.id)
        seccion = SeccionPrenda()
        self.addCleanup(seccion.deleteLater)
        seccion.mostrar(ficha, "8")
        self.assertTrue(seccion.isVisibleTo(None) or not seccion.isHidden())
        self.assertIn("8", seccion.chips_tallas)
        self.assertEqual(seccion.chips_tallas["8"].property("actual"), "si")
        self.assertEqual(seccion.chips_faltan["EXG"].text(), "EXG ＋ $305")
        tocadas = []
        seccion.talla_tocada.connect(tocadas.append)
        seccion.chips_faltan["EXG"].click()
        self.assertEqual(tocadas, ["EXG"])
        seccion.mostrar(None)
        self.assertTrue(seccion.isHidden())

    def test_sin_hermanas_ofrece_otra_talla(self) -> None:
        sueter = self.prod("Ignacio Allende", "Suéter")
        ficha = af.leer_ficha(self.s, sueter.id)
        seccion = SeccionPrenda()
        self.addCleanup(seccion.deleteLater)
        seccion.mostrar(ficha)
        self.assertEqual(seccion.chips_faltan, {})
        self.assertFalse(seccion.boton_otra.isHidden())
        otras = []
        seccion.otra_talla.connect(otras.append)
        seccion.menu_otra.actions()[0].trigger()
        self.assertEqual(len(otras), 1)


if __name__ == "__main__":
    unittest.main()
