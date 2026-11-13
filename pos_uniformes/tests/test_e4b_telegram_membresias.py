"""E4-B: propuestas de programa en el bot de Telegram, recordatorio diario,
caducidad a los 7 días y el aviso de vuelta a la empleada (Libreta).

Base local de prueba, transacción revertida. No manda nada a Telegram.
"""

from __future__ import annotations

import json
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

from sqlalchemy import select

from pos_uniformes.database.models import AlertaTelegram, Membresia
from pos_uniformes.services import alertas_service
from pos_uniformes.services import telegram_bot_service as bot
from pos_uniformes.services import telegram_menu_service as menu
from pos_uniformes.services import telegram_membresias_service as tm
from pos_uniformes.services.fidelizacion import membresia_service as ms
from pos_uniformes.tests.test_e4a_membresias import _Base


def _datos(botones: str) -> list[str]:
    return [b["callback_data"] for fila in json.loads(botones)["inline_keyboard"] for b in fila]


def _textos(botones: str) -> list[str]:
    return [b["text"] for fila in json.loads(botones)["inline_keyboard"] for b in fila]


class _Fabrica:
    """`session_factory` que entrega la sesión de la prueba sin cerrarla."""

    def __init__(self, s) -> None:
        self.s = s

    def __call__(self):
        return self

    def __enter__(self):
        return self.s

    def __exit__(self, *a):
        return False


class _ConBot(_Base):
    def setUp(self) -> None:
        super().setUp()
        self.f = _Fabrica(self.s)
        self.m = self._proponer()

    def _edad(self, m: Membresia, horas: float) -> datetime:
        """Pone la propuesta `horas` en el pasado y devuelve «ahora»."""
        ahora = datetime.now(timezone.utc)
        m.created_at = ahora - timedelta(hours=horas)
        self.s.flush()
        return ahora

    def _mios(self, avisos):
        return [a for a in avisos if self.cliente.nombre in a[0]]


class AvisoTests(_ConBot):
    def test_el_aviso_trae_con_que_decidir(self) -> None:
        texto = tm.aviso_de_propuesta(self.s, self.m)
        for esperado in ("Lupita propone", "Maximoda Profesional", "Maestra de la Benito Juárez",
                         self.cliente.nombre, self.cliente.codigo_cliente, "Tipo hoy:", "Programa hoy: ninguno",
                         "Sin compras", "su tipo pasa a Docente"):
            self.assertIn(esperado, texto)

    def test_mayorista_avisa_que_institucion_se_respeta(self) -> None:
        otro = self._cliente("Beto E4B")
        m = self._proponer("MAYORISTA", cliente=otro)
        self.assertIn("si es Institución, se queda Institución", tm.aviso_de_propuesta(self.s, m))

    def test_el_programa_actual_aparece_si_ya_esta_en_club(self) -> None:
        otro = self._cliente("Caro E4B")
        ms.inscribir_por_empleada(self.s, cliente_id=otro.id, programa_clave="CLUB", employee_code=self.lupita.codigo)
        m = self._proponer(cliente=otro)
        self.assertIn("Programa hoy: Maximoda Club", tm.aviso_de_propuesta(self.s, m))

    def test_las_compras_salen_de_la_libreta(self) -> None:
        """2026-11-12 (Daniel: «la caja antigua ya no es de utilidad, todo lo
        demás corre en libreta y kioskos»): cuenta las ventas del cliente en
        la Libreta; abonos, apartados y la compra de una empleada no; las
        privadas sí (el aviso solo lo ve el dueño)."""
        from decimal import Decimal

        from pos_uniformes.database.models import LibretaVenta

        ahora = datetime.now(timezone.utc)

        def fila(tipo, monto, dias, **extra):
            self.s.add(LibretaVenta(
                employee_code=self.lupita.codigo, employee_name="Lupita", tipo=tipo, piezas=1,
                monto_total=Decimal(monto), monto_neto=Decimal(monto), cliente_id=self.cliente.id,
                created_at=ahora - timedelta(days=dias), **extra))

        fila("venta", "500", 10)
        fila("venta", "300", 3, privado=True, pago_tarjeta=True)
        fila("abono", "200", 1)
        fila("apartado", "900", 1)
        fila("venta", "150", 0, descuento_empleada=True)
        self.s.flush()
        texto = tm.aviso_de_propuesta(self.s, self.m, ahora=ahora)
        self.assertIn("· 2 compras por $800 (la última hace 3 días)", texto)
        self.assertNotIn("Sin compras", texto)

    def test_una_sola_compra_va_en_singular(self) -> None:
        from decimal import Decimal

        from pos_uniformes.database.models import LibretaVenta

        ahora = datetime.now(timezone.utc)
        self.s.add(LibretaVenta(
            employee_code=self.lupita.codigo, employee_name="Lupita", tipo="venta", piezas=1,
            monto_total=Decimal("1250"), monto_neto=Decimal("1250"), cliente_id=self.cliente.id,
            created_at=ahora))
        self.s.flush()
        self.assertIn("· 1 compra por $1,250 (la última hoy)", tm.aviso_de_propuesta(self.s, self.m, ahora=ahora))

    def test_quien_solo_aparta_no_sale_sin_compras(self) -> None:
        """2026-11-12: el cliente que compra por apartado y liquida con
        abonos sale con sus apartados en una línea aparte (los abonos no se
        suman: sería el mismo dinero dos veces)."""
        from decimal import Decimal

        from pos_uniformes.database.models import LibretaVenta

        ahora = datetime.now(timezone.utc)
        for tipo, monto in (("apartado", "4800"), ("abono", "1600"), ("abono", "3200")):
            self.s.add(LibretaVenta(
                employee_code=self.lupita.codigo, employee_name="Lupita", tipo=tipo, piezas=1,
                monto_total=Decimal(monto), monto_neto=Decimal(monto), cliente_id=self.cliente.id,
                created_at=ahora - timedelta(days=5)))
        self.s.flush()
        texto = tm.aviso_de_propuesta(self.s, self.m, ahora=ahora)
        self.assertIn("· 1 apartado por $4,800 (el último hace 5 días)", texto)
        self.assertNotIn("Sin compras", texto)
        self.assertNotIn("compra por", texto)

    def test_hace_cuenta_dias_de_calendario_en_hora_local(self) -> None:
        """2026-11-12: «hoy»/«ayer» por fecha local, no por bloques de 24 h."""
        import os
        import time

        anterior = os.environ.get("TZ")
        os.environ["TZ"] = "America/Mexico_City"
        time.tzset()
        try:
            # 11/11 20:00 y 12/11 10:00 en la Ciudad de México (UTC-6).
            ahora = datetime(2026, 11, 12, 16, 0, tzinfo=timezone.utc)
            self.assertEqual(tm._hace(datetime(2026, 11, 12, 2, 0, tzinfo=timezone.utc), ahora), "ayer")
            # 10/11 09:00 y 12/11 08:00: anteayer, no «ayer».
            ahora = datetime(2026, 11, 12, 14, 0, tzinfo=timezone.utc)
            self.assertEqual(tm._hace(datetime(2026, 11, 10, 15, 0, tzinfo=timezone.utc), ahora), "hace 2 días")
            self.assertEqual(tm._hace(datetime(2026, 11, 12, 13, 0, tzinfo=timezone.utc), ahora), "hoy")
        finally:
            if anterior is None:
                os.environ.pop("TZ", None)
            else:
                os.environ["TZ"] = anterior
            time.tzset()

    def test_botones_de_una_propuesta(self) -> None:
        datos = _datos(tm.botones_de(self.m))
        self.assertEqual(datos, [f"mb:ok:{self.m.id}", f"mb:no:{self.m.id}", "mb:lista"])
        for d in datos:
            self.assertLessEqual(len(d.encode()), 64)

    def test_avisar_manda_con_botones_y_sin_red_queda_en_la_cola(self) -> None:
        with mock.patch("pos_uniformes.services.telegram_service.enviar_mensaje") as enviar:
            tm.avisar_a_daniel(self.s, self.m)
        _texto, kw = enviar.call_args.args[0], enviar.call_args.kwargs
        self.assertTrue(kw["conservar"])
        self.assertIn(f"mb:ok:{self.m.id}", kw["botones"])

        antes = self.s.scalar(select(AlertaTelegram.id).order_by(AlertaTelegram.id.desc()).limit(1)) or 0
        with mock.patch("pos_uniformes.services.telegram_service.enviar_mensaje", side_effect=RuntimeError("sin red")), \
                mock.patch.object(self.s, "commit"):
            tm.avisar_a_daniel(self.s, self.m)
        en_cola = list(self.s.scalars(select(AlertaTelegram).where(AlertaTelegram.id > antes)))
        self.assertEqual(len(en_cola), 1)
        self.assertIn(f"mb:no:{self.m.id}", en_cola[0].botones)


class BotonesTests(_ConBot):
    def test_aprobar_desde_el_bot(self) -> None:
        aviso, texto, botones = tm.atender(f"mb:ok:{self.m.id}", session_factory=self.f, quien="REMOTO")
        self.assertEqual(aviso, "Aprobado")
        self.assertIn(f"{self.cliente.nombre} ya está en Maximoda Profesional", texto)
        self.assertIn("m:raiz", botones)
        self.s.refresh(self.m)
        self.assertEqual((self.m.estado, self.m.resuelta_por), (ms.ACTIVA, ms.QUIEN_DUENO_TELEGRAM))
        self.assertEqual(self._tipo(self.cliente), "DOCENTE")

    def test_rechazar_desde_el_bot(self) -> None:
        aviso, texto, _b = tm.atender(f"mb:no:{self.m.id}", session_factory=self.f)
        self.assertEqual(aviso, "Rechazado")
        self.assertIn("no entra a Maximoda Profesional", texto)
        self.s.refresh(self.m)
        self.assertEqual(self.m.estado, ms.RECHAZADA)
        self.assertEqual(self._tipo(self.cliente), "GENERAL")

    def test_doble_toque_o_boton_viejo_no_hace_nada(self) -> None:
        tm.atender(f"mb:ok:{self.m.id}", session_factory=self.f)
        aviso, _t, _b = tm.atender(f"mb:no:{self.m.id}", session_factory=self.f)
        self.assertIn("ya no está pendiente: quedó activa", aviso)
        self.s.refresh(self.m)
        self.assertEqual(self.m.estado, ms.ACTIVA)

    def test_lista_detalle_y_botones_desconocidos(self) -> None:
        _a, texto, botones = tm.atender("mb:lista", session_factory=self.f)
        self.assertIn(self.cliente.nombre, texto)
        self.assertIn("caducan solas", texto)
        self.assertIn(f"mb:ver:{self.m.id}", _datos(botones))

        _a, texto, botones = tm.atender(f"mb:ver:{self.m.id}", session_factory=self.f)
        self.assertIn("Por qué: Maestra", texto)
        self.assertEqual(_datos(botones), [f"mb:ok:{self.m.id}", f"mb:no:{self.m.id}", "mb:lista"])

        for raro in ("mb:ok:abc", "mb:borrar:1", "mb:"):
            with self.subTest(raro=raro):
                self.assertEqual(tm.atender(raro, session_factory=self.f), ("No conozco ese botón", "", ""))

    def test_el_bot_no_cambia_ni_saca_de_programa(self) -> None:
        """P-E4-7: ningún botón del bot hace otra cosa que aprobar o rechazar."""
        _a, _t, botones = tm.atender(f"mb:ver:{self.m.id}", session_factory=self.f)
        acciones = {d.split(":")[1] for d in _datos(botones) if d.startswith(tm.PREFIJO)}
        self.assertEqual(acciones, {"ok", "no", "lista"})

    def test_el_bot_y_el_menu_llevan_los_botones_a_programas(self) -> None:
        self.assertEqual(bot.atender_toque("mb:lista", session_factory=self.f)[1],
                         tm.texto_y_botones(self.s)[0])
        self.assertIn("m:programas", _datos(menu.menu_raiz()[1]))
        _a, texto, _b = menu.atender("m:programas", session_factory=self.f)
        self.assertIn(self.cliente.nombre, texto)
        self.assertIn("programas", bot.comandos_conocidos())
        self.assertIn(self.cliente.nombre, bot.atender_texto("/programas", session_factory=self.f))


class TareaPeriodicaTests(_ConBot):
    def test_recordatorio_una_vez_al_dia(self) -> None:
        ahora = self._edad(self.m, 23)
        self.assertEqual(self._mios(ms.tarea_periodica(self.s, ahora=ahora)), [])
        ahora = self._edad(self.m, 25)
        avisos = self._mios(ms.tarea_periodica(self.s, ahora=ahora))
        self.assertEqual(len(avisos), 1)
        self.assertTrue(avisos[0][0].startswith("⏰ Sigue sin respuesta"))
        self.assertIn(f"mb:ok:{self.m.id}", avisos[0][1])
        self.assertEqual(self._mios(ms.tarea_periodica(self.s, ahora=ahora + timedelta(hours=2))), [])
        self.assertEqual(len(self._mios(ms.tarea_periodica(self.s, ahora=ahora + timedelta(hours=25)))), 1)
        self.assertEqual(self.m.recordatorios, 2)

    def test_a_los_siete_dias_caduca_y_se_avisa(self) -> None:
        ahora = self._edad(self.m, 7 * 24 + 1)
        avisos = self._mios(ms.tarea_periodica(self.s, ahora=ahora))
        self.assertEqual(len(avisos), 1)
        self.assertIn("Caducaron", avisos[0][0])
        self.assertEqual(avisos[0][1], "", "una caducada ya no tiene botones")
        self.s.refresh(self.m)
        self.assertEqual(self.m.estado, ms.EXPIRADA)
        self.assertEqual(self._tipo(self.cliente), "GENERAL")

    def test_la_vuelta_de_alertas_encola_y_no_truena_si_falta_la_tabla(self) -> None:
        self._edad(self.m, 25)
        enviados = []
        with mock.patch.object(self.s, "commit"):
            n = alertas_service._membresias(self.s, lambda texto, botones="": enviados.append(texto) or True)
        self.assertGreaterEqual(n, 0)
        self.assertTrue(any(self.cliente.nombre in t for t in enviados) or self.s.scalar(
            select(AlertaTelegram.id).where(AlertaTelegram.texto.contains(self.cliente.nombre))))

        sesion = mock.Mock()
        with mock.patch.object(ms, "tarea_periodica", side_effect=RuntimeError("no existe la tabla membresia")):
            self.assertEqual(alertas_service._membresias(sesion, lambda *a, **k: True), 0)
        sesion.rollback.assert_called_once()


class LibretaTests(_ConBot):
    def test_ella_ve_la_aprobacion_una_sola_vez(self) -> None:
        self.assertEqual(ms.respuestas_sin_ver(self.s, self.lupita.codigo), [], "pendiente todavía no")
        ms.aprobar_por_dueno(self.s, self.m.id)
        sin_ver = ms.respuestas_sin_ver(self.s, self.lupita.codigo.lower())
        self.assertEqual([m.id for m in sin_ver], [self.m.id])
        self.assertIn(f"Daniel aprobó a {self.cliente.nombre} en Maximoda Profesional", ms.texto_de_respuesta(self.s, sin_ver[0]))

        ms.marcar_vista(self.s, self.m.id, "OTRA")
        self.assertEqual(len(ms.respuestas_sin_ver(self.s, self.lupita.codigo)), 1, "otra no la marca")
        ms.marcar_vista(self.s, self.m.id, self.lupita.codigo)
        self.assertEqual(ms.respuestas_sin_ver(self.s, self.lupita.codigo), [])

    def test_rechazo_y_caducidad_tambien_le_llegan(self) -> None:
        ms.rechazar_por_dueno(self.s, self.m.id, motivo="Todavía no compra seguido")
        texto = ms.texto_de_respuesta(self.s, ms.respuestas_sin_ver(self.s, self.lupita.codigo)[0])
        self.assertIn("no aprobó", texto)
        self.assertIn("«Todavía no compra seguido»", texto)

        otro = self._cliente("Dora E4B")
        m2 = self._proponer(cliente=otro)
        ms.tarea_periodica(self.s, ahora=self._edad(m2, 8 * 24))
        textos = [ms.texto_de_respuesta(self.s, m) for m in ms.respuestas_sin_ver(self.s, self.lupita.codigo)]
        self.assertTrue(any("caducó" in t for t in textos))

    def test_el_club_que_inscribio_ella_no_le_llega_como_respuesta(self) -> None:
        otro = self._cliente("Eva E4B")
        ms.inscribir_por_empleada(self.s, cliente_id=otro.id, programa_clave="CLUB", employee_code=self.lupita.codigo)
        self.assertEqual(ms.respuestas_sin_ver(self.s, self.lupita.codigo), [])


if __name__ == "__main__":
    unittest.main()
