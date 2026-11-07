"""Base caída, 409 y supervisor en bucle: se dicen por el chat, no solo en el
log (auditoría 2026-11-07, #28)."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta

from pos_uniformes.scripts import supervisor as sup
from pos_uniformes.services import alertas_service as al
from pos_uniformes.services import telegram_bot_service as bot


class BaseCaidaTests(unittest.TestCase):
    def setUp(self) -> None:
        al._base_falla_desde = None
        al._base_falla_avisada = False
        self.addCleanup(setattr, al, "_base_falla_desde", None)
        self.addCleanup(setattr, al, "_base_falla_avisada", False)

    def test_a_los_diez_minutos_se_dice_una_vez_y_luego_que_volvio(self) -> None:
        mandados = []
        t0 = datetime(2026, 11, 7, 12, 0)
        exc = OSError("connection to server at 192.168.0.10 failed\nmás detalle")
        al._vuelta_sin_base(exc, mandados.append, t0)
        al._vuelta_sin_base(exc, mandados.append, t0 + timedelta(minutes=5))
        self.assertEqual(mandados, [])                       # un parpadeo no
        al._vuelta_sin_base(exc, mandados.append, t0 + timedelta(minutes=10))
        al._vuelta_sin_base(exc, mandados.append, t0 + timedelta(minutes=20))
        self.assertEqual(len(mandados), 1)
        self.assertIn("Desde las 12:00 no puedo leer la base: connection to server at 192.168.0.10 failed", mandados[0])
        al._vuelta_con_base(mandados.append, t0 + timedelta(minutes=25))
        self.assertIn("✅ La base volvió (12:25)", mandados[1])
        al._vuelta_con_base(mandados.append, t0 + timedelta(minutes=26))
        self.assertEqual(len(mandados), 2)

    def test_un_parpadeo_no_dice_que_volvio(self) -> None:
        mandados = []
        al._vuelta_sin_base(OSError("x"), mandados.append, datetime(2026, 11, 7, 12, 0))
        al._vuelta_con_base(mandados.append, datetime(2026, 11, 7, 12, 1))
        self.assertEqual(mandados, [])

    def test_sin_internet_se_reintenta(self) -> None:
        def sin_red(_):
            raise OSError("sin red")

        t0 = datetime(2026, 11, 7, 12, 0)
        al._vuelta_sin_base(OSError("x"), sin_red, t0)
        al._vuelta_sin_base(OSError("x"), sin_red, t0 + timedelta(minutes=11))
        mandados = []
        al._vuelta_sin_base(OSError("x"), mandados.append, t0 + timedelta(minutes=12))
        self.assertEqual(len(mandados), 1)

    def test_procesar_lo_usa(self) -> None:
        def factory():
            raise OSError("no route to host")

        al._base_falla_desde = datetime.now() - timedelta(minutes=30)
        mandados = []
        al.procesar(factory, mandados.append)
        self.assertIn("no route to host", mandados[0])


class OtroBotConMiTokenTests(unittest.TestCase):
    def test_se_avisa_si_dura_y_una_vez(self) -> None:
        c = bot._Conflicto()
        self.assertEqual(c.otro(0), "")
        self.assertEqual(c.otro(60), "")
        self.assertIn("otro bot usando mi token", c.otro(130))
        self.assertEqual(c.otro(200), "")
        c.listo()
        self.assertEqual(c.otro(300), "")      # episodio nuevo, vuelve a esperar


class SupervisorEnBucleTests(unittest.TestCase):
    def test_tres_levantadas_en_media_hora_se_avisan(self) -> None:
        s = sup.Servicio("Telegram bot", vivo=lambda: False, levantar=lambda: None, reiniciar=lambda: None)
        avisos = []
        for minuto in (0, 4, 8, 12, 16):
            sup.vuelta([s], ahora=minuto * 60.0, avisar=avisos.append)
        self.assertEqual(len(avisos), 1)
        self.assertIn("Telegram bot: lo he tenido que levantar 3 veces", avisos[0])

    def test_levantadas_espaciadas_no(self) -> None:
        s = sup.Servicio("PWA", vivo=lambda: False, levantar=lambda: None, reiniciar=lambda: None)
        avisos = []
        for hora in range(5):
            sup.vuelta([s], ahora=hora * 3600.0, avisar=avisos.append)
        self.assertEqual(avisos, [])


if __name__ == "__main__":
    unittest.main()
