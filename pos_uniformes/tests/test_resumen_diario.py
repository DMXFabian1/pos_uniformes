"""Resumen diario por Telegram: formato del texto y partición de mensajes."""

from __future__ import annotations

import unittest
from datetime import date
from decimal import Decimal

from pos_uniformes.services.resumen_diario_service import CorteResumen, DatosResumen, PagoResumen, formatear
from pos_uniformes.services.telegram_service import partir_mensaje


class FormatearTests(unittest.TestCase):
    def test_dia_completo(self) -> None:
        d = DatosResumen(
            fecha=date(2026, 9, 8),
            operaciones=14, piezas=31,
            ventas=Decimal("9800.00"), abonos=Decimal("1200.00"), apartados=Decimal("2500.00"),
            efectivo=Decimal("8400.00"), tarjeta=Decimal("2600.00"),
            por_empleada=[("Ana", 9, 40), ("Bety", 5, 12)],
            cortes=[CorteResumen("20:15", "ENC-1", Decimal("19540.00"), Decimal("19560.00"), Decimal("11160.00"), Decimal("1390.00"), Decimal("0"))],
            pagos=[PagoResumen("Ana", Decimal("1390.00"), 45, 0), PagoResumen("Bety", Decimal("1103.33"), 10, 1)],
            faltaron=["Caro"],
            afluencia_entradas=120, afluencia_pasan=640, afluencia_ventas=14,
            descansan_manana=["Bety"],
            pagos_proximos=[("Caro", "viernes", Decimal("1306.00"))],
        )
        t = formatear(d)
        self.assertIn("RESUMEN DEL DÍA · martes 08/09/2026", t)
        self.assertIn("14 operaciones · 31 piezas", t)
        self.assertIn("Efectivo: $8,400.00 · Tarjeta: $2,600.00", t)
        self.assertIn("Ana 9 ops/40 com.", t)
        self.assertIn("20:15 por ENC-1: en caja $19,540.00 · FALTARON $20.00", t)
        self.assertIn("fondo que queda $11,160.00 · pagos $1,390.00", t)
        self.assertIn("Pagado a Bety: $1,103.33 (10 com., 1 falta(s) descontada(s))", t)
        self.assertIn("Faltaron hoy: Caro", t)
        self.assertIn("Entraron 120 personas · pasaron por fuera 640", t)
        self.assertIn("conversión 12%", t)
        self.assertIn("Descansa: Bety", t)
        self.assertIn("Caro viernes $1,306.00", t)

    def test_dia_sin_nada_y_sin_corte_viejo(self) -> None:
        d = DatosResumen(fecha=date(2026, 9, 8), horas_sin_corte=50.0)
        t = formatear(d)
        self.assertIn("Sin operaciones registradas hoy", t)
        self.assertIn("SIN CORTE HOY. El último fue hace 2.1 días", t)
        self.assertNotIn("AFLUENCIA", t)
        self.assertNotIn("EMPLEADAS", t)
        self.assertIn("Descansa: nadie", t)

    def test_corte_cuadrado_y_sobrante(self) -> None:
        exacto = CorteResumen("20:00", "ENC-1", Decimal("100"), Decimal("100"), Decimal("50"), Decimal("0"), Decimal("0"))
        sobra = CorteResumen("21:00", "ENC-1", Decimal("110"), Decimal("100"), Decimal("50"), Decimal("0"), Decimal("5"))
        dueno = CorteResumen("21:30", "VEND-1", Decimal("90"), Decimal("100"), Decimal("50"), Decimal("0"), Decimal("0"))
        t = formatear(DatosResumen(fecha=date(2026, 9, 8), cortes=[exacto, sobra, dueno]))
        self.assertIn("cuadró exacto ✅", t)
        self.assertIn("sobraron $10.00 ⚠️", t)
        self.assertIn("por VEND-1: en caja $90.00 · ajustado (real $100.00)", t)
        self.assertNotIn("FALTARON", t)
        normal = CorteResumen("21:40", "VEND-1", Decimal("100"), Decimal("100"), Decimal("50"), Decimal("0"), Decimal("0"))
        self.assertIn("por VEND-1: en caja $100.00 · cuadró exacto ✅", formatear(DatosResumen(fecha=date(2026, 9, 8), cortes=[normal])))
        self.assertIn("otros retiros $5.00", t)


class PartirMensajeTests(unittest.TestCase):
    def test_corto_no_se_parte(self) -> None:
        self.assertEqual(partir_mensaje("hola\nmundo"), ["hola\nmundo"])

    def test_largo_se_parte_por_lineas(self) -> None:
        texto = "\n".join(f"línea {i}" for i in range(100))
        partes = partir_mensaje(texto, maximo=120)
        self.assertGreater(len(partes), 1)
        self.assertTrue(all(len(p) <= 120 for p in partes))
        self.assertEqual("\n".join(partes), texto)


if __name__ == "__main__":
    unittest.main()


class TlsFallbackTests(unittest.TestCase):
    """El reintento sin verificar TLS, en el camino de urllib.

    Desde 2026-10-02 las llamadas van primero por una conexión reutilizada
    (urllib3); urllib quedó de respaldo. Estos dos prueban el respaldo, así que
    apagan el camino rápido a propósito — si no, harían red de verdad.
    """

    @staticmethod
    def _sin_pool():
        from unittest.mock import patch

        from pos_uniformes.services import telegram_service as tg

        return patch.object(tg, "_obtener_pool", side_effect=RuntimeError("sin pool"))

    def test_certificado_no_reconocido_reintenta_sin_verificar(self) -> None:
        import io
        import json
        import ssl
        import urllib.error
        from contextlib import redirect_stdout
        from unittest.mock import MagicMock, patch

        from pos_uniformes.services import telegram_service as tg

        llamadas = []

        def fake_urlopen(req, timeout=None, context=None):
            llamadas.append(context.verify_mode)
            if len(llamadas) == 1:
                raise urllib.error.URLError(ssl.SSLCertVerificationError("self-signed certificate in certificate chain"))
            resp = MagicMock()
            resp.__enter__ = lambda s: s
            resp.__exit__ = lambda s, *a: False
            resp.read.return_value = json.dumps({"ok": True, "result": []}).encode()
            return resp

        tg._aviso_inseguro = False
        with self._sin_pool(), patch("urllib.request.urlopen", side_effect=fake_urlopen), \
                redirect_stdout(io.StringIO()) as out:
            payload = tg._llamar("t", "getUpdates")
        self.assertTrue(payload["ok"])
        self.assertEqual(llamadas[-1], ssl.CERT_NONE)
        self.assertIn("continuando sin verificar", out.getvalue())

    def test_otro_error_de_red_no_se_traga(self) -> None:
        import urllib.error
        from unittest.mock import patch

        from pos_uniformes.services import telegram_service as tg

        with self._sin_pool(), patch(
            "urllib.request.urlopen", side_effect=urllib.error.URLError("sin red")
        ):
            with self.assertRaises(urllib.error.URLError):
                tg._llamar("t", "getUpdates")


class ConexionReutilizadaTests(unittest.TestCase):
    """Abrir una conexión nueva en cada llamada cuesta un saludo TLS entero.

    Medido desde la Mac: 571 ms por llamada contra 182 ms reutilizando (−68%).
    El bot hace una llamada por cada cosa que contesta, y en la red de la
    tienda —WiFi, con pérdida— la diferencia es mayor. De ahí que se guarde la
    conexión; y de ahí también la red de seguridad, porque este es el único
    camino por el que el bot habla.
    """

    def setUp(self) -> None:
        from pos_uniformes.services import telegram_service as tg

        self.tg = tg
        tg.soltar_pool()
        self.addCleanup(tg.soltar_pool)

    def _pool_falso(self, cuerpo='{"ok": true, "result": []}'):
        from unittest.mock import MagicMock

        pool = MagicMock()
        pool.request.return_value = MagicMock(data=cuerpo.encode())
        return pool

    def test_la_conexion_se_reutiliza_entre_llamadas(self) -> None:
        from unittest.mock import patch

        pool = self._pool_falso()
        with patch.object(self.tg, "_obtener_pool", return_value=pool) as obtener:
            self.tg._llamar("t", "getMe")
            self.tg._llamar("t", "getMe")
        self.assertEqual(pool.request.call_count, 2)
        self.assertEqual(obtener.call_count, 2)   # mismo pool, no uno nuevo

    def test_guarda_el_mismo_pool(self) -> None:
        from unittest.mock import patch

        with patch("urllib3.PoolManager", side_effect=lambda **k: object()) as crear:
            primero = self.tg._obtener_pool(True)
            segundo = self.tg._obtener_pool(True)
        self.assertIs(primero, segundo)
        self.assertEqual(crear.call_count, 1)

    def test_cambiar_de_modo_TLS_abre_otro(self) -> None:
        from unittest.mock import patch

        with patch("urllib3.PoolManager", side_effect=lambda **k: object()):
            verificando = self.tg._obtener_pool(True)
            sin_verificar = self.tg._obtener_pool(False)
        self.assertIsNot(verificando, sin_verificar)

    def test_si_el_pool_truena_se_contesta_por_el_camino_viejo(self) -> None:
        # La red de seguridad: romper esto sería dejar a Daniel sin bot.
        import json
        from unittest.mock import MagicMock, patch

        resp = MagicMock()
        resp.__enter__ = lambda s: s
        resp.__exit__ = lambda s, *a: False
        resp.read.return_value = json.dumps({"ok": True, "result": "por urllib"}).encode()
        with patch.object(self.tg, "_obtener_pool", side_effect=RuntimeError("pool roto")), \
                patch("urllib.request.urlopen", return_value=resp):
            payload = self.tg._llamar("t", "getMe")
        self.assertEqual(payload["result"], "por urllib")

    def test_un_error_de_certificado_NO_se_tapa_con_el_respaldo(self) -> None:
        # Tiene que llegar a `_llamar` para que reintente sin verificar; si el
        # respaldo se lo tragara, el antivirus de la tienda dejaría al bot mudo.
        import ssl
        from unittest.mock import patch

        with patch.object(
            self.tg, "_obtener_pool",
            side_effect=ssl.SSLCertVerificationError("self-signed certificate"),
        ):
            with self.assertRaises(ssl.SSLCertVerificationError):
                self.tg._pedir("https://x", None, 5, True)

    def test_reconoce_el_error_del_certificado_aunque_venga_envuelto(self) -> None:
        import ssl

        hondo = ssl.SSLCertVerificationError("self-signed certificate in certificate chain")
        envuelto = RuntimeError("falló la conexión")
        envuelto.__cause__ = hondo
        self.assertTrue(self.tg._es_de_certificado(envuelto))
        self.assertFalse(self.tg._es_de_certificado(RuntimeError("sin red")))

    def test_por_el_texto_tambien(self) -> None:
        # urllib3 a veces lo entrega como texto, sin la excepción adentro.
        self.assertTrue(
            self.tg._es_de_certificado(OSError("CERTIFICATE_VERIFY_FAILED] self signed"))
        )

    def test_reconoce_el_del_urlopen_que_lo_guarda_en_reason(self) -> None:
        # urlopen NO lo encadena: lo mete en `.reason`. Perderlo significa no
        # reintentar sin verificar, y eso es el bot mudo en la tienda.
        import ssl
        import urllib.error

        envuelto = urllib.error.URLError(ssl.SSLCertVerificationError("self-signed certificate"))
        self.assertTrue(self.tg._es_de_certificado(envuelto))

    def test_un_error_dentro_del_except_NO_hereda_la_causa(self) -> None:
        # `__context__` es «qué se estaba atendiendo», no «qué lo causó».
        # Siguiéndolo, un RuntimeError lanzado mientras se atendía el error de
        # certificado se daba por certificado también, y el reintento sin
        # verificar se quedaba dando vueltas.
        import ssl

        try:
            try:
                raise ssl.SSLCertVerificationError("self-signed certificate")
            except ssl.SSLCertVerificationError:
                raise RuntimeError("otra cosa")
        except RuntimeError as otro:
            self.assertIsNotNone(otro.__context__)
            self.assertFalse(self.tg._es_de_certificado(otro))
