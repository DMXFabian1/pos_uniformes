"""Las pruebas no escriben en `pos_uniformes/data` ni `pos_uniformes/logs`.

Auditoría C1 (2026-11-08): una corrida completa reescribía el estado real del
bot (`bot_conexion.json`), la huella de postactualización y los cachés del
kiosko de esta máquina. `conftest._datos_de_la_maquina_fuera_del_alcance`
desvía esas rutas durante pytest; aquí se comprueba que de verdad lo hace.
"""

from __future__ import annotations

import importlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.conftest import _RUTAS_DE_LA_MAQUINA

_RAIZ = Path(__file__).resolve().parents[1]
_PROTEGIDAS = [(_RAIZ / "data").resolve(), (_RAIZ / "logs").resolve()]


def _dentro_de_protegidas(ruta: Path) -> bool:
    ruta = Path(ruta).resolve()
    for carpeta in _PROTEGIDAS:
        try:
            ruta.relative_to(carpeta)
            return True
        except ValueError:
            continue
    return False


def _foto(carpetas) -> dict[str, tuple[int, int]]:
    out = {}
    for c in carpetas:
        if c.exists():
            for p in c.rglob("*"):
                try:
                    st = p.stat()
                except OSError:
                    continue
                out[str(p)] = (st.st_mtime_ns, st.st_size)
    return out


class RutasDesviadasTests(unittest.TestCase):
    def test_ninguna_ruta_protegida_apunta_al_repo(self) -> None:
        for nombre_modulo, atributo in _RUTAS_DE_LA_MAQUINA:
            with self.subTest(f"{nombre_modulo}.{atributo}"):
                ruta = getattr(importlib.import_module(nombre_modulo), atributo)()
                self.assertFalse(_dentro_de_protegidas(ruta), ruta)

    def test_quien_desvia_su_carpeta_la_sigue_usando(self) -> None:
        from pos_uniformes.services import catalog_local_cache_service as cat

        with tempfile.TemporaryDirectory() as d, \
                patch.object(cat, "satellite_data_dir", return_value=Path(d)):
            self.assertEqual(cat._cache_path(), Path(d) / "data" / "catalog_cache.json")


class EstadoDelBotTests(unittest.TestCase):
    def test_el_estado_del_bot_no_se_escribe_en_el_repo(self) -> None:
        from pos_uniformes.services import bot_conexion_service as con

        antes = _foto(_PROTEGIDAS)
        con.anotar_fallo()
        con.anotar_ok()
        self.assertTrue(con.ruta_estado().exists())  # sí se escribió…
        self.assertFalse(_dentro_de_protegidas(con.ruta_estado()))  # …pero no aquí
        self.assertEqual(_foto(_PROTEGIDAS), antes)


class PostactualizacionTests(unittest.TestCase):
    def test_la_huella_de_servicios_no_se_escribe_en_el_repo(self) -> None:
        from pos_uniformes.scripts import postactualizacion as post
        from pos_uniformes.scripts import supervisor

        antes = _foto(_PROTEGIDAS)
        with tempfile.TemporaryDirectory() as d, \
                patch.object(supervisor, "_base", return_value=Path(d)), \
                patch.object(post, "_base", return_value=Path(d)), \
                patch.object(post.sys, "platform", "darwin"):
            post.reiniciar_servicios()
            self.assertEqual(post.ruta_huella_reiniciada().parent.parent, Path(d))
        self.assertEqual(_foto(_PROTEGIDAS), antes)


if __name__ == "__main__":
    unittest.main()
