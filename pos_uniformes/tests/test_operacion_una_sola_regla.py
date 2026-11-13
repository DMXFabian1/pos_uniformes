"""«¿Cuenta como operación?» definido UNA vez (2026-11-12).

Daniel decidió que lo que compra una empleada con precio especial no cuenta
como operación, ni piezas, ni importe, ni comisión de nadie. Antes cada
pantalla lo decidía por su cuenta y el corte sí la contaba. Esta prueba de
tabla pasa la MISMA lista de filas por todos los agregadores y revisa que
operaciones y piezas salgan coherentes con la regla de `libreta_service`.

Ese mismo día Daniel decidió que un abono tampoco es operación («no cuentan
como operación»): no suma operación ni piezas en ninguna pantalla, pero su
DINERO sigue igual y un periodo con solo abonos sigue siendo movimiento.
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
#   cuentan como operación (TIPOS_OPERACION): 1, 3  → 2 ops, 7 piezas
#   (el abono, 4, ya no: Daniel, 2026-11-12, «no cuentan como operación»)
#   en el ranking (TIPOS_DE_VENTA, hoy el mismo valor): 1, 3 → 2 ops, 7 piezas
OPS, PIEZAS = 2, 7
OPS_RANKING, PIEZAS_RANKING = 2, 7


class ReglaTests(unittest.TestCase):
    def test_la_regla_fila_por_fila(self) -> None:
        f = {r.id: r for r in tabla()}
        self.assertTrue(ls.cuenta_como_operacion(f[1]))
        self.assertFalse(ls.cuenta_como_operacion(f[2]))
        self.assertTrue(ls.cuenta_como_operacion(f[3]))
        # El abono no es operación (Daniel, 2026-11-12).
        self.assertFalse(ls.cuenta_como_operacion(f[4]))
        self.assertFalse(ls.cuenta_como_operacion(f[ID_A_CUENTA]))
        self.assertFalse(ls.cuenta_como_operacion(f[4], ls.TIPOS_DE_VENTA))
        # Una sola definición: el alias del ranking es el mismo valor.
        self.assertEqual(ls.TIPOS_OPERACION, ("venta", "apartado"))
        self.assertEqual(ls.TIPOS_DE_VENTA, ls.TIPOS_OPERACION)
        self.assertEqual(rk.TIPOS_OPERACION_RANKING, ls.TIPOS_OPERACION)
        self.assertEqual(gh.TIPOS_QUE_CUENTAN, ls.TIPOS_OPERACION)
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
        # El importe no cambia con la regla del abono: 900 + 1200 + 300.
        fanny = next(e for e in r if e.employee_code == "VEND-4")
        self.assertEqual((fanny.operaciones, fanny.monto_total), (2, Decimal("2400.00")))

    def test_el_cambio_de_talla_no_suma_importe_por_empleada(self) -> None:
        """Revisión 2026-11-12: al separar el importe de la operación, una
        fila tipo="cambio" (diferencia que paga el cliente) se coló al «$
        vendidos» de la empleada. El importe suma solo venta, apartado y
        abono, como antes de la regla del abono."""
        filas = [_fila(1, "venta", 2, "500"), _fila(2, "cambio", 0, "150"), _fila(3, "abono", 0, "300")]
        (ana,) = ls.resumir_por_empleada(filas)
        self.assertEqual((ana.operaciones, ana.piezas), (1, 2))
        self.assertEqual(ana.monto_total, Decimal("800.00"))   # 500 + 300; el cambio no
        self.assertEqual(ls.TIPOS_CON_IMPORTE, ("venta", "apartado", "abono"))

    def test_resumir_por_dia(self) -> None:
        (dia,) = ls.resumir_por_dia(tabla())
        self.assertEqual((dia.operaciones, dia.piezas), (OPS, PIEZAS))
        # El dinero no cambia: las dos compras de empleada entraron como venta,
        # y el abono sigue en abonos y en el cajón.
        self.assertEqual(dia.monto_ventas, Decimal("1550.00"))
        self.assertEqual(dia.monto_abonos, Decimal("300.00"))
        self.assertEqual(dia.monto_en_caja, Decimal("1850.00"))

    def test_ranking(self) -> None:
        r = rk.calcular(tabla())
        self.assertEqual(sum(f.operaciones for f in r), OPS_RANKING)
        self.assertEqual(sum(f.piezas for f in r), PIEZAS_RANKING)
        self.assertEqual(sum(f.ventas for f in r), 1)
        self.assertEqual(sum(f.abonos for f in r), 1)
        self.assertEqual(sum(f.importe_abonos for f in r), Decimal("300.00"))
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


class TextosTests(unittest.TestCase):
    def test_texto_operaciones(self) -> None:
        self.assertEqual(ls.texto_operaciones(3), "3 operaciones")
        self.assertEqual(ls.texto_operaciones(1), "1 operación")
        self.assertEqual(ls.texto_operaciones(3, 2), "3 operaciones + 2 abonos")
        self.assertEqual(ls.texto_operaciones(3, 0, corto=True), "3 ops")
        self.assertEqual(ls.texto_operaciones(0, 1, corto=True), "0 ops + 1 abono")

    def test_mensaje_de_la_empleada(self) -> None:
        self.assertEqual(ls.mensaje_libreta_empleada(ls.totales_libreta([]), "hoy"),
                         "Aún no tienes movimientos hoy. ¡Tú puedes! 💪")
        t = ls.totales_libreta([_fila(1, "venta", 3, "900")])
        self.assertEqual(ls.mensaje_libreta_empleada(t, "hoy"), "Llevas 3 pieza(s) y 3 comision(es) hoy. ¡Bien! ✨")


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


class CorteConSoloLaCompraDeEmpleadaTests(unittest.TestCase):
    """Si lo único del periodo fue la compra de una empleada con precio
    especial, hay 0 operaciones pero su efectivo está en el cajón: las
    puertas del corte (automático, Telegram, encargado, celular) deben
    dejar pasar el corte (revisión, 2026-11-12)."""

    def setUp(self) -> None:
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
        self.s = Session(engine)
        self.addCleanup(self.s.close)
        f = tabla()[1]   # venta de empleada, $400 en efectivo
        self.s.add(LibretaVenta(
            id=f.id, employee_code=f.employee_code, employee_name=f.employee_name, tipo=f.tipo,
            piezas=f.piezas, comisiones=f.comisiones, monto_total=f.monto_total,
            descuento_empleada=True, privado=False, created_at=f.created_at,
        ))
        self.s.commit()
        self.ahora = datetime.combine(HOY, time(20, 0))

    def test_resumen_dice_que_hubo_movimiento(self) -> None:
        r = cc.resumir_periodo([tabla()[1]])
        self.assertEqual((r.operaciones, r.piezas), (0, 0))
        self.assertEqual(r.efectivo, Decimal("400.00"))
        self.assertTrue(r.hubo_movimiento)

    def test_periodo_vacio_no_tiene_movimiento(self) -> None:
        self.assertFalse(cc.resumir_periodo([]).hubo_movimiento)

    def test_estado_caja_y_corte_automatico(self) -> None:
        from pos_uniformes.services.horario_tienda_service import decidir_corte_automatico, momento_corte

        estado = cc.estado_caja(self.s, self.ahora)
        self.assertEqual(estado.resumen.operaciones, 0)
        self.assertEqual(estado.resumen.efectivo, Decimal("400.00"))
        self.assertTrue(estado.resumen.hubo_movimiento)
        decision = decidir_corte_automatico(momento_corte(HOY), None, estado.resumen.hubo_movimiento)
        self.assertTrue(decision.hacer, decision.motivo)

    def test_corte_remoto_no_dice_sin_corte(self) -> None:
        from pos_uniformes.services import corte_remoto_service as crs

        estado = cc.estado_caja(self.s, self.ahora)

        class _Paso(Exception):
            pass

        with patch("pos_uniformes.services.corte_caja_service.estado_caja", return_value=estado), patch(
            "pos_uniformes.services.corte_caja_service.pagos_que_tocan_hoy", return_value=[]
        ), patch(
            "pos_uniformes.services.corte_caja_service.ultimo_corte", return_value=None
        ), patch(
            "pos_uniformes.services.corte_caja_service.cerrar_corte_automatico", side_effect=_Paso
        ) as cerrar:
            try:
                r = crs.hacer_corte_y_avisar(self.s, creado_por="VEND-1", ahora=self.ahora, sin_tarjeta=False)
            except _Paso:
                r = None
        self.assertIsNone(r, getattr(r, "mensaje", r))
        cerrar.assert_called_once()


class SoloAbonosTests(unittest.TestCase):
    """Un periodo con solo abonos: 0 operaciones y 0 piezas (Daniel,
    2026-11-12: «no cuentan como operación»), pero entró dinero. El resumen
    no dice «ninguna venta» y las puertas del corte lo dejan pasar."""

    def setUp(self) -> None:
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
        self.s = Session(engine)
        self.addCleanup(self.s.close)
        f = tabla()[3]   # abono de $300 en efectivo
        self.s.add(LibretaVenta(
            id=f.id, employee_code=f.employee_code, employee_name=f.employee_name, tipo="abono",
            piezas=0, comisiones=0, monto_total=f.monto_total,
            descuento_empleada=False, privado=False, created_at=f.created_at,
        ))
        self.s.commit()
        self.ahora = datetime.combine(HOY, time(20, 0))

    def test_resumir_periodo(self) -> None:
        r = cc.resumir_periodo([tabla()[3]])
        self.assertEqual((r.operaciones, r.piezas), (0, 0))
        # El dinero, igual que antes de la regla.
        self.assertEqual((r.abonos, r.efectivo, r.ventas), (Decimal("300.00"), Decimal("300.00"), Decimal("0.00")))
        self.assertTrue(r.hubo_movimiento)

    def test_resumen_de_telegram_no_dice_ninguna_venta(self) -> None:
        from pos_uniformes.services import resumen_diario_service as rd

        r = cc.resumir_periodo([tabla()[3]])
        d = rd.DatosResumen(fecha=HOY, operaciones=r.operaciones, piezas=r.piezas, ventas=r.ventas,
                            abonos=r.abonos, efectivo=r.efectivo)
        self.assertTrue(d.hubo_movimiento)
        texto = rd.formatear(d)
        self.assertNotIn("Sin operaciones", texto)
        self.assertIn("Abonos: $300.00", texto)
        self.assertIn("0 operaciones · 0 piezas", texto)
        hoy = rd.texto_hoy(d, ahora=datetime.combine(HOY, time(12, 0)))
        self.assertNotIn("ninguna venta", hoy.lower())
        self.assertIn("Entró: $300.00", hoy)

    def test_textos_del_corte_nombran_los_abonos(self) -> None:
        """Revisión 2026-11-12: «Venta efectivo: $300.00 (0 ops)» confundía;
        el efectivo de los abonos se explica con «+ N abonos»."""
        from pos_uniformes.services import corte_remoto_service as crs
        from pos_uniformes.ui.dialogs.corte_caja_dialog import texto_estado_caja

        estado = cc.estado_caja(self.s, self.ahora)
        self.assertEqual(estado.resumen.num_abonos, 1)
        self.assertIn("VENTA EN EFECTIVO: $300.00   (0 operaciones + 1 abono)", texto_estado_caja(estado))
        with patch("pos_uniformes.services.corte_caja_service.estado_caja", return_value=estado), patch(
            "pos_uniformes.services.corte_caja_service.pagos_que_tocan_hoy", return_value=[]
        ):
            self.assertIn("Venta efectivo: $300.00 (0 ops + 1 abono)", crs.texto_estado_actual(self.s, self.ahora))
            self.assertIn("Venta en efectivo: $300.00 (0 ops + 1 abono)", crs.texto_propuesta_corte(self.s, self.ahora))

    def test_libreta_de_la_empleada_con_solo_abonos(self) -> None:
        t = ls.totales_libreta([tabla()[3]])
        self.assertEqual((t.operaciones, t.abonos), (0, 1))
        self.assertEqual(ls.mensaje_libreta_empleada(t, "hoy"), "Llevas 1 abono(s) cobrado(s) hoy. ¡Tú puedes! 💪")
        self.assertEqual(ls.texto_operaciones(t.operaciones, t.abonos), "0 operaciones + 1 abono")

    def test_gafete_no_cuenta_el_abono(self) -> None:
        self.assertTrue(gh.resumen_de_hoy(self.s, hoy=HOY).vacio)

    def test_estado_caja_y_corte_automatico(self) -> None:
        from pos_uniformes.services.horario_tienda_service import decidir_corte_automatico, momento_corte

        estado = cc.estado_caja(self.s, self.ahora)
        self.assertEqual(estado.resumen.operaciones, 0)
        self.assertEqual(estado.resumen.abonos, Decimal("300.00"))
        self.assertEqual(estado.resumen.efectivo, Decimal("300.00"))
        self.assertTrue(estado.resumen.hubo_movimiento)
        decision = decidir_corte_automatico(momento_corte(HOY), None, estado.resumen.hubo_movimiento)
        self.assertTrue(decision.hacer, decision.motivo)

    def test_propuesta_de_corte_cierra_sola(self) -> None:
        from pos_uniformes.services import corte_propuesta_service as cp

        estado = cc.estado_caja(self.s, self.ahora)
        p = cp.Propuesta(fecha=HOY, momento=datetime.combine(HOY, time(17, 30)), recordado=True)
        self.assertTrue(cp.toca_cerrar_solo(
            p, hoy=HOY, minutos_tras_cierre=60, hubo_corte_despues=False,
            hubo_movimiento=estado.resumen.hubo_movimiento,
        ))

    def test_corte_remoto_no_dice_sin_corte(self) -> None:
        from pos_uniformes.services import corte_remoto_service as crs

        estado = cc.estado_caja(self.s, self.ahora)

        class _Paso(Exception):
            pass

        with patch("pos_uniformes.services.corte_caja_service.estado_caja", return_value=estado), patch(
            "pos_uniformes.services.corte_caja_service.pagos_que_tocan_hoy", return_value=[]
        ), patch(
            "pos_uniformes.services.corte_caja_service.ultimo_corte", return_value=None
        ), patch(
            "pos_uniformes.services.corte_caja_service.cerrar_corte_automatico", side_effect=_Paso
        ) as cerrar:
            try:
                r = crs.hacer_corte_y_avisar(self.s, creado_por="VEND-1", ahora=self.ahora, sin_tarjeta=False)
            except _Paso:
                r = None
        self.assertIsNone(r, getattr(r, "mensaje", r))
        cerrar.assert_called_once()


if __name__ == "__main__":
    unittest.main()
