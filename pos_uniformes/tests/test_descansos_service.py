"""Solicitudes de descanso: ella pide un día, Daniel lo aprueba viendo la semana.

Lo delicado: que una petición NO sea un día libre hasta que se apruebe (si se
escribiera en el calendario al pedirla, la nómina dejaría de contar ese día y
el detector de faltas se callaría sin que nadie autorizara nada), y que al
aprobarla el descanso fijo de esa semana se MUEVA en vez de regalar un día.
"""

from __future__ import annotations

import unittest
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import (
    Empleada,
    EmpleadaEvento,
    EmpleadaHorario,
    SolicitudDescanso,
)
from pos_uniformes.services import descansos_service as ds

HOY = date(2026, 10, 5)        # lunes
MIERCOLES = date(2026, 10, 7)
DOMINGO = date(2026, 10, 11)


class _Base(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.s = Session(engine)
        self.s.add(Empleada(codigo="VEND-5", nombre_completo="Cristal Torres", activo=True))
        self.s.add(Empleada(codigo="VEND-3", nombre_completo="Evelyn Ortiz", activo=True))
        # Cristal descansa domingo; Evelyn, sábado.
        self.s.add(EmpleadaHorario(employee_code="VEND-5", descanso_weekday=6,
                                   fecha_ultimo_pago=date(2026, 10, 3)))
        self.s.add(EmpleadaHorario(employee_code="VEND-3", descanso_weekday=5,
                                   fecha_ultimo_pago=date(2026, 10, 1)))
        self.s.flush()

    def _pedir(self, fecha=MIERCOLES, motivo="Escuela", code="VEND-5"):
        return ds.pedir(self.s, employee_code=code, nombre="Cristal Torres",
                        fecha=fecha, motivo=motivo, hoy=HOY)


class PedirTests(_Base):
    def test_queda_esperando_respuesta(self) -> None:
        s = self._pedir()
        self.assertEqual(s.estado, ds.PEDIDO)
        self.assertEqual(ds.pendientes(self.s, hoy=HOY), [s])

    def test_pedir_no_marca_nada_en_el_calendario(self) -> None:
        """Lo más importante: una petición no es un día libre."""
        self._pedir()
        self.assertEqual(self.s.scalars(select(EmpleadaEvento)).all(), [])

    def test_un_dia_que_ya_paso_no_se_pide(self) -> None:
        with self.assertRaises(ds.NoSePuede):
            self._pedir(fecha=HOY - timedelta(days=1))

    def test_no_se_aparta_el_año_entero(self) -> None:
        with self.assertRaises(ds.NoSePuede):
            self._pedir(fecha=HOY + timedelta(days=ds.DIAS_MAXIMO_ADELANTE + 1))

    def test_sin_motivo_no_se_puede_autorizar(self) -> None:
        with self.assertRaises(ds.NoSePuede):
            self._pedir(motivo="   ")

    def test_no_se_pide_dos_veces_el_mismo_dia(self) -> None:
        self._pedir()
        with self.assertRaises(ds.NoSePuede):
            self._pedir()

    def test_su_propio_descanso_no_se_pide(self) -> None:
        """El domingo ya descansa: pedirlo no significa nada."""
        with self.assertRaises(ds.NoSePuede):
            self._pedir(fecha=DOMINGO)

    def test_hoy_mismo_si_se_puede_pedir(self) -> None:
        self.assertIsNotNone(self._pedir(fecha=HOY))


class ResponderTests(_Base):
    def test_aprobar_mueve_el_descanso_fijo_de_esa_semana(self) -> None:
        """Cambia de día, no gana uno extra (decisión de Daniel, 2026-10-05)."""
        from pos_uniformes.services.calendario_empleadas_service import DESCANSO, TRABAJO

        s = self._pedir()
        ds.aprobar(self.s, s.id, quien="VEND-1")
        eventos = {
            e.fecha: e.tipo for e in self.s.scalars(
                select(EmpleadaEvento).where(EmpleadaEvento.employee_code == "VEND-5")
            ).all()
        }
        self.assertEqual(eventos.get(MIERCOLES), DESCANSO)
        self.assertEqual(eventos.get(DOMINGO), TRABAJO)   # su domingo se movió

    def test_el_calendario_dice_que_lo_pidio_ella(self) -> None:
        s = self._pedir(motivo="Doctor")
        ds.aprobar(self.s, s.id, quien="VEND-1")
        evento = self.s.scalars(
            select(EmpleadaEvento).where(EmpleadaEvento.fecha == MIERCOLES)
        ).first()
        self.assertIn("Doctor", evento.nota or "")

    def test_rechazar_no_toca_el_calendario(self) -> None:
        s = self._pedir()
        ds.rechazar(self.s, s.id, quien="VEND-1", respuesta="Ese día hay escuela")
        self.assertEqual(self.s.scalars(select(EmpleadaEvento)).all(), [])
        self.assertEqual(self.s.get(SolicitudDescanso, s.id).respuesta, "Ese día hay escuela")

    def test_no_se_responde_dos_veces(self) -> None:
        s = self._pedir()
        ds.aprobar(self.s, s.id, quien="VEND-1")
        with self.assertRaises(ds.NoSePuede):
            ds.rechazar(self.s, s.id, quien="VEND-1")

    def test_solo_ella_cancela_la_suya(self) -> None:
        s = self._pedir()
        with self.assertRaises(ds.NoSePuede):
            ds.cancelar(self.s, s.id, quien="VEND-3")
        ds.cancelar(self.s, s.id, quien="VEND-5")
        self.assertEqual(self.s.get(SolicitudDescanso, s.id).estado, ds.CANCELADO)

    def test_ya_aprobado_no_se_vuelve_a_pedir(self) -> None:
        s = self._pedir()
        ds.aprobar(self.s, s.id, quien="VEND-1")
        with self.assertRaises(ds.NoSePuede):
            self._pedir()


class ListasTests(_Base):
    def test_las_de_dias_que_ya_pasaron_no_estorban_la_lista(self) -> None:
        vieja = self._pedir(fecha=HOY + timedelta(days=1))
        vieja.fecha = HOY - timedelta(days=3)   # se quedó sin contestar
        self.s.flush()
        self.assertEqual(ds.pendientes(self.s, hoy=HOY), [])

    def test_pero_se_puede_saber_que_quedaron_sin_respuesta(self) -> None:
        """No contestar se siente como un «no» que nadie dijo."""
        s = self._pedir(fecha=HOY + timedelta(days=1))
        s.fecha = HOY - timedelta(days=3)
        self.s.flush()
        self.assertEqual(ds.sin_responder_que_ya_pasaron(self.s, hoy=HOY), [s])

    def test_la_mas_proxima_va_primero(self) -> None:
        # +20 cae en domingo, que es el descanso de Cristal y no se puede
        # pedir: +22 es martes.
        lejos = self._pedir(fecha=HOY + timedelta(days=22))
        cerca = ds.pedir(self.s, employee_code="VEND-3", nombre="Evelyn Ortiz",
                         fecha=HOY + timedelta(days=2), motivo="Trámite", hoy=HOY)
        self.assertEqual(ds.pendientes(self.s, hoy=HOY), [cerca, lejos])


class ContextoTests(_Base):
    def test_dice_quien_mas_descansa_ese_dia(self) -> None:
        sabado = date(2026, 10, 10)   # el descanso fijo de Evelyn
        s = self._pedir(fecha=sabado)
        ctx = ds.contexto_de(self.s, s)
        self.assertEqual(ctx.quien_mas_descansa, ["Evelyn"])
        self.assertEqual(ctx.trabajan_ese_dia, [])
        self.assertTrue(ctx.quedaria_corta is False or ctx.quedaria_corta is True)

    def test_avisa_cuando_no_quedaria_nadie(self) -> None:
        sabado = date(2026, 10, 10)
        s = self._pedir(fecha=sabado)
        ctx = ds.contexto_de(self.s, s)
        self.assertEqual(ctx.trabajan_ese_dia, [])

    def test_la_semana_trae_los_siete_dias_y_marca_el_pedido(self) -> None:
        s = self._pedir()
        ctx = ds.contexto_de(self.s, s)
        self.assertEqual(len(ctx.semana), 7)
        marcado = [d for d in ctx.semana if d.es_el_pedido]
        self.assertEqual([d.fecha for d in marcado], [MIERCOLES])

    def test_cuenta_los_descansos_ya_autorizados_de_ese_dia(self) -> None:
        """Dos aprobados el mismo día dejan la tienda corta y hay que verlo."""
        otra = ds.pedir(self.s, employee_code="VEND-3", nombre="Evelyn Ortiz",
                        fecha=MIERCOLES, motivo="Doctor", hoy=HOY)
        ds.aprobar(self.s, otra.id, quien="VEND-1")
        s = self._pedir()
        ctx = ds.contexto_de(self.s, s)
        self.assertEqual(ctx.quien_mas_descansa, ["Evelyn"])

    def test_avisa_si_ese_dia_le_toca_cobrar(self) -> None:
        # Cristal cobró el 3-oct con ciclo de 7 días: le toca el 10.
        s = self._pedir(fecha=date(2026, 10, 10))
        self.assertTrue(ds.contexto_de(self.s, s).tiene_pago)

    def test_sin_ventas_no_inventa_un_promedio(self) -> None:
        s = self._pedir()
        ctx = ds.contexto_de(self.s, s)
        self.assertIsNone(ctx.venta_tipica)
        self.assertFalse(ctx.es_el_dia_mas_movido)


if __name__ == "__main__":
    unittest.main()


class LaSemanaComoQuedariaTests(_Base):
    """El panorama dice "la semana quedaría así", así que tiene que estar
    pintada CON el cambio hecho: ella descansando el día que pidió y su
    descanso fijo pasado a trabajo. Antes decía "descansa —" en el día que se
    estaba decidiendo y la seguía poniendo libre su domingo (2026-10-05)."""

    def _semana_de(self, fecha=MIERCOLES):
        s = self._pedir(fecha=fecha)
        return {d.fecha: d for d in ds.contexto_de(self.s, s).semana}

    def test_aparece_descansando_el_dia_que_pidio(self) -> None:
        dia = self._semana_de()[MIERCOLES]
        self.assertTrue(any("Cristal" in n for n in dia.descansan))
        self.assertTrue(any("lo pide" in n for n in dia.descansan))

    def test_su_descanso_fijo_ya_sale_como_trabajo(self) -> None:
        dia = self._semana_de()[DOMINGO]
        self.assertTrue(any("Cristal" in n for n in dia.trabajan))
        self.assertEqual([n for n in dia.descansan if "Cristal" in n], [])

    def test_los_demas_no_se_mueven(self) -> None:
        semana = self._semana_de()
        sabado = semana[date(2026, 10, 10)]
        self.assertIn("Evelyn", sabado.descansan)
