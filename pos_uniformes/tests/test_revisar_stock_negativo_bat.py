"""El .bat que revisa el stock en rojo desde la PC principal.

No se puede correr un .bat desde aquí, así que se cuida que el guion no pierda
los pasos: que solo mire si no le dicen `--aplicar`, que deje el reporte en
`reportes\\` (que es como los reportes vuelven por git) y que ofrezca mandarlo.
"""

from __future__ import annotations

import unittest
from pathlib import Path

BAT = Path(__file__).resolve().parents[1] / "scripts" / "revisar_stock_negativo.bat"


class RevisarStockNegativoBatTests(unittest.TestCase):
    def setUp(self) -> None:
        self.texto = BAT.read_text(encoding="utf-8", errors="replace")

    def test_llama_al_guion_con_el_python_del_proyecto(self) -> None:
        self.assertIn(r".venv\Scripts\python.exe", self.texto)
        self.assertIn("pos_uniformes.scripts.revisar_stock_negativo", self.texto)

    def test_pasa_los_argumentos_para_poder_aplicar(self) -> None:
        # Sin `%*` no habría forma de decirle --aplicar desde el acceso directo.
        self.assertIn("revisar_stock_negativo %*", self.texto)

    def test_deja_el_reporte_donde_vuelve_por_git(self) -> None:
        self.assertIn(r"pos_uniformes\reportes\stock_negativo.txt", self.texto)

    def test_ofrece_mandarlo_reusando_enviar_reporte(self) -> None:
        # La mensajería por git ya existe: no se inventa otro camino.
        self.assertIn("enviar_reporte.bat", self.texto)

    def test_si_truena_igual_enseña_lo_que_dijo_la_consola(self) -> None:
        self.assertIn("errorlevel 1", self.texto)
        self.assertIn('type "%REPORTE%"', self.texto)

    def test_guarda_el_reporte_en_utf8(self) -> None:
        # La consola de Windows abre en la pagina 850: sin esto, "Suéter" se
        # guarda como "SuÚter" y el reporte llega roto a la Mac (22/09).
        self.assertIn("chcp 65001", self.texto)
        self.assertIn("PYTHONIOENCODING=utf-8", self.texto)
