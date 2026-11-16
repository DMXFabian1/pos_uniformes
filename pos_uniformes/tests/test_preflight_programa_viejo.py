"""El preflight distingue quién es el viejo: la base o el programa.

13-nov-2026: la PC principal migró la caja (d1e2f3a4b5c6) y el Kiosko
Principal seguía con un programa que no conocía esa revisión. No abría — eso
estaba bien — pero decía «La base de datos esta desactualizada», que era al
revés: el viejo era el programa. Tres casos:

1. La base va adelante y el programa conoce su revisión → arranca con aviso.
2. La base tiene una revisión que el programa NO conoce → no arranca, y dice
   que hay que actualizar el programa (sin hint de alembic).
3. Al programa le falta algo en la base → «base desactualizada» + alembic.
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from pos_uniformes.database import preflight


class _ScriptFalso:
    """Un ScriptDirectory de mentira: cadena lineal a → b → c, o un grafo con
    merges si se dan `padres` ({revisión: (padres…)})."""

    def __init__(self, cadena: tuple[str, ...] = ("aaa", "bbb", "ccc"), *, con_none: bool = False,
                 cabeza: str | None = None, padres: dict[str, tuple[str, ...]] | None = None) -> None:
        self.padres = padres or {r: ((cadena[i - 1],) if i else ()) for i, r in enumerate(cadena)}
        self.cadena = tuple(self.padres)
        self.con_none = con_none
        self.cabeza = cabeza or cadena[-1]

    def get_revision(self, rev: str):
        if rev not in self.cadena:
            if self.con_none:
                return None
            raise RuntimeError(f"Can't locate revision identified by '{rev}'")
        return SimpleNamespace(revision=rev)

    def iterate_revisions(self, desde: str, _hasta: str):
        vistas, pila = [], [desde]
        while pila:
            r = pila.pop()
            if r not in vistas:
                vistas.append(r)
                pila.extend(self.padres[r])
        return [SimpleNamespace(revision=r) for r in vistas]

    def get_heads(self):
        return [self.cabeza]


class RelacionTests(unittest.TestCase):
    def test_base_adelante_y_conocida(self) -> None:
        self.assertEqual(
            preflight._relacion_base(_ScriptFalso(), ("ccc",), ("bbb",)), preflight.BASE_ADELANTE,
        )

    def test_base_con_revision_desconocida_es_programa_viejo(self) -> None:
        self.assertEqual(
            preflight._relacion_base(_ScriptFalso(), ("d1e2f3a4b5c6",), ("ccc",)), preflight.BASE_DESCONOCIDA,
        )

    def test_get_revision_que_da_none_tambien_es_desconocida(self) -> None:
        self.assertEqual(
            preflight._relacion_base(_ScriptFalso(con_none=True), ("zzz",), ("ccc",)),
            preflight.BASE_DESCONOCIDA,
        )

    def test_base_atrasada(self) -> None:
        self.assertEqual(
            preflight._relacion_base(_ScriptFalso(), ("aaa",), ("ccc",)), preflight.BASE_ATRASADA,
        )

    def test_sin_cabezas_es_atrasada(self) -> None:
        self.assertEqual(preflight._relacion_base(_ScriptFalso(), (), ("ccc",)), preflight.BASE_ATRASADA)

    def test_varias_cabezas_con_una_desconocida_es_programa_viejo_en_cualquier_orden(self) -> None:
        for cabezas in (("d1e2f3a4b5c6", "aaa"), ("aaa", "d1e2f3a4b5c6")):
            with self.subTest(cabezas=cabezas):
                self.assertEqual(
                    preflight._relacion_base(_ScriptFalso(), cabezas, ("ccc",)), preflight.BASE_DESCONOCIDA,
                )

    def test_base_en_un_merge_que_junta_lo_que_pide_el_programa_va_adelante(self) -> None:
        # raiz → xxx, raiz → yyy, merge mmm(xxx, yyy). El programa pide (xxx, yyy).
        script = _ScriptFalso(
            cabeza="mmm",
            padres={"raiz": (), "xxx": ("raiz",), "yyy": ("raiz",), "mmm": ("xxx", "yyy")},
        )
        self.assertEqual(preflight._relacion_base(script, ("mmm",), ("xxx", "yyy")), preflight.BASE_ADELANTE)
        # Y al revés: la base en una sola rama del merge está atrasada.
        self.assertEqual(preflight._relacion_base(script, ("xxx",), ("mmm",)), preflight.BASE_ATRASADA)


class InspeccionTests(unittest.TestCase):
    """`inspect_database_status` con heads simulados (sin tocar ninguna base)."""

    def _estado(self, script: _ScriptFalso, cabezas_base: tuple[str, ...]):
        contexto = SimpleNamespace(get_current_heads=lambda: cabezas_base)

        class _Conexion:
            def __enter__(self):
                return object()

            def __exit__(self, *_a):
                return False

        with patch.object(preflight.ScriptDirectory, "from_config", return_value=script), \
                patch.object(preflight, "engine", SimpleNamespace(connect=lambda: _Conexion())), \
                patch.object(preflight.MigrationContext, "configure", return_value=contexto):
            return preflight.inspect_database_status()

    def test_al_dia(self) -> None:
        estado = self._estado(_ScriptFalso(), ("ccc",))
        self.assertTrue(estado.is_up_to_date)
        self.assertFalse(estado.base_adelante or estado.programa_viejo)

    def test_caso_1_base_adelante(self) -> None:
        # El programa conoce «ccc» pero pide «bbb» (p. ej. una rama de migraciones).
        estado = self._estado(_ScriptFalso(cabeza="bbb"), ("ccc",))
        self.assertTrue(estado.base_adelante)
        self.assertFalse(estado.programa_viejo)

    def test_caso_2_programa_viejo(self) -> None:
        estado = self._estado(_ScriptFalso(("aaa", "bbb")), ("d1e2f3a4b5c6",))
        self.assertTrue(estado.programa_viejo)
        self.assertFalse(estado.base_adelante)

    def test_caso_3_base_atrasada(self) -> None:
        estado = self._estado(_ScriptFalso(), ("aaa",))
        self.assertFalse(estado.programa_viejo or estado.base_adelante)


class AvisoTests(unittest.TestCase):
    def _assert(self, estado):
        with patch.object(preflight, "inspect_database_status", return_value=estado), \
                patch.object(preflight, "_version_del_programa", return_value="12 nov · 9fe9d71d"):
            return preflight.assert_database_ready()

    def test_caso_1_arranca_con_aviso_en_el_log(self) -> None:
        estado = preflight.DatabasePreflightStatus(("ccc",), ("bbb",), base_adelante=True)
        with self.assertLogs(preflight.logger, level="WARNING"):
            self.assertIs(self._assert(estado), estado)

    def test_caso_2_no_arranca_pero_dice_que_el_viejo_es_el_programa(self) -> None:
        estado = preflight.DatabasePreflightStatus(("d1e2f3a4b5c6",), ("c9a4e2b7d1f3",), programa_viejo=True)
        with self.assertRaises(preflight.DatabasePreflightError) as ctx:
            self._assert(estado)
        texto = str(ctx.exception)
        self.assertTrue(texto.startswith("Este programa es más viejo que la base de datos"))
        self.assertIn("reparar_satelite.bat", texto)
        self.assertIn("actualizar_pc_principal.bat", texto)
        self.assertIn("12 nov · 9fe9d71d", texto)
        self.assertIn("d1e2f3a4b5c6", texto)
        self.assertIn("c9a4e2b7d1f3", texto)
        self.assertNotIn("alembic", texto)
        self.assertNotIn("desactualizada", texto)
        self.assertEqual(ctx.exception.titulo, "Programa desactualizado")
        self.assertTrue(ctx.exception.programa_viejo)

    def test_caso_3_base_atrasada_conserva_el_hint_de_alembic(self) -> None:
        estado = preflight.DatabasePreflightStatus(("aaa",), ("ccc",))
        with self.assertRaises(preflight.DatabasePreflightError) as ctx:
            self._assert(estado)
        texto = str(ctx.exception)
        self.assertIn("La base de datos esta desactualizada", texto)
        self.assertIn("alembic upgrade head", texto)
        self.assertEqual(ctx.exception.titulo, "Base de datos no lista")
        self.assertFalse(ctx.exception.programa_viejo)

    def test_las_ventanas_usan_el_titulo_del_error(self) -> None:
        from pathlib import Path

        raiz = Path(preflight.__file__).resolve().parents[1]
        for nombre in ("main.py", "presupuestos_satelite_main.py"):
            with self.subTest(archivo=nombre):
                fuente = (raiz / nombre).read_text(encoding="utf-8")
                self.assertIn('getattr(exc, "titulo", "Base de datos no lista")', fuente)


if __name__ == "__main__":
    unittest.main()
