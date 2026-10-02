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
