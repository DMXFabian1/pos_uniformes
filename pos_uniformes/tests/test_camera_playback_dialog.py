"""Ver momento: reproduce la grabación del DVR alrededor de un movimiento de la Libreta."""

from __future__ import annotations

import os
import unittest
from datetime import datetime, timedelta

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QApplication, QWidget

from pos_uniformes.services.dvr_settings_cache_service import CanalDVR, DVRSettings
from pos_uniformes.ui.dialogs.camera_playback_dialog import ANTES, DESPUES, CameraPlaybackDialog


class _FakePlayer(QObject):
    errorOccurred = pyqtSignal(object, str)
    mediaStatusChanged = pyqtSignal(object)
    positionChanged = pyqtSignal(int)
    durationChanged = pyqtSignal(int)

    def __init__(self) -> None:
        super().__init__()
        self.sources: list[str] = []
        self.playing = False
        self.position = 0

    def setVideoOutput(self, _w) -> None:  # noqa: N802
        pass

    def setSource(self, url) -> None:  # noqa: N802
        self.sources.append(url.toString())

    def play(self) -> None:
        self.playing = True

    def pause(self) -> None:
        self.playing = False

    def stop(self) -> None:
        self.playing = False

    def setPosition(self, ms: int) -> None:  # noqa: N802
        self.position = ms

    def playbackState(self):  # noqa: N802
        class _S:
            name = "PlayingState" if self.playing else "PausedState"

        return _S()


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


MOMENTO = datetime(2026, 9, 8, 12, 30, 15)


class CameraPlaybackDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _dialog(self, settings: DVRSettings | None = None, pin: bool = False) -> CameraPlaybackDialog:
        loader = (lambda: settings) if settings is not None else _settings
        return CameraPlaybackDialog(
            MOMENTO,
            None,
            titulo="Venta #123",
            settings_loader=loader,
            player_factory=_FakePlayer,
            video_factory=QWidget,
            pin_prompt=lambda _p: pin,
        )

    def test_empleada_arranca_en_una_entrada_con_ventana_alrededor_del_momento(self) -> None:
        d = self._dialog()
        self.assertFalse(d.es_admin())
        self.assertEqual([d.camera_combo.itemText(i) for i in range(d.camera_combo.count())], ["ENTRADA1", "ENTRADA2"])
        inicio, fin = d.ventana()
        self.assertEqual(inicio, MOMENTO - ANTES)
        self.assertEqual(fin, MOMENTO + DESPUES)
        self.assertIn("cam/playback?channel=4&subtype=0", d.url)
        self.assertIn("starttime=2026_09_08_12_29_15", d.url)
        self.assertIn("endtime=2026_09_08_12_32_15", d.url)
        self.assertTrue(d.player.playing)
        d.close()

    def test_admin_con_pin_arranca_en_caja(self) -> None:
        d = self._dialog(pin=True)
        d.admin_button.click()
        self.assertTrue(d.es_admin())
        self.assertEqual(d.canal_actual().nombre, "CAJA")
        self.assertIn("channel=2&", d.url)
        d.close()

    def test_cambiar_camara_recarga(self) -> None:
        d = self._dialog()
        d.camera_combo.setCurrentIndex(1)
        self.assertIn("channel=6&", d.url)
        self.assertEqual(len(d.player.sources), 2)
        d.close()

    def test_desplazar_un_minuto(self) -> None:
        d = self._dialog()
        d.later_button.click()
        inicio, fin = d.ventana()
        self.assertEqual(inicio, MOMENTO - ANTES + timedelta(minutes=1))
        self.assertEqual(fin, MOMENTO + DESPUES + timedelta(minutes=1))
        self.assertIn("starttime=2026_09_08_12_30_15", d.url)
        d.earlier_button.click()
        d.earlier_button.click()
        self.assertIn("starttime=2026_09_08_12_28_15", d.url)
        d.close()

    def test_posicion_actualiza_reloj_y_slider(self) -> None:
        d = self._dialog()
        d.player.durationChanged.emit(120000)
        self.assertEqual(d.slider.maximum(), 120000)
        d.player.positionChanged.emit(65000)
        self.assertEqual(d.time_label.text(), "12:30:20")  # inicio 12:29:15 + 65 s
        self.assertEqual(d.slider.value(), 65000)
        d.close()

    def test_pausa_y_reproducir(self) -> None:
        d = self._dialog()
        d.play_button.click()
        self.assertFalse(d.player.playing)
        self.assertIn("Reproducir", d.play_button.text())
        d.play_button.click()
        self.assertTrue(d.player.playing)
        d.close()

    def test_sin_configurar_muestra_aviso(self) -> None:
        d = self._dialog(DVRSettings())
        self.assertIsNone(d.url)
        self.assertFalse(d.message_label.isHidden())
        d.close()

    def test_cerrar_detiene_y_olvida_admin(self) -> None:
        d = self._dialog(pin=True)
        d.admin_button.click()
        d.close()
        self.assertFalse(d.player.playing)
        self.assertFalse(d.es_admin())


class PlaybackUrlTests(unittest.TestCase):
    def test_fin_antes_de_inicio_lanza(self) -> None:
        s = _settings()
        with self.assertRaises(ValueError):
            s.playback_url(2, MOMENTO, MOMENTO)

    def test_canal_por_nombre_respeta_modo(self) -> None:
        s = _settings()
        self.assertIsNone(s.canal_por_nombre("CAJA", admin=False))
        self.assertEqual(s.canal_por_nombre("caja", admin=True).canal, 2)
        self.assertEqual(s.canal_por_nombre("ENTRADA", admin=False).canal, 4)


if __name__ == "__main__":
    unittest.main()
