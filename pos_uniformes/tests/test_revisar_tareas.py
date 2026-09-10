"""Diagnóstico de la ventana negra: qué tarea no pasa por el lanzador oculto."""

from __future__ import annotations

import unittest

from pos_uniformes.scripts.revisar_tareas import abre_ventana, tareas_del_pos

_CSV = '''"HostName","TaskName","Next Run Time","Status","Task To Run"
"PC","\\\\POS Supervisor","10/09/2026 13:00","Ready","wscript.exe \\"C:\\\\pos\\\\scripts\\\\correr_oculto.vbs\\" supervisor.bat"
"PC","\\\\POS Telegram vigia","10/09/2026 13:05","Ready","C:\\\\pos\\\\scripts\\\\telegram_bot_vigia.bat"
"PC","\\\\POS Pendientes","10/09/2026 13:30","Ready","wscript.exe \\"C:\\\\pos\\\\scripts\\\\correr_oculto.vbs\\" resumen_diario_telegram.bat --pendientes"
"PC","\\\\Otra cosa","N/A","Ready","cualquiera.bat"
'''


class RevisarTareasTests(unittest.TestCase):
    def test_solo_lista_las_del_pos(self) -> None:
        nombres = [n for n, _o in tareas_del_pos(_CSV)]
        self.assertEqual(nombres, ["POS Pendientes", "POS Supervisor", "POS Telegram vigia"])

    def test_detecta_la_que_abre_ventana(self) -> None:
        culpables = [n for n, o in tareas_del_pos(_CSV) if abre_ventana(o)]
        self.assertEqual(culpables, ["POS Telegram vigia"])

    def test_csv_vacio_no_truena(self) -> None:
        self.assertEqual(tareas_del_pos(""), [])
