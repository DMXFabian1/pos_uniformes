"""Dos ventas unidas cuentan como UNA operación en todo lugar que cuenta
operaciones (Daniel, 2026-11-13), y NADA más cambia.

La misma tabla pasa con y sin unión por cada contador: corte (y su ticket),
Libreta del kiosko (dueño y empleada), resumen por empleada y por día,
ranking, Resumen del POS, Analítica (operaciones, ventas, ticket promedio),
gafete, actividad de la empleada (tickets), Telegram (resumen y corte),
compras del cliente para membresías, detalle de nómina y el export. En
cada uno se revisa también que el dinero, las piezas y las comisiones sean
los mismos con y sin unión.
"""

from __future__ import annotations

import copy
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
from pos_uniformes.services import analitica_tablero_service as at
from pos_uniformes.services import corte_caja_service as cc
from pos_uniformes.services import gafete_hoy_service as gh
from pos_uniformes.services import libreta_service as ls
from pos_uniformes.services import ranking_libreta_service as rk
from pos_uniformes.services import resumen_pos_service as rp

HOY = date(2026, 11, 13)


def _fila(id_, tipo, piezas, monto, *, hora, minuto=0, grupo=None, code="VEND-4", cliente_id=None):
    return SimpleNamespace(
        id=id_, employee_code=code, employee_name="Fanny Ortiz" if code == "VEND-4" else "Stayce Chavarria",
        tipo=tipo, piezas=piezas, comisiones=0 if tipo == "abono" else piezas,
        monto_total=Decimal(monto), monto_neto=Decimal(monto), monto_monedero=Decimal("0"),
        pago_tarjeta=False, descuento_empleada=False, privado=False, cliente_id=cliente_id,
        created_at=datetime.combine(HOY, time(hora, minuto)), operacion_grupo_id=grupo, detalle=[],
        cliente=None, origen=None, operacion_uuid=None,
    )


def tabla(unidas: bool) -> list:
    """#1639 y #1640: la misma clienta (Fanny), ticket impreso y luego otra
    cosa. #1641: otra venta de Fanny. #1642: un apartado. #1643: un abono.
    #1644: una venta de Stayce."""
    g = 1639 if unidas else None
    return [
        _fila(1639, "venta", 2, "500", hora=10, grupo=g, cliente_id=7),
        _fila(1640, "venta", 1, "150", hora=10, minuto=7, grupo=g, cliente_id=7),
        _fila(1641, "venta", 3, "900", hora=12),
        _fila(1642, "apartado", 4, "1200", hora=13),
        _fila(1643, "abono", 0, "300", hora=14),
        _fila(1644, "venta", 1, "200", hora=15, code="VEND-5"),
    ]


class PurosTests(unittest.TestCase):
    """Los contadores puros, con y sin unión."""

    def test_contar_operaciones(self) -> None:
        self.assertEqual(ls.contar_operaciones(tabla(False)), 5)
        self.assertEqual(ls.contar_operaciones(tabla(True)), 4)
        self.assertEqual(ls.contar_operaciones(tabla(True), ("venta",)), 3)

    def test_libreta_del_kiosko(self) -> None:
        sin, con = ls.totales_libreta(tabla(False)), ls.totales_libreta(tabla(True))
        self.assertEqual((sin.operaciones, sin.ventas, sin.apartados), (5, 4, 1))
        self.assertEqual((con.operaciones, con.ventas, con.apartados), (4, 3, 1))
        # Lo demás no cambia.
        self.assertEqual((con.piezas, con.comisiones, con.abonos), (sin.piezas, sin.comisiones, sin.abonos))
        self.assertEqual(len(con.filas_dinero), len(sin.filas_dinero))
        self.assertEqual(ls.texto_operaciones(con.operaciones, con.abonos), "4 operaciones + 1 abono")

    def test_libreta_de_la_empleada(self) -> None:
        """Sus «VENTAS» en el kiosko: el grupo es 1; sus piezas, todas."""
        fanny = [r for r in tabla(True) if r.employee_code == "VEND-4"]
        t = ls.totales_libreta(fanny)
        self.assertEqual((t.ventas, t.piezas, t.comisiones), (2, 10, 10))
        self.assertEqual(ls.totales_libreta([r for r in tabla(False) if r.employee_code == "VEND-4"]).ventas, 3)

    def test_resumen_por_empleada(self) -> None:
        sin = {e.employee_code: e for e in ls.resumir_por_empleada(tabla(False))}
        con = {e.employee_code: e for e in ls.resumir_por_empleada(tabla(True))}
        self.assertEqual((sin["VEND-4"].operaciones, con["VEND-4"].operaciones), (4, 3))
        self.assertEqual(con["VEND-5"].operaciones, 1)
        for c in ("VEND-4", "VEND-5"):
            self.assertEqual(
                (con[c].piezas, con[c].comisiones, con[c].monto_total),
                (sin[c].piezas, sin[c].comisiones, sin[c].monto_total),
            )

    def test_resumen_por_dia(self) -> None:
        (sin,), (con,) = ls.resumir_por_dia(tabla(False)), ls.resumir_por_dia(tabla(True))
        self.assertEqual((sin.operaciones, con.operaciones), (5, 4))
        self.assertEqual(
            (con.piezas, con.monto_ventas, con.monto_en_caja, con.monto_abonos, con.monto_apartados),
            (sin.piezas, sin.monto_ventas, sin.monto_en_caja, sin.monto_abonos, sin.monto_apartados),
        )

    def test_corte(self) -> None:
        sin, con = cc.resumir_periodo(tabla(False)), cc.resumir_periodo(tabla(True))
        self.assertEqual((sin.operaciones, con.operaciones), (5, 4))
        self.assertEqual(
            (con.piezas, con.ventas, con.efectivo, con.abonos, con.apartados, con.movimientos),
            (sin.piezas, sin.ventas, sin.efectivo, sin.abonos, sin.apartados, sin.movimientos),
        )

    def test_ranking(self) -> None:
        sin = {f.employee_code: f for f in rk.calcular(tabla(False))}
        con = {f.employee_code: f for f in rk.calcular(tabla(True))}
        self.assertEqual((sin["VEND-4"].operaciones, sin["VEND-4"].ventas), (4, 3))
        self.assertEqual((con["VEND-4"].operaciones, con["VEND-4"].ventas), (3, 2))
        self.assertEqual(
            (con["VEND-4"].puntos, con["VEND-4"].piezas, con["VEND-4"].importe_ventas, con["VEND-4"].posicion),
            (sin["VEND-4"].puntos, sin["VEND-4"].piezas, sin["VEND-4"].importe_ventas, sin["VEND-4"].posicion),
        )

    def test_resumen_del_pos(self) -> None:
        sin, con = rp.cifras_periodo(tabla(False)), rp.cifras_periodo(tabla(True))
        self.assertEqual((sin.operaciones, sin.ventas), (5, 4))
        self.assertEqual((con.operaciones, con.ventas, con.apartados), (4, 3, 1))
        self.assertEqual((con.piezas, con.cobrado), (sin.piezas, sin.cobrado))

    def test_analitica(self) -> None:
        sin, con = at.cifras(tabla(False)), at.cifras(tabla(True))
        self.assertEqual((sin.operaciones, sin.ventas), (5, 4))
        self.assertEqual((con.operaciones, con.ventas), (4, 3))
        self.assertEqual((con.importe_ventas, con.piezas, con.cobrado), (sin.importe_ventas, sin.piezas, sin.cobrado))
        # Ticket promedio: lo que dejó cada clienta, no cada papel.
        self.assertEqual(sin.ticket_promedio, (Decimal("1750") / 4).quantize(Decimal("0.01")))
        self.assertEqual(con.ticket_promedio, (Decimal("1750") / 3).quantize(Decimal("0.01")))

    def test_actividad_de_la_empleada(self) -> None:
        from pos_uniformes.services.employee_activity_service import build_employee_activity_snapshot

        emp = SimpleNamespace(id=4, codigo="VEND-4", nombre_completo="Fanny Ortiz", activo=True)

        def snap(unidas):
            ops = [r for r in tabla(unidas) if r.employee_code == "VEND-4"]
            return build_employee_activity_snapshot(
                emp, pin_ready=True, qr_ready=True, card_ready=True, operaciones=ops,
                reference_date=HOY, history_days=1, summary_days=1,
                visible_name_builder=lambda *a, **k: "Fanny",
            )

        sin, con = snap(False), snap(True)
        self.assertEqual((sin.day_rows[0].tickets, con.day_rows[0].tickets), (4, 3))
        self.assertEqual(con.day_rows[0].pieces, sin.day_rows[0].pieces)
        self.assertEqual(con.day_rows[0].amount, sin.day_rows[0].amount)

    def test_resumen_de_telegram(self) -> None:
        from pos_uniformes.services import resumen_diario_service as rd

        r = cc.resumir_periodo(tabla(True))
        d = rd.DatosResumen(fecha=HOY, operaciones=r.operaciones, piezas=r.piezas, ventas=r.ventas,
                            abonos=r.abonos, efectivo=r.efectivo)
        self.assertIn("4 operaciones · 11 piezas", rd.formatear(d))

    def test_export(self) -> None:
        from pos_uniformes.services.exportacion_libreta_service import filas_ventas

        filas = filas_ventas(tabla(True))
        self.assertEqual([f["unida_con"] for f in filas[:3]], [1639, 1639, ""])
        self.assertEqual(len({f["operacion"] for f in filas if f["cuenta_como_operacion"]}), 4)

    def test_afluencia_conversion_por_hora(self) -> None:
        """«De cada 100 que entran, cuántos compran»: la clienta de dos
        ventas unidas compró una vez (en la hora de la primera)."""
        from pos_uniformes.services.afluencia_service import contar_por_hora

        def por_hora(unidas):
            return contar_por_hora([
                (r.created_at, ls.clave_operacion(r)) for r in tabla(unidas) if r.tipo in ("venta", "apartado")
            ])

        h10 = datetime.combine(HOY, time(10))
        self.assertEqual(por_hora(False)[h10], 2)
        self.assertEqual(por_hora(True)[h10], 1)
        self.assertEqual(sum(por_hora(True).values()), 4)

    def test_una_fila_sin_id_cuenta_sola(self) -> None:
        """Lo de la cola sin red no trae id: cada una es su propia operación."""
        filas = [SimpleNamespace(tipo="venta"), SimpleNamespace(tipo="venta")]
        self.assertEqual(ls.contar_operaciones(filas), 2)


class SqlTests(unittest.TestCase):
    """Los contadores que cuentan en SQL (gafete, membresías, nómina) y el
    corte con su ticket, en SQLite."""

    def setUp(self) -> None:
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
        self.s = Session(engine)
        self.addCleanup(self.s.close)
        for f in tabla(False):
            self.s.add(LibretaVenta(
                id=f.id, employee_code=f.employee_code, employee_name=f.employee_name, tipo=f.tipo,
                piezas=f.piezas, comisiones=f.comisiones, monto_total=f.monto_total, monto_neto=f.monto_neto,
                descuento_empleada=False, privado=False, created_at=f.created_at, cliente_id=f.cliente_id,
                detalle=[],
            ))
        self.s.commit()

    def unir(self) -> None:
        from pos_uniformes.services.libreta_unir_service import unir

        unir(self.s, 1639, 1640, actor="VEND-1")
        self.s.commit()

    def test_sql_igual_a_python(self) -> None:
        def cuenta():
            return self.s.scalar(select(ls.contar_operaciones_sql()).where(ls.predicado_operacion()))

        self.assertEqual(cuenta(), 5)
        self.unir()
        self.assertEqual(cuenta(), 4)
        filas = list(self.s.scalars(select(LibretaVenta)))
        self.assertEqual(ls.contar_operaciones(filas), 4)

    def test_afluencia(self) -> None:
        from pos_uniformes.services.afluencia_service import ventas_por_hora

        desde, hasta = datetime.combine(HOY, time.min), datetime.combine(HOY, time.max)
        self.assertEqual(sum(ventas_por_hora(self.s, desde=desde, hasta=hasta).values()), 5)
        self.unir()
        self.assertEqual(sum(ventas_por_hora(self.s, desde=desde, hasta=hasta).values()), 4)

    def test_gafete(self) -> None:
        with patch("pos_uniformes.services.horario_tienda_service.hora_apertura", return_value=time(9, 0)):
            sin = dict(gh.resumen_de_hoy(self.s, hoy=HOY).por_empleada)
            self.unir()
            con = dict(gh.resumen_de_hoy(self.s, hoy=HOY).por_empleada)
        self.assertEqual((sum(sin.values()), sum(con.values())), (5, 4))

    def test_compras_del_cliente_para_membresias(self) -> None:
        from pos_uniformes.services import telegram_membresias_service as tm

        n, monto, _ = tm._sumar(self.s, 7, "venta")
        self.assertEqual((n, monto), (2, Decimal("650")))
        self.unir()
        n, monto, _ = tm._sumar(self.s, 7, "venta")
        self.assertEqual((n, monto), (1, Decimal("650")))

    def test_detalle_de_nomina(self) -> None:
        from pos_uniformes.services import nomina_service as ns

        def linea():
            with patch.object(ns, "fecha_proximo_pago", return_value=HOY), \
                 patch.object(ns, "cargar_horario", return_value=None):
                return ns.detalle_del_dia(self.s, "VEND-4", HOY, hoy=HOY)[0]

        # Esta línea siempre contó todas las filas de Fanny del día (3 ventas,
        # el apartado y el abono): 5; con dos unidas, 4. Comisiones, igual.
        sin = linea()
        self.unir()
        con = linea()
        self.assertEqual(sin, "⭐ 10 comisiones en 5 ventas")
        self.assertEqual(con, "⭐ 10 comisiones en 4 ventas")

    def test_corte_y_su_ticket(self) -> None:
        from pos_uniformes.ui.dialogs.corte_caja_dialog import texto_estado_caja

        ahora = datetime.combine(HOY, time(20, 0))
        sin = cc.estado_caja(self.s, ahora)
        self.unir()
        con = cc.estado_caja(self.s, ahora)
        self.assertEqual((sin.resumen.operaciones, con.resumen.operaciones), (5, 4))
        self.assertEqual((con.esperado, con.resumen.piezas), (sin.esperado, sin.resumen.piezas))
        self.assertIn("(4 operaciones + 1 abono)", texto_estado_caja(con))

    def test_corte_remoto_de_telegram(self) -> None:
        from pos_uniformes.services import corte_remoto_service as crs

        ahora = datetime.combine(HOY, time(20, 0))
        self.unir()
        estado = cc.estado_caja(self.s, ahora)
        with patch("pos_uniformes.services.corte_caja_service.estado_caja", return_value=estado), patch(
            "pos_uniformes.services.corte_caja_service.pagos_que_tocan_hoy", return_value=[]
        ):
            self.assertIn("(4 ops + 1 abono)", crs.texto_estado_actual(self.s, ahora))


if __name__ == "__main__":
    unittest.main()
