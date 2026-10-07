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
