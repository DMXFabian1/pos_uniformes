"""Cada servidor de impresión dice QUÉ atiende.

Desde que hay dos (la principal estrenó impresora de tickets y las Brother de
etiquetas siguen en el kiosko) hacía falta: sin esto, el que no tiene
etiquetadora reclama una etiqueta, la manda a una impresora que no existe y la
deja en ERROR — peor que no imprimirla, porque el trabajo se pierde y parece
culpa de la cola (Daniel, 2026-10-07).
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pos_uniformes.database.models import TipoTrabajo
from pos_uniformes.services import print_routing_cache_service as rt


class _ConCache(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._ruta = Path(self._tmp.name) / "print_routing.json"
        self._p = patch.object(rt, "_cache_path", return_value=self._ruta)
        self._p.start()

    def tearDown(self) -> None:
        self._p.stop()
        self._tmp.cleanup()


class GuardarYLeerTests(_ConCache):
    def test_sin_configurar_atiende_todo(self) -> None:
        """Una máquina que nunca tocó esto se comporta como siempre."""
        self.assertIsNone(rt.tipos_configurados())
        self.assertIsNone(rt.tipos_que_atiende())

    def test_guarda_solo_lo_que_esta_pc_puede(self) -> None:
        rt.save_print_routing(rt.MODO_LOCAL, "principal", ["TICKET", "CONTEO"])
        self.assertEqual(rt.tipos_configurados(), ["CONTEO", "TICKET"])
        self.assertEqual(
            set(rt.tipos_que_atiende()), {TipoTrabajo.TICKET, TipoTrabajo.CONTEO}
        )
        self.assertNotIn(TipoTrabajo.ETIQUETA, rt.tipos_que_atiende())

    def test_el_modo_y_el_nombre_siguen_igual(self) -> None:
        rt.save_print_routing(rt.MODO_LOCAL, "kiosko", ["ETIQUETA"])
        self.assertEqual(rt.load_print_routing(), (rt.MODO_LOCAL, "kiosko"))

    def test_todos_marcados_se_guarda_como_todos(self) -> None:
        """Si mañana hay un tipo nuevo, una PC con todo marcado lo atiende sin
        que nadie vuelva al menú."""
        rt.save_print_routing(rt.MODO_LOCAL, "x", None)
        self.assertNotIn("tipos", json.loads(self._ruta.read_text(encoding="utf-8")))

    def test_lista_vacia_no_es_un_servidor_mudo(self) -> None:
        """Un servidor que no atiende nada no es un estado útil."""
        rt.save_print_routing(rt.MODO_LOCAL, "x", [])
        self.assertIsNone(rt.tipos_configurados())

    def test_un_tipo_desconocido_se_ignora(self) -> None:
        """Un archivo escrito por una versión más nueva no debe tirar a esta."""
        self._ruta.parent.mkdir(parents=True, exist_ok=True)
        self._ruta.write_text(
            json.dumps({"modo": "LOCAL", "origen": "x", "tipos": ["TICKET", "HOLOGRAMA"]}),
            encoding="utf-8",
        )
        self.assertEqual(rt.tipos_configurados(), ["TICKET"])

    def test_un_archivo_roto_no_truena(self) -> None:
        self._ruta.parent.mkdir(parents=True, exist_ok=True)
        self._ruta.write_text("{esto no es json", encoding="utf-8")
        self.assertIsNone(rt.tipos_configurados())


class LoQueDeVerdadImportaTests(_ConCache):
    def test_el_que_no_tiene_etiquetadora_no_reclama_etiquetas(self) -> None:
        """La prueba del problema real: la cola tiene una etiqueta y la PC
        principal —que solo hace tickets— no se la lleva."""
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session

        from pos_uniformes.database.connection import Base
        from pos_uniformes.services import trabajos_service as svc

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        s = Session(engine)
        etiqueta = svc.encolar(s, TipoTrabajo.ETIQUETA, {"sku": "X"})
        ticket = svc.encolar(s, TipoTrabajo.TICKET, {"texto": "hola"})

        rt.save_print_routing(rt.MODO_LOCAL, "principal", ["TICKET", "CONTEO"])
        tomado = svc.reclamar_siguiente(s, tipos=rt.tipos_que_atiende())
        self.assertEqual(tomado.id, ticket.id)   # se salta la etiqueta, que es más vieja

        # Y el kiosko, que sí la tiene, se la lleva.
        rt.save_print_routing(rt.MODO_LOCAL, "kiosko", None)
        tomado2 = svc.reclamar_siguiente(s, tipos=rt.tipos_que_atiende())
        self.assertEqual(tomado2.id, etiqueta.id)
        s.close()


class EstaEnlazadoTests(unittest.TestCase):
    def test_el_kiosko_le_pasa_los_tipos_al_despachador(self) -> None:
        import inspect

        from pos_uniformes.ui.quote_satellite_window import QuoteSatelliteWindow

        fuente = inspect.getsource(QuoteSatelliteWindow._start_trabajo_dispatcher)
        self.assertIn("tipos=tipos_que_atiende()", fuente)

    def test_el_servidor_sin_ventana_tambien(self) -> None:
        import inspect

        from pos_uniformes.ui.helpers import servidor_impresion_runner

        self.assertIn("tipos=tipos", inspect.getsource(servidor_impresion_runner.correr))


if __name__ == "__main__":
    unittest.main()


class LoSuyoTambienSeRuteaPorTipoTests(_ConCache):
    """La mitad que faltaba: qué hace una PC con lo QUE ELLA MISMA genera.

    El modelo viejo era un interruptor por máquina —todo aquí o todo allá— y
    dejó de describir la tienda el día que la principal estrenó impresora de
    tickets sin tener las Brother: en Estación sus tickets se iban al kiosko
    teniendo la impresora buena enfrente, y en Servidor sus etiquetas salían a
    una etiquetadora que no existe (Daniel, 2026-10-07).
    """

    def test_la_principal_imprime_sus_tickets_y_encola_sus_etiquetas(self) -> None:
        rt.guardar_impresoras("principal", ["TICKET", "CONTEO"])
        self.assertTrue(rt.puede_imprimir(TipoTrabajo.TICKET))
        self.assertTrue(rt.puede_imprimir(TipoTrabajo.CONTEO))
        self.assertFalse(rt.puede_imprimir(TipoTrabajo.ETIQUETA))

    def test_el_kiosko_con_todo_imprime_todo(self) -> None:
        rt.guardar_impresoras("kiosko", ["TICKET", "ETIQUETA", "CONTEO", "PEDIDO"])
        self.assertTrue(all(rt.puede_imprimir(t) for t in TipoTrabajo))
        self.assertIsNone(rt.tipos_que_atiende())   # None = todos, para el despachador

    def test_una_pc_sin_impresoras_no_imprime_nada(self) -> None:
        rt.guardar_impresoras("caja 2", [])
        self.assertFalse(any(rt.puede_imprimir(t) for t in TipoTrabajo))
        self.assertEqual(rt.tipos_que_atiende(), [])
        self.assertTrue(rt.enviar_al_satelite_activo())


class NadieCambiaPorActualizarTests(_ConCache):
    """Una máquina que nunca toque esto tiene que comportarse igual que ayer."""

    def test_lo_que_era_servidor_sigue_imprimiendo_todo(self) -> None:
        rt.save_print_routing(rt.MODO_LOCAL, "kiosko")      # como se guardaba antes
        self.assertTrue(all(rt.puede_imprimir(t) for t in TipoTrabajo))
        self.assertIsNone(rt.tipos_que_atiende())

    def test_lo_que_era_estacion_sigue_sin_imprimir_nada(self) -> None:
        rt.save_print_routing(rt.MODO_SATELITE, "caja 2")
        self.assertFalse(any(rt.puede_imprimir(t) for t in TipoTrabajo))
        self.assertEqual(rt.tipos_que_atiende(), [])

    def test_sin_archivo_imprime_todo_como_siempre(self) -> None:
        self.assertTrue(rt.puede_imprimir(TipoTrabajo.TICKET))


class ElArchivoSigueSiendoLegibleParaUnBuildViejoTests(_ConCache):
    def test_guardar_impresoras_escribe_tambien_el_modo(self) -> None:
        """Una PC con el .exe anterior lee el mismo archivo y solo entiende
        `modo`: si se dejara de escribir, se comportaría como Servidor."""
        rt.guardar_impresoras("principal", ["TICKET"])
        datos = json.loads(self._ruta.read_text(encoding="utf-8"))
        self.assertEqual(datos["modo"], rt.MODO_LOCAL)
        rt.guardar_impresoras("caja 2", [])
        datos = json.loads(self._ruta.read_text(encoding="utf-8"))
        self.assertEqual(datos["modo"], rt.MODO_SATELITE)


class LosTresCaminosPreguntanPorTipoTests(unittest.TestCase):
    def test_tickets_etiquetas_y_conteos(self) -> None:
        import inspect

        from pos_uniformes.ui.helpers import (
            conteo_routing_helper,
            label_routing_helper,
            ticket_routing_helper,
        )

        for modulo in (ticket_routing_helper, label_routing_helper, conteo_routing_helper):
            fuente = inspect.getsource(modulo)
            self.assertIn("puede_imprimir", fuente, modulo.__name__)
