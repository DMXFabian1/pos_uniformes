"""Ranking de empleadas sobre la Libreta (decisión D5, 2026-11-08).

- Fuente: `LibretaVenta` (la del POS formal ya no recibe ventas).
- Orden: puntos, luego piezas, luego código.
- Métricas separadas: puntos, piezas, operaciones, importe de ventas,
  apartados (cuántos y cuánto) y abonos aparte (cuántos y cuánto).
- Un abono NO es operación ni se suma al importe del apartado.
- Una venta privada cuenta completa (el ranking es solo del administrador).
"""

from __future__ import annotations

import unittest
from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import LibretaVenta
from pos_uniformes.services import libreta_service as lib
from pos_uniformes.services import ranking_libreta_service as rk
from pos_uniformes.ui.helpers.settings_employee_ranking_helper import (
    LIBRETA_ABONOS_HEADERS,
    LIBRETA_RANKING_HEADERS,
    build_libreta_ranking_view,
)

DIA = date(2026, 11, 6)
D = Decimal


def _item(nombre, cantidad, precio):
    return {"sku": "S", "nombre": nombre, "talla": "8", "cantidad": cantidad, "precio": str(precio)}


class RankingLibretaTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.s = Session(engine)

    def tearDown(self) -> None:
        self.s.close()

    def _op(self, code, nombre, tipo, items, monto, *, hora=12, comisiones=None, **kw):
        return lib.registrar_operacion(
            self.s, employee_code=code, employee_name=nombre, tipo=tipo, items=items,
            monto_total=D(monto), comisiones=comisiones,
            created_at=datetime(DIA.year, DIA.month, DIA.day, hora, 0),
            acreditar_cashback=False, **kw,
        )

    def test_su_propia_compra_no_es_operacion_ni_comision(self):
        """Daniel, 2026-11-12: lo que compra con precio especial no le cuenta."""
        self._op("VEND-4", "Stayce", "venta", [_item("Pantalón", 1, 369)], "332", descuento_empleada=True)
        self._op("VEND-4", "Stayce", "venta", [_item("Playera", 1, 180)], "180")
        [f] = rk.calcular(list(self.s.scalars(select(LibretaVenta))))
        self.assertEqual((f.operaciones, f.puntos), (1, 1))
        [r] = lib.resumir_por_empleada(list(self.s.scalars(select(LibretaVenta))))
        self.assertEqual((r.operaciones, r.comisiones), (1, 1))

    def _cargar(self):
        self.s.commit()
        with patch("pos_uniformes.services.libreta_service.ventana_rango",
                   return_value=(datetime(2026, 11, 6), datetime(2026, 11, 6, 23, 59, 59))):
            return {f.employee_code: f for f in rk.cargar(self.s, DIA, DIA)}

    def test_venta_apartado_abono_y_privada(self) -> None:
        # Evelyn: una venta con 3pz y una venta privada con tarjeta.
        self._op("VEND-3", "Evelyn", "venta", [_item("Pants 3pz", 2, 590)], "1180.00")
        privada = self._op("VEND-3", "Evelyn", "venta", [_item("Playera", 1, 200)], "200.00",
                           pago_tarjeta=True)
        privada.privado = True
        # Nayeli: un apartado de 3 piezas sueltas.
        self._op("VEND-5", "Nayeli", "apartado", [_item("Falda", 3, 300)], "900.00")
        # Cristal: solo cobra un abono (de ese apartado). Vale 0 puntos.
        self._op("VEND-6", "Cristal", "abono", [], "400.00", comisiones=0)

        filas = self._cargar()
        eve, nay, cri = filas["VEND-3"], filas["VEND-5"], filas["VEND-6"]

        # Evelyn: 3pz x2 = 4 puntos + 1 de la playera (la privada cuenta).
        self.assertEqual((eve.puntos, eve.piezas, eve.operaciones, eve.ventas), (5, 3, 2, 2))
        self.assertEqual(eve.importe_ventas, D("1380.00"))
        self.assertEqual((eve.apartados, eve.abonos), (0, 0))

        self.assertEqual((nay.puntos, nay.piezas, nay.operaciones, nay.ventas), (3, 3, 1, 0))
        self.assertEqual((nay.apartados, nay.importe_apartados), (1, D("900.00")))
        self.assertEqual(nay.importe_ventas, D("0.00"))  # un apartado no es venta

        # El abono va aparte: ni operación, ni piezas, ni importe del apartado.
        self.assertEqual((cri.puntos, cri.piezas, cri.operaciones), (0, 0, 0))
        self.assertEqual((cri.abonos, cri.importe_abonos), (1, D("400.00")))
        self.assertEqual(nay.importe_apartados, D("900.00"))

        self.assertEqual([eve.posicion, nay.posicion, cri.posicion], [1, 2, 3])

    def test_orden_puntos_luego_piezas_luego_codigo(self) -> None:
        rows = [
            # B y C empatan en puntos; C tiene más piezas. A y D empatan en todo.
            SimpleNamespace(employee_code="VEND-B", employee_name="B", tipo="venta", comisiones=4, piezas=2, monto_total=D("1")),
            SimpleNamespace(employee_code="VEND-C", employee_name="C", tipo="venta", comisiones=4, piezas=4, monto_total=D("1")),
            SimpleNamespace(employee_code="VEND-D", employee_name="D", tipo="venta", comisiones=1, piezas=1, monto_total=D("1")),
            SimpleNamespace(employee_code="VEND-A", employee_name="A", tipo="venta", comisiones=1, piezas=1, monto_total=D("1")),
            SimpleNamespace(employee_code="VEND-Z", employee_name="Z", tipo="venta", comisiones=9, piezas=1, monto_total=D("1")),
        ]
        orden = [f.employee_code for f in rk.calcular(rows)]
        self.assertEqual(orden, ["VEND-Z", "VEND-C", "VEND-B", "VEND-A", "VEND-D"])

    def test_agrupa_por_codigo_no_por_nombre(self) -> None:
        rows = [
            SimpleNamespace(employee_code="vend-3", employee_name="Eve", tipo="venta", comisiones=1, piezas=1, monto_total=D("10")),
            SimpleNamespace(employee_code="VEND-3", employee_name="Evelyn Ruiz", tipo="venta", comisiones=2, piezas=1, monto_total=D("20")),
        ]
        [f] = rk.calcular(rows)
        self.assertEqual((f.employee_code, f.puntos, f.operaciones, f.importe_ventas), ("VEND-3", 3, 2, D("30.00")))

    def test_vista_tabla_principal_y_abonos_aparte(self) -> None:
        self._op("VEND-3", "Evelyn", "venta", [_item("Pants 3pz", 1, 590)], "590.00")
        self._op("VEND-5", "Nayeli", "apartado", [_item("Falda", 1, 300)], "300.00")
        self._op("VEND-6", "Cristal", "abono", [], "150.00", comisiones=0)
        vista = build_libreta_ranking_view(list(self._cargar().values()), period_label="Hoy")

        self.assertEqual(len(LIBRETA_RANKING_HEADERS), len(vista.rows[0].values))
        self.assertEqual([r.values[1] for r in vista.rows], ["Evelyn", "Nayeli"])  # Cristal no vendió
        self.assertEqual(vista.rows[0].values[2:6], ("2", "1", "1", "$590.00"))
        self.assertEqual(vista.rows[1].values[6:], ("1", "$300.00"))
        self.assertTrue(vista.rows[0].is_top)
        self.assertEqual(len(LIBRETA_ABONOS_HEADERS), len(vista.abonos_rows[0]))
        self.assertEqual(vista.abonos_rows, (("Cristal", "1", "$150.00"),))
        self.assertIn("ventas $590.00", vista.status_label)  # el abono no infla las ventas

    def test_sin_operaciones(self) -> None:
        vista = build_libreta_ranking_view([], period_label="Hoy")
        self.assertEqual((vista.rows, vista.abonos_rows), ((), ()))
        self.assertIn("Sin operaciones", vista.status_label)


class RegresionComisionesTests(unittest.TestCase):
    """Lo que ya valía no cambia con el ranking nuevo."""

    def test_3pz_vale_2_por_pieza_y_lo_demas_1(self) -> None:
        self.assertEqual(lib.comisiones_de_items([_item("Pants 3pz", 3, 1)]), 6)
        self.assertEqual(lib.comisiones_de_items([_item("Conjunto 3 PZ", 1, 1)]), 2)
        self.assertEqual(lib.comisiones_de_items([_item("Conjunto 2pz", 2, 1), _item("Playera", 1, 1)]), 3)

    def test_abono_vale_0_puntos(self) -> None:
        row = SimpleNamespace(employee_code="VEND-6", employee_name="C", tipo="abono", comisiones=0, piezas=0, monto_total=D("400"))
        [f] = rk.calcular([row])
        self.assertEqual((f.puntos, f.operaciones, f.abonos), (0, 0, 1))

    def test_venta_con_monedero_cuenta_completa(self) -> None:
        # Parte pagada con monedero: el importe de venta y los puntos son los
        # de la venta completa (el monedero es forma de pago, no descuento).
        row = SimpleNamespace(employee_code="VEND-3", employee_name="E", tipo="venta", comisiones=2,
                              piezas=1, monto_total=D("590.00"), monto_monedero=D("100.00"))
        [f] = rk.calcular([row])
        self.assertEqual((f.puntos, f.importe_ventas), (2, D("590.00")))


if __name__ == "__main__":
    unittest.main()
