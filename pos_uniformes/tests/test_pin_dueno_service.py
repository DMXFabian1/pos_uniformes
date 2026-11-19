"""El PIN del dueño en el kiosko: verificación, copia local, intentos e inactividad.

Ningún PIN real: los hashes se generan aquí con un PIN inventado."""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from pos_uniformes.services import pin_dueno_service as pd
from pos_uniformes.services.auth_service import AuthService
from pos_uniformes.services.nomina_service import OWNER_CODE

PIN_INVENTADO = "4821"
HASH_INVENTADO = AuthService.hash_password(PIN_INVENTADO)


class _SesionFalsa:
    """Basta con `scalar` y el context manager: lo demás no se usa."""

    def __init__(self, valor=None, error: Exception | None = None) -> None:
        self.valor = valor
        self.error = error
        self.consultas = []

    def __enter__(self):
        if self.error is not None:
            raise self.error
        return self

    def __exit__(self, *exc):
        return False

    def scalar(self, stmt):
        self.consultas.append(stmt)
        return self.valor


class _ConCarpeta(unittest.TestCase):
    def setUp(self) -> None:
        self._dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._dir.cleanup)
        self.ruta = Path(self._dir.name) / "data" / "pin_dueno.json"
        p = patch.object(pd, "_ruta_local", lambda: self.ruta)
        p.start()
        self.addCleanup(p.stop)


class VerificarPinTests(unittest.TestCase):
    def test_pin_correcto(self) -> None:
        self.assertTrue(pd.verificar_pin(HASH_INVENTADO, PIN_INVENTADO))

    def test_pin_correcto_con_espacios(self) -> None:
        self.assertTrue(pd.verificar_pin(HASH_INVENTADO, f" {PIN_INVENTADO} "))

    def test_pin_incorrecto(self) -> None:
        self.assertFalse(pd.verificar_pin(HASH_INVENTADO, "4822"))

    def test_sin_hash(self) -> None:
        self.assertFalse(pd.verificar_pin(None, PIN_INVENTADO))
        self.assertFalse(pd.verificar_pin("", PIN_INVENTADO))
        self.assertFalse(pd.verificar_pin("   ", PIN_INVENTADO))

    def test_nunca_compara_en_texto_plano(self) -> None:
        # verify_password aceptaría esto (compatibilidad vieja); aquí no.
        self.assertFalse(pd.verificar_pin(PIN_INVENTADO, PIN_INVENTADO))

    def test_pin_con_formato_invalido(self) -> None:
        for malo in ("", "12", "123456789", "12a4", None):
            self.assertFalse(pd.verificar_pin(HASH_INVENTADO, malo), malo)

    def test_hash_danado_no_truena(self) -> None:
        self.assertFalse(pd.verificar_pin("pbkdf2_sha256$muchas$00$00", PIN_INVENTADO))
        self.assertFalse(pd.verificar_pin("pbkdf2_sha256$1000$zz$00", PIN_INVENTADO))
        self.assertFalse(pd.verificar_pin("pbkdf2_sha256$", PIN_INVENTADO))

    def test_si_verify_password_truena_es_false(self) -> None:
        with patch.object(AuthService, "verify_password", side_effect=RuntimeError("x")):
            self.assertFalse(pd.verificar_pin(HASH_INVENTADO, PIN_INVENTADO))


class HashDelDuenoTests(unittest.TestCase):
    def test_devuelve_lo_que_lee_la_base(self) -> None:
        sesion = _SesionFalsa(HASH_INVENTADO)
        self.assertEqual(pd.hash_del_dueno(sesion), HASH_INVENTADO)
        sql = str(sesion.consultas[0].compile(compile_kwargs={"literal_binds": True}))
        self.assertIn(OWNER_CODE, sql)
        self.assertIn("activo", sql)

    def test_sin_pin_es_none(self) -> None:
        self.assertIsNone(pd.hash_del_dueno(_SesionFalsa(None)))
        self.assertIsNone(pd.hash_del_dueno(_SesionFalsa("  ")))


class CopiaLocalTests(_ConCarpeta):
    def test_guardar_y_leer(self) -> None:
        pd.guardar_copia_local(HASH_INVENTADO)
        datos = json.loads(self.ruta.read_text(encoding="utf-8"))
        self.assertEqual(datos["codigo"], OWNER_CODE)
        self.assertEqual(datos["pin_hash"], HASH_INVENTADO)
        self.assertTrue(datos["actualizado"])
        self.assertEqual(pd.leer_copia_local(), HASH_INVENTADO)

    def test_sin_temporales_tirados(self) -> None:
        pd.guardar_copia_local(HASH_INVENTADO)
        pd.guardar_copia_local(HASH_INVENTADO)
        self.assertEqual([p.name for p in self.ruta.parent.iterdir()], ["pin_dueno.json"])

    def test_escritura_atomica_con_os_replace(self) -> None:
        with patch.object(pd.os, "replace", wraps=pd.os.replace) as reemplazo:
            pd.guardar_copia_local(HASH_INVENTADO)
        reemplazo.assert_called_once()
        self.assertEqual(Path(reemplazo.call_args.args[1]), self.ruta)

    def test_si_falla_la_escritura_queda_la_copia_anterior(self) -> None:
        pd.guardar_copia_local(HASH_INVENTADO)
        otro = AuthService.hash_password("9137")
        with patch.object(pd.os, "replace", side_effect=OSError("disco lleno")):
            with self.assertRaises(OSError):
                pd.guardar_copia_local(otro)
        self.assertEqual(pd.leer_copia_local(), HASH_INVENTADO)
        self.assertEqual([p.name for p in self.ruta.parent.iterdir()], ["pin_dueno.json"])

    def test_sin_pin_borra_la_copia(self) -> None:
        pd.guardar_copia_local(HASH_INVENTADO)
        pd.guardar_copia_local(None)
        self.assertFalse(self.ruta.exists())
        self.assertIsNone(pd.leer_copia_local())

    def test_hash_en_texto_plano_no_se_guarda(self) -> None:
        pd.guardar_copia_local(PIN_INVENTADO)
        self.assertFalse(self.ruta.exists())

    def test_sin_archivo_es_none(self) -> None:
        self.assertIsNone(pd.leer_copia_local())

    def test_archivo_danado_es_none(self) -> None:
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        for contenido in ("{no es json", "[]", json.dumps({"codigo": OWNER_CODE, "pin_hash": PIN_INVENTADO}),
                          json.dumps({"codigo": "OTRO-9", "pin_hash": HASH_INVENTADO})):
            self.ruta.write_text(contenido, encoding="utf-8")
            self.assertIsNone(pd.leer_copia_local(), contenido)

    def test_refrescar_lee_la_base_y_guarda(self) -> None:
        pd.refrescar_copia_local(_SesionFalsa(HASH_INVENTADO))
        self.assertEqual(pd.leer_copia_local(), HASH_INVENTADO)

    def test_refrescar_sin_pin_borra(self) -> None:
        pd.guardar_copia_local(HASH_INVENTADO)
        pd.refrescar_copia_local(_SesionFalsa(None))
        self.assertIsNone(pd.leer_copia_local())

    def test_refrescar_nunca_truena(self) -> None:
        class _Rota:
            def scalar(self, stmt):
                raise RuntimeError("sin base")

        pd.guardar_copia_local(HASH_INVENTADO)
        pd.refrescar_copia_local(_Rota())  # no truena
        self.assertEqual(pd.leer_copia_local(), HASH_INVENTADO)  # y no borra lo que había


class VerificarPinDuenoTests(_ConCarpeta):
    def test_en_linea_correcto_y_refresca_la_copia(self) -> None:
        r = pd.verificar_pin_dueno(PIN_INVENTADO, sesion_factory=lambda: _SesionFalsa(HASH_INVENTADO))
        self.assertEqual(r.estado, pd.OK)
        self.assertTrue(r.ok)
        self.assertEqual(pd.leer_copia_local(), HASH_INVENTADO)

    def test_en_linea_incorrecto(self) -> None:
        r = pd.verificar_pin_dueno("0000", sesion_factory=lambda: _SesionFalsa(HASH_INVENTADO))
        self.assertEqual(r.estado, pd.INCORRECTO)
        self.assertFalse(r.ok)
        self.assertEqual(r.mensaje, "PIN incorrecto.")

    def test_en_linea_sin_pin(self) -> None:
        pd.guardar_copia_local(HASH_INVENTADO)
        r = pd.verificar_pin_dueno(PIN_INVENTADO, sesion_factory=lambda: _SesionFalsa(None))
        self.assertEqual(r.estado, pd.SIN_PIN)
        self.assertEqual(r.mensaje, "Define tu PIN en el POS principal: Configuración › Empleadas › Definir PIN.")
        # El dueño quitó su PIN: la copia vieja ya no vale.
        self.assertIsNone(pd.leer_copia_local())

    def test_en_linea_hash_en_texto_plano_es_sin_pin(self) -> None:
        """Un pin_hash viejo en texto plano en la base no es un PIN: ni siquiera
        tecleando ese mismo texto se entra, y no queda copia local."""
        pd.guardar_copia_local(HASH_INVENTADO)
        r = pd.verificar_pin_dueno(PIN_INVENTADO, sesion_factory=lambda: _SesionFalsa(PIN_INVENTADO))
        self.assertEqual(r.estado, pd.SIN_PIN)
        self.assertFalse(r.ok)
        self.assertIsNone(pd.leer_copia_local())
        self.assertFalse(self.ruta.exists())

    def test_base_caida_usa_la_copia(self) -> None:
        pd.guardar_copia_local(HASH_INVENTADO)
        caida = lambda: _SesionFalsa(error=OSError("sin red"))  # noqa: E731
        self.assertEqual(pd.verificar_pin_dueno(PIN_INVENTADO, sesion_factory=caida).estado, pd.OK)
        self.assertEqual(pd.verificar_pin_dueno("1111", sesion_factory=caida).estado, pd.INCORRECTO)

    def test_sin_conexion_con_copia(self) -> None:
        pd.guardar_copia_local(HASH_INVENTADO)

        def _no_debe_llamarse():
            raise AssertionError("sin conexión no se toca la base")

        r = pd.verificar_pin_dueno(PIN_INVENTADO, sesion_factory=_no_debe_llamarse, en_linea=False)
        self.assertEqual(r.estado, pd.OK)
        r = pd.verificar_pin_dueno("9999", sesion_factory=_no_debe_llamarse, en_linea=False)
        self.assertEqual(r.estado, pd.INCORRECTO)

    def test_sin_conexion_sin_copia(self) -> None:
        r = pd.verificar_pin_dueno(PIN_INVENTADO, en_linea=False)
        self.assertEqual(r.estado, pd.SIN_DATOS)
        self.assertIn("Sin conexión", r.mensaje)
        self.assertIn("Conecta la PC principal una vez", r.mensaje)

    def test_base_caida_sin_copia(self) -> None:
        caida = lambda: _SesionFalsa(error=OSError("sin red"))  # noqa: E731
        self.assertEqual(pd.verificar_pin_dueno(PIN_INVENTADO, sesion_factory=caida).estado, pd.SIN_DATOS)

    def test_copia_danada_sin_conexion_es_sin_datos(self) -> None:
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        self.ruta.write_text("{roto", encoding="utf-8")
        self.assertEqual(pd.verificar_pin_dueno(PIN_INVENTADO, en_linea=False).estado, pd.SIN_DATOS)

    def test_si_no_se_puede_guardar_la_copia_igual_verifica(self) -> None:
        with patch.object(pd, "guardar_copia_local", side_effect=OSError("solo lectura")):
            r = pd.verificar_pin_dueno(PIN_INVENTADO, sesion_factory=lambda: _SesionFalsa(HASH_INVENTADO))
        self.assertEqual(r.estado, pd.OK)


class ControlIntentosTests(unittest.TestCase):
    def test_cinco_fallos_bloquean_sesenta_segundos(self) -> None:
        c = pd.ControlIntentos()
        for i in range(4):
            self.assertEqual(c.registrar_fallo(100.0 + i), 0)
            self.assertFalse(c.bloqueado(100.0 + i))
        self.assertEqual(c.registrar_fallo(104.0), 60)
        self.assertTrue(c.bloqueado(104.0))
        self.assertEqual(c.segundos_restantes(134.0), 30)
        self.assertEqual(c.segundos_restantes(163.5), 1)
        self.assertFalse(c.bloqueado(164.0))
        # Al vencer, vuelve a contar desde cero.
        self.assertEqual(c.fallos, 0)
        self.assertEqual(c.registrar_fallo(165.0), 0)

    def test_fallos_durante_el_bloqueo_no_lo_alargan(self) -> None:
        c = pd.ControlIntentos(max_fallos=2, bloqueo_seg=10)
        c.registrar_fallo(0)
        c.registrar_fallo(0)
        self.assertEqual(c.registrar_fallo(5), 5)
        self.assertFalse(c.bloqueado(10))

    def test_un_acierto_reinicia_la_cuenta(self) -> None:
        c = pd.ControlIntentos()
        for i in range(4):
            c.registrar_fallo(i)
        c.registrar_exito()
        self.assertEqual(c.fallos, 0)
        for i in range(4):
            self.assertEqual(c.registrar_fallo(10 + i), 0)
        self.assertFalse(c.bloqueado(20))

    def test_sin_fallos_no_hay_bloqueo(self) -> None:
        self.assertEqual(pd.ControlIntentos().segundos_restantes(0), 0)


class InactividadTests(unittest.TestCase):
    def test_cinco_minutos_en_segundos(self) -> None:
        self.assertFalse(pd.debe_cerrar_sesion(1000.0, 1000.0 + 299))
        self.assertTrue(pd.debe_cerrar_sesion(1000.0, 1000.0 + 300))
        self.assertTrue(pd.debe_cerrar_sesion(1000.0, 1000.0 + 3600))

    def test_con_datetimes(self) -> None:
        t = datetime(2026, 11, 19, 12, 0)
        self.assertFalse(pd.debe_cerrar_sesion(t, t + timedelta(minutes=4, seconds=59)))
        self.assertTrue(pd.debe_cerrar_sesion(t, t + timedelta(minutes=5)))

    def test_otros_minutos(self) -> None:
        self.assertTrue(pd.debe_cerrar_sesion(0, 60, minutos=1))
        self.assertFalse(pd.debe_cerrar_sesion(0, 59, minutos=1))

    def test_sin_dato_no_cierra(self) -> None:
        self.assertFalse(pd.debe_cerrar_sesion(None, 1000.0))


if __name__ == "__main__":
    unittest.main()
