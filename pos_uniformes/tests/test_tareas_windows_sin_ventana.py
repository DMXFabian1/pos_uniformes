"""Las tareas de Windows del POS no deben abrir la ventana negra.

Una tarea que llama directo al .bat hace parpadear una consola cada vez
que corre (los vigías corren cada 5 minutos). Deben pasar por
`correr_oculto.vbs`, que lanza el .bat con la ventana escondida.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
_INSTALADORES = (
    "instalar_servidor_pwa.bat",
    "instalar_resumen_diario.bat",
    "quitar_parpadeo_tareas.bat",
)


def _lineas_schtasks_create(texto: str) -> list[str]:
    return [l.strip() for l in texto.splitlines() if "schtasks /Create" in l]


class TareasSinVentanaTests(unittest.TestCase):
    def test_ninguna_tarea_llama_al_bat_directo(self) -> None:
        for nombre in _INSTALADORES:
            texto = (_SCRIPTS / nombre).read_text(encoding="utf-8", errors="ignore")
            for linea in _lineas_schtasks_create(texto):
                destino = re.search(r"/TR\s+\"(.+)\"\s*>?", linea)
                self.assertIsNotNone(destino, linea)
                orden = destino.group(1)
                if orden.endswith(".bat\\") or orden.rstrip("\\\"").endswith(".bat"):
                    self.assertIn("correr_oculto.vbs", orden, f"{nombre}: {linea}")

    def test_los_vigias_de_cada_5_min_van_ocultos(self) -> None:
        for nombre in _INSTALADORES:
            texto = (_SCRIPTS / nombre).read_text(encoding="utf-8", errors="ignore")
            for linea in _lineas_schtasks_create(texto):
                if "/SC MINUTE" in linea:
                    self.assertIn("correr_oculto.vbs", linea, f"{nombre}: {linea}")

    def test_el_lanzador_oculto_existe_y_esconde_la_ventana(self) -> None:
        vbs = (_SCRIPTS / "correr_oculto.vbs").read_text(encoding="utf-8", errors="ignore")
        # El 0 de sh.Run es "ventana oculta"; sin él vuelve el parpadeo.
        self.assertRegex(vbs, r"sh\.Run\s+cmd,\s*0,")


if __name__ == "__main__":
    unittest.main()
