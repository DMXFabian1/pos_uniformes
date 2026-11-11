"""E5-A (Daniel, 2026-11-10): el Monedero abona el % del programa del cliente
(Club 5, Leal 10, Profesional 13, Mayorista 15; sin programa, nada), Club
sube solo a Leal con el gasto del año, y el % se edita en Programas con
bitácora.

Base local de prueba (`pos_uniformes_test`), en una transacción que se revierte.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch

from sqlalchemy import select

from pos_uniformes.database.models import ConfiguracionNegocio, Membresia, MonederoConfig, MonederoMovimiento
from pos_uniformes.services import libreta_service as lib
from pos_uniformes.services import monedero_service as mon
from pos_uniformes.services.fidelizacion import admin_programas_service as aps
from pos_uniformes.services.fidelizacion import membresia_service as ms
from pos_uniformes.services.fidelizacion import subida_leal_service as leal
from pos_uniformes.tests.test_e4a_membresias import _Base

D = Decimal


class _Monedero(_Base):
    def setUp(self) -> None:
        super().setUp()
        self._encender()
        stock = patch.object(lib, "descontar_stock", return_value=0)
        stock.start()
        self.addCleanup(stock.stop)
        # Las reglas de Leal no dependen de lo que tenga la base de prueba.
        self._reglas_reales = leal.reglas
        reglas = patch.object(leal, "reglas", return_value=(D("3000.00"), 365))
        reglas.start()
        self.addCleanup(reglas.stop)

    def _encender(self, habilitado=True) -> None:
        self.s.add(MonederoConfig(tasa_cashback=D("1"), habilitado=habilitado, usuario_id=self.admin.id,
                                  vigente_desde=datetime.now(timezone.utc) - timedelta(seconds=1)))
        self.s.flush()

    def _club(self, cliente=None) -> Membresia:
        return ms.inscribir_por_empleada(self.s, cliente_id=(cliente or self.cliente).id, programa_clave="CLUB",
                                         employee_code=self.lupita.codigo)

    def _aprobado(self, clave: str, cliente=None) -> Membresia:
        p = self._proponer(clave, cliente=cliente)
        return ms.aprobar_por_admin(self.s, p.id, usuario_id=self.admin.id)

    def _venta(self, total: str, cliente=None):
        return lib.registrar_operacion(
            self.s, employee_code=self.lupita.codigo, employee_name="Lupita", tipo="venta", items=[],
            monto_total=D(total), origen="Entrada", cliente_id=(cliente or self.cliente).id,
            operacion_uuid=str(uuid.uuid4()), created_at=datetime.now(timezone.utc),
        )

    def _cashback(self, venta) -> MonederoMovimiento | None:
        return self.s.scalars(select(MonederoMovimiento).where(
            MonederoMovimiento.libreta_venta_id == venta.id, MonederoMovimiento.tipo == mon.CASHBACK)).first()

    def _clave(self, cliente=None) -> str | None:
        activa = ms.estado_de_cliente(self.s, (cliente or self.cliente).id).activa
        return activa.programa.clave if activa else None


class TasaPorProgramaTests(_Monedero):
    def test_las_tasas_de_la_migracion(self) -> None:
        tasas = {clave: ms.programa_por_clave(self.s, clave).tasa_monedero
                 for clave in ("CLUB", "LEAL", "PROFESIONAL", "MAYORISTA")}
        self.assertEqual(tasas, {"CLUB": D("5"), "LEAL": D("10"), "PROFESIONAL": D("13"), "MAYORISTA": D("15")})
        self.assertEqual([c for c in tasas if ms.programa_por_clave(self.s, c).permite_descuento], ["MAYORISTA"])
        self.assertEqual(ms.programa_por_clave(self.s, "LEAL").ingreso_modo, "automatico")

    def test_sin_programa_no_hay_monedero(self) -> None:
        self.assertIsNone(mon.tasa_para_cliente(self.s, self.cliente.id))
        v = self._venta("500")
        self.assertIsNone(self._cashback(v))
        self.assertIsNone(mon.resumen_cliente(self.s, self.cliente.id).tasa)

    def test_club_abona_5(self) -> None:
        self._club()
        mov = self._cashback(self._venta("450"))
        self.assertEqual((mov.monto, mov.tasa_snapshot), (D("22.50"), D("5.00")))
        self.assertEqual(mon.resumen_cliente(self.s, self.cliente.id).tasa, D("5.00"))

    def test_profesional_13_y_mayorista_15(self) -> None:
        otro = self._cliente("Beto E5A")
        self._aprobado("PROFESIONAL")
        self._aprobado("MAYORISTA", cliente=otro)
        self.assertEqual(self._cashback(self._venta("1000")).monto, D("130.00"))
        self.assertEqual(self._cashback(self._venta("1000", cliente=otro)).monto, D("150.00"))

    def test_una_propuesta_pendiente_no_cambia_la_tasa(self) -> None:
        self._club()
        self._proponer("MAYORISTA")
        self.assertEqual(mon.tasa_para_cliente(self.s, self.cliente.id), D("5.00"))

    def test_monedero_apagado_no_abona_aunque_tenga_programa(self) -> None:
        self._club()
        self._encender(habilitado=False)
        self.assertIsNone(mon.tasa_para_cliente(self.s, self.cliente.id))
        self.assertIsNone(self._cashback(self._venta("450")))

    def test_rige_el_programa_que_tenia_al_comprar(self) -> None:
        club = self._club()
        antes = club.desde - timedelta(minutes=1)
        self.assertIsNone(mon.tasa_para_cliente(self.s, self.cliente.id, antes), "antes de inscribirse no tenía")
        self._aprobado("PROFESIONAL")
        self.s.refresh(club)
        self.assertEqual(mon.tasa_para_cliente(self.s, self.cliente.id, club.hasta - timedelta(microseconds=1)), D("5.00"))
        self.assertEqual(mon.tasa_para_cliente(self.s, self.cliente.id), D("13.00"))


class SubidaALealTests(_Monedero):
    def test_sube_al_juntar_3000_y_la_venta_que_cruza_abona_como_club(self) -> None:
        self._club()
        self._venta("2000")
        self.assertEqual(self._clave(), "CLUB")
        cruza = self._venta("1000")
        self.assertEqual(self._clave(), "LEAL")
        self.assertEqual(self._cashback(cruza).tasa_snapshot, D("5.00"))
        self.assertEqual(self._cashback(self._venta("100")).monto, D("10.00"))

    def test_deja_rastro(self) -> None:
        club = self._club()
        self._venta("3000")
        self.s.refresh(club)
        self.assertEqual(club.estado, ms.REEMPLAZADA)
        nueva = ms.estado_de_cliente(self.s, self.cliente.id).activa
        self.assertEqual(self._eventos(nueva), [leal.EV_SUBIDA_AUTOMATICA])
        self.assertEqual(self._eventos(club), [ms.EV_ALTA, ms.EV_REEMPLAZO])
        self.assertIsNotNone(nueva.avisada_at)

    def test_solo_cuenta_el_ultimo_año(self) -> None:
        self._club()
        vieja = self._venta("2900")
        vieja.created_at = datetime.now(timezone.utc) - timedelta(days=400)
        self.s.flush()
        self._venta("200")
        self.assertEqual(self._clave(), "CLUB")

    def test_apartados_no_cuentan(self) -> None:
        self._club()
        lib.registrar_operacion(self.s, employee_code=self.lupita.codigo, employee_name="Lupita", tipo="apartado",
                                items=[], monto_total=D("5000"), cliente_id=self.cliente.id,
                                created_at=datetime.now(timezone.utc))
        self.assertEqual(self._clave(), "CLUB")

    def test_profesional_y_mayorista_no_bajan_a_leal(self) -> None:
        self._aprobado("PROFESIONAL")
        self._venta("5000")
        self.assertEqual(self._clave(), "PROFESIONAL")

    def test_sin_programa_no_sube(self) -> None:
        self._venta("5000")
        self.assertIsNone(self._clave())

    def test_leal_pausado_no_sube_nadie(self) -> None:
        ms.programa_por_clave(self.s, "LEAL").estado = "pausado"
        self._club()
        self._venta("5000")
        self.assertEqual(self._clave(), "CLUB")

    def test_si_falla_la_venta_queda(self) -> None:
        self._club()
        with patch.object(leal, "subir_si_alcanza", side_effect=RuntimeError("boom")):
            v = self._venta("5000")
        self.assertIsNotNone(v.id)
        self.assertEqual(self._clave(), "CLUB")
        self.assertIsNotNone(self._cashback(v), "el cashback se queda")

    def test_las_reglas_salen_de_la_configuracion(self) -> None:
        config = self.s.scalar(select(ConfiguracionNegocio).limit(1))
        umbral, dias = self._reglas_reales(self.s)
        if config is None:
            self.assertEqual((umbral, dias), (D("3000.00"), 365))
        else:
            self.assertEqual((umbral, dias), (D(str(config.leal_spend_threshold)), int(config.loyalty_review_window_days)))


class EditarTasaTests(_Monedero):
    def _editar(self, clave="CLUB", **kw):
        p = ms.programa_por_clave(self.s, clave)
        return aps.editar_programa(self.s, usuario_id=self.admin.id, clave=clave, nombre=p.nombre,
                                   descripcion=p.descripcion or "", estado=p.estado, **kw)

    def test_cambia_y_deja_bitacora(self) -> None:
        self._editar(tasa="6.5")
        self.assertEqual(ms.programa_por_clave(self.s, "CLUB").tasa_monedero, D("6.50"))
        (cambio,) = aps.cambios_de_tasa(self.s, "CLUB")
        self.assertEqual((cambio.antes, cambio.despues, cambio.usuario_id), (D("5.00"), D("6.50"), self.admin.id))

    def test_sin_cambio_no_hay_bitacora(self) -> None:
        self._editar(tasa="5")
        self._editar()
        self.assertEqual(aps.cambios_de_tasa(self.s, "CLUB"), [])

    def test_fuera_de_rango(self) -> None:
        for malo in ("-1", "101", "cinco"):
            with self.subTest(malo=malo), self.assertRaises(ms.NoSePuede):
                self._editar(tasa=malo)

    def test_solo_admin(self) -> None:
        with self.assertRaises(PermissionError):
            aps.editar_programa(self.s, usuario_id=self.cajero.id, clave="CLUB", nombre="Maximoda Club",
                                descripcion="", estado="activo", tasa="7")

    def test_la_lista_muestra_el_porcentaje(self) -> None:
        filas = {f.clave: f.monedero for f in aps.listar_programas(self.s, usuario_id=self.admin.id)}
        self.assertEqual(filas, {"CLUB": "5 %", "LEAL": "10 %", "PROFESIONAL": "13 %", "MAYORISTA": "15 % o descuento"})

    def test_el_nuevo_porcentaje_aplica_desde_ya(self) -> None:
        self._club()
        self._editar(tasa="8")
        self.assertEqual(self._cashback(self._venta("100")).monto, D("8.00"))


class PantallaTests(_Monedero):
    @classmethod
    def setUpClass(cls) -> None:
        import os

        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def test_editar_ofrece_el_porcentaje(self) -> None:
        from pos_uniformes.ui.dialogs import programas_dialog as pd

        fila = next(f for f in aps.listar_programas(self.s, usuario_id=self.admin.id) if f.clave == "MAYORISTA")
        e = pd.EditarProgramaDialog(None, fila)
        self.addCleanup(e.deleteLater)
        self.assertEqual(e.tasa_input.value(), 15.0)
        e.guardar_button.click()
        self.assertIsNone(e.tasa_resultado, "sin tocarlo no hay cambio")
        e.tasa_input.setValue(14.5)
        e.guardar_button.click()
        self.assertEqual(e.tasa_resultado, 14.5)

    def test_el_kiosko_deja_proponer_desde_leal(self) -> None:
        from pos_uniformes.ui.helpers.quick_sale_programa_helper import estado_para_barra

        e = estado_para_barra(en_linea=True, activa="Maximoda Leal", activa_clave="LEAL", pendiente=None)
        self.assertEqual(e.texto, "★ Miembro Maximoda Leal")
        self.assertTrue(e.puede_proponer)
