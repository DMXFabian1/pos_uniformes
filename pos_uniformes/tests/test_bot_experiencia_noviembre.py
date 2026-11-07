"""Auditoría del bot 2026-11-07, sección 5 (experiencia en el celular)."""

from __future__ import annotations

import json
import unittest
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import CajaEntrada, CajaRetiro, LibretaCorte
from pos_uniformes.services import telegram_bot_service as bot
from pos_uniformes.services import telegram_cortes_service as ct
from pos_uniformes.services import telegram_pagos_service as pg


def _nunca_abre():
    raise AssertionError("no debía abrir la base")


class ErroresLegiblesTests(unittest.TestCase):
    def test_la_base_caida_se_dice_en_palabras(self):
        exc = Exception("(psycopg.OperationalError) connection to server at 192.168.0.10 failed")
        r = bot.error_legible(exc)
        self.assertTrue(r.startswith("Falló"))
        self.assertIn("base de datos de la tienda", r)
        self.assertNotIn("psycopg", r)
        self.assertNotIn("192.168", r)

    def test_los_nuestros_pasan_tal_cual(self):
        self.assertEqual(bot.error_legible(ValueError("Ese retiro ya se registró.")), "Falló: Ese retiro ya se registró.")

    def test_lo_demas_no_enseña_tripas(self):
        r = bot.error_legible(KeyError("x"))
        self.assertIn("KeyError", r)
        r = bot.error_legible(AttributeError("'NoneType' object has no attribute 'fecha'"))
        self.assertNotIn("NoneType", r)
        self.assertIn("registro", r)


class ComandoDesconocidoTests(unittest.TestCase):
    def test_sugiere_el_parecido_y_no_manda_la_ayuda(self):
        r = bot.atender_texto("/cortte", session_factory=_nunca_abre)
        self.assertIn("No conozco /cortte", r)
        self.assertIn("/corte", r)
        self.assertLess(len(r), 300)

    def test_sin_parecido_solo_dice_donde_ver(self):
        r = bot.atender_texto("/zzzzzz", session_factory=_nunca_abre)
        self.assertNotIn("Quisiste", r)
        self.assertIn("/ayuda", r)


class ArgumentosQueSeIgnorabanTests(unittest.TestCase):
    def test_nocorte_manana_no_cancela_hoy(self):
        with patch("pos_uniformes.services.corte_propuesta_service.cancelar") as cancelar:
            r = bot.atender_texto("/nocorte mañana", session_factory=_nunca_abre)
        cancelar.assert_not_called()
        self.assertIn("No cancelé nada", r)

    def test_nocorte_solo_si_cancela(self):
        with patch("pos_uniformes.services.corte_propuesta_service.cancelar", return_value=True) as cancelar:
            bot.atender_texto("/nocorte", session_factory=_nunca_abre)
        cancelar.assert_called_once()

    def test_resumen_ayer_da_el_de_ayer(self):
        sesion = MagicMock()
        sesion.__enter__.return_value = sesion
        with patch("pos_uniformes.services.resumen_diario_service.recolectar") as rec, \
                patch("pos_uniformes.services.resumen_diario_service.formatear", return_value="ok"):
            bot.atender_texto("/resumen ayer", session_factory=lambda: sesion, hoy=date(2026, 11, 7))
        self.assertEqual(rec.call_args.args[1], date(2026, 11, 6))

    def test_resumen_con_basura_lo_dice(self):
        r = bot.atender_texto("/resumen mañanita", session_factory=_nunca_abre, hoy=date(2026, 11, 7))
        self.assertIn("No entendí", r)

    def test_dias(self):
        hoy = date(2026, 11, 7)
        self.assertEqual(bot.dia_de_argumento("", hoy), hoy)
        self.assertEqual(bot.dia_de_argumento("antier", hoy), date(2026, 11, 5))
        self.assertEqual(bot.dia_de_argumento("5/11", hoy), date(2026, 11, 5))
        self.assertEqual(bot.dia_de_argumento("20/12", hoy), date(2025, 12, 20))   # no el futuro
        self.assertEqual(bot.dia_de_argumento("1/2/26", hoy), date(2026, 2, 1))
        with self.assertRaises(ValueError):
            bot.dia_de_argumento("31/02", hoy)


class AyudaYAutocompletarTests(unittest.TestCase):
    def test_la_ayuda_trae_lo_que_faltaba(self):
        for pedazo in ("/faltas 30", "/actualizar noche", "/corte fondo", "/corte otros",
                       "/corte contarjeta", "/corte segundo", "/deshacer", "/resumen ayer"):
            self.assertIn(pedazo, bot.AYUDA)

    def test_los_comandos_del_menu_existen_y_telegram_los_acepta(self):
        import inspect

        # Sin correrlos (/corte haría un corte): que el despachador los atienda.
        fuente = inspect.getsource(bot.atender_texto)
        for nombre, descripcion in bot.COMANDOS_MENU:
            self.assertRegex(nombre, r"^[a-z0-9_]{1,32}$")
            self.assertTrue(0 < len(descripcion) <= 256)
            self.assertIn(f'"{nombre}"', fuente, nombre)

    def test_se_registran_al_arrancar(self):
        llamadas = []

        def _llamar(token, metodo, datos=None, timeout=15.0):
            llamadas.append((metodo, datos))
            return {"result": []}

        with patch("pos_uniformes.services.telegram_service._llamar", side_effect=_llamar), \
                patch.object(bot, "asegurar_menu_fijado"), patch.object(bot, "limpiar_si_toca"), \
                patch.object(bot, "refrescar_menu_si_toca"):
            bot.escuchar(session_factory=MagicMock(), token="t", chat_id="1", una_vez=True, alertas=False)
        registro = [d for m, d in llamadas if m == "setMyCommands"]
        self.assertEqual(len(registro), 1)
        self.assertEqual(json.loads(registro[0]["commands"])[0]["command"], "menu")


class DeshacerRetiroOEntradaTests(unittest.TestCase):
    HOY = date(2026, 11, 7)

    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.s = Session(engine)
        self.addCleanup(self.s.close)

    def _retiro(self, monto, motivo, hora=12, dia=7):
        r = CajaRetiro(monto=Decimal(monto), motivo=motivo, creado_por="VEND-1",
                       created_at=datetime(2026, 11, dia, hora, 0))
        self.s.add(r)
        self.s.commit()
        return r

    def test_sin_clave_enseña_los_de_hoy_tocables(self):
        r = self._retiro("500", "gasolina")
        self._retiro("300", "de ayer", dia=6)
        e = CajaEntrada(monto=Decimal("1750"), motivo="Fondo de papá", creado_por="VEND-1",
                        created_at=datetime(2026, 11, 7, 13, 0))
        self.s.add(e)
        self.s.commit()
        texto = pg.deshacer(self.s, "", quien="VEND-1", hoy=self.HOY)
        self.assertIn(f"/deshacer_r{r.id}", texto)
        self.assertIn(f"/deshacer_e{e.id}", texto)
        self.assertNotIn("de ayer", texto)
        self.assertLess(texto.index("Entrada de"), texto.index("Retiro de"))   # el más nuevo arriba
        self.assertEqual(self.s.query(CajaRetiro).count(), 2)            # no borró nada

    def test_con_clave_lo_deshace(self):
        r = self._retiro("500", "gasolina")
        texto = pg.deshacer(self.s, f"r{r.id}", quien="VEND-1", hoy=self.HOY)
        self.assertIn("Deshice el retiro de $500.00", texto)
        self.assertEqual(self.s.query(CajaRetiro).count(), 0)

    def test_el_comando_tocable_llega_a_lo_mismo(self):
        cmd = bot.parsear("/deshacer_r12")
        self.assertEqual((cmd.nombre, cmd.argumento), ("deshacer", "r12"))
        self.assertEqual(bot.parsear("/deshacer_pago").nombre, "deshacer_pago")

    def test_el_de_un_prestamo_no(self):
        r = self._retiro("800", "Préstamo a Fanny")
        texto = pg.deshacer(self.s, f"r{r.id}", quien="VEND-1", hoy=self.HOY)
        self.assertIn("es el préstamo", texto)
        self.assertEqual(self.s.query(CajaRetiro).count(), 1)

    def test_si_ya_hubo_corte_no(self):
        r = self._retiro("500", "gasolina", hora=12)
        self.s.add(LibretaCorte(fecha=self.HOY, monto_final=Decimal("1"), created_at=datetime(2026, 11, 7, 17, 0)))
        self.s.commit()
        texto = pg.deshacer(self.s, f"r{r.id}", quien="VEND-1", hoy=self.HOY)
        self.assertIn("ya entró en el corte", texto)
        self.assertEqual(self.s.query(CajaRetiro).count(), 1)

    def test_el_de_otro_dia_no(self):
        r = self._retiro("500", "gasolina", dia=6)
        texto = pg.deshacer(self.s, f"r{r.id}", quien="VEND-1", hoy=self.HOY)
        self.assertIn("No encuentro", texto)
        self.assertEqual(self.s.query(CajaRetiro).count(), 1)


class AjustarConConfirmacionTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.s = Session(engine)
        self.addCleanup(self.s.close)
        self.corte = LibretaCorte(
            fecha=date(2026, 9, 20), periodo_label="x",
            monto_final=Decimal("22548"), monto_esperado=Decimal("22548"),
            reactivo_inicial=Decimal("11160"), reactivo_final=Decimal("11160"),
            retiros_pagos=Decimal("0"), otros_retiros=Decimal("0"),
            operaciones=32, creado_por="VEND-1",
            desde=datetime(2026, 9, 19, 17, 58), hasta=datetime(2026, 9, 20, 16, 34),
        )
        self.s.add(self.corte)
        self.s.commit()

    def test_sin_si_solo_pregunta(self):
        r = ct.ajustar(self.s, f"{self.corte.id} 10000 depósito al banco", quien="VEND-1")
        self.assertIn("¿Cambio el corte", r)
        self.assertIn("de $11,388.00 a $10,000.00", r)
        self.assertIn(f"/ajustar {self.corte.id} 10000 depósito al banco si", r)
        self.s.expire_all()
        self.assertEqual(self.s.get(LibretaCorte, self.corte.id).monto_final, Decimal("22548"))

    def test_con_si_lo_cambia_y_el_si_no_entra_a_la_nota(self):
        r = ct.ajustar(self.s, f"{self.corte.id} 10000 depósito al banco si", quien="VEND-1")
        self.assertIn("ahora dice $10,000.00", r)
        self.s.expire_all()
        corte = self.s.get(LibretaCorte, self.corte.id)
        self.assertNotEqual(corte.monto_final, Decimal("22548"))
        self.assertNotIn(" si", corte.nota or "")

    def test_los_errores_salen_desde_la_pregunta(self):
        r = ct.ajustar(self.s, f"{self.corte.id} 10000", quien="VEND-1")
        self.assertNotIn("¿Cambio", r)   # falta el por qué: lo dice ya


if __name__ == "__main__":
    unittest.main()
