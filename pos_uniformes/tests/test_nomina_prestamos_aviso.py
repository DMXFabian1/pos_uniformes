import unittest
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from pos_uniformes.services import nomina_service as nom


class AvisoConPrestamo(unittest.TestCase):
    """El aviso de pago (y por lo tanto el corte) ya resta el préstamo."""

    def _avisos(self, prestamo):
        emp = SimpleNamespace(codigo="VEND-3", nombre_completo="Naye López", activo=True)
        horario = nom.HorarioEmpleada("VEND-3", fecha_ultimo_pago=date(2026, 9, 27))
        with patch.object(nom, "_empleadas_activas", return_value=[emp]), \
             patch.object(nom, "cargar_parametros", return_value=nom.ParametrosCaja(
                 reactivo_actual=Decimal("2000"), sueldo_base=Decimal("1300"),
                 tarifa_comision=Decimal("2"), descuento_falta=Decimal("100"))), \
             patch.object(nom, "cargar_horario", return_value=horario), \
             patch.object(nom, "fecha_proximo_pago", return_value=date(2026, 10, 4)), \
             patch.object(nom, "comisiones_desde_ultimo_pago", return_value=10), \
             patch("pos_uniformes.services.prestamos_service.total_por_cobrar",
                   return_value=Decimal(prestamo)):
            return nom.avisos_de_pago(object(), hoy=date(2026, 10, 4))

    def test_resta_el_prestamo_del_estimado(self):
        sin, = self._avisos("0.00")
        con, = self._avisos("500.00")
        self.assertEqual(sin.total_estimado - Decimal("500.00"), con.total_estimado)

    def test_dice_cuanto_era_el_prestamo(self):
        con, = self._avisos("500.00")
        self.assertEqual(con.prestamos, Decimal("500.00"))


class DesgloseDelKiosko(unittest.TestCase):
    """El diálogo de pago explica por qué bajó el total."""

    def test_el_texto_trae_la_linea_del_prestamo(self):
        import inspect
        from pos_uniformes.ui.dialogs import corte_caja_dialog as d
        fuente = inspect.getsource(d.confirmar_pago)
        self.assertIn("d.prestamo_cubierto", fuente)
        self.assertIn("Préstamo", fuente)


if __name__ == "__main__":
    unittest.main()


class PrestamoMayorQueElSueldo(unittest.TestCase):
    """Lo que el pago no alcanzó a cubrir sigue debiéndose."""

    def _detalle(self, prestamo):
        from pos_uniformes.services.nomina_service import DetallePago
        return DetallePago(
            employee_code="VEND-3", desde=date(2026, 9, 28), hasta=date(2026, 10, 4),
            comisiones=0, sueldo_base=Decimal("1300.00"), tarifa_comision=Decimal("2.00"),
            faltas=0, descuento_falta=Decimal("100.00"), prestamos=Decimal(prestamo),
        )

    def test_cubierto_es_lo_que_alcanzo(self):
        d = self._detalle("2000.00")
        self.assertEqual(d.total, Decimal("0.00"))
        self.assertEqual(d.prestamo_cubierto, Decimal("1300.00"))
        self.assertEqual(d.prestamo_sin_cubrir, Decimal("700.00"))

    def test_si_alcanza_se_cubre_todo(self):
        d = self._detalle("500.00")
        self.assertEqual(d.prestamo_cubierto, Decimal("500.00"))
        self.assertEqual(d.prestamo_sin_cubrir, Decimal("0.00"))

    def test_el_pago_guarda_y_salda_solo_lo_cubierto(self):
        import inspect
        from pos_uniformes.services import nomina_service as n
        fuente = inspect.getsource(n.registrar_pago_con_monto)
        self.assertIn("descuento_prestamos=detalle.prestamo_cubierto", fuente)
        self.assertIn("cubierto=detalle.prestamo_cubierto", fuente)
