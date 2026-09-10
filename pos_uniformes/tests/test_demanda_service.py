"""Demanda no atendida: colapso del tecleo y agregados."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace

from pos_uniformes.services import demanda_service as dm

_AHORA = datetime(2026, 9, 10, 11, 0)


def _busqueda(texto, *, seg=0, emp="VEND-2"):
    return {
        "tipo": dm.BUSQUEDA_VACIA, "texto": texto, "employee_code": emp,
        "created_at": (_AHORA + timedelta(seconds=seg)).isoformat(),
    }


def _fila(tipo, *, texto="", producto="", talla="", piezas=1, seg=0):
    return SimpleNamespace(
        tipo=tipo, texto=texto, producto=producto, talla=talla, piezas=piezas,
        created_at=_AHORA + timedelta(seconds=seg),
    )


class ColapsarTests(unittest.TestCase):
    def test_una_cadena_de_tecleo_deja_solo_la_palabra_completa(self) -> None:
        limpias = dm.colapsar([_busqueda("cam", seg=0), _busqueda("camis", seg=2),
                               _busqueda("camisa", seg=4)])
        self.assertEqual([e["texto"] for e in limpias], ["camisa"])

    def test_dos_busquedas_distintas_se_conservan(self) -> None:
        limpias = dm.colapsar([_busqueda("camisa"), _busqueda("calceta", seg=5)])
        self.assertEqual({e["texto"] for e in limpias}, {"camisa", "calceta"})

    def test_lo_muy_corto_es_un_teclazo(self) -> None:
        self.assertEqual(dm.colapsar([_busqueda("ca")]), [])

    def test_la_misma_palabra_mucho_despues_si_cuenta(self) -> None:
        tarde = int(dm.VENTANA_TECLEO.total_seconds()) + 60
        limpias = dm.colapsar([_busqueda("camisa"), _busqueda("camisa", seg=tarde)])
        self.assertEqual(len(limpias), 2)

    def test_dos_empleadas_no_se_mezclan(self) -> None:
        limpias = dm.colapsar([_busqueda("camisa", emp="VEND-2"),
                               _busqueda("camisa", seg=1, emp="VEND-5")])
        self.assertEqual(len(limpias), 2)

    def test_las_tallas_agotadas_pasan_intactas(self) -> None:
        talla = {"tipo": dm.TALLA_AGOTADA, "producto": "Camisa", "talla": "6",
                 "created_at": _AHORA.isoformat()}
        self.assertIn(talla, dm.colapsar([talla, _busqueda("ab")]))

    def test_basura_no_truena(self) -> None:
        self.assertEqual(dm.colapsar([]), [])
        malo = {"tipo": dm.BUSQUEDA_VACIA, "texto": "camisa", "created_at": "no-es-fecha"}
        self.assertEqual(len(dm.colapsar([malo])), 1)


class AgregadosTests(unittest.TestCase):
    def setUp(self) -> None:
        self.filas = [
            _fila(dm.TALLA_AGOTADA, producto="Camisa Prowear MC Blanca", talla="6"),
            _fila(dm.TALLA_AGOTADA, producto="Camisa Prowear MC Blanca", talla="6", seg=60),
            _fila(dm.TALLA_AGOTADA, producto="Camisa Prowear MC Blanca", talla="6", seg=90),
            _fila(dm.TALLA_AGOTADA, producto="Calceta Escolar Blanca", talla="3-5", piezas=3),
            _fila(dm.BUSQUEDA_VACIA, texto="Chamarra SABES"),
            _fila(dm.BUSQUEDA_VACIA, texto="chamarra sabes", seg=200),
            _fila(dm.CARRITO_VACIO, producto="Jumper"),
        ]

    def test_lo_mas_pedido_y_agotado_va_primero(self) -> None:
        top = dm.por_producto_talla(self.filas)
        self.assertEqual(top[0].clave, "Camisa Prowear MC Blanca · 6")
        self.assertEqual(top[0].veces, 3)
        self.assertTrue(top[0].urgente)
        self.assertEqual(top[1].piezas, 3)
        self.assertFalse(top[1].urgente)

    def test_las_busquedas_vacias_se_juntan_sin_importar_mayusculas(self) -> None:
        textos = dm.por_texto(self.filas)
        self.assertEqual(textos[0].clave, "chamarra sabes")
        self.assertEqual(textos[0].veces, 2)

    def test_resumen(self) -> None:
        r = dm.resumen(self.filas)
        self.assertEqual(r.tallas_agotadas, 4)
        self.assertEqual(r.busquedas_vacias, 2)
        self.assertEqual(r.carritos_vacios, 1)
        self.assertEqual(r.piezas_perdidas, 6)

    def test_sin_datos_no_truena(self) -> None:
        self.assertEqual(dm.por_producto_talla([]), [])
        self.assertEqual(dm.resumen([]).piezas_perdidas, 0)


if __name__ == "__main__":
    unittest.main()


class BotonTallaApagadoTests(unittest.TestCase):
    """Por defecto la empleada NO ve existencia: el stock no es confiable."""

    def setUp(self) -> None:
        from pos_uniformes.ui.helpers import quote_guided_catalog_helper as h

        self.h = h

    def test_todas_las_tallas_se_ven_igual(self) -> None:
        agotada = {"talla": "6", "stock_actual": 0}
        self.assertEqual(self.h.etiqueta_talla(agotada, 265.0), "Talla 6 · $265.00")
        self.assertEqual(self.h.estilo_talla(agotada), self.h.estilo_talla({"stock_actual": 9}))
        self.assertNotIn("dashed", self.h.estilo_talla(agotada))

    def test_tocarla_no_la_pinta_de_verde(self) -> None:
        self.assertIn("#87492c", self.h.estilo_talla_seleccionada({"stock_actual": 0}))

    def test_pero_por_dentro_si_sabe_que_esta_agotada(self) -> None:
        """Sin esto no habría qué anotar: la señal se junta aunque no se vea."""
        self.assertTrue(self.h.esta_agotada({"stock_actual": 0}))
        self.assertFalse(self.h.esta_agotada({"stock_actual": 3}))


class BotonTallaEncendidoTests(unittest.TestCase):
    """El día que el stock se sostenga solo, se prende y se ve así."""

    def setUp(self) -> None:
        from unittest.mock import patch

        from pos_uniformes.ui.helpers import quote_guided_catalog_helper as h

        self.h = h
        parche = patch.object(dm, "EXISTENCIA_CONFIABLE", True)
        parche.start()
        self.addCleanup(parche.stop)

    def test_con_existencia_muestra_precio(self) -> None:
        self.assertEqual(
            self.h.etiqueta_talla({"talla": "6", "stock_actual": 4}, 265.0),
            "Talla 6 · $265.00",
        )

    def test_agotada_lo_dice_en_vez_del_precio(self) -> None:
        self.assertEqual(
            self.h.etiqueta_talla({"talla": "6", "stock_actual": 0}, 265.0),
            "Talla 6 · agotado",
        )

    def test_al_tocarla_acusa_recibo(self) -> None:
        texto = self.h.etiqueta_talla({"talla": "6", "stock_actual": 0}, 265.0, anotada=True)
        self.assertIn("anotado", texto)

    def test_stock_raro_se_asume_disponible(self) -> None:
        self.assertFalse(self.h.esta_agotada({"stock_actual": "muchos"}))
        self.assertTrue(self.h.esta_agotada({}))

    def test_la_agotada_se_ve_distinta_y_la_anotada_verde(self) -> None:
        self.assertIn("solid", self.h.estilo_talla({"stock_actual": 3}))
        self.assertIn("dashed", self.h.estilo_talla({"stock_actual": 0}))
        self.assertNotEqual(
            self.h.estilo_talla({"stock_actual": 0}),
            self.h.estilo_talla({"stock_actual": 0}, anotada=True),
        )
        self.assertIn("#2f6b2f", self.h.estilo_talla_seleccionada({"stock_actual": 0}))
        self.assertIn("#87492c", self.h.estilo_talla_seleccionada({"stock_actual": 9}))


if __name__ == "__main__":
    unittest.main()
