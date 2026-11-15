"""«Prenda general o de temporada» en la ventana «Nueva prenda» (tanda 4 del alta, 2026-11-15).

Sobre la caja en miniatura (SQLite) con la pantalla de verdad (offscreen):
el recorrido completo, «Igual que esta, otro modelo», precio por talla, lo
que falta en ámbar (no en rojo), Cancelar no crea nada, solo ADMIN y 1366×768.
"""

from __future__ import annotations

import os
import unittest
from decimal import Decimal
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QEvent, QRect
from PyQt6.QtWidgets import QApplication, QLabel, QPushButton
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from pos_uniformes.database.models import CambioCatalogo, MovimientoInventario, Producto, Variante
from pos_uniformes.services import alta_prenda_service as alta
from pos_uniformes.services.catalog_service import CatalogService
from pos_uniformes.ui.dialogs import nueva_prenda_dialog as npd
from pos_uniformes.ui.helpers import nueva_prenda_general as npg
from tests._ayuda_mini_caja import MiniCaja
from tests.test_alta_general import temporada

AREA_100 = QRect(0, 0, 1366, 728)
AREA_125 = QRect(0, 0, 1093, 574)
D = Decimal


def _procesar() -> None:
    for _ in range(3):
        QApplication.processEvents()


class _Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.engine = create_engine("sqlite://")
        self.caja = MiniCaja(self.engine)
        self.s = self.caja.s
        self.chaleco = temporada(self.caja)
        quieto = patch.object(CatalogService, "_avisar_busqueda")
        quieto.start()
        self.addCleanup(quieto.stop)
        area = patch.object(npd, "_area_disponible", return_value=AREA_100)
        area.start()
        self.addCleanup(area.stop)
        self.al_imprimir = Mock()
        self.al_terminar = Mock()

    def dialogo(self, usuario=None) -> npd.NuevaPrendaDialog:
        d = npd.NuevaPrendaDialog(
            None, session_factory=lambda: Session(self.engine, expire_on_commit=False),
            usuario_id=(usuario or self.caja.admin).id, al_imprimir=self.al_imprimir,
            al_terminar=self.al_terminar,
        )
        self.addCleanup(self._cerrar, d)
        d.tarjetas[npd.TARJETA_GENERAL].click()
        self.assertEqual(d.pasos.currentIndex(), npd.GENERAL)
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
        return {m.__name__: self.contar(m) for m in (Producto, Variante, CambioCatalogo, MovimientoInventario)}

    @staticmethod
    def llenar(d, *, nombre="Calceta Deportiva Blanca", juego="CH · MD · GD · EXG", precio="45") -> npg.FormularioGeneral:
        g = d.general
        g.escribir_nombre(nombre)
        g.elegir_juego(juego)
        g.precio.setText(precio)
        g.marca.setCurrentText("Ykan")
        g._al_marca()
        g.elegir_color("Blanco")
        g.elegir(g.tipo_prenda, "Deportivo")
        g.elegir(g.pieza, "Playera")
        g.replanear()
        return g


class RecorridoGeneralTests(_Base):
    def test_prenda_general_completa(self) -> None:
        d = self.dialogo()
        self.assertFalse(d.principal.isEnabled())
        self.assertEqual(d.bloqueo.text(), "Escribe el nombre.")
        g = self.llenar(d)
        g.campos["CH"][1].setText("12")
        g.costo.setText("20")
        g.replanear()
        self.assertTrue(d.principal.isEnabled(), d.bloqueo.text())
        self.assertEqual(d.principal.text(), "Dar de alta 4 tallas")
        self.assertIn("Calceta Deportiva Blanca", g.ficha.textos())
        d.principal.click()
        self.assertEqual(d.pasos.currentIndex(), npd.CONFIRMAR)
        self.assertEqual(d.frase.text(), "Se crean 4 tallas de Calceta Deportiva Blanca, a $45.")
        self.assertNotIn("None", d.detalle_confirmar.text())
        # «Revisar otra vez» vuelve a la pantalla general.
        next(b for b in d.secundarios if b.text() == "Revisar otra vez").click()
        self.assertEqual(d.pasos.currentIndex(), npd.GENERAL)
        d.principal.click()
        d.principal.click()
        self.assertEqual(d.pasos.currentIndex(), npd.LISTO)
        self.assertEqual(d.principal.text(), "Imprimir etiquetas")
        self.assertEqual([b.text() for b in d.secundarios], ["Ver en Inventario", "Otra prenda general"])
        self.s.expire_all()
        p = self.s.scalar(select(Producto).where(Producto.nombre == "Calceta Deportiva Blanca"))
        self.assertIsNone(p.escuela_id)
        variantes = self.s.scalars(select(Variante).where(Variante.producto_id == p.id)).all()
        self.assertEqual({(v.talla, v.color, v.precio_venta, v.costo_referencia) for v in variantes},
                         {(t, "Blanco", D(45), D(20)) for t in ("CH", "MD", "GD", "EXG")})
        self.assertEqual(sum(v.stock_actual for v in variantes), 12)
        notas = self.s.scalars(select(CambioCatalogo.observacion)).all()
        self.assertTrue(any(str(n or "").startswith(alta.ORIGEN_GENERAL) for n in notas), notas)
        # «✓ Listo → Imprimir etiquetas».
        d._pausa_hasta = 0.0
        d.principal.setEnabled(True)
        d.principal.click()
        _procesar()
        self.al_imprimir.assert_called_once()
        self.assertEqual(len(self.al_imprimir.call_args.args[0]), 4)

    def test_precio_por_talla(self) -> None:
        d = self.dialogo()
        g = self.llenar(d, juego="Infantil · Adulto")
        g.precio_por_talla(True)
        self.assertEqual(g.campos["Infantil"][0].text(), "45")  # parte del precio único
        g.campos["Adulto"][0].setText("55")
        g.replanear()
        self.assertEqual({t.talla: t.precio for t in g.plan.tallas}, {"Infantil": D(45), "Adulto": D(55)})

    def test_igual_que_esta_otro_modelo(self) -> None:
        d = self.dialogo()
        g = d.general
        g.escribir_nombre("Chaleco Mujer KY18005")
        self.assertFalse(g.caja_parecidas.isHidden())
        g.botones_parecidas[self.chaleco.id].click()
        self.assertEqual(g.juego, "Infantil · Adulto")
        self.assertEqual(g.precio.text(), "389")
        self.assertEqual((npg._texto(g.marca), npg._texto(g.tipo_prenda), npg._texto(g.pieza)),
                         ("Ykan", "Temporada", "Chaleco"))
        self.assertTrue(g.caja_parecidas.isHidden())
        self.assertFalse(g.texto_modelo.isHidden())
        self.assertFalse(d.principal.isEnabled())
        self.assertEqual(d.bloqueo.text(), "Elige el color.")  # el color se elige siempre
        g.elegir_color("Negro")
        self.assertTrue(d.principal.isEnabled(), d.bloqueo.text())
        self.assertEqual(alta.origen_bitacora(g.plan),
                         f"{alta.ORIGEN_GENERAL} · modelo: Chaleco Mujer KY17002")

    def test_lo_que_falta_va_en_ambar_no_en_rojo(self) -> None:
        d = self.dialogo()
        g = d.general
        g.escribir_nombre("Bata Blanca")
        g.elegir_juego("Unitalla")
        g.precio.setText("250")
        g.replanear()
        self.assertFalse(d.principal.isEnabled())
        self.assertTrue(d.bloqueo.text())
        self.assertTrue(g.ficha.errores.isHidden(), g.plan.errores)  # nada en rojo todavía

    def test_marca_nueva_pregunta(self) -> None:
        d = self.dialogo()
        g = self.llenar(d)
        g.confirmar_marca = Mock(return_value=True)
        g.marca.setCurrentText("Fertoni")
        g._al_marca()
        g.confirmar_marca.assert_called_once()
        self.assertTrue(d.principal.isEnabled(), d.bloqueo.text())
        g.confirmar_marca = Mock(return_value=False)
        g.marca.setCurrentText("Otra Marca")
        g._al_marca()
        self.assertEqual(npg._texto(g.marca), "")
        self.assertFalse(d.principal.isEnabled())

    def test_cancelar_no_crea_nada(self) -> None:
        antes = self.foto()
        d = self.dialogo()
        self.llenar(d)
        d.principal.click()  # a Confirmar
        d.cancelar.click()
        self.assertEqual(self.foto(), antes)

    def test_solo_admin(self) -> None:
        antes = self.foto()
        d = self.dialogo(usuario=self.caja.cajera)
        self.llenar(d)
        d.principal.click()
        d.principal.click()
        self.assertEqual(d.pasos.currentIndex(), npd.CONFIRMAR)
        self.assertIn("ADMIN", d.error_confirmar.text())
        self.assertEqual(self.foto(), antes)

    def test_otra_prenda_general_empieza_en_blanco(self) -> None:
        d = self.dialogo()
        self.llenar(d)
        d.principal.click()
        d.principal.click()
        next(b for b in d.secundarios if b.text() == "Otra prenda general").click()
        self.assertEqual(d.pasos.currentIndex(), npd.GENERAL)
        self.assertEqual(d.general.nombre.text(), "")
        self.assertIsNone(d.general.juego)

    def test_a_1366_nada_cortado(self) -> None:
        for area in (AREA_100, AREA_125):
            with patch.object(npd, "_area_disponible", return_value=area):
                d = self.dialogo()
                self.llenar(d)
                d.show()
                _procesar()
                self.assertLessEqual(d.width(), area.width())
                self.assertLessEqual(d.height(), area.height())
                g = d.general
                self.assertEqual(g.scroll.horizontalScrollBar().maximum(), 0)
                for w in g.findChildren(QPushButton) + g.findChildren(QLabel):
                    if w.isVisible() and not w.wordWrap() if isinstance(w, QLabel) else w.isVisible():
                        self.assertGreaterEqual(w.width(), w.fontMetrics().horizontalAdvance(w.text()) - 2,
                                                f"{w.text()} @ {area.width()}")
                self.assertTrue(d.principal.isVisible())
                self.assertGreaterEqual(d.principal.width(),
                                        d.principal.fontMetrics().horizontalAdvance(d.principal.text()))



class RevisionGeneralTests(_Base):
    """Revisión 2026-11-15: modelo con tallas que no son un juego, lo que dice el nombre, categoría."""

    def modelo_ch_md_gd(self, precios=(389, 389, 389)) -> Producto:
        p = Producto(nombre="Chaleco Mujer KY17000", nombre_base="Chaleco Mujer KY17000",
                     categoria_id=self.chaleco.categoria_id, marca_id=self.chaleco.marca_id,
                     tipo_prenda_id=self.chaleco.tipo_prenda_id, tipo_pieza_id=self.chaleco.tipo_pieza_id,
                     genero="Mujer")
        self.s.add(p)
        self.s.flush()
        for i, (talla, precio) in enumerate(zip(("CH", "MD", "GD"), precios), start=950):
            self.s.add(Variante(producto_id=p.id, sku=f"SKU{i:06d}", talla=talla, color="Surtido",
                                precio_venta=D(precio), stock_actual=0))
        self.s.commit()
        return p

    def test_modelo_con_tallas_que_no_son_juego_copia_sus_tallas_y_precio(self) -> None:
        modelo = self.modelo_ch_md_gd()
        d = self.dialogo()
        g = d.general
        g.elegir_juego("CH · MD · GD · EXG")  # algo ya elegido antes
        g.precio.setText("450")
        g.escribir_nombre("Chaleco Mujer KY18005")
        g.botones_parecidas[modelo.id].click()
        self.assertEqual(g.juego, npg.JUEGO_MODELO)
        self.assertEqual(g.tallas_elegidas(), ["CH", "MD", "GD"])
        self.assertEqual(g.boton_modelo.text(), "Como el modelo: CH · MD · GD")
        self.assertTrue(g.boton_modelo.isChecked())
        self.assertEqual(g.precio.text(), "389")
        g.elegir_color("Negro")
        self.assertEqual({t.talla: t.precio for t in g.plan.tallas}, {"CH": D(389), "MD": D(389), "GD": D(389)})
        self.assertTrue(d.principal.isEnabled(), d.bloqueo.text())
        # «Quitar» el modelo: sus tallas ya no valen.
        g.quitar_modelo.click()
        self.assertIsNone(g.juego)
        self.assertTrue(g.boton_modelo.isHidden())
        self.assertEqual(g.plan.tallas, [])

    def test_modelo_con_precios_distintos_los_pone_por_talla(self) -> None:
        modelo = self.modelo_ch_md_gd((389, 389, 409))
        d = self.dialogo()
        g = d.general
        g.escribir_nombre("Chaleco Mujer KY18005")
        g.botones_parecidas[modelo.id].click()
        self.assertTrue(g.por_talla)
        g.elegir_color("Negro")
        self.assertEqual({t.talla: t.precio for t in g.plan.tallas}, {"CH": D(389), "MD": D(389), "GD": D(409)})

    def test_el_nombre_propone_pieza_genero_y_tipo(self) -> None:
        d = self.dialogo()
        g = d.general
        g.escribir_nombre("Chaleco Mujer KY99999")
        self.assertEqual((npg._texto(g.pieza), npg._texto(g.genero), npg._texto(g.tipo_prenda)),
                         ("Chaleco", "Mujer", "Temporada"))
        self.assertEqual(npg._texto(g.color), "")  # el color no se adivina
        # Lo elegido a mano ya no se toca; lo demás sigue al nombre.
        g.elegir(g.pieza, "Suéter")
        g.escribir_nombre("Chaleco Unisex KY99999")
        self.assertEqual((npg._texto(g.pieza), npg._texto(g.genero)), ("Suéter", "Unisex"))

    def test_la_categoria_va_plegada_y_sale_sola(self) -> None:
        d = self.dialogo()
        g = self.llenar(d)
        self.assertTrue(g.categoria.isHidden())
        self.assertIn("Deportivo", g.nota_categoria.text())  # «Categoría: …, sale sola del tipo de prenda.»
        g.boton_categoria.click()
        self.assertFalse(g.categoria.isHidden())

    def test_nota_al_pie_sin_mayusculas_a_media_frase(self) -> None:
        d = self.dialogo()
        textos = [w.text() for w in d.general.findChildren(QLabel)]
        self.assertIn(npg.NOTA_PIE, textos)
        self.assertNotIn("LLEGAN HOY y COSTO", npg.NOTA_PIE)


if __name__ == "__main__":
    unittest.main()
