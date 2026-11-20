"""Un solo PIN: las puertas de administrador del kiosko piden el PIN del dueño
(Daniel, 2026-11-19: «quiero que sea el mismo pin para no tener tantos»).

Administración (Ctrl+Shift+A), «Ver todas» las cámaras, ejecutar desde el
buzón y ligar productos a escuelas comparaban contra un PIN fijo escrito en el
código (y el repo es público). Ahora usan `pin_dueno_dialog.pedir_pin_dueno`:
el PIN de Configuración › Empleadas, con copia local sin red y bloqueo por
intentos. Ninguna prueba abre un diálogo de verdad.
"""

from __future__ import annotations

import os
import re
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QDialog, QWidget

from pos_uniformes.ui.helpers import pin_dueno_dialog as pin_dlg

_RAIZ = Path(__file__).resolve().parents[1]


class _Llamadas:
    """Sustituto de `pedir_pin_dueno` que anota cómo lo llamaron."""

    def __init__(self, respuesta: bool) -> None:
        self.respuesta = respuesta
        self.llamadas: list[dict] = []

    def __call__(self, parent, *, en_linea, motivo):
        self.llamadas.append({"parent": parent, "en_linea": en_linea, "motivo": motivo})
        return self.respuesta


class _Qt(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])


class SinPinFijoEnElCodigoTest(unittest.TestCase):
    def test_ningun_archivo_trae_un_pin_de_administrador_fijo(self) -> None:
        culpables = []
        for carpeta in ("ui", "services", "api"):
            for ruta in (_RAIZ / carpeta).rglob("*.py"):
                texto = ruta.read_text(encoding="utf-8")
                if "_ADMIN_PIN" in texto or "_LABEL_PRINT_PINS" in texto or re.search(
                    r"\.strip\(\)\s*(==|!=|in|not in)\s*[\"'{]\s*[\"']?\d", texto
                ):
                    culpables.append(str(ruta.relative_to(_RAIZ)))
        self.assertEqual(culpables, [])

    def test_los_textos_ya_no_hablan_del_pin_de_administrador(self) -> None:
        for nombre in (
            "ui/dialogs/satellite_admin_dialog.py",
            "ui/dialogs/camera_wall_dialog.py",
            "ui/dialogs/buzon_dialog.py",
            "ui/dialogs/school_product_link_dialog.py",
        ):
            texto = (_RAIZ / nombre).read_text(encoding="utf-8")
            self.assertNotIn("PIN de administrador", texto, nombre)
            self.assertNotIn("contraseña de administrador", texto, nombre)


class AdministracionTest(_Qt):
    def test_prompt_pin_usa_el_pin_del_dueno(self) -> None:
        from pos_uniformes.ui.dialogs import satellite_admin_dialog as admin

        falso = _Llamadas(True)
        with patch.object(pin_dlg, "pedir_pin_dueno", falso):
            self.assertTrue(admin._prompt_pin(None))
        self.assertEqual(len(falso.llamadas), 1)
        self.assertIn("Administración", falso.llamadas[0]["motivo"])

    def test_prompt_pin_niega_si_el_dueno_no_lo_da(self) -> None:
        from pos_uniformes.ui.dialogs import satellite_admin_dialog as admin

        with patch.object(pin_dlg, "pedir_pin_dueno", _Llamadas(False)):
            self.assertFalse(admin._prompt_pin(None))

    def test_sin_red_valida_contra_la_copia_local(self) -> None:
        from pos_uniformes.ui.dialogs import satellite_admin_dialog as admin

        ventana = QWidget()
        ventana.offline_mode = True
        hijo = QWidget(ventana)
        falso = _Llamadas(True)
        with patch.object(pin_dlg, "pedir_pin_dueno", falso):
            admin._prompt_pin(hijo)
        self.assertFalse(falso.llamadas[0]["en_linea"])
        ventana.offline_mode = False
        with patch.object(pin_dlg, "pedir_pin_dueno", falso):
            admin._prompt_pin(hijo)
        self.assertTrue(falso.llamadas[1]["en_linea"])

    def test_sin_pin_no_abre_y_no_repite_el_aviso(self) -> None:
        from pos_uniformes.ui.dialogs import satellite_admin_dialog as admin

        with patch.object(pin_dlg, "pedir_pin_dueno", _Llamadas(False)), patch.object(
            admin, "QDialog"
        ) as dialogo, patch.object(admin.QMessageBox, "warning") as aviso:
            admin.open_satellite_admin_dialog(QWidget())
        dialogo.assert_not_called()
        aviso.assert_not_called()


class RescateDeConexionTest(_Qt):
    """Sin red y sin copia local del PIN no hay con qué validar, y la conexión
    vive en Administración: se abre solo la tarjeta de conexión."""

    def _ventana(self, offline: bool) -> QWidget:
        ventana = QWidget()
        ventana.offline_mode = offline
        return ventana

    def test_sin_red_y_sin_copia_es_rescate(self) -> None:
        from pos_uniformes.services import pin_dueno_service as pin_svc
        from pos_uniformes.ui.dialogs import satellite_admin_dialog as admin

        with patch.object(pin_svc, "leer_copia_local", return_value=None):
            self.assertTrue(admin._sin_red_ni_copia_del_pin(self._ventana(True)))
            self.assertFalse(admin._sin_red_ni_copia_del_pin(self._ventana(False)))
        with patch.object(pin_svc, "leer_copia_local", return_value="pbkdf2_sha256$x"):
            self.assertFalse(admin._sin_red_ni_copia_del_pin(self._ventana(True)))

    def test_en_rescate_no_pide_pin_y_solo_abre_la_conexion(self) -> None:
        from pos_uniformes.ui.dialogs import satellite_admin_dialog as admin

        with patch.object(admin, "_sin_red_ni_copia_del_pin", return_value=True), patch.object(
            admin, "_abrir_solo_conexion"
        ) as rescate, patch.object(admin, "_prompt_pin") as prompt:
            admin.open_satellite_admin_dialog(self._ventana(True))
        rescate.assert_called_once()
        prompt.assert_not_called()

    def test_con_copia_pide_el_pin_como_siempre(self) -> None:
        from pos_uniformes.ui.dialogs import satellite_admin_dialog as admin

        with patch.object(admin, "_sin_red_ni_copia_del_pin", return_value=False), patch.object(
            admin, "_abrir_solo_conexion"
        ) as rescate, patch.object(admin, "_prompt_pin", return_value=False) as prompt:
            admin.open_satellite_admin_dialog(self._ventana(True))
        rescate.assert_not_called()
        prompt.assert_called_once()

    def test_la_ventana_de_rescate_solo_trae_la_conexion(self) -> None:
        from PyQt6.QtWidgets import QGroupBox

        from pos_uniformes.ui.dialogs import satellite_admin_dialog as admin

        vistas = []

        def _exec(dlg):
            vistas.extend(g.title() for g in dlg.findChildren(QGroupBox))
            return 0

        with patch.object(admin.QDialog, "exec", _exec):
            admin._abrir_solo_conexion(self._ventana(True))
        self.assertEqual(vistas, ["Conexión con la PC principal"])


class FavoritosTest(_Qt):
    def test_favoritos_pide_el_pin_del_dueno(self) -> None:
        from pos_uniformes.ui.quote_satellite_window import QuoteSatelliteWindow

        ventana = MagicMock()
        ventana._pedir_pin_dueno.return_value = True
        self.assertTrue(QuoteSatelliteWindow._confirm_favorites_password(ventana, "agregar este favorito"))
        ventana._pedir_pin_dueno.assert_called_once_with("Para agregar este favorito.")
        ventana._pedir_pin_dueno.return_value = False
        self.assertFalse(QuoteSatelliteWindow._confirm_favorites_password(ventana, "quitar este favorito"))


class CamarasTest(_Qt):
    def test_ver_todas_pide_el_pin_del_dueno(self) -> None:
        from pos_uniformes.ui.dialogs import camera_wall_dialog as camaras

        falso = _Llamadas(True)
        with patch.object(pin_dlg, "pedir_pin_dueno", falso):
            self.assertTrue(camaras._default_pin_prompt(None))
        self.assertIn("cámaras", falso.llamadas[0]["motivo"])

    def test_grabaciones_no_avisa_pin_incorrecto_al_cancelar(self) -> None:
        texto = (_RAIZ / "ui/dialogs/camera_playback_dialog.py").read_text(encoding="utf-8")
        self.assertNotIn("PIN incorrecto", texto)


class LigarProductosTest(_Qt):
    def test_con_el_pin_del_dueno_abre(self) -> None:
        from pos_uniformes.ui.dialogs import school_product_link_dialog as ligar

        falso = _Llamadas(True)
        with patch.object(pin_dlg, "pedir_pin_dueno", falso), patch.object(
            ligar, "SchoolProductLinkDialog"
        ) as dialogo:
            ligar.prompt_school_product_link_admin(None)
        dialogo.assert_called_once()
        dialogo.return_value.exec.assert_called_once()
        self.assertIn("escuelas", falso.llamadas[0]["motivo"])

    def test_sin_el_pin_no_abre(self) -> None:
        from pos_uniformes.ui.dialogs import school_product_link_dialog as ligar

        with patch.object(pin_dlg, "pedir_pin_dueno", _Llamadas(False)), patch.object(
            ligar, "SchoolProductLinkDialog"
        ) as dialogo:
            ligar.prompt_school_product_link_admin(None)
        dialogo.assert_not_called()


class BuzonTest(_Qt):
    def _confirmar(self, *, acepta: bool, pin: bool):
        from pos_uniformes.ui.dialogs import buzon_dialog as buzon

        ventana = MagicMock()
        ventana.exec.return_value = (
            QDialog.DialogCode.Accepted if acepta else QDialog.DialogCode.Rejected
        )
        falso = _Llamadas(pin)
        with patch.object(buzon, "_ConfirmarEjecucion", return_value=ventana), patch.object(
            pin_dlg, "pedir_pin_dueno", falso
        ):
            respuesta = buzon._confirmar_con_pin(QWidget(), "Get-Date", "Claude")
        return respuesta, falso

    def test_con_el_pin_del_dueno_se_ejecuta(self) -> None:
        respuesta, falso = self._confirmar(acepta=True, pin=True)
        self.assertIs(respuesta, True)
        self.assertIn("Claude", falso.llamadas[0]["motivo"])

    def test_sin_el_pin_no_se_ejecuta_y_no_avisa_dos_veces(self) -> None:
        respuesta, _ = self._confirmar(acepta=True, pin=False)
        self.assertIsNone(respuesta)

    def test_si_se_arrepiente_ni_siquiera_pide_el_pin(self) -> None:
        respuesta, falso = self._confirmar(acepta=False, pin=True)
        self.assertIsNone(respuesta)
        self.assertEqual(falso.llamadas, [])


if __name__ == "__main__":
    unittest.main()
