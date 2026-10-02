"""¿Por qué no baja nada con el acceso directo?

Daniel (02/10) le dio al acceso y «no pasa nada». El acceso cuenta lo que le
falta a la rama actual CONTRA SU RAMA REMOTA: si la copia está parada en otra
rama, no le falta nada de esa, y salía «Ya estás al día» — una respuesta
correcta a la pregunta equivocada.

Los tests arman repositorios de verdad en carpetas temporales: lo que se está
probando es justamente cómo se ve git desde afuera.
"""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from pos_uniformes.scripts import revisar_actualizacion as rev


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=str(repo), check=True, capture_output=True)


def _commit(repo: Path, texto: str) -> None:
    (repo / "archivo.txt").write_text(texto, encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "-c", "user.email=t@t", "-c", "user.name=T", "commit", "-m", texto)


class DiagnosticoTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        raiz = Path(self._tmp.name)

        # Un "origin" de verdad, con main vieja y la rama buena adelante.
        self.origen = raiz / "origen"
        self.origen.mkdir()
        _git(self.origen, "init", "-b", "main")
        _commit(self.origen, "lo de julio")
        _git(self.origen, "checkout", "-b", rev.RAMA_BUENA)
        _commit(self.origen, "lo de octubre")
        _git(self.origen, "checkout", "main")

        self.copia = raiz / "copia"
        subprocess.run(
            ["git", "clone", str(self.origen), str(self.copia)], check=True, capture_output=True
        )

    def _diagnosticar(self):
        return rev.diagnosticar(self.copia)

    def test_en_main_al_dia_pero_el_codigo_vive_en_otra_rama(self) -> None:
        # Este es el caso de Daniel: main está al día consigo misma, así que el
        # acceso decía «ya estás al día» y no bajaba nada.
        lineas, problemas = self._diagnosticar()
        self.assertIn("Rama de esta copia : main", "\n".join(lineas))
        self.assertTrue(problemas)
        texto = "\n".join(problemas)
        self.assertIn(rev.RAMA_BUENA, texto)
        self.assertIn("git checkout", texto)

    def test_en_la_rama_buena_no_se_queja(self) -> None:
        _git(self.copia, "checkout", rev.RAMA_BUENA)
        lineas, problemas = self._diagnosticar()
        self.assertIn(rev.RAMA_BUENA, "\n".join(lineas))
        self.assertEqual(problemas, [])

    def test_una_rama_sin_remota_se_dice(self) -> None:
        # `git pull` no sabe de dónde bajar, y el acceso tampoco.
        _git(self.copia, "checkout", "-b", "suelta")
        lineas, problemas = self._diagnosticar()
        self.assertIn("Rama remota        : NINGUNA", "\n".join(lineas))
        self.assertTrue(any("no está conectada" in p for p in problemas))

    def test_cambios_locales_se_avisan(self) -> None:
        _git(self.copia, "checkout", rev.RAMA_BUENA)
        (self.copia / "archivo.txt").write_text("tocado a mano", encoding="utf-8")
        lineas, problemas = self._diagnosticar()
        self.assertIn("1 archivo(s) modificados", "\n".join(lineas))
        self.assertTrue(any("pull puede estar negándose" in p for p in problemas))

    def test_los_archivos_nuevos_sin_seguir_no_cuentan(self) -> None:
        # Un .txt tirado en la carpeta no detiene ningún pull.
        _git(self.copia, "checkout", rev.RAMA_BUENA)
        (self.copia / "nuevo.txt").write_text("hola", encoding="utf-8")
        lineas, problemas = self._diagnosticar()
        self.assertIn("ninguno", "\n".join(lineas))
        self.assertEqual(problemas, [])

    def test_dice_cuantos_commits_faltan(self) -> None:
        _git(self.copia, "checkout", rev.RAMA_BUENA)
        _git(self.copia, "reset", "--hard", "HEAD~1")
        lineas, _ = self._diagnosticar()
        self.assertIn("Le faltan          : 1 commit(s)", "\n".join(lineas))

    def test_una_carpeta_que_no_es_repo_no_revienta(self) -> None:
        with tempfile.TemporaryDirectory() as vacia:
            lineas, problemas = rev.diagnosticar(Path(vacia))
            self.assertTrue(lineas)  # contesta algo en vez de tronar


class AbrirPosTests(unittest.TestCase):
    """El .bat del acceso directo: que el silencio no se vea como éxito."""

    def setUp(self) -> None:
        self.texto = (
            Path(__file__).resolve().parents[1] / "scripts" / "abrir_pos.bat"
        ).read_text(encoding="utf-8", errors="ignore")

    def test_usa_centinela_en_vez_de_asumir_cero(self) -> None:
        # Antes: `set BEHIND=0` y si el conteo fallaba se quedaba en 0, o sea
        # "estás al día". Ahora falla a "?" y lo dice.
        self.assertIn("set BEHIND=?", self.texto)
        self.assertNotIn("set BEHIND=0", self.texto)

    def test_avisa_si_la_rama_no_tiene_remota(self) -> None:
        self.assertIn("no esta conectada a ninguna rama remota", self.texto)

    def test_dice_en_que_rama_esta_al_decir_que_esta_al_dia(self) -> None:
        # Para que se vea de un vistazo que está en la rama equivocada.
        self.assertIn("Ya estas al dia ^(rama %RAMA%^)", self.texto)

    def test_manda_al_diagnostico(self) -> None:
        self.assertIn("revisar_actualizacion.bat", self.texto)


if __name__ == "__main__":
    unittest.main()
