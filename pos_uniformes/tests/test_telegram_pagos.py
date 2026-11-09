"""Pagos desde el celular.

El corte ya se hacía desde lejos; los pagos no (Daniel, 2026-09-25). Lo que se
cuida aquí es el candado: un dedo en el celular resbala más fácil que un clic
en la caja, así que lo que saca dinero no pasa con una sola palabra.
"""

from __future__ import annotations

import unittest
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from pos_uniformes.services import telegram_pagos_service as pg


class _Det:
    """Lo mínimo que el texto le pide a un DetallePago."""

    def __init__(self, total="1412.00", comisiones=56, faltas=0):
        self.desde, self.hasta = date(2026, 9, 18), date(2026, 9, 25)
        self.sueldo_base = Decimal("1300.00")
        self.comisiones = comisiones
        self.tarifa_comision = Decimal("2.00")
        self.faltas = faltas
        self.descuento_falta = Decimal("100.00")
        self.dias_trabajados = None
        self.tarifa_dia = None
        self.total = Decimal(total)

    por_dia = False
    monto_comisiones = Decimal("112.00")
    descuento_faltas = Decimal("0.00")


class PagarTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registrados = []

    def _correr(self, argumento, *, det=None, code="VEND-5"):
        from pos_uniformes.services import asistencia_service as asis
        from pos_uniformes.services import nomina_service as nom

        sesion = object()
        det = det or _Det()

        def registrar(*a, **k):
            # Como el servicio real: devuelve el pago GUARDADO. El mensaje del
            # bot sale de aquí, no del pendiente calculado antes (M3).
            self.registrados.append(a)
            return SimpleNamespace(
                total=det.total,
                descuento_prestamos=getattr(det, "prestamo_cubierto", Decimal("0.00")),
            )

        with patch.object(asis, "buscar_code", return_value=code), \
             patch.object(nom, "pago_pendiente", return_value=det), \
             patch.object(nom, "registrar_pago_con_monto", side_effect=registrar), \
             patch.object(pg, "_nombre", return_value="Evelyn Ortiz"), \
             patch.object(pg, "_detalle_texto", wraps=pg._detalle_texto):
            with patch("pos_uniformes.services.telegram_pagos_service.Session"):
                sesion = type("S", (), {
                    "commit": lambda self_: None,
                    # `pagar_por_code` comprueba que la empleada exista y
                    # siga activa antes de mover dinero (2026-10-08). La
                    # sesión falsa tiene que saber contestar eso.
                    "scalar": lambda self_, *a, **k: object(),
                })()
                return pg.pagar(sesion, argumento, quien="VEND-1")

    def test_sin_confirmar_enseña_el_desglose_y_no_paga(self):
        r = self._correr("Evelyn")
        self.assertIn("TOTAL: $1,412.00", r)
        self.assertIn("/pagar Evelyn si", r)
        self.assertEqual(self.registrados, [], "el dinero no se mueve con una sola palabra")

    def test_con_la_confirmacion_si_paga(self):
        r = self._correr("Evelyn si")
        self.assertIn("✅ Pagado", r)
        self.assertIn("$1,412.00", r)
        self.assertEqual(len(self.registrados), 1)

    def test_otras_palabras_tambien_confirman(self):
        for palabra in ("sí", "ok", "dale", "confirmar"):
            self.registrados.clear()
            self._correr(f"Evelyn {palabra}")
            self.assertEqual(len(self.registrados), 1, palabra)

    def test_si_ya_cobro_hoy_lo_dice_y_no_paga(self):
        """El servicio rechaza el segundo pago del día; el bot lo cuenta en
        vez de decir «Pagado» (doble toque, 2026-10-10)."""
        from pos_uniformes.services import asistencia_service as asis
        from pos_uniformes.services import nomina_service as nom

        with patch.object(asis, "buscar_code", return_value="VEND-5"), \
             patch.object(nom, "pago_pendiente", return_value=_Det()), \
             patch.object(nom, "registrar_pago_con_monto",
                          side_effect=ValueError("Ya se le pagó hoy ($1,300.00).")), \
             patch.object(pg, "_nombre", return_value="Evelyn Ortiz"):
            sesion = type("S", (), {"commit": lambda s_: None, "rollback": lambda s_: None,
                                    "scalar": lambda s_, *a, **k: object()})()
            texto = pg.pagar(sesion, "Evelyn si", quien="VEND-1")
        self.assertIn("Ya se le pagó hoy", texto)
        self.assertNotIn("✅", texto)

    def test_si_no_debe_nada_no_ofrece_pagar(self):
        r = self._correr("Evelyn", det=_Det(total="0.00"))
        self.assertIn("no tiene nada pendiente", r)
        self.assertNotIn("/pagar", r)

    def test_si_el_prestamo_se_come_todo_se_cierra_el_ciclo(self):
        """Decía «no tiene nada pendiente» y el ciclo nunca se cerraba: las
        comisiones seguían sumando y el préstamo nunca quedaba cobrado
        (auditoría 2026-11-07)."""
        det = _Det(total="0.00")
        det.prestamo_cubierto = Decimal("1412.00")
        r = self._correr("Evelyn", det=det)
        self.assertIn("TOTAL: $0.00", r)
        self.assertIn("/pagar Evelyn si", r)
        r = self._correr("Evelyn si", det=det)
        self.assertEqual(len(self.registrados), 1)
        self.assertIn("✅ Ciclo de Evelyn Ortiz cerrado: el préstamo se llevó todo el pago ($1,412.00)", r)

    def test_a_quien_no_existe_lo_dice(self):
        r = self._correr("Menganita", code=None)
        self.assertIn("¿Quién es", r)
        self.assertEqual(self.registrados, [])

    def test_sin_nombre_explica_como_se_usa(self):
        self.assertIn("/pagar Fanny", pg.pagar(None, "", quien="VEND-1"))


class RetiroTest(unittest.TestCase):
    def setUp(self) -> None:
        self.hechos = []

    def _correr(self, argumento):
        from pos_uniformes.services import retiros_service

        sesion = type("S", (), {
                    "commit": lambda self_: None,
                    # `pagar_por_code` comprueba que la empleada exista y
                    # siga activa antes de mover dinero (2026-10-08). La
                    # sesión falsa tiene que saber contestar eso.
                    "scalar": lambda self_, *a, **k: object(),
                })()
        with patch.object(retiros_service, "registrar_retiro",
                          side_effect=lambda *a, **k: self.hechos.append(k)):
            return pg.retiro(sesion, argumento, quien="VEND-1")

    def test_pide_el_motivo(self):
        """Sin motivo, el corte de la noche es un misterio."""
        r = self._correr("500")
        self.assertIn("¿Para qué", r)
        self.assertEqual(self.hechos, [])

    def test_con_monto_y_motivo_lo_anota(self):
        r = self._correr("500 gasolina")
        self.assertIn("✅", r)
        self.assertEqual(self.hechos[0]["monto"], Decimal("500"))
        self.assertEqual(self.hechos[0]["motivo"], "gasolina")

    def test_acepta_el_signo_y_las_comas(self):
        self._correr("$1,500 proveedor")
        self.assertEqual(self.hechos[0]["monto"], Decimal("1500"))

    def test_la_coma_decimal_no_multiplica_por_cien(self):
        """«/retiro 500,50 gas» apuntaba $50,050 (2026-10-10)."""
        self._correr("500,50 gasolina")
        self.assertEqual(self.hechos[-1]["monto"], Decimal("500.50"))

    def test_lo_que_no_es_cantidad_no_pasa(self):
        self.assertIn("No entendí", self._correr("abc gasolina"))
        self.assertEqual(self.hechos, [])

    def test_cero_o_negativo_no_pasa(self):
        for malo in ("0 gasolina", "-50 gasolina"):
            self.hechos.clear()
            r = self._correr(malo)
            self.assertEqual(self.hechos, [], malo)
            self.assertTrue("mayor a cero" in r or "No entendí" in r)


class RetiroConTopeTest(RetiroTest):
    """Con un cero de más el esperado quedaba negativo y el siguiente corte
    dejaba el fondo en $0 (auditoría 2026-11-07)."""

    def _con_cajon(self, argumento, hay="4320.00"):
        with patch.object(pg, "_en_cajon", return_value=Decimal(hay)):
            return self._correr(argumento)

    def test_mas_de_lo_que_hay_no_se_apunta(self):
        r = self._con_cajon("15000 gasolina")
        self.assertEqual(self.hechos, [])
        self.assertIn("debería haber $4,320.00 y quieres sacar $15,000.00", r)
        self.assertIn("/retiro 15000 gasolina forzar", r)

    def test_dentro_de_lo_que_hay_si(self):
        self._con_cajon("1500 gasolina")
        self.assertEqual(self.hechos[0]["monto"], Decimal("1500"))

    def test_forzar_lo_apunta_sin_esa_palabra_en_el_motivo(self):
        r = self._con_cajon("15000 proveedor de telas forzar")
        self.assertIn("✅", r)
        self.assertEqual(self.hechos[0]["motivo"], "proveedor de telas")

    def test_si_no_se_sabe_el_cajon_no_se_frena(self):
        with patch.object(pg, "_en_cajon", return_value=None):
            self._correr("15000 gasolina")
        self.assertEqual(len(self.hechos), 1)


class ElBotLosConoceTest(unittest.TestCase):
    def test_estan_en_la_ayuda_y_en_el_despachador(self):
        from pathlib import Path

        from pos_uniformes.services.telegram_bot_service import AYUDA

        for c in ("/pagos", "/pagar", "/retiro", "/deshacerpago"):
            self.assertIn(c, AYUDA, f"{c} no sale en /ayuda")
        fuente = (
            Path(__file__).resolve().parent.parent / "services" / "telegram_bot_service.py"
        ).read_text(encoding="utf-8")
        for c in ("pagos", "pagar", "retiro"):
            self.assertIn(f'cmd.nombre == "{c}"', fuente)


if __name__ == "__main__":
    unittest.main()


class DeshacerSoloElDeHoyTests(unittest.TestCase):
    """El último pago de la tabla puede ser de otro día y de otra persona;
    deshacerlo desde el celular sin verlo era demasiado fácil (2026-10-10)."""

    def _ultimo(self, fecha):
        from types import SimpleNamespace

        from datetime import datetime

        ultimo = SimpleNamespace(id=7, employee_code="VEND-2", total=Decimal("1300.00"), fecha=fecha,
                                 created_at=datetime(2026, 10, 10, 13, 5))
        sesion = type("S", (), {
            "scalars": lambda s_, *a, **k: type("R", (), {"first": lambda r_: ultimo})(),
            "commit": lambda s_: None,
        })()
        return sesion

    def test_el_de_otro_dia_no_se_toca(self):
        from pos_uniformes.services import nomina_service as nom

        with patch.object(pg, "_nombre", return_value="Ana"), patch.object(nom, "deshacer_pago") as des:
            r = pg.deshacer_pago(self._ultimo(date(2026, 10, 9)), quien="VEND-1", hoy=date(2026, 10, 10))
        des.assert_not_called()
        self.assertIn("no de hoy", r)

    def test_el_de_hoy_si(self):
        from pos_uniformes.services import nomina_service as nom

        with patch.object(pg, "_nombre", return_value="Ana"), patch.object(pg, "_corte_despues", return_value=None), \
             patch.object(nom, "deshacer_pago", return_value={"prestamo_regresado": Decimal("0.00")}) as des:
            r = pg.deshacer_pago(self._ultimo(date(2026, 10, 10)), "7", quien="VEND-1", hoy=date(2026, 10, 10))
        des.assert_called_once()
        self.assertIn("Deshecho", r)
        self.assertNotIn("préstamo", r)

    def test_dice_que_el_prestamo_vuelve_a_deberse(self):
        """Auditoría 2026-11-07: el préstamo descontado se perdía al deshacer."""
        from pos_uniformes.services import nomina_service as nom

        with patch.object(pg, "_nombre", return_value="Ana"), patch.object(pg, "_corte_despues", return_value=None), \
             patch.object(nom, "deshacer_pago", return_value={"prestamo_regresado": Decimal("500.00")}):
            r = pg.deshacer_pago(self._ultimo(date(2026, 10, 10)), "7", quien="VEND-1", hoy=date(2026, 10, 10))
        self.assertIn("Su préstamo de $500.00 vuelve a estar pendiente", r)

    def _probar(self, argumento, corte=None):
        from pos_uniformes.services import nomina_service as nom

        with patch.object(pg, "_nombre", return_value="Ana"), patch.object(pg, "_corte_despues", return_value=corte), \
             patch.object(nom, "deshacer_pago", return_value={}) as des:
            r = pg.deshacer_pago(self._ultimo(date(2026, 10, 10)), argumento, quien="VEND-1", hoy=date(2026, 10, 10))
        return r, des

    def test_sin_id_solo_ensena_a_quien_y_cuanto(self):
        """Auditoría 2026-11-07 #10: deshacía sin decir a quién ni pedir confirmación."""
        r, des = self._probar("")
        des.assert_not_called()
        self.assertIn("Ana", r)
        self.assertIn("$1,300.00", r)
        self.assertIn("13:05", r)
        self.assertIn("/deshacerpago 7", r)

    def test_con_otro_id_no_deshace(self):
        r, des = self._probar("6")
        des.assert_not_called()
        self.assertIn("#6 ya no es el último", r)

    def test_si_ya_hubo_corte_no_se_toca(self):
        """El corte ya restó el pago: deshacerlo dejaba dos cortes descuadrados."""
        from datetime import datetime
        from types import SimpleNamespace

        r, des = self._probar("7", corte=SimpleNamespace(created_at=datetime(2026, 10, 10, 18, 0)))
        des.assert_not_called()
        self.assertIn("ya entró en el corte de las 18:00", r)

    def test_busca_el_corte_en_la_base(self):
        from datetime import datetime, timezone

        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from pos_uniformes.database.models import Base, LibretaCorte

        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        pago = datetime(2026, 10, 10, 13, 5)
        with sessionmaker(engine)() as s:
            s.add(LibretaCorte(fecha=date(2026, 10, 10), monto_final=Decimal("100"), created_at=datetime(2026, 10, 10, 12, 0)))
            s.commit()
            self.assertIsNone(pg._corte_despues(s, pago))
            s.add(LibretaCorte(fecha=date(2026, 10, 10), monto_final=Decimal("100"), created_at=datetime(2026, 10, 10, 18, 0)))
            s.commit()
            self.assertIsNotNone(pg._corte_despues(s, pago))


class RetiroRepetidoTests(unittest.TestCase):
    def test_el_mismo_retiro_dos_veces_seguidas_es_uno(self):
        """Telegram reentregando o dos toques: no hay confirmación en /retiro,
        así que esta es la red (2026-10-10)."""
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from pos_uniformes.database.models import Base, CajaRetiro
        from pos_uniformes.services import retiros_service

        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        with sessionmaker(engine)() as s, patch("pos_uniformes.services.alertas_service.encolar"):
            retiros_service.registrar_retiro(s, monto=Decimal("500"), motivo="gasolina", creado_por="VEND-1")
            with self.assertRaises(ValueError):
                retiros_service.registrar_retiro(s, monto=Decimal("500"), motivo="gasolina", creado_por="VEND-1")
            retiros_service.registrar_retiro(s, monto=Decimal("500"), motivo="hielo", creado_por="VEND-1")
            self.assertEqual(s.query(CajaRetiro).count(), 2)


class FechaPagoTest(unittest.TestCase):
    """«/fechapago Stayce 18/10»: el último pago de esa persona pasa a ese día."""

    def _correr(self, argumento, *, mover=None, ultimo=object()):
        from types import SimpleNamespace

        from pos_uniformes.services import asistencia_service as asis
        from pos_uniformes.services import nomina_service as nom

        resultado = mover or {"employee_code": "VEND-4", "employee_name": "Stayce", "de": date(2026, 10, 19),
                              "a": date(2026, 10, 18), "total": Decimal("1476.00"), "ciclo_movido": True}
        with patch.object(asis, "buscar_code", return_value="VEND-4"), \
                patch.object(pg, "existe_y_trabaja", return_value=True), \
                patch.object(pg, "_nombre", return_value="Stayce"), \
                patch.object(nom, "ultimo_pago_registrado", return_value=SimpleNamespace(id=27) if ultimo is not None else None), \
                patch.object(nom, "mover_fecha_pago", return_value=resultado) as mover_mock:
            texto = pg.fecha_pago(MagicMock(), argumento, quien="VEND-1", hoy=date(2026, 10, 20))
        return texto, mover_mock

    def test_el_caso_de_stayce(self) -> None:
        texto, mover = self._correr("Stayce 18/10")
        mover.assert_called_once()
        self.assertEqual(mover.call_args.args[1:], (27, date(2026, 10, 18)))
        self.assertIn("pasó del 19/10 al 18/10", texto)
        self.assertIn("siguiente pago también se recorrió", texto)

    def test_ayer_y_antier(self) -> None:
        _, mover = self._correr("Stayce ayer")
        self.assertEqual(mover.call_args.args[2], date(2026, 10, 19))
        _, mover = self._correr("Stayce antier")
        self.assertEqual(mover.call_args.args[2], date(2026, 10, 18))

    def test_sin_fecha_o_fecha_rara_explica(self) -> None:
        self.assertIn("Por ejemplo", self._correr("Stayce")[0])
        self.assertIn("No entendí", self._correr("Stayce lunes")[0])
        self.assertIn("no es un día", self._correr("Stayce 31/02")[0])

    def test_sin_pagos_lo_dice(self) -> None:
        texto, _ = self._correr("Stayce 18/10", ultimo=None)
        self.assertIn("ningún pago", texto)

    def test_lo_que_el_servicio_rechaza_se_dice_tal_cual(self) -> None:
        from pos_uniformes.services import asistencia_service as asis
        from pos_uniformes.services import nomina_service as nom
        from types import SimpleNamespace

        with patch.object(asis, "buscar_code", return_value="VEND-4"), \
                patch.object(pg, "existe_y_trabaja", return_value=True), \
                patch.object(pg, "_nombre", return_value="Stayce"), \
                patch.object(nom, "ultimo_pago_registrado", return_value=SimpleNamespace(id=27)), \
                patch.object(nom, "mover_fecha_pago", side_effect=ValueError("Ya hay otro pago el 18/10")):
            texto = pg.fecha_pago(MagicMock(), "Stayce 18/10", quien="VEND-1", hoy=date(2026, 10, 20))
        self.assertIn("No se pudo: Ya hay otro pago", texto)
