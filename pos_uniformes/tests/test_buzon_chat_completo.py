"""El buzón como chat completo: historia, palomitas, el resultado pegado a su
comando, capturas, buscar y borrar.

Daniel, 2026-11-06: «¿qué otra cosa mejorarías de este sistema de mensajes?» →
«hazlo completo».
"""

from __future__ import annotations

from PyQt6.QtCore import QMimeData
from PyQt6.QtGui import QColor, QImage
from PyQt6.QtWidgets import QApplication, QLabel, QPushButton, QToolButton
from sqlalchemy import select

from pos_uniformes.database.models import BuzonAdjunto, BuzonMensaje
from pos_uniformes.services import buzon_service as bz
from pos_uniformes.tests.test_buzon_dialog import _ConBase


def _asentar() -> None:
    for _ in range(4):
        QApplication.processEvents()


def _imagen(ancho: int = 200, alto: int = 100) -> QImage:
    img = QImage(ancho, alto, QImage.Format.Format_RGB32)
    img.fill(QColor("#336699"))
    return img


class ServicioTests(_ConBase):
    def test_una_imagen_viaja_aparte_y_puede_ir_sin_texto(self) -> None:
        with self._sesion() as s:
            m = bz.enviar(s, "", de="Caja", para="Entrada", imagen=b"\x89PNG-datos")
            s.commit()
            self.assertTrue(m.adjunto)
            self.assertEqual(bz.imagen_de(s, m.id), b"\x89PNG-datos")
            self.assertEqual(bz.vista_previa(m), "📷 Imagen")
            with self.assertRaises(bz.NoSePuede):
                bz.enviar(s, "", de="Caja")                       # ni texto ni imagen
            with self.assertRaises(bz.NoSePuede):
                bz.enviar(s, "x", de="Caja", imagen=b"0" * (bz.MAXIMO_IMAGEN + 1))

    def test_borrar_solo_lo_propio_y_se_lleva_texto_e_imagen(self) -> None:
        with self._sesion() as s:
            m = bz.enviar(s, "clave del wifi", de="Caja", para="Entrada", imagen=b"img")
            s.commit()
            with self.assertRaises(bz.NoSePuede):
                bz.borrar(s, m.id, de="Entrada")
            self.assertTrue(bz.borrar(s, m.id, de="Caja"))
            s.commit()
            self.assertEqual(m.texto, "")
            self.assertIsNotNone(m.borrado_at)
            self.assertIsNone(s.scalars(select(BuzonAdjunto)).first())
            self.assertEqual(bz.vista_previa(m), "Se borró este mensaje")
            self.assertFalse(bz.borrar(s, m.id, de="Caja"))       # ya estaba borrado

    def test_buscar_encuentra_en_toda_la_historia_sin_mayusculas(self) -> None:
        self._mandar("Reinicia la IMPRESORA de tickets", de="Entrada", para="Caja")
        for i in range(80):
            self._mandar(f"relleno {i}", de="Entrada", para="Caja")
        self._mandar("100% listo", de="Caja", para="Entrada")
        with self._sesion() as s:
            hallados = bz.conversacion(s, yo="Caja", con="Entrada", buscar="impresora")
            self.assertEqual([m.texto for m in hallados], ["Reinicia la IMPRESORA de tickets"])
            # «%» se busca como letra, no como comodín.
            self.assertEqual([m.texto for m in bz.conversacion(s, yo="Caja", con="Entrada", buscar="%")], ["100% listo"])

    def test_hay_anteriores(self) -> None:
        for i in range(5):
            self._mandar(f"m{i}", de="Entrada", para="Caja")
        with self._sesion() as s:
            ultimos = bz.conversacion(s, yo="Caja", con="Entrada", limite=3)
            self.assertTrue(bz.hay_anteriores(s, yo="Caja", con="Entrada", antes_de=ultimos[0].id))
            todos = bz.conversacion(s, yo="Caja", con="Entrada", limite=10)
            self.assertFalse(bz.hay_anteriores(s, yo="Caja", con="Entrada", antes_de=todos[0].id))

    def test_lo_leido_por_los_demas_y_nunca_retrocede(self) -> None:
        with self._sesion() as s:
            bz.anotar_leido(s, lector="Entrada", chat="Caja", hasta_id=7)
            bz.anotar_leido(s, lector="Entrada", chat="Caja", hasta_id=3)      # no baja
            bz.anotar_leido(s, lector="Entrada", chat=bz.GRUPO, hasta_id=9)
            bz.anotar_leido(s, lector="Bodega", chat=bz.GRUPO, hasta_id=4)
            bz.anotar_leido(s, lector="Caja", chat=bz.GRUPO, hasta_id=12)
            s.commit()
            self.assertEqual(bz.leido_por_otros(s, yo="Caja", con="Entrada"), {"Entrada": 7})
            self.assertEqual(bz.leido_por_otros(s, yo="Caja", con=bz.GRUPO), {"Entrada": 9, "Bodega": 4})

    def test_al_renombrar_lo_leido_se_muda(self) -> None:
        with self._sesion() as s:
            bz.anotar_leido(s, lector="DESKTOP-1", chat="Caja", hasta_id=5)
            bz.anotar_leido(s, lector="Caja", chat="DESKTOP-1", hasta_id=6)
            s.commit()
            bz.renombrar(s, "DESKTOP-1", "Entrada")
            s.commit()
            self.assertEqual(bz.leido_por_otros(s, yo="Caja", con="Entrada"), {"Entrada": 5})
            self.assertEqual(bz.leido_por_otros(s, yo="Entrada", con="Caja"), {"Caja": 6})

    def test_el_recibido_no_cuenta_como_mensaje_por_leer(self) -> None:
        with self._sesion() as s:
            cmd = bz.enviar(s, "Get-Date | Out-String", de="Claude", para="Entrada")
            bz.enviar(s, "⏳ Recibido en Entrada: ejecutando…", de="Entrada", para="Claude",
                      responde_a=cmd.id, estado=bz.RECIBIDO)
            s.commit()
            chat = next(c for c in bz.chats(s, yo="Claude") if c.clave == "Entrada")
            self.assertEqual(chat.no_leidos, 0)
            self.assertEqual(chat.ultimo_texto, "Get-Date | Out-String")


class HistoriaTests(_ConBase):
    def _burbujas(self, d) -> int:
        return len(d._mensajes.findChildren(QLabel, "cuerpo"))

    def test_trae_un_tramo_y_el_boton_trae_el_anterior(self) -> None:
        for i in range(25):
            self._mandar(f"m{i}", de="Entrada")
        d = self._ventana("Caja", tramo=10)
        self.assertEqual(self._burbujas(d), 10)
        mas = d._mensajes.findChild(QPushButton, "anteriores")
        self.assertIsNotNone(mas)
        mas.click()
        self.assertEqual(self._burbujas(d), 20)
        d._mensajes.findChild(QPushButton, "anteriores").click()
        self.assertEqual(self._burbujas(d), 25)
        self.assertEqual(self._textos(d)[0], "m0")
        self.assertIsNone(d._mensajes.findChild(QPushButton, "anteriores"))     # ya no hay más

    def test_cargar_lo_anterior_no_mueve_lo_que_estas_leyendo(self) -> None:
        for i in range(60):
            self._mandar(f"m{i}", de="Entrada")
        d = self._ventana("Caja", tramo=30)
        d.resize(1000, 500)
        d.show()
        _asentar()
        barra = d._scroll.verticalScrollBar()
        barra.setValue(0)
        _asentar()
        desde_abajo = barra.maximum() - barra.value()
        d.cargar_anteriores()
        _asentar()
        self.assertEqual(self._burbujas(d), 60)
        self.assertAlmostEqual(barra.maximum() - barra.value(), desde_abajo, delta=4)
        self.assertGreater(barra.value(), 200)             # lo viejo quedó ARRIBA, no lo brincó

    def test_al_cambiar_de_chat_vuelve_al_tramo_de_entrada(self) -> None:
        for i in range(25):
            self._mandar(f"m{i}", de="Entrada")
        self._mandar("privado", de="Entrada", para="Caja")
        d = self._ventana("Caja", tramo=10)
        d.cargar_anteriores()
        d.abrir_chat("Entrada")
        d.abrir_chat(bz.GRUPO)
        self.assertEqual(self._burbujas(d), 10)


class PalomitasTests(_ConBase):
    def _palomitas(self, d) -> list[str]:
        return [w.text() for w in d._mensajes.findChildren(QLabel, "palomita")]

    def test_una_al_mandar_y_dos_cuando_lo_abren(self) -> None:
        self._mandar("hola", de="Entrada", para="Caja")       # para que exista el chat
        caja = self._ventana("Caja")
        caja.abrir_chat("Entrada")
        caja.editor.setPlainText("¿ya llegó el pedido?")
        caja.enviar()
        self.assertEqual(self._palomitas(caja), ["✓"])
        entrada = self._ventana("Entrada")
        entrada.abrir_chat("Caja")                              # lo abre: lo leyó
        caja.refrescar()
        self.assertEqual(self._palomitas(caja), ["✓✓"])

    def test_lo_ajeno_no_lleva_palomita(self) -> None:
        self._mandar("hola", de="Entrada")
        d = self._ventana("Caja")
        self.assertEqual(self._palomitas(d), [])

    def test_en_el_grupo_dice_quien_lo_leyo(self) -> None:
        caja = self._ventana("Caja")
        caja.editor.setPlainText("aviso a todas")
        caja.enviar()
        self._ventana("Entrada")                                # abre en el grupo: lo lee
        caja.refrescar()
        marca = caja._mensajes.findChildren(QLabel, "palomita")[0]
        self.assertEqual(marca.text(), "✓✓")
        self.assertIn("Entrada", marca.toolTip())


class LeidoEsLoQueSeVioTests(_ConBase):
    def test_leyendo_arriba_lo_nuevo_sigue_pendiente_hasta_bajar(self) -> None:
        for i in range(40):
            self._mandar(f"m{i}", de="Entrada")
        d = self._ventana("Caja")
        d.resize(1000, 500)
        d.show()
        _asentar()
        barra = d._scroll.verticalScrollBar()
        barra.setValue(40)
        _asentar()
        visto = self.leidos["Caja"][bz.GRUPO]
        self._mandar("llegó mientras leía arriba", de="Entrada")
        d.refrescar()
        _asentar()
        self.assertEqual(self.leidos["Caja"][bz.GRUPO], visto)          # no se marcó
        self.assertEqual(d._chats[0].no_leidos, 1)                      # y la lista lo dice
        d.ir_abajo.click()
        _asentar()
        self.assertGreater(self.leidos["Caja"][bz.GRUPO], visto)
        with self._sesion() as s:
            self.assertEqual(bz.leido_por_otros(s, yo="Entrada", con=bz.GRUPO)["Caja"], self.leidos["Caja"][bz.GRUPO])


class ResultadoPegadoAlComandoTests(_ConBase):
    def _corrido(self, ok: bool = True):
        from pos_uniformes.services.buzon_ejecutar_service import Resultado

        self._mandar("Get-Date | Out-String", de="Claude", para="Entrada")
        d = self._ventana(
            "Entrada", confirmar=lambda *_: True,
            ejecutar=lambda _t: Resultado("06/11/2026\n", 0 if ok else 1, 0.4),
        )
        d.abrir_chat("Claude")
        next(b for b in d._mensajes.findChildren(QToolButton) if "Ejecutar" in b.text()).click()
        _asentar()
        return d

    def test_el_resultado_cita_su_comando_y_el_recibido_no_es_burbuja(self) -> None:
        d = self._corrido()
        textos = self._textos(d)
        self.assertEqual(len(textos), 2)                                 # comando + resultado
        self.assertFalse([t for t in textos if "Recibido" in t])
        citas = [w.text() for w in d._mensajes.findChildren(QLabel, "cita")]
        self.assertEqual(len(citas), 1)
        self.assertIn("Get-Date | Out-String", citas[0])
        with self._sesion() as s:
            cmd, recibido, resultado = s.scalars(select(BuzonMensaje).order_by(BuzonMensaje.id)).all()
        self.assertEqual((recibido.responde_a, recibido.estado), (cmd.id, bz.RECIBIDO))
        self.assertEqual((resultado.responde_a, resultado.estado), (cmd.id, bz.TERMINO_BIEN))

    def test_la_burbuja_del_comando_dice_como_le_fue_en_las_dos_pcs(self) -> None:
        d = self._corrido()
        estados = [w.text() for w in d._mensajes.findChildren(QLabel, "estadoComando") if w.text()]
        self.assertEqual(estados, ["✔ Corrió en Entrada: terminó bien"])
        quien_pidio = self._ventana("Claude")
        quien_pidio.abrir_chat("Entrada")
        estados = [w.text() for w in quien_pidio._mensajes.findChildren(QLabel, "estadoComando") if w.text()]
        self.assertEqual(estados, ["✔ Corrió en Entrada: terminó bien"])

    def test_si_no_termino_bien_lo_dice(self) -> None:
        d = self._corrido(ok=False)
        estados = [w.text() for w in d._mensajes.findChildren(QLabel, "estadoComando") if w.text()]
        self.assertEqual(estados, ["⚠️ Corrió en Entrada: no terminó bien"])

    def test_mientras_corre_dice_ejecutando(self) -> None:
        with self._sesion() as s:
            cmd = bz.enviar(s, "Get-Date | Out-String", de="Claude", para="Entrada")
            bz.enviar(s, "⏳ Recibido en Entrada: ejecutando…", de="Entrada", para="Claude",
                      responde_a=cmd.id, estado=bz.RECIBIDO)
            s.commit()
        d = self._ventana("Claude")
        d.abrir_chat("Entrada")
        estados = [w.text() for w in d._mensajes.findChildren(QLabel, "estadoComando") if w.text()]
        self.assertEqual(estados, ["⏳ Ejecutando en Entrada…"])


class ResponderTests(_ConBase):
    def test_responder_cita_el_mensaje(self) -> None:
        self._mandar("¿Quién cierra hoy?", de="Entrada")
        d = self._ventana("Caja")
        self.assertFalse(d.respuesta_barra.isVisibleTo(d))
        next(b for b in d._mensajes.findChildren(QToolButton) if "Responder" in b.text()).click()
        self.assertTrue(d.respuesta_barra.isVisibleTo(d))
        self.assertIn("¿Quién cierra hoy?", d.respuesta_label.text())
        d.editor.setPlainText("Yo")
        d.enviar()
        self.assertFalse(d.respuesta_barra.isVisibleTo(d))
        citas = [w.text() for w in d._mensajes.findChildren(QLabel, "cita")]
        self.assertEqual(len(citas), 1)
        self.assertIn("Entrada: ¿Quién cierra hoy?", citas[0])
        with self._sesion() as s:
            pregunta, respuesta = s.scalars(select(BuzonMensaje).order_by(BuzonMensaje.id)).all()
        self.assertEqual(respuesta.responde_a, pregunta.id)

    def test_la_equis_quita_la_respuesta(self) -> None:
        self._mandar("hola", de="Entrada")
        d = self._ventana("Caja")
        next(b for b in d._mensajes.findChildren(QToolButton) if "Responder" in b.text()).click()
        d._quitar_respuesta()
        d.editor.setPlainText("sin cita")
        d.enviar()
        self.assertEqual(d._mensajes.findChildren(QLabel, "cita"), [])


class CapturasTests(_ConBase):
    def test_pegar_una_captura_la_deja_lista_y_enter_la_manda(self) -> None:
        d = self._ventana("Caja")
        datos = QMimeData()
        datos.setImageData(_imagen())
        d.editor.insertFromMimeData(datos)
        self.assertTrue(d.imagen_barra.isVisibleTo(d))
        self.assertEqual(d.editor.toPlainText(), "")                    # no metió texto raro
        d.enviar()                                                      # sin texto: va la pura imagen
        self.assertFalse(d.imagen_barra.isVisibleTo(d))
        foto = d._mensajes.findChild(QLabel, "foto")
        self.assertIsNotNone(foto)
        self.assertEqual((foto.pixmap().width(), foto.pixmap().height()), (200, 100))
        with self._sesion() as s:
            m = s.scalars(select(BuzonMensaje)).one()
            self.assertTrue(m.adjunto)

    def test_la_otra_pc_la_ve_y_tocarla_la_abre_completa(self) -> None:
        caja = self._ventana("Caja")
        caja.poner_imagen(_imagen(900, 600))
        caja.editor.setPlainText("mira el error")
        caja.enviar()
        abiertas = []
        entrada = self._ventana("Entrada", ver_imagen=lambda _p, pix: abiertas.append((pix.width(), pix.height())))
        foto = entrada._mensajes.findChild(QLabel, "foto")
        self.assertLessEqual(foto.pixmap().width(), 340)                 # en la burbuja, chica
        foto.tocada.emit()
        self.assertEqual(abiertas, [(900, 600)])                         # al tocarla, entera
        self.assertEqual(self._textos(entrada), ["mira el error"])
        self.assertTrue(entrada._chats[0].ultimo_texto.startswith("📷 Imagen"))

    def test_una_muy_grande_se_achica_antes_de_mandarse(self) -> None:
        from pos_uniformes.ui.dialogs.buzon_dialog import LADO_IMAGEN, _a_bytes

        salida = QImage()
        salida.loadFromData(_a_bytes(_imagen(4000, 2000)))
        self.assertEqual((salida.width(), salida.height()), (LADO_IMAGEN, LADO_IMAGEN // 2))

    def test_la_equis_quita_la_imagen(self) -> None:
        d = self._ventana("Caja")
        d.poner_imagen(_imagen())
        d._quitar_imagen()
        d.enviar()
        with self._sesion() as s:
            self.assertEqual(s.scalars(select(BuzonMensaje)).all(), [])


class BuscarTests(_ConBase):
    def test_buscar_deja_solo_lo_que_coincide_y_cerrar_regresa_todo(self) -> None:
        self._mandar("Reinicia la impresora", de="Entrada")
        self._mandar("ok", de="Caja")
        self._mandar("La impresora ya quedó", de="Entrada")
        d = self._ventana("Caja")
        d.buscar_texto("impresora")
        self.assertEqual(self._textos(d), ["Reinicia la impresora", "La impresora ya quedó"])
        letreros = [w.text() for w in d._mensajes.findChildren(QLabel, "fecha")]
        self.assertIn("2 mensajes con «impresora»", letreros)
        d._alternar_busqueda() if d.buscar.isVisibleTo(d) else d.buscar_texto("")
        self.assertEqual(len(self._textos(d)), 3)

    def test_sin_resultados_lo_dice(self) -> None:
        self._mandar("hola", de="Entrada")
        d = self._ventana("Caja")
        d.buscar_texto("zapato")
        self.assertEqual(self._textos(d), [])
        self.assertIn("Nada con «zapato» en este chat.", [w.text() for w in d._mensajes.findChildren(QLabel, "fecha")])

    def test_mandar_algo_cierra_la_busqueda(self) -> None:
        self._mandar("hola", de="Entrada")
        d = self._ventana("Caja")
        d.buscar_texto("hola")
        d.editor.setPlainText("nuevo")
        d.enviar()
        self.assertEqual(self._textos(d), ["hola", "nuevo"])


class BorrarTests(_ConBase):
    def _botones_borrar(self, d) -> list[QToolButton]:
        return d._mensajes.findChildren(QToolButton, "borrar")

    def test_solo_lo_mio_se_puede_borrar_y_la_otra_pc_lo_ve_borrado(self) -> None:
        self._mandar("de Entrada", de="Entrada")
        self._mandar("la clave es 1234", de="Caja")
        entrada = self._ventana("Entrada")
        caja = self._ventana("Caja", confirmar_borrado=lambda _p: True)
        self.assertEqual(len(self._botones_borrar(caja)), 1)             # solo el suyo
        self._botones_borrar(caja)[0].click()
        self.assertEqual(self._textos(caja), ["de Entrada"])
        self.assertEqual(len(caja._mensajes.findChildren(QLabel, "borrado")), 1)
        entrada.refrescar()
        self.assertEqual(self._textos(entrada), ["de Entrada"])
        self.assertEqual(len(entrada._mensajes.findChildren(QLabel, "borrado")), 1)

    def test_si_dice_que_no_no_se_borra(self) -> None:
        self._mandar("se queda", de="Caja")
        d = self._ventana("Caja", confirmar_borrado=lambda _p: False)
        self._botones_borrar(d)[0].click()
        self.assertEqual(self._textos(d), ["se queda"])
