"""Visor de cámaras del kiosko: empleada ve entradas, admin (PIN) ve todas.

Se inyecta un reproductor falso para no abrir RTSP ni cargar ffmpeg en tests.
"""

from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QApplication, QWidget

from pos_uniformes.services.dvr_settings_cache_service import CanalDVR, DVRSettings
from pos_uniformes.ui.dialogs.camera_wall_dialog import CameraWallDialog


class _FakePlayer(QObject):
    errorOccurred = pyqtSignal(object, str)
    mediaStatusChanged = pyqtSignal(object)
    instancias: list["_FakePlayer"] = []

    def __init__(self) -> None:
        super().__init__()
        self.source = None
        self.playing = False
        self.stopped = 0
        _FakePlayer.instancias.append(self)

    def setVideoOutput(self, _widget) -> None:  # noqa: N802
        pass

    def setSource(self, url) -> None:  # noqa: N802
        self.source = url.toString() if hasattr(url, "toString") else url

    def play(self) -> None:
        self.playing = True

    def stop(self) -> None:
        self.playing = False
        self.stopped += 1


def _settings() -> DVRSettings:
    return DVRSettings(
        host="192.168.0.11",
        user="dany",
        password="x",
        canales=[
            CanalDVR(1, "VESTIDOR"),
            CanalDVR(2, "CAJA"),
            CanalDVR(4, "ENTRADA1", entrada=True),
            CanalDVR(6, "ENTRADA2", entrada=True),
        ],
    )


class CameraWallDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        _FakePlayer.instancias = []
        self.pin_respuestas: list[bool] = []

    def _dialog(self, settings: DVRSettings | None = None) -> CameraWallDialog:
        loader = (lambda: settings) if settings is not None else _settings
        return CameraWallDialog(
            None,
            settings_loader=loader,
            player_factory=_FakePlayer,
            video_factory=QWidget,
            pin_prompt=lambda _parent: self.pin_respuestas.pop(0) if self.pin_respuestas else False,
        )

    def test_abre_en_modo_empleada_solo_entradas(self) -> None:
        d = self._dialog()
        d.show()
        self.assertFalse(d.es_admin())
        canales = [c for c, _ in d.tiles_activos()]
        self.assertEqual(canales, [4, 6])
        for _, url in d.tiles_activos():
            self.assertIn("subtype=1", url)  # mosaico usa substream
        self.assertTrue(all(p.playing for p in _FakePlayer.instancias))
        d.close()

    def test_pin_correcto_muestra_todas(self) -> None:
        d = self._dialog()
        d.show()
        self.pin_respuestas = [True]
        d.admin_button.click()
        self.assertTrue(d.es_admin())
        self.assertEqual([c for c, _ in d.tiles_activos()], [1, 2, 4, 6])
        d.close()

    def test_pin_incorrecto_sigue_en_entradas(self) -> None:
        from unittest.mock import patch

        d = self._dialog()
        d.show()
        self.pin_respuestas = [False]
        with patch("pos_uniformes.ui.dialogs.camera_wall_dialog.QMessageBox.warning"):
            d.admin_button.click()
        self.assertFalse(d.es_admin())
        self.assertEqual([c for c, _ in d.tiles_activos()], [4, 6])
        d.close()

    def test_cerrar_olvida_el_modo_admin_y_detiene_video(self) -> None:
        d = self._dialog()
        d.show()
        self.pin_respuestas = [True]
        d.admin_button.click()
        players = list(_FakePlayer.instancias)
        d.close()
        self.assertFalse(d.es_admin())
        self.assertEqual(d.tiles_activos(), [])
        self.assertTrue(all(not p.playing for p in players))
        # Reabrir vuelve a modo empleada sin pedir nada.
        d.show()
        self.assertEqual([c for c, _ in d.tiles_activos()], [4, 6])
        d.close()

    def test_ampliar_usa_stream_principal_y_esc_regresa(self) -> None:
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import QKeyEvent
        from PyQt6.QtCore import QEvent

        d = self._dialog()
        d.show()
        d._ampliar(6)
        activos = d.tiles_activos()
        self.assertEqual(len(activos), 1)
        self.assertEqual(activos[0][0], 6)
        self.assertIn("subtype=0", activos[0][1])
        self.assertTrue(d.back_button.isVisible() or not d.back_button.isHidden())
        d.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier))
        self.assertEqual([c for c, _ in d.tiles_activos()], [4, 6])
        d.close()

    def test_sin_configurar_muestra_aviso(self) -> None:
        d = self._dialog(DVRSettings())
        d.show()
        self.assertEqual(d.tiles_activos(), [])
        self.assertFalse(d.message_label.isHidden())
        self.assertIn("no están configuradas", d.message_label.text())
        d.close()

    def test_sin_entradas_marcadas_avisa_a_empleada(self) -> None:
        s = _settings()
        for c in s.canales:
            c.entrada = False
        d = self._dialog(s)
        d.show()
        self.assertEqual(d.tiles_activos(), [])
        self.assertIn("entrada", d.message_label.text().lower())
        d.close()

    def test_stream_caido_reintenta(self) -> None:
        d = self._dialog()
        d.show()
        tile = d._tiles[0]
        tile.player.errorOccurred.emit(object(), "boom")
        self.assertIn("Sin señal", tile.status_label.text())
        self.assertTrue(tile._retry.isActive())
        d.close()
        self.assertFalse(tile._retry.isActive())


if __name__ == "__main__":
    unittest.main()
