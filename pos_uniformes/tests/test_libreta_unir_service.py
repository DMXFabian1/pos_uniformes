"""Unir dos ventas en UNA operación (Daniel, 2026-11-13).

«a veces mis empleadas venden e imprimen el ticket, pero esa misma persona se
decide y se lleva otra cosa». Unir NO anula ni borra: el dinero, las piezas,
las comisiones y la existencia quedan igual; solo se cuentan como 1.
"""

from __future__ import annotations

import unittest
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import AuditoriaAusencias, LibretaVenta
from pos_uniformes.services import libreta_service as ls
from pos_uniformes.services import libreta_unir_service as lu

HOY = date(2026, 11, 13)
DUENO = "VEND-1"


def _en(hora: int, minuto: int = 0, dia: date = HOY) -> datetime:
    return datetime.combine(dia, time(hora, minuto))


class _Base(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
        self.s = Session(engine)
        self.addCleanup(self.s.close)

    def venta(self, id_, hora, *, code="VEND-4", tipo="venta", piezas=1, monto="300", empleada=False,
              minuto=0, dia=HOY) -> LibretaVenta:
        row = LibretaVenta(
            id=id_, employee_code=code, employee_name="Fanny Ortiz", tipo=tipo, piezas=piezas,
            comisiones=0 if empleada or tipo == "abono" else piezas, monto_total=Decimal(monto),
            monto_neto=Decimal(monto), descuento_empleada=empleada, privado=False,
            created_at=_en(hora, minuto, dia), detalle=[],
        )
        self.s.add(row)
        self.s.flush()
        return row

    def foto(self, *ids):
        """Lo que NO debe cambiar al unir: dinero, piezas, comisiones."""
        return [
            (r.id, r.monto_total, r.monto_neto, r.piezas, r.comisiones, r.tipo, r.employee_code)
            for r in (self.s.get(LibretaVenta, i) for i in ids)
        ]


class UnirTests(_Base):
    def test_unir_dos_ventas_las_cuenta_como_una(self) -> None:
        a, b = self.venta(1639, 10, piezas=2, monto="500"), self.venta(1640, 10, minuto=7, monto="150")
        antes = self.foto(1639, 1640)
        r = lu.unir(self.s, a.id, b.id, actor=DUENO)
        self.assertEqual((r.grupo_id, r.ids), (1639, (1639, 1640)))
        self.assertEqual((a.operacion_grupo_id, b.operacion_grupo_id), (1639, 1639))
        self.assertEqual(b.operacion_unida_por, "VEND-1")
        self.assertIsNotNone(b.operacion_unida_en)
        # El dinero, las piezas y las comisiones no cambian; ninguna se borra.
        self.assertEqual(self.foto(1639, 1640), antes)
        filas = [a, b]
        self.assertEqual(ls.contar_operaciones(filas), 1)
        self.assertEqual(ls.totales_libreta(filas).piezas, 3)
        # Queda rastro en la bitácora.
        bit = self.s.scalars(select(AuditoriaAusencias).where(AuditoriaAusencias.operacion == "unir_operacion")).all()
        self.assertEqual([(x.actor, x.entidad_id) for x in bit], [("VEND-1", 1640)])

    def test_el_orden_de_los_argumentos_no_importa_para_la_primera(self) -> None:
        a, b = self.venta(1, 10), self.venta(2, 11)
        r = lu.unir(self.s, b.id, a.id, actor=DUENO)
        self.assertEqual(r.grupo_id, 1)

    def test_unir_una_tercera_agranda_el_grupo(self) -> None:
        a, b, c = self.venta(1, 10), self.venta(2, 11), self.venta(3, 12)
        lu.unir(self.s, a.id, b.id, actor=DUENO)
        r = lu.unir(self.s, b.id, c.id, actor=DUENO)
        self.assertEqual((r.grupo_id, r.ids), (1, (1, 2, 3)))
        self.assertEqual(ls.contar_operaciones([a, b, c]), 1)

    def test_solo_el_dueno(self) -> None:
        a, b = self.venta(1, 10), self.venta(2, 11)
        with self.assertRaises(lu.SoloElDuenoUne):
            lu.unir(self.s, a.id, b.id, actor="VEND-4")
        self.assertIsNone(b.operacion_grupo_id)

    def test_distinta_empleada(self) -> None:
        a, b = self.venta(1, 10), self.venta(2, 11, code="VEND-5")
        with self.assertRaisesRegex(lu.NoSePuedeUnir, "empleadas distintas"):
            lu.unir(self.s, a.id, b.id, actor=DUENO)

    def test_distinto_dia(self) -> None:
        a, b = self.venta(1, 10, dia=HOY - timedelta(days=1)), self.venta(2, 11)
        with self.assertRaisesRegex(lu.NoSePuedeUnir, "días distintos"):
            lu.unir(self.s, a.id, b.id, actor=DUENO)

    def test_tipos_que_no_son_venta(self) -> None:
        a = self.venta(1, 10)
        for i, tipo in ((2, "abono"), (3, "apartado"), (4, "cambio")):
            otra = self.venta(i, 11, tipo=tipo)
            with self.assertRaisesRegex(lu.NoSePuedeUnir, "Solo se unen ventas"):
                lu.unir(self.s, a.id, otra.id, actor=DUENO)
        empleada = self.venta(5, 12, empleada=True)
        with self.assertRaisesRegex(lu.NoSePuedeUnir, "compra de una empleada"):
            lu.unir(self.s, a.id, empleada.id, actor=DUENO)

    def test_ya_unida(self) -> None:
        a, b, c, d = self.venta(1, 10), self.venta(2, 11), self.venta(3, 12), self.venta(4, 13)
        lu.unir(self.s, a.id, b.id, actor=DUENO)
        with self.assertRaisesRegex(lu.NoSePuedeUnir, "ya cuentan como 1"):
            lu.unir(self.s, a.id, b.id, actor=DUENO)
        lu.unir(self.s, c.id, d.id, actor=DUENO)
        # D ya está en otro grupo: no se mete a la fuerza en el de A+B.
        with self.assertRaisesRegex(lu.NoSePuedeUnir, "ya está unida"):
            lu.unir(self.s, b.id, d.id, actor=DUENO)

    def test_misma_venta(self) -> None:
        a = self.venta(1, 10)
        with self.assertRaises(lu.NoSePuedeUnir):
            lu.unir(self.s, a.id, a.id, actor=DUENO)


class SepararTests(_Base):
    def test_separar_deshace_la_union(self) -> None:
        a, b = self.venta(1, 10), self.venta(2, 11)
        lu.unir(self.s, a.id, b.id, actor=DUENO)
        self.assertIsNone(lu.separar(self.s, b.id, actor=DUENO))
        self.assertEqual((a.operacion_grupo_id, b.operacion_grupo_id), (None, None))
        self.assertIsNone(b.operacion_unida_por)
        self.assertEqual(ls.contar_operaciones([a, b]), 2)
        bit = self.s.scalars(select(AuditoriaAusencias.operacion).order_by(AuditoriaAusencias.id)).all()
        self.assertEqual(bit, ["unir_operacion", "separar_operacion"])

    def test_separar_la_primera_de_tres_pasa_el_grupo_a_la_siguiente(self) -> None:
        a, b, c = self.venta(1, 10), self.venta(2, 11), self.venta(3, 12)
        lu.unir(self.s, a.id, b.id, actor=DUENO)
        lu.unir(self.s, b.id, c.id, actor=DUENO)
        r = lu.separar(self.s, a.id, actor=DUENO)
        self.assertEqual((r.grupo_id, r.ids), (2, (2, 3)))
        self.assertEqual([x.operacion_grupo_id for x in (a, b, c)], [None, 2, 2])
        self.assertEqual(ls.contar_operaciones([a, b, c]), 2)

    def test_separar_rechazos(self) -> None:
        a, b = self.venta(1, 10), self.venta(2, 11)
        with self.assertRaisesRegex(lu.NoSePuedeUnir, "no está unida"):
            lu.separar(self.s, a.id, actor=DUENO)
        lu.unir(self.s, a.id, b.id, actor=DUENO)
        with self.assertRaises(lu.SoloElDuenoUne):
            lu.separar(self.s, b.id, actor="VEND-4")


class AnteriorTests(_Base):
    def test_la_venta_inmediata_anterior_de_la_misma_empleada(self) -> None:
        self.venta(1, 9)
        a = self.venta(2, 10)
        self.venta(3, 10, minuto=3, code="VEND-5")          # otra empleada
        self.venta(4, 10, minuto=4, tipo="abono")           # se salta
        self.venta(5, 10, minuto=5, empleada=True)          # se salta
        b = self.venta(6, 10, minuto=8)
        self.assertEqual(lu.anterior_para_unir(self.s, b.id).id, a.id)

    def test_no_cruza_de_dia_ni_repite_el_grupo(self) -> None:
        self.venta(1, 18, dia=HOY - timedelta(days=1))
        a = self.venta(2, 10)
        self.assertIsNone(lu.anterior_para_unir(self.s, a.id))
        b = self.venta(3, 11)
        lu.unir(self.s, a.id, b.id, actor=DUENO)
        self.assertIsNone(lu.anterior_para_unir(self.s, b.id))


class CorteEnMedioTests(_Base):
    """Si entre las dos ventas ya se hizo un corte, cada una cuenta en su
    corte y ninguno bajaría: no se unen (revisión 2026-11-13)."""

    def corte(self, hora, minuto=0, *, con_hasta=True):
        from pos_uniformes.database.models import LibretaCorte

        momento = _en(hora, minuto)
        c = LibretaCorte(fecha=HOY, monto_final=Decimal("0"), operaciones=10, piezas=0, creado_por=DUENO,
                         created_at=momento + timedelta(seconds=30), hasta=momento if con_hasta else None)
        self.s.add(c)
        self.s.flush()
        return c

    def test_corte_entre_las_dos_rechaza(self) -> None:
        a = self.venta(1639, 15, minuto=50)
        self.corte(16)
        b = self.venta(1640, 16, minuto=5)
        antes = self.foto(1639, 1640)
        with self.assertRaisesRegex(lu.NoSePuedeUnir, "ya se hizo un corte"):
            lu.unir(self.s, a.id, b.id, actor=DUENO)
        self.assertEqual((a.operacion_grupo_id, b.operacion_grupo_id), (None, None))
        self.assertEqual(self.foto(1639, 1640), antes)
        self.assertTrue(lu.corte_entre(self.s, a.created_at, b.created_at))

    def test_corte_viejo_sin_hasta_usa_su_hora(self) -> None:
        a = self.venta(1, 15, minuto=50)
        self.corte(16, con_hasta=False)
        b = self.venta(2, 16, minuto=5)
        with self.assertRaises(lu.NoSePuedeUnir):
            lu.unir(self.s, a.id, b.id, actor=DUENO)

    def test_corte_antes_o_despues_de_las_dos_si_deja(self) -> None:
        self.corte(9)
        a, b = self.venta(1, 10), self.venta(2, 10, minuto=7)
        self.corte(18)
        self.assertEqual(lu.unir(self.s, a.id, b.id, actor=DUENO).ids, (1, 2))

    def test_la_venta_justo_a_la_hora_del_corte_cae_en_ese_corte(self) -> None:
        a = self.venta(1, 16)            # created_at == hasta: es del corte de las 16:00
        self.corte(16)
        b = self.venta(2, 16, minuto=1)
        with self.assertRaises(lu.NoSePuedeUnir):
            lu.unir(self.s, a.id, b.id, actor=DUENO)
        self.assertFalse(lu.corte_entre(self.s, _en(15), _en(16)))   # las dos antes o en el corte

    def test_agrandar_un_grupo_pasando_un_corte_tambien_se_rechaza(self) -> None:
        a, b = self.venta(1, 10), self.venta(2, 10, minuto=5)
        lu.unir(self.s, a.id, b.id, actor=DUENO)
        self.corte(11)
        c = self.venta(3, 11, minuto=30)
        with self.assertRaises(lu.NoSePuedeUnir):
            lu.unir(self.s, b.id, c.id, actor=DUENO)
        self.assertIsNone(c.operacion_grupo_id)


class HayAnteriorEnPantallaTests(unittest.TestCase):
    """Para no ofrecer «Unir con la anterior» en la primera venta del día."""

    @staticmethod
    def fila(id_, hora, minuto=0, *, code="VEND-4", tipo="venta", grupo=None, empleada=False, dia=HOY):
        from types import SimpleNamespace

        return SimpleNamespace(id=id_, tipo=tipo, employee_code=code, descuento_empleada=empleada,
                               operacion_grupo_id=grupo, created_at=_en(hora, minuto, dia))

    def test_primera_y_segunda(self) -> None:
        f = self.fila
        primera, otra_emp, segunda = f(1, 12), f(2, 12, 1, code="VEND-6"), f(3, 12, 2)
        rows = [segunda, otra_emp, primera]
        self.assertFalse(lu.hay_anterior_en(rows, primera))
        self.assertFalse(lu.hay_anterior_en(rows, otra_emp))
        self.assertTrue(lu.hay_anterior_en(rows, segunda))

    def test_no_cuenta_otro_dia_ni_lo_que_no_se_une_ni_su_propio_grupo(self) -> None:
        f = self.fila
        ayer = f(1, 18, dia=HOY - timedelta(days=1))
        abono, empleada = f(2, 9, tipo="abono"), f(3, 9, 30, empleada=True)
        a, b = f(4, 10, grupo=4), f(5, 10, 5, grupo=4)
        rows = [ayer, abono, empleada, a, b]
        self.assertFalse(lu.hay_anterior_en(rows, a))
        # b ya está con a: si estuviera suelta, a sí sería su anterior.
        self.assertFalse(lu.hay_anterior_en(rows, b))
        self.assertTrue(lu.hay_anterior_en(rows, f(5, 10, 5)))


class BorrarYReasignarTests(_Base):
    def test_borrar_una_unida_deja_sola_a_la_otra(self) -> None:
        a, b = self.venta(1, 10), self.venta(2, 11)
        lu.unir(self.s, a.id, b.id, actor=DUENO)
        ls._borrar_operacion(self.s, a, a.id)
        self.s.flush()
        self.assertIsNone(self.s.get(LibretaVenta, 2).operacion_grupo_id)


class TextosTests(unittest.TestCase):
    def test_confirmacion(self) -> None:
        self.assertEqual(
            lu.texto_confirmar_union([1640, 1639], "VEND-4"),
            "#1639 y #1640 de VEND-4 cuentan como 1 operación. El dinero, las piezas y las comisiones no cambian.",
        )
        self.assertIn("#1, #2 y #3", lu.texto_confirmar_union([3, 1, 2], "Fanny"))

    def test_marca_y_posiciones(self) -> None:
        from types import SimpleNamespace

        filas = [
            SimpleNamespace(id=2, operacion_grupo_id=1, created_at=_en(11)),
            SimpleNamespace(id=1, operacion_grupo_id=1, created_at=_en(10)),
            SimpleNamespace(id=3, operacion_grupo_id=None, created_at=_en(12)),
        ]
        self.assertEqual(lu.horas_de_las_otras(filas), {1: ["11:00"], 2: ["10:00"]})
        self.assertTrue(lu.puede_ofrecerse(SimpleNamespace(id=9, tipo="venta", operacion_grupo_id=None)))
        self.assertFalse(lu.puede_ofrecerse(SimpleNamespace(id=9, tipo="apartado", operacion_grupo_id=None)))


if __name__ == "__main__":
    unittest.main()
