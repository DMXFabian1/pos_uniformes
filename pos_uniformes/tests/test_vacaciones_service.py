"""Vacaciones: ley, saldo trazable y su lugar en el calendario y la nómina.

Cada prueba revisa la base: periodos, movimientos, eventos y estados.
"""

from __future__ import annotations

import unittest
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import (
    CajaParametros,
    Empleada,
    EmpleadaEvento,
    EmpleadaHorario,
    MovimientoVacaciones,
    PeriodoVacaciones,
    SolicitudVacaciones,
)
from pos_uniformes.services import descansos_service as ds
from pos_uniformes.services import vacaciones_service as vs


def _con_autoservicio(session, code, **kw):
    """Expediente + autoservicio abierto: estas pruebas son de ella pidiendo."""
    exp = vs.capturar_expediente(session, code, **kw)
    vs.habilitar_autoservicio(session, code, True, quien="VEND-1")
    return exp
from pos_uniformes.services.calendario_empleadas_service import (
    DESCANSO,
    VACACIONES,
    cargar_horario,
    estado_del_dia,
    faltas_netas_en_rango,
    marcar_dia,
    TRABAJO,
)

HOY = date(2026, 10, 5)                 # lunes
INGRESO = date(2024, 3, 1)              # dos años cumplidos al 1-mar-2026
LUNES = date(2026, 11, 2)
DOMINGO = date(2026, 11, 8)             # descanso fijo de Cristal


class LeyTests(unittest.TestCase):
    def test_21_dias_por_antiguedad_lft_art_76(self) -> None:
        esperado = {1: 12, 2: 14, 3: 16, 4: 18, 5: 20, 6: 22, 10: 22, 11: 24,
                    15: 24, 16: 26, 21: 28, 26: 30, 31: 32}
        for anio, dias in esperado.items():
            self.assertEqual(vs.dias_por_anio_de_servicio(anio), dias, anio)
        self.assertEqual(vs.dias_por_anio_de_servicio(0), 0)

    def test_26_prima_vacacional_25_por_ciento(self) -> None:
        # Sueldo semanal $1,300 → diario 185.714…; 12 días → 2,228.57; 25 % = 557.14
        self.assertEqual(vs.prima_vacacional(Decimal("1300"), 12), Decimal("557.14"))


class _Base(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.s = Session(engine)
        self.s.add(Empleada(codigo="VEND-5", nombre_completo="Cristal Torres", activo=True))
        self.s.add(Empleada(codigo="VEND-3", nombre_completo="Evelyn Ortiz", activo=True))
        self.s.add(EmpleadaHorario(employee_code="VEND-5", descanso_weekday=6))
        self.s.add(EmpleadaHorario(employee_code="VEND-3", descanso_weekday=5))
        self.s.add(CajaParametros(sueldo_base=Decimal("1300")))
        self.s.commit()
        _con_autoservicio(self.s, "VEND-5", fecha_ingreso=INGRESO, quien="VEND-1")
        vs.generar_periodos(self.s, "VEND-5", hoy=HOY)
        self.s.commit()

    def tearDown(self) -> None:
        self.s.close()

    def _pedir(self, desde=LUNES, hasta=DOMINGO, code="VEND-5"):
        return vs.pedir(self.s, employee_code=code, nombre=code, desde=desde, hasta=hasta, hoy=HOY)

    def _vac(self, code="VEND-5"):
        return sorted(e.fecha for e in self.s.scalars(select(EmpleadaEvento).where(
            EmpleadaEvento.employee_code == code, EmpleadaEvento.tipo == VACACIONES)).all())


class PeriodosTests(_Base):
    def test_21_genera_un_periodo_por_anio_cumplido_sin_duplicar(self) -> None:
        periodos = self.s.scalars(select(PeriodoVacaciones).order_by(PeriodoVacaciones.anio_servicio)).all()
        self.assertEqual([(p.anio_servicio, p.dias_correspondientes) for p in periodos], [(1, 12), (2, 14)])
        self.assertEqual(periodos[1].aniversario, date(2026, 3, 1))
        self.assertEqual(periodos[1].fecha_limite, date(2026, 9, 1))   # art. 81
        self.assertEqual(vs.generar_periodos(self.s, "VEND-5", hoy=HOY), [])
        self.assertEqual(vs.saldo(self.s, "VEND-5").disponible, 26)

    def test_sin_expediente_no_hay_saldo_inventado(self) -> None:
        self.assertEqual(vs.generar_periodos(self.s, "VEND-3", hoy=HOY), [])
        with self.assertRaises(vs.NoSePuede):
            self._pedir(code="VEND-3")

    def test_no_reinicia_en_enero(self) -> None:
        """El periodo nace en SU aniversario, no el 1 de enero."""
        self.assertEqual(vs.generar_periodos(self.s, "VEND-5", hoy=date(2027, 2, 28)), [])
        [p] = vs.generar_periodos(self.s, "VEND-5", hoy=date(2027, 3, 1))
        self.assertEqual((p.anio_servicio, p.dias_correspondientes), (3, 16))


class SolicitudTests(_Base):
    def test_22_aprobar_reserva_y_pinta_solo_dias_laborables(self) -> None:
        s = self._pedir()
        self.assertEqual(s.dias, 6)                      # el domingo es su descanso
        self.assertEqual(self._vac(), [])                # pedir no toca el calendario
        vs.aprobar(self.s, s.id, quien="VEND-1", hoy=HOY)
        self.assertEqual(self._vac(), [LUNES + timedelta(days=i) for i in range(6)])
        sal = vs.saldo(self.s, "VEND-5", periodo_id=s.periodo_id)
        self.assertEqual((sal.reservado, sal.disfrutado), (6, 0))
        self.assertEqual(estado_del_dia(cargar_horario(self.s, "VEND-5"), DOMINGO), DESCANSO)
        self.assertEqual(s.prima_estimada, vs.prima_vacacional(Decimal("1300"), 6))

    def test_22_usa_el_periodo_mas_viejo_primero(self) -> None:
        s = self._pedir()
        anio1 = self.s.scalars(select(PeriodoVacaciones).where(PeriodoVacaciones.anio_servicio == 1)).one()
        self.assertEqual(s.periodo_id, anio1.id)

    def test_anticipacion_apagada_hasta_que_daniel_la_defina(self) -> None:
        """Política sin definir: no se impone (Daniel, 2026-10-12)."""
        self.assertIsNone(vs.ANTICIPACION_VACACIONES_DIAS)
        self.assertIsNotNone(self._pedir(desde=HOY + timedelta(days=3), hasta=HOY + timedelta(days=5)))

    def test_anticipacion_configurable(self) -> None:
        from unittest import mock

        with mock.patch.object(vs, "ANTICIPACION_VACACIONES_DIAS", 15):
            with self.assertRaises(vs.NoSePuede):
                self._pedir(desde=HOY + timedelta(days=3), hasta=HOY + timedelta(days=5))

    def test_en_el_pasado_nunca(self) -> None:
        with self.assertRaises(vs.NoSePuede):
            self._pedir(desde=HOY - timedelta(days=3), hasta=HOY)

    def test_no_alcanza_el_saldo(self) -> None:
        with self.assertRaises(vs.NoSePuede):
            self._pedir(hasta=LUNES + timedelta(days=30))

    def test_23_consumo_parcial_y_cancelacion_a_medias(self) -> None:
        """Se fue lunes a miércoles y regresó: 3 disfrutados, 3 devueltos."""
        s = self._pedir()
        vs.aprobar(self.s, s.id, quien="VEND-1", hoy=HOY)
        jueves = LUNES + timedelta(days=3)
        self.assertEqual(vs.consumir(self.s, hoy=jueves), 3)
        self.assertEqual(vs.consumir(self.s, hoy=jueves), 0)       # no dos veces
        vs.cancelar(self.s, s.id, quien="VEND-1", hoy=jueves, motivo="regresó antes")
        sal = vs.saldo(self.s, "VEND-5", periodo_id=s.periodo_id)
        self.assertEqual((sal.reservado, sal.disfrutado, sal.disponible), (0, 3, 9))
        self.assertEqual(self._vac(), [LUNES, LUNES + timedelta(days=1), LUNES + timedelta(days=2)])

    def test_24_cancelar_un_periodo_aprobado_devuelve_todo(self) -> None:
        s = self._pedir()
        vs.aprobar(self.s, s.id, quien="VEND-1", hoy=HOY)
        vs.cancelar(self.s, s.id, quien="VEND-5", hoy=HOY)
        self.assertEqual(vs.saldo(self.s, "VEND-5").disponible, 26)
        self.assertEqual(self._vac(), [])
        tipos = [m.tipo for m in self.s.scalars(select(MovimientoVacaciones).where(
            MovimientoVacaciones.solicitud_id == s.id)).all()]
        self.assertEqual(tipos, ["reserva", "liberacion"])

    def test_25_no_se_encima_con_otras_ausencias(self) -> None:
        marcar_dia(self.s, "VEND-5", LUNES + timedelta(days=2), "falta", actor="VEND-1")
        with self.assertRaises(vs.NoSePuede):
            self._pedir()

    def test_25_ni_con_un_descanso_pedido(self) -> None:
        ds.pedir(self.s, employee_code="VEND-5", nombre="Cristal", fecha=LUNES + timedelta(days=2),
                 motivo="x", hoy=HOY)
        with self.assertRaises(vs.NoSePuede):
            self._pedir()

    def test_25_y_un_descanso_no_se_pide_en_vacaciones(self) -> None:
        s = self._pedir()
        vs.aprobar(self.s, s.id, quien="VEND-1", hoy=HOY)
        with self.assertRaises(ds.NoSePuede):
            ds.pedir(self.s, employee_code="VEND-5", nombre="Cristal", fecha=LUNES + timedelta(days=2),
                     motivo="x", hoy=HOY)

    def test_una_sola_de_vacaciones_a_la_vez(self) -> None:
        _con_autoservicio(self.s, "VEND-3", fecha_ingreso=INGRESO, quien="VEND-1")
        vs.generar_periodos(self.s, "VEND-3", hoy=HOY)
        self._pedir()
        with self.assertRaises(vs.NoSePuede):
            self._pedir(code="VEND-3", desde=LUNES + timedelta(days=3), hasta=LUNES + timedelta(days=10))

    def test_no_gasta_los_cambios_de_descanso(self) -> None:
        s = self._pedir()
        vs.aprobar(self.s, s.id, quien="VEND-1", hoy=HOY)
        self.assertEqual(ds.cambios_usados(self.s, "VEND-5", (2026, 11)), 0)

    def test_aprobar_dos_veces_no_duplica(self) -> None:
        s = self._pedir()
        vs.aprobar(self.s, s.id, quien="VEND-1", hoy=HOY)
        with self.assertRaises(vs.NoSePuede):
            vs.aprobar(self.s, s.id, quien="VEND-1", hoy=HOY)
        self.assertEqual(len(self._vac()), 6)

    def test_rechazar_no_toca_saldo_ni_calendario(self) -> None:
        s = self._pedir()
        vs.rechazar(self.s, s.id, quien="VEND-1")
        self.assertEqual(vs.saldo(self.s, "VEND-5").disponible, 26)
        self.assertEqual(self._vac(), [])

    def test_vence_si_nadie_contesta(self) -> None:
        s = self._pedir()
        vs.vencer_pendientes(self.s, hoy=LUNES + timedelta(days=1))
        self.assertEqual(s.estado, vs.VENCIDO)

    def test_quitar_un_dia_desde_el_calendario_revoca_y_devuelve(self) -> None:
        s = self._pedir()
        vs.aprobar(self.s, s.id, quien="VEND-1", hoy=HOY)
        jueves = LUNES + timedelta(days=3)
        marcar_dia(self.s, "VEND-5", jueves, TRABAJO, actor="VEND-1")
        self.assertEqual(s.estado, vs.REVOCADO)
        self.assertEqual(self._vac(), [LUNES, LUNES + timedelta(days=1), LUNES + timedelta(days=2)])
        sal = vs.saldo(self.s, "VEND-5", periodo_id=s.periodo_id)
        self.assertEqual((sal.reservado, sal.disfrutado), (0, 3))

    def test_ajuste_con_motivo_y_sin_negativos(self) -> None:
        p = self.s.scalars(select(PeriodoVacaciones).where(PeriodoVacaciones.anio_servicio == 1)).one()
        with self.assertRaises(vs.NoSePuede):
            vs.ajustar(self.s, "VEND-5", p.id, -2, quien="VEND-1", motivo="")
        with self.assertRaises(vs.NoSePuede):
            vs.ajustar(self.s, "VEND-5", p.id, -20, quien="VEND-1", motivo="ya las tomó en 2025")
        self.s.rollback()
        vs.ajustar(self.s, "VEND-5", p.id, -12, quien="VEND-1", motivo="ya las tomó en 2025")
        self.assertEqual(vs.saldo(self.s, "VEND-5", periodo_id=p.id).disponible, 0)


class NominaTests(_Base):
    def test_las_vacaciones_no_son_faltas(self) -> None:
        s = self._pedir()
        vs.aprobar(self.s, s.id, quien="VEND-1", hoy=HOY)
        h = cargar_horario(self.s, "VEND-5")
        self.assertEqual(faltas_netas_en_rango(h, LUNES, DOMINGO), 0)
        self.assertEqual(estado_del_dia(h, LUNES), VACACIONES)

    def test_por_dia_se_le_pagan_los_dias_de_vacaciones(self) -> None:
        from pos_uniformes.services.nomina_service import ParametrosCaja, calcular_pago

        self.s.add(Empleada(codigo="VEND-6", nombre_completo="Nayeli", activo=True))
        self.s.add(EmpleadaHorario(employee_code="VEND-6", modo_pago="por_dia", dias_trabajo=[5, 6],
                                   fecha_ultimo_pago=date(2026, 11, 1)))
        self.s.commit()
        _con_autoservicio(self.s, "VEND-6", fecha_ingreso=INGRESO, quien="VEND-1")
        vs.generar_periodos(self.s, "VEND-6", hoy=HOY)
        s = vs.pedir(self.s, employee_code="VEND-6", nombre="Nayeli", desde=LUNES, hasta=DOMINGO, hoy=HOY)
        self.assertEqual(s.dias, 2)
        vs.aprobar(self.s, s.id, quien="VEND-1", hoy=HOY)
        params = ParametrosCaja(sueldo_base=Decimal("1300"), tarifa_comision=Decimal("2"),
                                descuento_falta=Decimal("200"))
        detalle = calcular_pago(cargar_horario(self.s, "VEND-6"), comisiones=0, params=params, hasta=DOMINGO)
        self.assertEqual(detalle.dias_trabajados, 2)


class SoloDanielPorAhoraTests(_Base):
    """Daniel, 2026-10-12: las vacaciones las gestiona él desde su Libreta y las
    va abriendo a cada empleada conforme vea que no hay fallos."""

    def setUp(self) -> None:
        super().setUp()
        vs.capturar_expediente(self.s, "VEND-3", fecha_ingreso=INGRESO, quien="VEND-1")
        vs.generar_periodos(self.s, "VEND-3", hoy=HOY)
        self.s.commit()

    def test_sin_autoservicio_ella_no_puede_pedir_por_ningun_lado(self) -> None:
        with self.assertRaises(vs.NoSePuede) as e:
            self._pedir(code="VEND-3")
        self.assertIn("Daniel", str(e.exception))
        self.assertEqual(self.s.scalars(select(SolicitudVacaciones)).all(), [])

    def test_daniel_las_registra_y_quedan_aprobadas_al_momento(self) -> None:
        s = vs.registrar_por_dueno(self.s, employee_code="VEND-3", nombre="Evelyn", desde=LUNES,
                                   hasta=DOMINGO, quien="VEND-1", hoy=HOY)
        self.assertEqual((s.estado, s.origen, s.resuelto_por), (vs.APROBADO, "libreta", "VEND-1"))
        self.assertEqual(len(self._vac("VEND-3")), 6)   # Evelyn descansa el sábado
        self.assertEqual(vs.saldo(self.s, "VEND-3", periodo_id=s.periodo_id).reservado, 6)
        self.assertEqual(len(vs.primas_pendientes(self.s)), 1)

    def test_nadie_mas_registra_ni_abre_el_autoservicio(self) -> None:
        with self.assertRaises(vs.NoSePuede):
            vs.registrar_por_dueno(self.s, employee_code="VEND-3", nombre="x", desde=LUNES,
                                   hasta=DOMINGO, quien="ENC-1", hoy=HOY)
        with self.assertRaises(vs.NoSePuede):
            vs.habilitar_autoservicio(self.s, "VEND-3", True, quien="VEND-3")

    def test_daniel_no_queda_atado_a_la_anticipacion(self) -> None:
        from unittest import mock

        with mock.patch.object(vs, "ANTICIPACION_VACACIONES_DIAS", 30):
            s = vs.registrar_por_dueno(self.s, employee_code="VEND-3", nombre="x", desde=LUNES,
                                       hasta=DOMINGO, quien="VEND-1", hoy=HOY)
        self.assertEqual(s.estado, vs.APROBADO)

    def test_las_mismas_validaciones_aplican_a_daniel(self) -> None:
        marcar_dia(self.s, "VEND-3", LUNES, "falta", actor="VEND-1")
        with self.assertRaises(vs.NoSePuede):
            vs.registrar_por_dueno(self.s, employee_code="VEND-3", nombre="x", desde=LUNES,
                                   hasta=DOMINGO, quien="VEND-1", hoy=HOY)

    def test_abrirle_el_autoservicio_queda_en_la_bitacora(self) -> None:
        from pos_uniformes.database.models import AuditoriaAusencias

        vs.habilitar_autoservicio(self.s, "VEND-3", True, quien="VEND-1")
        self.assertIsNotNone(self._pedir(code="VEND-3"))
        ops = [a.operacion for a in self.s.scalars(select(AuditoriaAusencias).where(
            AuditoriaAusencias.employee_code == "VEND-3")).all()]
        self.assertIn("vacaciones:autoservicio", ops)

    def test_el_panel_lista_al_equipo_sin_el_dueno(self) -> None:
        self.s.add(Empleada(codigo="VEND-1", nombre_completo="Daniel", activo=True))
        self.s.commit()
        codes = [c for c, _n, _e in vs.equipo(self.s, hoy=HOY)]
        self.assertEqual(sorted(codes), ["VEND-3", "VEND-5"])


class ExpedienteTests(_Base):
    def test_sin_fecha_de_ingreso_queda_pendiente_de_completar(self) -> None:
        e = vs.expediente(self.s, "VEND-3", hoy=HOY)
        self.assertFalse(e.completo)
        self.assertIn("fecha de ingreso verificada", e.falta)
        self.assertEqual(e.periodos, [])

    def test_expediente_completo(self) -> None:
        s = self._pedir()
        e = vs.expediente(self.s, "VEND-5", hoy=HOY)
        self.assertTrue(e.completo)
        self.assertEqual(e.anios_cumplidos, 2)
        self.assertEqual([p.periodo.dias_correspondientes for p in e.periodos], [12, 14])
        self.assertEqual(e.periodos[0].pedidos, 6)
        self.assertEqual(e.solicitudes, [s])

    def test_antiguedad_reconocida_cuenta_desde_antes(self) -> None:
        _con_autoservicio(self.s, "VEND-3", fecha_ingreso=date(2026, 1, 10), quien="VEND-1",
                               antiguedad_desde=date(2022, 1, 10))
        nuevos = vs.generar_periodos(self.s, "VEND-3", hoy=HOY)
        self.assertEqual([p.dias_correspondientes for p in nuevos], [12, 14, 16, 18])

    def test_condiciones_especiales_se_senalan_no_se_sustituyen(self) -> None:
        _con_autoservicio(self.s, "VEND-3", fecha_ingreso=INGRESO, quien="VEND-1",
                               condiciones_especiales="contrato: 15 días desde el primer año")
        self.assertIn("revisar", vs.expediente(self.s, "VEND-3", hoy=HOY).revisar)

    def test_la_fecha_no_se_mueve_si_ya_hay_periodos(self) -> None:
        with self.assertRaises(vs.NoSePuede):
            _con_autoservicio(self.s, "VEND-5", fecha_ingreso=date(2023, 1, 1), quien="VEND-1")

    def test_art_78_se_informa(self) -> None:
        s = self._pedir()
        vs.aprobar(self.s, s.id, quien="VEND-1", hoy=HOY)
        p = vs.expediente(self.s, "VEND-5", hoy=HOY).periodos[0]
        self.assertEqual(p.continuo_max, 6)
        self.assertFalse(p.cumple_art_78)     # se le dice, no se le prohíbe


class PrimaTests(_Base):
    def _aprobada(self):
        s = self._pedir()
        vs.aprobar(self.s, s.id, quien="VEND-1", hoy=HOY)
        return s

    def test_26_al_aprobar_queda_pendiente_con_su_calculo(self) -> None:
        s = self._aprobada()
        [p] = vs.primas_pendientes(self.s)
        self.assertEqual((p.solicitud_id, p.dias, p.monto), (s.id, 6, vs.prima_vacacional(Decimal("1300"), 6)))
        self.assertEqual(p.salario_diario, Decimal("185.71"))

    def test_se_paga_una_sola_vez(self) -> None:
        self._aprobada()
        [p] = vs.primas_pendientes(self.s)
        vs.marcar_prima_pagada(self.s, p.id, quien="VEND-1")
        with self.assertRaises(vs.NoSePuede):
            vs.marcar_prima_pagada(self.s, p.id, quien="VEND-1")
        self.assertEqual(vs.primas_pendientes(self.s), [])

    def test_solo_quien_paga_la_marca(self) -> None:
        self._aprobada()
        [p] = vs.primas_pendientes(self.s)
        with self.assertRaises(vs.NoSePuede):
            vs.marcar_prima_pagada(self.s, p.id, quien="VEND-5")

    def test_cancelada_antes_de_disfrutar_se_cancela_la_prima(self) -> None:
        s = self._aprobada()
        vs.cancelar(self.s, s.id, quien="VEND-1", hoy=HOY)
        p = self.s.scalars(select(vs.PrimaVacacional)).one()
        self.assertEqual(p.estado, vs.PRIMA_CANCELADA)

    def test_consumo_parcial_ajusta_la_prima_pendiente(self) -> None:
        s = self._aprobada()
        vs.cancelar(self.s, s.id, quien="VEND-1", hoy=LUNES + timedelta(days=3), motivo="regresó")
        p = self.s.scalars(select(vs.PrimaVacacional)).one()
        self.assertEqual((p.estado, p.dias), (vs.PRIMA_PENDIENTE, 3))

    def test_si_ya_se_pago_no_se_toca_y_se_avisa(self) -> None:
        s = self._aprobada()
        [p] = vs.primas_pendientes(self.s)
        vs.marcar_prima_pagada(self.s, p.id, quien="VEND-1")
        vs.cancelar(self.s, s.id, quien="VEND-1", hoy=LUNES + timedelta(days=3), motivo="regresó")
        self.assertEqual((p.estado, p.dias), (vs.PRIMA_PAGADA, 6))
        self.assertIn("Revisar", p.nota)

    def test_conciliacion_con_nomina(self) -> None:
        s = self._aprobada()
        [c] = vs.conciliacion_nomina(self.s, LUNES, DOMINGO)
        self.assertEqual(len(c.dias_vacaciones), 6)
        self.assertEqual(c.faltas_en_vacaciones, [])
        self.assertEqual(c.primas_pendientes, s.prima_estimada)


class RespuestaTests(_Base):
    def test_ella_ve_la_respuesta_hasta_que_la_lee(self) -> None:
        s = self._pedir()
        vs.rechazar(self.s, s.id, quien="VEND-1", respuesta="Temporada alta")
        [r] = vs.respuestas_sin_ver(self.s, "VEND-5")
        self.assertIn("Temporada alta", vs.texto_de_respuesta(r))
        vs.marcar_vista(self.s, r.id, "VEND-5")
        self.assertEqual(vs.respuestas_sin_ver(self.s, "VEND-5"), [])

    def test_fallo_al_aprobar_no_deja_nada(self) -> None:
        from unittest import mock

        from pos_uniformes.services import auditoria_ausencias_service as aud

        s = self._pedir()
        self.s.commit()
        real = aud.registrar

        def _falla(session, **kw):
            if kw.get("operacion") == "vacaciones:aprobado":
                raise RuntimeError("se fue la luz")
            return real(session, **kw)

        with mock.patch.object(aud, "registrar", _falla):
            with self.assertRaises(RuntimeError):
                vs.aprobar(self.s, s.id, quien="VEND-1", hoy=HOY)
        self.s.rollback()
        self.s.expire_all()
        self.assertEqual(self.s.get(SolicitudVacaciones, s.id).estado, vs.PEDIDO)
        self.assertEqual(self._vac(), [])
        self.assertEqual(vs.saldo(self.s, "VEND-5").reservado, 0)
        self.assertEqual(vs.primas_pendientes(self.s), [])

    def test_no_se_pide_mas_de_lo_que_hay_entre_pedidas(self) -> None:
        """Lo pedido aparta: dos pedidas no pueden pasar del saldo."""
        self._pedir(desde=LUNES, hasta=LUNES + timedelta(days=12))         # 11 laborables del año 1 (12)
        s2 = self._pedir(desde=LUNES + timedelta(days=21), hasta=LUNES + timedelta(days=22))
        anio2 = self.s.scalars(select(PeriodoVacaciones).where(PeriodoVacaciones.anio_servicio == 2)).one()
        self.assertEqual(s2.periodo_id, anio2.id)   # ya no cabía en el año 1


if __name__ == "__main__":
    unittest.main()
