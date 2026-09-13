"""Revisar = decidir qué pedir: ventas por talla, ritmo, sugerencia y memoria del pedido."""

from __future__ import annotations

import unittest
from datetime import date, datetime, timedelta

from sqlalchemy import create_engine, select

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import ConteoInventario, DemandaNoAtendida, LibretaVenta, Variante
from pos_uniformes.services import conteo_jornada_service as jn
from pos_uniformes.services import revision_service as rv
from pos_uniformes.services.conteo_service import ConteoInput, registrar_conteos_lote
from pos_uniformes.tests.test_conteo_jornada_service import _seed
from sqlalchemy.orm import Session

HOY = date(2026, 9, 13)


def _dt(d: date, hora: int = 12) -> datetime:
    return datetime(d.year, d.month, d.day, hora)


class SugerirTests(unittest.TestCase):
    def test_pide_lo_que_falta_para_cuatro_semanas(self) -> None:
        # 14 vendidas en 14 días = 7/semana; 4 semanas = 28; hay 10 → pedir 18
        sugerido, ritmo, cubiertas, estado = rv.sugerir(conto=10, vendidas=14, dias_observados=14, pidieron=0)
        self.assertEqual((sugerido, ritmo, cubiertas, estado), (18, 7.0, 1.4, rv.PEDIR))

    def test_bien_cuando_alcanza(self) -> None:
        sugerido, _, cubiertas, estado = rv.sugerir(conto=40, vendidas=14, dias_observados=14, pidieron=0)
        self.assertEqual((sugerido, estado), (0, rv.BIEN))
        self.assertGreaterEqual(cubiertas, 4)

    def test_urgente_si_no_hay_y_la_piden(self) -> None:
        sugerido, _, _, estado = rv.sugerir(conto=0, vendidas=0, dias_observados=20, pidieron=3)
        self.assertEqual(estado, rv.URGENTE)
        self.assertGreater(sugerido, 0)

    def test_lo_que_pidieron_y_no_habia_cuenta_como_venta(self) -> None:
        con, *_ = rv.sugerir(conto=0, vendidas=4, dias_observados=28, pidieron=0)
        con_demanda, *_ = rv.sugerir(conto=0, vendidas=4, dias_observados=28, pidieron=4)
        self.assertEqual((con, con_demanda), (4, 8))

    def test_no_se_mueve_vs_sin_datos(self) -> None:
        self.assertEqual(rv.sugerir(conto=5, vendidas=0, dias_observados=30, pidieron=0)[3], rv.NO_SE_MUEVE)
        self.assertEqual(rv.sugerir(conto=5, vendidas=0, dias_observados=3, pidieron=0)[3], rv.SIN_DATOS)

    def test_semanas_configurables(self) -> None:
        self.assertEqual(rv.sugerir(conto=0, vendidas=7, dias_observados=7, pidieron=0, semanas=2)[0], 14)


class _Escenario(unittest.TestCase):
    """Escuela con 2 prendas × tallas 6 y 8, y ayudas para ventas y conteos."""

    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.s = Session(self.engine)
        self.escuela = _seed(self.s, "Uno")   # 2 prendas × tallas 6 y 8
        self.s.commit()
        self.v = list(self.s.scalars(select(Variante).order_by(Variante.id)).all())

    def tearDown(self) -> None:
        self.s.close()

    # --- ayudas ---------------------------------------------------------------
    def _venta(self, dia: date, sku: str, cantidad: int, tipo: str = "venta") -> None:
        self.s.add(LibretaVenta(
            employee_code="VEND-4", tipo=tipo, piezas=cantidad, monto_total=100 * cantidad,
            detalle=[{"sku": sku, "talla": "6", "nombre": "x", "cantidad": cantidad, "precio": "100", "subtotal": "100"}],
            created_at=_dt(dia),
        ))
        self.s.flush()

    def _conteo_previo(self, variante: Variante, fisico: int, dia: date, *, pedido: int | None = None, sugerido: int | None = None) -> ConteoInventario:
        c = ConteoInventario(
            variante_id=variante.id, escuela_id=self.escuela.id, stock_sistema=0, stock_fisico=fisico,
            diferencia=fisico, contado_por="x", contado_at=_dt(dia), pedido=pedido, pedido_sugerido=sugerido,
            pedido_decidido_at=_dt(dia) if pedido is not None else None,
        )
        self.s.add(c)
        self.s.flush()
        return c

    def _jornada_con(self, tallas: dict[Variante, int], dia: date = HOY, notas: dict[Variante, str] | None = None):
        j = jn.abrir_jornada(self.s, escuela_id=self.escuela.id, empleada_code="VEND-4", empleada_nombre="Fanny")
        registrar_conteos_lote(
            self.s,
            [ConteoInput(v.id, n, (notas or {}).get(v)) for v, n in tallas.items()],
            "Fanny (VEND-4)",
            jornada_id=j.id,
        )
        for c in self.s.scalars(select(ConteoInventario).where(ConteoInventario.jornada_id == j.id)):
            c.contado_at = _dt(dia)
        self.s.flush()
        return j


class RevisarTests(_Escenario):
    def test_ventas_desde_el_conteo_anterior_por_sku(self) -> None:
        v0 = self.v[0]
        self._conteo_previo(v0, 20, HOY - timedelta(days=14))
        self._venta(HOY - timedelta(days=20), v0.sku, 5)   # antes del conteo anterior: no cuenta
        self._venta(HOY - timedelta(days=10), v0.sku, 3)
        self._venta(HOY - timedelta(days=2), v0.sku, 4)
        self._venta(HOY - timedelta(days=2), self.v[1].sku, 9)  # otra talla
        j = self._jornada_con({v0: 13})
        linea = rv.revisar(self.s, j, hoy=HOY).lineas[0]
        self.assertEqual((linea.anterior, linea.anterior_at), (20, HOY - timedelta(days=14)))
        self.assertEqual(linea.vendidas, 7)
        self.assertEqual(linea.dias_observados, 14)
        self.assertEqual(linea.ritmo_semana, 3.5)
        # 3.5 × 4 = 14; hay 13 → pedir 1
        self.assertEqual((linea.sugerido, linea.estado), (1, rv.PEDIR))

    def test_sin_conteo_anterior_mira_desde_que_hay_libreta(self) -> None:
        v0 = self.v[0]
        self._venta(HOY - timedelta(days=21), v0.sku, 6)
        self._venta(HOY - timedelta(days=1), v0.sku, 1)
        j = self._jornada_con({v0: 0})
        linea = rv.revisar(self.s, j, hoy=HOY).lineas[0]
        self.assertIsNone(linea.anterior)
        self.assertEqual((linea.vendidas, linea.dias_observados), (7, 21))
        self.assertEqual(linea.estado, rv.URGENTE)

    def test_sin_libreta_no_inventa_ritmo(self) -> None:
        j = self._jornada_con({self.v[0]: 4})
        linea = rv.revisar(self.s, j, hoy=HOY).lineas[0]
        self.assertEqual((linea.vendidas, linea.dias_observados, linea.sugerido, linea.estado), (0, 0, 0, rv.SIN_DATOS))

    def test_apartados_cuentan_y_otros_tipos_no(self) -> None:
        v0 = self.v[0]
        self._venta(HOY - timedelta(days=5), v0.sku, 2, tipo="apartado")
        self._venta(HOY - timedelta(days=5), v0.sku, 9, tipo="devolucion")
        j = self._jornada_con({v0: 30})
        self.assertEqual(rv.revisar(self.s, j, hoy=HOY).lineas[0].vendidas, 2)

    def test_lo_que_pidieron_y_no_habia_entra_a_la_cuenta(self) -> None:
        v0 = self.v[0]
        self._venta(HOY - timedelta(days=13), v0.sku, 1)  # para que exista Libreta
        self.s.add(DemandaNoAtendida(tipo="talla_agotada", sku=v0.sku, piezas=2, created_at=_dt(HOY - timedelta(days=3))))
        self.s.add(DemandaNoAtendida(tipo="busqueda_vacia", sku=v0.sku, piezas=1, created_at=_dt(HOY - timedelta(days=3))))
        self.s.flush()
        j = self._jornada_con({v0: 0})
        linea = rv.revisar(self.s, j, hoy=HOY).lineas[0]
        self.assertEqual(linea.pidieron, 2)
        self.assertEqual(linea.estado, rv.URGENTE)

    def test_lo_que_ellas_anotaron_en_la_hoja(self) -> None:
        v0 = self.v[0]
        j = self._jornada_con({v0: 3}, notas={v0: "Pedido: 12"})
        self.assertEqual(rv.revisar(self.s, j, hoy=HOY).lineas[0].ellas_sugieren, 12)

    def test_recuerda_el_pedido_anterior_y_que_paso_despues(self) -> None:
        v0 = self.v[0]
        self._conteo_previo(v0, 2, HOY - timedelta(days=21), pedido=6, sugerido=5)
        self._venta(HOY - timedelta(days=10), v0.sku, 4)
        j = self._jornada_con({v0: 4})
        linea = rv.revisar(self.s, j, hoy=HOY).lineas[0]
        self.assertEqual((linea.pedido_anterior, linea.pedido_anterior_at), (6, HOY - timedelta(days=21)))
        self.assertEqual(linea.vendidas_desde_pedido, 4)

    def test_guardar_pedidos_es_del_dueno_y_deja_memoria(self) -> None:
        v0, v1 = self.v[0], self.v[1]
        self._venta(HOY - timedelta(days=14), v0.sku, 14)
        j = self._jornada_con({v0: 10, v1: 10})
        rev = rv.revisar(self.s, j, hoy=HOY)
        ids = {l.variante_id: l.conteo_id for l in rev.lineas}
        with self.assertRaises(PermissionError):
            rv.guardar_pedidos(self.s, j, {ids[v0.id]: 20}, decidido_por="VEND-4")
        n = rv.guardar_pedidos(self.s, j, {ids[v0.id]: 20, ids[v1.id]: None}, decidido_por="VEND-1")
        self.assertEqual(n, 1)
        c0 = self.s.get(ConteoInventario, ids[v0.id])
        self.assertEqual((c0.pedido, c0.pedido_sugerido), (20, rev.lineas[0].sugerido))
        self.assertIsNotNone(c0.pedido_decidido_at)
        self.assertIsNone(self.s.get(ConteoInventario, ids[v1.id]).pedido)
        # La revisión ya trae lo decidido.
        rev2 = rv.revisar(self.s, j, hoy=HOY)
        self.assertEqual([l.pedido for l in rev2.lineas], [20, None])
        self.assertEqual(rev2.piezas_pedidas, 20)

    def test_totales(self) -> None:
        v0, v1 = self.v[0], self.v[1]
        self._venta(HOY - timedelta(days=14), v0.sku, 14)
        self._venta(HOY - timedelta(days=14), v1.sku, 2)
        j = self._jornada_con({v0: 0, v1: 50})
        rev = rv.revisar(self.s, j, hoy=HOY)
        self.assertEqual(rev.tallas_a_pedir, 1)
        self.assertEqual(rev.piezas_sugeridas, 28)
        self.assertEqual(rev.urgentes, 1)
        self.assertEqual(rev.quien, "Fanny")


class HojaDePedidoTests(unittest.TestCase):
    def _revision(self, pedidos):
        lineas = [
            rv.LineaRevision(
                conteo_id=i, variante_id=i, producto=prod, talla=talla, color=color, conto=0, anterior=None,
                anterior_at=None, vendidas=0, dias_observados=0, ritmo_semana=0, semanas_cubiertas=None,
                pidieron=0, ellas_sugieren=None, sugerido=0, estado=rv.SIN_DATOS, pedido_anterior=None,
                pedido_anterior_at=None, vendidas_desde_pedido=None, pedido=pedido,
            )
            for i, (prod, talla, color, pedido) in enumerate(pedidos)
        ]
        return rv.Revision(1, "Práxedis Guerrero", "Fanny", date(2026, 9, 13), lineas)

    def test_texto_agrupa_por_prenda_y_suma(self) -> None:
        r = self._revision([
            ("Camisa Blanca Práxedis Guerrero", "6", "", 12),
            ("Camisa Blanca Práxedis Guerrero", "8", "", 3),
            ("Pantalón Gris Práxedis Guerrero", "6", "", None),
            ("Pantalón Gris Práxedis Guerrero", "8", "", 0),
            ("Suéter Práxedis Guerrero", "M", "", 2),
        ])
        texto = rv.texto_pedido(r)
        self.assertEqual(texto.splitlines()[0], "Pedido Práxedis Guerrero · 13/09/2026")
        self.assertIn("Camisa Blanca\n  6: 12\n  8: 3", texto)
        self.assertNotIn("Pantalón", texto)   # sin piezas no aparece
        self.assertIn("Suéter\n  M: 2", texto)
        self.assertTrue(texto.endswith("Total: 17 piezas"))

    def test_el_color_solo_cuando_hay_mas_de_uno(self) -> None:
        r = self._revision([("Polo Práxedis Guerrero", "6", "AZUL", 1), ("Polo Práxedis Guerrero", "6", "ROJO", 2)])
        self.assertIn("6 AZUL: 1", rv.texto_pedido(r))
        r = self._revision([("Polo Práxedis Guerrero", "6", "AZUL", 1), ("Polo Práxedis Guerrero", "8", "AZUL", 2)])
        self.assertIn("  6: 1", rv.texto_pedido(r))

    def test_sin_piezas_lo_dice(self) -> None:
        self.assertIn("(sin piezas)", rv.texto_pedido(self._revision([("Camisa", "6", "", None)])))

    def test_html_lleva_lo_mismo(self) -> None:
        r = self._revision([("Camisa Blanca Práxedis Guerrero", "6", "", 12)])
        html = rv.html_pedido(r)
        self.assertIn("Pedido · Práxedis Guerrero", html)
        self.assertIn("Camisa Blanca", html)
        self.assertIn("<b>12</b>", html)
        self.assertIn("12 piezas", html)


class HistoriaTests(_Escenario):
    def test_conteos_con_lo_pedido_y_lo_vendido_despues(self) -> None:
        v0 = self.v[0]
        self._conteo_previo(v0, 12, HOY - timedelta(days=42), pedido=6, sugerido=4)
        self._conteo_previo(v0, 8, HOY - timedelta(days=21))
        self._venta(HOY - timedelta(days=30), v0.sku, 3)   # entre el 1º y el 2º
        self._venta(HOY - timedelta(days=10), v0.sku, 5)   # después del 2º
        self._venta(HOY, v0.sku, 1)                        # hoy también cuenta
        h = rv.historia_de_talla(self.s, v0.id, hoy=HOY)
        self.assertEqual(h.talla, "6")
        self.assertEqual([c.conto for c in h.conteos], [8, 12])
        self.assertEqual([c.vendidas_despues for c in h.conteos], [6, 3])
        self.assertEqual((h.conteos[1].pedido, h.conteos[1].sugerido), (6, 4))
        self.assertEqual(h.pedido_total, 6)

    def test_ventas_por_semana_con_lo_que_pidieron(self) -> None:
        v0 = self.v[0]
        lunes = HOY - timedelta(days=HOY.weekday())
        self._venta(lunes, v0.sku, 2)
        self._venta(lunes - timedelta(days=7), v0.sku, 4)
        self._venta(lunes - timedelta(weeks=20), v0.sku, 9)   # fuera de las 12 semanas
        self.s.add(DemandaNoAtendida(tipo="talla_agotada", sku=v0.sku, piezas=1, created_at=_dt(lunes + timedelta(days=2))))
        self.s.flush()
        h = rv.historia_de_talla(self.s, v0.id, hoy=HOY)
        self.assertEqual(len(h.semanas), 12)
        self.assertEqual((h.semanas[-1].vendidas, h.semanas[-1].pidieron), (2, 1))
        self.assertEqual(h.semanas[-2].vendidas, 4)
        self.assertEqual(h.vendidas_total, 6)
        self.assertEqual(h.maximo_semana, 4)
        self.assertEqual(h.semanas[-1].etiqueta, lunes.strftime("%d/%m"))

    def test_sin_libreta_no_dice_vendidas(self) -> None:
        v0 = self.v[0]
        self._conteo_previo(v0, 3, HOY - timedelta(days=5))
        h = rv.historia_de_talla(self.s, v0.id, hoy=HOY)
        self.assertIsNone(h.conteos[0].vendidas_despues)
        self.assertEqual(h.vendidas_total, 0)

    def test_variante_inexistente(self) -> None:
        with self.assertRaises(ValueError):
            rv.historia_de_talla(self.s, 99999, hoy=HOY)


if __name__ == "__main__":
    unittest.main()
