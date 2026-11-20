"""💼 Mi pago desde el bot de Telegram (Daniel, 2026-11-19).

«¿puedes hacer que también lo gestione con mi bot de Telegram?»: ver la
cuenta, registrar «ya me pagaron», deshacerlo, decidir los días de más y
marcar sus días con /vino yo. Lo que se cuida es lo de siempre en el bot: lo
que mueve la cuenta pide el segundo toque, un botón viejo o repetido no
registra dos veces, y sin cuenta o sin tablas se contesta claro sin tumbarlo.

Base SQLite en memoria, como las demás pruebas del bot con base.
"""

from __future__ import annotations

import json
import unittest
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from pos_uniformes.services import pago_dueno_service as pd
from pos_uniformes.services import telegram_bot_service as bot
from pos_uniformes.services import telegram_mi_pago_service as mp

D = date
JUE_19 = D(2026, 11, 19)   # el día en que arrancó la cuenta de verdad
MAR_24 = D(2026, 11, 24)   # su descanso (martes)


def _botones(json_botones: str) -> list[tuple[str, str]]:
    if not json_botones:
        return []
    return [(b["text"], b["callback_data"]) for fila in json.loads(json_botones)["inline_keyboard"] for b in fila]


def _dato(json_botones: str, empieza: str) -> str:
    for _, dato in _botones(json_botones):
        if dato.startswith(empieza):
            return dato
    raise AssertionError(f"No hay botón {empieza!r} en {_botones(json_botones)}")


class _ConBase(unittest.TestCase):
    """VEND-1 descansa los martes; Fanny (VEND-5) es una empleada normal."""

    tablas_de_pago = True

    def setUp(self) -> None:
        from pos_uniformes.database.connection import Base
        from pos_uniformes.database.models import Empleada, EmpleadaHorario

        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
        if not self.tablas_de_pago:
            # Un kiosko o una caja sin la migración del pago del dueño.
            for nombre in ("pago_dueno_dia_extra", "pago_dueno_registro", "pago_dueno_config"):
                Base.metadata.tables[nombre].drop(engine)
        self.addCleanup(engine.dispose)
        self.factory = sessionmaker(bind=engine, expire_on_commit=False)
        with self.factory() as s:
            s.add_all([
                Empleada(codigo="VEND-1", nombre_completo="Daniel Fabian", activo=True),
                Empleada(codigo="VEND-5", nombre_completo="Fanny Ortiz", activo=True),
                EmpleadaHorario(employee_code="VEND-1", descanso_weekday=1),
                EmpleadaHorario(employee_code="VEND-5", descanso_weekday=3),
            ])
            s.commit()

    # -- ayudas
    def _configurar(self, inicio=D(2026, 11, 1)) -> None:
        with self.factory() as s:
            pd.guardar_config(s, fecha_inicio=inicio)

    def _registrar(self, programada, pagado, monto=None) -> None:
        with self.factory() as s:
            pd.registrar_pago(s, programada, pagado, monto, "VEND-1", hoy=pagado)

    def _marcar(self, fecha, tipo, code="VEND-1") -> None:
        from pos_uniformes.database.models import EmpleadaEvento

        with self.factory() as s:
            s.add(EmpleadaEvento(employee_code=code, fecha=fecha, tipo=tipo))
            s.commit()

    def _registros(self) -> dict:
        from pos_uniformes.database.models import PagoDuenoRegistro

        with self.factory() as s:
            return {r.fecha_programada: (r.fecha_pago, Decimal(r.monto)) for r in s.query(PagoDuenoRegistro).all()}

    def _eventos(self, code) -> dict:
        from pos_uniformes.database.models import EmpleadaEvento

        with self.factory() as s:
            return {e.fecha: e.tipo for e in s.query(EmpleadaEvento).filter(EmpleadaEvento.employee_code == code)}

    def _decision(self, fecha):
        with self.factory() as s:
            return pd.decision_dia_extra(s, fecha)

    def _responder(self, texto, hoy=JUE_19):
        return bot.responder(texto, session_factory=self.factory, hoy=hoy)

    def _tocar(self, dato, hoy=JUE_19):
        return bot.atender_toque(dato, session_factory=self.factory, hoy=hoy)


# ─── Sin cuenta / sin tablas ─────────────────────────────────────────────


class SinCuentaTests(_ConBase):
    def test_los_comandos_lo_dicen_claro(self) -> None:
        for texto in ("/mipago", "/mepagaron", "/deshacermipago", "/diasdemas"):
            with self.subTest(texto=texto):
                respuesta, _ = self._responder(texto)
                self.assertEqual(respuesta, mp.TEXTO_SIN_CUENTA)
                self.assertIn("Libreta → 💼 Caja → Mi pago", respuesta)

    def test_un_boton_tampoco_registra(self) -> None:
        aviso, texto, _ = self._tocar("mp:pagarok:20261121:20261119:c2500.00")
        self.assertEqual(texto, mp.TEXTO_SIN_CUENTA)
        self.assertEqual(self._registros(), {})

    def test_cuenta_inactiva_es_como_sin_cuenta(self) -> None:
        with self.factory() as s:
            pd.guardar_config(s, fecha_inicio=JUE_19, activo=False)
        self.assertEqual(self._responder("/mipago")[0], mp.TEXTO_SIN_CUENTA)

    def test_vino_yo_marca_aunque_no_haya_cuenta(self) -> None:
        """El calendario es aparte de la cuenta: /receso tampoco la pide."""
        texto, botones = self._responder("/vino yo", hoy=MAR_24)
        self.assertIn("Tú: viniste ✅", texto)
        self.assertEqual(botones, "")
        self.assertEqual(self._eventos("VEND-1"), {MAR_24: "trabajo"})


class SinTablasTests(_ConBase):
    tablas_de_pago = False

    def test_mipago_dice_que_falta_actualizar_sin_tumbar_el_bot(self) -> None:
        for texto in ("/mipago", "/mepagaron", "/diasdemas", "/deshacermipago"):
            with self.subTest(texto=texto):
                self.assertEqual(self._responder(texto)[0], mp.TEXTO_SIN_TABLAS)
                self.assertEqual(bot.atender_texto(texto, session_factory=self.factory, hoy=JUE_19),
                                 mp.TEXTO_SIN_TABLAS)

    def test_los_botones_tambien(self) -> None:
        _, texto, _ = self._tocar("mp:ver")
        self.assertEqual(texto, mp.TEXTO_SIN_TABLAS)
        _, texto, _ = self._tocar("mp:dia:20261124:p")
        self.assertEqual(texto, mp.TEXTO_SIN_TABLAS)

    def test_vino_yo_marca_igual(self) -> None:
        texto, botones = self._responder("/vino yo", hoy=MAR_24)
        self.assertIn("Tú: viniste ✅", texto)
        self.assertEqual(botones, "")
        self.assertEqual(self._eventos("VEND-1"), {MAR_24: "trabajo"})

    def test_el_aviso_y_el_menu_no_truenan(self) -> None:
        from pos_uniformes.services import telegram_menu_service as menu

        with self.factory() as s:
            self.assertEqual(mp.aviso(s, JUE_19), "")
        texto, botones = menu.menu_raiz(self.factory(), hoy=JUE_19)
        self.assertNotIn("Tu pago", texto)
        self.assertIn("mp:ver", botones)


# ─── /mipago ─────────────────────────────────────────────────────────────


class MiPagoTests(_ConBase):
    def test_caso_real_toca_el_3_de_4(self) -> None:
        # Arrancó el 19-nov; ese día le pagaron el 2 de 4 (14-nov).
        self._configurar(JUE_19)
        self._registrar(D(2026, 11, 14), JUE_19)
        texto, botones = self._responder("/mipago")
        self.assertIn("💵 TOCA: 3 de 4 · sáb 21-nov", texto)
        self.assertIn("$2,500 · cubre del 19-nov al 21-nov · Toca en 2 días", texto)
        self.assertIn("Último pago: 19-nov · $2,500 (fue el pago del 14-nov)", texto)
        self.assertIn("Días a favor: 0", texto)
        self.assertIn("Atrasados: ninguno", texto)
        self.assertIn("Pagos de noviembre 2026:", texto)
        self.assertIn("▫️ 1 de 4 · sáb 07-nov · antes de tu cuenta", texto)
        self.assertIn("✅ 2 de 4 · sáb 14-nov · $2,500 · pagado el 19-nov", texto)
        self.assertIn("⏳ 3 de 4 · sáb 21-nov · $2,500 · pendiente", texto)
        self.assertIn("⏳ 4 de 4 · sáb 28-nov · $2,500 · pendiente", texto)
        self.assertIn(("💵 Ya me pagaron (3 de 4 · $2,500)", "mp:pagar:20261121"), _botones(botones))
        self.assertIn(("‹ oct", "mp:mes:202610"), _botones(botones))
        self.assertIn(("dic ›", "mp:mes:202612"), _botones(botones))

    def test_atrasado_el_mas_viejo_arriba(self) -> None:
        self._configurar(D(2026, 11, 1))
        texto, botones = self._responder("/mipago")
        self.assertIn("❗ PAGO ATRASADO: 1 de 4 · sáb 07-nov", texto)
        self.assertIn("atrasado 12 días", texto)
        self.assertIn("Atrasados: 2 (1 de 4 07-nov, 2 de 4 14-nov)", texto)
        self.assertIn("❗ 2 de 4 · sáb 14-nov · $2,500 · atrasado", texto)
        self.assertEqual(_dato(botones, "mp:pagar:"), "mp:pagar:20261107")

    def test_toca_hoy(self) -> None:
        self._configurar(JUE_19)
        texto, _ = self._responder("/mipago", hoy=D(2026, 11, 21))
        self.assertIn("Toca hoy", texto)
        self.assertIn("🔔 3 de 4 · sáb 21-nov · $2,500 · toca hoy", texto)

    def test_dias_de_mas_y_faltas_en_el_desglose(self) -> None:
        self._configurar(D(2026, 11, 1))
        self._marcar(D(2026, 11, 17), "trabajo")          # su martes: día de más
        with self.factory() as s:
            pd.decidir_dia_extra(s, D(2026, 11, 17), pd.PAGAR)
        self._marcar(MAR_24, "trabajo")                    # otro, sin decidir
        texto, botones = self._responder("/mipago", hoy=D(2026, 11, 25))
        self.assertIn("❗ 3 de 4 · sáb 21-nov · $2,885 · atrasado", texto)
        self.assertIn("+ 1 día de más (17-nov) +$385", texto)
        self.assertIn("📌 Días de más sin decidir (por ahora se guardan): 24-nov", texto)
        self.assertIn(("💵 Págamelo 24-nov", "mp:dia:20261124:p"), _botones(botones))
        self.assertIn(("📦 Guárdamelo 24-nov", "mp:dia:20261124:a"), _botones(botones))

    def test_otro_mes(self) -> None:
        self._configurar(JUE_19)
        for arg in ("dic", "diciembre", "12", "12/2026"):
            with self.subTest(arg=arg):
                texto, _ = self._responder(f"/mipago {arg}")
                self.assertIn("Pagos de diciembre 2026:", texto)
                self.assertIn("⏳ 1 de 4 · lun 07-dic · $2,500 · pendiente", texto)
        _, texto, _ = self._tocar("mp:mes:202612")
        self.assertIn("Pagos de diciembre 2026:", texto)
        self.assertIn("No entendí «xyz» como mes", self._responder("/mipago xyz")[0])

    def test_leer_mes_sin_anio_elige_el_mas_cercano(self) -> None:
        self.assertEqual(mp.leer_mes("ene", JUE_19), (2027, 1))
        self.assertEqual(mp.leer_mes("oct", JUE_19), (2026, 10))
        self.assertEqual(mp.leer_mes("anterior", D(2026, 1, 5)), (2025, 12))
        self.assertEqual(mp.leer_mes("", JUE_19), (2026, 11))


# ─── /mepagaron ──────────────────────────────────────────────────────────


class MePagaronTests(_ConBase):
    def setUp(self) -> None:
        super().setUp()
        self._configurar(JUE_19)
        self._registrar(D(2026, 11, 14), JUE_19)

    def test_pregunta_antes_de_escribir(self) -> None:
        texto, botones = self._responder("/mepagaron")
        self.assertIn("¿Registro este pago?", texto)
        self.assertIn("💵 3 de 4 · sáb 21-nov (cubre del 19-nov al 21-nov)", texto)
        self.assertIn("Monto: $2,500 (el calculado)", texto)
        self.assertIn("Te pagaron: hoy, jue 19-nov", texto)
        self.assertEqual(_dato(botones, "mp:pagarok:"), "mp:pagarok:20261121:20261119:c2500.00")
        self.assertIn(("✖️ No", "mp:no"), _botones(botones))
        self.assertNotIn(D(2026, 11, 21), self._registros(), "el dinero no se mueve con una sola palabra")

    def test_el_si_registra_y_el_segundo_toque_no_duplica(self) -> None:
        _, botones = self._responder("/mepagaron")
        dato = _dato(botones, "mp:pagarok:")
        aviso, texto, _ = self._tocar(dato)
        self.assertEqual(aviso, "Anotado")
        self.assertIn("✅ Anotado: te pagaron el 3 de 4 (sáb 21-nov) · $2,500, el 19-nov.", texto)
        self.assertIn("El que sigue: 4 de 4 · sáb 28-nov · $2,500", texto)
        self.assertIn("/deshacermipago 21/11", texto)
        self.assertEqual(self._registros()[D(2026, 11, 21)], (JUE_19, Decimal("2500.00")))
        aviso, texto, _ = self._tocar(dato)
        self.assertEqual(aviso, "Ya estaba")
        self.assertIn("No registré nada otra vez", texto)
        self.assertEqual(len(self._registros()), 2)

    def test_otro_monto_y_otra_fecha(self) -> None:
        texto, botones = self._responder("/mepagaron 2400 18/11")
        self.assertIn("Monto: $2,400 (el calculado es $2,500)", texto)
        self.assertIn("Te pagaron: ayer, mié 18-nov", texto)
        dato = _dato(botones, "mp:pagarok:")
        self.assertEqual(dato, "mp:pagarok:20261121:20261118:m2400.00")
        self._tocar(dato)
        self.assertEqual(self._registros()[D(2026, 11, 21)], (D(2026, 11, 18), Decimal("2400.00")))

    def test_elegir_el_pago(self) -> None:
        texto, botones = self._responder("/mepagaron 4 de 4")
        self.assertIn("💵 4 de 4 · sáb 28-nov", texto)
        self.assertEqual(_dato(botones, "mp:pagarok:"), "mp:pagarok:20261128:20261119:c2500.00")
        texto, botones = self._responder("/mepagaron pago 28/11 ayer")
        self.assertEqual(_dato(botones, "mp:pagarok:"), "mp:pagarok:20261128:20261118:c2500.00")

    def test_lo_que_no_se_puede(self) -> None:
        self.assertIn("ya está registrado", self._responder("/mepagaron 2 de 4")[0])
        self.assertIn("no es fecha de pago", self._responder("/mepagaron pago 15/11")[0])
        self.assertIn("No entendí «gasolina»", self._responder("/mepagaron gasolina")[0])
        self.assertIn("no puede ser futura", self._responder("/mepagaron 20/11/2026")[0])

    def test_si_el_monto_cambio_pregunta_otra_vez(self) -> None:
        _, botones = self._responder("/mepagaron")
        dato = _dato(botones, "mp:pagarok:")
        self._marcar(D(2026, 11, 20), "falta")            # ahora son $2,115
        aviso, texto, botones = self._tocar(dato)
        self.assertEqual(aviso, "Cambió el monto")
        self.assertIn("era $2,500 y ahora es $2,115. No registré nada.", texto)
        self.assertEqual(_dato(botones, "mp:pagarok:"), "mp:pagarok:20261121:20261119:c2115.00")
        self.assertNotIn(D(2026, 11, 21), self._registros())

    def test_el_boton_de_otro_dia_ya_no_hace_nada(self) -> None:
        ayer = datetime(2026, 11, 18, 18, 0).astimezone()
        ahora = datetime(2026, 11, 19, 10, 0).astimezone()
        for dato in ("mp:pagarok:20261121:20261118:c2500.00", "mp:deshacerok:20261114:20261119:2500.00"):
            with self.subTest(dato=dato):
                self.assertIn("ya no hace nada", bot.boton_vencido(dato, ayer.timestamp(), ahora))
        # Ver y elegir un día de más no mueven dinero: no se bloquean.
        self.assertIsNone(bot.boton_vencido("mp:ver", ayer.timestamp(), ahora))
        self.assertIsNone(bot.boton_vencido("mp:pagar:20261121", ayer.timestamp(), ahora))

    def test_ya_me_pagaron_de_mipago_lleva_a_la_pregunta(self) -> None:
        _, texto, botones = self._tocar("mp:pagar:20261121")
        self.assertIn("¿Registro este pago?", texto)
        self.assertEqual(_dato(botones, "mp:pagarok:"), "mp:pagarok:20261121:20261119:c2500.00")
        aviso, texto, _ = self._tocar("mp:no")
        self.assertEqual(texto, "Ok, no cambié nada.")

    def test_leer_pedido(self) -> None:
        dias = (7, 14, 21, 28)
        self.assertEqual(mp.leer_pedido_pago("", JUE_19, dias), (None, JUE_19, None))
        self.assertEqual(mp.leer_pedido_pago("$2,400 antier", JUE_19, dias), (None, D(2026, 11, 17), Decimal("2400.00")))
        self.assertEqual(mp.leer_pedido_pago("del 7/12", JUE_19, dias)[0], D(2026, 12, 7))
        with self.assertRaises(ValueError):
            mp.leer_pedido_pago("5 de 4", JUE_19, dias)
        with self.assertRaises(ValueError):
            mp.leer_pedido_pago("2400 2500", JUE_19, dias)


# ─── /deshacermipago ─────────────────────────────────────────────────────


class DeshacerTests(_ConBase):
    def setUp(self) -> None:
        super().setUp()
        self._configurar(JUE_19)
        self._registrar(D(2026, 11, 14), JUE_19)

    def test_pregunta_y_deshace_el_ultimo(self) -> None:
        texto, botones = self._responder("/deshacermipago")
        self.assertIn("¿Deshago este pago?", texto)
        self.assertIn("↩️ 2 de 4 · sáb 14-nov · $2,500, pagado el 19-nov", texto)
        self.assertIn(D(2026, 11, 14), self._registros(), "preguntar no deshace")
        dato = _dato(botones, "mp:deshacerok:")
        aviso, texto, _ = self._tocar(dato)
        self.assertEqual(aviso, "Deshecho")
        self.assertIn("↩️ Deshecho: el 2 de 4 (sáb 14-nov) vuelve a estar atrasado.", texto)
        self.assertEqual(self._registros(), {})
        aviso, texto, _ = self._tocar(dato)
        self.assertEqual(aviso, "Ya no estaba")

    def test_el_indicado(self) -> None:
        self._registrar(D(2026, 11, 21), D(2026, 11, 21))
        texto, botones = self._responder("/deshacermipago 14/11", hoy=D(2026, 11, 21))
        self.assertEqual(_dato(botones, "mp:deshacerok:"), "mp:deshacerok:20261114:20261119:2500.00")
        self.assertIn("No tengo registrado el pago del 28-nov", self._responder("/deshacermipago 28/11")[0])

    def test_si_cambio_desde_que_se_vio_no_deshace(self) -> None:
        _, botones = self._responder("/deshacermipago")
        dato = _dato(botones, "mp:deshacerok:")
        with self.factory() as s:
            pd.deshacer_pago(s, D(2026, 11, 14), "VEND-1")
        self._registrar(D(2026, 11, 14), JUE_19, monto="2000")
        aviso, texto, _ = self._tocar(dato)
        self.assertEqual(aviso, "Cambió")
        self.assertIn("No deshice nada", texto)
        self.assertIn(D(2026, 11, 14), self._registros())

    def test_sin_pagos(self) -> None:
        with self.factory() as s:
            pd.deshacer_pago(s, D(2026, 11, 14), "VEND-1")
        self.assertIn("No hay ningún pago tuyo registrado", self._responder("/deshacermipago")[0])


# ─── Sus días: /vino yo, /falta yo, /descanso yo y /diasdemas ────────────


class MarcarSusDiasTests(_ConBase):
    def setUp(self) -> None:
        super().setUp()
        self._configurar(JUE_19)

    def test_vino_en_su_descanso_pregunta_pagamelo_o_guardamelo(self) -> None:
        texto, botones = self._responder("/vino_yo", hoy=MAR_24)
        self.assertIn("Tú: viniste ✅ (mar 24-nov)", texto)
        self.assertIn("¿Te lo pagamos o te lo guardamos?", texto)
        self.assertIn("💵 Págamelo: suma $385 a tu pago del 28-nov.", texto)
        self.assertIn(("💵 Págamelo 24-nov", "mp:dia:20261124:p"), _botones(botones))
        self.assertIn(("📦 Guárdamelo 24-nov", "mp:dia:20261124:a"), _botones(botones))
        aviso, texto, _ = self._tocar("mp:dia:20261124:p", hoy=MAR_24)
        self.assertEqual(aviso, "Te lo pagamos")
        self.assertIn("💵 Te lo pagamos: el 24-nov suma $385 a tu pago del 28-nov.", texto)
        self.assertEqual(self._decision(MAR_24), pd.PAGAR)
        self.assertIn("⏳ 4 de 4 · sáb 28-nov · $2,885 · pendiente", self._responder("/mipago", hoy=MAR_24)[0])

    def test_todas_las_formas_de_decir_yo(self) -> None:
        for texto in ("/vino yo", "/vino_Daniel", "/vino daniel", "/vino dueño"):
            with self.subTest(texto=texto):
                with self.factory() as s:
                    from pos_uniformes.services.calendario_empleadas_service import quitar_marca

                    quitar_marca(s, "VEND-1", MAR_24)
                self.assertIn("Tú: viniste ✅", self._responder(texto, hoy=MAR_24)[0])

    def test_dos_veces_quita_la_marca_y_la_decision(self) -> None:
        self._responder("/vino yo", hoy=MAR_24)
        self._tocar("mp:dia:20261124:p", hoy=MAR_24)
        texto, botones = self._responder("/vino yo", hoy=MAR_24)
        self.assertIn("Tú: marca quitada ↩", texto)
        self.assertEqual(botones, "")
        self.assertIsNone(self._decision(MAR_24), "un «págamelo» viejo no revive")

    def test_un_boton_de_un_dia_que_ya_no_es_de_mas_no_cambia_nada(self) -> None:
        aviso, texto, _ = self._tocar("mp:dia:20261124:p", hoy=MAR_24)
        self.assertEqual(aviso, "Ya no es día de más")
        self.assertIn("No cambié nada", texto)
        self.assertIsNone(self._decision(MAR_24))

    def test_descanso_en_otro_dia_mueve_el_martes(self) -> None:
        jue_26 = D(2026, 11, 26)
        texto, _ = self._responder("/descanso yo", hoy=jue_26)
        self.assertIn("Tú: descansas 🛌 (jue 26-nov)", texto)
        self.assertIn("Tu descanso del mar 24-nov pasa a trabajo (se movió; no es día de más).", texto)
        with self.factory() as s:
            self.assertFalse(pd.es_dia_extra(s, MAR_24))

    def test_descansar_otro_dia_quita_el_dia_de_mas_y_lo_dice(self) -> None:
        self._responder("/vino yo", hoy=MAR_24)
        self._tocar("mp:dia:20261124:p", hoy=MAR_24)
        texto, _ = self._responder("/descanso yo", hoy=D(2026, 11, 26))
        self.assertIn("El mar 24-nov ya no es día de más: esa semana ya quedó pareja con tu descanso.", texto)
        self.assertIsNone(self._decision(MAR_24), "la decisión huérfana se borra")

    def test_falta_se_descuenta_o_se_cubre(self) -> None:
        texto, _ = self._responder("/falta yo", hoy=D(2026, 11, 20))
        self.assertIn("Tú: falta ✗ (vie 20-nov)", texto)
        self.assertIn("Se descuenta $385 de tu pago del 21-nov (queda en $2,115).", texto)
        # Con un día a favor guardado, la siguiente falta se cubre.
        self._responder("/vino yo", hoy=MAR_24)
        self._tocar("mp:dia:20261124:a", hoy=MAR_24)
        texto, _ = self._responder("/falta yo", hoy=D(2026, 11, 25))
        self.assertIn("Se cubre con un día a favor (te quedan 0).", texto)

    def test_diasdemas(self) -> None:
        self.assertIn("No tienes días de más", self._responder("/diasdemas")[0])
        self._responder("/vino yo", hoy=MAR_24)
        self._marcar(D(2026, 12, 1), "trabajo")
        self._tocar("mp:dia:20261124:p", hoy=D(2026, 12, 1))
        texto, botones = self._responder("/diasdemas", hoy=D(2026, 12, 1))
        self.assertIn("· mar 24-nov — 💵 se paga el 28-nov", texto)
        self.assertIn("· mar 01-dic — ❔ sin decidir (por ahora se guarda)", texto)
        datos = [d for _, d in _botones(botones)]
        self.assertIn("mp:dia:20261124:a", datos)
        self.assertNotIn("mp:dia:20261124:p", datos, "ya está en págamelo: solo se ofrece el cambio")
        self.assertIn("mp:dia:20261201:p", datos)
        self.assertIn("mp:dia:20261201:a", datos)


class LasEmpleadasNoCambianTests(_ConBase):
    def test_vino_fanny_sigue_igual(self) -> None:
        self._configurar(JUE_19)
        texto = bot.atender_texto("/vino Fanny", session_factory=self.factory, hoy=JUE_19)
        self.assertTrue(texto.startswith("Fanny: vino ✅"))
        self.assertEqual(self._eventos("VEND-5"), {JUE_19: "trabajo"})
        self.assertEqual(self._eventos("VEND-1"), {})
        texto, botones = self._responder("/falta_Fanny")
        self.assertTrue(texto.startswith("Fanny: falta ✗"))
        self.assertEqual(botones, "")

    def test_si_una_empleada_se_llama_daniel_daniel_es_ella(self) -> None:
        from pos_uniformes.database.models import Empleada

        with self.factory() as s:
            s.add(Empleada(codigo="VEND-9", nombre_completo="Daniel Ruiz", activo=True))
            s.commit()
        texto = bot.atender_texto("/vino daniel", session_factory=self.factory, hoy=JUE_19)
        self.assertTrue(texto.startswith("Daniel: vino ✅"))
        self.assertEqual(self._eventos("VEND-9"), {JUE_19: "trabajo"})
        self.assertEqual(self._eventos("VEND-1"), {})
        # «yo» sigue siendo él.
        self.assertIn("Tú:", self._responder("/vino yo")[0])

    def test_quien_es_yo(self) -> None:
        for si in ("yo", "Yo", "dueño", "VEND-1", "daniel"):
            self.assertTrue(mp.es_el_dueno(si), si)
        for no in ("Fanny", "", "Daniela", "yolanda"):
            self.assertFalse(mp.es_el_dueno(no), no)


# ─── Ayuda, menú, autocompletar y aviso ──────────────────────────────────


class AyudaYMenuTests(unittest.TestCase):
    def test_la_ayuda_los_lista(self) -> None:
        for c in ("/mipago", "/mepagaron", "/deshacermipago", "/diasdemas", "/vino_yo", "/falta_yo"):
            self.assertIn(c, bot.AYUDA, f"{c} no sale en /ayuda")

    def test_autocompletar(self) -> None:
        nombres = {c for c, _ in bot.COMANDOS_MENU}
        self.assertTrue({"mipago", "mepagaron", "diasdemas"} <= nombres)

    def test_quisiste_decir(self) -> None:
        self.assertIn("/mipago", bot.comando_desconocido("mipgo"))
        self.assertIn("/mepagaron", bot.comando_desconocido("mepagron"))
        self.assertIn("/diasdemas", bot.comando_desconocido("diasdema"))

    def test_el_bot_y_el_servicio_conocen_los_mismos_comandos(self) -> None:
        self.assertEqual(set(bot._MI_PAGO), set(mp.COMANDOS))
        for nombre in mp.COMANDOS:
            self.assertFalse(nombre.startswith("deshacer_"), "parsear lo mandaría a /deshacer")

    def test_el_tablero_tiene_mi_pago_y_sigue_cabiendo(self) -> None:
        from pos_uniformes.services import telegram_menu_service as menu

        self.assertIn("mp:ver", {d for fila in menu._RAIZ for _, d in fila})
        self.assertLessEqual(len(menu._RAIZ), 7)
        self.assertFalse(menu.es_del_menu("mp:ver"))


class AvisoTests(_ConBase):
    def test_texto_aviso(self) -> None:
        self._configurar(JUE_19)
        with self.factory() as s:
            self.assertEqual(mp.aviso(s, JUE_19), "")
            self.assertEqual(mp.aviso(s, D(2026, 11, 21)), "💼 Tu pago: toca hoy el 3 de 4 · $2,500 → /mipago")
            self.assertEqual(mp.aviso(s, D(2026, 11, 20), incluir_manana=True),
                             "💼 Tu pago: mañana toca el 3 de 4 · $2,500 → /mipago")
            self.assertEqual(mp.aviso(s, D(2026, 11, 20)), "")
            self.assertEqual(
                mp.aviso(s, D(2026, 11, 29)),
                "💼 Tu pago: ❗ atrasado el 3 de 4 (21-nov) · $2,500 y 1 más → /mipago",
            )

    def test_sin_cuenta_no_hay_aviso(self) -> None:
        with self.factory() as s:
            self.assertEqual(mp.aviso(s, D(2026, 11, 21)), "")

    def test_va_en_el_resumen_del_dia(self) -> None:
        from pos_uniformes.services import resumen_diario_service as rd

        d = rd.DatosResumen(fecha=D(2026, 11, 21), pago_dueno="💼 Tu pago: toca hoy el 3 de 4 · $2,500 → /mipago")
        texto = rd.formatear(d)
        self.assertIn("💼 Tu pago: toca hoy el 3 de 4", texto)
        self.assertLess(texto.index("💼 Tu pago"), texto.index("📅 MAÑANA"))
        self.assertNotIn("Tu pago", rd.formatear(rd.DatosResumen(fecha=D(2026, 11, 21))))

    def test_el_resumen_lo_recolecta(self) -> None:
        from pos_uniformes.services import resumen_diario_service as rd

        self._configurar(JUE_19)
        d = rd.DatosResumen(fecha=D(2026, 11, 21))
        with self.factory() as s:
            rd._pago_dueno(s, d, D(2026, 11, 21))
        self.assertEqual(d.pago_dueno, "💼 Tu pago: toca hoy el 3 de 4 · $2,500 → /mipago")

    def test_va_en_el_menu_de_la_manana(self) -> None:
        from unittest.mock import patch

        from pos_uniformes.services import resumen_diario_service as rd
        from pos_uniformes.services import telegram_menu_service as menu

        self._configurar(JUE_19)
        with patch.object(rd, "recolectar", return_value=rd.DatosResumen(fecha=D(2026, 11, 21))), \
             patch("pos_uniformes.services.asistencia_service.asistencia_del_dia", return_value=[]):
            with self.factory() as s:
                texto = menu.cabecera(s, hoy=D(2026, 11, 21))
        self.assertIn("💼 Tu pago: toca hoy el 3 de 4 · $2,500 → /mipago", texto)
        self.assertTrue(texto.endswith("¿Qué quieres ver?"))


if __name__ == "__main__":
    unittest.main()


# ─── Hallazgos de la revisión (2026-11-19) ───────────────────────────────


class FechaSinAnioTests(_ConBase):
    def setUp(self) -> None:
        super().setUp()
        self._configurar(JUE_19)

    def test_una_fecha_futura_sin_anio_se_rechaza(self) -> None:
        """«24/11» con hoy 19-nov era el 24-nov-2025 y se registraba."""
        for arg in ("24/11", "1/12"):
            with self.subTest(arg=arg):
                texto, botones = self._responder(f"/mepagaron {arg}")
                self.assertIn("no puede ser futura", texto)
                self.assertNotIn("mp:pagarok:", botones)
        self.assertEqual(self._registros(), {})

    def test_a_inicios_de_enero_un_dia_de_diciembre_es_del_anio_pasado(self) -> None:
        dias = (7, 14, 21, 28)
        self.assertEqual(mp.leer_pedido_pago("28/12", D(2027, 1, 3), dias)[1], D(2026, 12, 28))
        self.assertEqual(mp.leer_pedido_pago("18/11", JUE_19, dias)[1], D(2026, 11, 18))
        self.assertEqual(mp.leer_pedido_pago("24/11", JUE_19, dias)[1], D(2026, 11, 24))

    def test_si_te_pagaron_otro_anio_se_ve_el_anio(self) -> None:
        self.assertIn("2025", mp._cuando_te_pagaron(D(2025, 12, 28), D(2026, 1, 3)))
        self.assertNotIn("2026", mp._cuando_te_pagaron(D(2026, 11, 17), JUE_19))
