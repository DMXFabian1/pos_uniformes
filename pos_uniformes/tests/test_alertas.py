"""Alertas por Telegram: cola en la base, textos, vigilante y enganches."""

from __future__ import annotations

import unittest
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from pos_uniformes.database.models import AlertaTelegram, CajaRetiro, LibretaCorte, LibretaVenta
from pos_uniformes.services import alertas_service as al


def _sqlite(*tablas):
    engine = create_engine("sqlite://")
    for t in tablas:
        t.__table__.create(engine)
    return sessionmaker(bind=engine)


class ColaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.factory = _sqlite(AlertaTelegram)

    def test_encolar_y_enviar(self) -> None:
        with self.factory() as s:
            self.assertTrue(al.encolar(s, "uno"))
            self.assertTrue(al.encolar(s, "dos"))
            self.assertFalse(al.encolar(s, "   "))
            salidas = []
            self.assertEqual(al.enviar_pendientes(s, salidas.append), 2)
            self.assertEqual(salidas, ["uno", "dos"])
            self.assertEqual(al.pendientes(s), [])
            self.assertEqual(al.enviar_pendientes(s, salidas.append), 0)

    def test_sin_red_se_queda_pendiente_y_cuenta_intentos(self) -> None:
        def falla(_t):
            raise OSError("sin red")

        with self.factory() as s:
            al.encolar(s, "uno")
            al.encolar(s, "dos")
            self.assertEqual(al.enviar_pendientes(s, falla), 0)
            pend = al.pendientes(s)
            self.assertEqual([p.texto for p in pend], ["uno", "dos"])
            self.assertEqual(pend[0].intentos, 1)
            self.assertEqual(pend[1].intentos, 0)  # se detuvo en la primera
            for _ in range(al.MAX_INTENTOS):
                al.enviar_pendientes(s, falla)
            self.assertEqual([p.texto for p in al.pendientes(s)], ["dos"])  # "uno" agotó intentos

    def test_encolar_sin_tabla_no_rompe(self) -> None:
        factory = _sqlite()  # sin alerta_telegram
        with factory() as s:
            self.assertFalse(al.encolar(s, "x"))


class TextosTests(unittest.TestCase):
    def _corte(self, **extra):
        base = dict(
            creado_por="ENC-1", hasta=datetime(2026, 9, 9, 17, 31), created_at=None, monto_final=Decimal("13000.00"),
            reactivo_final=Decimal("11160.00"), retiros_pagos=Decimal("1390.00"), otros_retiros=Decimal("0"),
            monto_esperado=Decimal("13000.00"), nota=None,
        )
        base.update(extra)
        return SimpleNamespace(**base)

    def test_corte_encargado(self) -> None:
        pago = SimpleNamespace(employee_name="Ana López", employee_code="VEND-2", total=Decimal("1390.00"))
        t = al.texto_alerta_corte(self._corte(), Decimal("3230.00"), pagos=[pago])
        self.assertIn("Corte hecho por ENC-1 a las 17:31", t)
        self.assertIn("Venta efectivo $3,230.00 · pagos $1,390.00", t)
        self.assertIn("💵 Ana: $1,390.00", t)
        self.assertIn("Se saca $1,840.00 · reactivo queda $11,160.00", t)
        self.assertNotIn("FALTARON", t)

    def test_corte_encargado_con_faltante(self) -> None:
        t = al.texto_alerta_corte(self._corte(creado_por="ENC-1", monto_final=Decimal("12900.00"), nota="cambio"), Decimal("3230.00"))
        self.assertIn("⚠️ FALTARON $100.00", t)
        self.assertIn("Nota: cambio", t)
        t2 = al.texto_alerta_corte(self._corte(creado_por="ENC-1", monto_final=Decimal("13010.00")), Decimal("0"))
        self.assertIn("Sobraron $10.00", t2)
        self.assertNotIn("⚠️", t2)

    def test_corte_del_dueno_muestra_ajuste_solo_a_daniel(self) -> None:
        # Su cifra es la oficial; en SU Telegram ve el real y el ajuste (no "faltaron").
        t = al.texto_alerta_corte(self._corte(creado_por="VEND-1", monto_final=Decimal("12900.00")), Decimal("3230.00"))
        self.assertNotIn("FALTARON", t)
        self.assertIn("Ajuste: calculado $13,000.00 → real $12,900.00 (−$100.00)", t)
        # Sin cambios: todo normal, ninguna línea extra.
        t2 = al.texto_alerta_corte(self._corte(creado_por="VEND-1"), Decimal("3230.00"))
        self.assertNotIn("Ajuste", t2)

    def test_retiro(self) -> None:
        r = SimpleNamespace(monto=Decimal("500"), motivo="Proveedor", creado_por="enc-1", created_at=datetime(2026, 9, 9, 12, 5))
        self.assertEqual(al.texto_alerta_retiro(r), "💸 Retiro del cajón: $500.00 — Proveedor (ENC-1, 12:05)")


def _venta(s, momento: datetime, monto="300", nombre="Ana López"):
    row = LibretaVenta(employee_code="VEND-2", employee_name=nombre, tipo="venta", piezas=1, monto_total=Decimal(monto), monto_neto=Decimal(monto), created_at=momento)
    s.add(row)
    s.commit()
    return row


def _corte_db(s, dia: date):
    s.add(LibretaCorte(fecha=dia, periodo_label="x", monto_final=Decimal("1"), creado_por="ENC-1", created_at=datetime.now().astimezone()))
    s.commit()


class VigilanteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.factory = _sqlite(LibretaVenta, LibretaCorte)
        self.lunes = date(2026, 9, 7)

    def test_primera_vuelta_no_reclama_lo_viejo(self) -> None:
        v = al.Vigilante()
        with self.factory() as s:
            _venta(s, datetime(2026, 9, 6, 22, 0))  # viejo, fuera de horario
            self.assertEqual(v.revisar(s, datetime(2026, 9, 7, 10, 0)), [])
            self.assertEqual(v.ultimo_id, 1)

    def test_movimiento_fuera_de_horario(self) -> None:
        v = al.Vigilante()
        with self.factory() as s:
            v.revisar(s, datetime(2026, 9, 7, 10, 0))
            _venta(s, datetime(2026, 9, 7, 12, 0))          # en horario
            _venta(s, datetime(2026, 9, 7, 18, 40), "450")  # lunes cierra 18:00
            textos = v.revisar(s, datetime(2026, 9, 7, 18, 41))
            fuera = [t for t in textos if "fuera de horario" in t]
            self.assertEqual(len(fuera), 1)
            self.assertIn("venta $450.00 por Ana a las 18:40 (horario 09:00–18:00)", fuera[0])
            self.assertTrue(any("no se ha hecho corte" in t for t in textos))  # también avisa el cierre sin corte
            self.assertEqual(v.revisar(s, datetime(2026, 9, 7, 18, 42)), [])  # no repite
            _venta(s, datetime(2026, 9, 10, 17, 30), "80")  # jueves cierra 17:00
            self.assertIn("17:00)", v.revisar(s, datetime(2026, 9, 10, 17, 31))[0])

    def test_cierre_sin_corte_una_vez_al_dia(self) -> None:
        v = al.Vigilante()
        with self.factory() as s:
            v.revisar(s, datetime(2026, 9, 7, 10, 0))
            _venta(s, datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc) + timedelta(hours=0))
            self.assertEqual(v.revisar(s, datetime(2026, 9, 7, 18, 5)), [])   # todavía no (cierre + 10 min)
            textos = v.revisar(s, datetime(2026, 9, 7, 18, 12))
            self.assertEqual(len(textos), 1)
            self.assertIn("Ya cerró la tienda (18:00) y hoy no se ha hecho corte", textos[0])
            self.assertEqual(v.revisar(s, datetime(2026, 9, 7, 19, 0)), [])   # ya avisó hoy

    def test_con_corte_o_sin_movimiento_no_avisa(self) -> None:
        with self.factory() as s:
            v = al.Vigilante()
            v.revisar(s, datetime(2026, 9, 7, 10, 0))
            self.assertEqual(v.revisar(s, datetime(2026, 9, 7, 18, 30)), [])  # sin movimientos hoy
            v2 = al.Vigilante()
            v2.revisar(s, datetime(2026, 9, 8, 10, 0))
            _venta(s, datetime.now().astimezone())
            _corte_db(s, date.today())
            self.assertEqual(v2.revisar(s, datetime.combine(date.today(), datetime.min.time()).replace(hour=23)), [])


class ProcesarTests(unittest.TestCase):
    def test_manda_cola_y_vigilante(self) -> None:
        factory = _sqlite(AlertaTelegram, LibretaVenta, LibretaCorte)
        with factory() as s:
            al.encolar(s, "pendiente")
        salidas = []
        v = al.Vigilante(ultimo_id=0)
        with factory() as s:
            _venta(s, datetime(2026, 9, 7, 20, 0))
        with patch.object(al, "datetime", wraps=datetime) as dt:
            dt.now.return_value = datetime(2026, 9, 7, 20, 1).astimezone()
            n = al.procesar(factory, salidas.append, v)
        self.assertEqual(n, 3)
        self.assertEqual(salidas[0], "pendiente")
        self.assertIn("fuera de horario", salidas[1])
        self.assertIn("no se ha hecho corte", salidas[2])

    def test_nunca_truena(self) -> None:
        def factory():
            raise RuntimeError("sin base")

        self.assertEqual(al.procesar(factory, lambda t: None, al.Vigilante()), 0)


class EnganchesTests(unittest.TestCase):
    def test_retiro_encola_alerta(self) -> None:
        from pos_uniformes.services.retiros_service import registrar_retiro

        factory = _sqlite(CajaRetiro, AlertaTelegram)
        with factory() as s:
            registrar_retiro(s, monto="500", motivo="Renta", creado_por="ENC-1")
            pend = al.pendientes(s)
            self.assertEqual(len(pend), 1)
            self.assertIn("$500.00 — Renta (ENC-1", pend[0].texto)

    def test_retiro_sin_tabla_de_alertas_sigue_funcionando(self) -> None:
        from pos_uniformes.services.retiros_service import registrar_retiro

        factory = _sqlite(CajaRetiro)
        with factory() as s:
            r = registrar_retiro(s, monto="20", motivo="Cambio", creado_por="VEND-1")
            self.assertEqual(r.monto, Decimal("20.00"))

    def test_cerrar_corte_encola_alerta(self) -> None:
        from pos_uniformes.services import corte_caja_service as caja

        estado = caja.EstadoCaja(
            desde=None, hasta=datetime(2026, 9, 9, 17, 30).astimezone(), reactivo=Decimal("11160.00"),
            resumen=caja.ResumenPeriodo(3, 5, Decimal("2000"), Decimal("0"), Decimal("0"), Decimal("0"), Decimal("2000.00")),
            pagos=Decimal("0.00"),
        )
        factory = _sqlite(LibretaCorte, AlertaTelegram)
        with factory() as s, patch.object(caja, "estado_caja", return_value=estado), patch.object(
            caja, "guardar_parametros", side_effect=lambda session, **k: session.commit()
        ), patch.object(caja, "pagos_registrados_del_periodo", return_value=[]):
            corte = caja.cerrar_corte(s, contado=Decimal("13100.00"), creado_por="VEND-1", reactivo_final=Decimal("11160.00"), ahora=estado.hasta)
            pend = al.pendientes(s)
            self.assertEqual(corte.monto_final, Decimal("13100.00"))
        self.assertEqual(len(pend), 1)
        self.assertIn("Corte hecho por VEND-1 a las 17:30", pend[0].texto)
        self.assertNotIn("FALTARON", pend[0].texto)
        self.assertIn("Ajuste: calculado $13,160.00 → real $13,100.00 (−$60.00)", pend[0].texto)
        self.assertEqual(corte.monto_esperado, Decimal("13160.00"))  # el real se guarda; solo Daniel lo ve


class BotIntegraTests(unittest.TestCase):
    def test_escuchar_manda_alertas_pendientes(self) -> None:
        from pos_uniformes.services import telegram_bot_service as bot

        factory = _sqlite(AlertaTelegram, LibretaVenta, LibretaCorte)
        with factory() as s:
            al.encolar(s, "🧾 corte")
        with patch("pos_uniformes.services.telegram_service._llamar", return_value={"result": []}), patch(
            "pos_uniformes.services.telegram_service.enviar_mensaje"
        ) as enviar:
            bot.escuchar(session_factory=factory, token="t", chat_id="123", una_vez=True)
        enviar.assert_called_once()
        self.assertEqual(enviar.call_args.args[0], "🧾 corte")
        self.assertEqual(enviar.call_args.kwargs["chat_id"], "123")


if __name__ == "__main__":
    unittest.main()
