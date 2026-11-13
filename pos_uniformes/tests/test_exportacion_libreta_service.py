"""Hojas 06_ventas y 07_detalle_ventas del export de Analítica, desde la Libreta.

Daniel (2026-11-12): «la caja antigua ya no es de utilidad, todo lo demás
corre en libreta y kioskos» → «Pantallas con datos viejos». Esas hojas leían
la tabla `venta` de la Caja antigua y llegaban vacías o con lo de abril.
"""

from __future__ import annotations

import unittest
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import Cliente, LibretaVenta
from pos_uniformes.services import exportacion_libreta_service as ex

HOY = date(2026, 11, 12)


class ExportacionLibretaTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
        self.s = Session(engine)
        self.addCleanup(self.s.close)

    def _anotar(self, tipo="venta", monto="300", *, dia=HOY, hora=12, cliente_id=None, detalle=None, **extra):
        row = LibretaVenta(
            employee_code="VEND-4", employee_name="Fanny", tipo=tipo, piezas=1 if tipo != "abono" else 0,
            monto_total=Decimal(monto), monto_neto=Decimal(monto), cliente_id=cliente_id,
            detalle=detalle if detalle is not None else [
                {"sku": "SKU8", "nombre": "Pants 2pz", "talla": "8", "precio": monto, "cantidad": 1, "subtotal": monto}
            ],
            created_at=datetime.combine(dia, time(hora, 0)).astimezone(), **extra,
        )
        self.s.add(row)
        self.s.commit()
        return row

    def _periodo(self):
        return (
            datetime.combine(HOY, time.min).astimezone(),
            datetime.combine(HOY + timedelta(days=1), time.min).astimezone(),
        )

    def test_las_hojas_traen_las_filas_de_la_libreta(self) -> None:
        venta = self._anotar("venta", "300", hora=10, pago_tarjeta=True, privado=True)
        self._anotar("apartado", "900", hora=11)
        self._anotar("abono", "100", hora=12, detalle=[])
        self._anotar("venta", "999", dia=HOY - timedelta(days=1))   # fuera del periodo

        ventas, detalle = ex.cargar(self.s, *self._periodo())

        self.assertEqual([f["tipo"] for f in ventas], ["venta", "apartado", "abono"])
        self.assertEqual(ventas[0]["operacion_id"], venta.id)
        self.assertEqual(ventas[0]["monto_total"], Decimal("300.00"))
        self.assertTrue(ventas[0]["pago_tarjeta"])
        self.assertTrue(ventas[0]["privado"])          # el export es del dueño
        self.assertTrue(ventas[0]["cuenta_como_operacion"])
        self.assertFalse(ventas[2]["cuenta_como_operacion"])   # el abono no es operación
        self.assertEqual(ventas[0]["cliente"], "Mostrador")
        self.assertEqual(len(detalle), 2)              # el abono no trae prendas
        self.assertEqual(detalle[0]["sku"], "SKU8")
        self.assertEqual(detalle[0]["subtotal_linea"], Decimal("300.00"))
        self.assertEqual(detalle[1]["tipo"], "apartado")

    def test_la_anulada_no_sale(self) -> None:
        from pos_uniformes.services.libreta_service import eliminar_operacion

        self._anotar("venta", "300")
        anulada = self._anotar("venta", "700")
        eliminar_operacion(self.s, anulada.id)
        self.s.commit()
        ventas, detalle = ex.cargar(self.s, *self._periodo())
        self.assertEqual([f["monto_total"] for f in ventas], [Decimal("300.00")])
        self.assertEqual(len(detalle), 1)

    def test_filtrado_por_cliente(self) -> None:
        cliente = Cliente(nombre="Ana", codigo_cliente="CLI-1")
        self.s.add(cliente)
        self.s.commit()
        self._anotar("venta", "300", cliente_id=cliente.id, cliente="Ana")
        self._anotar("venta", "500")
        ventas, _ = ex.cargar(self.s, *self._periodo(), cliente_id=cliente.id)
        self.assertEqual(len(ventas), 1)
        self.assertEqual(ventas[0]["cliente"], "Ana")
        self.assertEqual(ventas[0]["cliente_id"], cliente.id)

    def test_linea_sin_subtotal_se_calcula(self) -> None:
        self._anotar("venta", "200", detalle=[{"sku": "A", "nombre": "Playera", "precio": "100", "cantidad": 2}])
        _, detalle = ex.cargar(self.s, *self._periodo())
        self.assertEqual(detalle[0]["subtotal_linea"], Decimal("200.00"))


if __name__ == "__main__":
    unittest.main()
