"""Ejecutar desde el buzón: con PIN, a la vista, con límite, y el resultado regresa."""

from __future__ import annotations

import base64
import subprocess
import unittest
from unittest.mock import patch

from pos_uniformes.services import buzon_ejecutar_service as ej


class ArmarComandoTests(unittest.TestCase):
    def test_el_script_viaja_intacto_aunque_traiga_comillas_y_signos(self) -> None:
        script = 'Get-Content "$env:APPDATA\\x.json" | ConvertFrom-Json\n"fin"'
        cmd = ej.armar_comando(script)
        self.assertEqual(cmd[-2], "-EncodedCommand")
        decodificado = base64.b64decode(cmd[-1]).decode("utf-16-le")
        self.assertIn(script, decodificado)

    def test_los_errores_y_lo_ancho_tambien_salen(self) -> None:
        decodificado = base64.b64decode(ej.armar_comando("x")[-1]).decode("utf-16-le")
        self.assertIn("*>&1", decodificado)              # errores junto con lo demás
        self.assertIn(f"-Width {ej.ANCHO_SALIDA}", decodificado)
        self.assertIn("UTF8", decodificado)


class EjecutarTests(unittest.TestCase):
    def test_sin_powershell_se_dice_y_no_truena(self) -> None:
        with patch.object(ej, "_powershell", return_value=None):
            r = ej.ejecutar("dir")
        self.assertFalse(r.ok)
        self.assertIn("PowerShell", r.error)

    def test_lo_que_sale_se_regresa_con_su_codigo(self) -> None:
        hecho = subprocess.CompletedProcess([], 0, stdout="hola\n".encode(), stderr=b"")
        with patch.object(ej, "_powershell", return_value="powershell"), \
                patch.object(ej.subprocess, "run", return_value=hecho):
            r = ej.ejecutar("dir")
        self.assertTrue(r.ok)
        self.assertEqual(r.salida, "hola\n")

    def test_un_comando_trabado_se_corta(self) -> None:
        trabado = subprocess.TimeoutExpired(cmd="x", timeout=1, output=b"a medias")
        with patch.object(ej, "_powershell", return_value="powershell"), \
                patch.object(ej.subprocess, "run", side_effect=trabado):
            r = ej.ejecutar("Start-Sleep 999", tiempo_limite=1)
        self.assertIsNone(r.codigo)
        self.assertIn("Se cortó", r.error)
        self.assertEqual(r.salida, "a medias")

    def test_solo_de_remitentes_de_confianza(self) -> None:
        self.assertTrue(ej.puede_ejecutarse("Claude"))
        self.assertTrue(ej.puede_ejecutarse("PC principal"))
        self.assertFalse(ej.puede_ejecutarse("Entrada"))


class TextoDeResultadoTests(unittest.TestCase):
    def test_dice_de_que_pc_y_como_le_fue(self) -> None:
        texto = ej.texto_de_resultado(ej.Resultado("ok\n", 0, 1.2), pc="Entrada", maximo=1000)
        self.assertTrue(texto.startswith("▶ Resultado en Entrada (terminó bien"))
        self.assertIn("ok", texto)

    def test_lo_muy_largo_se_corta_y_se_avisa(self) -> None:
        texto = ej.texto_de_resultado(ej.Resultado("x" * 5000, 0, 1), pc="E", maximo=500)
        self.assertLessEqual(len(texto), 500)
        self.assertIn("se cortó", texto)


if __name__ == "__main__":
    unittest.main()
