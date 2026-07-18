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
