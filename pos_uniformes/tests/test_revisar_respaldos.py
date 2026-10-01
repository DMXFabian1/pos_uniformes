"""¿Hay respaldo, y sirve?

Un respaldo que nunca se restauró no es un respaldo, es un archivo
(2026-10-01). Por eso este guion no se conforma con mirar la carpeta: restaura
el último en una base de juguete y cuenta lo que trajo.
"""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from pos_uniformes.scripts import revisar_respaldos as rr

_BAT = Path(__file__).resolve().parent.parent / "scripts" / "revisar_respaldos.bat"


class MirarTest(unittest.TestCase):
    def setUp(self) -> None:
        import tempfile

        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.carpeta = Path(self.tmp.name)

    def _respaldo(self, nombre="pos_uniformes_20260910.dump", dias=0, mb=0.7):
        f = self.carpeta / nombre
        f.write_bytes(b"x" * int(mb * 1024 * 1024))
        viejo = (datetime.now() - timedelta(days=dias)).timestamp()
        import os

        os.utime(f, (viejo, viejo))
        return f

    def test_sin_respaldos_lo_dice_sin_rodeos(self):
        with patch("builtins.print") as p:
            self.assertEqual(rr.mirar(self.carpeta), [])
        dicho = " ".join(str(c) for c in p.call_args_list)
        self.assertIn("NO HAY NINGÚN RESPALDO", dicho)
        self.assertIn("se lleva todo", dicho)

    def test_uno_de_hoy_no_asusta(self):
        self._respaldo(dias=0)
        with patch("builtins.print") as p:
            rr.mirar(self.carpeta)
        dicho = " ".join(str(c) for c in p.call_args_list)
        self.assertIn("👍", dicho)
        self.assertNotIn("se pierden", dicho)

    def test_uno_viejo_dice_cuanto_trabajo_se_perderia(self):
        self._respaldo(dias=21)
        with patch("builtins.print") as p:
            rr.mirar(self.carpeta)
        dicho = " ".join(str(c) for c in p.call_args_list)
        self.assertIn("se pierden 21 días de trabajo", dicho)

    def test_el_mas_nuevo_va_primero(self):
        self._respaldo("viejo.dump", dias=30)
        nuevo = self._respaldo("nuevo.dump", dias=1)
        self.assertEqual(rr.mirar(self.carpeta)[0], nuevo)

    def test_ignora_lo_que_no_es_respaldo(self):
        self._respaldo()
        (self.carpeta / "notas.txt").write_text("x")
        self.assertEqual(len(rr.mirar(self.carpeta)), 1)


class ProbarTest(unittest.TestCase):
    """Lo que de verdad importa: que restaure y que no toque la base buena."""

    def test_la_base_de_prueba_se_borra_aunque_falle(self):
        import subprocess

        hechos = []

        def _falso(*args, **kwargs):
            hechos.append(" ".join(args))
            if "CREATE DATABASE" in " ".join(args):
                return subprocess.CompletedProcess([], 0, "", "")
            raise RuntimeError("tronó restaurando")

        with patch.object(rr, "_psql", side_effect=_falso), self.assertRaises(RuntimeError):
            rr.probar(Path("x.dump"))
        self.assertTrue(
            any("DROP DATABASE" in h for h in hechos),
            "la base de juguete tiene que irse pase lo que pase",
        )

    def test_nunca_se_llama_a_la_base_de_la_tienda(self):
        import inspect

        fuente = inspect.getsource(rr.probar)
        self.assertIn("BASE_PRUEBA", fuente)
        self.assertNotIn("settings.db_name", fuente)


class ElBatTest(unittest.TestCase):
    def setUp(self) -> None:
        self.texto = _BAT.read_text(encoding="utf-8", errors="replace")

    def test_prueba_la_restauracion_no_solo_mira(self):
        self.assertIn("revisar_respaldos --probar", self.texto)

    def test_deja_el_reporte_donde_vuelve_por_git(self):
        self.assertIn(r"pos_uniformes\reportes\respaldos.txt", self.texto)
        self.assertIn("enviar_reporte.bat", self.texto)

    def test_guarda_en_utf8(self):
        self.assertIn("chcp 65001", self.texto)
        self.assertIn("PYTHONIOENCODING=utf-8", self.texto)


if __name__ == "__main__":
    unittest.main()
