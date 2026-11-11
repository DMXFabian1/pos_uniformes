"""El buzón se porta como un chat de verdad cuando llega un mensaje.

Daniel, 2026-11-06: «cuando llega un mensaje nuevo, se va hasta arriba la
barra, y tengo que bajar manualmente para ver el nuevo mensaje». Cada mensaje
borraba y repintaba toda la conversación, y bajaba antes de que el layout
terminara. Las reglas de ahora son las de Signal Desktop: si estás abajo, lo
nuevo te sigue; si estás leyendo arriba, no se te mueve nada y un botón dice
cuántos llegaron.
"""

from __future__ import annotations

from PyQt6.QtWidgets import QApplication, QLabel, QToolButton

from pos_uniformes.services import buzon_service as bz
from pos_uniformes.tests.test_buzon_dialog import _ConBase


def _asentar() -> None:
    for _ in range(4):
        QApplication.processEvents()


class SeguirLoNuevoTests(_ConBase):
    def _larga(self, yo: str = "Caja"):
        for i in range(40):
            self._mandar(f"mensaje {i}", de="Entrada")
        d = self._ventana(yo)
        d.resize(1000, 500)
        d.show()
        self.addCleanup(d.close)  # cada prueba cierra lo que abre
        _asentar()
        return d, d._scroll.verticalScrollBar()

    def test_abre_al_final_de_la_conversacion(self) -> None:
        d, barra = self._larga()
        self.assertGreater(barra.maximum(), 0)
        self.assertEqual(barra.value(), barra.maximum())
        self.assertFalse(d.ir_abajo.isVisible())

    def test_estando_abajo_lo_nuevo_se_ve_solo(self) -> None:
        d, barra = self._larga()
        antes = barra.maximum()
        self._mandar("el que acaba de llegar", de="Entrada")
        d.refrescar()
        _asentar()
        self.assertGreater(barra.maximum(), antes)
        self.assertEqual(barra.value(), barra.maximum())          # antes se iba a 0
        self.assertFalse(d.ir_abajo.isVisible())

    def test_no_se_repinta_lo_que_ya_estaba(self) -> None:
        d, _ = self._larga()
        primera = d._mensajes.findChildren(QLabel, "cuerpo")[0]
        self._mandar("otro", de="Entrada")
        d.refrescar()
        _asentar()
        self.assertIs(d._mensajes.findChildren(QLabel, "cuerpo")[0], primera)   # la misma burbuja
        self.assertEqual(self._textos(d)[-1], "otro")
        self.assertEqual(self._textos(d).count("mensaje 0"), 1)

    def test_leyendo_arriba_no_se_mueve_y_el_boton_dice_cuantos(self) -> None:
        d, barra = self._larga()
        barra.setValue(40)
        _asentar()
        self.assertTrue(d.ir_abajo.isVisible())
        self.assertEqual(d.ir_abajo.text(), "↓")
        self._mandar("uno", de="Entrada")
        self._mandar("dos", de="Entrada")
        d.refrescar()
        _asentar()
        self.assertEqual(barra.value(), 40)                       # sigue donde leía
        self.assertEqual(d.ir_abajo.text(), "↓  2 nuevos")
        d.ir_abajo.click()
        _asentar()
        self.assertEqual(barra.value(), barra.maximum())
        self.assertFalse(d.ir_abajo.isVisible())

    def test_lo_que_mando_yo_baja_aunque_estuviera_arriba(self) -> None:
        d, barra = self._larga()
        barra.setValue(40)
        _asentar()
        d.editor.setPlainText("ya voy")
        d.enviar()
        _asentar()
        self.assertEqual(barra.value(), barra.maximum())
        self.assertEqual(self._textos(d)[-1], "ya voy")

    def test_el_boton_va_en_la_esquina_de_abajo_dentro_de_la_conversacion(self) -> None:
        d, barra = self._larga()
        barra.setValue(40)
        _asentar()
        b, area = d.ir_abajo, d._scroll
        self.assertGreater(b.x(), area.width() // 2)
        self.assertLessEqual(b.x() + b.width(), area.width())
        self.assertGreater(b.y(), area.height() // 2)
        self.assertLessEqual(b.y() + b.height(), area.height())


class ListaDeChatsTests(_ConBase):
    def test_sin_cambios_no_se_rehace_la_lista(self) -> None:
        self._mandar("hola", de="Entrada", para="Caja")
        d = self._ventana("Caja")
        d.refrescar()
        renglon = d.lista.itemWidget(d.lista.item(0))
        d.refrescar()
        d.refrescar()
        self.assertIs(d.lista.itemWidget(d.lista.item(0)), renglon)   # antes era otro cada 5 s

    def test_con_un_mensaje_nuevo_si_se_actualiza(self) -> None:
        self._mandar("hola", de="Entrada", para="Caja")
        d = self._ventana("Caja")
        d.refrescar()
        self._mandar("te escribo por privado", de="Entrada", para="Caja")
        d.refrescar()
        privado = next(c for c in d._chats if c.clave == "Entrada")
        self.assertEqual(privado.ultimo_texto, "te escribo por privado")


class BorradoresTests(_ConBase):
    def test_lo_escrito_a_medias_se_queda_en_su_chat(self) -> None:
        self._mandar("hola", de="Entrada", para="Caja")
        d = self._ventana("Caja")
        d.editor.setPlainText("para todas, a medias")
        d.abrir_chat("Entrada")
        self.assertEqual(d.editor.toPlainText(), "")
        d.editor.setPlainText("solo para Entrada")
        d.abrir_chat(bz.GRUPO)
        self.assertEqual(d.editor.toPlainText(), "para todas, a medias")
        d.abrir_chat("Entrada")
        self.assertEqual(d.editor.toPlainText(), "solo para Entrada")

    def test_al_mandarlo_el_borrador_se_va(self) -> None:
        self._mandar("hola", de="Entrada", para="Caja")
        d = self._ventana("Caja")
        d.abrir_chat("Entrada")
        d.editor.setPlainText("listo")
        d.enviar()
        d.abrir_chat(bz.GRUPO)
        d.abrir_chat("Entrada")
        self.assertEqual(d.editor.toPlainText(), "")


class MensajesNuevosTests(_ConBase):
    def _rayas(self, d) -> list[str]:
        return [w.text() for w in d._mensajes.findChildren(QLabel, "nuevos")]

    def test_al_abrir_un_chat_marca_desde_donde_no_habia_visto(self) -> None:
        self._mandar("ya visto", de="Entrada", para="Caja")
        d = self._ventana("Caja")
        d.abrir_chat("Entrada")          # lo lee
        d.abrir_chat(bz.GRUPO)
        self._mandar("nuevo 1", de="Entrada", para="Caja")
        self._mandar("nuevo 2", de="Entrada", para="Caja")
        d.refrescar()
        d.abrir_chat("Entrada")
        self.assertEqual(self._rayas(d), ["2 mensajes nuevos"])
        # Y va justo antes del primero sin ver.
        ly = d._mensajes_ly
        orden = [ly.itemAt(i).widget() for i in range(ly.count()) if ly.itemAt(i).widget() is not None]
        i_raya = next(i for i, w in enumerate(orden) if w.objectName() == "nuevos")
        self.assertEqual(orden[i_raya + 1].findChild(QLabel, "cuerpo").text(), "nuevo 1")

    def test_sin_nada_nuevo_no_hay_raya(self) -> None:
        self._mandar("ya visto", de="Entrada", para="Caja")
        d = self._ventana("Caja")
        d.abrir_chat("Entrada")
        d.abrir_chat(bz.GRUPO)
        d.abrir_chat("Entrada")
        self.assertEqual(self._rayas(d), [])

    def test_lo_que_llega_con_el_chat_abierto_no_pone_raya(self) -> None:
        self._mandar("uno", de="Entrada")
        d = self._ventana("Caja")
        self._mandar("dos", de="Entrada")
        d.refrescar()
        self.assertEqual(self._rayas(d), [])


class MensajesLargosTests(_ConBase):
    def test_un_resultado_largo_sale_recortado_y_se_abre(self) -> None:
        largo = "\n".join(f"renglon {i}" for i in range(120))
        self._mandar(largo, de="Entrada")
        d = self._ventana("Caja")
        cuerpo = d._mensajes.findChildren(QLabel, "cuerpo")[0]
        self.assertEqual(len(cuerpo.text().splitlines()), 31)             # 30 + «…»
        ver = next(b for b in d._mensajes.findChildren(QToolButton) if "Ver todo" in b.text())
        self.assertIn("120 renglones", ver.text())
        ver.click()
        self.assertEqual(cuerpo.text(), largo)
        self.assertIn("Ver menos", ver.text())
        ver.click()
        self.assertEqual(len(cuerpo.text().splitlines()), 31)

    def test_copiar_se_lleva_el_mensaje_entero_aunque_este_recortado(self) -> None:
        largo = "\n".join(f"renglon {i}" for i in range(120))
        self._mandar(largo, de="Entrada")
        d = self._ventana("Caja")
        next(b for b in d._mensajes.findChildren(QToolButton) if "Copiar" in b.text()).click()
        self.assertEqual(QApplication.clipboard().text(), largo)

    def test_uno_normal_no_lleva_ver_todo(self) -> None:
        self._mandar("corto\nde dos renglones", de="Entrada")
        d = self._ventana("Caja")
        self.assertFalse([b for b in d._mensajes.findChildren(QToolButton) if "Ver todo" in b.text()])


class BotonDeEjecutarTests(_ConBase):
    def test_al_terminar_el_boton_vuelve_sin_repintar_la_conversacion(self) -> None:
        from pos_uniformes.services.buzon_ejecutar_service import Resultado

        self._mandar("Get-Date | Out-String", de="Claude", para="Caja")
        d = self._ventana("Caja", confirmar=lambda *_: True,
                          ejecutar=lambda _t: Resultado("hoy", 0, 0.1))
        d.abrir_chat("Claude")
        burbuja = d._mensajes.findChildren(QLabel, "cuerpo")[0]
        boton = next(b for b in d._mensajes.findChildren(QToolButton) if "Ejecutar" in b.text())
        boton.click()
        _asentar()
        self.assertEqual(boton.text(), "▶ Ejecutar")
        self.assertTrue(boton.isEnabled())
        self.assertIs(d._mensajes.findChildren(QLabel, "cuerpo")[0], burbuja)
