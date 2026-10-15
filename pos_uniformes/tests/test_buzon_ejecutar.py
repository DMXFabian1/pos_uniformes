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

    def _proceso(self, *, escribe: bytes = b"", codigo: int = 0, se_traba: bool = False):
        """Un PowerShell de mentiras que escribe en el archivo que le dieron."""
        prueba = self

        class _Proc:
            pid = 4242

            def __init__(self, args, stdin=None, stdout=None, stderr=None, **_):
                prueba.recibio = {"stdin": stdin, "stdout": stdout, "stderr": stderr}
                stdout.write(escribe)
                stdout.flush()
                self.matado = False
                prueba.proc = self

            def wait(self, timeout=None):
                if se_traba and not self.matado:
                    raise subprocess.TimeoutExpired("powershell", timeout)
                return codigo

            def kill(self):
                self.matado = True

        return _Proc

    def test_lo_que_sale_se_regresa_con_su_codigo(self) -> None:
        with patch.object(ej, "_powershell", return_value="powershell"), \
                patch.object(ej.subprocess, "Popen", self._proceso(escribe="hola ñ\n".encode())):
            r = ej.ejecutar("dir")
        self.assertTrue(r.ok)
        self.assertEqual(r.salida, "hola ñ\n")

    def test_la_entrada_va_cerrada_y_la_salida_a_un_archivo(self) -> None:
        # Lo que dejó el botón en «Ejecutando…» para siempre (2026-10-15).
        with patch.object(ej, "_powershell", return_value="powershell"), \
                patch.object(ej.subprocess, "Popen", self._proceso()):
            ej.ejecutar("dir")
        self.assertIs(self.recibio["stdin"], subprocess.DEVNULL)
        self.assertTrue(hasattr(self.recibio["stdout"], "fileno"))     # archivo, no tubería
        self.assertIs(self.recibio["stderr"], subprocess.STDOUT)

    def test_un_comando_trabado_se_corta_y_se_mata(self) -> None:
        with patch.object(ej, "_powershell", return_value="powershell"), \
                patch.object(ej.subprocess, "Popen", self._proceso(escribe=b"a medias", se_traba=True)), \
                patch.object(ej.subprocess, "run"):
            r = ej.ejecutar("Start-Sleep 999", tiempo_limite=1)
        self.assertTrue(self.proc.matado)
        self.assertIsNone(r.codigo)
        self.assertIn("Se cortó", r.error)
        self.assertEqual(r.salida, "a medias")

    def test_el_archivo_temporal_no_se_queda(self) -> None:
        import glob
        import tempfile

        antes = set(glob.glob(f"{tempfile.gettempdir()}/buzon_*.txt"))
        with patch.object(ej, "_powershell", return_value="powershell"), \
                patch.object(ej.subprocess, "Popen", self._proceso(escribe=b"x")):
            ej.ejecutar("dir")
        self.assertEqual(set(glob.glob(f"{tempfile.gettempdir()}/buzon_*.txt")), antes)

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



class ConProcesoDeVerdadTests(unittest.TestCase):
    """Python hace de PowerShell: lo que se prueba es el arranque, la espera, el
    corte y la lectura de verdad, que es donde se trabó en la tienda."""

    def _como_powershell(self, codigo_python: str):
        import sys

        return patch.multiple(
            ej,
            _powershell=lambda: sys.executable,
            armar_comando=lambda script, ejecutable="": [ejecutable, "-c", codigo_python],
        )

    def test_la_salida_se_lee_completa(self) -> None:
        with self._como_powershell("print('hola'); import sys; print('ojo', file=sys.stderr)"):
            r = ej.ejecutar("x", tiempo_limite=20)
        self.assertTrue(r.ok, r)
        self.assertIn("hola", r.salida)
        self.assertIn("ojo", r.salida)          # los errores también llegan

    def test_uno_trabado_de_verdad_se_corta_a_tiempo(self) -> None:
        import time

        inicio = time.monotonic()
        with self._como_powershell("import time; print('empece', flush=True); time.sleep(60)"):
            r = ej.ejecutar("x", tiempo_limite=1)
        self.assertLess(time.monotonic() - inicio, 15)
        self.assertIn("Se cortó", r.error)
        self.assertIn("empece", r.salida)

    def test_no_se_queda_esperando_la_entrada(self) -> None:
        # Lee la entrada: con la entrada cerrada, termina en vez de esperar.
        with self._como_powershell("import sys; print(repr(sys.stdin.read()))"):
            r = ej.ejecutar("x", tiempo_limite=10)
        self.assertTrue(r.ok, r)
        self.assertIn("''", r.salida)


if __name__ == "__main__":
    unittest.main()
