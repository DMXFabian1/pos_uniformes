"""Tests del controlador de cartelera (inactividad, rotación, aviso inmediato).

Qt headless (offscreen). El reloj se inyecta y se invocan los métodos internos
directamente, sin depender de que los QTimer disparen.
"""

from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QWidget

from pos_uniformes.ui.helpers.anuncio_cartelera import AnuncioCartelera

_app = QApplication.instance() or QApplication([])


class _Reloj:
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t

    def avanzar(self, seg: float) -> None:
        self.t += seg


def _anuncios():
    return [
        {"id": 1, "titulo": "A", "mensaje": "uno", "imagen_path": None, "duracion_seg": 5},
        {"id": 2, "titulo": "B", "mensaje": "dos", "imagen_path": None, "duracion_seg": 5},
    ]


class CarteleraTests(unittest.TestCase):
    def setUp(self) -> None:
        self.parent = QWidget()
        self.parent.resize(800, 600)
        self.parent.show()
        self.reloj = _Reloj()
        self.ctrl = AnuncioCartelera(
            self.parent, inactividad_seg=120, now_fn=self.reloj
        )
        self.overlay = self.ctrl._overlay

    def tearDown(self) -> None:
        self.ctrl.stop()
        self.parent.close()

    def test_no_entra_antes_del_umbral(self) -> None:
        self.ctrl.set_anuncios(_anuncios())
        self.reloj.avanzar(60)  # menos de 120s
        self.ctrl._chequear_inactividad()
        self.assertFalse(self.overlay.isVisible())

    def test_entra_cartelera_tras_inactividad(self) -> None:
        self.ctrl.set_anuncios(_anuncios())
        self.reloj.avanzar(130)
        self.ctrl._chequear_inactividad()
        self.assertTrue(self.overlay.isVisible())
        self.assertEqual(self.ctrl.indice_actual, 0)

    def test_no_entra_sin_anuncios(self) -> None:
        self.ctrl.set_anuncios([])
        self.reloj.avanzar(130)
        self.ctrl._chequear_inactividad()
        self.assertFalse(self.overlay.isVisible())

    def test_rotacion_avanza_indice(self) -> None:
        self.ctrl.set_anuncios(_anuncios())
        self.reloj.avanzar(130)
        self.ctrl._chequear_inactividad()
        self.ctrl._rotar()
        self.assertEqual(self.ctrl.indice_actual, 1)
        self.ctrl._rotar()
        self.assertEqual(self.ctrl.indice_actual, 0)  # da la vuelta

    def test_actividad_cierra_overlay(self) -> None:
        self.ctrl.set_anuncios(_anuncios())
        self.reloj.avanzar(130)
        self.ctrl._chequear_inactividad()
        self.assertTrue(self.overlay.isVisible())
        self.reloj.avanzar(2)  # supera el antirrebote
        self.ctrl.notar_actividad()
        self.assertFalse(self.overlay.isVisible())

    def test_aviso_inmediato_se_muestra_y_se_descarta(self) -> None:
        self.ctrl.mostrar_inmediato(
            {"id": 9, "titulo": "YA", "mensaje": "urgente", "imagen_path": None}
        )
        self.assertTrue(self.overlay.isVisible())
        self.assertFalse(self.ctrl._en_cartelera)
        self.reloj.avanzar(2)
        self.ctrl._al_descartar()
        self.assertFalse(self.overlay.isVisible())

    def test_antirrebote_ignora_descarte_inmediato(self) -> None:
        self.ctrl.mostrar_inmediato(
            {"id": 9, "titulo": "YA", "mensaje": "x", "imagen_path": None}
        )
        # Descarte en el mismo instante (dentro del antirrebote) → se ignora.
        self.ctrl._al_descartar()
        self.assertTrue(self.overlay.isVisible())

    def test_set_anuncios_vacio_cierra_cartelera(self) -> None:
        self.ctrl.set_anuncios(_anuncios())
        self.reloj.avanzar(130)
        self.ctrl._chequear_inactividad()
        self.assertTrue(self.overlay.isVisible())
        self.ctrl.set_anuncios([])
        self.assertFalse(self.overlay.isVisible())


if __name__ == "__main__":
    unittest.main()


def _aviso(anuncio_id: int = 9, **extra):
    """Un aviso de Telegram: pide acuse."""
    base = {
        "id": anuncio_id,
        "titulo": "Junta a las 6",
        "mensaje": None,
        "imagen_path": None,
        "duracion_seg": 8,
        "pide_acuse": True,
    }
    base.update(extra)
    return base


class AcuseTests(unittest.TestCase):
    """Un aviso con acuse no se va solo ni de un roce: solo por sus botones."""

    def setUp(self) -> None:
        self.parent = QWidget()
        self.parent.resize(800, 600)
        self.parent.show()
        self.reloj = _Reloj()
        self.acusados: list[dict] = []
        self.ctrl = AnuncioCartelera(
            self.parent,
            inactividad_seg=120,
            now_fn=self.reloj,
            al_acusar=self.acusados.append,
        )
        self.overlay = self.ctrl._overlay

    def tearDown(self) -> None:
        self.ctrl.stop()
        self.parent.close()

    def test_un_toque_al_aire_no_quita_el_aviso(self) -> None:
        self.ctrl.mostrar_inmediato(_aviso())
        self.reloj.avanzar(5)  # pasado el antirrebote
        self.ctrl.notar_actividad()
        self.assertTrue(self.overlay.isVisible())

    def test_no_se_cierra_solo(self) -> None:
        # El de siempre se cierra a los 20 s; uno con acuse no, porque entonces
        # nadie podría jurar que lo vieron.
        self.ctrl.mostrar_inmediato(_aviso())
        self.assertFalse(self.ctrl._inmediato_timer.isActive())

    def test_el_anuncio_normal_si_se_cierra_solo(self) -> None:
        self.ctrl.mostrar_inmediato(_anuncios()[0])
        self.assertTrue(self.ctrl._inmediato_timer.isActive())

    def test_enterada_cierra_y_avisa(self) -> None:
        self.ctrl.mostrar_inmediato(_aviso(7))
        self.overlay.acusado.emit()
        self.assertFalse(self.overlay.isVisible())
        self.assertEqual([a["id"] for a in self.acusados], [7])

    def test_luego_cierra_sin_acusar(self) -> None:
        self.ctrl.mostrar_inmediato(_aviso(7))
        self.overlay.descartado.emit()
        self.assertFalse(self.overlay.isVisible())
        self.assertEqual(self.acusados, [])
        self.assertEqual(self.ctrl.acusados, set())

    def test_luego_no_lo_frena_el_antirrebote(self) -> None:
        # Es un botón: se le apuntó. Si el antirrebote lo tragara, la caja
        # quedaría bloqueada con un cliente enfrente.
        self.ctrl.mostrar_inmediato(_aviso())
        self.ctrl._al_descartar()  # sin avanzar el reloj
        self.assertFalse(self.overlay.isVisible())

    def test_ya_acusado_deja_de_pedir_acuse_en_esta_pantalla(self) -> None:
        self.ctrl.mostrar_inmediato(_aviso(7))
        self.overlay.acusado.emit()
        # Vuelve a salir (sigue activo para las otras pantallas): ahora es común.
        self.ctrl.mostrar_inmediato(_aviso(7))
        self.assertFalse(self.overlay.pide_acuse)
        self.reloj.avanzar(5)
        self.ctrl.notar_actividad()
        self.assertFalse(self.overlay.isVisible())

    def test_un_aviso_sin_acusar_no_rota(self) -> None:
        self.ctrl.set_anuncios([_aviso(1), _anuncios()[0]])
        self.reloj.avanzar(200)
        self.ctrl._chequear_inactividad()
        self.assertTrue(self.overlay.isVisible())
        self.assertFalse(self.ctrl._rotacion_timer.isActive())

    def test_el_acuse_sin_nada_en_pantalla_no_revienta(self) -> None:
        self.ctrl._al_acusar()
        self.assertEqual(self.acusados, [])

    def test_un_callback_que_truena_no_deja_el_overlay_abierto(self) -> None:
        def _truena(_anuncio):
            raise RuntimeError("sin DB")

        self.ctrl._al_acusar_cb = _truena
        self.ctrl.mostrar_inmediato(_aviso())
        self.overlay.acusado.emit()
        self.assertFalse(self.overlay.isVisible())


class OverlayAvisoTests(unittest.TestCase):
    """Lo que la ventana de avisos no hacía: botones, letra que cabe, y la hora."""

    def setUp(self) -> None:
        from pos_uniformes.ui.anuncio_overlay import AnuncioOverlay

        self.parent = QWidget()
        self.parent.resize(800, 600)
        self.overlay = AnuncioOverlay(self.parent)

    def tearDown(self) -> None:
        self.parent.close()

    def test_un_anuncio_normal_no_tiene_botones(self) -> None:
        self.overlay.render_anuncio(_anuncios()[0])
        self.assertFalse(self.overlay._botones.isVisible())
        self.assertFalse(self.overlay.pide_acuse)

    def test_un_aviso_tiene_enterada(self) -> None:
        self.parent.show()
        self.overlay.show()
        self.overlay.render_anuncio(_aviso())
        self.assertTrue(self.overlay._botones.isVisible())
        self.assertTrue(self.overlay.pide_acuse)
        self.assertIn("Enterada", self.overlay._hint_label.text())

    def test_la_letra_baja_cuando_el_texto_crece(self) -> None:
        from pos_uniformes.ui.anuncio_overlay import (
            _MENSAJE_ESCALONES,
            _MENSAJE_MINIMO,
            _tamano,
        )

        corto = _tamano("x" * 10, _MENSAJE_ESCALONES, _MENSAJE_MINIMO)
        largo = _tamano("x" * 600, _MENSAJE_ESCALONES, _MENSAJE_MINIMO)
        self.assertGreater(corto, largo)
        self.assertEqual(largo, _MENSAJE_MINIMO)

    def test_la_cabecera_dice_de_cuando_es(self) -> None:
        from datetime import datetime, timedelta, timezone

        hace_rato = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        self.overlay.render_anuncio(_aviso(creado_en=hace_rato))
        self.assertIn("5 min", self.overlay._kicker_label.text())

    def test_hace_cuanto_aguanta_basura(self) -> None:
        from pos_uniformes.ui.anuncio_overlay import hace_cuanto

        self.assertEqual(hace_cuanto(None), "")
        self.assertEqual(hace_cuanto("no es una fecha"), "")


class FondoDeVerdadTests(unittest.TestCase):
    """El overlay tiene que PINTARSE, no solo decir que se pinta.

    En la tienda (02/10) el aviso salió transparente: se veía el kiosko detrás y
    el texto, que va en crema, desaparecía sobre el blanco de la pantalla. La
    causa es vieja y silenciosa de Qt: un QWidget pelado NO pinta el
    `background-color` de su hoja de estilo si no se le pide con
    WA_StyledBackground. Todos los tests de antes miraban atributos y pasaban.

    Estos miran los píxeles, que es lo único que mira quien está enfrente.
    """

    def setUp(self) -> None:
        from pos_uniformes.ui.anuncio_overlay import AnuncioOverlay

        # Padre blanco: si el overlay fuera transparente, se vería blanco —
        # exactamente lo que pasó en la tienda.
        self.parent = QWidget()
        self.parent.setStyleSheet("background: white;")
        self.parent.resize(600, 400)
        self.overlay = AnuncioOverlay(self.parent)
        self.overlay.setGeometry(self.parent.rect())

    def tearDown(self) -> None:
        self.parent.close()

    def _color_de_esquina(self):
        imagen = self.overlay.grab().toImage()
        # Una esquina: lejos de las etiquetas, es fondo puro.
        return imagen.pixelColor(4, 4)

    def test_pinta_aunque_la_hoja_de_estilo_no_sirva(self) -> None:
        """El de verdad: sin hoja de estilo, el fondo tiene que seguir ahí.

        Aquí en la Mac Qt respeta el `background-color` de la hoja, así que un
        test que solo mire los píxeles pasa igual aunque el código esté como
        estaba en la tienda — por eso este le quita la hoja: deja al descubierto
        si alguien vuelve a dejar el fondo colgando de ella.
        """
        self.overlay.render_anuncio(_aviso())
        self.overlay.setStyleSheet("")          # como si Qt la ignorara
        self.assertEqual(self._color_de_esquina().name(), "#8f2f12")

    def test_el_atributo_que_hace_que_se_pinte(self) -> None:
        from PyQt6.QtCore import Qt as _Qt

        self.assertTrue(
            self.overlay.testAttribute(_Qt.WidgetAttribute.WA_StyledBackground)
        )

    def test_un_aviso_no_es_transparente(self) -> None:
        self.overlay.render_anuncio(_aviso())
        color = self._color_de_esquina()
        self.assertNotEqual(color.name(), "#ffffff", "el overlay salió transparente")
        self.assertEqual(color.name(), "#8f2f12")

    def test_un_anuncio_de_texto_tiene_su_fondo(self) -> None:
        self.overlay.render_anuncio(_anuncios()[0])
        self.assertEqual(self._color_de_esquina().name(), "#7b2d14")

    def test_el_titulo_contrasta_con_el_fondo(self) -> None:
        # El texto va en crema. Si el fondo quedara claro no se leería, que es
        # justo como se veía en la foto de la tienda.
        from pos_uniformes.ui.anuncio_overlay import _MENSAJE, _TITULO

        self.overlay.render_anuncio(_aviso())
        fondo = self._color_de_esquina()
        for color_texto in (_TITULO, _MENSAJE):
            from PyQt6.QtGui import QColor

            texto = QColor(color_texto)
            distancia = (
                abs(texto.red() - fondo.red())
                + abs(texto.green() - fondo.green())
                + abs(texto.blue() - fondo.blue())
            )
            self.assertGreater(distancia, 200, f"{color_texto} no se lee sobre {fondo.name()}")

    def test_cambiar_de_anuncio_repinta_el_fondo(self) -> None:
        # La cartelera rota: un aviso y luego uno normal tienen fondos distintos
        # y el segundo no puede quedarse con el del primero.
        self.overlay.render_anuncio(_aviso())
        self.assertEqual(self._color_de_esquina().name(), "#8f2f12")
        self.overlay.render_anuncio(_anuncios()[0])
        self.assertEqual(self._color_de_esquina().name(), "#7b2d14")

    def test_con_imagen_el_fondo_es_oscuro(self) -> None:
        self.overlay.render_anuncio({**_aviso(), "imagen_path": "/no/existe.jpg"})
        # Sin archivo cae a texto; lo que importa es que nunca quede en blanco.
        self.assertNotEqual(self._color_de_esquina().name(), "#ffffff")


class FotoGrandeTests(unittest.TestCase):
    """La foto salía del tamaño de una estampilla (foto de la tienda, 02/10).

    El escalado se medía contra el QLabel, y ahí estaba el huevo y la gallina:
    el label medía lo que su pixmap, y el pixmap se escalaba al label. Ahora se
    mide contra la ventana, que sí tiene tamaño propio desde el principio.
    """

    def setUp(self) -> None:
        import tempfile

        from PyQt6.QtGui import QColor, QImage

        from pos_uniformes.ui.anuncio_overlay import AnuncioOverlay

        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.foto = f"{self._tmp.name}/foto.png"
        imagen = QImage(900, 1200, QImage.Format.Format_RGB32)   # vertical, de celular
        imagen.fill(QColor("#3a6ea5"))
        imagen.save(self.foto)

        self.parent = QWidget()
        self.parent.resize(1280, 800)
        self.overlay = AnuncioOverlay(self.parent)
        self.overlay.setGeometry(self.parent.rect())

    def tearDown(self) -> None:
        self.parent.close()

    def _con_foto(self, **extra):
        anuncio = {
            "id": 5, "titulo": "Así va el aparador", "mensaje": None,
            "imagen_path": self.foto, "duracion_seg": 8, "pide_acuse": True,
        }
        anuncio.update(extra)
        return anuncio

    def test_el_area_se_mide_contra_la_ventana(self) -> None:
        area = self.overlay.area_para_imagen()
        self.assertGreater(area.width(), 1000)   # casi todo el ancho de 1280
        self.assertGreater(area.height(), 400)

    def test_la_foto_ocupa_buena_parte_de_la_pantalla(self) -> None:
        self.overlay.render_anuncio(self._con_foto())
        pixmap = self.overlay._image_label.pixmap()
        self.assertIsNotNone(pixmap)
        # Una vertical en pantalla ancha la limita el alto; aun así tiene que
        # llenar más de la mitad, no ser una estampilla de veinte píxeles.
        self.assertGreater(pixmap.height(), self.overlay.height() * 0.5)

    def test_conserva_la_proporcion(self) -> None:
        self.overlay.render_anuncio(self._con_foto())
        pixmap = self.overlay._image_label.pixmap()
        self.assertAlmostEqual(pixmap.width() / pixmap.height(), 900 / 1200, places=1)

    def test_el_pie_de_foto_se_lee(self) -> None:
        # Quien manda una foto con pie lo escribió para que se leyera.
        self.overlay.render_anuncio(self._con_foto())
        self.assertTrue(self.overlay._message_label.isVisibleTo(self.overlay))
        self.assertIn("aparador", self.overlay._message_label.text())

    def test_sin_pie_no_deja_un_renglon_vacio(self) -> None:
        self.overlay.render_anuncio(self._con_foto(titulo=None, mensaje=None))
        self.assertFalse(self.overlay._message_label.isVisibleTo(self.overlay))

    def test_al_crecer_la_ventana_la_foto_crece(self) -> None:
        self.overlay.render_anuncio(self._con_foto())
        chica = self.overlay._image_label.pixmap().height()
        self.parent.resize(1920, 1200)
        self.overlay.setGeometry(self.parent.rect())
        self.overlay._reescalar_pixmap()
        self.assertGreater(self.overlay._image_label.pixmap().height(), chica)


class SinBandasBlancasTests(unittest.TestCase):
    """Las etiquetas se pintaban su propio fondo blanco.

    Con una hoja de estilo en el padre, Qt dibuja también a los hijos con el
    estilo de hojas y cada etiqueta se pinta de blanco. El texto va en crema:
    sobre esas bandas desaparecía igual que sobre el kiosko.
    """

    def setUp(self) -> None:
        from pos_uniformes.ui.anuncio_overlay import AnuncioOverlay

        self.parent = QWidget()
        self.parent.resize(900, 600)
        self.overlay = AnuncioOverlay(self.parent)
        self.overlay.setGeometry(self.parent.rect())
        self.overlay.render_anuncio(_aviso())

    def tearDown(self) -> None:
        self.parent.close()

    def _imagen(self):
        return self.overlay.grab().toImage()

    def test_detras_del_titulo_esta_el_fondo_del_aviso(self) -> None:
        imagen = self._imagen()
        geo = self.overlay._title_label.geometry()
        # Junto al borde izquierdo de la etiqueta, fuera de las letras.
        color = imagen.pixelColor(geo.left() + 2, geo.center().y())
        self.assertEqual(color.name(), "#8f2f12")

    def test_detras_del_pie_tambien(self) -> None:
        imagen = self._imagen()
        geo = self.overlay._hint_label.geometry()
        color = imagen.pixelColor(geo.left() + 2, geo.center().y())
        self.assertEqual(color.name(), "#8f2f12")

    def test_el_boton_enterada_conserva_su_fondo(self) -> None:
        # La regla de «sin fondo» del contenedor se la heredaban los botones y
        # «Enterada» quedaba invisible: letra vino sobre vino.
        hoja = self.overlay._botones.styleSheet()
        self.assertIn("#avisoBotones", hoja)


class BugsEncontradosRevisandoTests(unittest.TestCase):
    """Lo que salió al revisar anuncios a conciencia (02/10).

    Los tres eran del mismo tipo: código que funcionaba en el orden en que lo
    probé y no en el orden en que ocurre de verdad.
    """

    def setUp(self) -> None:
        from pos_uniformes.ui.anuncio_overlay import AnuncioOverlay

        self.parent = QWidget()
        self.parent.resize(1280, 800)
        self.overlay = AnuncioOverlay(self.parent)
        self.overlay.setGeometry(self.parent.rect())

    def tearDown(self) -> None:
        self.parent.close()

    def test_el_pie_se_descuenta_aunque_la_ventana_no_este_mostrada(self) -> None:
        # La cartelera pinta y DESPUÉS muestra, así que al medir la foto la
        # ventana está oculta e isVisible() siempre decía False.
        self.overlay._message_label.setText("Así va el aparador")
        self.overlay._message_label.setVisible(True)
        self.overlay._pide_acuse = True
        con_pie = self.overlay.area_para_imagen().height()
        self.overlay._message_label.setVisible(False)
        sin_pie = self.overlay.area_para_imagen().height()
        self.assertLess(con_pie, sin_pie, "el pie de foto no se está descontando")

    def test_la_ventana_oculta_no_cambia_la_cuenta(self) -> None:
        self.overlay._message_label.setVisible(True)
        oculta = self.overlay.area_para_imagen().height()
        self.parent.show()
        self.overlay.show()
        mostrada = self.overlay.area_para_imagen().height()
        self.assertEqual(oculta, mostrada)


class SinPcPrincipalAlAcusarTests(unittest.TestCase):
    """El escenario completo: se cae la PC, tocan Enterada, reinician el kiosko.

    Es el hueco que quedaba: el acuse vivía en memoria y el reinicio lo borraba.
    """

    def setUp(self) -> None:
        import tempfile
        from pathlib import Path
        from unittest.mock import patch

        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        parche = patch(
            "pos_uniformes.services.acuse_local_queue_service.satellite_data_dir",
            return_value=Path(self._tmp.name),
        )
        parche.start()
        self.addCleanup(parche.stop)
        from pos_uniformes.services import acuse_local_queue_service as cola

        self.cola = cola
        self.parent = QWidget()
        self.parent.resize(800, 600)
        self.parent.show()
        self.reloj = _Reloj()

    def tearDown(self) -> None:
        self.parent.close()

    def _cartelera(self, **extra):
        return AnuncioCartelera(
            self.parent, inactividad_seg=120, now_fn=self.reloj, **extra
        )

    def test_el_kiosko_reiniciado_no_le_saca_otra_vez_lo_acusado(self) -> None:
        # Toca Enterada con la PC caída: el acuse se encola.
        self.cola.encolar(7, satelite="s1", empleada="Evelyn", etiqueta="Junta")
        # El kiosko se reinicia: cartelera nueva, memoria en blanco.
        ctrl = self._cartelera()
        self.addCleanup(ctrl.stop)
        ctrl.set_anuncios([_aviso(7), _anuncios()[0]])
        self.assertNotIn(7, [a["id"] for a in ctrl._anuncios])
        self.assertIn(7, ctrl.acusados)

    def test_lo_que_no_se_acuso_si_sigue_saliendo(self) -> None:
        ctrl = self._cartelera()
        self.addCleanup(ctrl.stop)
        ctrl.set_anuncios([_aviso(7)])
        self.assertEqual([a["id"] for a in ctrl._anuncios], [7])

    def test_una_cola_ilegible_no_impide_arrancar(self) -> None:
        from pathlib import Path

        ruta = Path(self._tmp.name) / "data" / "acuses_pendientes.json"
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text("no soy json", encoding="utf-8")
        ctrl = self._cartelera()
        self.addCleanup(ctrl.stop)
        ctrl.set_anuncios([_aviso(7)])
        self.assertEqual([a["id"] for a in ctrl._anuncios], [7])
