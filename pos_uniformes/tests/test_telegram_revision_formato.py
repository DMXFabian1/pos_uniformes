"""Revisión del formato común del bot (2026-11-20): un solo encabezado por
mensaje, la etiqueta de /hoy, el aviso de «cambió el monto», la ayuda que
cabe en un mensaje y los recordatorios con su encabezado arriba.

Todo con dobles: no toca la base ni manda nada a Telegram.
"""

from __future__ import annotations

import re
import unittest
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest import mock

from pos_uniformes.services import telegram_formato as fmt

HOY = date(2026, 11, 20)

#: Un encabezado con fecha: «✅ PRÉSTAMO APROBADO · vie 20 nov».
_CON_FECHA = re.compile(r" · (lun|mar|mié|jue|vie|sáb|dom) \d{1,2} (" + "|".join(fmt.MESES) + r")\b")


def _encabezados(texto: str) -> list[str]:
    return [l for l in texto.splitlines() if fmt.es_encabezado(l) and _CON_FECHA.search(l)]


@contextmanager
def _sesion():
    yield mock.MagicMock()


def _lista(emoji: str, titulo: str) -> tuple[str, str]:
    """Lo que daría texto_y_botones: su propio encabezado y una línea."""
    return fmt.mensaje(emoji, titulo, cuando=HOY, principal="Nada esperando respuesta. ✅"), "{}"


class QuitarEncabezadoTest(unittest.TestCase):
    def test_quita_solo_un_encabezado(self) -> None:
        t = fmt.mensaje("💵", "Préstamos", cuando=HOY, principal="2 esperando", detalle="· Ana")
        self.assertEqual(fmt.quitar_encabezado(t), "2 esperando\n\n· Ana")
        self.assertEqual(fmt.quitar_encabezado("Sin encabezado\notra"), "Sin encabezado\notra")


class UnSoloEncabezadoAlDecidirTest(unittest.TestCase):
    """#12: el resultado de decidir + la lista llevaban dos encabezados."""

    def _uno(self, texto: str) -> None:
        heads = _encabezados(texto)
        self.assertEqual(len(heads), 1, texto)
        self.assertEqual(texto.splitlines()[0], heads[0])

    def test_prestamos(self) -> None:
        from pos_uniformes.services import prestamos_service as pr
        from pos_uniformes.services import telegram_prestamos_service as prs

        p = SimpleNamespace(employee_name="Ana López", employee_code="ana", monto=Decimal("500"))
        with mock.patch.object(pr, "aprobar", return_value=p), \
                mock.patch.object(prs, "_es_compra", return_value=False), \
                mock.patch.object(prs, "texto_y_botones", return_value=_lista("💵", "Préstamos")):
            aviso, texto, _ = prs.atender("pr:ok:1", session_factory=_sesion, quien="dueño")
        self.assertEqual(aviso, "Aprobado")
        self.assertTrue(texto.startswith("✅ PRÉSTAMO APROBADO"))
        self.assertIn("Nada esperando respuesta", texto)
        self._uno(texto)

    def test_descansos(self) -> None:
        from pos_uniformes.services import descansos_service as ds
        from pos_uniformes.services import telegram_descansos_service as dsc

        s = SimpleNamespace(employee_name="Ana", employee_code="ana", fecha=date(2026, 11, 22))
        with mock.patch.object(ds, "aprobar", return_value=s), \
                mock.patch.object(dsc, "texto_y_botones", return_value=_lista("🛌", "Días de descanso")):
            _, texto, _ = dsc.atender("dc:ok:1", session_factory=_sesion, quien="dueño")
        self.assertTrue(texto.startswith("✅ DESCANSO APROBADO"))
        self._uno(texto)

    def test_vacaciones(self) -> None:
        from pos_uniformes.services import telegram_vacaciones_service as vcs
        from pos_uniformes.services import vacaciones_service as vs

        s = SimpleNamespace(employee_name="Ana", employee_code="ana", desde=date(2026, 12, 1),
                            hasta=date(2026, 12, 5), prima_estimada=0)
        with mock.patch.object(vs, "aprobar", return_value=s), \
                mock.patch.object(vcs, "texto_y_botones", return_value=_lista("🏖", "Vacaciones")):
            _, texto, _ = vcs.atender("vc:ok:1", session_factory=_sesion, quien="dueño")
        self.assertTrue(texto.startswith("✅ VACACIONES APROBADAS"))
        self._uno(texto)

    def test_programas(self) -> None:
        from pos_uniformes.services import telegram_membresias_service as tm
        from pos_uniformes.services.fidelizacion import membresia_service as ms

        m = SimpleNamespace(cliente_id=7, programa=SimpleNamespace(nombre="Profesional"))
        with mock.patch.object(ms, "aprobar_por_dueno", return_value=m), \
                mock.patch.object(tm, "_cliente", return_value=SimpleNamespace(nombre="Escuela X")), \
                mock.patch.object(tm, "texto_y_botones", return_value=_lista("⭐", "Programas")):
            _, texto, _ = tm.atender("mb:ok:7", session_factory=_sesion)
        self.assertTrue(texto.startswith("✅ PROGRAMA APROBADO"))
        self._uno(texto)

    def _dias(self, *, falla: bool = False) -> str:
        from pos_uniformes.services import telegram_mi_pago_service as mp

        lineas = [fmt.encabezado("📆", "Tus días de más", HOY), "1 día de más", "", "· sáb 15 nov — 💵"]
        config = SimpleNamespace(valor_dia=Decimal("400"))
        datos = SimpleNamespace(registros={})
        decidir = mock.Mock(side_effect=ValueError("ya no")) if falla else mock.Mock()
        with mock.patch.object(mp, "_cuenta", return_value=config), \
                mock.patch.object(mp.pd, "decidir_dia_extra", decidir), \
                mock.patch.object(mp, "_pago_que_cubre", return_value=date(2026, 11, 21)), \
                mock.patch.object(mp.pd, "cargar_datos", return_value=datos), \
                mock.patch.object(mp, "_texto_dias", return_value=(lineas, [])):
            return mp._decidir(mock.MagicMock(), "20261115:p", hoy=HOY)[1]

    def test_dias_de_mas(self) -> None:
        texto = self._dias()
        self.assertTrue(texto.startswith("💵 DÍA DE MÁS"))
        self.assertIn("1 día de más", texto)
        self._uno(texto)

    def test_dias_de_mas_ya_no_es(self) -> None:
        texto = self._dias(falla=True)
        self.assertTrue(texto.startswith("📆 TUS DÍAS DE MÁS"))
        self.assertIn("ya no es un día de más", texto)
        self._uno(texto)


class HoyConSuPeriodoTest(unittest.TestCase):
    """#13: /hoy decía «entró hoy» aunque era lo de desde el último corte."""

    def _datos(self, inicio):
        from pos_uniformes.services.resumen_diario_service import DatosResumen

        return DatosResumen(fecha=HOY, operaciones=2, piezas=3, efectivo=Decimal("200"),
                            tarjeta=Decimal("0"), ventas=Decimal("200"), inicio_corte=inicio)

    def _cifra(self, inicio) -> str:
        from pos_uniformes.services.resumen_diario_service import texto_hoy

        return texto_hoy(self._datos(inicio), ahora=datetime(2026, 11, 20, 15, 0)).splitlines()[1]

    def test_corte_de_hoy(self) -> None:
        linea = self._cifra(datetime(2026, 11, 20, 14, 0))
        self.assertTrue(linea.startswith("💰 $200.00 entró desde el corte de hoy"), linea)

    def test_corte_de_ayer(self) -> None:
        linea = self._cifra(datetime(2026, 11, 19, 16, 56))
        self.assertTrue(linea.startswith("💰 $200.00 entró desde el corte de ayer"), linea)

    def test_sin_corte_sigue_diciendo_hoy(self) -> None:
        self.assertEqual(self._cifra(None), "💰 $200.00 entró hoy")

    def test_no_repite_el_periodo(self) -> None:
        from pos_uniformes.services.resumen_diario_service import texto_hoy

        t = texto_hoy(self._datos(datetime(2026, 11, 20, 14, 0)), ahora=datetime(2026, 11, 20, 15, 0))
        self.assertNotIn("(dinero ", t)


class PagarConMontoCambiadoTest(unittest.TestCase):
    """#14: «Cambió el monto» llevaba dos encabezados y la cifra tres veces."""

    def test_un_encabezado_y_una_cifra(self) -> None:
        from pos_uniformes.services import telegram_bot_service as bot
        from pos_uniformes.services import telegram_menu_service as menu
        from pos_uniformes.services import telegram_pagos_service as pg

        desglose = fmt.mensaje("💵", "Pago a Fanny", cuando=HOY, principal=fmt.cifra(Decimal("2115"), "a pagar"),
                               detalle="Sueldo $2,115.00\nTOTAL $2,115.00")
        with mock.patch.object(pg, "monto_pendiente", return_value=Decimal("2115")), \
                mock.patch.object(pg, "desglose_por_code", return_value=desglose), \
                mock.patch.object(pg, "pagar_por_code") as pagar, \
                mock.patch.object(bot, "leer_cifra", return_value=Decimal("2500")):
            aviso, texto, botones = menu.atender("m:pagarok:fanny:2500.00", session_factory=_sesion, hoy=HOY)
        pagar.assert_not_called()
        self.assertEqual(aviso, "Cambió el monto")
        self.assertEqual(len(_encabezados(texto)), 1, texto)
        self.assertEqual(texto.splitlines()[0], "💵 PAGO A FANNY · vie 20 nov")
        self.assertEqual(texto.splitlines()[1], "💰 $2,115.00 a pagar")
        self.assertEqual(texto.count("💰"), 1, texto)
        self.assertIn("era $2,500.00", texto)
        self.assertIn("No pagué nada", texto)
        self.assertIn("pagarok:fanny:2115.00", botones)


class AyudaCabeEnUnMensajeTest(unittest.TestCase):
    """#15: «/ayuda todo» pasaba de telegram_service._MAX y salía partida."""

    def test_ayuda_completa_con_margen(self) -> None:
        from pos_uniformes.services import telegram_service
        from pos_uniformes.services.telegram_bot_service import AYUDA_COMPLETA

        # Telegram cuenta en UTF-16; margen de 50 para lo que se le agregue.
        largo = len(AYUDA_COMPLETA.encode("utf-16-le")) // 2
        self.assertLessEqual(largo, telegram_service._MAX - 50)
        self.assertEqual(len(telegram_service.partir_mensaje(AYUDA_COMPLETA)), 1)


class RecordatorioConEncabezadoArribaTest(unittest.TestCase):
    """#16: «⏰ Sigue sin respuesta:» iba antes del encabezado del aviso."""

    def test_descanso_y_fechada(self) -> None:
        from pos_uniformes.services import alertas_service as al
        from pos_uniformes.services import descansos_service as ds
        from pos_uniformes.services import telegram_descansos_service as dsc

        ahora = datetime(2026, 11, 20, 18, 0, tzinfo=timezone.utc)
        s = SimpleNamespace(ultimo_recordatorio_at=None, created_at=ahora - timedelta(days=2),
                            recordatorios=0, employee_name="Ana", employee_code="ana")
        aviso = fmt.mensaje("🛌", "Pide descanso", cuando=date(2026, 11, 22), principal="Ana pide el domingo.")
        with mock.patch.object(ds, "vencer_pendientes", return_value=[]), \
                mock.patch.object(ds, "pendientes", return_value=[s]), \
                mock.patch.object(dsc, "aviso_de_solicitud", return_value=aviso), \
                mock.patch.object(dsc, "botones_de", return_value="{}"):
            avisos = ds.tarea_periodica(mock.MagicMock(), ahora=ahora)
        self.assertEqual(len(avisos), 1)
        texto = avisos[0][0]
        self.assertTrue(texto.startswith("🛌 PIDE DESCANSO · dom 22 nov"), texto)
        self.assertTrue(texto.endswith("⏰ Sigue sin respuesta."), texto)

        # Si sale tarde de la cola, la nota de «llegó tarde» va al pie, no arriba.
        alerta = SimpleNamespace(texto=texto, created_at=ahora - timedelta(hours=3))
        fechada = al._fechada(alerta, ahora=ahora)
        self.assertTrue(fechada.startswith("🛌 PIDE DESCANSO"), fechada)
        self.assertIn("llegó tarde", fechada.splitlines()[-1])


if __name__ == "__main__":
    unittest.main()
