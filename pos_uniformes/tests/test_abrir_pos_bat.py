"""El acceso "POS Uniformes" del escritorio corre `scripts/abrir_pos.bat`:
un solo clic trae lo nuevo, migra, publica a los kioskos y abre el POS.

No se puede correr un .bat desde aquí; se revisa que el guion no pierda los
pasos (y sobre todo el de republicar, que fue el hueco del 2026-09-22).
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

BAT = Path(__file__).resolve().parents[1] / "scripts" / "abrir_pos.bat"


class AbrirPosTests(unittest.TestCase):
    def setUp(self) -> None:
        self.texto = BAT.read_text(encoding="utf-8", errors="replace")

    def test_hace_los_cuatro_pasos_y_abre(self) -> None:
        for paso in ("git fetch origin", "git pull", "alembic upgrade head",
                     "build_presupuestos_satelite_windows.bat", "postactualizacion.bat", "main.py"):
            self.assertIn(paso, self.texto, f"falta el paso: {paso}")

    def test_si_los_kioskos_quedaron_atras_republica(self) -> None:
        # Estar al día con el repositorio no basta: tras un `git pull` a mano,
        # lo publicado para kioskos puede ser más viejo que el código.
        self.assertIn(":revisar_publicado", self.texto)
        self.assertIn("PresupuestosSatelite\\VERSION.txt", self.texto)
        self.assertIn("git rev-parse --short HEAD", self.texto)
        bloque = self.texto.split(":revisar_publicado", 1)[1]
        self.assertIn("goto :build", bloque)

    def test_cada_salto_tiene_su_etiqueta(self) -> None:
        etiquetas = set(re.findall(r"^:(\w+)", self.texto, re.M))
        saltos = set(re.findall(r"goto :(\w+)", self.texto))
        self.assertEqual(saltos - etiquetas, set())

    def test_nunca_deja_de_abrir_el_pos(self) -> None:
        # Todo error cae a :launch; el POS abre aunque falle la actualización.
        self.assertGreaterEqual(self.texto.count("goto :launch"), 4)
        self.assertTrue(self.texto.rstrip().endswith("exit /b 0"))
