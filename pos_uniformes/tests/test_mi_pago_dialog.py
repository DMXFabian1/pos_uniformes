"""💼 Mi pago (kiosko, solo VEND-1) y la pregunta del calendario del dueño
«¿Te lo pagamos o te lo guardamos?» (Daniel, 2026-11-19)."""

from __future__ import annotations

import os
import unittest
from contextlib import contextmanager
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QDate
from PyQt6.QtWidgets import QApplication, QMessageBox
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import Empleada, EmpleadaEvento, EmpleadaHorario
from pos_uniformes.services import pago_dueno_service as pd
from pos_uniformes.services.calendario_empleadas_service import DESCANSO, FALTA, TRABAJO
from pos_uniformes.ui.dialogs import mi_pago_dialog as mp

D = date
HOY = date.today()
# El martes más reciente (descanso del dueño), con la cuenta arrancando una semana antes.
MARTES = HOY - timedelta(days=(HOY.weekday() - 1) % 7)
INICIO = MARTES - timedelta(days=7)


def _base():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    fabrica = sessionmaker(bind=engine)
    with fabrica() as s:
        s.add(Empleada(codigo="VEND-1", nombre_completo="Daniel Fabian", activo=True))
        s.add(EmpleadaHorario(employee_code="VEND-1", descanso_weekday=1))
        s.commit()

    @contextmanager
    def sesion():
        s = fabrica()
        try:
            yield s
        finally:
            s.close()

    return engine, fabrica, sesion


def _desglose(**kw) -> pd.DesglosePago:
    datos = dict(
        fecha_programada=D(2026, 11, 21), numero=3, de=4, desde=D(2026, 11, 15), hasta=D(2026, 11, 21),
        base=Decimal("2500.00"), valor_dia=Decimal("385.00"),
    )
    datos.update(kw)
    return pd.DesglosePago(**datos)


class TextosTests(unittest.TestCase):
    def test_titulo_y_estados(self) -> None:
        p = _desglose()
        self.assertEqual(mp.titulo_pago(p), "3 de 4 · sáb 21-nov")
        self.assertEqual(mp.texto_estado(p, D(2026, 11, 19)), "Pendiente")
        self.assertEqual(mp.texto_estado(p, D(2026, 11, 21)), "Toca hoy")
        self.assertEqual(mp.texto_estado(p, D(2026, 11, 22)), "Atrasado")
        p.registro = pd.RegistroPago(D(2026, 11, 21), D(2026, 11, 20), Decimal("2500.00"))
        # El monto ya va en grande en la tarjeta: el chip solo dice cuándo.
        self.assertEqual(mp.texto_estado(p, D(2026, 11, 22)), "Pagado el 20-nov")

    def test_desglose_con_dias_de_mas_y_faltas(self) -> None:
        p = _desglose(
            dias_extra_pagados=[D(2026, 11, 17)],
            dias_extra_acumulados=[D(2026, 11, 18)], dias_extra_sin_decidir=[D(2026, 11, 18)],
            faltas_descontadas=[D(2026, 11, 20)], faltas_cubiertas=[D(2026, 11, 19)],
        )
        self.assertEqual(mp.texto_cubre(p), "Cubre del 15 al 21-nov")
        R = mp.Renglon
        self.assertEqual(mp.renglones_desglose(p), [
            R("Base", "$2,500", "base"),
            R("+ 1 día de más (17-nov)", "+$385", "suma"),
            R("− 1 falta (20-nov)", "−$385", "resta"),
            R("Falta cubierta con día a favor (19-nov)", "no se descuenta", "nota"),
            R("Día de más sin decidir (18-nov)", "se guarda", "nota"),
        ])
        self.assertEqual(mp.resumen_ajustes(p), "+1 día de más · 1 falta (−$385) · 1 falta cubierta")

    def test_desglose_simple_es_una_sola_linea(self) -> None:
        # Sin días de más ni faltas no hay nada que desglosar: basta «Cubre…».
        self.assertEqual(mp.renglones_desglose(_desglose()), [])
        self.assertEqual(mp.resumen_ajustes(_desglose()), "")

    def test_desglose_de_un_pago_con_monto_editado(self) -> None:
        p = _desglose(registro=pd.RegistroPago(D(2026, 11, 21), D(2026, 11, 21), Decimal("2400.00")))
        self.assertEqual([(r.texto, r.cifra) for r in mp.renglones_desglose(p)],
                         [("Base", "$2,500"), ("Calculado", "$2,500"), ("Pagado", "$2,400")])

    def test_rango_corto(self) -> None:
        self.assertEqual(mp.rango_corto(D(2026, 11, 15), D(2026, 11, 21)), "del 15 al 21-nov")
        self.assertEqual(mp.rango_corto(D(2026, 11, 29), D(2026, 12, 7)), "del 29-nov al 7-dic")
        # Sin cero a la izquierda: «del 1 al 7-nov», como se dice en la tienda.
        self.assertEqual(mp.rango_corto(D(2026, 11, 1), D(2026, 11, 7)), "del 1 al 7-nov")

    def test_tono_cuando_toca(self) -> None:
        self.assertEqual([mp.tono_cuando_toca(n) for n in (0, 1, 3, 4, 9)],
                         ["hoy", "pronto", "pronto", "luego", "luego"])

    def test_pasos_del_mes(self) -> None:
        # Cuenta desde el 19-nov; el 14 se registró aunque es de antes; hoy 21.
        p21 = _desglose()
        p28 = _desglose(fecha_programada=D(2026, 11, 28), numero=4, desde=D(2026, 11, 22), hasta=D(2026, 11, 28))
        pasos = mp.pasos_del_mes((7, 14, 21, 28), 2026, 11, [p21, p28], {D(2026, 11, 14)}, D(2026, 11, 21))
        self.assertEqual([(x.numero, x.fecha.day, x.estado) for x in pasos], [
            (1, 7, mp.ANTES), (2, 14, pd.PAGADO), (3, 21, pd.TOCA_HOY), (4, 28, pd.PENDIENTE),
        ])
        self.assertEqual(mp.resumen_del_mes(pasos), ("1 de 3 pagados", False))
        atrasado = mp.pasos_del_mes((7, 14, 21, 28), 2026, 11, [p21], set(), D(2026, 11, 23))
        self.assertEqual(atrasado[2].estado, pd.ATRASADO)

    def test_resumen_del_mes(self) -> None:
        P = mp.Paso
        todos = [P(i, D(2026, 12, 7 * i), pd.PAGADO) for i in range(1, 5)]
        self.assertEqual(mp.resumen_del_mes(todos), ("✓ Todos pagados", True))
        self.assertEqual(mp.resumen_del_mes([P(1, D(2026, 10, 7), mp.ANTES)]), ("", False))
        self.assertEqual(mp.resumen_del_mes([]), ("", False))

    def test_chip_del_dia_de_mas(self) -> None:
        sin = pd.DiaExtra(D(2026, 11, 17), pd.ACUMULAR, False)
        pagar = pd.DiaExtra(D(2026, 11, 10), pd.PAGAR, True)
        guardado = pd.DiaExtra(D(2026, 11, 3), pd.ACUMULAR, True)
        self.assertEqual([mp.estado_dia_extra(e) for e in (sin, pagar, guardado)],
                         ["sin_decidir", pd.PAGAR, pd.ACUMULAR])
        self.assertEqual([mp.texto_dia_extra(e) for e in (sin, pagar, guardado)],
                         ["Sin decidir · se guarda", "Se paga en su pago", "Guardado a favor"])
        # Con la fecha del pago que lo cubre, dice en cuál.
        self.assertEqual(mp.texto_dia_extra(pagar, D(2026, 11, 14)), "Se paga el 14-nov")
        self.assertEqual(mp.texto_dia_extra(guardado, D(2026, 11, 7)), "Guardado a favor")

    def test_ficha_del_ultimo_pago(self) -> None:
        self.assertEqual(mp.texto_ultimo_pago({}), ("Ninguno", "todavía no se registra ninguno"))
        tarde = pd.RegistroPago(D(2026, 11, 14), D(2026, 11, 19), Decimal("2500"))
        self.assertEqual(mp.texto_ultimo_pago({tarde.fecha_programada: tarde}),
                         ("19-nov", "fue el pago del 14-nov"))
        a_tiempo = pd.RegistroPago(D(2026, 11, 21), D(2026, 11, 21), Decimal("2500"))
        self.assertEqual(mp.texto_ultimo_pago({tarde.fecha_programada: tarde, a_tiempo.fecha_programada: a_tiempo}),
                         ("21-nov", "la última vez que te pagaron"))

    def test_texto_atraso(self) -> None:
        self.assertEqual([mp.texto_atraso(n) for n in (1, 5)], ["Atrasado 1 día", "Atrasado 5 días"])

    def test_dias_de_pago(self) -> None:
        self.assertEqual(mp.leer_dias_de_pago("7, 14, 21, 28"), (7, 14, 21, 28))
        self.assertEqual(mp.leer_dias_de_pago("28 14"), (14, 28))
        for malo in ("7, 31", "siete", ""):
            with self.assertRaises(ValueError):
                mp.leer_dias_de_pago(malo)


class MiPagoDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.engine, self.fabrica, self.sesion = _base()
        self.addCleanup(self.engine.dispose)

    def _dialogo(self, hoy=D(2026, 11, 19)) -> mp.MiPagoDialog:
        d = mp.MiPagoDialog(None, quien="VEND-1", session_factory=self.sesion, hoy=hoy)
        self.addCleanup(d.deleteLater)
        return d

    def test_sin_configuracion_lo_dice_y_se_puede_configurar(self) -> None:
        d = self._dialogo()
        # Sin cuenta: el aviso en lugar de la tarjeta grande, y la configuración abierta.
        self.assertFalse(d.vacio_config.isHidden())
        self.assertTrue(d.heroe.isHidden())
        self.assertFalse(d.config_box.isHidden())
        self.assertEqual(d.pagos, [])
        d.cfg_inicio.setDate(QDate(2026, 11, 19))
        d._guardar_config()
        self.assertTrue(d.vacio_config.isHidden())
        self.assertFalse(d.heroe.isHidden())
        self.assertEqual(d.heroe_titulo.text(), "3 de 4 · sáb 21-nov")
        self.assertEqual(d.heroe_monto.text(), "$2,500")
        self.assertEqual([p.fecha_programada for p in d.pagos], [D(2026, 11, 21), D(2026, 11, 28)])

    def test_fechas_de_pago_invalidas_no_se_guardan(self) -> None:
        d = self._dialogo()
        d.cfg_dias.setText("7, 30")
        with patch.object(QMessageBox, "warning") as aviso:
            d._guardar_config()
        aviso.assert_called_once()
        with self.sesion() as s:
            self.assertIsNone(pd.cargar_config(s))

    def test_el_caso_real_pago_2_de_4_y_deshacer(self) -> None:
        with self.sesion() as s:
            pd.guardar_config(s, fecha_inicio=D(2026, 11, 19))
        d = self._dialogo()
        self.assertTrue(d.registrar(D(2026, 11, 14), D(2026, 11, 19), None))
        self.assertEqual(d.stat_ultimo.text(), "19-nov")
        self.assertEqual(d.stat_ultimo.pie.text(), "fue el pago del 14-nov")
        # El 14 es de antes del inicio, pero se pagó: la tira lo marca pagado
        # y tiene su tarjeta, con «Deshacer pago».
        self.assertEqual([c.paso.estado for c in d.tira], [mp.ANTES, pd.PAGADO, pd.PENDIENTE, pd.PENDIENTE])
        self.assertEqual(sorted(d.tarjetas), [D(2026, 11, 14), D(2026, 11, 21), D(2026, 11, 28)])
        self.assertEqual(d.tarjetas[D(2026, 11, 14)].boton.text(), "Deshacer pago")
        self.assertEqual(d.tarjetas[D(2026, 11, 14)].boton.objectName(), "miPagoDeshacer")
        self.assertIn("Pago 2 de 4 guardado: $2,500", d.status.text())
        # Un monto editado
        self.assertTrue(d.registrar(D(2026, 11, 21), D(2026, 11, 19), Decimal("2400")))
        self.assertTrue(d.pagos[0].pagado)
        self.assertEqual(d.pagos[0].registro.monto, Decimal("2400.00"))
        self.assertTrue(d.deshacer(D(2026, 11, 21)))
        self.assertFalse(d.pagos[0].pagado)

    def test_la_tarjeta_pagada_muestra_lo_que_de_verdad_se_pago(self) -> None:
        with self.sesion() as s:
            pd.guardar_config(s, fecha_inicio=D(2026, 11, 19))
        d = self._dialogo()
        self.assertTrue(d.registrar(D(2026, 11, 21), D(2026, 11, 19), Decimal("2400")))
        tarjeta = d._pagos_box.itemAt(0).widget()
        self.assertEqual(tarjeta.monto.text(), "$2,400")
        self.assertIn(mp.Renglon("Calculado", "$2,500", "nota"), tarjeta.renglones)
        self.assertIn(mp.Renglon("Pagado", "$2,400", "base"), tarjeta.renglones)
        # Sin pagar: la cifra grande es la calculada.
        self.assertEqual(d._pagos_box.itemAt(1).widget().monto.text(), "$2,500")

    def test_un_pago_futuro_avisa_y_no_se_guarda(self) -> None:
        with self.sesion() as s:
            pd.guardar_config(s, fecha_inicio=D(2026, 11, 19))
        d = self._dialogo()
        with patch.object(QMessageBox, "warning") as aviso:
            self.assertFalse(d.registrar(D(2026, 11, 21), D(2026, 11, 22), None))
        aviso.assert_called_once()

    def test_las_tarjetas_ofrecen_el_boton_correcto(self) -> None:
        with self.sesion() as s:
            pd.guardar_config(s, fecha_inicio=D(2026, 11, 19))
            pd.registrar_pago(s, D(2026, 11, 21), D(2026, 11, 19), None, "VEND-1", hoy=D(2026, 11, 19))
        d = self._dialogo()
        tarjetas = [d._pagos_box.itemAt(i).widget() for i in range(d._pagos_box.count())]
        self.assertEqual([t.boton.text() for t in tarjetas], ["Deshacer pago", "💵 Ya me pagaron"])

    def test_la_configuracion_se_pliega_si_ya_hay_cuenta(self) -> None:
        with self.sesion() as s:
            pd.guardar_config(s, fecha_inicio=D(2026, 11, 19))
        d = self._dialogo()
        self.assertTrue(d.config_box.isHidden())
        d.btn_config.click()
        self.assertFalse(d.config_box.isHidden())

    def test_la_tarjeta_grande_va_al_proximo_si_no_hay_atrasados(self) -> None:
        with self.sesion() as s:
            pd.guardar_config(s, fecha_inicio=D(2026, 11, 19))
        d = self._dialogo(hoy=D(2026, 11, 21))
        self.assertEqual(d.heroe_kicker.text(), "PRÓXIMO PAGO")
        self.assertEqual(d.heroe_titulo.text(), "3 de 4 · sáb 21-nov")
        self.assertEqual(d.heroe_cuando.text(), "Toca hoy")
        self.assertEqual(d.heroe_cuando.property("tono"), "hoy")
        self.assertEqual([c.property("destacado") for c in d.tira], ["false", "false", "true", "false"])

    def test_la_tarjeta_grande_y_las_fichas(self) -> None:
        with self.sesion() as s:
            pd.guardar_config(s, fecha_inicio=D(2026, 11, 1))
        d = self._dialogo(hoy=D(2026, 11, 19))
        # Con atrasados, arriba va el más viejo (y su botón lo registra).
        self.assertEqual(d.heroe_kicker.text(), "PAGO ATRASADO")
        self.assertEqual(d.heroe_titulo.text(), "1 de 4 · sáb 07-nov")
        self.assertEqual(d.heroe_cuando.text(), "Atrasado 12 días")
        self.assertEqual(d.heroe_cuando.property("tono"), "atrasado")
        self.assertEqual([c.property("destacado") for c in d.tira], ["true", "false", "false", "false"])
        self.assertEqual(d.stat_ultimo.text(), "Ninguno")
        self.assertEqual(d.stat_atrasados.text(), "2")
        self.assertEqual(d.stat_atrasados.property("alerta"), "true")
        # Botón lleno en los atrasados; de contorno en los demás.
        nombres = [d._pagos_box.itemAt(i).widget().boton.objectName() for i in range(d._pagos_box.count())]
        self.assertEqual(nombres, ["miPagoPrimario", "miPagoPrimario", "miPagoChico", "miPagoChico"])
        with patch.object(mp.MiPagoDialog, "_ya_me_pagaron") as pagar:
            d.btn_heroe.click()
        pagar.assert_called_once_with(d.pago_heroe())
        self.assertEqual(d.pago_heroe().fecha_programada, D(2026, 11, 7))
        # Tocar un cuadro de la tira no truena (baja a su tarjeta).
        d.ir_a_tarjeta(D(2026, 11, 28))
        d._mover_mes(-1)
        self.assertEqual(d.mes_label.text(), "Octubre 2026")
        self.assertEqual([c.paso.estado for c in d.tira], [mp.ANTES] * 4)

    def test_cambiar_el_destino_de_un_dia_de_mas(self) -> None:
        with self.sesion() as s:
            pd.guardar_config(s, fecha_inicio=D(2026, 11, 19))
            s.add(EmpleadaEvento(employee_code="VEND-1", fecha=D(2026, 11, 24), tipo=TRABAJO))
            s.commit()
        d = self._dialogo(hoy=D(2026, 11, 25))
        self.assertEqual(len(d.extras), 1)
        self.assertTrue(d.extras[0].sin_decidir)
        d._decidir(D(2026, 11, 24), pd.PAGAR)
        self.assertEqual(d.extras[0].destino, pd.PAGAR)
        self.assertEqual(d.pagos[-1].monto, Decimal("2885.00"))

    def test_avisa_si_no_tiene_descanso_guardado(self) -> None:
        with self.sesion() as s:
            pd.guardar_config(s, fecha_inicio=D(2026, 11, 19))
        d = self._dialogo()
        self.assertTrue(d.aviso_descanso.isHidden())
        with self.sesion() as s:
            s.get(EmpleadaHorario, "VEND-1").descanso_weekday = None
            s.commit()
        d.recargar()
        self.assertFalse(d.aviso_descanso.isHidden())
        self.assertIn("descanso fijo no está guardado", d.aviso_descanso.text())

    def test_las_acciones_no_borran_la_configuracion_sin_guardar(self) -> None:
        with self.sesion() as s:
            pd.guardar_config(s, fecha_inicio=D(2026, 11, 19))
            s.add(EmpleadaEvento(employee_code="VEND-1", fecha=D(2026, 11, 24), tipo=TRABAJO))
            s.commit()
        d = self._dialogo(hoy=D(2026, 11, 25))
        self.assertEqual(d.cfg_monto.value(), 2500)
        d.cfg_monto.setValue(3000)
        d._decidir(D(2026, 11, 24), pd.PAGAR)
        d.registrar(D(2026, 11, 21), D(2026, 11, 25), None)
        d._mover_mes(1)
        self.assertEqual(d.cfg_monto.value(), 3000)
        d._guardar_config()
        with self.sesion() as s:
            self.assertEqual(pd.cargar_config(s).monto_por_pago, Decimal("3000.00"))
        self.assertEqual(d.cfg_monto.value(), 3000)

    def test_sin_conexion_no_invita_a_configurar(self) -> None:
        def falla():
            raise OSError("sin red")

        d = mp.MiPagoDialog(None, quien="VEND-1", session_factory=falla, hoy=D(2026, 11, 19))
        self.addCleanup(d.deleteLater)
        self.assertTrue(d.config_box.isHidden())
        self.assertTrue(d.btn_config.isHidden())
        self.assertFalse(d.btn_guardar_config.isEnabled())
        self.assertIn("Sin conexión", d.vacio_titulo.text())
        self.assertIn("Sin conexión", d.status.text())

    def test_si_se_cae_la_conexion_despues_se_queda_lo_que_se_veia(self) -> None:
        with self.sesion() as s:
            pd.guardar_config(s, fecha_inicio=D(2026, 11, 19))
        d = self._dialogo()
        self.assertFalse(d.heroe.isHidden())

        def falla():
            raise OSError("sin red")

        d._sf = falla
        d.recargar()
        self.assertFalse(d.heroe.isHidden())
        self.assertTrue(d.vacio_config.isHidden())
        self.assertFalse(d.btn_guardar_config.isEnabled())
        self.assertIn("Sin conexión", d.status.text())

    def test_solo_el_dueno(self) -> None:
        with patch.object(QMessageBox, "information") as aviso, patch.object(mp.MiPagoDialog, "exec") as exe:
            self.assertFalse(mp.abrir_mi_pago(None, "VEND-4"))
            aviso.assert_called_once()
            exe.assert_not_called()
        with patch("pos_uniformes.database.connection.get_session", self.sesion), \
                patch.object(mp.MiPagoDialog, "exec") as exe:
            self.assertTrue(mp.abrir_mi_pago(None, "vend-1"))
            exe.assert_called_once()


class PreguntaDelCalendarioTests(unittest.TestCase):
    """`despues_de_marcar_dueno`: lo que el calendario llama tras marcar un día del dueño."""

    def setUp(self) -> None:
        self.engine, self.fabrica, self.sesion = _base()
        self.addCleanup(self.engine.dispose)
        with self.sesion() as s:
            pd.guardar_config(s, fecha_inicio=D(2026, 11, 19))
        self.preguntas = []

    def _marcar(self, fecha, tipo) -> None:
        from pos_uniformes.services.calendario_empleadas_service import marcar_dia

        with self.sesion() as s:
            marcar_dia(s, "VEND-1", fecha, tipo, actor="VEND-1")

    def _despues(self, fecha, tipo, respuesta):
        def preguntar(parent, f, valor_dia, actual):
            self.preguntas.append((f, valor_dia, actual))
            return respuesta

        return mp.despues_de_marcar_dueno(None, fecha, tipo, session_factory=self.sesion, preguntar=preguntar)

    def _decision(self, fecha):
        with self.sesion() as s:
            return pd.decision_dia_extra(s, fecha)

    def test_trabajo_en_su_descanso_pregunta_y_guarda(self) -> None:
        self._marcar(D(2026, 11, 24), TRABAJO)
        self.assertEqual(self._despues(D(2026, 11, 24), TRABAJO, pd.PAGAR), pd.PAGAR)
        self.assertEqual(self.preguntas, [(D(2026, 11, 24), Decimal("385.00"), None)])
        self.assertEqual(self._decision(D(2026, 11, 24)), pd.PAGAR)

    def test_luego_lo_deja_sin_decidir(self) -> None:
        self._marcar(D(2026, 11, 24), TRABAJO)
        self.assertIsNone(self._despues(D(2026, 11, 24), TRABAJO, None))
        self.assertIsNone(self._decision(D(2026, 11, 24)))

    def test_trabajo_en_dia_normal_no_pregunta(self) -> None:
        self._marcar(D(2026, 11, 25), TRABAJO)        # miércoles
        self.assertIsNone(self._despues(D(2026, 11, 25), TRABAJO, pd.PAGAR))
        self.assertEqual(self.preguntas, [])

    def test_quitar_la_marca_borra_la_decision(self) -> None:
        from pos_uniformes.services.calendario_empleadas_service import quitar_marca

        self._marcar(D(2026, 11, 24), TRABAJO)
        self._despues(D(2026, 11, 24), TRABAJO, pd.PAGAR)
        with self.sesion() as s:
            quitar_marca(s, "VEND-1", D(2026, 11, 24), actor="VEND-1")
        self.assertIsNone(self._despues(D(2026, 11, 24), "", pd.PAGAR))
        self.assertIsNone(self._decision(D(2026, 11, 24)))

    def test_cambiarlo_a_falta_borra_la_decision(self) -> None:
        self._marcar(D(2026, 11, 24), TRABAJO)
        self._despues(D(2026, 11, 24), TRABAJO, pd.ACUMULAR)
        self._marcar(D(2026, 11, 24), FALTA)
        self._despues(D(2026, 11, 24), FALTA, pd.PAGAR)
        self.assertIsNone(self._decision(D(2026, 11, 24)))

    def test_sin_cuenta_no_pregunta(self) -> None:
        with self.sesion() as s:
            pd.guardar_config(s, fecha_inicio=D(2026, 11, 19), activo=False)
        self._marcar(D(2026, 11, 24), TRABAJO)
        self.assertIsNone(self._despues(D(2026, 11, 24), TRABAJO, pd.PAGAR))
        self.assertEqual(self.preguntas, [])


class CalendarioDelDuenoTests(unittest.TestCase):
    """En el calendario, eligiendo a VEND-1: «Sí trabajó» en su martes pregunta."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from pos_uniformes.ui.dialogs import calendario_empleadas_dialog as cal

        self.engine, self.fabrica, self.sesion = _base()
        self.addCleanup(self.engine.dispose)
        with self.fabrica() as s:
            s.add(Empleada(codigo="VEND-4", nombre_completo="Stayce Chavarria", activo=True))
            s.add(EmpleadaHorario(employee_code="VEND-4", descanso_weekday=1))
            s.commit()
            pd.guardar_config(s, fecha_inicio=INICIO)
        parches = [
            patch("pos_uniformes.database.connection.get_session", self.sesion),
            patch("pos_uniformes.services.satellite_startup_service.probe_database_host", return_value=True),
        ]
        for p in parches:
            p.start()
        self.addCleanup(lambda: [p.stop() for p in parches])
        self.d = cal.CalendarioEmpleadasDialog(None, employee_code="VEND-1", employee_name="Daniel", is_owner=True)
        self.addCleanup(self.d.deleteLater)

    def _elegir(self, code: str, dia: date) -> None:
        self.d._combo.setCurrentIndex(self.d._combo.findData(code))
        self.d.cal.setSelectedDate(QDate(dia.year, dia.month, dia.day))

    def test_si_trabajo_en_su_martes_pregunta_y_guarda(self) -> None:
        self._elegir("VEND-1", MARTES)
        with patch.object(mp, "preguntar_destino", return_value=pd.ACUMULAR) as preguntar:
            self.d._marcar(TRABAJO)
        preguntar.assert_called_once()
        with self.sesion() as s:
            self.assertEqual(pd.decision_dia_extra(s, MARTES), pd.ACUMULAR)
        with patch.object(mp, "preguntar_destino") as preguntar:
            self.d._quitar()
        preguntar.assert_not_called()
        with self.sesion() as s:
            self.assertIsNone(pd.decision_dia_extra(s, MARTES))

    def test_otra_empleada_no_pregunta(self) -> None:
        self._elegir("VEND-4", MARTES)
        with patch.object(mp, "preguntar_destino") as preguntar:
            self.d._marcar(TRABAJO)
        preguntar.assert_not_called()

    def test_descanso_del_dueno_no_pregunta(self) -> None:
        self._elegir("VEND-1", MARTES + timedelta(days=1) if MARTES + timedelta(days=1) <= HOY else MARTES)
        with patch.object(mp, "preguntar_destino") as preguntar:
            self.d._marcar(DESCANSO)
        preguntar.assert_not_called()


if __name__ == "__main__":
    unittest.main()
