"""«Escuela igual a otra» en la ventana «Nueva prenda» (tanda 5 del alta, 2026-11-15).

Sobre la caja en miniatura (SQLite) con la pantalla de verdad (offscreen):
el recorrido crea lo mismo que el plan del servicio, Cancelar no crea nada,
solo ADMIN, «¿Es la misma que…?» antes de crear una escuela, y nada se corta
a 1366×768 al 100 % ni al 125 %.
"""

from __future__ import annotations

import os
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QAbstractButton, QCheckBox, QLabel
from sqlalchemy import select

from pos_uniformes.database.models import CambioCatalogo, Escuela, Producto, Variante
from pos_uniformes.services import copiar_escuela_service as ce
from pos_uniformes.ui.dialogs import nueva_prenda_dialog as npd
from pos_uniformes.ui.dialogs.quisiste_decir_dialog import ACCION_USAR, Eleccion
from pos_uniformes.ui.styles import nueva_prenda_styles as nps_estilos
from tests.test_nueva_prenda_dialog import AREA_100, AREA_125, _Base, _procesar

ORIGEN = "Ignacio Allende"
JARAL = "Ignacio Allende (Jaral)"
RANCHO = "Ignacio Allende Rancho Nuevo"


class _BaseCopia(_Base):
    def escuela(self, d, nombre: str):  # noqa: D401 - las de «Escuela igual a otra»
        return next(e for e in d.copia.escuelas if e.nombre == nombre)

    def a_lista(self, d, destino: str = JARAL) -> None:
        d.tarjetas[npd.TARJETA_IGUAL].click()
        self.assertEqual(d.pasos.currentIndex(), npd.COPIAR_ESCUELAS)
        self.assertFalse(d.principal.isEnabled())
        d.copia.col_origen.buscar.setText("allende")
        self.assertEqual(d.copia.col_origen.lista.count(), 2)  # sin acentos ni mayúsculas
        d.copia.elegir_origen(self.escuela(d, ORIGEN))
        d.copia.elegir_destino(self.escuela(d, destino))
        self.assertTrue(d.principal.isEnabled(), d.bloqueo.text())
        self.assertEqual(d.principal.text(), "Ver las prendas")
        d.principal.click()
        self.assertEqual(d.pasos.currentIndex(), npd.COPIAR)


class RecorridoCopiaTests(_BaseCopia):
    def test_flujo_completo_crea_lo_mismo_que_el_plan(self) -> None:
        chaleco = self.caja.productos[(ORIGEN, "Chaleco")].id
        esperado = ce.planear_copia(self.s, ORIGEN, JARAL, colores={"Rojo": "Azul"}, color_de={chaleco: "Blanco"})
        self.s.rollback()
        d = self.dialogo()
        self.a_lista(d)
        c = d.copia
        estados = {f.nombre.text(): f.estado.text() for f in c.filas.values()}
        self.assertEqual(estados["Pants Suelto"], "NUEVA")
        self.assertEqual(estados["Pants 2pz Deportivo"], "YA ESTÁ")
        # Para todas y prenda por prenda.
        c.cambiar_color_todas("Rojo", "Azul")
        c.cambiar_color_de(chaleco, "Blanco")
        self.assertEqual(c.fila("Suéter Botones M Rojo").nombre.text(), "Suéter Botones M Azul")
        self.assertEqual(c.fila("Chaleco Rojo").nombre.text(), "Chaleco Blanco")
        self.assertEqual(d.principal.text(), "Copiar 3 prendas (24 tallas)")
        self.assertIn("3 prendas nuevas", c.ficha.rango.text())
        d.principal.click()
        self.assertEqual(d.pasos.currentIndex(), npd.CONFIRMAR)
        self.assertEqual(d.frase.text(), esperado.resumen())
        d.principal.click()  # «Sí, copiar»
        self.assertEqual(d.pasos.currentIndex(), npd.LISTO, d.error_confirmar.text())
        _procesar()
        self.al_terminar.assert_called_once()
        self.assertIn("quedó igual que Ignacio Allende", d.texto_listo.text())
        self.s.expire_all()
        for plan in esperado.planes:
            producto = self.s.scalar(select(Producto).where(Producto.nombre == plan.nombre))
            self.assertIsNotNone(producto, plan.nombre)
            self.assertEqual({v.talla: v.precio_venta for v in producto.variantes},
                             {t.talla: t.precio for t in plan.tallas})
            self.assertEqual({v.stock_actual for v in producto.variantes}, {0})
        nota = self.s.scalar(select(CambioCatalogo.observacion).where(
            CambioCatalogo.entidad_id == self.s.scalar(select(Producto.id).where(
                Producto.nombre == f"Chaleco Blanco {JARAL}"))))
        self.assertTrue(nota.startswith(f"Copia de escuela: {ORIGEN} → {JARAL}"))
        # Imprimir etiquetas: las tallas nuevas.
        self.assertEqual(len(d.variantes_creadas()), 24)
        d._fin_pausa_listo()
        d.principal.click()
        _procesar()
        self.al_imprimir.assert_called_once()

    def test_desmarcar_y_cambia_color(self) -> None:
        d = self.dialogo()
        self.a_lista(d)
        c = d.copia
        c.fila("Suéter Botones M Rojo").casilla.setChecked(False)
        self.assertEqual(c.fila("Suéter Botones M Rojo").estado.property("estado"), "fuera")
        playera = self.caja.productos[(ORIGEN, "Playera")].id
        c.cambiar_color_de(playera, "Azul")
        self.assertEqual(c.fila("Playera Deportiva").estado.text(), "CAMBIA COLOR")
        self.assertIn("Gris → Azul", c.fila("Playera Deportiva").detalle.text())
        self.assertIn("Gris → Azul", c.ficha.llegan.text())
        self.assertEqual(d.principal.text(), "Copiar 2 prendas (17 tallas)")

    def test_color_escrito_pasa_por_quisiste_decir(self) -> None:
        preguntas = []

        def preguntar(_padre, revision, _crear):
            preguntas.append(revision.escrito)
            return Eleccion(ACCION_USAR, "Gris")

        d = self.dialogo()
        d.preguntar = preguntar
        self.a_lista(d)
        combo = d.copia.combos_todas["Rojo"]
        combo.setEditText("Grisz")
        combo.lineEdit().editingFinished.emit()
        self.assertEqual(preguntas, ["Grisz"])
        self.assertEqual(d.copia.plan.color_para_todas("Rojo"), "Gris")

    def test_cancelar_no_crea_nada(self) -> None:
        antes = self.foto()
        d = self.dialogo()
        self.a_lista(d)
        d.copia.cambiar_color_todas("Rojo", "Azul")
        d.principal.click()
        self.assertEqual(d.pasos.currentIndex(), npd.CONFIRMAR)
        d.cancelar.click()
        self.assertEqual(self.foto(), antes)

    def test_atras_vuelve_a_las_escuelas(self) -> None:
        d = self.dialogo()
        self.a_lista(d)
        d.atras.click()
        self.assertEqual(d.pasos.currentIndex(), npd.COPIAR_ESCUELAS)
        d.atras.click()
        self.assertEqual(d.pasos.currentIndex(), npd.PUERTA)


class EscuelaNuevaTests(_BaseCopia):
    def _preguntar(self, d, texto: str = RANCHO) -> None:
        d.tarjetas[npd.TARJETA_IGUAL].click()
        d.copia.elegir_origen(self.escuela(d, ORIGEN))
        d.copia.col_destino.buscar.setText(texto)
        self.assertFalse(d.copia.boton_nueva.isHidden())
        d.copia.boton_nueva.click()
        self.assertFalse(d.copia.panel_misma.isHidden())
        self.assertFalse(d.principal.isEnabled())
        self.assertEqual(d.bloqueo.text(), "Contesta si es la misma escuela.")

    def test_es_la_misma_usa_la_que_existe(self) -> None:
        d = self.dialogo()
        self._preguntar(d)
        self.assertEqual(list(d.copia.botones_misma), [JARAL])  # la de origen no se ofrece
        d.copia.botones_misma[JARAL].click()
        self.assertEqual(d.copia.destino.nombre, JARAL)
        self.assertTrue(d.principal.isEnabled())

    def test_es_otra_crea_la_escuela(self) -> None:
        d = self.dialogo()
        self._preguntar(d)
        d.copia.boton_es_otra.click()
        self.assertIn("escuela nueva", d.copia.col_destino.elegida_texto.text())
        d.principal.click()
        self.assertEqual(d.pasos.currentIndex(), npd.COPIAR)
        self.assertEqual(d.principal.text(), "Copiar 7 prendas (64 tallas)")
        self.assertIn("escuela nueva", d.copia.ficha.sub.text())
        d.principal.click()
        self.assertTrue(d.frase.text().startswith(f"Se crea la escuela {RANCHO}"))
        d.principal.click()
        self.assertEqual(d.pasos.currentIndex(), npd.LISTO, d.error_confirmar.text())
        self.s.expire_all()
        self.assertIsNotNone(self.s.scalar(select(Escuela).where(Escuela.nombre == RANCHO)))

    def test_escribir_otra_cosa_olvida_la_nueva(self) -> None:
        d = self.dialogo()
        self._preguntar(d)
        d.copia.boton_es_otra.click()
        d.copia.col_destino.buscar.setText("Otra")
        self.assertFalse(d.copia.nueva_confirmada)
        self.assertFalse(d.principal.isEnabled())


class SoloAdminTests(_BaseCopia):
    def test_una_cajera_no_entra(self) -> None:
        d = self.dialogo(usuario=self.caja.cajera)
        d.tarjetas[npd.TARJETA_IGUAL].click()
        self.assertEqual(d.pasos.currentIndex(), npd.PUERTA)
        self.assertFalse(d.nota_puerta.isHidden())
        self.assertIn("Solo un ADMIN", d.nota_puerta.text())
        # Tampoco le sale «es una escuela nueva».
        d.copia.col_destino.buscar.setText(RANCHO)
        self.assertTrue(d.copia.boton_nueva.isHidden())

    def test_si_deja_de_ser_admin_no_guarda(self) -> None:
        antes = self.foto()
        d = self.dialogo()
        self.a_lista(d)
        d.copia.cambiar_color_todas("Rojo", "Azul")
        d.principal.click()
        d.usuario_id = self.caja.cajera.id
        d.principal.click()
        self.assertEqual(d.pasos.currentIndex(), npd.CONFIRMAR)
        self.assertIn("solo un ADMIN", d.error_confirmar.text())
        self.assertEqual(self.foto(), antes)


class TamanoCopiaTests(_BaseCopia):
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

    def _recorrer(self, d, area) -> None:
        def revisar(nombre: str) -> None:
            _procesar()
            self.assertLessEqual(d.frameGeometry().height(), area.height(), nombre)
            if d.principal.isVisible():
                abajo = d.principal.mapTo(d, d.principal.rect().bottomLeft()).y()
                self.assertLessEqual(abajo, d.height(), nombre)
            self.assertEqual(self._cortados(d), [], nombre)

        d.show()
        _procesar()
        d.tarjetas[npd.TARJETA_IGUAL].click()
        d.copia.elegir_origen(self.escuela(d, ORIGEN))
        d.copia.col_destino.buscar.setText(RANCHO)
        d.copia.boton_nueva.click()
        revisar("es la misma")
        d.copia.botones_misma[JARAL].click()
        revisar("escuelas")
        d.principal.click()
        playera = self.caja.productos[(ORIGEN, "Playera")].id
        d.copia.cambiar_color_todas("Rojo", "Azul")
        d.copia.cambiar_color_de(playera, "Blanco")
        revisar("lista")
        self.assertEqual(d.copia.scroll_lista.horizontalScrollBar().maximum(), 0)
        d.principal.click()
        revisar("confirmar")
        d.principal.click()
        self.assertEqual(d.pasos.currentIndex(), npd.LISTO)
        revisar("listo")

    def test_a_1366_al_100(self) -> None:
        d = self.dialogo()
        self.assertLessEqual(d.width() + nps_estilos.MARCO_ANCHO, AREA_100.width())
        self._recorrer(d, AREA_100)

    def test_a_1366_al_125(self) -> None:
        self.area.stop()
        area = patch.object(npd, "_area_disponible", return_value=AREA_125)
        area.start()
        self.addCleanup(area.stop)
        d = self.dialogo()
        self._recorrer(d, AREA_125)

