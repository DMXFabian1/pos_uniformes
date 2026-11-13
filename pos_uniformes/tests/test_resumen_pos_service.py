"""La pestaña Resumen del POS, desde la Libreta (2026-11-12).

Daniel (2026-11-12): «la caja antigua ya no es de utilidad, todo lo demás
corre en libreta y kioskos» → «Pantallas con datos viejos». La tarjeta
«Ventas» y el «Ingreso confirmado» leían la tabla `venta` de la Caja antigua.
"""

from __future__ import annotations

import unittest
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import LibretaVenta
from pos_uniformes.services import resumen_pos_service as rp

HOY = date(2026, 11, 12)


def _op(tipo="venta", monto="100", *, piezas=1, tarjeta=False, neto=None, privado=False, empleada=False):
    return SimpleNamespace(
        tipo=tipo,
        monto_total=Decimal(monto),
        monto_neto=Decimal(neto) if neto else Decimal(monto),
        monto_monedero=Decimal("0"),
        pago_tarjeta=tarjeta,
        piezas=piezas,
        privado=privado,
        descuento_empleada=empleada,
    )


class CifrasPeriodoTests(unittest.TestCase):
    def test_sin_operaciones_todo_en_cero(self) -> None:
        c = rp.cifras_periodo([])
        self.assertEqual((c.operaciones, c.ventas, c.apartados, c.piezas), (0, 0, 0, 0))
        self.assertEqual(c.cobrado, Decimal("0.00"))

    def test_ventas_cuentan_y_se_cobran(self) -> None:
        c = rp.cifras_periodo([_op(monto="300", piezas=2), _op(monto="150")])
        self.assertEqual(c.ventas, 2)
        self.assertEqual(c.operaciones, 2)
        self.assertEqual(c.piezas, 3)
        self.assertEqual(c.cobrado, Decimal("450.00"))

    def test_el_apartado_es_operacion_pero_no_dinero_cobrado(self) -> None:
        c = rp.cifras_periodo([_op(monto="200"), _op("apartado", "900", piezas=3)])
        self.assertEqual(c.operaciones, 2)
        self.assertEqual(c.ventas, 1)
        self.assertEqual(c.apartados, 1)
        self.assertEqual(c.piezas, 4)
        self.assertEqual(c.cobrado, Decimal("200.00"))   # sin sumar el apartado

    def test_el_abono_es_dinero_pero_no_operacion(self) -> None:
        c = rp.cifras_periodo([_op("abono", "250", piezas=0)])
        self.assertEqual(c.operaciones, 0)
        self.assertEqual(c.ventas, 0)
        self.assertEqual(c.cobrado, Decimal("250.00"))

    def test_la_tarjeta_cuenta_lo_que_llega_tras_la_comision(self) -> None:
        c = rp.cifras_periodo([_op(monto="100", tarjeta=True, neto="95.50")])
        self.assertEqual(c.cobrado, Decimal("95.50"))

    def test_la_compra_de_una_empleada_no_es_operacion(self) -> None:
        c = rp.cifras_periodo([_op(monto="100", empleada=True)])
        self.assertEqual(c.operaciones, 0)
        self.assertEqual(c.ventas, 0)

    def test_las_privadas_solo_las_ve_el_dueno(self) -> None:
        rows = [_op(monto="100"), _op(monto="500", tarjeta=True, privado=True)]
        self.assertEqual(rp.cifras_periodo(rows).cobrado, Decimal("600.00"))
        sin = rp.cifras_periodo(rows, incluir_privados=False)
        self.assertEqual(sin.cobrado, Decimal("100.00"))
        self.assertEqual(sin.ventas, 1)

    def test_el_ajuste_del_dueno_corrige_el_cobrado(self) -> None:
        c = rp.cifras_periodo([_op(monto="1000")], ajuste=Decimal("-200"))
        self.assertEqual(c.cobrado, Decimal("800.00"))


class CargarTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
        self.s = Session(engine)
        self.addCleanup(self.s.close)

    def _anotar(self, dia, tipo="venta", monto="300", **extra) -> LibretaVenta:
        row = LibretaVenta(
            employee_code="VEND-4", employee_name="Fanny", tipo=tipo, piezas=1 if tipo != "abono" else 0,
            monto_total=Decimal(monto), monto_neto=Decimal(monto),
            detalle=[], created_at=datetime.combine(dia, time(12, 0)).astimezone(), **extra,
        )
        self.s.add(row)
        self.s.commit()
        return row

    def test_hoy_y_el_mes_salen_de_la_libreta(self) -> None:
        self._anotar(HOY, "venta", "300")
        self._anotar(HOY, "apartado", "900")
        self._anotar(HOY, "abono", "100")
        self._anotar(HOY - timedelta(days=3), "venta", "500")
        self._anotar(date(2026, 10, 31), "venta", "999")   # el mes pasado no cuenta
        r = rp.cargar(self.s, HOY)
        self.assertEqual((r.hoy.ventas, r.hoy.apartados, r.hoy.operaciones), (1, 1, 2))
        self.assertEqual(r.hoy.cobrado, Decimal("400.00"))
        self.assertEqual((r.mes.ventas, r.mes.operaciones), (2, 3))
        self.assertEqual(r.mes.cobrado, Decimal("900.00"))

    def test_la_operacion_anulada_ya_no_cuenta(self) -> None:
        from pos_uniformes.services.libreta_service import eliminar_operacion

        self._anotar(HOY, "venta", "300")
        anulada = self._anotar(HOY, "venta", "700")
        self.assertTrue(eliminar_operacion(self.s, anulada.id))
        self.s.commit()
        r = rp.cargar(self.s, HOY)
        self.assertEqual(r.hoy.ventas, 1)
        self.assertEqual(r.hoy.cobrado, Decimal("300.00"))

    def test_sin_privadas_para_quien_no_es_dueno(self) -> None:
        self._anotar(HOY, "venta", "300")
        self._anotar(HOY, "venta", "500", pago_tarjeta=True, privado=True)
        self.assertEqual(rp.cargar(self.s, HOY).hoy.cobrado, Decimal("800.00"))
        self.assertEqual(rp.cargar(self.s, HOY, incluir_privados=False).hoy.cobrado, Decimal("300.00"))


if __name__ == "__main__":
    unittest.main()
