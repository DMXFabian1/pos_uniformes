"""Compra a cuenta ligada por columnas y guardada en una sola transacción
(2026-11-12).

Antes la compra, su venta y su retiro se encontraban leyendo el texto del
motivo. Si la liga fallaba (folio nulo, venta fuera de la ventana) el retiro
salía del corte y la venta no: un faltante falso. Un retiro manual «Compra a
cuenta de bolsas» desaparecía del corte. Y el kiosko guardaba la compra y la
venta en dos transacciones.
"""

from __future__ import annotations

import os
import unittest
from datetime import date, datetime
from decimal import Decimal as D
from unittest.mock import patch

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import CajaRetiro, Empleada, LibretaVenta, PrestamoEmpleada
from pos_uniformes.services import compra_a_cuenta_service as cac
from pos_uniformes.services import corte_caja_service as cc
from pos_uniformes.services import prestamos_service as pr
from pos_uniformes.services import retiros_service as rs

SAB14 = date(2026, 11, 14)
FOLIO = "abcdef12-0000-4000-8000-000000000001"
DESDE, HASTA = datetime(2000, 1, 1), datetime(2100, 1, 1)


class _Base(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.s = Session(engine)
        self.s.add(Empleada(codigo="VEND-3", nombre_completo="Cristal", activo=True))
        self.s.flush()
        p = patch.object(pr, "ganado_hasta_hoy", return_value=D("2000"))
        p.start()
        self.addCleanup(p.stop)
        self.addCleanup(self.s.close)
        self.este = cac.opciones_de_pago(SAB14, 7)[0]

    def _venta(self, folio=FOLIO, monto="332"):
        from pos_uniformes.services import libreta_service as lib

        return lib.registrar_operacion(
            self.s, employee_code="VEND-3", employee_name="Cristal", tipo="venta",
            items=[{"sku": "S1", "nombre": "Pantalón", "precio": "369", "cantidad": 1}],
            monto_total=D(monto), descuento_empleada=True, compradora_code="VEND-3",
            operacion_uuid=folio,
        )

    def _compra(self, *, folio=FOLIO, venta=None, monto="332"):
        return cac.registrar(self.s, employee_code="VEND-3", nombre="Cristal", monto=monto,
                             opcion=self.este, quien="VEND-2", folio=folio, libreta_venta=venta)

    def _corte(self):
        ventas = [r.id for r in cc.operaciones_del_periodo(self.s, DESDE, HASTA)]
        retiros = [r.motivo for r in rs.retiros_del_periodo(self.s, DESDE, HASTA)]
        return ventas, retiros, rs.total_retiros(self.s, DESDE, HASTA)

    def _entrada(self, folio=FOLIO, monto="332", **extra):
        return {
            "employee_code": "VEND-2", "employee_name": "Fanny", "tipo": "venta", "cliente": None,
            "items": [{"sku": "S1", "nombre": "Pantalón", "talla": "8", "cantidad": 1, "precio": "369"}],
            "monto_total": monto, "monto_neto": monto, "pago_tarjeta": False, "descuento_empleada": True,
            "compradora_code": "VEND-3", "origen": "kiosko-1",
            "created_at": datetime.now().astimezone().isoformat(), "operacion_uuid": folio, **extra,
        }


class LigaPorColumnasTests(_Base):
    def test_la_compra_guarda_su_tipo_su_venta_y_su_retiro(self):
        venta = self._venta()
        p = self._compra()
        self.assertEqual((p.tipo, p.libreta_venta_id), (pr.TIPO_COMPRA, venta.id))
        retiro = self.s.scalars(select(CajaRetiro)).one()
        self.assertEqual((retiro.prestamo_id, retiro.creado_por), (p.id, "VEND-2"))
        # El motivo se sigue escribiendo igual (es lo que se lee).
        self.assertEqual(retiro.motivo, f"Compra a cuenta de Cristal · #{p.id}")
        self.assertTrue(cac.es_compra(p))

    def test_folio_nulo_no_deja_retiro_huerfano_en_el_corte(self):
        """Sin venta ligada, la venta y el retiro cuentan los dos y se cancelan:
        antes el retiro salía del corte y la venta no (faltante falso)."""
        venta = self._venta()
        p = self._compra(folio=None)
        self.assertIsNone(p.libreta_venta_id)
        ventas, retiros, total = self._corte()
        self.assertEqual(ventas, [venta.id])
        self.assertEqual((retiros, total), ([f"Compra a cuenta de Cristal · #{p.id}"], D("332.00")))

    def test_retiro_manual_con_ese_texto_si_cuenta_en_el_corte(self):
        rs.registrar_retiro(self.s, monto="80", motivo="Compra a cuenta de bolsas", creado_por="VEND-1")
        venta = self._venta()
        self._compra(venta=venta)
        ventas, retiros, total = self._corte()
        self.assertEqual(ventas, [])
        self.assertEqual((retiros, total), (["Compra a cuenta de bolsas"], D("80.00")))

    def test_rechazada_quita_su_retiro_por_columna_y_no_el_manual(self):
        rs.registrar_retiro(self.s, monto="332", motivo="Compra a cuenta de Cristal · #1", creado_por="VEND-1")
        p = self._compra(venta=self._venta())
        pr.rechazar(self.s, p.id, quien="VEND-1")
        self.assertEqual([r.prestamo_id for r in self.s.scalars(select(CajaRetiro))], [None])
        self.assertEqual([r.id for r in cac.rechazadas_recientes(self.s, "VEND-3")], [p.id])

    def test_un_prestamo_con_motivo_de_compra_no_es_compra(self):
        p = pr.pedir(self.s, employee_code="VEND-3", nombre="Cristal", monto="50", motivo="Compra a cuenta de gas")
        self.assertEqual(p.tipo, pr.TIPO_PRESTAMO)
        self.assertFalse(cac.es_compra(p))
        pr.aprobar(self.s, p.id, quien="VEND-1")
        retiro = self.s.scalars(select(CajaRetiro)).one()
        # El préstamo aprobado liga su retiro, y ese sí cuenta en el corte.
        self.assertEqual((retiro.prestamo_id, retiro.motivo), (p.id, "Préstamo a Cristal"))
        self.assertEqual(self._corte()[2], D("50.00"))

    def test_lo_que_se_llevo_sale_de_la_columna(self):
        from pos_uniformes.services import telegram_prestamos_service as prs

        venta = self._venta(folio="sin-ticket-en-el-motivo")
        p = self._compra(folio=None, venta=venta)
        self.assertNotIn("ticket", p.motivo)
        self.assertIn("Se llevó: Pantalón x1", prs.aviso_de_solicitud(p, session=self.s))


class PagoParcialTests(_Base):
    def _compra_aprobada(self):
        venta = self._venta(monto="600")
        p = self._compra(venta=venta, monto="600")
        pr.aprobar(self.s, p.id, quien="VEND-1")
        return venta, p

    def test_la_parte_apunta_a_su_original_y_sigue_ligada_a_la_venta(self):
        venta, p = self._compra_aprobada()
        self.assertEqual(pr.marcar_cobrados(self.s, "VEND-3", pago_id=None, cubierto=D("200")), D("200.00"))
        parte = self.s.scalars(select(PrestamoEmpleada).where(PrestamoEmpleada.id != p.id)).one()
        self.assertEqual((parte.origen_id, parte.tipo, parte.libreta_venta_id), (p.id, pr.TIPO_COMPRA, venta.id))
        self.assertEqual((p.monto, parte.monto), (D("400.00"), D("200.00")))
        # Mientras deba algo, sigue «autorizada» (no alterna con «descontada»).
        self.assertEqual(cac.estados_en_libreta(self.s, [venta]), {venta.id: cac.AUTORIZADA})
        # La venta sigue fuera del corte y su retiro también.
        self.assertEqual(self._corte(), ([], [], D("0.00")))

    def test_deshacer_el_pago_regresa_la_parte_por_columna(self):
        from pos_uniformes.database.models import EmpleadaPago

        _venta, p = self._compra_aprobada()
        pago = EmpleadaPago(employee_code="VEND-3", employee_name="Cristal", fecha=SAB14, hasta=SAB14)
        self.s.add(pago)
        self.s.flush()
        pago_id = pago.id
        pr.marcar_cobrados(self.s, "VEND-3", pago_id=pago_id, cubierto=D("200"))
        # Aunque alguien cambie el texto del motivo, la liga es la columna.
        parte = self.s.scalars(select(PrestamoEmpleada).where(PrestamoEmpleada.id != p.id)).one()
        parte.motivo = "otro texto"
        self.assertEqual(pr.regresar_cobrados(self.s, pago_id), D("200.00"))
        self.assertEqual([(x.id, x.monto, x.estado) for x in self.s.scalars(select(PrestamoEmpleada))],
                         [(p.id, D("600.00"), pr.APROBADO)])


class EstadosDeterministasTests(_Base):
    def test_mismo_resultado_sin_importar_el_orden(self):
        v1, v2 = self._venta(), self._venta(folio="99999999-0000-4000-8000-000000000002", monto="100")
        p1 = self._compra(venta=v1)
        self._compra(venta=v2, monto="100")
        pr.aprobar(self.s, p1.id, quien="VEND-1")
        pr.marcar_cobrados(self.s, "VEND-3", pago_id=None, cubierto=D("100"))   # p1 queda partida
        esperado = {v1.id: cac.AUTORIZADA, v2.id: cac.POR_AUTORIZAR}
        for filas in ([v1, v2], [v2, v1], [v2, v1, v1]):
            self.assertEqual(cac.estados_en_libreta(self.s, filas), esperado)
        # Ya cobrada completa: «descontada».
        pr.marcar_cobrados(self.s, "VEND-3", pago_id=None)
        self.assertEqual(cac.estados_en_libreta(self.s, [v1])[v1.id], cac.DESCONTADA)

    def test_sin_filas(self):
        self.assertEqual(cac.estados_en_libreta(self.s, []), {})


class UnaSolaTransaccionTests(_Base):
    def _cuenta(self, modelo):
        return self.s.scalar(select(func.count()).select_from(modelo))

    def test_guarda_venta_compra_y_retiro_juntos_con_un_commit(self):
        commits = []
        original = self.s.commit
        with patch.object(self.s, "commit", side_effect=lambda: (commits.append(1), original())[1]), \
             patch.object(rs, "avisar_retiro") as aviso:
            p = cac.registrar_venta_a_cuenta(self.s, entrada=self._entrada(), employee_code="VEND-3",
                                             nombre="Cristal", opcion=self.este, creado_por="VEND-2")
        self.assertEqual(len(commits), 1)
        aviso.assert_called_once()
        venta = self.s.scalars(select(LibretaVenta)).one()
        retiro = self.s.scalars(select(CajaRetiro)).one()
        self.assertEqual((p.libreta_venta_id, retiro.prestamo_id, retiro.creado_por), (venta.id, p.id, "VEND-2"))
        self.assertEqual((venta.operacion_uuid, p.monto, p.estado), (FOLIO, D("332.00"), pr.PEDIDO))
        self.assertEqual(self._corte(), ([], [], D("0.00")))
        # Un reintento con el mismo folio no duplica nada.
        cac.registrar_venta_a_cuenta(self.s, entrada=self._entrada(), employee_code="VEND-3",
                                     nombre="Cristal", opcion=self.este, creado_por="VEND-2")
        self.assertEqual((self._cuenta(LibretaVenta), self._cuenta(PrestamoEmpleada), self._cuenta(CajaRetiro)),
                         (1, 1, 1))

    def test_si_falla_a_la_mitad_no_queda_nada(self):
        self.s.commit()   # la empleada ya estaba
        with patch.object(rs, "registrar_retiro_de_compra_a_cuenta", side_effect=RuntimeError("se cayó")):
            with self.assertRaises(RuntimeError):
                cac.registrar_venta_a_cuenta(self.s, entrada=self._entrada(), employee_code="VEND-3",
                                             nombre="Cristal", opcion=self.este, creado_por="VEND-2")
        self.assertEqual((self._cuenta(LibretaVenta), self._cuenta(PrestamoEmpleada), self._cuenta(CajaRetiro)),
                         (0, 0, 0))

    def test_si_no_cabe_no_queda_ni_la_venta(self):
        self.s.commit()
        with self.assertRaises(pr.NoSePuede):
            cac.registrar_venta_a_cuenta(self.s, entrada=self._entrada(monto="5000"), employee_code="VEND-3",
                                         nombre="Cristal", opcion=self.este, creado_por="VEND-2")
        self.assertEqual(self._cuenta(LibretaVenta), 0)

    def test_solo_para_la_compradora_y_con_descuento(self):
        for entrada in (self._entrada(compradora_code="VEND-4"), self._entrada(descuento_empleada=False)):
            with self.subTest(entrada=entrada), self.assertRaises(pr.NoSePuede):
                cac.registrar_venta_a_cuenta(self.s, entrada=entrada, employee_code="VEND-3",
                                             nombre="Cristal", opcion=self.este, creado_por="VEND-2")

    def test_puede_dejarse_a_cuenta(self):
        self.assertIsNone(cac.puede_dejarse_a_cuenta(self.s, "VEND-3", "1400"))
        self.assertIn("$1,400.00", cac.puede_dejarse_a_cuenta(self.s, "VEND-3", "1401"))


class PermisoDelRetiroTests(_Base):
    def test_registrar_retiro_sigue_cerrado(self):
        with self.assertRaises(PermissionError):
            rs.registrar_retiro(self.s, monto="10", motivo="Compra a cuenta de X · #1", creado_por="VEND-2")

    def test_el_de_la_compra_solo_para_una_compra_pedida_y_sin_retiro(self):
        prestamo = pr.pedir(self.s, employee_code="VEND-3", nombre="Cristal", monto="50", motivo="renta")
        with self.assertRaises(PermissionError):
            rs.registrar_retiro_de_compra_a_cuenta(self.s, prestamo, creado_por="VEND-2")
        compra = self._compra(venta=self._venta())
        with self.assertRaises(ValueError):   # ya tiene su retiro
            rs.registrar_retiro_de_compra_a_cuenta(self.s, compra, creado_por="VEND-2")
        with self.assertRaises(PermissionError):
            rs.registrar_retiro_de_compra_a_cuenta(self.s, compra, creado_por=" ")

    def test_commit_false_no_guarda_ni_avisa(self):
        self.s.commit()
        with patch("pos_uniformes.services.alertas_service.encolar") as encolar:
            rs.registrar_retiro(self.s, monto="10", motivo="Cambio", creado_por="VEND-1", commit=False)
        encolar.assert_not_called()
        self.s.rollback()
        self.assertEqual(self.s.scalars(select(CajaRetiro)).all(), [])


if __name__ == "__main__":
    unittest.main()
