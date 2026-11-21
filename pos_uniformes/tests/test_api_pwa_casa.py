"""La PWA de la casa: llave de sesiones, modo casa (solo consulta) y frescura.

- Llave: ya no es la pública del repo; se genera una vez y se reutiliza, y la
  de POS_API_SECRET_KEY manda.
- Modo: POS_PWA_MODO=casa rechaza todo lo que escribe (409 «solo_en_tienda»)
  salvo entrar y salir; sin la variable, todo igual que antes.
- Frescura: /movil/inicio en casa trae "datos_de" (hora de la tienda de la copia).
"""

from __future__ import annotations

import os
import stat
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import jwt
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from pos_uniformes.api.dependencies import get_db
from pos_uniformes.api.main import app
from pos_uniformes.api.services.limite_login import LimiteLogin, limite_login
from pos_uniformes.api.services.token_service import ALGORITHM, TokenService
from pos_uniformes.database.connection import build_connect_args
from pos_uniformes.database.models import Empleada
from pos_uniformes.services.auth_service import AuthService
from pos_uniformes.services.frescura_copia_service import datos_de, hora_de_la_nota
from pos_uniformes.services import version_base_service
from pos_uniformes.utils import config, llave_api
from pos_uniformes.utils.llave_api import LLAVE_PUBLICA_VIEJA, resolver_llave


class _ConModo:
    """Pone POS_PWA_MODO (o lo quita) y limpia el caché de modo_pwa."""

    def __init__(self, modo: str | None) -> None:
        self.modo = modo

    def __enter__(self):
        self._antes = os.environ.get("POS_PWA_MODO")
        os.environ["POS_PWA_MODO"] = self.modo or ""
        config.modo_pwa.cache_clear()
        return self

    def __exit__(self, *exc) -> None:
        if self._antes is None:
            os.environ.pop("POS_PWA_MODO", None)
        else:
            os.environ["POS_PWA_MODO"] = self._antes
        config.modo_pwa.cache_clear()


# ─── Llave de sesiones ────────────────────────────────────────────────────


class LlaveSesionesTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.ruta = Path(self._tmp.name) / "data" / "api_secret.key"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_sin_llave_se_genera_una_vez_y_se_reutiliza(self) -> None:
        primera = resolver_llave("", self.ruta)
        self.assertTrue(self.ruta.exists())
        self.assertGreaterEqual(len(primera), 60)  # token_urlsafe(48) = 64 caracteres
        self.assertEqual(self.ruta.read_text(encoding="utf-8").strip(), primera)
        self.assertEqual(resolver_llave(None, self.ruta), primera)
        self.assertEqual(resolver_llave("", self.ruta), primera)
        # sin restos del archivo temporal
        self.assertEqual([p.name for p in self.ruta.parent.iterdir()], ["api_secret.key"])

    @unittest.skipIf(sys.platform.startswith("win"), "permisos POSIX")
    def test_el_archivo_solo_lo_lee_el_dueno(self) -> None:
        resolver_llave("", self.ruta)
        modo = stat.S_IMODE(self.ruta.stat().st_mode)
        self.assertEqual(modo, 0o600)

    def test_la_publica_vieja_se_reemplaza(self) -> None:
        llave = resolver_llave(LLAVE_PUBLICA_VIEJA, self.ruta)
        self.assertNotEqual(llave, LLAVE_PUBLICA_VIEJA)
        self.assertTrue(self.ruta.exists())
        # y tampoco se acepta si alguien la dejó escrita en el archivo
        self.ruta.write_text(LLAVE_PUBLICA_VIEJA, encoding="utf-8")
        otra = resolver_llave("", self.ruta)
        self.assertNotEqual(otra, LLAVE_PUBLICA_VIEJA)
        self.assertEqual(self.ruta.read_text(encoding="utf-8").strip(), otra)

    def test_la_del_entorno_manda_y_no_escribe_archivo(self) -> None:
        propia = "una-llave-larga-puesta-por-daniel-" + "z" * 30
        self.assertEqual(resolver_llave(propia, self.ruta), propia)
        self.assertFalse(self.ruta.exists())

    def test_un_archivo_truncado_se_reemplaza(self) -> None:
        self.ruta.parent.mkdir(parents=True)
        self.ruta.write_text("corta", encoding="utf-8")
        llave = resolver_llave("", self.ruta)
        self.assertNotEqual(llave, "corta")
        self.assertEqual(self.ruta.read_text(encoding="utf-8").strip(), llave)

    def test_sin_carpeta_escribible_sigue_en_memoria(self) -> None:
        with patch.object(llave_api, "_escribir", side_effect=PermissionError("solo lectura")):
            llave = resolver_llave("", self.ruta)
        self.assertGreaterEqual(len(llave), 60)

    def test_dos_procesos_a_la_vez_usan_la_misma(self) -> None:
        # B llega a escribir después de que A ya la creó (los dos vieron que no
        # había): B no la pisa, usa la de A.
        a = llave_api._escribir(self.ruta, "A" * 40)
        b = llave_api._escribir(self.ruta, "B" * 40)
        self.assertEqual(a, "A" * 40)
        self.assertEqual(b, "A" * 40)
        self.assertEqual(self.ruta.read_text(encoding="utf-8").strip(), "A" * 40)
        self.assertEqual([p.name for p in self.ruta.parent.iterdir()], ["api_secret.key"])

    def test_sin_enlaces_duros_tampoco_se_pisa(self) -> None:
        with patch.object(llave_api.os, "link", side_effect=OSError("sin enlaces")):
            a = llave_api._escribir(self.ruta, "A" * 40)
            b = llave_api._escribir(self.ruta, "B" * 40)
        self.assertEqual((a, b), ("A" * 40, "A" * 40))
        self.assertEqual(self.ruta.read_text(encoding="utf-8").strip(), "A" * 40)

    def test_en_windows_se_restringe_con_icacls(self) -> None:
        llamadas = []

        def falso_run(args, **kw):
            llamadas.append(args)
            salida = '"pc\\pos","S-1-5-21-1-2-3-1001"' if args[0] == "whoami" else ""
            return type("R", (), {"returncode": 0, "stdout": salida})()

        with patch.object(llave_api, "_ES_WINDOWS", True), \
                patch.object(llave_api.subprocess, "run", side_effect=falso_run):
            llave_api._restringir_en_windows(self.ruta)
        icacls = llamadas[-1]
        self.assertEqual(icacls[0], "icacls")
        self.assertIn("/inheritance:r", icacls)
        for sid in ("*S-1-5-21-1-2-3-1001:F", "*S-1-5-18:F", "*S-1-5-32-544:F"):
            self.assertIn(sid, icacls)
        # sin saber la cuenta no se toca nada (mejor que dejarla sin dueño)
        llamadas.clear()
        with patch.object(llave_api, "_ES_WINDOWS", True), patch.object(
            llave_api.subprocess, "run",
            side_effect=lambda a, **k: type("R", (), {"returncode": 1, "stdout": ""})(),
        ) as run:
            llave_api._restringir_en_windows(self.ruta)
        self.assertEqual(run.call_count, 1)  # solo whoami

    def test_fuera_de_windows_no_llama_icacls(self) -> None:
        with patch.object(llave_api, "_ES_WINDOWS", False), \
                patch.object(llave_api.subprocess, "run") as run:
            llave_api._restringir_en_windows(self.ruta)
        run.assert_not_called()

    def test_settings_lee_llave_y_horas_del_entorno(self) -> None:
        with patch.dict(os.environ, {
            "POS_API_SECRET_KEY": "  llave-del-entorno  ",
            "POS_API_TOKEN_EXPIRE_HOURS": "24",
        }):
            s = config.Settings.from_env()
        self.assertEqual(s.api_secret_key, "llave-del-entorno")
        self.assertEqual(s.api_token_expire_hours, 24)
        with patch.dict(os.environ, {"POS_API_TOKEN_EXPIRE_HOURS": "nada"}):
            self.assertEqual(config.Settings.from_env().api_token_expire_hours, 8)

    def test_un_token_firmado_con_la_llave_publica_ya_no_sirve(self) -> None:
        llave_api.olvidar_llave_en_memoria()
        try:
            falso = jwt.encode(
                {"sub": "1", "name": "Daniel", "device_id": "x",
                 "exp": datetime(2100, 1, 1)},
                LLAVE_PUBLICA_VIEJA, algorithm=ALGORITHM,
            )
            with self.assertRaises(jwt.InvalidTokenError):
                TokenService.decode_token(falso)
            bueno, _ = TokenService.create_token(1, "Daniel")
            self.assertEqual(TokenService.decode_token(bueno).employee_id, 1)
        finally:
            llave_api.olvidar_llave_en_memoria()


# ─── Modo casa ────────────────────────────────────────────────────────────


class ModoServidorTests(unittest.TestCase):
    def test_sin_variable_es_como_antes(self) -> None:
        from pos_uniformes.api.routers.movil import _modo_servidor
        from pos_uniformes.database.connection import engine

        esperado = "casa" if engine.url.get_backend_name() == "sqlite" else "tienda"
        with _ConModo(None):
            self.assertEqual(_modo_servidor(), esperado)
        with _ConModo("cualquier-cosa"):
            self.assertEqual(_modo_servidor(), esperado)

    def test_la_variable_manda(self) -> None:
        from pos_uniformes.api.routers.movil import _modo_servidor

        with _ConModo("casa"):
            self.assertEqual(_modo_servidor(), "casa")
        with _ConModo(" TIENDA "):
            self.assertEqual(_modo_servidor(), "tienda")

    def test_conexion_de_solo_lectura(self) -> None:
        args = build_connect_args(30_000, solo_lectura=True)
        self.assertIn("-c statement_timeout=30000", args["options"])
        self.assertIn("-c default_transaction_read_only=on", args["options"])
        self.assertEqual(build_connect_args(0, solo_lectura=True)["options"],
                         "-c default_transaction_read_only=on")
        # la tienda: igual que antes
        self.assertEqual(build_connect_args(30_000)["options"], "-c statement_timeout=30000")
        self.assertNotIn("options", build_connect_args(0))


class ModoCasaApiTests(unittest.TestCase):
    _ESCRITURAS = [
        ("post", "/api/v1/quotes"),
        ("put", "/api/v1/quotes/1"),
        ("delete", "/api/v1/quotes/1"),
        ("post", "/api/v1/quotes/1/ready"),
        ("post", "/api/v1/favorites/toggle"),
        ("post", "/api/v1/search/reindex"),
        ("post", "/api/v1/movil/etiqueta"),
        ("post", "/api/v1/movil/encargado/marcar"),
        ("post", "/api/v1/movil/encargado/corte"),
        ("post", "/api/v1/movil/dueno/corte"),
        ("post", "/api/v1/movil/dueno/nombrar"),
        ("post", "/api/v1/movil/conteos"),
        ("post", "/api/v1/movil/conteos/1/tallas"),
        ("post", "/api/v1/movil/conteos/1/terminar"),
        ("post", "/api/v1/movil/bodega/llego"),
        ("post", "/api/v1/movil/bodega/piso"),
        ("post", "/api/v1/movil/bodega/corregir"),
        ("patch", "/api/v1/movil/inicio"),
    ]

    def setUp(self) -> None:
        engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
        )
        Empleada.__table__.create(engine)
        self.session = sessionmaker(bind=engine)()
        self.session.add(Empleada(
            codigo="VEND-1", nombre_completo="Daniel Fabian", activo=True,
            pin_hash=AuthService.hash_password("1234"),
        ))
        self.session.commit()
        self.dueno_id = self.session.query(Empleada).one().id
        app.dependency_overrides[get_db] = lambda: self.session
        self.client = TestClient(app)
        limite_login.olvidar()

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        self.session.close()
        limite_login.olvidar()

    def _token(self) -> str:
        r = self.client.post("/api/v1/auth/login",
                             json={"employee_id": self.dueno_id, "pin": "1234"})
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()["token"]

    def test_en_casa_todo_lo_que_escribe_es_409(self) -> None:
        with _ConModo("casa"):
            h = {"Authorization": "Bearer " + self._token()}
            for metodo, ruta in self._ESCRITURAS:
                with self.subTest(metodo=metodo, ruta=ruta):
                    r = self.client.request(metodo.upper(), ruta, headers=h, json={})
                    self.assertEqual(r.status_code, 409)
                    self.assertEqual(r.json()["detail"]["error"]["code"], "solo_en_tienda")
                    self.assertEqual(r.json()["detail"]["error"]["message"],
                                     "Esta acción solo funciona conectado a la tienda.")

    def test_en_casa_se_entra_y_se_sale(self) -> None:
        with _ConModo("casa"):
            token = self._token()
            h = {"Authorization": "Bearer " + token}
            self.assertEqual(self.client.get("/api/v1/auth/me", headers=h).status_code, 200)
            self.assertEqual(self.client.post("/api/v1/auth/logout", headers=h).status_code, 204)
            self.assertEqual(self.client.get("/api/v1/auth/employees").status_code, 200)

    def test_en_casa_se_frena_a_quien_adivina_el_pin(self) -> None:
        with _ConModo("casa"):
            for _ in range(5):
                r = self.client.post("/api/v1/auth/login",
                                     json={"employee_id": self.dueno_id, "pin": "9999"})
                self.assertEqual(r.status_code, 401)
            r = self.client.post("/api/v1/auth/login",
                                 json={"employee_id": self.dueno_id, "pin": "1234"})
            self.assertEqual(r.status_code, 429)  # ni con el bueno, hasta que pase
            self.assertEqual(r.json()["detail"]["error"]["code"], "demasiados_intentos")
            self.assertGreater(int(r.headers["Retry-After"]), 0)

    def test_en_tienda_no_hay_freno(self) -> None:
        with _ConModo("tienda"):
            for _ in range(8):
                r = self.client.post("/api/v1/auth/login",
                                     json={"employee_id": self.dueno_id, "pin": "9999"})
                self.assertEqual(r.status_code, 401)
            self._token()

    def test_sin_modo_casa_el_candado_no_estorba(self) -> None:
        with _ConModo("tienda"):
            r = self.client.post("/api/v1/favorites/toggle", json={})
            self.assertNotEqual(r.status_code, 409)  # llega al router (401/403/422)

    def test_inicio_en_casa_trae_datos_de(self) -> None:
        with _ConModo("casa"), patch(
            "pos_uniformes.services.frescura_copia_service.datos_de",
            return_value="2026-11-20T14:15",
        ), patch("pos_uniformes.api.routers.movil._payload_dueno", return_value={}):
            h = {"Authorization": "Bearer " + self._token()}
            data = self.client.get("/api/v1/movil/inicio", headers=h).json()
        self.assertEqual(data["modo"], "casa")
        self.assertEqual(data["datos_de"], "2026-11-20T14:15")

    def test_inicio_en_tienda_no_trae_datos_de(self) -> None:
        with _ConModo("tienda"), patch(
            "pos_uniformes.api.routers.movil._payload_dueno", return_value={},
        ):
            h = {"Authorization": "Bearer " + self._token()}
            data = self.client.get("/api/v1/movil/inicio", headers=h).json()
        self.assertEqual(data["modo"], "tienda")
        self.assertNotIn("datos_de", data)


# ─── Pedir una copia nueva (solo casa) ───────────────────────────────────


class _DisparadorFalso:
    """nucleo-pedir-copia de mentira en 127.0.0.1: contesta lo que se le diga
    (código, cuerpo, espera) y anota qué firma le llegó (tokens) y todas las
    cabeceras (para revisar que el token no viaje)."""

    def __init__(self) -> None:
        import http.server
        import threading

        falso = self
        self.codigo, self.cuerpo, self.espera, self.tokens = 200, {"estado": "pidiendo"}, 0.0, []
        self.cabeceras, self.rutas = [], []

        class Manejador(http.server.BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                import json as _json
                import time as _time

                falso.tokens.append(self.headers.get("X-Firma"))
                falso.cabeceras.append(dict(self.headers.items()))
                falso.rutas.append(self.path)
                if falso.espera:
                    _time.sleep(falso.espera)
                cuerpo = _json.dumps(falso.cuerpo).encode()
                self.send_response(falso.codigo)
                self.send_header("Content-Length", str(len(cuerpo)))
                self.end_headers()
                self.wfile.write(cuerpo)

            def log_message(self, *args):
                pass

        self.servidor = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Manejador)
        self.servidor.daemon_threads = True
        self.url = f"http://127.0.0.1:{self.servidor.server_address[1]}/copia"
        threading.Thread(target=self.servidor.serve_forever, daemon=True).start()

    def cerrar(self) -> None:
        self.servidor.shutdown()
        self.servidor.server_close()


class PedirCopiaTests(unittest.TestCase):
    """POST /api/v1/movil/actualizar: en casa le pide la copia a nucleo."""

    RUTA = "/api/v1/movil/actualizar"

    def setUp(self) -> None:
        ModoCasaApiTests.setUp(self)
        self._tmp = tempfile.TemporaryDirectory()
        self.archivo_token = Path(self._tmp.name) / "pedir-copia.token"
        self.archivo_token.write_text("token-de-prueba\n", encoding="utf-8")
        self.falso = _DisparadorFalso()
        self._datos_de = patch("pos_uniformes.services.frescura_copia_service.datos_de",
                               return_value="2026-11-20T17:31")
        self._datos_de.start()

    def tearDown(self) -> None:
        self._datos_de.stop()
        self.falso.cerrar()
        self._tmp.cleanup()
        ModoCasaApiTests.tearDown(self)

    def _entorno(self, url: str | None = None, archivo: str | None = None):
        return patch.dict(os.environ, {
            "POS_PWA_PEDIR_COPIA_URL": self.falso.url if url is None else url,
            "POS_PWA_PEDIR_COPIA_TOKEN_FILE": str(self.archivo_token) if archivo is None else archivo,
        })

    def _pedir(self, token: str | None = None):
        h = {"Authorization": "Bearer " + (token or ModoCasaApiTests._token(self))}
        return self.client.post(self.RUTA, headers=h)

    def test_en_casa_pide_la_copia_firmada_y_dice_de_cuando_son_los_datos(self) -> None:
        import hashlib
        import hmac
        import time

        with _ConModo("casa"), self._entorno():
            r = self._pedir()
            r2 = self._pedir()
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json(), {"estado": "pidiendo", "datos_de": "2026-11-20T17:31"})
        self.assertEqual(r2.status_code, 200, r2.text)
        self.assertEqual(self.falso.rutas, ["/copia", "/copia"])
        # El token nunca viaja (HTTP plano en la LAN): ni en Authorization ni en ningún lado
        for cab in self.falso.cabeceras:
            self.assertNotIn("Authorization", cab)
            self.assertNotIn("token-de-prueba", repr(cab))
        # Cada petición lleva una firma HMAC de un solo uso, con la hora de ahora
        nonces = set()
        for valor in self.falso.tokens:
            segundos, nonce, dada = valor.split(".")
            self.assertLess(abs(time.time() - int(segundos)), 10)
            esperada = hmac.new(b"token-de-prueba", f"POST /copia {segundos} {nonce}".encode(),
                                hashlib.sha256).hexdigest()
            self.assertEqual(dada, esperada)
            nonces.add(nonce)
        self.assertEqual(len(nonces), 2, "cada petición con su propio nonce")

    def test_la_firma_es_la_que_revisa_nucleo(self) -> None:
        """Mismo cálculo que firma() de host/bin/nucleo-pedir-copia (servidor-nucleo)."""
        import hashlib
        import hmac

        from pos_uniformes.services.pedir_copia_service import firma

        valor = firma("abc", "POST", "/copia", segundos=1763680000, nonce="n0nce1234")
        esperada = hmac.new(b"abc", b"POST /copia 1763680000 n0nce1234", hashlib.sha256).hexdigest()
        self.assertEqual(valor, "1763680000.n0nce1234." + esperada)

    def test_pasa_tal_cual_lo_que_contesta_el_disparador(self) -> None:
        for estado in ("en_curso", "reciente", "espera", "tienda_apagada", "sin_configurar",
                       "fuera_de_horario", "tope"):
            with self.subTest(estado=estado), _ConModo("casa"), self._entorno():
                self.falso.cuerpo = {"estado": estado}
                self.assertEqual(self._pedir().json()["estado"], estado)

    def test_sin_configurar_no_llama_a_nadie(self) -> None:
        vacio = Path(self._tmp.name) / "vacio.token"
        vacio.write_text("\n", encoding="utf-8")
        for url, archivo in (("", None), (None, ""), (None, str(vacio)),
                             (None, str(Path(self._tmp.name) / "no-existe"))):
            with self.subTest(url=url, archivo=archivo), _ConModo("casa"), \
                    self._entorno(url, archivo):
                r = self._pedir()
                self.assertEqual(r.status_code, 200)
                self.assertEqual(r.json(), {"estado": "sin_configurar", "datos_de": "2026-11-20T17:31"})
        self.assertEqual(self.falso.tokens, [])

    def test_si_el_disparador_tarda_no_se_queda_esperando(self) -> None:
        import time

        from pos_uniformes.services import pedir_copia_service

        self.falso.espera = 2.0
        with _ConModo("casa"), self._entorno(), \
                patch.object(pedir_copia_service, "LIMITE_S", 0.3):
            token = ModoCasaApiTests._token(self)
            inicio = time.monotonic()
            r = self._pedir(token)
            tardo = time.monotonic() - inicio
        self.assertEqual(r.json()["estado"], "sin_respuesta")
        self.assertLess(tardo, 1.5)

    def test_disparador_caido_o_con_error(self) -> None:
        with _ConModo("casa"), self._entorno(url="http://127.0.0.1:1/copia"):
            self.assertEqual(self._pedir().json()["estado"], "sin_respuesta")
        self.falso.codigo, self.falso.cuerpo = 403, {"estado": "no_permitido"}
        with _ConModo("casa"), self._entorno():
            self.assertEqual(self._pedir().json()["estado"], "error")
        self.falso.codigo, self.falso.cuerpo = 200, {"estado": "algo-raro"}
        with _ConModo("casa"), self._entorno():
            self.assertEqual(self._pedir().json()["estado"], "error")

    def test_sin_sesion_no_pide_nada(self) -> None:
        with _ConModo("casa"), self._entorno():
            r = self.client.post(self.RUTA)
            self.assertIn(r.status_code, (401, 403))
            r = self.client.post(self.RUTA, headers={"Authorization": "Bearer no-es-un-token"})
            self.assertIn(r.status_code, (401, 403))
        self.assertEqual(self.falso.tokens, [])

    def test_en_tienda_no_existe(self) -> None:
        with _ConModo("tienda"), self._entorno():
            r = self._pedir()
        self.assertEqual(r.status_code, 404)
        self.assertEqual(self.falso.tokens, [])

    def test_el_candado_sigue_cerrando_lo_demas(self) -> None:
        with _ConModo("casa"), self._entorno():
            h = {"Authorization": "Bearer " + ModoCasaApiTests._token(self)}
            for metodo, ruta in ModoCasaApiTests._ESCRITURAS + [
                ("post", self.RUTA + "/otra"), ("post", "/api/v1/movil/actualizarx"),
            ]:
                with self.subTest(metodo=metodo, ruta=ruta):
                    r = self.client.request(metodo.upper(), ruta, headers=h, json={})
                    self.assertEqual(r.status_code, 409)
            # otro método en la misma ruta no llega a nada que escriba
            self.assertEqual(self.client.put(self.RUTA, headers=h).status_code, 405)
        self.assertEqual(self.falso.tokens, [])


class LimiteLoginTests(unittest.TestCase):
    def setUp(self) -> None:
        self.ahora = 1000.0
        self.limite = LimiteLogin(reloj=lambda: self.ahora)

    def test_cinco_libres_y_luego_esperas_que_crecen_hasta_15_min(self) -> None:
        for _ in range(5):
            self.assertEqual(self.limite.intento(7), 0)
        self.assertEqual(self.limite.intento(7), 60)
        self.ahora += 60
        self.assertEqual(self.limite.intento(7), 0)  # el 6.º pasa…
        self.assertEqual(self.limite.intento(7), 120)  # …y la espera se duplica
        for _ in range(10):
            self.ahora += 10_000
            self.limite.intento(7)
        self.assertEqual(self.limite.intento(7), 15 * 60)
        self.assertEqual(self.limite.intento(8), 0)  # otra empleada, aparte

    def test_un_pin_bueno_lo_reinicia(self) -> None:
        for _ in range(4):
            self.limite.intento(7)
        self.limite.exito(7)
        for _ in range(5):
            self.assertEqual(self.limite.intento(7), 0)


class VersionBaseTests(unittest.TestCase):
    def test_compara_la_base_con_las_migraciones(self) -> None:
        todas, cabezas = frozenset({"a", "b", "c"}), frozenset({"c"})
        self.assertEqual(version_base_service.comparar({"c"}, todas, cabezas), "igual")
        self.assertEqual(version_base_service.comparar({"d"}, todas, cabezas), "casa_mas_vieja")
        self.assertEqual(version_base_service.comparar({"b"}, todas, cabezas), "casa_mas_nueva")
        self.assertEqual(version_base_service.comparar(set(), todas, cabezas), "desconocida")

    def test_el_codigo_tiene_una_sola_cabeza(self) -> None:
        todas, cabezas = version_base_service.revisiones_del_codigo()
        self.assertGreater(len(todas), 10)
        self.assertEqual(len(cabezas), 1, cabezas)

    def test_lee_archivos_de_migracion(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            Path(d, "1.py").write_text('revision = "uno"\ndown_revision = None\n', encoding="utf-8")
            Path(d, "2.py").write_text(
                'revision: str = "dos"\ndown_revision: Union[str, None] = "uno"\n', encoding="utf-8")
            todas, cabezas = version_base_service.revisiones_del_codigo.__wrapped__(Path(d))
        self.assertEqual((todas, cabezas), (frozenset({"uno", "dos"}), frozenset({"dos"})))

    def test_health_en_casa_trae_version_base(self) -> None:
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                               poolclass=StaticPool)
        sesion = sessionmaker(bind=engine)()
        app.dependency_overrides[get_db] = lambda: sesion
        try:
            cliente = TestClient(app)
            with _ConModo("casa"), patch.object(
                version_base_service, "estado_version", return_value="casa_mas_vieja",
            ):
                data = cliente.get("/health").json()
            self.assertEqual(data["database"], "conectada")
            self.assertEqual(data["version_base"], "casa_mas_vieja")
            with _ConModo("tienda"):
                self.assertNotIn("version_base", cliente.get("/health").json())
            with _ConModo(None):
                self.assertNotIn("version_base", cliente.get("/health").json())
        finally:
            app.dependency_overrides.clear()
            sesion.close()

    def test_en_sqlite_es_desconocida(self) -> None:
        engine = create_engine("sqlite://")
        with sessionmaker(bind=engine)() as s:
            self.assertEqual(version_base_service.estado_version(s), "desconocida")


# ─── Frescura de la copia ─────────────────────────────────────────────────


class FrescuraCopiaTests(unittest.TestCase):
    def test_lee_la_hora_de_la_tienda_del_comment(self) -> None:
        nota = ("copia pos_uniformes_20261120_141503.dump (de la tienda a las "
                "2026-11-20 14:15), cargada 2026-11-20 14:17")
        self.assertEqual(hora_de_la_nota(nota), datetime(2026, 11, 20, 14, 15))

    def test_sin_la_frase_usa_el_nombre_del_dump(self) -> None:
        self.assertEqual(hora_de_la_nota("copia pos_uniformes_20261119_183000.dump"),
                         datetime(2026, 11, 19, 18, 30))

    def test_nota_vacia_o_rara_es_none(self) -> None:
        for nota in (None, "", "otra cosa", "de la tienda a las 2026-13-45 99:99"):
            with self.subTest(nota=nota):
                self.assertIsNone(hora_de_la_nota(nota))

    def test_en_sqlite_no_hay_nota(self) -> None:
        engine = create_engine("sqlite://")
        with sessionmaker(bind=engine)() as s:
            self.assertIsNone(datos_de(s))


if __name__ == "__main__":
    unittest.main()


# ─── La PWA trayendo lo más nuevo (JS de pwa/index.html, con node) ───────

_ARNES_JS = r"""
const fuente = require("fs").readFileSync(process.argv[process.argv.length - 1], "utf8");
const trozo = (desde, hasta) => { const i = fuente.indexOf(desde), j = fuente.indexOf(hasta, i);
  if (i < 0 || j < 0) throw new Error("no está: " + desde); return fuente.slice(i, j); };
const traer = trozo("const COPIA_CADA_MS", "let ocultaDesde")
  .replace("COPIA_CADA_MS = 8000, COPIA_MAX_MS = 150000", "COPIA_CADA_MS = 5, COPIA_MAX_MS = 200");
const nav = trozo("let navOtraVez = false;", "function navMenu()");
const escenarios = {};
let respuestas, pintadas, navs, token, modoServidor, datosDeActual, avisoDatos, navPila, navRefrescando,
    clases, cargas, trayendoVisto;
function reiniciar(lista, enPantalla) {
  respuestas = lista.slice(); pintadas = []; navs = 0; token = "t"; modoServidor = "casa";
  datosDeActual = enPantalla; avisoDatos = ""; navPila = [{nombre: "calendario", args: []}];
  navRefrescando = false; cargas = 0; trayendoVisto = false;
}
const $ = () => ({classList: {add() {}, remove() {}}});
function navPintar() {}
function pintarFrescura() { pintadas.push([avisoDatos, datosDeActual]); if (avisoDatos === "trayendo") trayendoVisto = true; }
async function fetch(url) {
  const r = respuestas.length ? respuestas.shift() : "falla";
  if (r === "falla") throw new Error("red");
  if (typeof r === "function") return r();
  return {ok: true, json: async () => r};
}
window = {calendario: async () => { navs++; await new Promise(ok => setTimeout(ok, 3)); }};
async function cargarInicio() { cargas++; }
let navRestaurando = false;
eval(traer + nav);
const fin = async () => { await traerLoMasNuevo(); await new Promise(ok => setTimeout(ok, 30)); };
const salida = {};
(async () => {
  // reciente con una copia más nueva que la de pantalla, en una pantalla que no es inicio
  reiniciar([{estado: "reciente", datos_de: "2026-11-20T17:45"}], "2026-11-20T17:31");
  await fin(); salida.reciente = {hora: datosDeActual, aviso: avisoDatos, navs};
  // en_curso con datos_de ya nuevo y la copia que se esperaba falla: se queda la nueva
  reiniciar([{estado: "en_curso", datos_de: "2026-11-20T17:45"}, {estado: "en_curso", datos_de: "2026-11-20T17:45"},
             {estado: "espera", datos_de: "2026-11-20T17:45"}], "2026-11-20T17:31");
  await fin(); salida.en_curso_nueva = {hora: datosDeActual, aviso: avisoDatos, navs, quedan: respuestas.length};
  // pidiendo y luego resulta que la tienda está apagada: deja de esperar y lo dice
  reiniciar([{estado: "pidiendo", datos_de: "2026-11-20T17:31"}, {estado: "tienda_apagada", datos_de: "2026-11-20T17:31"},
             {estado: "pidiendo", datos_de: "x"}], "2026-11-20T17:31");
  await fin(); salida.apagada = {hora: datosDeActual, aviso: avisoDatos, trayendo: trayendoVisto, quedan: respuestas.length};
  // pidiendo, en_curso, y llega la nueva: repinta y para
  reiniciar([{estado: "pidiendo", datos_de: "2026-11-20T17:31"}, {estado: "en_curso", datos_de: "2026-11-20T17:31"},
             {estado: "reciente", datos_de: "2026-11-20T17:48"}, {estado: "pidiendo", datos_de: "y"}], "2026-11-20T17:31");
  await fin(); salida.llega = {hora: datosDeActual, aviso: avisoDatos, navs, quedan: respuestas.length};
  // fuera de horario: «cerrada»
  reiniciar([{estado: "fuera_de_horario", datos_de: "2026-11-20T17:31"}], "2026-11-20T17:31");
  await fin(); salida.fuera = {aviso: avisoDatos, navs};
  // el teléfono se durmió a media espera: el fetch se queda colgado y falla al despertar, ya
  // pasado el plazo. Una falla no basta para rendirse: se vuelve a preguntar.
  const colgado = () => new Promise((_, mal) => setTimeout(() => mal(new Error("dormido")), 260));
  reiniciar([{estado: "pidiendo", datos_de: "2026-11-20T17:31"}, colgado,
             {estado: "reciente", datos_de: "2026-11-20T17:50"}], "2026-11-20T17:31");
  await fin(); salida.dormido = {hora: datosDeActual, aviso: avisoDatos};
  // …y si también falla la siguiente pero volvió a la app (visibilitychange a media espera), al
  // acabar se pide otra vez desde cero
  reiniciar([{estado: "pidiendo", datos_de: "2026-11-20T17:31"}, colgado, "falla",
             {estado: "reciente", datos_de: "2026-11-20T17:52"}], "2026-11-20T17:31");
  const p = traerLoMasNuevo();
  await new Promise(ok => setTimeout(ok, 100));
  traerLoMasNuevo();                                        // volvió a la app
  await p; await new Promise(ok => setTimeout(ok, 50));
  salida.dormido_volvio = {hora: datosDeActual, aviso: avisoDatos, quedan: respuestas.length};
  // error de entrada: no rompe ni toca nada
  reiniciar(["falla"], "2026-11-20T17:31");
  await fin(); salida.error = {hora: datosDeActual, aviso: avisoDatos, navs};
  reiniciar([() => ({ok: false})], "2026-11-20T17:31");
  await fin(); salida.http_error = {hora: datosDeActual, navs};
  // en la tienda no hace nada
  reiniciar([{estado: "pidiendo", datos_de: "z"}], "2026-11-20T17:31"); modoServidor = "tienda";
  await fin(); salida.tienda = {quedan: respuestas.length};
  // navActualizar a media corrida: se repite al acabar (no se pierde la copia nueva)
  reiniciar([], "a"); const n1 = navActualizar(); await navActualizar(); await n1;
  await new Promise(ok => setTimeout(ok, 20)); salida.nav_doble = navs;
  console.log(JSON.stringify(salida));
})().catch(e => { console.error(e); process.exit(1); });
"""


@unittest.skipUnless(__import__("shutil").which("node"), "sin node")
class TraerLoMasNuevoJsTests(unittest.TestCase):
    """traerLoMasNuevo() de la PWA con fetch falso: la hora de arriba siempre
    sigue a la copia de la base, aunque no se esté en inicio."""

    @classmethod
    def setUpClass(cls) -> None:
        import json
        import subprocess

        html = Path(__file__).resolve().parent.parent / "pwa" / "index.html"
        r = subprocess.run(["node", "-e", _ARNES_JS, "--", str(html)],
                           capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            raise AssertionError(r.stderr)
        cls.s = json.loads(r.stdout)

    def test_reciente_con_copia_nueva_cambia_la_hora_fuera_de_inicio(self) -> None:
        self.assertEqual(self.s["reciente"], {"hora": "2026-11-20T17:45", "aviso": "", "navs": 1})

    def test_en_curso_con_copia_mas_nueva_repinta_ya_y_no_regresa_a_la_vieja(self) -> None:
        self.assertEqual(self.s["en_curso_nueva"]["hora"], "2026-11-20T17:45")
        self.assertEqual(self.s["en_curso_nueva"]["aviso"], "")
        self.assertEqual(self.s["en_curso_nueva"]["navs"], 1)
        self.assertEqual(self.s["en_curso_nueva"]["quedan"], 0, "para al llegar «espera»")

    def test_tienda_apagada_a_media_espera_deja_de_girar_y_lo_dice(self) -> None:
        self.assertEqual(self.s["apagada"], {"hora": "2026-11-20T17:31", "aviso": "cerrada",
                                             "trayendo": True, "quedan": 1})

    def test_llega_la_nueva_repinta_y_para(self) -> None:
        self.assertEqual(self.s["llega"], {"hora": "2026-11-20T17:48", "aviso": "", "navs": 1, "quedan": 1})

    def test_fuera_de_horario_dice_cerrada(self) -> None:
        self.assertEqual(self.s["fuera"], {"aviso": "cerrada", "navs": 0})

    def test_si_se_durmio_no_se_rinde_con_una_falla(self) -> None:
        self.assertEqual(self.s["dormido"], {"hora": "2026-11-20T17:50", "aviso": ""})

    def test_si_volvio_a_la_app_a_media_espera_se_pide_otra_vez(self) -> None:
        self.assertEqual(self.s["dormido_volvio"], {"hora": "2026-11-20T17:52", "aviso": "", "quedan": 0})

    def test_errores_se_queda_lo_que_hay(self) -> None:
        self.assertEqual(self.s["error"], {"hora": "2026-11-20T17:31", "aviso": "", "navs": 0})
        self.assertEqual(self.s["http_error"], {"hora": "2026-11-20T17:31", "navs": 0})

    def test_en_tienda_no_pide_nada(self) -> None:
        self.assertEqual(self.s["tienda"], {"quedan": 1})

    def test_navactualizar_a_media_corrida_se_repite(self) -> None:
        self.assertEqual(self.s["nav_doble"], 2)
