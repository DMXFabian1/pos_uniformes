"""El vigilante del bot, sin avisos que mienten ni silencios (auditoría 2026-11-07)."""

from __future__ import annotations

import unittest
import unittest.mock
from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from pos_uniformes.database.models import LibretaCorte, LibretaVenta
from pos_uniformes.services import alertas_service as al


def _sqlite():
    engine = create_engine("sqlite://")
    for t in (LibretaVenta, LibretaCorte):
        t.__table__.create(engine)
    return sessionmaker(bind=engine)


def _venta(s, momento, monto="300"):
    s.add(LibretaVenta(employee_code="VEND-2", employee_name="Ana López", tipo="venta", piezas=1,
                       monto_total=Decimal(monto), monto_neto=Decimal(monto), created_at=momento))
    s.commit()


_SIN_RESPALDO = patch.object(al.Vigilante, "_respaldo_viejo", lambda self, ahora: [])


class FueraDeHorarioTests(unittest.TestCase):
    def setUp(self) -> None:
        self.factory = _sqlite()
        _SIN_RESPALDO.start()
        self.addCleanup(_SIN_RESPALDO.stop)

    def test_al_cierre_hay_margen(self) -> None:
        """Una venta a las 18:03 era un 🚨: la clienta que se quedó al cierre."""
        v = al.Vigilante()
        with self.factory() as s:
            v.revisar(s, datetime(2026, 9, 7, 10, 0))
            _venta(s, datetime(2026, 9, 7, 18, 3))
            _venta(s, datetime(2026, 9, 7, 8, 45))     # abrió un poco antes
            textos = v.revisar(s, datetime(2026, 9, 7, 18, 5))
        self.assertFalse([t for t in textos if "fuera de horario" in t])

    def test_varias_de_noche_son_un_solo_mensaje(self) -> None:
        v = al.Vigilante()
        with self.factory() as s:
            v.revisar(s, datetime(2026, 9, 7, 10, 0))
            for minuto in (0, 5, 9):
                _venta(s, datetime(2026, 9, 7, 21, minuto), "100")
            textos = v.revisar(s, datetime(2026, 9, 7, 21, 10))
        fuera = [t for t in textos if "fuera de horario" in t]
        self.assertEqual(len(fuera), 1)
        self.assertIn("🚨 3 movimientos fuera de horario", fuera[0])
        self.assertIn("21:05 venta $100.00 por Ana", fuera[0])


class CorteQueNoSeHizoTests(unittest.TestCase):
    """Con propuesta en pie el vigilante se callaba, y si el cierre automático
    tronaba el día se quedaba sin corte sin que nadie se enterara."""

    def setUp(self) -> None:
        self.factory = _sqlite()
        _SIN_RESPALDO.start()
        self.addCleanup(_SIN_RESPALDO.stop)

    def _correr(self, *, cancelado=False, corte=False):
        propuesta = SimpleNamespace(hay=True, fecha=date(2026, 9, 7), cancelado=cancelado)
        v = al.Vigilante()
        with self.factory() as s, patch("pos_uniformes.services.corte_propuesta_service.leer", return_value=propuesta):
            v.revisar(s, datetime(2026, 9, 7, 10, 0))
            _venta(s, datetime(2026, 9, 7, 12, 0))
            if corte:
                s.add(LibretaCorte(fecha=date(2026, 9, 7), periodo_label="x", monto_final=Decimal("1"),
                                   creado_por="VEND-1", created_at=datetime(2026, 9, 7, 18, 40)))
                s.commit()
            a_los_10 = v.revisar(s, datetime(2026, 9, 7, 18, 12))
            a_la_hora = v.revisar(s, datetime(2026, 9, 7, 19, 0))
            a_la_hora_y_media = v.revisar(s, datetime(2026, 9, 7, 19, 31))
            despues = v.revisar(s, datetime(2026, 9, 7, 20, 0))
        return a_los_10, a_la_hora, a_la_hora_y_media, despues

    def test_si_nadie_lo_hizo_se_avisa_una_vez(self) -> None:
        a10, a60, a90, despues = self._correr()
        self.assertEqual((a10, a60), ([], []))      # la conversación sigue en marcha
        self.assertEqual(len(a90), 1)
        self.assertIn("El corte de hoy no se hizo", a90[0])
        self.assertEqual(despues, [])

    def test_hoy_no_es_una_decision(self) -> None:
        self.assertEqual(self._correr(cancelado=True)[2], [])

    def test_con_corte_no_dice_nada(self) -> None:
        self.assertEqual(self._correr(corte=True)[2], [])


class PantallasAvisadasSobrevivenAlReinicioTests(unittest.TestCase):
    def test_otro_vigilante_el_mismo_dia_las_recuerda(self) -> None:
        v = al.Vigilante()
        v.dia_de_las_pantallas = date(2026, 11, 7)
        v.pantallas_avisadas = {"kiosko-1"}
        v._recordar()
        nuevo = al.Vigilante()
        self.assertEqual(nuevo._avisadas_guardadas, (date(2026, 11, 7), ("kiosko-1",)))


class UnaRevisionRotaNoApagaALasDemasTests(unittest.TestCase):
    def setUp(self) -> None:
        _SIN_RESPALDO.start()
        self.addCleanup(_SIN_RESPALDO.stop)

    def test_las_otras_siguen_y_a_la_media_hora_se_dice(self) -> None:
        v = al.Vigilante()
        sesion = SimpleNamespace(rollback=lambda: None)
        rota = patch.object(al.Vigilante, "_movimientos_fuera_de_horario", side_effect=RuntimeError("tabla rota"))
        pantallas = patch.object(al.Vigilante, "_pantalla_apagada", return_value=["⚠️ Caja lleva 12 min"])
        corte = patch.object(al.Vigilante, "_cierre_sin_corte", return_value=[])
        cola = patch.object(al.Vigilante, "_impresion_atorada", return_value=[])
        resumen = patch.object(al.Vigilante, "_resumen_que_no_salio", return_value=[])
        with rota, pantallas, corte, cola, resumen:
            primero = v.revisar(sesion, datetime(2026, 11, 7, 10, 0))
            a_los_20 = v.revisar(sesion, datetime(2026, 11, 7, 10, 20))
            a_los_31 = v.revisar(sesion, datetime(2026, 11, 7, 10, 31))
            despues = v.revisar(sesion, datetime(2026, 11, 7, 10, 40))
        self.assertEqual(primero, ["⚠️ Caja lleva 12 min"])   # las pantallas siguieron
        self.assertEqual(a_los_20, ["⚠️ Caja lleva 12 min"])
        self.assertEqual(len(a_los_31), 2)
        self.assertIn("Desde las 10:00 no puedo revisar los movimientos fuera de horario: tabla rota", a_los_31[0])
        self.assertEqual(a_los_31[1], "⚠️ Caja lleva 12 min")
        self.assertEqual(despues, ["⚠️ Caja lleva 12 min"])    # una sola vez


if __name__ == "__main__":
    unittest.main()


class LasSolicitudesNoSeBarrenTests(unittest.TestCase):
    """La solicitud de descanso que llega del kiosko se borraba en la limpieza
    de la mañana antes de contestarla (auditoría 2026-11-07, #31)."""

    def test_descanso_y_vacaciones_se_conservan(self) -> None:
        from pos_uniformes.services import telegram_descansos_service as tds
        from pos_uniformes.services import telegram_vacaciones_service as tvs

        for modulo in (tds, tvs):
            with patch.object(modulo, "aviso_de_solicitud", return_value="🙋 Ana pide el sábado"), \
                 patch.object(modulo, "botones_de", return_value="{}"), \
                 patch("pos_uniformes.services.telegram_service.enviar_mensaje") as enviar:
                modulo.avisar_a_daniel(None, SimpleNamespace(id=1))
            self.assertTrue(enviar.call_args.kwargs["conservar"], modulo.__name__)


class AbonosFaltantesTests(unittest.TestCase):
    """D2 (Daniel, 2026-11-11): cada 15 min se reponen los abonos de Monedero
    que faltan, y si repone alguno avisa."""

    def setUp(self) -> None:
        al._ultima_revision_abonos = None
        self.addCleanup(setattr, al, "_ultima_revision_abonos", None)
        self.s = unittest.mock.MagicMock()
        self.enviar = unittest.mock.MagicMock()

    def _vuelta(self, ahora, repuestos):
        with patch("pos_uniformes.services.monedero_service.acreditar_faltantes", return_value=repuestos) as af, \
             patch.object(al, "encolar", return_value=True) as enc, \
             patch.object(al, "enviar_pendientes", return_value=1):
            al._abonos_faltantes(self.s, self.enviar, ahora=ahora)
        return af, enc

    def test_repone_y_avisa(self) -> None:
        af, enc = self._vuelta(datetime(2026, 11, 11, 10, 0), 2)
        af.assert_called_once()
        self.assertIn("2 ventas", enc.call_args.args[1])
        self.assertIn("Ya se repusieron", enc.call_args.args[1])

    def test_sin_faltantes_no_avisa(self) -> None:
        af, enc = self._vuelta(datetime(2026, 11, 11, 10, 0), 0)
        af.assert_called_once()
        enc.assert_not_called()

    def test_corre_cada_15_minutos(self) -> None:
        self._vuelta(datetime(2026, 11, 11, 10, 0), 0)
        af, _ = self._vuelta(datetime(2026, 11, 11, 10, 10), 0)
        af.assert_not_called()
        af, _ = self._vuelta(datetime(2026, 11, 11, 10, 16), 0)
        af.assert_called_once()

    def test_si_falla_no_tumba_la_vuelta(self) -> None:
        with patch("pos_uniformes.services.monedero_service.acreditar_faltantes", side_effect=RuntimeError("x")):
            self.assertEqual(al._abonos_faltantes(self.s, self.enviar, ahora=datetime(2026, 11, 11, 10, 0)), 0)
        self.s.rollback.assert_called_once()
