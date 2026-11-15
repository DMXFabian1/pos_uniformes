"""Los textos de «Revisar conteo»: fecha, motivo real, qué hacer y confirmaciones."""

from __future__ import annotations

import unittest
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

from pos_uniformes.services import conteo_revision_vista_service as vista
from pos_uniformes.services.revision_service import BIEN, NO_SE_MUEVE, PEDIR, SIN_DATOS, SURTIR, URGENTE

HOY = date(2026, 11, 15)   # domingo


def _l(estado: str, *, conto: int = 5, en_cajas: int = 0, sugerido: int = 0, surtir: int = 0):
    return SimpleNamespace(estado=estado, conto=conto, en_cajas=en_cajas, sugerido=sugerido, surtir=surtir)


class FechaTests(unittest.TestCase):
    def test_hoy_ayer_y_hace_n_dias(self) -> None:
        self.assertEqual(vista.hace_texto(0), "hoy")
        self.assertEqual(vista.hace_texto(1), "ayer")
        self.assertEqual(vista.hace_texto(41), "hace 41 días")

    def test_dias_desde_con_hoy_inyectado(self) -> None:
        self.assertEqual(vista.dias_desde(date(2026, 10, 5), HOY), 41)
        self.assertEqual(vista.dias_desde(date(2026, 11, 15), HOY), 0)
        self.assertEqual(vista.dias_desde(date(2026, 11, 14), HOY), 1)
        self.assertIsNone(vista.dias_desde(None, HOY))

    def test_encabezado_con_dia_de_la_semana(self) -> None:
        self.assertEqual(vista.cuando_se_conto(date(2026, 10, 5), HOY), "lun 5 oct · hace 41 días")
        self.assertEqual(vista.cuando_se_conto(date(2026, 11, 15), HOY), "dom 15 nov · hoy")
        self.assertEqual(vista.cuando_se_conto(date(2026, 11, 14), HOY), "sáb 14 nov · ayer")
        self.assertEqual(vista.cuando_se_conto(None, HOY), "")

    def test_la_hora_de_la_base_se_lee_en_la_zona_de_la_tienda(self) -> None:
        # 2:00 UTC del 6 de octubre = 20:00 del 5 en San Felipe.
        self.assertEqual(vista.fecha_tienda(datetime(2026, 10, 6, 2, 0)), date(2026, 10, 5))
        self.assertEqual(vista.fecha_tienda(datetime(2026, 10, 6, 2, 0, tzinfo=timezone.utc)), date(2026, 10, 5))
        con_zona = datetime(2026, 10, 5, 20, 0, tzinfo=timezone(timedelta(hours=-6)))
        self.assertEqual(vista.fecha_tienda(con_zona), date(2026, 10, 5))

    def test_aviso_ambar_desde_siete_dias(self) -> None:
        self.assertEqual(vista.aviso_conteo_viejo(6), "")
        self.assertEqual(vista.aviso_conteo_viejo(None), "")
        self.assertEqual(vista.aviso_conteo_viejo(7), "Conteo de hace 7 días: conviene recontar antes de corregir.")
        self.assertIn("hace 41 días", vista.aviso_conteo_viejo(41))


class QueHacerTests(unittest.TestCase):
    def test_contada_en_cero_sin_demanda_se_acabo(self) -> None:
        self.assertEqual(vista.que_hacer(_l(NO_SE_MUEVE, conto=0)), "se acabó")
        self.assertEqual(vista.que_hacer(_l(SIN_DATOS, conto=0)), "se acabó")

    def test_con_piezas_sigue_siendo_no_se_mueve_o_sin_datos(self) -> None:
        self.assertEqual(vista.que_hacer(_l(NO_SE_MUEVE, conto=3)), "no se mueve")
        self.assertEqual(vista.que_hacer(_l(SIN_DATOS, conto=3)), "sin datos")

    def test_en_cero_con_cajas_no_se_acabo(self) -> None:
        # (con cajas y sin colgado la regla pone SURTIR; aquí se fuerza el estado para el texto)
        self.assertEqual(vista.que_hacer(_l(NO_SE_MUEVE, conto=0, en_cajas=4)), "no se mueve")

    def test_urgente_pedir_surtir_y_bien(self) -> None:
        self.assertEqual(vista.que_hacer(_l(URGENTE, conto=0, sugerido=6)), "¡URGENTE! pedir 6")
        self.assertEqual(vista.que_hacer(_l(PEDIR, sugerido=6, surtir=2)), "pedir 6 · surtir 2")
        self.assertEqual(vista.que_hacer(_l(SURTIR, surtir=2)), "surtir 2")
        self.assertEqual(vista.que_hacer(_l(BIEN)), "bien")


class MotivoTests(unittest.TestCase):
    def test_con_accion_no_hay_motivo(self) -> None:
        self.assertEqual(vista.motivo_sin_accion([_l(PEDIR, sugerido=3), _l(BIEN)]), "")
        self.assertEqual(vista.motivo_sin_accion([]), "")

    def test_lo_que_hay_alcanza(self) -> None:
        self.assertEqual(vista.motivo_sin_accion([_l(BIEN), _l(BIEN)]), "Nada que pedir ni surtir: lo que hay alcanza (2 tallas).")

    def test_el_caso_de_la_chazarilla(self) -> None:
        # 3 bien, 4 contadas en 0 sin demanda, 8 con piezas y sin ventas.
        lineas = [_l(BIEN)] * 3 + [_l(NO_SE_MUEVE, conto=0)] * 4 + [_l(NO_SE_MUEVE, conto=4)] * 8
        texto = vista.motivo_sin_accion(lineas)
        self.assertEqual(
            texto,
            "Nada que pedir ni surtir: lo que hay alcanza (3 tallas) · 8 tallas sin ventas · 4 se acabaron y nadie las pidió.",
        )
        self.assertNotIn("faltan", texto)

    def test_faltan_dias_solo_si_de_verdad_es_sin_datos(self) -> None:
        self.assertEqual(
            vista.motivo_sin_accion([_l(SIN_DATOS), _l(NO_SE_MUEVE, conto=0)]),
            "Nada que pedir ni surtir: 1 se acabó y nadie la pidió · faltan días para saber el ritmo (1 talla).",
        )


class ConfirmacionTests(unittest.TestCase):
    def test_suma_la_diferencia_y_cuenta_tallas_y_piezas(self) -> None:
        texto = vista.texto_confirmar_aplicar(quien="Stayce", contado=date(2026, 11, 14), diferencias=[-3, -4, 2, 0], hoy=HOY)
        self.assertIn("A cada talla se le suma la diferencia que encontró Stayce el sáb 14 nov.", texto)
        self.assertIn("Se corrigen 3 tallas (faltan 7, sobran 2).", texto)
        self.assertNotIn("quedará como lo contó", texto)
        self.assertNotIn("recontar", texto)

    def test_sin_diferencias_lo_dice(self) -> None:
        texto = vista.texto_confirmar_aplicar(quien="Stayce", contado=date(2026, 11, 14), diferencias=[0, 0], hoy=HOY)
        self.assertIn("Ninguna talla tiene diferencia; solo se marca como revisado", texto)

    def test_un_conteo_viejo_lo_avisa_en_la_confirmacion(self) -> None:
        texto = vista.texto_confirmar_aplicar(quien="Stayce", contado=date(2026, 10, 5), diferencias=[-1], hoy=HOY)
        self.assertIn("Se corrigen 1 talla (faltan 1, sobran 0).", texto)
        self.assertIn("Conteo de hace 41 días", texto)

    def test_el_boton_dice_la_edad_desde_catorce_dias(self) -> None:
        self.assertEqual(vista.boton_corregir(0), "Sí, corregir")
        self.assertEqual(vista.boton_corregir(13), "Sí, corregir")
        self.assertEqual(vista.boton_corregir(None), "Sí, corregir")
        self.assertEqual(vista.boton_corregir(14), "Sí, corregir con un conteo de hace 14 días")
        self.assertEqual(vista.boton_corregir(41), "Sí, corregir con un conteo de hace 41 días")


class YaRevisadaTests(unittest.TestCase):
    def test_corregido_y_no_usado(self) -> None:
        cuando = datetime(2026, 9, 22, 18, 0, tzinfo=timezone.utc)
        self.assertEqual(vista.texto_ya_revisada(revisada_at=cuando, aplicada=True, por="Daniel"), "Corregido el 22 sep por Daniel")
        self.assertEqual(vista.texto_ya_revisada(revisada_at=cuando, aplicada=True), "Corregido el 22 sep")
        self.assertEqual(vista.texto_ya_revisada(revisada_at=cuando, aplicada=False, por="Daniel"), "No se usó (22 sep)")
        self.assertEqual(vista.texto_ya_revisada(revisada_at=None, aplicada=True), "")

    def test_ya_revisada(self) -> None:
        self.assertTrue(vista.ya_revisada(SimpleNamespace(revisada_at=datetime(2026, 9, 22))))
        self.assertFalse(vista.ya_revisada(SimpleNamespace(revisada_at=None)))


if __name__ == "__main__":
    unittest.main()
