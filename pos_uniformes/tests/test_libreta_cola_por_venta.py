"""La cola de ventas del kiosko sube venta por venta.

Antes subían todas juntas o ninguna: una sola que la base rechazara atoraba
para siempre a todas las de atrás, en silencio (2026-10-15, Entrada)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine, func, select
from sqlalchemy import exc as sa_exc
from sqlalchemy.orm import Session

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import LibretaVenta
from pos_uniformes.services import libreta_local_queue_service as cola


def _venta(monto="100.00", hora="2026-10-15T10:00:00.123456-06:00", code="VEND-4"):
    return {
        "employee_code": code, "employee_name": "Stayce", "tipo": "venta",
        "items": [{"sku": "SKU999", "nombre": "Playera", "talla": "10", "cantidad": 1, "precio": monto}],
        "monto_total": monto, "origen": "bfaf933365a0", "created_at": hora,
    }


class ColaPorVentaTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._p = patch.object(cola, "satellite_data_dir", return_value=Path(self._tmp.name))
        self._p.start()
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.s = Session(engine)

    def tearDown(self) -> None:
        self.s.close()
        self._p.stop()
        self._tmp.cleanup()

    def _en_base(self) -> int:
        return self.s.scalar(select(func.count()).select_from(LibretaVenta))

    def test_una_venta_mala_no_atora_a_las_demas(self) -> None:
        cola.encolar_operacion(_venta("100.00", "2026-10-15T10:00:00.1-06:00"))
        cola.encolar_operacion(_venta("no-es-numero", "2026-10-15T10:05:00.2-06:00"))
        cola.encolar_operacion(_venta("255.00", "2026-10-15T14:30:00.3-06:00"))
        self.assertEqual(cola.drenar_pendientes(self.s), 2)
        self.assertEqual(self._en_base(), 2)
        quedan = cola.pendientes()
        self.assertEqual([q["monto_total"] for q in quedan], ["no-es-numero"])
        self.assertEqual(quedan[0]["intentos"], 1)
        self.assertTrue(quedan[0]["ultimo_error"])

    def test_si_falla_la_red_no_se_culpa_a_ninguna_venta(self) -> None:
        cola.encolar_operacion(_venta())
        caida = sa_exc.OperationalError("SELECT", {}, Exception("No route to host"))
        with patch.object(cola, "_subir", side_effect=caida):
            with self.assertRaises(sa_exc.OperationalError):
                cola.drenar_pendientes(self.s)
        quedan = cola.pendientes()
        self.assertEqual(len(quedan), 1)
        self.assertNotIn("intentos", quedan[0])      # no se le cuenta como fallida

    def test_una_venta_que_ya_subio_no_se_duplica(self) -> None:
        # La base guardó pero el kiosko no alcanzó a sacarla de la cola.
        cola.encolar_operacion(_venta())
        cola.drenar_pendientes(self.s)
        cola.encolar_operacion(_venta())             # la misma, otra vez
        self.assertEqual(cola.drenar_pendientes(self.s), 1)
        self.assertEqual(self._en_base(), 1)
        self.assertEqual(cola.pendientes(), [])

    def test_dos_ventas_iguales_a_distinta_hora_si_suben_las_dos(self) -> None:
        cola.encolar_operacion(_venta("49.00", "2026-10-15T12:58:39.1-06:00"))
        cola.encolar_operacion(_venta("49.00", "2026-10-15T12:59:10.5-06:00"))
        self.assertEqual(cola.drenar_pendientes(self.s), 2)
        self.assertEqual(self._en_base(), 2)

    def test_al_quinto_intento_se_avisa_una_sola_vez_y_no_se_borra(self) -> None:
        cola.encolar_operacion(_venta("no-es-numero"))
        with patch.object(cola, "_avisar_a_daniel") as avisar:
            for _ in range(cola.INTENTOS_PARA_AVISAR + 2):
                cola.drenar_pendientes(self.s)
        self.assertEqual(avisar.call_count, 1)
        self.assertEqual(len(cola.pendientes()), 1)            # sigue guardada
        self.assertEqual(len(cola.atoradas()), 1)              # y se dice en pantalla

    def test_cuando_por_fin_sube_sale_de_la_cola(self) -> None:
        cola.encolar_operacion(_venta())
        with patch.object(cola, "_subir", side_effect=ValueError("algo raro")):
            cola.drenar_pendientes(self.s)
        self.assertEqual(cola.pendientes()[0]["intentos"], 1)
        self.assertEqual(cola.drenar_pendientes(self.s), 1)    # ya sin el problema
        self.assertEqual(cola.pendientes(), [])
        self.assertEqual(self._en_base(), 1)

    def test_el_aviso_dice_que_venta_de_que_pc_y_por_que(self) -> None:
        mensajes = []
        with patch("pos_uniformes.services.alertas_service.encolar",
                   side_effect=lambda s, t, botones="": mensajes.append(t) or True), \
                patch("pos_uniformes.services.satellite_identity_service.get_satellite_name",
                      return_value="Entrada"):
            cola._avisar_a_daniel(self.s, [dict(_venta("255.00"), intentos=5, ultimo_error="boom")])
        self.assertEqual(len(mensajes), 1)
        for pedazo in ("Entrada", "VEND-4", "255.00", "boom", "Sigue guardada"):
            self.assertIn(pedazo, mensajes[0])


if __name__ == "__main__":
    unittest.main()
