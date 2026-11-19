"""El PIN del dueño en las puertas del kiosko (Daniel, 2026-11-19).

Libreta, Conteos, precio especial, cambio fuera de plazo y el detalle del día
del Calendario: con el gafete del dueño ya no basta, hace falta su PIN. Y la
sesión del dueño se cierra sola a los 5 minutos sin tocar el kiosko.

Ninguna prueba abre un diálogo de verdad: se parchea el helper
(`pin_dueno_dialog.pedir_pin_dueno`) o el método `_pedir_pin_dueno` de la
pantalla. Ningún PIN real: los hashes salen de un PIN inventado.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from pos_uniformes.services import pin_dueno_service as pin_svc
from pos_uniformes.services.auth_service import AuthService
from pos_uniformes.ui.helpers import pin_dueno_dialog as pin_dlg

# La función de verdad, guardada al importar: conftest la reemplaza en cada
# prueba (por omisión niega), y aquí se prueba la real con `exec` parcheado.
_PEDIR_PIN_REAL = pin_dlg.pedir_pin_dueno

PIN_INVENTADO = "6142"
HASH_INVENTADO = AuthService.hash_password(PIN_INVENTADO)
DUENO = "VEND-1"


class _Qt(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])


class _ConCopiaLocal(_Qt):
    """La copia local del PIN en una carpeta de la prueba."""

    def setUp(self) -> None:
        self._dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._dir.cleanup)
        ruta = Path(self._dir.name) / "pin_dueno.json"
        p = patch.object(pin_svc, "_ruta_local", lambda: ruta)
        p.start()
        self.addCleanup(p.stop)


def _teclea(pin: str, llamadas: list | None = None):
    """Un `pedir_pin_dueno` falso que «teclea» `pin` y usa el servicio de verdad."""

    def _falso(parent, *, en_linea, motivo):
        if llamadas is not None:
            llamadas.append({"parent": parent, "en_linea": en_linea, "motivo": motivo})
        return pin_svc.verificar_pin_dueno(pin, en_linea=en_linea).ok

    return _falso


# ── el diálogo ───────────────────────────────────────────────────────────


class PinDuenoDialogTests(_ConCopiaLocal):
    def _dialogo(self, verificar=None, reloj=None, en_linea=False):
        from pos_uniformes.ui.helpers.pin_dueno_dialog import PinDuenoDialog

        self.control = pin_svc.ControlIntentos()
        self.ahora = [1000.0]
        dlg = PinDuenoDialog(
            None, en_linea=en_linea, motivo="Para abrir la Libreta como dueño.",
            verificar=verificar, control=self.control, reloj=reloj or (lambda: self.ahora[0]),
        )
        self.addCleanup(dlg.deleteLater)
        return dlg

    def _escribe(self, dlg, pin: str) -> None:
        dlg.pin_input.setText(pin)
        dlg.pin_input.returnPressed.emit()  # Enter acepta

    def test_lo_que_se_ve(self) -> None:
        from PyQt6.QtWidgets import QLineEdit, QPushButton

        dlg = self._dialogo()
        self.assertEqual(dlg.windowTitle(), "PIN del dueño")
        self.assertEqual(dlg.motivo_label.text(), "Para abrir la Libreta como dueño.")
        self.assertEqual(dlg.pin_input.echoMode(), QLineEdit.EchoMode.Password)
        teclas = {b.text() for b in dlg.findChildren(QPushButton)}
        self.assertTrue({"0", "1", "9", "⌫", "Aceptar", "Cancelar"} <= teclas)
        self.assertNotIn(".", teclas)  # el PIN no lleva punto

    def test_el_teclado_escribe_en_el_pin(self) -> None:
        from PyQt6.QtWidgets import QPushButton

        dlg = self._dialogo()
        teclas = {b.text(): b for b in dlg.findChildren(QPushButton)}
        for t in "61428":
            teclas[t].click()
        teclas["⌫"].click()
        self.assertEqual(dlg.pin_input.text(), PIN_INVENTADO)

    def test_pin_correcto_sin_conexion_con_copia_local(self) -> None:
        pin_svc.guardar_copia_local(HASH_INVENTADO)
        dlg = self._dialogo(en_linea=False)
        self._escribe(dlg, PIN_INVENTADO)
        self.assertTrue(dlg.autorizado)
        self.assertEqual(dlg.result(), dlg.DialogCode.Accepted)

    def test_pin_incorrecto_avisa_y_deja_reintentar(self) -> None:
        pin_svc.guardar_copia_local(HASH_INVENTADO)
        dlg = self._dialogo(en_linea=False)
        self._escribe(dlg, "1111")
        self.assertFalse(dlg.autorizado)
        self.assertIn("PIN incorrecto", dlg.aviso_label.text())
        self.assertFalse(dlg.aviso_label.isHidden())
        self.assertEqual(dlg.pin_input.text(), "")  # el campo se limpia
        self._escribe(dlg, PIN_INVENTADO)
        self.assertTrue(dlg.autorizado)
        self.assertEqual(self.control.fallos, 0)

    def test_cinco_fallos_bloquean_y_dicen_cuanto_falta(self) -> None:
        verificar = MagicMock(return_value=pin_svc.ResultadoPin(pin_svc.INCORRECTO, "PIN incorrecto."))
        dlg = self._dialogo(verificar=verificar)
        for _ in range(4):
            self._escribe(dlg, "1111")
        self._escribe(dlg, "1111")
        self.assertIn("espera 60 segundos", dlg.aviso_label.text())
        self.ahora[0] += 20
        verificar.reset_mock()
        self._escribe(dlg, PIN_INVENTADO)
        verificar.assert_not_called()  # bloqueado: ni se verifica
        self.assertIn("Espera 40 segundos", dlg.aviso_label.text())
        self.assertFalse(dlg.autorizado)
        self.ahora[0] += 41
        verificar.return_value = pin_svc.ResultadoPin(pin_svc.OK, "PIN correcto.")
        self._escribe(dlg, PIN_INVENTADO)
        self.assertTrue(dlg.autorizado)

    def test_sin_copia_y_sin_conexion_muestra_el_mensaje_y_no_autoriza(self) -> None:
        from PyQt6.QtWidgets import QMessageBox

        dlg = self._dialogo(en_linea=False)
        with patch.object(QMessageBox, "warning") as aviso:
            self._escribe(dlg, PIN_INVENTADO)
        self.assertFalse(dlg.autorizado)
        self.assertEqual(dlg.result(), dlg.DialogCode.Rejected)
        self.assertIn("Conecta la PC principal una vez", aviso.call_args.args[2])

    def test_sin_pin_dice_donde_definirlo(self) -> None:
        from PyQt6.QtWidgets import QMessageBox

        verificar = lambda pin, en_linea: pin_svc.ResultadoPin(pin_svc.SIN_PIN, pin_svc.MENSAJE_SIN_PIN)  # noqa: E731
        dlg = self._dialogo(verificar=verificar, en_linea=True)
        with patch.object(QMessageBox, "warning") as aviso:
            self._escribe(dlg, PIN_INVENTADO)
        self.assertFalse(dlg.autorizado)
        self.assertEqual(
            aviso.call_args.args[2],
            "Define tu PIN en el POS principal: Configuración › Empleadas › Definir PIN.",
        )

    def test_cancelar_no_autoriza(self) -> None:
        dlg = self._dialogo()
        dlg.pin_input.setText(PIN_INVENTADO)
        dlg.cancelar_button.click()
        self.assertFalse(dlg.autorizado)
        self.assertEqual(dlg.result(), dlg.DialogCode.Rejected)

    def test_vacio_no_cuenta_como_intento(self) -> None:
        verificar = MagicMock()
        dlg = self._dialogo(verificar=verificar)
        self._escribe(dlg, "")
        verificar.assert_not_called()
        self.assertEqual(dlg.aviso_label.text(), "Escribe tu PIN.")

    def test_en_linea_de_sube_hasta_la_ventana(self) -> None:
        from PyQt6.QtWidgets import QWidget

        from pos_uniformes.ui.helpers.pin_dueno_dialog import en_linea_de

        class _Ventana(QWidget):
            offline_mode = True

        v = _Ventana()
        hijo = QWidget(QWidget(v))
        self.addCleanup(v.deleteLater)
        self.assertFalse(en_linea_de(hijo))
        _Ventana.offline_mode = False
        self.assertTrue(en_linea_de(hijo))
        self.assertTrue(en_linea_de(None))


class PedirPinDuenoRealTests(_ConCopiaLocal):
    """`pedir_pin_dueno` tal cual, con `exec` parcheado (nada se queda esperando)."""

    def setUp(self) -> None:
        super().setUp()
        p = patch.object(pin_dlg, "_hay_pantalla", return_value=True)
        p.start()
        self.addCleanup(p.stop)
        self.addCleanup(pin_dlg.CONTROL_INTENTOS.registrar_exito)

    def _con_exec(self, hacer):
        """Parchea PinDuenoDialog.exec con `hacer(dlg)` y devuelve lo de la función real."""
        creados = []

        def _exec(dlg):
            creados.append(dlg)
            hacer(dlg)
            return dlg.result()

        with patch.object(pin_dlg.PinDuenoDialog, "exec", _exec):
            ok = _PEDIR_PIN_REAL(None, en_linea=False, motivo="Para abrir la Libreta como dueño.")
        return ok, creados

    def test_pin_bueno_devuelve_true(self) -> None:
        pin_svc.guardar_copia_local(HASH_INVENTADO)

        def teclea(dlg):
            dlg.pin_input.setText(PIN_INVENTADO)
            dlg.pin_input.returnPressed.emit()

        ok, creados = self._con_exec(teclea)
        self.assertTrue(ok)
        self.assertEqual(creados[0].motivo_label.text(), "Para abrir la Libreta como dueño.")

    def test_pin_malo_y_cancelar_devuelve_false(self) -> None:
        pin_svc.guardar_copia_local(HASH_INVENTADO)

        def malo_y_cancela(dlg):
            dlg.pin_input.setText("0000")
            dlg.pin_input.returnPressed.emit()
            dlg.cancelar_button.click()

        ok, _ = self._con_exec(malo_y_cancela)
        self.assertFalse(ok)

    def test_esc_y_cerrar_devuelven_false(self) -> None:
        from PyQt6.QtCore import Qt
        from PyQt6.QtTest import QTest

        pin_svc.guardar_copia_local(HASH_INVENTADO)

        def esc(dlg):
            dlg.pin_input.setText(PIN_INVENTADO)  # escrito pero sin aceptar
            dlg.show()
            QTest.keyClick(dlg, Qt.Key.Key_Escape)

        def cerrar(dlg):
            dlg.pin_input.setText(PIN_INVENTADO)
            dlg.show()
            dlg.close()

        for hacer in (esc, cerrar):
            ok, creados = self._con_exec(hacer)
            self.assertFalse(ok)
            self.assertEqual(creados[0].result(), creados[0].DialogCode.Rejected)

    def test_sin_pantalla_no_abre_nada_y_niega(self) -> None:
        with patch.object(pin_dlg, "_hay_pantalla", return_value=False), \
                patch.object(pin_dlg, "PinDuenoDialog") as dialogo:
            self.assertFalse(_PEDIR_PIN_REAL(None, en_linea=True, motivo="x"))
        dialogo.assert_not_called()

    def test_el_bloqueo_sobrevive_a_cerrar_y_reabrir(self) -> None:
        """Cerrar y volver a abrir el diálogo no reinicia la cuenta de intentos."""
        ahora = [1000.0]
        verificar = MagicMock(return_value=pin_svc.ResultadoPin(pin_svc.INCORRECTO, "PIN incorrecto."))

        def _dlg():
            d = pin_dlg.PinDuenoDialog(None, en_linea=False, motivo="x", verificar=verificar, reloj=lambda: ahora[0])
            self.addCleanup(d.deleteLater)
            return d

        primero = _dlg()
        for _ in range(5):
            primero.pin_input.setText("1111")
            primero.pin_input.returnPressed.emit()
        primero.cancelar_button.click()
        self.assertEqual(verificar.call_count, 5)

        ahora[0] += 10
        segundo = _dlg()
        segundo.pin_input.setText(PIN_INVENTADO)
        segundo.pin_input.returnPressed.emit()
        self.assertEqual(verificar.call_count, 5)  # bloqueado: ni se verificó
        self.assertIn("Espera 50 segundos", segundo.aviso_label.text())
        self.assertFalse(segundo.autorizado)


# ── a) Libreta ───────────────────────────────────────────────────────────


class LibretaTests(_ConCopiaLocal):
    def _fake(self, code: str, *, offline=True):
        from pos_uniformes.ui.quote_satellite_window import QuoteSatelliteWindow

        fake = SimpleNamespace(
            offline_mode=offline,
            libreta_gate_input=MagicMock(), libreta_gate_error=MagicMock(), libreta_gate=MagicMock(),
            libreta_view=MagicMock(), libreta_owner_panel=MagicMock(), libreta_owner_bar=MagicMock(),
            libreta_meta_bar=MagicMock(), libreta_meta_spin=MagicMock(), libreta_emp_list=MagicMock(),
            libreta_table=MagicMock(), libreta_titular_label=MagicMock(), libreta_ciclo_button=MagicMock(),
            _gafete_libreta_valido=lambda code: True, _sync_libreta_filtros=MagicMock(),
            _refresh_libreta_view=MagicMock(), _abrir_calendario_encargado=MagicMock(),
            _libreta_code=None, _libreta_is_owner=False,
        )
        fake._pedir_pin_dueno = lambda motivo: QuoteSatelliteWindow._pedir_pin_dueno(fake, motivo)
        fake.libreta_gate_input.text.return_value = code
        return fake

    def _escanea(self, fake) -> None:
        from pos_uniformes.ui.quote_satellite_window import QuoteSatelliteWindow

        with patch("pos_uniformes.services.libreta_meta_service.load_meta_semanal", return_value=0):
            QuoteSatelliteWindow._on_libreta_gate_scan(fake)

    def test_sin_conexion_con_copia_y_pin_bueno_entra(self) -> None:
        pin_svc.guardar_copia_local(HASH_INVENTADO)
        llamadas = []
        fake = self._fake("EMP:VEND-1")
        with patch("pos_uniformes.ui.helpers.pin_dueno_dialog.pedir_pin_dueno", _teclea(PIN_INVENTADO, llamadas)):
            self._escanea(fake)
        self.assertTrue(fake._libreta_is_owner)
        self.assertEqual(fake._libreta_code, DUENO)
        self.assertEqual(llamadas[0]["en_linea"], False)  # offline → copia local
        self.assertIs(llamadas[0]["parent"], fake)

    def test_pin_malo_no_entra_y_avisa(self) -> None:
        pin_svc.guardar_copia_local(HASH_INVENTADO)
        fake = self._fake("EMP:VEND-1")
        with patch("pos_uniformes.ui.helpers.pin_dueno_dialog.pedir_pin_dueno", _teclea("0000")):
            self._escanea(fake)
        self.assertFalse(fake._libreta_is_owner)
        self.assertIsNone(fake._libreta_code)
        fake.libreta_view.setVisible.assert_not_called()
        fake.libreta_gate_input.clear.assert_called()
        fake.libreta_gate_error.setText.assert_called_once_with("No se confirmó el PIN del dueño.")

    def test_sin_conexion_y_sin_copia_no_entra(self) -> None:
        fake = self._fake("EMP:VEND-1")
        with patch("pos_uniformes.ui.helpers.pin_dueno_dialog.pedir_pin_dueno", _teclea(PIN_INVENTADO)):
            self._escanea(fake)
        self.assertFalse(fake._libreta_is_owner)
        self.assertIsNone(fake._libreta_code)

    def test_en_linea_se_pasa_al_dialogo(self) -> None:
        llamadas = []
        fake = self._fake("VEND-1", offline=False)
        with patch("pos_uniformes.ui.helpers.pin_dueno_dialog.pedir_pin_dueno",
                   lambda parent, **kw: llamadas.append(kw) or False):
            self._escanea(fake)
        self.assertTrue(llamadas[0]["en_linea"])
        self.assertTrue(llamadas[0]["motivo"])

    def test_empleada_y_encargado_no_piden_pin(self) -> None:
        pedido = MagicMock(return_value=False)
        with patch("pos_uniformes.ui.helpers.pin_dueno_dialog.pedir_pin_dueno", pedido):
            empleada = self._fake("EMP:VEND-2")
            self._escanea(empleada)
            encargado = self._fake("ENC-1")
            self._escanea(encargado)
        pedido.assert_not_called()
        self.assertEqual(empleada._libreta_code, "VEND-2")
        self.assertFalse(empleada._libreta_is_owner)
        encargado._abrir_calendario_encargado.assert_called_once()

    def test_por_omision_las_pruebas_no_autorizan(self) -> None:
        """La red de conftest: sin parche, el PIN no se confirma (y nada se cuelga)."""
        fake = self._fake("EMP:VEND-1")
        self._escanea(fake)
        self.assertFalse(fake._libreta_is_owner)


class LibretaEndurecimientoTests(_Qt):
    """Sin sesión de dueño nada se hace a nombre del dueño."""

    def _fake(self, **kw):
        base = dict(_libreta_code=None, _libreta_is_owner=False, _set_status=MagicMock(),
                    _refresh_libreta_view=MagicMock(), libreta_meta_spin=MagicMock())
        base.update(kw)
        return SimpleNamespace(**base)

    def test_pagar_pendiente_exige_dueno(self) -> None:
        from pos_uniformes.ui.quote_satellite_window import QuoteSatelliteWindow

        with patch("pos_uniformes.ui.dialogs.corte_caja_dialog.confirmar_pago") as pago:
            QuoteSatelliteWindow._pagar_pendiente(self._fake(), "VEND-2", "Fanny López")
            pago.assert_not_called()
            pago.return_value = None
            QuoteSatelliteWindow._pagar_pendiente(
                self._fake(_libreta_code=DUENO, _libreta_is_owner=True), "VEND-2", "Fanny López"
            )
        self.assertEqual(pago.call_args.kwargs["creado_por"], DUENO)

    def test_meta_y_descuentos_exigen_dueno(self) -> None:
        from pos_uniformes.ui.quote_satellite_window import QuoteSatelliteWindow

        fake = self._fake()
        with patch("pos_uniformes.services.libreta_meta_service.save_meta_semanal") as guardar, \
                patch("PyQt6.QtWidgets.QInputDialog.getInt") as pedir, \
                patch("pos_uniformes.ui.dialogs.descuento_empleadas_dialog.abrir_descuento_empleadas") as desc:
            QuoteSatelliteWindow._guardar_meta_libreta(fake)
            QuoteSatelliteWindow._libreta_pedir_meta(fake)
            QuoteSatelliteWindow._libreta_descuento_empleadas(fake)
        guardar.assert_not_called()
        pedir.assert_not_called()
        desc.assert_not_called()

    def test_ya_no_hay_respaldo_al_codigo_del_dueno(self) -> None:
        import inspect

        from pos_uniformes.ui import quote_satellite_window as qsw

        fuente = inspect.getsource(qsw)
        self.assertNotIn('_libreta_code or "VEND-1"', fuente)
        self.assertNotIn("_libreta_code or 'VEND-1'", fuente)
        self.assertNotIn('None) or "VEND-1"', fuente)


# ── b) Conteos ───────────────────────────────────────────────────────────


class ConteosTests(_ConCopiaLocal):
    def _fake(self, code: str, pin_ok: bool):
        from pos_uniformes.ui.quote_satellite_window import QuoteSatelliteWindow

        self.pines = []
        fake = SimpleNamespace(
            offline_mode=True, conteos_gate_input=MagicMock(), conteos_gate_error=MagicMock(),
            conteos_titulo_label=MagicMock(), conteos_quien_label=MagicMock(), conteos_gate=MagicMock(),
            conteos_work=MagicMock(), _gafete_libreta_valido=lambda c: True,
            _nombre_de_gafete=lambda c: "", _refresh_conteos_vista=MagicMock(),
            _conteos_code=None, _conteos_nombre="",
            _pedir_pin_dueno=lambda motivo: self.pines.append(motivo) or pin_ok,
        )
        fake._conteos_es_dueno = lambda: QuoteSatelliteWindow._conteos_es_dueno(fake)
        fake.conteos_gate_input.text.return_value = code
        QuoteSatelliteWindow._on_conteos_gate_scan(fake)
        return fake

    def test_dueno_con_pin_bueno(self) -> None:
        fake = self._fake("EMP:VEND-1", pin_ok=True)
        self.assertEqual(fake._conteos_code, DUENO)
        self.assertEqual(len(self.pines), 1)
        fake.conteos_work.setVisible.assert_called_with(True)

    def test_dueno_con_pin_malo(self) -> None:
        fake = self._fake("EMP:VEND-1", pin_ok=False)
        self.assertIsNone(fake._conteos_code)
        fake.conteos_work.setVisible.assert_not_called()
        fake.conteos_gate_input.clear.assert_called()
        fake.conteos_gate_error.setText.assert_called_once_with("No se confirmó el PIN del dueño.")

    def test_empleada_no_pide_pin(self) -> None:
        fake = self._fake("VEND-4", pin_ok=False)
        self.assertEqual(fake._conteos_code, "VEND-4")
        self.assertEqual(self.pines, [])

    def test_sin_conexion_con_y_sin_copia_local(self) -> None:
        from pos_uniformes.ui.quote_satellite_window import QuoteSatelliteWindow

        def _con(pin):
            fake = self._fake("VEND-2", pin_ok=False)  # solo para tener el doble armado
            fake.conteos_gate_input.text.return_value = "EMP:VEND-1"
            fake._pedir_pin_dueno = lambda motivo: QuoteSatelliteWindow._pedir_pin_dueno(fake, motivo)
            fake._conteos_code = None
            with patch("pos_uniformes.ui.helpers.pin_dueno_dialog.pedir_pin_dueno", _teclea(pin)):
                QuoteSatelliteWindow._on_conteos_gate_scan(fake)
            return fake._conteos_code

        self.assertIsNone(_con(PIN_INVENTADO))  # sin copia: no hay con qué validar
        pin_svc.guardar_copia_local(HASH_INVENTADO)
        self.assertIsNone(_con("9999"))
        self.assertEqual(_con(PIN_INVENTADO), DUENO)

    def test_historial_solo_del_dueno(self) -> None:
        from pos_uniformes.ui.quote_satellite_window import QuoteSatelliteWindow

        with patch("pos_uniformes.ui.dialogs.conteo_historial_dialog.abrir_historial_conteos") as abrir:
            empleada = SimpleNamespace(_conteos_code="VEND-4", offline_mode=False)
            empleada._conteos_es_dueno = lambda: QuoteSatelliteWindow._conteos_es_dueno(empleada)
            QuoteSatelliteWindow._open_conteo_historial(empleada)
            abrir.assert_not_called()
            dueno = SimpleNamespace(_conteos_code=DUENO, offline_mode=False)
            dueno._conteos_es_dueno = lambda: QuoteSatelliteWindow._conteos_es_dueno(dueno)
            QuoteSatelliteWindow._open_conteo_historial(dueno)
            abrir.assert_called_once_with(dueno)


# ── c) Precio especial ───────────────────────────────────────────────────


class PrecioEspecialTests(_ConCopiaLocal):
    def _kiosko(self, offline=False):
        from pos_uniformes.ui.views.quick_sale_view import QuickSaleWidget

        w = QuickSaleWidget(SimpleNamespace(offline_mode=offline, _kiosk_lookup_from_cache=None, _db_online=not offline))
        w._employee_code, w._employee_name = "VEND-2", "Fanny"
        w._poner_categorias = lambda items: None
        self.addCleanup(w.deleteLater)
        return w

    def test_solo_pide_el_pin(self) -> None:
        w = self._kiosko(offline=True)
        llamadas = []
        pin_svc.guardar_copia_local(HASH_INVENTADO)
        with patch("pos_uniformes.ui.helpers.pin_dueno_dialog.pedir_pin_dueno", _teclea(PIN_INVENTADO, llamadas)):
            self.assertTrue(w._authorize_owner())
        self.assertEqual(llamadas[0]["en_linea"], False)
        self.assertIs(llamadas[0]["parent"], w)
        with patch("pos_uniformes.ui.helpers.pin_dueno_dialog.pedir_pin_dueno", _teclea("1234")):
            self.assertFalse(w._authorize_owner())

    def test_sin_conexion_sin_copia_no_autoriza(self) -> None:
        w = self._kiosko(offline=True)
        with patch("pos_uniformes.ui.helpers.pin_dueno_dialog.pedir_pin_dueno", _teclea(PIN_INVENTADO)):
            self.assertFalse(w._authorize_owner())

    def test_en_linea_pasa_en_linea(self) -> None:
        w = self._kiosko(offline=False)
        llamadas = []
        with patch("pos_uniformes.ui.helpers.pin_dueno_dialog.pedir_pin_dueno",
                   lambda parent, **kw: llamadas.append(kw) or True):
            self.assertTrue(w._authorize_owner())
        self.assertTrue(llamadas[0]["en_linea"])

    def test_pin_malo_no_pone_el_precio_especial(self) -> None:
        w = self._kiosko()
        with patch.object(w, "_pedir_pin_dueno", return_value=False), \
                patch.object(w, "_elegir_compradora") as elegir:
            w._accion_precio_especial.trigger()
        self.assertFalse(w._discount_active)
        elegir.assert_not_called()

    def test_ya_no_hay_regla_por_nombre(self) -> None:
        from pos_uniformes.ui.views.quick_sale_view import QuickSaleWidget

        self.assertFalse(hasattr(QuickSaleWidget, "_OWNER_NAME"))

    def test_el_gafete_ya_no_muestra_el_codigo_del_dueno(self) -> None:
        w = self._kiosko()
        self.assertEqual(w._gate_input.placeholderText(), "Gafete...")


# ── d) Cambio fuera de plazo o de Liquidación ────────────────────────────


class CambioTests(_Qt):
    def _fake(self, pin_ok: bool):
        from pos_uniformes.ui.views.quick_sale_view import QuickSaleWidget

        self.pines = []
        return SimpleNamespace(
            _OWNER_CODE=QuickSaleWidget._OWNER_CODE,
            _clean_scanned_code=QuickSaleWidget._clean_scanned_code,
            _pedir_pin_dueno=lambda motivo, parent=None: self.pines.append((motivo, parent)) or pin_ok,
        )

    def _autoriza(self, fake, codigo, dialogo="dlg"):
        from pos_uniformes.ui.helpers.quick_sale_folio_helper import FolioVentaMixin

        return FolioVentaMixin._dueno_autoriza_cambio(fake, dialogo, codigo)

    def test_gafete_y_pin_del_dueno(self) -> None:
        fake = self._fake(pin_ok=True)
        self.assertTrue(self._autoriza(fake, "EMP:VEND-1"))
        self.assertTrue(self._autoriza(fake, "EMPÑVEND'1"))  # teclado español del escáner
        self.assertEqual(self.pines[0][1], "dlg")  # el diálogo del PIN va sobre el del cambio

    def test_pin_malo_no_autoriza(self) -> None:
        self.assertFalse(self._autoriza(self._fake(pin_ok=False), "VEND-1"))

    def test_otro_gafete_ni_pide_pin(self) -> None:
        fake = self._fake(pin_ok=True)
        self.assertFalse(self._autoriza(fake, "VEND-2"))
        self.assertFalse(self._autoriza(fake, ""))
        self.assertFalse(self._autoriza(fake, None))
        self.assertEqual(self.pines, [])

    def test_en_el_dialogo_del_cambio(self) -> None:
        from PyQt6.QtWidgets import QMessageBox

        from pos_uniformes.tests.test_cambio_dialog import _datos, _renglones
        from pos_uniformes.ui.dialogs.cambio_dialog import CambioDialog

        for pin_ok in (False, True):
            fake = self._fake(pin_ok=pin_ok)
            dlg = CambioDialog(
                datos_venta=_datos(), renglones=_renglones(), abono=0, ya_quitado=0, dias=60,
                cliente=None, buscar_producto=lambda sku: None, elegir_cliente=lambda: None,
                es_dueno=lambda c: self._autoriza(fake, c, dlg), registrar=lambda d: None,
            )
            self.addCleanup(dlg.deleteLater)
            self.assertFalse(dlg.autorizado)  # 60 días: fuera de plazo
            dlg.gafete.setText("EMP:VEND-1")
            with patch.object(QMessageBox, "warning") as aviso:
                dlg._autorizar()
            self.assertEqual(dlg.autorizado, pin_ok)
            self.assertEqual(dlg.dueno, pin_ok)
            self.assertEqual(aviso.called, not pin_ok)
            self.assertIs(self.pines[0][1], dlg)



class CambioEnElKioskoTests(_ConCopiaLocal):
    """El `es_dueno` que de verdad le inyecta Venta rápida a CambioDialog."""

    def _es_dueno_inyectado(self, *, offline: bool):
        from contextlib import nullcontext

        from pos_uniformes.services import cambio_service as cs
        from pos_uniformes.ui.views.quick_sale_view import QuickSaleWidget

        # Arrancó sin conexión (offline_mode) pero la base ya contestó: el
        # cambio se abre, y el PIN se valida con la copia local.
        w = QuickSaleWidget(SimpleNamespace(offline_mode=offline, _kiosk_lookup_from_cache=None, _db_online=True))
        w._employee_code, w._employee_name = "VEND-2", "Fanny"
        self.addCleanup(w.deleteLater)
        capturado: dict = {}

        class _CambioFalso:
            def __init__(self, parent, **kw):
                capturado.update(kw)
                capturado["dialogo"] = self

            def exec(self):
                return 0

        sesion = MagicMock()
        sesion.get.return_value = SimpleNamespace(cliente_id=None, cliente="")
        with patch("pos_uniformes.database.connection.get_session", lambda: nullcontext(sesion)), \
                patch.object(cs, "renglones_vendidos", return_value=[SimpleNamespace(disponibles=1)]), \
                patch.object(cs, "contexto_cashback", return_value=(0, 0)), \
                patch.object(cs, "dias_desde", return_value=60), \
                patch("pos_uniformes.ui.dialogs.venta_folio_dialog.datos_de_venta", return_value={}), \
                patch("pos_uniformes.ui.dialogs.cambio_dialog.CambioDialog", _CambioFalso):
            w._hacer_cambio(SimpleNamespace(id=7))
        self.assertIn("es_dueno", capturado)
        return capturado["es_dueno"], capturado["dialogo"]

    def test_en_linea_gafete_y_pin(self) -> None:
        es_dueno, dialogo = self._es_dueno_inyectado(offline=False)
        llamadas = []
        with patch("pos_uniformes.ui.helpers.pin_dueno_dialog.pedir_pin_dueno",
                   lambda parent, **kw: llamadas.append((parent, kw)) or True):
            self.assertTrue(es_dueno("EMP:VEND-1"))
            self.assertFalse(es_dueno("VEND-2"))
        self.assertEqual(len(llamadas), 1)  # VEND-2 ni pide PIN
        self.assertIs(llamadas[0][0], dialogo)  # el PIN va sobre el diálogo del cambio
        self.assertTrue(llamadas[0][1]["en_linea"])
        with patch("pos_uniformes.ui.helpers.pin_dueno_dialog.pedir_pin_dueno", lambda *a, **k: False):
            self.assertFalse(es_dueno("EMP:VEND-1"))

    def test_sin_conexion_con_copia_local(self) -> None:
        es_dueno, _ = self._es_dueno_inyectado(offline=True)
        pin_svc.guardar_copia_local(HASH_INVENTADO)
        llamadas = []
        with patch("pos_uniformes.ui.helpers.pin_dueno_dialog.pedir_pin_dueno", _teclea(PIN_INVENTADO, llamadas)):
            self.assertTrue(es_dueno("EMP:VEND-1"))
        self.assertFalse(llamadas[0]["en_linea"])
        with patch("pos_uniformes.ui.helpers.pin_dueno_dialog.pedir_pin_dueno", _teclea("0000")):
            self.assertFalse(es_dueno("EMP:VEND-1"))

    def test_sin_conexion_sin_copia_local(self) -> None:
        es_dueno, _ = self._es_dueno_inyectado(offline=True)
        with patch("pos_uniformes.ui.helpers.pin_dueno_dialog.pedir_pin_dueno", _teclea(PIN_INVENTADO)):
            self.assertFalse(es_dueno("EMP:VEND-1"))


# ── e) Detalle del día del Calendario ────────────────────────────────────


class DiaCalendarioTests(_Qt):
    HOY = date(2026, 9, 8)

    def _dlg(self, pin_ok: bool):
        from pos_uniformes.services import dia_calendario_service as svc
        from pos_uniformes.ui.dialogs.dia_calendario_dialog import DiaCalendarioDialog

        self.pines = []
        resumen = svc.ResumenDia(self.HOY)
        with patch.object(DiaCalendarioDialog, "_cargar_resumen", return_value=resumen):
            dlg = DiaCalendarioDialog(
                None, self.HOY, hoy=self.HOY,
                pedir_pin_dueno=lambda motivo: self.pines.append(motivo) or pin_ok,
            )
        self.addCleanup(dlg.deleteLater)
        return dlg

    def _vista_todas(self):
        from pos_uniformes.services import dia_calendario_service as svc

        return svc.VistaPagos(True, "Daniel", [])

    def test_dueno_con_pin_ve_todas(self) -> None:
        dlg = self._dlg(pin_ok=True)
        with patch.object(dlg, "_consultar_pagos", return_value=self._vista_todas()) as consulta:
            dlg.scan_input.setText("EMP:VEND-1")
            dlg.scan_input.returnPressed.emit()
        consulta.assert_called_once()
        self.assertEqual(len(self.pines), 1)
        self.assertFalse(dlg.error_label.isVisibleTo(dlg))

    def test_dueno_con_pin_malo_no_ve_nada(self) -> None:
        from PyQt6.QtWidgets import QTableWidget

        dlg = self._dlg(pin_ok=False)
        with patch.object(dlg, "_consultar_pagos", return_value=self._vista_todas()) as consulta:
            dlg.scan_input.setText("EMPÑVEND'1")
            dlg.scan_input.returnPressed.emit()
        consulta.assert_not_called()
        self.assertEqual(dlg.pago_box.findChildren(QTableWidget), [])
        self.assertEqual(dlg.error_label.text(), "No se confirmó el PIN del dueño.")
        self.assertEqual(dlg.scan_input.text(), "")

    def test_encargado_y_empleada_sin_pin(self) -> None:
        dlg = self._dlg(pin_ok=False)
        with patch.object(dlg, "_consultar_pagos", return_value=None) as consulta:
            for code in ("ENC-1", "EMP:VEND-2"):
                dlg.scan_input.setText(code)
                dlg.scan_input.returnPressed.emit()
        self.assertEqual(consulta.call_count, 2)
        self.assertEqual(self.pines, [])

    def test_sin_inyectar_usa_el_helper(self) -> None:
        from pos_uniformes.services import dia_calendario_service as svc
        from pos_uniformes.ui.dialogs.dia_calendario_dialog import DiaCalendarioDialog

        with patch.object(DiaCalendarioDialog, "_cargar_resumen", return_value=svc.ResumenDia(self.HOY)):
            dlg = DiaCalendarioDialog(None, self.HOY, hoy=self.HOY)
        self.addCleanup(dlg.deleteLater)
        llamadas = []
        with patch("pos_uniformes.ui.helpers.pin_dueno_dialog.pedir_pin_dueno",
                   lambda parent, **kw: llamadas.append((parent, kw)) or False), \
                patch.object(dlg, "_consultar_pagos") as consulta:
            dlg.scan_input.setText("VEND-1")
            dlg.scan_input.returnPressed.emit()
        consulta.assert_not_called()
        self.assertIs(llamadas[0][0], dlg)
        self.assertTrue(llamadas[0][1]["en_linea"])


class DiaCalendarioSinConexionTests(_ConCopiaLocal):
    """Abierto sobre un kiosko sin conexión: el PIN se valida con la copia local."""

    HOY = date(2026, 9, 8)

    def _dlg(self):
        from PyQt6.QtWidgets import QWidget

        from pos_uniformes.services import dia_calendario_service as svc
        from pos_uniformes.ui.dialogs.dia_calendario_dialog import DiaCalendarioDialog

        class _Kiosko(QWidget):
            offline_mode = True

        kiosko = _Kiosko()
        self.addCleanup(kiosko.deleteLater)
        with patch.object(DiaCalendarioDialog, "_cargar_resumen", return_value=svc.ResumenDia(self.HOY)):
            dlg = DiaCalendarioDialog(kiosko, self.HOY, hoy=self.HOY)
        return dlg

    def _escanea(self, dlg, pin: str):
        from pos_uniformes.services import dia_calendario_service as svc

        llamadas = []
        with patch("pos_uniformes.ui.helpers.pin_dueno_dialog.pedir_pin_dueno", _teclea(pin, llamadas)), \
                patch.object(dlg, "_consultar_pagos", return_value=svc.VistaPagos(True, "Daniel", [])) as consulta:
            dlg.scan_input.setText("EMP:VEND-1")
            dlg.scan_input.returnPressed.emit()
        self.assertFalse(llamadas[0]["en_linea"])
        return consulta

    def test_sin_copia_local_no_se_consulta_nada(self) -> None:
        dlg = self._dlg()
        self._escanea(dlg, PIN_INVENTADO).assert_not_called()
        self.assertEqual(dlg.error_label.text(), "No se confirmó el PIN del dueño.")

    def test_con_copia_local_y_pin_bueno_se_consulta(self) -> None:
        pin_svc.guardar_copia_local(HASH_INVENTADO)
        dlg = self._dlg()
        self._escanea(dlg, PIN_INVENTADO).assert_called_once()

    def test_con_copia_local_y_pin_malo_no(self) -> None:
        pin_svc.guardar_copia_local(HASH_INVENTADO)
        dlg = self._dlg()
        self._escanea(dlg, "0000").assert_not_called()


# ── 4) Cierre por inactividad ────────────────────────────────────────────


class InactividadTests(_Qt):
    def _ventana(self, *, libreta_dueno=False, conteos=None):
        v = SimpleNamespace(
            _libreta_is_owner=libreta_dueno, _libreta_logout=MagicMock(), _conteos_code=conteos,
            _conteos_logout=MagicMock(), _set_status=MagicMock(),
        )
        v._conteos_es_dueno = lambda: v._conteos_code == DUENO
        return v

    def _cierre(self, ventana):
        from pos_uniformes.ui.helpers.cierre_inactividad_dueno import CierreInactividadDueno

        self.ahora = [0.0]
        c = CierreInactividadDueno(ventana, reloj=lambda: self.ahora[0])
        self.addCleanup(c.deleteLater)
        return c

    def test_cinco_minutos_cierran_la_libreta_y_conteos_del_dueno(self) -> None:
        v = self._ventana(libreta_dueno=True, conteos=DUENO)
        c = self._cierre(v)
        self.assertEqual(c.timer.interval(), 5 * 60 * 1000)
        self.assertTrue(c.timer.isSingleShot())
        self.ahora[0] = 299
        self.assertFalse(c.revisar())
        v._libreta_logout.assert_not_called()
        self.ahora[0] = 300
        self.assertTrue(c.revisar())
        v._libreta_logout.assert_called_once()
        v._conteos_logout.assert_called_once()
        v._set_status.assert_called_once_with("Se cerró la sesión del dueño por inactividad.")

    def test_la_actividad_reinicia_la_cuenta(self) -> None:
        v = self._ventana(libreta_dueno=True)
        c = self._cierre(v)
        c.timer.stop()
        self.ahora[0] = 280
        c.notar_actividad()
        self.assertTrue(c.timer.isActive())
        self.assertEqual(c.ultimo_toque, 280)
        self.ahora[0] = 400
        self.assertFalse(c.revisar())
        v._libreta_logout.assert_not_called()
        self.ahora[0] = 580
        self.assertTrue(c.revisar())

    def test_timer_preciso_y_si_vence_antes_se_rearma_solo_por_lo_que_falta(self) -> None:
        """Un timer que vence unos ms antes (299.6 s) no debe esperar otros 5 min."""
        from PyQt6.QtCore import Qt

        v = self._ventana(libreta_dueno=True)
        c = self._cierre(v)
        self.assertEqual(c.timer.timerType(), Qt.TimerType.PreciseTimer)
        self.ahora[0] = 299.6
        self.assertFalse(c.revisar())
        self.assertTrue(c.timer.isActive())
        self.assertLessEqual(c.timer.interval(), 1000)  # lo que falta, no 300 000
        self.ahora[0] = 300.0
        self.assertTrue(c.revisar())
        v._libreta_logout.assert_called_once()

    def test_la_actividad_vuelve_a_la_cuenta_completa(self) -> None:
        v = self._ventana(libreta_dueno=True)
        c = self._cierre(v)
        self.ahora[0] = 299.6
        c.revisar()  # rearmado corto
        c.notar_actividad()
        self.assertEqual(c.timer.interval(), 5 * 60 * 1000)

    def test_no_cierra_sesiones_de_empleadas(self) -> None:
        v = self._ventana(libreta_dueno=False, conteos="VEND-4")
        c = self._cierre(v)
        self.ahora[0] = 10_000
        self.assertFalse(c.revisar())
        v._libreta_logout.assert_not_called()
        v._conteos_logout.assert_not_called()
        v._set_status.assert_not_called()


class InactividadDialogosTests(_Qt):
    """Al cerrar por inactividad, los diálogos del dueño que quedaron abiertos
    encima del kiosko también se cierran (como Cancelar)."""

    def _kiosko(self, *, dueno: bool):
        from PyQt6.QtWidgets import QWidget

        class _Kiosko(QWidget):
            pass

        k = _Kiosko()
        k._libreta_is_owner = dueno
        k._libreta_logout = MagicMock()
        k._conteos_es_dueno = lambda: False
        k._conteos_logout = MagicMock()
        k._set_status = MagicMock()
        self.addCleanup(k.deleteLater)
        return k

    def _modal(self, padre):
        from PyQt6.QtWidgets import QDialog

        d = QDialog(padre)
        d.setModal(True)
        d.show()
        self.addCleanup(d.deleteLater)
        self.addCleanup(d.hide)
        return d

    def test_cierra_los_modales_del_dueno_y_luego_la_sesion(self) -> None:
        from PyQt6.QtWidgets import QWidget

        from pos_uniformes.ui.helpers.cierre_inactividad_dueno import cerrar_sesiones_de_dueno

        k = self._kiosko(dueno=True)
        historial = self._modal(k)
        encima = self._modal(QWidget(historial))  # un diálogo abierto desde otro
        self.assertIs(self.app.activeModalWidget(), encima)
        self.assertTrue(cerrar_sesiones_de_dueno(k))
        self.assertFalse(encima.isVisible())
        self.assertFalse(historial.isVisible())
        self.assertEqual(historial.result(), historial.DialogCode.Rejected)
        self.assertIsNone(self.app.activeModalWidget())
        k._libreta_logout.assert_called_once()

    def test_sin_sesion_de_dueno_no_toca_los_dialogos(self) -> None:
        from pos_uniformes.ui.helpers.cierre_inactividad_dueno import cerrar_sesiones_de_dueno

        k = self._kiosko(dueno=False)
        d = self._modal(k)
        self.assertFalse(cerrar_sesiones_de_dueno(k))
        self.assertTrue(d.isVisible())

    def test_no_cierra_modales_ajenos_al_kiosko(self) -> None:
        from pos_uniformes.ui.helpers.cierre_inactividad_dueno import cerrar_sesiones_de_dueno

        k = self._kiosko(dueno=True)
        ajeno = self._modal(None)
        self.assertTrue(cerrar_sesiones_de_dueno(k))
        self.assertTrue(ajeno.isVisible())
        k._libreta_logout.assert_called_once()


class WatchdogCopiaPinTests(_ConCopiaLocal):
    """El watchdog del kiosko refresca la copia local del PIN y no se cae si falla."""

    def _ciclo(self, sesion, *, parchear_refresco=True):
        import threading
        from contextlib import nullcontext

        from pos_uniformes.ui import quote_satellite_window as qsw

        win = qsw.QuoteSatelliteWindow(user_id=1, offline_mode=True)
        self.addCleanup(win.close)
        win._db_refresh_running = False
        win._db_refresh_ready = MagicMock()
        win._anuncios_ready = MagicMock()
        refresco = MagicMock()
        extra = [patch.object(qsw, "refrescar_copia_pin_dueno", refresco)] if parchear_refresco else []
        parches = [
            patch("pos_uniformes.services.satellite_startup_service.probe_database_host", return_value=True),
            patch.object(qsw, "get_session", lambda: nullcontext(sesion)),
            patch.object(qsw, "load_catalog_snapshot_rows", return_value=[{"sku": "SKU-1"}]),
            patch("pos_uniformes.services.foto_local_cache_service.sincronizar"),
            patch.object(qsw, "nombres_por_codigo"),
            patch.object(qsw, "list_all_active_links", return_value=["liga"]),
            # Los anuncios no se tocan aquí: que fallen al empezar (el ciclo los tolera).
            patch("pos_uniformes.services.satellite_identity_service.get_satellite_id",
                  side_effect=RuntimeError("fuera de la prueba")),
            *extra,
        ]
        for p in parches:
            p.start()
            self.addCleanup(p.stop)
        with patch.object(threading, "Thread") as hilo:
            win._start_background_db_refresh()
            hilo.call_args.kwargs["target"]()
        return win, refresco

    def test_refresca_la_copia_con_la_sesion(self) -> None:
        sesion = MagicMock()
        win, refresco = self._ciclo(sesion)
        refresco.assert_called_once_with(sesion)
        win._db_refresh_ready.emit.assert_called_once_with([{"sku": "SKU-1"}], ["liga"])

    def test_si_la_base_truena_al_leer_el_pin_el_ciclo_sigue(self) -> None:
        pin_svc.guardar_copia_local(HASH_INVENTADO)
        sesion = MagicMock()
        sesion.scalar.side_effect = OSError("la base se cayó a medias")
        win, _ = self._ciclo(sesion, parchear_refresco=False)
        win._db_refresh_ready.emit.assert_called_once_with([{"sku": "SKU-1"}], ["liga"])
        sesion.rollback.assert_called()
        self.assertEqual(pin_svc.leer_copia_local(), HASH_INVENTADO)  # la copia vieja sigue


class InactividadEnLaVentanaTests(_ConCopiaLocal):
    """Con la ventana de verdad: el filtro de teclas avisa y el cierre cierra."""

    def test_tecla_reinicia_y_cinco_minutos_cierran_la_libreta(self) -> None:
        from PyQt6.QtCore import QEvent, Qt
        from PyQt6.QtGui import QKeyEvent

        from pos_uniformes.ui.quote_satellite_window import QuoteSatelliteWindow

        win = QuoteSatelliteWindow(user_id=1, offline_mode=True)
        self.addCleanup(win.close)
        win._gafete_libreta_valido = lambda c: True
        win._pedir_pin_dueno = lambda motivo: True
        win._refresh_libreta_view = lambda: None
        win.libreta_gate_input.setText(DUENO)
        win._on_libreta_gate_scan()
        self.assertTrue(win._libreta_is_owner)

        ahora = [5000.0]
        win._cierre_dueno._reloj = lambda: ahora[0]
        QApplication.sendEvent(win, QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_A, Qt.KeyboardModifier.NoModifier, "a"))
        self.assertEqual(win._cierre_dueno.ultimo_toque, 5000.0)

        ahora[0] += 4 * 60
        self.assertFalse(win._cierre_dueno.revisar())
        self.assertTrue(win._libreta_is_owner)
        ahora[0] += 60
        self.assertTrue(win._cierre_dueno.revisar())
        self.assertFalse(win._libreta_is_owner)
        self.assertIsNone(win._libreta_code)
        self.assertFalse(win.libreta_gate.isHidden())


if __name__ == "__main__":
    unittest.main()
