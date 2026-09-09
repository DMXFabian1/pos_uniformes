"""Movimientos privados del dueño: el encargado no los ve en ninguna parte."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from pos_uniformes.database.models import LibretaVenta
from pos_uniformes.services import libreta_service as L


def _sesion():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    LibretaVenta.__table__.create(engine)
    return sessionmaker(bind=engine)()


def _venta(session, *, tarjeta: bool, monto="500.00", comisiones=2, cuando=None):
    v = LibretaVenta(
        employee_code="VEND-4", employee_name="Fanny", tipo="venta", piezas=3,
        comisiones=comisiones, monto_total=Decimal(monto), monto_neto=Decimal(monto),
        pago_tarjeta=tarjeta, detalle=[], created_at=cuando or datetime.now(),
    )
    session.add(v)
    session.commit()
    return v


class MarcarTests(unittest.TestCase):
    def setUp(self) -> None:
        self.session = _sesion()

    def tearDown(self) -> None:
        self.session.close()

    def test_solo_el_dueno_puede_ocultar(self) -> None:
        v = _venta(self.session, tarjeta=True)
        with self.assertRaises(L.SoloElDueno):
            L.marcar_privado(self.session, v.id, privado=True, creado_por="ENC-1")
        self.assertFalse(self.session.get(LibretaVenta, v.id).privado)

    def test_el_efectivo_no_se_puede_ocultar(self) -> None:
        """Esconder efectivo descuadraría el corte del cajón."""
        v = _venta(self.session, tarjeta=False)
        with self.assertRaises(ValueError):
            L.marcar_privado(self.session, v.id, privado=True, creado_por="VEND-1")

    def test_ocultar_y_volver_a_mostrar(self) -> None:
        v = _venta(self.session, tarjeta=True)
        L.marcar_privado(self.session, v.id, privado=True, creado_por="VEND-1")
        self.assertTrue(self.session.get(LibretaVenta, v.id).privado)
        L.marcar_privado(self.session, v.id, privado=False, creado_por="VEND-1")
        self.assertFalse(self.session.get(LibretaVenta, v.id).privado)

    def test_ocultar_todo_el_periodo_solo_toca_la_tarjeta(self) -> None:
        ahora = datetime.now()
        con = _venta(self.session, tarjeta=True, cuando=ahora)
        efectivo = _venta(self.session, tarjeta=False, cuando=ahora)
        viejo = _venta(self.session, tarjeta=True, cuando=ahora - timedelta(days=3))
        cuantos = L.marcar_privadas_del_periodo(
            self.session, ahora - timedelta(hours=1), ahora + timedelta(minutes=1), creado_por="VEND-1"
        )
        self.assertEqual(cuantos, 1)
        self.assertTrue(self.session.get(LibretaVenta, con.id).privado)
        self.assertFalse(self.session.get(LibretaVenta, efectivo.id).privado)
        self.assertFalse(self.session.get(LibretaVenta, viejo.id).privado)

    def test_lo_que_ve_el_encargado_no_trae_privados(self) -> None:
        v = _venta(self.session, tarjeta=True)
        otra = _venta(self.session, tarjeta=False)
        L.marcar_privado(self.session, v.id, privado=True, creado_por="VEND-1")
        rows = self.session.query(LibretaVenta).all()
        vistas = L.sin_privados(rows)
        self.assertEqual([r.id for r in vistas], [otra.id])
        self.assertTrue(L.hay_privados(rows))
        self.assertEqual(L.comisiones_ocultas(rows), 2)

    def test_el_dinero_privado_no_entra_en_los_totales_visibles(self) -> None:
        """Lo que se esconde es el dinero; `sin_privados` es lo que ve él."""
        v = _venta(self.session, tarjeta=True, monto="700.00", comisiones=2)
        _venta(self.session, tarjeta=False, monto="300.00", comisiones=1)
        L.marcar_privado(self.session, v.id, privado=True, creado_por="VEND-1")
        rows = L.sin_privados(self.session.query(LibretaVenta).all())
        resumen = L.resumir_por_empleada(rows)
        self.assertEqual(len(resumen), 1)
        self.assertEqual(resumen[0].monto_total, Decimal("300.00"))


if __name__ == "__main__":
    unittest.main()
