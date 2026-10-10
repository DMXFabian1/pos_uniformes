"""La tarea programada de respaldo tiene que poder arrancar el script.

Del 1 al 10 de octubre de 2026 la tarea «POS Respaldo» llamaba
`respaldo_diario.bat --callado`, el .bat reenviaba el argumento a Python y
argparse no lo conocía: salía con error 2 antes de tocar pg_dump. Nueve días
sin respaldo automático, sin un solo aviso, porque tronaba antes de avisar.
"""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch


class LaTareaPuedeArrancarElScriptTests(unittest.TestCase):
    def test_los_argumentos_de_la_tarea_los_acepta_el_script(self) -> None:
        """Los mismos argumentos que pone postactualizacion en la tarea."""
        from pos_uniformes.scripts import postactualizacion as post
        from pos_uniformes.scripts import respaldo_diario as rd

        tarea = next(t for t in post.tareas_esperadas(hay_telegram=False, resumen_a_hora_fija=False)
                     if t.nombre == "POS Respaldo")
        self.assertEqual(tarea.script, "respaldo_diario.bat")
        with patch.object(rd.est, "leer_estado") as leer, \
             patch("pos_uniformes.services.backup_service.run_automatic_backup",
                   return_value=(Path("x.dump"), [], None)):
            leer.return_value = type("E", (), {
                "error": None, "al_dia": True, "sospechoso": False, "error_externa": None,
            })()
            with patch.object(rd.est, "texto_resumen", return_value="ok"):
                # Con los argumentos de la tarea: ni SystemExit ni error 2.
                codigo = rd.main([*tarea.args, "--sin-avisar"])
        self.assertEqual(codigo, 0)

    def test_el_bat_reenvia_los_argumentos_tal_cual(self) -> None:
        """Si alguien cambia el .bat para filtrar, esto deja de importar; si lo
        deja igual, el script TIENE que aceptar lo que la tarea manda."""
        bat = Path(__file__).resolve().parents[1].joinpath("scripts/respaldo_diario.bat").read_text(encoding="utf-8")
        self.assertIn("%*", bat)
