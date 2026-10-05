"""Un aviso puede sonar al salir en las pantallas.

La regla que ordena todo: el sonido NUNCA puede impedir que el aviso se vea.
Un kiosko sin bocinas, sin códec o con el nombre mal escrito tiene que seguir
enseñando el recado.
"""

from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from pos_uniformes.services import sonidos_service as sn
from pos_uniformes.services import telegram_avisos_service as av


class NombresDeSonidoTests(unittest.TestCase):
    def test_el_nombre_se_escribe_sin_acentos_ni_espacios(self) -> None:
        """En el celular no se teclean acentos cómodos."""
        self.assertEqual(sn.clave("Risa del Payaso.wav"), "risadelpayaso")
        self.assertEqual(sn.clave("Sirena-01.mp3"), "sirena01")
        self.assertEqual(sn.clave("risa.wav"), "risa")

    def test_sin_nombre_no_hay_clave(self) -> None:
        self.assertEqual(sn.clave(""), "")
        self.assertEqual(sn.clave(None), "")

    def test_se_encuentra_sin_importar_como_se_escriba(self) -> None:
        falso = [("risadelpayaso", Path("/x/Risa del Payaso.wav"))]
        with patch.object(sn, "disponibles", return_value=falso):
            self.assertIsNotNone(sn.buscar("Risa del Payaso"))
            self.assertIsNotNone(sn.buscar("risadelpayaso"))
            self.assertIsNone(sn.buscar("sirena"))

    def test_sin_carpeta_no_truena(self) -> None:
        with patch.object(sn, "carpeta", return_value=Path("/no/existe/aqui")):
            self.assertEqual(sn.disponibles(), [])
            self.assertEqual(sn.nombres(), [])
            self.assertFalse(sn.existe("risa"))


class LeerElComandoTests(unittest.TestCase):
    def _leer(self, texto, hay=("risa",)):
        with patch.object(sn, "existe", side_effect=lambda n: sn.clave(n) in hay), \
             patch.object(sn, "nombres", return_value=list(hay)), \
             patch.object(av, "buscar_pantalla", return_value=None):
            return av._leer_prefijos(object(), texto)

    def test_toma_el_sonido_y_deja_el_recado(self) -> None:
        resto, horas, pantalla, sonido, quejas = self._leer("sonido=risa 🤡 Te veo...")
        self.assertEqual(resto, "🤡 Te veo...")
        self.assertEqual(sonido, "risa")
        self.assertEqual(quejas, [])

    def test_un_sonido_que_no_existe_no_se_come_el_aviso(self) -> None:
        """Quedarse sin aviso por un sonido mal escrito sería el peor de los males."""
        resto, _h, _p, sonido, quejas = self._leer("sonido=sirena Junta a las 6")
        self.assertEqual(resto, "Junta a las 6")
        self.assertIsNone(sonido)
        self.assertTrue(quejas)
        self.assertIn("sirena", quejas[0])
        self.assertIn("risa", quejas[0])   # dice cuáles sí hay

    def test_convive_con_el_plazo_y_la_pantalla(self) -> None:
        resto, horas, _p, sonido, _q = self._leer("3h sonido=risa Te veo")
        self.assertEqual(resto, "Te veo")
        self.assertEqual(horas, 3.0)
        self.assertEqual(sonido, "risa")

    def test_sin_sonido_todo_sigue_igual(self) -> None:
        resto, horas, _p, sonido, quejas = self._leer("Junta a las 6")
        self.assertEqual(resto, "Junta a las 6")
        self.assertIsNone(sonido)
        self.assertEqual(quejas, [])

    def test_la_palabra_sonido_en_el_texto_no_es_una_orden(self) -> None:
        """«sonido» a secas es parte del recado, no un prefijo."""
        resto, _h, _p, sonido, _q = self._leer("El sonido de la bocina está fallando")
        self.assertEqual(resto, "El sonido de la bocina está fallando")
        self.assertIsNone(sonido)


class ElSonidoNoEstropeaElAvisoTests(unittest.TestCase):
    def test_sin_nombre_no_intenta_nada(self) -> None:
        from pos_uniformes.ui.helpers.anuncio_sonido import reproducir

        self.assertFalse(reproducir(None))
        self.assertFalse(reproducir(""))

    def test_un_sonido_que_no_esta_devuelve_falso_y_no_lanza(self) -> None:
        from pos_uniformes.ui.helpers import anuncio_sonido

        with patch.object(sn, "buscar", return_value=None):
            self.assertFalse(anuncio_sonido.reproducir("fantasma"))

    def test_si_el_audio_truena_el_aviso_no_se_entera(self) -> None:
        from pos_uniformes.ui.helpers import anuncio_sonido

        with patch.object(sn, "buscar", return_value=Path("/x/risa.wav")), \
             patch("PyQt6.QtMultimedia.QMediaPlayer", side_effect=RuntimeError("sin audio")):
            self.assertFalse(anuncio_sonido.reproducir("risa"))

    def test_el_overlay_pide_sonar_hasta_despues_de_pintar(self) -> None:
        """Si el audio truena, el recado ya quedó en pantalla."""
        import inspect

        from pos_uniformes.ui import anuncio_overlay

        fuente = inspect.getsource(anuncio_overlay.AnuncioOverlay.render_anuncio)
        self.assertLess(
            fuente.index("_render_cabecera_y_pie"), fuente.index("reproducir")
        )


class ViajaHastaLaPantallaTests(unittest.TestCase):
    """El sonido tiene que llegar al kiosko: base → cache local → overlay."""

    def test_el_cache_lo_guarda_y_lo_devuelve(self) -> None:
        import json
        import tempfile

        from pos_uniformes.services import anuncio_local_cache_service as cache

        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(cache, "_dir", return_value=Path(tmp)):
                cache.save_anuncios_cache([
                    {"id": 1, "titulo": "Te veo", "sonido": "risa", "duracion_seg": 8}
                ])
                guardado = json.loads((Path(tmp) / cache._INDEX_FILENAME).read_text(encoding="utf-8"))
                self.assertEqual(guardado["anuncios"][0]["sonido"], "risa")
                leido, = cache.load_anuncios_cache()
        self.assertEqual(leido["sonido"], "risa")

    def test_lo_que_sale_de_la_base_lo_trae(self) -> None:
        import inspect

        from pos_uniformes.services import anuncio_service

        self.assertIn('"sonido"', inspect.getsource(anuncio_service.filas_para_cache))


if __name__ == "__main__":
    unittest.main()
