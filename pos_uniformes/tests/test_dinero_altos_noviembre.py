"""El fondo de papá no es venta, en ningún lado (auditoría 2026-11-07, #6)."""

from __future__ import annotations

import unittest
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from pos_uniformes.database.models import CajaEntrada, LibretaCorte
from pos_uniformes.services import historial_cortes_service as hist


def _sesion():
    engine = create_engine("sqlite://")
    for t in (CajaEntrada, LibretaCorte):
        t.__table__.create(engine)
    return sessionmaker(bind=engine)()


def _corte(s, *, desde, hasta, final="3000", esperado="3000"):
    # Venta de efectivo $1,500, reactivo $1,000, pagos $1,250 y entró $1,750
    # del fondo: en el cajón 1,000 + 1,500 + 1,750 − 1,250 = 3,000.
    c = LibretaCorte(
        fecha=hasta.date(), periodo_label="x", monto_final=Decimal(final), monto_esperado=Decimal(esperado),
        reactivo_inicial=Decimal("1000"), reactivo_final=Decimal("1000"), retiros_pagos=Decimal("1250"),
        otros_retiros=Decimal("0"), creado_por="VEND-1", desde=desde, hasta=hasta, created_at=hasta,
    )
    s.add(c)
    s.commit()
    return c


class LaVentaDeCadaCorteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.s = _sesion()
        self.s.add(CajaEntrada(monto=Decimal("1750"), motivo="Fondo de papá", creado_por="VEND-1",
                               created_at=datetime(2026, 10, 18, 12, 0)))
        self.s.add(CajaEntrada(monto=Decimal("999"), motivo="de otro corte", creado_por="VEND-1",
                               created_at=datetime(2026, 10, 19, 12, 0)))
        self.s.commit()
        self.c = _corte(self.s, desde=datetime(2026, 10, 17, 18, 0), hasta=datetime(2026, 10, 18, 18, 0))

    def test_no_cuenta_el_fondo_como_venta(self) -> None:
        """Decía venta $3,250: los $1,500 vendidos más los $1,750 de papá."""
        cortes = hist.listar_cortes_mes(self.s, date(2026, 10, 1), date(2026, 10, 31))
        self.assertEqual(cortes[0].entradas_periodo, Decimal("1750.00"))     # la del 19 no
        self.assertEqual(hist.venta_oficial(cortes[0]), Decimal("1500.00"))
        self.assertEqual(hist.venta_real(cortes[0]), Decimal("1500.00"))

    def test_ajustar_parte_de_la_venta_sin_el_fondo(self) -> None:
        r = hist.ajustar_corte(self.s, self.c.id, venta=Decimal("1500"), creado_por="VEND-1")
        self.assertEqual(r["monto_final"], Decimal("3000.00"))   # no cambia: es la venta real
        self.assertEqual(r["sin_reportar"], Decimal("0.00"))
        self.assertEqual(r["nota"], "")

    def test_el_detalle_del_celular_lo_dice(self) -> None:
        from pos_uniformes.services import telegram_cortes_service as tc

        texto, _ = tc.detalle(self.s, self.c.id)
        self.assertIn("Lo que dice el ticket: $1,500.00", texto)
        self.assertNotIn("Ajuste tuyo", texto)
        self.assertIn("Entró sin ser venta (fondo de papá…): $1,750.00", texto)

    def test_sin_la_tabla_queda_como_antes(self) -> None:
        engine = create_engine("sqlite://")
        LibretaCorte.__table__.create(engine)
        s = sessionmaker(bind=engine)()
        c = _corte(s, desde=datetime(2026, 10, 17, 18, 0), hasta=datetime(2026, 10, 18, 18, 0))
        hist.anotar_entradas(s, [c])
        self.assertEqual(c.entradas_periodo, Decimal("0.00"))


class CortesDeUnDiaTests(unittest.TestCase):
    def test_un_dia_es_hoy(self) -> None:
        """`/cortes 1` enseñaba hoy y ayer (auditoría 2026-11-07)."""
        from pos_uniformes.services import telegram_cortes_service as tc

        hoy = date(2026, 11, 7)
        self.assertEqual(tc.desde_de(1, hoy), hoy)
        self.assertEqual(tc.desde_de(14, hoy), date(2026, 10, 25))   # 14 días con hoy
        self.assertEqual(tc.desde_de(0, hoy), hoy)


if __name__ == "__main__":
    unittest.main()
