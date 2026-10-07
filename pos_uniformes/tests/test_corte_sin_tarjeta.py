"""«Sin tarjeta» no puede depender de que Daniel se acuerde de escribirlo.

El 6-oct escribió «/corte sin tarjeta» —con espacio— y el bot solo reconocía
`sintarjeta` pegado. Como desde el 4-oct cualquier texto suelto se guarda como
nota, su intento de opción quedó de MOTIVO: el corte salió con las tarjetas y
el papel decía «sin tarjeta». Un dedazo que se veía igual que una decisión.
"""

from __future__ import annotations

import unittest
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from pos_uniformes.services.telegram_bot_service import leer_opciones_corte


class LeerLaOpcionTests(unittest.TestCase):
    def test_sin_tarjeta_con_espacio_tambien_cuenta(self) -> None:
        o = leer_opciones_corte("sin tarjeta")
        self.assertIs(o.sin_tarjeta, True)
        self.assertEqual(o.nota, "")

    def test_en_plural_tambien(self) -> None:
        self.assertIs(leer_opciones_corte("sin tarjetas").sin_tarjeta, True)

    def test_pegado_sigue_funcionando(self) -> None:
        self.assertIs(leer_opciones_corte("sintarjeta").sin_tarjeta, True)

    def test_con_tarjeta_pide_lo_contrario(self) -> None:
        """Para el día suelto en que sí quiere que se vean."""
        self.assertIs(leer_opciones_corte("contarjeta").sin_tarjeta, False)
        self.assertIs(leer_opciones_corte("con tarjeta").sin_tarjeta, False)

    def test_sin_decir_nada_queda_en_None(self) -> None:
        """None = «como lo tengas guardado». No es lo mismo que «muéstralas»."""
        self.assertIsNone(leer_opciones_corte("").sin_tarjeta)
        self.assertIsNone(leer_opciones_corte("5000").sin_tarjeta)

    def test_convive_con_la_cifra_y_la_nota(self) -> None:
        o = leer_opciones_corte("5000 sin tarjeta deposité al banco")
        self.assertEqual(o.retirar, Decimal("5000.00"))
        self.assertIs(o.sin_tarjeta, True)
        self.assertEqual(o.nota, "deposité al banco")

    def test_una_nota_que_habla_de_tarjetas_avisa(self) -> None:
        """Lo que pasó el 6-oct: hoy al menos se dice."""
        o = leer_opciones_corte("sin tarjets")
        self.assertIsNone(o.sin_tarjeta)
        self.assertEqual(o.nota, "sin tarjets")
        self.assertIn("se guardó como NOTA", o.aviso)
        self.assertIn("sintarjeta", o.aviso)

    def test_si_la_opcion_si_se_leyo_no_molesta_con_avisos(self) -> None:
        o = leer_opciones_corte("sin tarjeta pagué la tarjeta del banco")
        self.assertIs(o.sin_tarjeta, True)
        self.assertEqual(o.aviso, "")

    def test_una_nota_normal_no_dispara_el_aviso(self) -> None:
        self.assertEqual(leer_opciones_corte("5000 deposité al banco").aviso, "")


class RespetarLoGuardadoTests(unittest.TestCase):
    """El kiosko ya recordaba la casilla en `caja_parametros.ocultar_tarjeta`;
    el celular era el único que la ignoraba, y por eso los dos decían cosas
    distintas de la misma caja."""

    def _hacer(self, sin_tarjeta, guardado):
        from pos_uniformes.services import corte_remoto_service as cr

        estado = SimpleNamespace(
            resumen=SimpleNamespace(operaciones=0, efectivo=Decimal("0")),
        )
        with patch.object(cr, "__name__", cr.__name__), \
             patch("pos_uniformes.services.corte_caja_service.cargar_parametros",
                   return_value=SimpleNamespace(ocultar_tarjeta=guardado)), \
             patch("pos_uniformes.services.corte_caja_service.estado_caja",
                   return_value=estado), \
             patch("pos_uniformes.services.corte_caja_service.pagos_que_tocan_hoy",
                   return_value=[]), \
             patch("pos_uniformes.services.libreta_service.marcar_privadas_del_periodo") as marcar:
            cr.hacer_corte_y_avisar(object(), creado_por="VEND-1", sin_tarjeta=sin_tarjeta)
        return marcar

    def test_sin_decir_nada_usa_lo_guardado(self) -> None:
        """Se corta antes (no hay ventas), pero la preferencia ya se resolvió:
        lo que importa es que None no significa False."""
        import inspect

        from pos_uniformes.services import corte_remoto_service as cr

        fuente = inspect.getsource(cr.hacer_corte_y_avisar)
        self.assertIn("if sin_tarjeta is None:", fuente)
        self.assertIn("ocultar_tarjeta", fuente)
        # Y se resuelve ANTES de cortar por "no hay ventas", para que el valor
        # no dependa de por dónde salga la función.
        self.assertLess(fuente.index("ocultar_tarjeta"), fuente.index("Sin corte:"))

    def test_la_firma_acepta_los_tres_estados(self) -> None:
        import inspect

        from pos_uniformes.services import corte_remoto_service as cr

        firma = inspect.signature(cr.hacer_corte_y_avisar)
        self.assertIsNone(firma.parameters["sin_tarjeta"].default)


if __name__ == "__main__":
    unittest.main()
