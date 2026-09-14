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

    def test_windows_en_espanol_con_el_acento_roto(self) -> None:
        # 2026-09-14: en la PC de Daniel la columna llegaba como 'Tarea que se ejecutar\xe1'
        # mal decodificada y TODAS salían como "abre ventana".
        csv_es = (
            '"Nombre de host","Nombre de tarea","Pr\xf3xima ejecuci\xf3n","Estado","Tarea que se ejecutar\ufffd"\n'
            '"PC","\\\\POS Asistencia","15/09/2026 11:00","Listo","wscript.exe \\"C:\\\\pos\\\\scripts\\\\correr_oculto.vbs\\" resumen_diario_telegram.bat --asistencia"\n'
            '"PC","\\\\POS Corte 1630","14/09/2026 16:30","Listo","\\"C:\\\\pos\\\\scripts\\\\corte_automatico.bat\\""\n'
        )
        tareas = dict(tareas_del_pos(csv_es))
        self.assertIn("correr_oculto.vbs", tareas["POS Asistencia"])
        culpables = [n for n, o in tareas.items() if abre_ventana(o)]
        self.assertEqual(culpables, ["POS Corte 1630"])
