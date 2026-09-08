"""Caja con reactivo y corte por periodo: sumas puras y cierre."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from pos_uniformes.services import corte_caja_service as caja
from pos_uniformes.services.corte_caja_service import EstadoCaja, ParametrosCaja, ResumenPeriodo, diferencia, resumir_periodo


def _op(tipo, monto, tarjeta=False, piezas=1):
    return SimpleNamespace(tipo=tipo, monto_total=Decimal(monto), pago_tarjeta=tarjeta, piezas=piezas)


class ResumirPeriodoTests(unittest.TestCase):
    def test_efectivo_solo_ventas_y_abonos_sin_tarjeta(self) -> None:
        r = resumir_periodo([
            _op("venta", "500"),
            _op("venta", "300", tarjeta=True),
            _op("abono", "200"),
            _op("abono", "100", tarjeta=True),
            _op("apartado", "900", piezas=3),
        ])
        self.assertEqual(r.operaciones, 5)
        self.assertEqual(r.piezas, 7)
        self.assertEqual(r.ventas, Decimal("800.00"))
        self.assertEqual(r.abonos, Decimal("300.00"))
        self.assertEqual(r.apartados, Decimal("900.00"))
        self.assertEqual(r.tarjeta, Decimal("400.00"))
        self.assertEqual(r.efectivo, Decimal("700.00"))

    def test_vacio(self) -> None:
        r = resumir_periodo([])
        self.assertEqual(r.efectivo, Decimal("0.00"))
        self.assertEqual(r.operaciones, 0)


class EstadoCajaTests(unittest.TestCase):
    def test_esperado_suma_reactivo_y_resta_pagos(self) -> None:
        estado = EstadoCaja(
            desde=None,
            hasta=datetime(2026, 9, 8, 20, tzinfo=timezone.utc),
            reactivo=Decimal("11160.00"),
            resumen=ResumenPeriodo(3, 5, Decimal("2000"), Decimal("500"), Decimal("0"), Decimal("300"), Decimal("2200.00")),
            pagos=Decimal("1350.00"),
            otros_retiros=Decimal("100.00"),
        )
        self.assertEqual(estado.esperado, Decimal("11910.00"))

    def test_diferencia(self) -> None:
        self.assertEqual(diferencia(Decimal("11900"), Decimal("11910")), Decimal("-10.00"))
        self.assertEqual(diferencia(Decimal("11920"), Decimal("11910")), Decimal("10.00"))


class CerrarCorteTests(unittest.TestCase):
    def _estado(self, reactivo="11160.00", efectivo="2200.00", pagos="1350.00"):
        return EstadoCaja(
            desde=datetime(2026, 9, 7, 20, tzinfo=timezone.utc),
            hasta=datetime(2026, 9, 8, 20, tzinfo=timezone.utc),
            reactivo=Decimal(reactivo),
            resumen=ResumenPeriodo(3, 5, Decimal("2000"), Decimal("500"), Decimal("0"), Decimal("300"), Decimal(efectivo)),
            pagos=Decimal(pagos),
        )

    def test_guarda_corte_por_periodo_y_deja_reactivo(self) -> None:
        session = MagicMock()
        guardados = {}

        def _guardar(_s, **campos):
            guardados.update(campos)
            return ParametrosCaja(reactivo_actual=campos["reactivo_actual"])

        with patch.object(caja, "estado_caja", return_value=self._estado()), patch.object(
            caja, "guardar_parametros", side_effect=_guardar
        ):
            corte = caja.cerrar_corte(
                session,
                contado=Decimal("12000.00"),
                creado_por="enc-1",
                reactivo_final=Decimal("11160.00"),
                nota="todo bien",
                ahora=datetime(2026, 9, 8, 20, tzinfo=timezone.utc),
            )
        session.add.assert_called_once_with(corte)
        self.assertEqual(corte.monto_final, Decimal("12000.00"))
        self.assertEqual(corte.monto_esperado, Decimal("12010.00"))  # 11160 + 2200 - 1350
        self.assertEqual(corte.retiros_pagos, Decimal("1350.00"))
        self.assertEqual(corte.reactivo_inicial, Decimal("11160.00"))
        self.assertEqual(corte.reactivo_final, Decimal("11160.00"))
        self.assertEqual(corte.creado_por, "ENC-1")
        self.assertEqual(corte.operaciones, 3)
        self.assertIsNotNone(corte.desde)
        self.assertEqual(guardados, {"reactivo_actual": Decimal("11160.00")})

    def test_reactivo_por_defecto_es_el_mismo_fondo(self) -> None:
        session = MagicMock()
        with patch.object(caja, "estado_caja", return_value=self._estado()), patch.object(
            caja, "guardar_parametros", return_value=ParametrosCaja()
        ):
            corte = caja.cerrar_corte(session, contado=Decimal("12010"), creado_por="VEND-1")
        self.assertEqual(corte.reactivo_final, Decimal("11160.00"))

    def test_reactivo_mayor_al_contado_no_se_permite(self) -> None:
        with patch.object(caja, "estado_caja", return_value=self._estado()):
            with self.assertRaises(ValueError):
                caja.cerrar_corte(MagicMock(), contado=Decimal("100"), creado_por="VEND-1", reactivo_final=Decimal("500"))

    def test_etiqueta_periodo(self) -> None:
        d = datetime(2026, 9, 7, 20, 30)
        h = datetime(2026, 9, 8, 21, 0)
        self.assertEqual(caja._etiqueta_periodo(d, h), "07/09 20:30 → 08/09 21:00")
        self.assertEqual(caja._etiqueta_periodo(None, h), "hasta 08/09 21:00")


if __name__ == "__main__":
    unittest.main()
