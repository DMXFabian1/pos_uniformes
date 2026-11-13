"""«¿Cuenta como operación?» definido UNA vez (2026-11-12).

Daniel decidió que lo que compra una empleada con precio especial no cuenta
como operación, ni piezas, ni importe, ni comisión de nadie. Antes cada
pantalla lo decidía por su cuenta y el corte sí la contaba. Esta prueba de
tabla pasa la MISMA lista de filas por todos los agregadores y revisa que
operaciones y piezas salgan coherentes con la regla de `libreta_service`.
"""

from __future__ import annotations

import os
import unittest
from datetime import date, datetime, time
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import LibretaVenta
from pos_uniformes.services import corte_caja_service as cc
from pos_uniformes.services import gafete_hoy_service as gh
from pos_uniformes.services import libreta_service as ls
from pos_uniformes.services import ranking_libreta_service as rk

HOY = date(2026, 11, 12)
ID_A_CUENTA = 5


def _fila(id_, tipo, piezas, monto, *, empleada=False, comisiones=None, tarjeta=False, code="VEND-4", hora=10):
    return SimpleNamespace(
        id=id_,
        employee_code=code,
        employee_name="Fanny Ortiz" if code == "VEND-4" else "Stayce Chavarria",
        tipo=tipo,
        piezas=piezas,
        comisiones=(0 if empleada or tipo == "abono" else piezas) if comisiones is None else comisiones,
        monto_total=Decimal(monto),
        monto_neto=Decimal(monto),
        monto_monedero=Decimal("0"),
        pago_tarjeta=tarjeta,
        descuento_empleada=empleada,
        privado=False,
        created_at=datetime.combine(HOY, time(hora, 0)),
    )


def tabla():
    """Venta normal, venta de empleada (precio especial), apartado, abono y
    compra a cuenta (que también es compra de empleada con precio especial)."""
    return [
        _fila(1, "venta", 3, "900", hora=10),                                  # venta normal
        _fila(2, "venta", 2, "400", empleada=True, code="VEND-5", hora=11),   # compra de empleada (paga en caja)
        _fila(3, "apartado", 4, "1200", hora=12),                              # apartado
        _fila(4, "abono", 0, "300", hora=13),                                  # abono
        _fila(ID_A_CUENTA, "venta", 1, "250", empleada=True, code="VEND-5", hora=14),  # compra a cuenta
    ]


# Lo que dice la regla, a mano, para la tabla:
#   cuentan como operación (TIPOS_OPERACION): 1, 3, 4  → 3 ops, 7 piezas
#   en el ranking (TIPOS_DE_VENTA):           1, 3     → 2 ops, 7 piezas
OPS, PIEZAS = 3, 7
OPS_RANKING, PIEZAS_RANKING = 2, 7


class ReglaTests(unittest.TestCase):
    def test_la_regla_fila_por_fila(self) -> None:
        f = {r.id: r for r in tabla()}
        self.assertTrue(ls.cuenta_como_operacion(f[1]))
        self.assertFalse(ls.cuenta_como_operacion(f[2]))
        self.assertTrue(ls.cuenta_como_operacion(f[3]))
        self.assertTrue(ls.cuenta_como_operacion(f[4]))
        self.assertFalse(ls.cuenta_como_operacion(f[ID_A_CUENTA]))
        # El ranking pide menos tipos: el abono no es venta.
        self.assertFalse(ls.cuenta_como_operacion(f[4], ls.TIPOS_DE_VENTA))
        # Un tipo que no es de la Libreta (p. ej. un retiro) no es operación.
        self.assertFalse(ls.cuenta_como_operacion(SimpleNamespace(tipo="retiro")))

    def test_comision_de_la_compra_de_empleada_es_cero(self) -> None:
        items = [{"nombre": "Pants 3pz", "cantidad": 2}]
        self.assertEqual(ls.comisiones_de_operacion(items, None, descuento_empleada=True), 0)


class AgregadoresTests(unittest.TestCase):
    def test_resumir_por_empleada(self) -> None:
        r = ls.resumir_por_empleada(tabla())
        self.assertEqual(sum(e.operaciones for e in r), OPS)
        self.assertEqual(sum(e.piezas for e in r), PIEZAS)
        stayce = next(e for e in r if e.employee_code == "VEND-5")
        self.assertEqual((stayce.operaciones, stayce.piezas, stayce.monto_total, stayce.comisiones), (0, 0, Decimal("0"), 0))

    def test_resumir_por_dia(self) -> None:
        (dia,) = ls.resumir_por_dia(tabla())
        self.assertEqual((dia.operaciones, dia.piezas), (OPS, PIEZAS))
        # El dinero no cambia: las dos compras de empleada entraron como venta.
        self.assertEqual(dia.monto_ventas, Decimal("1550.00"))

    def test_ranking(self) -> None:
        r = rk.calcular(tabla())
        self.assertEqual(sum(f.operaciones for f in r), OPS_RANKING)
        self.assertEqual(sum(f.piezas for f in r), PIEZAS_RANKING)
        self.assertEqual(sum(f.ventas for f in r), 1)
        self.assertEqual(sum(f.abonos for f in r), 1)
        stayce = next(f for f in r if f.employee_code == "VEND-5")
        self.assertEqual((stayce.operaciones, stayce.piezas, stayce.importe_ventas), (0, 0, Decimal("0")))

    def test_totales_de_la_libreta_del_kiosko(self) -> None:
        t = ls.totales_libreta(tabla(), {ID_A_CUENTA: "por_autorizar"})
        self.assertEqual((t.operaciones, t.piezas), (OPS, PIEZAS))
        self.assertEqual((t.ventas, t.apartados), (1, 1))
        self.assertEqual(t.comisiones, 3 + 4)
        # El dinero quita solo la compra a cuenta (no entró nada).
        self.assertEqual([r.id for r in t.filas_dinero], [1, 2, 3, 4])

    def test_totales_de_la_libreta_sin_compras_a_cuenta(self) -> None:
        t = ls.totales_libreta(tabla(), None)
        self.assertEqual(len(t.filas_dinero), 5)

    def test_apartado_de_empleada_no_cuenta_como_apartado(self) -> None:
        """Antes el kiosko contaba los apartados sin mirar la regla."""
        filas = [_fila(9, "apartado", 2, "500", empleada=True)]
        t = ls.totales_libreta(filas)
        self.assertEqual((t.operaciones, t.piezas, t.apartados), (0, 0, 0))

    def test_corte_resumir_periodo(self) -> None:
        """Operaciones y piezas siguen la regla; el DINERO del corte no
        cambia (la compra de empleada pagada en caja sí entró)."""
        with patch(
            "pos_uniformes.services.compra_a_cuenta_service.estados_en_libreta",
            return_value={ID_A_CUENTA: "por_autorizar"},
        ):
            filas = cc.sin_compras_a_cuenta(None, tabla())
        r = cc.resumir_periodo(filas)
        self.assertEqual((r.operaciones, r.piezas), (OPS, PIEZAS))
        self.assertEqual(r.ventas, Decimal("1300.00"))      # 900 + 400 (la de empleada sí entró)
        self.assertEqual(r.abonos, Decimal("300.00"))
        self.assertEqual(r.apartados, Decimal("1200.00"))
        self.assertEqual(r.efectivo, Decimal("1600.00"))    # ventas + abonos en efectivo


class GafeteYSqlTests(unittest.TestCase):
    """La versión SQL (`predicado_operacion`) dice lo mismo que la de Python."""

    def setUp(self) -> None:
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
        self.s = Session(engine)
        self.addCleanup(self.s.close)
        for f in tabla():
            self.s.add(LibretaVenta(
                id=f.id, employee_code=f.employee_code, employee_name=f.employee_name, tipo=f.tipo,
                piezas=f.piezas, comisiones=f.comisiones, monto_total=f.monto_total,
                descuento_empleada=f.descuento_empleada, privado=False, created_at=f.created_at,
            ))
        self.s.commit()

    def test_predicado_sql_igual_a_la_regla(self) -> None:
        for tipos in (ls.TIPOS_OPERACION, ls.TIPOS_DE_VENTA):
            ids_sql = set(self.s.scalars(select(LibretaVenta.id).where(ls.predicado_operacion(tipos))))
            ids_py = {f.id for f in tabla() if ls.cuenta_como_operacion(f, tipos)}
            self.assertEqual(ids_sql, ids_py, tipos)

    def test_gafete(self) -> None:
        r = gh.resumen_de_hoy(self.s, hoy=HOY)
        self.assertEqual(sum(n for _, n in r.por_empleada), OPS)
        self.assertEqual([nombre for nombre, _ in r.por_empleada], ["Fanny"])


class ResumenDiarioTests(unittest.TestCase):
    def test_solo_la_compra_de_empleada_no_esconde_el_dinero(self) -> None:
        """Si en el periodo solo hubo la compra de una empleada, hay 0
        operaciones pero su efectivo sí entró: el resumen no dice «ninguna
        venta» (2026-11-12)."""
        from pos_uniformes.services import resumen_diario_service as rd

        r = cc.resumir_periodo([tabla()[1]])
        d = rd.DatosResumen(fecha=HOY, operaciones=r.operaciones, piezas=r.piezas,
                            ventas=r.ventas, efectivo=r.efectivo)
        self.assertEqual(d.operaciones, 0)
        self.assertTrue(d.hubo_movimiento)
        self.assertIn("Efectivo: $400.00", rd.formatear(d))
        self.assertIn("Entró: $400.00", rd.texto_hoy(d, ahora=datetime.combine(HOY, time(12, 0))))

    def test_sin_nada_sigue_diciendo_ninguna_venta(self) -> None:
        from pos_uniformes.services import resumen_diario_service as rd

        d = rd.DatosResumen(fecha=HOY)
        self.assertFalse(d.hubo_movimiento)
        self.assertIn("Sin operaciones", rd.formatear(d))


class LibretaOfflineTests(unittest.TestCase):
    def test_filas_offline_traen_descuento_empleada(self) -> None:
        from pos_uniformes.ui.quote_satellite_window import QuoteSatelliteWindow

        entrada = {
            "created_at": datetime.combine(HOY, time(10, 0)).isoformat(),
            "employee_code": "VEND-5", "employee_name": "Stayce", "tipo": "venta",
            "items": [{"nombre": "Playera", "cantidad": 1}], "monto_total": "200",
            "descuento_empleada": True,
        }
        with patch("pos_uniformes.services.libreta_local_queue_service.pendientes", return_value=[entrada]):
            (fila,) = QuoteSatelliteWindow._libreta_rows_locales(
                datetime.combine(HOY, time.min), datetime.combine(HOY, time.max), None
            )
        self.assertTrue(fila.descuento_empleada)
        self.assertFalse(ls.cuenta_como_operacion(fila))
        self.assertEqual(fila.comisiones, 0)


if __name__ == "__main__":
    unittest.main()
