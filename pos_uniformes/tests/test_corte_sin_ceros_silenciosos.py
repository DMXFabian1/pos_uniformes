"""El corte no inventa ceros cuando una consulta falla.

Revisión de deuda, 2026-11-12: retiros, entradas y ajustes del dueño
valían cero ante cualquier error («base sin la tabla todavía», tablas que
existen desde septiembre), y el esperado salía mal sin avisar.
"""

from __future__ import annotations

import unittest
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from sqlalchemy.exc import OperationalError, ProgrammingError

from pos_uniformes.services import corte_caja_service as ccs

AHORA = datetime(2026, 11, 12, 18, 0, tzinfo=timezone.utc)


def _error(clase):
    return clase("SELECT", {}, Exception("falló"))


class EstadoCajaTests(unittest.TestCase):
    def _estado(self, *, retiros=None, entradas=None):
        with patch.object(ccs, "inicio_periodo", return_value=None), \
                patch.object(ccs, "cargar_parametros", return_value=SimpleNamespace(reactivo_actual=Decimal("1000"))), \
                patch.object(ccs, "operaciones_del_periodo", return_value=[]), \
                patch.object(ccs, "pagos_del_periodo", return_value=Decimal("0")), \
                patch("pos_uniformes.services.retiros_service.total_retiros", side_effect=retiros, return_value=Decimal("20")), \
                patch("pos_uniformes.services.entradas_service.total_entradas", side_effect=entradas, return_value=Decimal("0")):
            return ccs.estado_caja(MagicMock(), AHORA)

    def test_con_todo_leido_cuenta_los_retiros(self) -> None:
        self.assertEqual(self._estado().retiros, Decimal("20"))

    def test_si_no_se_leen_los_retiros_no_cuenta_cero(self) -> None:
        with self.assertRaises(OperationalError):
            self._estado(retiros=_error(OperationalError))

    def test_si_no_se_leen_las_entradas_no_cuenta_cero(self) -> None:
        with self.assertRaises(OperationalError):
            self._estado(entradas=_error(OperationalError))


class AjustesEnRangoTests(unittest.TestCase):
    def test_una_caida_de_red_sube(self) -> None:
        session = MagicMock()
        session.scalar.side_effect = _error(OperationalError)
        with self.assertRaises(OperationalError):
            ccs.ajustes_en_rango(session, None, AHORA)

    def test_solo_una_base_sin_las_columnas_vale_cero(self) -> None:
        session = MagicMock()
        session.scalar.side_effect = _error(ProgrammingError)
        self.assertEqual(ccs.ajustes_en_rango(session, None, AHORA), Decimal("0.00"))
        session.rollback.assert_called_once()


if __name__ == "__main__":
    unittest.main()
