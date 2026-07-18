"""Tests de recordatorios del calendario (pagos, descansos, notas)."""

from __future__ import annotations

import unittest
from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from pos_uniformes.database.connection import Base
from pos_uniformes.services.recordatorio_service import (
    actualizar_recordatorio,
    crear_recordatorio,
    eliminar_recordatorio,
    eliminar_recordatorios_vencidos,
    listar_recordatorios,
    ocurre_en,
    proximos_recordatorios,
    recordatorios_del_mes,
)


def _make_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


class RecordatorioCrudTests(unittest.TestCase):
    def setUp(self) -> None:
        self.s = _make_session()

    def test_crear_unica_y_listar(self) -> None:
        crear_recordatorio(
            self.s, tipo="pago", titulo="Renta", recurrencia="unica",
            fecha=date(2026, 6, 5), monto=8000,
        )
        self.s.commit()
        recs = listar_recordatorios(self.s)
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0].titulo, "Renta")
        self.assertEqual(str(recs[0].monto), "8000.00")

    def test_validaciones(self) -> None:
        with self.assertRaises(ValueError):
            crear_recordatorio(self.s, tipo="x", titulo="a", recurrencia="unica", fecha=date(2026, 1, 1))
        with self.assertRaises(ValueError):
            crear_recordatorio(self.s, tipo="pago", titulo="", recurrencia="unica", fecha=date(2026, 1, 1))
        with self.assertRaises(ValueError):
            crear_recordatorio(self.s, tipo="pago", titulo="Renta", recurrencia="unica")  # sin fecha
        with self.assertRaises(ValueError):
            crear_recordatorio(self.s, tipo="pago", titulo="Nómina", recurrencia="mensual")  # sin día

    def test_actualizar_cambia_recurrencia_y_limpia_campos(self) -> None:
        r = crear_recordatorio(
            self.s, tipo="pago", titulo="Renta", recurrencia="unica",
            fecha=date(2026, 6, 5), monto=8000,
        )
        self.s.commit()
        actualizar_recordatorio(
            self.s, r.id, tipo="pago", titulo="Renta local",
            recurrencia="mensual", dia_mes=1,
        )
        self.s.commit()
        recs = listar_recordatorios(self.s)
        self.assertEqual(len(recs), 1)  # no duplicó
        self.assertEqual(recs[0].titulo, "Renta local")
        self.assertEqual(recs[0].recurrencia, "mensual")
        self.assertEqual(recs[0].dia_mes, 1)
        self.assertIsNone(recs[0].fecha)  # el campo de la recurrencia vieja se limpió

    def test_limpiar_vencidos_solo_borra_unicas_pasadas(self) -> None:
        crear_recordatorio(self.s, tipo="nota", titulo="Pasada", recurrencia="unica", fecha=date(2020, 1, 1))
        crear_recordatorio(self.s, tipo="nota", titulo="Futura", recurrencia="unica", fecha=date(2030, 1, 1))
        crear_recordatorio(self.s, tipo="pago", titulo="Renta", recurrencia="mensual", dia_mes=1)
        self.s.commit()
        n = eliminar_recordatorios_vencidos(self.s, date(2026, 6, 16))
        self.s.commit()
        self.assertEqual(n, 1)
        self.assertEqual({r.titulo for r in listar_recordatorios(self.s)}, {"Futura", "Renta"})

    def test_eliminar(self) -> None:
        r = crear_recordatorio(self.s, tipo="nota", titulo="X", recurrencia="unica", fecha=date(2026, 1, 1))
        rid = r.id
        self.s.commit()
        eliminar_recordatorio(self.s, rid)
        self.s.commit()
        self.assertEqual(listar_recordatorios(self.s), [])


class RecordatorioOcurrenciaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.s = _make_session()

    def _crear(self, **kw):
        r = crear_recordatorio(self.s, **kw)
        self.s.commit()
        return r

    def test_mensual_cae_cada_dia_del_mes(self) -> None:
        r = self._crear(tipo="pago", titulo="Renta", recurrencia="mensual", dia_mes=1)
        self.assertTrue(ocurre_en(r, date(2026, 6, 1)))
        self.assertTrue(ocurre_en(r, date(2026, 7, 1)))
        self.assertFalse(ocurre_en(r, date(2026, 6, 2)))

    def test_mensual_dia_31_cae_ultimo_dia_en_meses_cortos(self) -> None:
        r = self._crear(tipo="pago", titulo="Cierre", recurrencia="mensual", dia_mes=31)
        self.assertTrue(ocurre_en(r, date(2026, 6, 30)))   # junio: 30
        self.assertTrue(ocurre_en(r, date(2026, 2, 28)))   # feb: 28
        self.assertTrue(ocurre_en(r, date(2026, 7, 31)))   # julio: 31

    def test_semanal_cae_ese_dia(self) -> None:
        # dia_semana 6 = domingo. 2026-06-07 es domingo.
        r = self._crear(tipo="descanso", titulo="Descanso", recurrencia="semanal", dia_semana=6)
        self.assertTrue(ocurre_en(r, date(2026, 6, 7)))
        self.assertFalse(ocurre_en(r, date(2026, 6, 8)))  # lunes

    def test_recordatorios_del_mes_agrupa(self) -> None:
        self._crear(tipo="pago", titulo="Renta", recurrencia="mensual", dia_mes=1)
        self._crear(tipo="pago", titulo="Nómina", recurrencia="unica", fecha=date(2026, 6, 15))
        recs = listar_recordatorios(self.s)
        por_dia = recordatorios_del_mes(recs, 2026, 6)
        self.assertIn(1, por_dia)
        self.assertIn(15, por_dia)
        self.assertNotIn(2, por_dia)

    def test_proximos_desde_hoy(self) -> None:
        self._crear(tipo="pago", titulo="Renta", recurrencia="mensual", dia_mes=10)
        recs = listar_recordatorios(self.s)
        prox = proximos_recordatorios(recs, date(2026, 6, 8), dias=7)  # 8..15
        fechas = [f for f, _ in prox]
        self.assertIn(date(2026, 6, 10), fechas)
        self.assertNotIn(date(2026, 6, 20), fechas)


if __name__ == "__main__":
    unittest.main()
