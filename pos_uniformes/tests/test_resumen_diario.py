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
        with patch("urllib.request.urlopen", side_effect=fake_urlopen), redirect_stdout(io.StringIO()) as out:
            payload = tg._llamar("t", "getUpdates")
        self.assertTrue(payload["ok"])
        self.assertEqual(llamadas[-1], ssl.CERT_NONE)
        self.assertIn("continuando sin verificar", out.getvalue())

    def test_otro_error_de_red_no_se_traga(self) -> None:
        import urllib.error
        from unittest.mock import patch

        from pos_uniformes.services import telegram_service as tg

        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("sin red")):
            with self.assertRaises(urllib.error.URLError):
                tg._llamar("t", "getUpdates")
