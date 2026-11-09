"""Reasignar una venta de la Libreta a otra empleada (decisión D2, 2026-11-08).

Reglas de Daniel; si una falla NO se reasigna nada:
- solo el dueño (VEND-1);
- solo el mismo día de la venta;
- la empleada destino existe y está activa;
- la comisión no se le ha pagado a la empleada original;
- sin cambios retroactivos (si a la destino ya se le pagó después de esa
  venta, nadie la cobraría);
- queda en la bitácora: quién, cuándo, de quién a quién y cuántos puntos.
"""

from __future__ import annotations

import unittest
from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import (
    AuditoriaAusencias,
    Empleada,
    EmpleadaHorario,
    EmpleadaPago,
    LibretaVenta,
)
from pos_uniformes.services.calendario_empleadas_service import (
    cargar_horario,
    comisiones_desde_ultimo_pago,
)
from pos_uniformes.services.libreta_service import ReasignacionNoPermitida, reasignar_empleada

DIA = date(2026, 11, 6)
ORIGEN, DESTINO, INACTIVA = "VEND-3", "VEND-5", "VEND-7"


def _local(dia: date, hora: int, minuto: int = 0) -> datetime:
    # Hora local de la tienda sin zona: así la guarda y la devuelve SQLite.
    return datetime(dia.year, dia.month, dia.day, hora, minuto)


class ReasignacionSeguraTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.s = Session(engine)
        self.s.add_all([
            Empleada(codigo=ORIGEN, nombre_completo="Evelyn Ruiz", activo=True),
            Empleada(codigo=DESTINO, nombre_completo="Nayeli Herrera", activo=True),
            Empleada(codigo=INACTIVA, nombre_completo="Ya No Trabaja", activo=False),
        ])
        self.s.commit()

    def tearDown(self) -> None:
        self.s.close()

    # ── utilidades ────────────────────────────────────────────────────
    def _venta(self, *, cuando=None, comisiones=4, code=ORIGEN) -> LibretaVenta:
        venta = LibretaVenta(
            employee_code=code, employee_name="Evelyn Ruiz", tipo="venta", piezas=2,
            comisiones=comisiones, monto_total=Decimal("1180.00"), monto_neto=Decimal("1180.00"),
            detalle=[{"nombre": "Pants 3pz", "cantidad": 2, "precio": "590.00"}],
            created_at=cuando or _local(DIA, 11, 38),
        )
        self.s.add(venta)
        self.s.commit()
        return venta

    def _pagar(self, code: str, *, cuando: datetime) -> None:
        """Pago ya registrado (como lo deja `registrar_pago_con_monto`)."""
        self.s.add(EmpleadaPago(
            employee_code=code, employee_name=code, fecha=cuando.date(), desde=cuando.date(),
            hasta=cuando.date(), comisiones=10, sueldo_base=Decimal("1300.00"),
            tarifa_comision=Decimal("2.00"), monto_comisiones=Decimal("20.00"), faltas=0,
            descuento_faltas=Decimal("0.00"), total=Decimal("1320.00"), creado_por="VEND-1",
            created_at=cuando,
        ))
        fila = self.s.get(EmpleadaHorario, code)
        if fila is None:
            self.s.add(EmpleadaHorario(employee_code=code, fecha_ultimo_pago=cuando.date()))
        else:
            fila.fecha_ultimo_pago = cuando.date()
        self.s.commit()

    def _pendiente(self, code: str) -> int:
        return comisiones_desde_ultimo_pago(self.s, code, cargar_horario(self.s, code))

    def _auditoria(self) -> list[AuditoriaAusencias]:
        return list(self.s.scalars(
            select(AuditoriaAusencias).where(AuditoriaAusencias.operacion == "reasignar_venta")
        ))

    def _bloqueada(self, venta, code=DESTINO, *, actor="VEND-1", hoy=DIA, error=ReasignacionNoPermitida):
        with self.assertRaises(error) as ctx:
            reasignar_empleada(self.s, venta.id, code, None, actor=actor, hoy=hoy)
        self.s.rollback()
        self.s.refresh(venta)
        self.assertEqual(venta.employee_code, ORIGEN, "la venta no debió moverse")
        self.assertEqual(self._auditoria(), [], "nada que auditar si no se reasignó")
        return str(ctx.exception)

    # ── caso válido ───────────────────────────────────────────────────
    def test_reasignacion_valida_mueve_puntos_y_deja_auditoria(self) -> None:
        venta = self._venta(comisiones=4)
        self.assertEqual((self._pendiente(ORIGEN), self._pendiente(DESTINO)), (4, 0))

        out = reasignar_empleada(self.s, venta.id, "vend-5", "nombre del diálogo", actor="vend-1", hoy=DIA)

        self.assertIs(out, venta)
        self.assertEqual(venta.employee_code, DESTINO)
        self.assertEqual(venta.employee_name, "Nayeli Herrera")  # el del catálogo
        self.assertEqual((venta.comisiones, venta.monto_total, venta.created_at),
                         (4, Decimal("1180.00"), _local(DIA, 11, 38)))  # nada más cambia
        # Los puntos se mueven completos: ni se duplican ni se pierden.
        self.assertEqual((self._pendiente(ORIGEN), self._pendiente(DESTINO)), (0, 4))

        [aud] = self._auditoria()
        self.assertEqual(aud.actor, "VEND-1")
        self.assertEqual(aud.entidad, "libreta_venta")
        self.assertEqual(aud.entidad_id, venta.id)
        self.assertEqual(aud.employee_code, DESTINO)
        self.assertIsNotNone(aud.created_at)
        self.assertEqual(aud.antes["employee_code"], ORIGEN)
        self.assertEqual(aud.despues["employee_code"], DESTINO)
        self.assertEqual(aud.antes["comisiones"], 4)

    def test_origen_pagado_ayer_si_se_puede(self) -> None:
        self._pagar(ORIGEN, cuando=_local(DIA - timedelta(days=1), 18))
        venta = self._venta()
        reasignar_empleada(self.s, venta.id, DESTINO, actor="VEND-1", hoy=DIA)
        self.assertEqual(venta.employee_code, DESTINO)

    def test_origen_pagado_hoy_antes_de_la_venta_si_se_puede(self) -> None:
        self._pagar(ORIGEN, cuando=_local(DIA, 9, 13))
        venta = self._venta(cuando=_local(DIA, 11, 38))
        reasignar_empleada(self.s, venta.id, DESTINO, actor="VEND-1", hoy=DIA)
        self.assertEqual(venta.employee_code, DESTINO)

    # ── bloqueos ──────────────────────────────────────────────────────
    def test_venta_de_otro_dia_bloqueada(self) -> None:
        venta = self._venta(cuando=_local(DIA - timedelta(days=1), 17))
        self.assertIn("mismo día", self._bloqueada(venta))

    def test_venta_ya_pagada_a_la_original_bloqueada(self) -> None:
        venta = self._venta(cuando=_local(DIA, 11, 38))
        self._pagar(ORIGEN, cuando=_local(DIA, 19, 0))  # el pago ya incluyó la venta
        self.assertIn("ya se le pagó", self._bloqueada(venta))
        self.assertEqual(self._pendiente(DESTINO), 0)

    def test_destino_pagada_despues_de_la_venta_bloqueada(self) -> None:
        venta = self._venta(cuando=_local(DIA, 11, 38))
        self._pagar(DESTINO, cuando=_local(DIA, 19, 0))
        # Si se moviera, quedaría antes del corte de Nayeli: nadie la cobraría.
        self.assertIn("ya se le pagó después", self._bloqueada(venta))
        self.assertEqual(self._pendiente(ORIGEN), 4)

    def test_destino_inexistente_bloqueada(self) -> None:
        venta = self._venta()
        self.assertIn("No existe", self._bloqueada(venta, "VEND-99"))

    def test_destino_inactiva_bloqueada(self) -> None:
        venta = self._venta()
        self.assertIn("no está activa", self._bloqueada(venta, INACTIVA))

    def test_misma_empleada_bloqueada(self) -> None:
        venta = self._venta()
        self._bloqueada(venta, ORIGEN)

    def test_si_la_venta_cambio_de_empleada_al_esperar_el_candado_se_rechaza(self) -> None:
        """M2: se leyó «es de Evelyn» y se tomó SU candado; mientras se
        esperaba, otra reasignación la pasó a VEND-8. No se sigue con un
        candado que ya no es el de la dueña de la venta."""
        from sqlalchemy import update

        venta = self._venta()
        candados = []

        def otra_reasignacion_se_cuela(session, codes):
            candados.append(sorted(codes))
            session.execute(update(LibretaVenta).where(LibretaVenta.id == venta.id).values(employee_code="VEND-8"))

        with patch("pos_uniformes.services.calendario_empleadas_service.bloquear_empleadas",
                   side_effect=otra_reasignacion_se_cuela):
            with self.assertRaises(ReasignacionNoPermitida) as ctx:
                reasignar_empleada(self.s, venta.id, DESTINO, actor="VEND-1", hoy=DIA)
        self.assertIn("cambió de empleada", str(ctx.exception))
        self.assertEqual(candados, [[ORIGEN, DESTINO]])
        self.assertEqual(self._auditoria(), [])  # sin bitácora
        self.assertFalse(self.s.in_transaction() and (self.s.dirty or self.s.new))  # se hizo rollback

    def test_quien_no_es_el_dueno_no_puede(self) -> None:
        venta = self._venta()
        for actor in ("VEND-2", "", None, "ENCARGADO"):
            with self.subTest(actor=actor):
                self._bloqueada(venta, actor=actor, error=PermissionError)


if __name__ == "__main__":
    unittest.main()
