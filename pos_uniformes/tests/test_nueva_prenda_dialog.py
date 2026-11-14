"""La ventana «Nueva prenda» (tanda 3 del alta, 2026-11-13).

Se prueba sobre la caja en miniatura (SQLite) con la pantalla de verdad
(offscreen): el recorrido completo crea lo mismo que el plan del motor,
Cancelar no crea nada, varias escuelas de una vez, «¿Quisiste decir…?» en el
color, el $0 bloqueado, el formulario anterior sigue alcanzable y nada se
corta a 1366×768.
"""

from __future__ import annotations

import os
import unittest
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QEvent
from PyQt6.QtWidgets import QAbstractButton, QApplication, QCheckBox, QLabel, QMessageBox, QPushButton, QToolButton
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from pos_uniformes.database.models import CambioCatalogo, Producto, RolUsuario, UniformePieza, Variante
from pos_uniformes.services import alta_prenda_service as alta
from pos_uniformes.services.catalog_service import CatalogService
from pos_uniformes.ui.dialogs import nueva_prenda_dialog as npd
from pos_uniformes.ui.dialogs.quisiste_decir_dialog import ACCION_CORREGIR, ACCION_USAR, Eleccion
from pos_uniformes.ui.helpers import nueva_prenda_abrir
from tests._ayuda_mini_caja import ESCALERAS, MiniCaja

JARAL = "Ignacio Allende (Jaral)"
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
        quieto = patch.object(CatalogService, "_avisar_busqueda")
        quieto.start()
        self.addCleanup(quieto.stop)
        self.al_terminar = Mock()
        self.al_imprimir = Mock()
        self.al_ver = Mock()
        self.al_anterior = Mock()

    def dialogo(self, usuario=None) -> npd.NuevaPrendaDialog:
        d = npd.NuevaPrendaDialog(
            None,
            session_factory=lambda: Session(self.engine, expire_on_commit=False),
            usuario_id=(usuario or self.caja.admin).id,
            al_imprimir=self.al_imprimir, al_ver=self.al_ver,
            al_formulario_anterior=self.al_anterior, al_terminar=self.al_terminar,
        )
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
        return {m.__name__: self.contar(m) for m in (Producto, Variante, UniformePieza, CambioCatalogo)}

    @staticmethod
    def escuela(d, nombre: str, nivel: str = "Primaria"):
        return next(e for e in d.escuelas if e.nombre == nombre and e.nivel == nivel)

    def a_principal(self, d, escuela: str = JARAL, pieza: str = "Pants Suelto") -> None:
        d.tarjetas[npd.TARJETA_ESCUELA].click()
        self.assertEqual(d.pasos.currentIndex(), npd.ESCUELA)
        d.elegir_escuela(self.escuela(d, escuela))
        self.assertEqual(d.pasos.currentIndex(), npd.FALTA)
        boton = d.botones_falta.get(pieza)
        if boton is not None:
            boton.click()
        else:
            d.elegir_pieza(pieza)
        self.assertEqual(d.pasos.currentIndex(), npd.PRINCIPAL)


class RecorridoTests(_Base):
    def test_flujo_completo_crea_lo_mismo_que_el_plan(self) -> None:
        esperado = alta.planear_desde_modelo(self.s, JARAL, "Pants Suelto")
        self.s.rollback()
        d = self.dialogo()
        self.a_principal(d)
        self.assertEqual(d.principal.text(), "Dar de alta 10 tallas")
        self.assertTrue(d.principal.isEnabled())
        self.assertIn("Pants Suelto Ignacio Allende (Jaral)", d.ficha.textos())
        self.assertIn("10 tallas · $245 a $295", d.ficha.textos())
        self.assertIn("Queda en su uniforme: Deportivo", d.ficha.textos())
        self.assertIn("igual en 3 escuelas de primaria", d.modelo.text())

        d.principal.click()
        self.assertEqual(d.pasos.currentIndex(), npd.CONFIRMAR)
        self.assertEqual(d.frase.text(), esperado.resumen)
        d.principal.click()  # «Sí, dar de alta»
        self.assertEqual(d.pasos.currentIndex(), npd.LISTO, d.error_confirmar.text())
        self.al_terminar.assert_called_once()

        producto = self.s.scalar(select(Producto).where(Producto.nombre == esperado.nombre))
        self.assertIsNotNone(producto)
        tallas = {v.talla: v.precio_venta for v in producto.variantes}
        self.assertEqual(tallas, {t.talla: t.precio for t in esperado.tallas})
        self.assertEqual({v.color for v in producto.variantes}, {esperado.color})
        self.assertEqual(sorted(v.sku for v in producto.variantes), sorted(esperado.skus_previstos))
        liga = self.s.scalar(select(UniformePieza).where(UniformePieza.producto_id == producto.id))
        self.assertEqual(liga.grupo, "Deportivo")
        bitacora = self.s.scalars(select(CambioCatalogo.observacion).where(
            CambioCatalogo.entidad_id == producto.id)).all()
        self.assertTrue(any("Alta desde POS · modelo:" in (o or "") for o in bitacora))
        self.assertIn("10 tallas de Pants Suelto Ignacio Allende (Jaral), de $245 a $295.", d.texto_listo.text())

        # [Imprimir etiquetas] manda las tallas creadas.
        ids = d.variantes_creadas()
        d.principal.click()
        _procesar()
        self.al_imprimir.assert_called_once_with(ids)
        self.assertEqual(len(ids), 10)

    def test_cancelar_no_crea_nada(self) -> None:
        antes = self.foto()
        d = self.dialogo()
        self.a_principal(d)
        d.principal.click()
        self.assertEqual(d.pasos.currentIndex(), npd.CONFIRMAR)
        d.secundarios[0].click()  # «Revisar otra vez»
        self.assertEqual(d.pasos.currentIndex(), npd.PRINCIPAL)
        d.cancelar.click()
        self.assertEqual(self.foto(), antes)
        self.al_terminar.assert_not_called()

    def test_varias_escuelas_de_una_vez(self) -> None:
        antes = self.contar(Producto)
        d = self.dialogo()
        self.a_principal(d, pieza="Chaleco")
        self.assertIn("le falta a 3 de primaria", d.otras.text())
        d.marcar_otra_escuela("Miguel Hidalgo")
        d.marcar_otra_escuela("Justo Sierra")
        self.assertEqual(d.principal.text(), "Dar de alta 3 prendas (21 tallas)")
        self.assertIn("También para 2 escuelas más", d.ficha.textos())
        d.principal.click()
        self.assertIn("una para cada escuela: Ignacio Allende (Jaral), Justo Sierra y Miguel Hidalgo", d.frase.text())
        d.principal.click()
        self.assertEqual(d.pasos.currentIndex(), npd.LISTO, d.error_confirmar.text())
        self.assertEqual(self.contar(Producto), antes + 3)
        nombres = set(self.s.scalars(select(Producto.nombre).where(Producto.nombre.like("Chaleco Rojo %"))).all())
        self.assertEqual(nombres, {"Chaleco Rojo Ignacio Allende", "Chaleco Rojo Ignacio Allende (Jaral)",
                                   "Chaleco Rojo Miguel Hidalgo", "Chaleco Rojo Justo Sierra"})
        skus = d.resultado.skus
        self.assertEqual(len(skus), len(set(skus)))
        self.assertEqual(len(skus), 21)

    def test_color_con_quisiste_decir(self) -> None:
        d = self.dialogo()
        preguntas = []
        d.preguntar = lambda _p, rev, _c: preguntas.append(rev) or Eleccion(ACCION_USAR, "Blanco")
        self.a_principal(d, pieza="Chaleco")
        self.assertEqual(d.plan.nombre, "Chaleco Rojo Ignacio Allende (Jaral)")
        d.color.setEditText("blanca")
        d.color.lineEdit().editingFinished.emit()
        self.assertEqual(len(preguntas), 1)
        self.assertEqual(preguntas[0].valor, "Blanco")
        self.assertEqual(d.plan.color, "Blanco")
        self.assertEqual(d.plan.nombre, "Chaleco Blanco Ignacio Allende (Jaral)")
        self.assertIn("Chaleco Blanco Ignacio Allende (Jaral)", d.ficha.textos())
        # «Corregir» deja el color como estaba.
        d.preguntar = lambda *_a: Eleccion(ACCION_CORREGIR)
        d.color.setEditText("Azulx")
        d.color.lineEdit().editingFinished.emit()
        self.assertEqual(d.plan.color, "Blanco")
        self.assertEqual(d.color.currentText(), "Blanco")
        # Un color de la lista no pregunta nada.
        d.preguntar = Mock()
        d.color.setEditText("Azul")
        d.color.lineEdit().editingFinished.emit()
        d.preguntar.assert_not_called()
        self.assertEqual(d.plan.nombre, "Chaleco Azul Ignacio Allende (Jaral)")

    def test_precio_en_cero_o_vacio_bloquea(self) -> None:
        d = self.dialogo()
        self.a_principal(d)
        fila = d.tabla.filas["4"]
        fila.precio.setText("0")
        fila.precio.editingFinished.emit()
        self.assertFalse(d.principal.isEnabled())
        self.assertEqual(d.bloqueo.text(), "La talla 4 está en $0.")
        self.assertEqual(fila.precio.property("estado"), "error")
        d.principal.click()
        self.assertEqual(d.pasos.currentIndex(), npd.PRINCIPAL)
        fila.precio.setText("")
        fila.precio.editingFinished.emit()
        self.assertEqual(d.bloqueo.text(), "Falta precio en 1 talla.")
        fila.precio.setText("245")
        fila.precio.editingFinished.emit()
        self.assertTrue(d.principal.isEnabled())
        self.assertEqual(d.bloqueo.text(), "")
        self.assertEqual(fila.donde.text(), "como las demás")

    def test_precio_mas_bajo_avisa_y_deja_y_sugerencia_5_9(self) -> None:
        d = self.dialogo()
        self.a_principal(d)
        fila = d.tabla.filas["GD"]
        fila.precio.setText("290")
        fila.precio.editingFinished.emit()
        self.assertTrue(d.principal.isEnabled())
        self.assertEqual(fila.donde.property("tono"), "warning")
        self.assertIn("más bajo", fila.donde.text())
        self.assertFalse(fila.sugerencia.isHidden())
        self.assertEqual(fila.sugerencia.text(), "¿$295?")
        fila.sugerencia.click()
        self.assertEqual(d.plan.tallas[-1].precio, D(295))
        self.assertEqual(fila.donde.text(), "como las demás")
        self.assertTrue(fila.sugerencia.isHidden())

    def test_talla_que_no_trae_el_modelo_se_marca(self) -> None:
        d = self.dialogo()
        self.a_principal(d)
        exg = d.tabla.filas["EXG"]
        self.assertFalse(exg.marca.isChecked())
        self.assertEqual(exg.donde.text(), "la tienen 1 de 4")
        self.assertFalse(exg.precio.isEnabled())
        exg.marca.setChecked(True)
        self.assertEqual(d.principal.text(), "Dar de alta 11 tallas")
        self.assertEqual(d.plan.tallas[-1].talla, "EXG")
        d.tabla.filas["4"].marca.setChecked(False)
        self.assertEqual(d.principal.text(), "Dar de alta 10 tallas")
        self.assertNotIn("4", [t.talla for t in d.plan.tallas])

    def test_llegan_entra_como_entrada(self) -> None:
        d = self.dialogo()
        self.a_principal(d)
        d.tabla.filas["10"].llegan.setText("5")
        d.tabla.filas["10"].llegan.editingFinished.emit()
        self.assertIn("Llegan 5 piezas", d.ficha.textos())
        d.principal.click()
        d.principal.click()
        self.assertEqual(d.pasos.currentIndex(), npd.LISTO, d.error_confirmar.text())
        v = self.s.scalar(select(Variante).join(Producto).where(
            Producto.nombre == "Pants Suelto Ignacio Allende (Jaral)", Variante.talla == "10"))
        self.assertEqual(v.stock_actual, 5)

    def test_otra_igual_desde_ultimas_altas(self) -> None:
        d = self.dialogo()
        ultima = d.ultimas[0]
        d._hacer_otra_igual(ultima)
        self.assertEqual(d.pasos.currentIndex(), npd.ESCUELA)
        d.elegir_escuela(self.escuela(d, "Miguel Hidalgo"))
        self.assertEqual(d.pasos.currentIndex(), npd.PRINCIPAL)
        self.assertEqual(d.plan.modelo_id, ultima.producto_id)

    def test_listo_otra_prenda_y_misma_pieza_para_otra(self) -> None:
        d = self.dialogo()
        self.a_principal(d)
        d.principal.click()
        d.principal.click()
        textos = [b.text() for b in d.secundarios]
        self.assertEqual(textos, ["Ver en Inventario", "Esta misma pieza para otra escuela",
                                  "Otra prenda para esta escuela"])
        d.secundarios[2].click()
        self.assertEqual(d.pasos.currentIndex(), npd.FALTA)
        self.assertNotIn("Pants Suelto", d.botones_falta)  # ya lo tiene
        creado = d.resultado.productos[0].producto_id
        d._ir(npd.LISTO)
        d.secundarios[1].click()
        self.assertEqual(d.pasos.currentIndex(), npd.ESCUELA)
        self.assertEqual(d.modelo_forzado, creado)

    def test_escuela_sin_prendas_pide_nivel(self) -> None:
        self.caja._escuela("Rancho Nuevo")
        self.s.commit()
        d = self.dialogo()
        d.tarjetas[npd.TARJETA_ESCUELA].click()
        d.buscar.setText("rancho")
        self.assertEqual(d.lista.count(), 1)
        d._elegir_primera()
        self.assertEqual(d.pasos.currentIndex(), npd.FALTA)
        self.assertEqual(d.sub.text(), "¿De qué nivel es la prenda?")
        d._elegir_nivel("Primaria")
        self.assertIn("Pants Suelto", d.botones_falta)

    def test_buscador_sin_acentos(self) -> None:
        d = self.dialogo()
        d.tarjetas[npd.TARJETA_ESCUELA].click()
        d.buscar.setText("IGNACIO jaral")
        self.assertEqual(d.lista.count(), 1)
        self.assertIn("Primaria · 4 prendas", d.lista.item(0).text())


class PuertaTests(_Base):
    def test_tres_tarjetas_y_el_formulario_anterior(self) -> None:
        d = self.dialogo()
        self.assertEqual(d.pasos.currentIndex(), npd.PUERTA)
        self.assertEqual([t.titulo.text() for t in d.tarjetas.values()],
                         ["Prenda para una escuela", "Escuela igual a otra", "Prenda general o de temporada"])
        d.tarjetas[npd.TARJETA_IGUAL].click()
        self.assertFalse(d.nota_puerta.isHidden())
        self.assertEqual(d.pasos.currentIndex(), npd.PUERTA)
        d.tarjetas[npd.TARJETA_GENERAL].click()
        _procesar()
        self.al_anterior.assert_called_once_with()

    def test_solo_admin(self) -> None:
        ventana = SimpleNamespace(current_role=RolUsuario.CAJERO, user_id=self.caja.cajera.id)
        with patch.object(QMessageBox, "warning") as aviso:
            self.assertIsNone(nueva_prenda_abrir.abrir_nueva_prenda(ventana))
        aviso.assert_called_once()

    def test_abrir_desde_inventario_conecta_con_la_ventana(self) -> None:
        ventana = Mock()
        ventana.current_role = RolUsuario.ADMIN
        ventana.user_id = self.caja.admin.id
        with patch.object(npd, "NuevaPrendaDialog") as clase:
            nueva_prenda_abrir.abrir_nueva_prenda(ventana, session_factory=Mock())
        clase.return_value.open.assert_called_once_with()
        self.assertEqual(clase.call_args.kwargs["usuario_id"], self.caja.admin.id)
        d = SimpleNamespace(**clase.call_args.kwargs)
        d.al_formulario_anterior()
        ventana._handle_create_product.assert_called_once_with()
        d.al_imprimir([7])
        ventana._open_inventory_label_dialog_for_variant.assert_called_once_with(7)
        d.al_imprimir([7, 8])
        ventana._handle_inventory_print_label_batch.assert_called_once_with([7, 8])
        resultado = alta.ResultadoAlta(productos=(alta.ProductoCreado(
            5, "Pants Suelto Jaral", "Jaral", (alta.TallaCreada(9, "SKU9", "4", "Gris", D(245)),)),))
        d.al_ver(resultado)
        ventana.inventory_search_input.setText.assert_called_once_with("Pants Suelto Jaral")
        ventana.inventario_pantalla.seleccionar.assert_called_once_with(9)
        d.al_terminar(resultado)
        ventana.refresh_all.assert_called_once_with()

    def test_una_cajera_no_puede_guardar(self) -> None:
        antes = self.contar(Producto)
        d = self.dialogo(usuario=self.caja.cajera)
        self.a_principal(d)
        d.principal.click()
        d.principal.click()
        self.assertEqual(d.pasos.currentIndex(), npd.CONFIRMAR)
        self.assertIn("solo un ADMIN", d.error_confirmar.text())
        self.assertEqual(self.contar(Producto), antes)


class TamanoTests(_Base):
    def _cortados(self, d) -> list[str]:
        cortados = []
        for w in d.findChildren((QLabel, QAbstractButton)):
            if not w.isVisibleTo(d) or not w.isVisible():
                continue
            if isinstance(w, QLabel) and (w.wordWrap() or not w.text()):
                continue
            texto = w.text()
            if not texto or "\n" in texto:
                continue
            ancho = w.fontMetrics().horizontalAdvance(texto)
            extra = 24 if isinstance(w, QCheckBox) else 0
            if w.width() + 1 < ancho + extra:
                cortados.append(f"{texto!r} {w.width()} < {ancho + extra}")
        return cortados

    def test_a_1366_nada_cortado(self) -> None:
        d = self.dialogo()
        self.assertLessEqual(d.width(), 1366)
        self.assertLessEqual(d.height(), 768 - 40)  # la barra de Windows
        d.show()
        _procesar()
        self.assertEqual(self._cortados(d), [], "puerta")
        self.a_principal(d, pieza="Chaleco")
        d.marcar_otra_escuela("Miguel Hidalgo")
        d.mas_datos.setChecked(True)
        _procesar()
        self.assertEqual(self._cortados(d), [], "principal")
        self.assertEqual(d.scroll_principal.horizontalScrollBar().maximum(), 0)
        for paso in (npd.ESCUELA, npd.FALTA):
            d._ir(paso)
            _procesar()
            self.assertEqual(self._cortados(d), [], paso)
        d._ir(npd.PRINCIPAL)
        d.principal.click()
        _procesar()
        self.assertEqual(self._cortados(d), [], "confirmar")
        d.principal.click()
        _procesar()
        self.assertEqual(d.pasos.currentIndex(), npd.LISTO)
        self.assertEqual(self._cortados(d), [], "listo")


if __name__ == "__main__":
    unittest.main()
