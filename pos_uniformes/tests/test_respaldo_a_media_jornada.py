"""El respaldo diario corre con la PC prendida (2026-11-09).

La tarea «POS Respaldo» estaba a las 20:30 y «POS Monederos» a las 21:00. Los
eventos de Windows de la PC principal (24/10 al 08/11) muestran que se apaga
todos los días entre las 16:24 y las 18:08: el respaldo automático no corrió
ni una vez. Los respaldos que había salían del botón del bot o de una
migración. Estas pruebas fijan que las dos tareas caigan en horario de tienda,
que el número de infraestructura suba para que la PC las recree, y que los
textos digan la hora real.
"""

from __future__ import annotations

import unittest

from pos_uniformes.scripts import postactualizacion as post
from pos_uniformes.services import respaldo_estado_service as est

#: La PC prende ~09:00 y se apaga desde las 16:24. Con margen a los dos lados.
ABRE, APAGA_MAS_TEMPRANO = "10:00", "16:00"


def _hora(tarea: post.Tarea) -> str:
    return tarea.schedule[tarea.schedule.index("/ST") + 1]


def _tarea(nombre: str) -> post.Tarea:
    return next(
        t for t in post.tareas_esperadas(hay_telegram=True, resumen_a_hora_fija=False)
        if t.nombre == nombre
    )


class RespaldoConLaPcPrendidaTests(unittest.TestCase):
    def test_el_respaldo_es_a_las_13(self) -> None:
        self.assertEqual(_hora(_tarea("POS Respaldo")), "13:00")
        self.assertEqual(est.HORA_RESPALDO, "13:00")

    def test_respaldo_y_monederos_caen_con_la_tienda_abierta(self) -> None:
        for nombre in ("POS Respaldo", "POS Monederos"):
            with self.subTest(nombre):
                hora = _hora(_tarea(nombre))
                self.assertGreaterEqual(hora, ABRE)
                self.assertLess(hora, APAGA_MAS_TEMPRANO)

    def test_monederos_va_despues_del_respaldo(self) -> None:
        # El respaldo se lleva la base de antes de asentar vencimientos.
        self.assertGreater(_hora(_tarea("POS Monederos")), _hora(_tarea("POS Respaldo")))

    def test_sube_la_version_para_que_la_pc_recree_las_tareas(self) -> None:
        # Sin esto la PC (en la 8) no vuelve a crear las tareas y se queda
        # con el horario viejo hasta el siguiente cambio de infraestructura.
        self.assertGreaterEqual(post.INFRA_VERSION, 9)

    def test_el_aviso_detecta_el_primer_dia_sin_respaldo(self) -> None:
        # De 13:00 a las 10:00 del día siguiente: 21 h, no avisa. Si falló un
        # día, a las 10:00 del siguiente van 45 h: tiene que avisar.
        self.assertLess(21, est.HORAS_PARA_AVISAR)
        self.assertGreater(45, est.HORAS_PARA_AVISAR)

    def test_los_textos_dicen_la_hora_real(self) -> None:
        from pos_uniformes.ui.helpers.settings_backup_helper import (
            build_settings_backup_automatic_status_view,
        )

        _resumen, detalle = build_settings_backup_automatic_status_view(automatic_status=None)
        self.assertIn("13:00", detalle)
        self.assertNotIn("20:30", detalle)


if __name__ == "__main__":
    unittest.main()
