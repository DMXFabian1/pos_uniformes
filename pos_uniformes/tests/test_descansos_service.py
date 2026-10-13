"""Descansos: el modelo antiguo (Calendario) y la Libreta, con las mismas reglas.

Reglas del autoservicio antiguo, que se conservan (Daniel, 2026-10-12):
7 días de anticipación, nadie más descansando ese día, 2 cambios al mes,
el descanso de la semana se MUEVE (si no había, se otorga), intercambio con
gafete. Correcciones mínimas autorizadas: D2 (tope por mes del día y no se
devuelve al borrar), D3 (semana con dos descansos: no se mueve uno solo),
D4 (intercambio en la misma semana). Mejoras: transacción única, solicitud
ligada a sus eventos, bitácora, botones viejos sin efecto, vencimiento.

Cada prueba revisa la BASE (eventos, estados, bitácora), no solo mensajes.
"""

from __future__ import annotations

import unittest
from datetime import date, datetime, timedelta, timezone
from unittest import mock

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import (
    AuditoriaAusencias,
    Empleada,
    EmpleadaEvento,
    EmpleadaHorario,
    SolicitudDescanso,
)
from pos_uniformes.services import descansos_service as ds
from pos_uniformes.services.calendario_empleadas_service import (
    DESCANSO,
    FALTA,
    PAGO,
    TRABAJO,
    aplicar_intercambio,
    aplicar_solicitud_descanso,
    cambios_del_mes,
    cargar_horario,
    cargar_horarios_todos,
    estado_del_dia,
    faltas_netas_en_rango,
    marcar_dia,
    quienes_descansan,
    quitar_marca,
)

HOY = date(2026, 10, 5)              # lunes
LUNES = date(2026, 10, 12)
MARTES = date(2026, 10, 13)          # descanso fijo de Daniel (VEND-1)
MIERCOLES = date(2026, 10, 14)       # 9 días después de HOY
JUEVES = date(2026, 10, 15)
SABADO = date(2026, 10, 17)          # descanso fijo de Evelyn
DOMINGO = date(2026, 10, 18)         # descanso fijo de Cristal


class _Base(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.s = Session(engine)
        self.s.add(Empleada(codigo="VEND-1", nombre_completo="Daniel Fabián", activo=True))
        self.s.add(Empleada(codigo="VEND-5", nombre_completo="Cristal Torres", activo=True))
        self.s.add(Empleada(codigo="VEND-3", nombre_completo="Evelyn Ortiz", activo=True))
        self.s.add(EmpleadaHorario(employee_code="VEND-1", descanso_weekday=1))
        self.s.add(EmpleadaHorario(employee_code="VEND-5", descanso_weekday=6,
                                   fecha_ultimo_pago=date(2026, 10, 3)))
        self.s.add(EmpleadaHorario(employee_code="VEND-3", descanso_weekday=5,
                                   fecha_ultimo_pago=date(2026, 10, 1)))
        self.s.commit()

    def tearDown(self) -> None:
        self.s.close()

    # Libreta (Daniel aprueba)
    def _pedir(self, fecha=MIERCOLES, motivo="Escuela", code="VEND-5", hoy=HOY):
        return ds.pedir(self.s, employee_code=code, nombre=code, fecha=fecha, motivo=motivo, hoy=hoy)

    def _aprobar(self, s, hoy=HOY):
        return ds.aprobar(self.s, s.id, quien="VEND-1", hoy=hoy)

    # Calendario (autoservicio)
    def _auto(self, fecha=MIERCOLES, code="VEND-5", hoy=HOY):
        return aplicar_solicitud_descanso(self.s, cargar_horarios_todos(self.s), code, fecha, hoy)

    def _eventos(self, code="VEND-5") -> dict[date, str]:
        return {e.fecha: e.tipo for e in self.s.scalars(
            select(EmpleadaEvento).where(EmpleadaEvento.employee_code == code)).all()}

    def _descansos_semana(self, code="VEND-5", fecha=MIERCOLES) -> list[date]:
        h = cargar_horario(self.s, code)
        lunes = fecha - timedelta(days=fecha.weekday())
        return [lunes + timedelta(days=i) for i in range(7)
                if estado_del_dia(h, lunes + timedelta(days=i)) == DESCANSO]

    def _estado(self, sid) -> str:
        self.s.expire_all()
        return self.s.get(SolicitudDescanso, sid).estado


class AutoservicioComoAntesTests(_Base):
    """El Calendario aprueba solo, con las reglas, como siempre."""

    def test_aprueba_solo_y_mueve_el_fijo(self) -> None:
        ok, msg = self._auto()
        self.assertTrue(ok, msg)
        self.assertIn("trabajas el 18/Oct", msg)
        self.assertEqual(self._descansos_semana(), [MIERCOLES])

    def test_queda_como_solicitud_aprobada_por_las_reglas_y_ligada(self) -> None:
        self._auto()
        s = self.s.scalars(select(SolicitudDescanso)).one()
        self.assertEqual((s.estado, s.resuelto_por, s.origen), (ds.APROBADO, ds.REGLAS, "calendario"))
        ligados = self.s.scalars(select(EmpleadaEvento).where(EmpleadaEvento.solicitud_id == s.id)).all()
        self.assertEqual({e.fecha for e in ligados}, {MIERCOLES, DOMINGO})
        self.assertEqual(ds.respuestas_sin_ver(self.s, "VEND-5"), [])   # ya vio el «Listo»

    def test_sin_anticipacion_no(self) -> None:
        ok, msg = self._auto(fecha=HOY + timedelta(days=6))
        self.assertFalse(ok)
        self.assertIn("7 días", msg)
        self.assertEqual(self._eventos(), {})

    def test_cupo_como_antes_cuenta_a_cualquiera_que_descanse(self) -> None:
        """D1 no se corrigió (Daniel): el martes de Daniel sigue ocupando el día."""
        ok, msg = self._auto(fecha=MARTES)
        self.assertFalse(ok)
        self.assertIn("VEND-1", msg)
        ok, msg = self._auto(fecha=SABADO)
        self.assertFalse(ok)
        self.assertIn("VEND-3", msg)

    def test_semana_sin_descanso_se_otorga_como_antes(self) -> None:
        marcar_dia(self.s, "VEND-5", DOMINGO, TRABAJO, actor="VEND-1")   # vino en su domingo
        ok, msg = self._auto()
        self.assertTrue(ok, msg)
        self.assertEqual(self._descansos_semana(), [MIERCOLES])

    def test_dos_pedidos_en_la_misma_semana_no_dan_dos_descansos(self) -> None:
        """Como antes: el segundo mueve el descanso que ya se había movido."""
        self.assertTrue(self._auto()[0])
        ok, msg = self._auto(fecha=JUEVES)
        self.assertTrue(ok, msg)
        self.assertEqual(self._descansos_semana(), [JUEVES])

    def test_d3_semana_con_dos_descansos_se_rechaza(self) -> None:
        """El caso real de Cristal (5 y 8 de nov): antes movía uno y quedaban dos."""
        self.s.add(EmpleadaEvento(employee_code="VEND-5", fecha=JUEVES, tipo=DESCANSO,
                                  nota="pedido desde la Libreta"))
        self.s.commit()
        self.assertEqual(self._descansos_semana(), [JUEVES, DOMINGO])
        ok, msg = self._auto()
        self.assertFalse(ok)
        self.assertIn("2 descansos", msg)
        self.assertEqual(self._descansos_semana(), [JUEVES, DOMINGO])   # sin tocar

    def test_un_pago_en_el_dia_no_se_borra(self) -> None:
        self.s.add(EmpleadaEvento(employee_code="VEND-5", fecha=MIERCOLES, tipo=PAGO))
        self.s.commit()
        self.assertTrue(self._auto()[0])
        tipos = sorted(e.tipo for e in self.s.scalars(select(EmpleadaEvento).where(
            EmpleadaEvento.employee_code == "VEND-5", EmpleadaEvento.fecha == MIERCOLES)).all())
        self.assertEqual(tipos, [DESCANSO, PAGO])


class TopeMensualTests(_Base):
    def test_el_tercer_cambio_del_mes_no_entra(self) -> None:
        self.assertTrue(self._auto(fecha=date(2026, 10, 14))[0])
        self.assertTrue(self._auto(fecha=date(2026, 10, 22))[0])
        ok, msg = self._auto(fecha=date(2026, 10, 29))
        self.assertFalse(ok)
        self.assertIn("2 cambios", msg)

    def test_d2_cuenta_el_mes_del_dia_no_el_de_cuando_se_pidio(self) -> None:
        self.assertTrue(self._auto(fecha=date(2026, 10, 14))[0])
        self.assertTrue(self._auto(fecha=date(2026, 10, 22))[0])
        self.assertTrue(self._auto(fecha=date(2026, 11, 4))[0])   # noviembre, otro tope
        self.assertEqual(cambios_del_mes(self.s, "VEND-5", date(2026, 11, 1)), 1)

    def test_d2_quitar_el_dia_no_devuelve_el_cambio(self) -> None:
        self.assertTrue(self._auto(fecha=date(2026, 10, 14))[0])
        quitar_marca(self.s, "VEND-5", date(2026, 10, 14), actor="VEND-1")
        self.assertEqual(cambios_del_mes(self.s, "VEND-5", HOY), 1)

    def test_la_libreta_no_brinca_el_tope(self) -> None:
        """Antes lo aprobado por Telegram no contaba: era la vía para brincarlo."""
        self._aprobar(self._pedir(fecha=date(2026, 10, 14)))
        self.assertTrue(self._auto(fecha=date(2026, 10, 22))[0])
        with self.assertRaises(ds.NoSePuede):
            self._pedir(fecha=date(2026, 10, 29))
        self.assertFalse(self._auto(fecha=date(2026, 10, 29))[0])

    def test_lo_pedido_en_la_libreta_aparta_su_cambio(self) -> None:
        self._pedir(fecha=date(2026, 10, 14))
        self._pedir(fecha=date(2026, 10, 22))
        self.assertFalse(self._auto(fecha=date(2026, 10, 29))[0])

    def test_rechazado_cancelado_o_vencido_no_gasta(self) -> None:
        a = self._pedir(fecha=date(2026, 10, 14))
        b = self._pedir(fecha=date(2026, 10, 22))
        ds.rechazar(self.s, a.id, quien="VEND-1")
        ds.cancelar(self.s, b.id, quien="VEND-5")
        self.assertEqual(ds.cambios_usados(self.s, "VEND-5", (2026, 10)), 0)

    def test_los_del_autoservicio_viejo_tambien_cuentan(self) -> None:
        for f in (date(2026, 10, 22), date(2026, 10, 29)):
            self.s.add(EmpleadaEvento(employee_code="VEND-5", fecha=f, tipo=DESCANSO,
                                      nota="pedido desde la Libreta"))
        self.s.commit()
        self.assertFalse(self._auto()[0])

    def test_marcas_del_dueno_no_gastan(self) -> None:
        marcar_dia(self.s, "VEND-5", MIERCOLES, DESCANSO, actor="VEND-1")
        self.assertEqual(cambios_del_mes(self.s, "VEND-5", HOY), 0)


class IntercambioTests(_Base):
    """Cristal (domingo 18) y Evelyn (sábado 17) se cambian el descanso."""

    def _cambiar(self, mia=DOMINGO, suya=SABADO):
        return aplicar_intercambio(self.s, cargar_horarios_todos(self.s), "VEND-5", mia,
                                   "VEND-3", suya, HOY)

    def test_directo_con_gafete_como_antes_y_un_cambio_a_cada_una(self) -> None:
        ok, msg = self._cambiar()
        self.assertTrue(ok, msg)
        self.assertEqual(self._descansos_semana("VEND-5"), [SABADO])
        self.assertEqual(self._descansos_semana("VEND-3"), [DOMINGO])
        self.assertEqual(cambios_del_mes(self.s, "VEND-5", HOY), 1)
        self.assertEqual(cambios_del_mes(self.s, "VEND-3", HOY), 1)
        s = self.s.scalars(select(SolicitudDescanso)).one()
        self.assertEqual(len(self.s.scalars(select(EmpleadaEvento).where(
            EmpleadaEvento.solicitud_id == s.id)).all()), 4)

    def test_d4_dias_de_semanas_distintas_no(self) -> None:
        ok, msg = self._cambiar(suya=date(2026, 10, 24))
        self.assertFalse(ok)
        self.assertIn("misma semana", msg)
        self.assertEqual(self._eventos(), {})

    def test_si_la_companera_ya_no_tiene_cambios_no_queda_nada(self) -> None:
        for f in (date(2026, 10, 7), date(2026, 10, 28)):
            self.s.add(EmpleadaEvento(employee_code="VEND-3", fecha=f, tipo=DESCANSO,
                                      nota="pedido desde la Libreta"))
        self.s.commit()
        ok, msg = self._cambiar()
        self.assertFalse(ok)
        self.assertIn("VEND-3", msg)
        self.assertEqual(self._eventos("VEND-5"), {})

    def test_si_falla_a_la_mitad_no_queda_medio_intercambio(self) -> None:
        """Antes eran cuatro commits: un error dejaba a una cambiada y a la otra no."""
        real = ds._poner
        llamadas = []

        def _falla(session, code, *a, **k):
            llamadas.append(code)
            if len(llamadas) == 3:
                raise RuntimeError("se fue la luz")
            return real(session, code, *a, **k)

        with mock.patch.object(ds, "_poner", _falla):
            with self.assertRaises(RuntimeError):
                self._cambiar()
        self.assertEqual(self.s.scalars(select(EmpleadaEvento)).all(), [])
        self.assertEqual(self.s.scalars(select(SolicitudDescanso)).all(), [])


class LibretaTests(_Base):
    """La Libreta pide con las mismas reglas; Daniel aprueba por Telegram."""

    def test_pedir_no_toca_calendario_ni_nomina(self) -> None:
        antes = faltas_netas_en_rango(cargar_horario(self.s, "VEND-5"), LUNES, DOMINGO)
        s = self._pedir()
        self.assertEqual(s.estado, ds.PEDIDO)
        self.assertEqual(self._eventos(), {})
        self.assertEqual(faltas_netas_en_rango(cargar_horario(self.s, "VEND-5"), LUNES, DOMINGO), antes)

    def test_mismas_reglas_que_el_calendario(self) -> None:
        for fecha in (HOY + timedelta(days=6), MARTES, SABADO, DOMINGO):
            with self.assertRaises(ds.NoSePuede):
                self._pedir(fecha=fecha)

    def test_sin_motivo_no(self) -> None:
        with self.assertRaises(ds.NoSePuede):
            self._pedir(motivo=" ")

    def test_aprobar_aplica_completo_y_ligado(self) -> None:
        s = self._pedir(motivo="Doctor")
        self._aprobar(s)
        self.assertEqual(self._descansos_semana(), [MIERCOLES])
        ligados = self.s.scalars(select(EmpleadaEvento).where(EmpleadaEvento.solicitud_id == s.id)).all()
        self.assertIn("Doctor", next(e.nota for e in ligados if e.fecha == MIERCOLES))

    def test_al_aprobar_se_vuelve_a_mirar_el_cupo(self) -> None:
        """Mientras esperaba, Evelyn tomó ese día por el Calendario."""
        s = self._pedir()
        self.assertTrue(self._auto(code="VEND-3", fecha=MIERCOLES)[0])
        with self.assertRaises(ds.NoSePuede):
            self._aprobar(s)
        self.s.rollback()
        self.assertEqual(self._estado(s.id), ds.PEDIDO)

    def test_si_la_semana_cambio_mueve_el_descanso_que_tiene_hoy(self) -> None:
        s = self._pedir()
        self.assertTrue(self._auto(fecha=JUEVES)[0])     # por el Calendario movió al jueves
        self._aprobar(s)
        self.assertEqual(self._descansos_semana(), [MIERCOLES])

    def test_rechazar_no_toca_nada(self) -> None:
        s = self._pedir()
        ds.rechazar(self.s, s.id, quien="VEND-1", respuesta="Hay conteo")
        self.assertEqual(self._eventos(), {})

    def test_aprobar_dos_veces_no_duplica(self) -> None:
        s = self._pedir()
        self._aprobar(s)
        n = len(self.s.scalars(select(EmpleadaEvento)).all())
        with self.assertRaises(ds.NoSePuede):
            self._aprobar(s)
        self.assertEqual(len(self.s.scalars(select(EmpleadaEvento)).all()), n)

    def test_no_se_aprueba_un_dia_que_ya_paso(self) -> None:
        s = self._pedir()
        with self.assertRaises(ds.NoSePuede):
            self._aprobar(s, hoy=MIERCOLES + timedelta(days=1))

    def test_si_algo_falla_al_aprobar_no_queda_nada(self) -> None:
        s = self._pedir()
        self.s.commit()
        from pos_uniformes.services import auditoria_ausencias_service as aud

        real = aud.registrar

        def _falla(session, **kw):
            if kw.get("operacion") == "aprobado":
                raise RuntimeError("se fue la luz")
            return real(session, **kw)

        with mock.patch.object(aud, "registrar", _falla):
            with self.assertRaises(RuntimeError):
                self._aprobar(s)
        self.s.rollback()
        self.assertEqual(self._estado(s.id), ds.PEDIDO)
        self.assertEqual(self._eventos(), {})

    def test_vence_y_deja_de_bloquear(self) -> None:
        s = self._pedir()
        despues = MIERCOLES + timedelta(days=1)
        self.assertIsNone(ds.pendiente_de(self.s, "VEND-5", hoy=despues))
        ds.vencer_pendientes(self.s, hoy=despues)
        self.assertEqual(self._estado(s.id), ds.VENCIDO)
        self.assertEqual(ds.cambios_usados(self.s, "VEND-5", (2026, 10)), 0)

    def test_ella_ve_la_respuesta(self) -> None:
        s = self._pedir()
        ds.rechazar(self.s, s.id, quien="VEND-1", respuesta="Hay conteo")
        [r] = ds.respuestas_sin_ver(self.s, "VEND-5")
        self.assertIn("Hay conteo", ds.texto_de_respuesta(r, "VEND-5"))
        ds.marcar_vista(self.s, r.id, "VEND-5")
        self.assertEqual(ds.respuestas_sin_ver(self.s, "VEND-5"), [])


class RevocarYBitacoraTests(_Base):
    def test_quitar_el_dia_desde_el_calendario_revoca_y_regresa_el_fijo(self) -> None:
        self._auto()
        s = self.s.scalars(select(SolicitudDescanso)).one()
        quitar_marca(self.s, "VEND-5", MIERCOLES, actor="ENC-1", origen="calendario")
        self.assertEqual(self._estado(s.id), ds.REVOCADO)
        self.assertEqual(self._descansos_semana(), [DOMINGO])

    def test_cada_paso_queda_en_la_bitacora(self) -> None:
        self._auto()
        ops = [a.operacion for a in self.s.scalars(select(AuditoriaAusencias)).all()]
        self.assertEqual(ops, ["pedir", "aprobado"])

    def test_marca_administrativa_auditada(self) -> None:
        marcar_dia(self.s, "VEND-5", date(2026, 9, 30), FALTA, actor="VEND-1",
                   origen="calendario", nota="corrección")
        fila = self.s.scalars(select(AuditoriaAusencias)).one()
        self.assertEqual((fila.actor, fila.origen, fila.operacion), ("VEND-1", "calendario", "marcar_dia"))


class RecordatoriosTests(_Base):
    def test_recuerda_a_las_24_horas_y_nunca_aprueba(self) -> None:
        s = self._pedir()
        s.created_at = datetime(2026, 10, 5, 10, tzinfo=timezone.utc)
        self.s.flush()
        c = s.created_at
        self.assertEqual(ds.tarea_periodica(self.s, ahora=c + timedelta(hours=23)), [])
        self.assertEqual(len(ds.tarea_periodica(self.s, ahora=c + timedelta(hours=25))), 1)
        self.assertEqual(ds.tarea_periodica(self.s, ahora=c + timedelta(hours=26)), [])
        self.assertEqual(s.estado, ds.PEDIDO)

    def test_sin_internet_el_recordatorio_se_reintenta(self) -> None:
        from pos_uniformes.services import alertas_service

        s = self._pedir()
        s.created_at = datetime(2026, 10, 5, 10, tzinfo=timezone.utc)
        self.s.commit()
        c = s.created_at
        with mock.patch.object(ds, "_ahora", return_value=c + timedelta(hours=25)), \
             mock.patch.object(alertas_service, "encolar", return_value=False):
            self.assertEqual(alertas_service._descansos(self.s, lambda *a, **k: None), 0)
        self.s.rollback()
        self.s.expire_all()
        self.assertIsNone(self.s.get(SolicitudDescanso, s.id).ultimo_recordatorio_at)


class ConsistenciaTests(_Base):
    def test_calendario_celular_y_nomina_dicen_lo_mismo(self) -> None:
        s = self._pedir()
        self.assertNotIn("VEND-5", quienes_descansan(cargar_horarios_todos(self.s), MIERCOLES))
        self._aprobar(s)
        horarios = cargar_horarios_todos(self.s)
        self.assertIn("VEND-5", quienes_descansan(horarios, MIERCOLES))
        self.assertNotIn("VEND-5", quienes_descansan(horarios, DOMINGO))
        self.assertEqual(faltas_netas_en_rango(horarios["VEND-5"], LUNES, DOMINGO), 0)

    def test_descanso_y_pago_el_mismo_dia_no_se_pisan(self) -> None:
        dia = date(2026, 9, 17)
        self.s.add(EmpleadaEvento(employee_code="VEND-3", fecha=dia, tipo=PAGO))
        self.s.add(EmpleadaEvento(employee_code="VEND-3", fecha=dia, tipo=DESCANSO))
        self.s.commit()
        h = cargar_horario(self.s, "VEND-3")
        self.assertEqual(estado_del_dia(h, dia), DESCANSO)
        self.assertIn(dia, h.pagos)


class ContextoTests(_Base):
    def test_la_semana_trae_los_siete_dias_y_su_fijo_trabajando(self) -> None:
        s = self._pedir()
        semana = {d.fecha: d for d in ds.contexto_de(self.s, s).semana}
        self.assertEqual(len(semana), 7)
        self.assertTrue(semana[MIERCOLES].es_el_pedido)
        self.assertTrue(any("Cristal" in n or "VEND-5" in n for n in semana[DOMINGO].trabajan))


if __name__ == "__main__":
    unittest.main()
