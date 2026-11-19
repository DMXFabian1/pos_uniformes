"""Actualizar la tienda con cuidado: build → respaldo → migraciones → publicar.

Daniel, 2026-11-06: «¿el sistema de actualizaciones tiene rango de mejora?» →
«hazlo completo». Antes se migraba sin respaldo, y si el build fallaba la base
ya había cambiado. Aquí se fija el ORDEN y qué pasa en cada tropiezo.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pos_uniformes.scripts import actualizar as act


class _Falso:
    """Un mundo de mentira que anota lo que se le pide, en orden."""

    def __init__(self, *, ahora="bbb2222", publicado="aaa1111", pendientes=True, share=True,
                 build=True, respaldo=True, migrar=True, publicar=True, volver=True, traer=True,
                 conoce=None):
        self.hechos: list[str] = []
        self.avisos: list[str] = []
        self.marcas: dict[str, str] = {}
        self.ahora, self.publicado = ahora, publicado
        self._r = dict(build=build, respaldo=respaldo, migrar=migrar, publicar=publicar, volver=volver, traer=traer)
        self.pendientes, self.share = pendientes, share
        self.conoce = conoce                    # ¿la versión de los kioskos conoce la base?
        self.preguntas_conoce: list[str] = []

    def _hacer(self, que: str) -> bool:
        self.hechos.append(que)
        return self._r[que]

    def _respaldar(self) -> Path:
        self.hechos.append("respaldo")
        if not self._r["respaldo"]:
            raise RuntimeError("pg_dump no está")
        return Path("/respaldos/pos_20261106.dump")

    def _pendientes(self) -> bool:
        if self.pendientes == "sin base":
            raise RuntimeError("no contesta")
        if self.pendientes == "programa viejo":
            from pos_uniformes.database.preflight import DatabasePreflightError

            raise DatabasePreflightError("Versión de la base: zzz9", programa_viejo=True)
        return bool(self.pendientes)

    def _volver(self, commit: str) -> bool:
        self.hechos.append(f"volver:{commit}")
        if self._r["volver"]:
            self.ahora = commit
        return self._r["volver"]

    def _conoce(self, commit: str):
        self.preguntas_conoce.append(commit)
        return self.conoce

    def mundo(self) -> act.Mundo:
        return act.Mundo(
            commit_actual=lambda: self.ahora,
            hay_share=lambda: self.share,
            commit_publicado=lambda: self.publicado,
            migraciones_pendientes=self._pendientes,
            construir=lambda: self._hacer("build"),
            respaldar=self._respaldar,
            migrar=lambda: self._hacer("migrar"),
            publicar=lambda: self._hacer("publicar"),
            volver_a=self._volver,
            existe_commit=lambda c: True,
            cambios_entre=lambda a, b: 3,
            version_de=lambda: "6 nov · bbb2222",
            avisar=self.avisos.append,
            leer_marca=lambda n: self.marcas.get(n, ""),
            escribir_marca=lambda n, v: self.marcas.__setitem__(n, v) if v else self.marcas.pop(n, None),
            traer=lambda: self._hacer("traer"),
            version_conoce_base=self._conoce,
            decir=lambda _t: None,
        )


class OrdenTests(unittest.TestCase):
    def test_build_respaldo_migrar_publicar_en_ese_orden(self) -> None:
        f = _Falso()
        r = act.actualizar(f.mundo())
        self.assertEqual(f.hechos, ["build", "respaldo", "migrar", "publicar"])
        self.assertEqual(r.que, act.ACTUALIZADO)
        self.assertTrue(r.ok)
        self.assertEqual(len(f.avisos), 1)
        self.assertIn("✅ Tienda actualizada a 6 nov · bbb2222 (3 cambios)", f.avisos[0])
        self.assertIn("respaldo antes: pos_20261106.dump", f.avisos[0])
        self.assertIn("Kioskos: publicado", f.avisos[0])

    def test_sin_migraciones_no_respalda_ni_migra(self) -> None:
        f = _Falso(pendientes=False)
        r = act.actualizar(f.mundo())
        self.assertEqual(f.hechos, ["build", "publicar"])
        self.assertIn("Base: sin cambios", r.texto)

    def test_ya_al_dia_no_hace_nada_ni_molesta_por_telegram(self) -> None:
        f = _Falso(publicado="bbb2222", pendientes=False)
        r = act.actualizar(f.mundo())
        self.assertEqual((r.que, f.hechos, f.avisos), (act.AL_DIA, [], []))

    def test_publicado_con_clave_mas_larga_es_el_mismo_commit(self) -> None:
        f = _Falso(ahora="bbb2222", publicado="bbb22229f", pendientes=False)
        self.assertEqual(act.actualizar(f.mundo()).que, act.AL_DIA)

    def test_solo_migraciones_pendientes_no_rehace_el_build(self) -> None:
        f = _Falso(publicado="bbb2222", pendientes=True)
        act.actualizar(f.mundo())
        self.assertEqual(f.hechos, ["respaldo", "migrar"])

    def test_sin_carpeta_de_updates_migra_pero_no_construye(self) -> None:
        f = _Falso(share=False)
        act.actualizar(f.mundo())
        self.assertEqual(f.hechos, ["respaldo", "migrar"])

    def test_con_traer_hace_el_pull_primero(self) -> None:
        f = _Falso()
        act.actualizar(f.mundo(), traer=True)
        self.assertEqual(f.hechos[0], "traer")

    def test_si_no_se_pudo_traer_no_toca_nada(self) -> None:
        f = _Falso(traer=False)
        r = act.actualizar(f.mundo(), traer=True)
        self.assertEqual((r.que, f.hechos), (act.FALLO_TRAER, ["traer"]))
        self.assertFalse(r.ok)


class TropiezosTests(unittest.TestCase):
    def test_si_falla_el_build_la_base_no_se_toca_y_el_codigo_regresa(self) -> None:
        f = _Falso(build=False)
        r = act.actualizar(f.mundo())
        self.assertEqual(f.hechos, ["build", "volver:aaa1111"])       # ni respaldo ni migración
        self.assertEqual(r.que, act.FALLO_BUILD)
        self.assertIn("La base NO se tocó", f.avisos[0])
        self.assertIn("regresó a aaa1111", f.avisos[0])
        self.assertEqual(f.marcas[act.MARCA_FALLIDA], "bbb2222")

    def test_sin_respaldo_no_se_migra(self) -> None:
        f = _Falso(respaldo=False)
        r = act.actualizar(f.mundo())
        self.assertEqual(f.hechos, ["build", "respaldo", "volver:aaa1111"])
        self.assertEqual(r.que, act.FALLO_RESPALDO)
        self.assertIn("sin respaldo no se\nmigra".replace("\n", " "), f.avisos[0])

    def test_si_falla_la_migracion_no_se_publica_y_dice_donde_esta_el_respaldo(self) -> None:
        f = _Falso(migrar=False)
        r = act.actualizar(f.mundo())
        self.assertEqual(f.hechos, ["build", "respaldo", "migrar", "volver:aaa1111"])
        self.assertEqual(r.que, act.FALLO_MIGRACION)
        self.assertIn("pos_20261106.dump", f.avisos[0])
        self.assertIn("NO se publicaron", f.avisos[0])

    def test_si_falla_publicar_el_codigo_nuevo_se_queda_porque_la_base_ya_migro(self) -> None:
        f = _Falso(publicar=False)
        r = act.actualizar(f.mundo())
        self.assertEqual(f.hechos, ["build", "respaldo", "migrar", "publicar"])    # sin volver
        self.assertEqual(r.que, act.FALLO_PUBLICAR)
        self.assertNotIn(act.MARCA_FALLIDA, f.marcas)
        self.assertEqual(f.ahora, "bbb2222")

    def test_si_falla_publicar_tras_migrar_el_aviso_es_urgente(self) -> None:
        # 13-nov-2026: con una migración de por medio, la versión que tienen los
        # kioskos NO abre. Decir «abre igual» era mentira.
        f = _Falso(publicar=False)
        r = act.actualizar(f.mundo())
        self.assertEqual(r.que, act.FALLO_PUBLICAR)
        self.assertTrue(f.avisos[0].startswith("🛑"))
        self.assertIn("la base ya se migró pero NO se pudo publicar a los kioskos", f.avisos[0])
        self.assertIn("(aaa1111) NO van a abrir", f.avisos[0])
        self.assertIn("scripts\\actualizar_pc_principal.bat", f.avisos[0])
        self.assertNotIn("abre igual", f.avisos[0])
        self.assertEqual(f.preguntas_conoce, ["aaa1111"])

    def test_si_falla_publicar_sin_migrar_abre_igual_es_verdad(self) -> None:
        f = _Falso(publicar=False, pendientes=False, conoce=True)
        r = act.actualizar(f.mundo())
        self.assertEqual(r.que, act.FALLO_PUBLICAR)
        self.assertIn("que abre igual", f.avisos[0])
        self.assertTrue(f.avisos[0].startswith("⚠️"))

    def test_si_falla_publicar_sin_migrar_y_no_se_sabe_no_promete_que_abren(self) -> None:
        # La base pudo migrarse en otra corrida (o a mano) y git no contestó:
        # ante la duda no se dice «abre igual».
        f = _Falso(publicar=False, pendientes=False, conoce=None)
        r = act.actualizar(f.mundo())
        self.assertEqual(r.que, act.FALLO_PUBLICAR)
        self.assertTrue(f.avisos[0].startswith("⚠️"))
        self.assertNotIn("abre igual", f.avisos[0])
        self.assertIn("no se pudo comprobar si la versión que tienen (aaa1111) conoce la base", f.avisos[0])
        self.assertIn("scripts\\actualizar_pc_principal.bat", f.avisos[0])

    def test_si_el_build_falla_no_regresa_a_un_codigo_que_no_conoce_la_base(self) -> None:
        # Tras migrar sin poder publicar, el reintento al abrir el POS falla en
        # el build: regresar a aaa1111 dejaría sin abrir también a la principal.
        f = _Falso(build=False, pendientes=False, conoce=False)
        r = act.actualizar(f.mundo(), al_abrir=True)
        self.assertEqual(r.que, act.FALLO_BUILD)
        self.assertEqual(f.hechos, ["build"])                   # sin volver
        self.assertEqual(f.ahora, "bbb2222")
        self.assertIn("aaa1111 no conoce la base ya migrada", f.avisos[0])

    def test_si_la_version_de_los_kioskos_no_conoce_la_base_es_urgente_aunque_no_se_migre_ahora(self) -> None:
        # Se migró en una corrida anterior que tampoco pudo publicar.
        f = _Falso(publicar=False, pendientes=False, conoce=False)
        act.actualizar(f.mundo())
        self.assertIn("NO van a abrir", f.avisos[0])

    def test_si_la_version_de_los_kioskos_si_conoce_la_base_abre_igual_aunque_se_migre(self) -> None:
        f = _Falso(publicar=False, conoce=True)
        act.actualizar(f.mundo())
        self.assertIn("que abre igual", f.avisos[0])

    def test_tras_fallar_publicar_al_abrir_el_pos_si_se_reintenta(self) -> None:
        f = _Falso(publicar=False)
        act.actualizar(f.mundo())                       # migra, pero no publica
        f.hechos.clear()
        f.pendientes = False                            # la base ya quedó migrada
        f._r["publicar"] = True
        r = act.actualizar(f.mundo(), al_abrir=True)    # abrir_pos.bat
        self.assertEqual(r.que, act.ACTUALIZADO)
        self.assertEqual(f.hechos, ["build", "publicar"])

    def test_sin_base_no_se_decide_nada(self) -> None:
        f = _Falso(pendientes="sin base")
        r = act.actualizar(f.mundo())
        self.assertEqual((r.que, f.hechos), (act.SIN_BASE, []))
        self.assertEqual(len(f.avisos), 1)

    def test_si_no_se_pudo_regresar_el_codigo_lo_dice(self) -> None:
        f = _Falso(build=False, volver=False)
        r = act.actualizar(f.mundo())
        self.assertIn("No se pudo regresar el código", r.texto)

    def test_al_abrir_no_reintenta_lo_que_ya_fallo_pero_a_mano_si(self) -> None:
        f = _Falso(build=False)
        act.actualizar(f.mundo())                       # falla y regresa a aaa1111
        f.ahora = "bbb2222"                             # abrir_pos.bat volvió a traerlo
        f.hechos.clear()
        r = act.actualizar(f.mundo(), al_abrir=True)
        self.assertEqual(r.que, act.YA_HABIA_FALLADO)
        self.assertEqual(f.hechos, ["volver:aaa1111"])  # ni un minuto de build
        f.ahora = "bbb2222"
        f.hechos.clear()
        f._r["build"] = True
        r = act.actualizar(f.mundo())                   # a mano: sí reintenta
        self.assertEqual(r.que, act.ACTUALIZADO)
        self.assertNotIn(act.MARCA_FALLIDA, f.marcas)


class VolverTests(unittest.TestCase):
    def _carpeta(self, d: str, con_anterior: bool = True) -> Path:
        raiz = Path(d)
        (raiz / "PresupuestosSatelite").mkdir()
        (raiz / "PresupuestosSatelite" / "VERSION.txt").write_text("2026.11.06+bbb2222")
        (raiz / "PresupuestosSatelite" / "app.exe").write_text("nuevo")
        if con_anterior:
            (raiz / "PresupuestosSatelite_anterior").mkdir()
            (raiz / "PresupuestosSatelite_anterior" / "VERSION.txt").write_text("2026.11.05+aaa1111")
            (raiz / "PresupuestosSatelite_anterior" / "app.exe").write_text("viejo")
        return raiz

    def test_intercambia_lo_publicado_con_lo_anterior_y_pone_pausa(self) -> None:
        marcas, avisos = {}, []
        with tempfile.TemporaryDirectory() as d:
            raiz = self._carpeta(d)
            ok, texto = act.volver_kioskos(
                carpeta=raiz, commit_actual="bbb2222", escribir_marca=marcas.__setitem__,
                avisar=avisos.append, decir=lambda _t: None,
            )
            self.assertTrue(ok)
            self.assertEqual((raiz / "PresupuestosSatelite" / "app.exe").read_text(), "viejo")
            self.assertEqual((raiz / "PresupuestosSatelite_anterior" / "app.exe").read_text(), "nuevo")
            self.assertFalse((raiz / "PresupuestosSatelite_cambio").exists())
        self.assertEqual(marcas, {act.MARCA_PAUSA: "bbb2222"})
        self.assertIn("2026.11.05+aaa1111", avisos[0])

    def _volver(self, raiz: Path, conoce):
        marcas, avisos, preguntas = {}, [], []

        def _conoce(commit):
            preguntas.append(commit)
            return conoce

        ok, texto = act.volver_kioskos(
            carpeta=raiz, commit_actual="bbb2222", escribir_marca=marcas.__setitem__,
            avisar=avisos.append, decir=lambda _t: None, conoce_base=_conoce,
        )
        return ok, texto, marcas, avisos, preguntas

    def test_no_vuelve_si_la_version_anterior_no_conoce_la_base(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            raiz = self._carpeta(d)
            ok, texto, marcas, avisos, preguntas = self._volver(raiz, False)
            self.assertFalse(ok)
            self.assertEqual(preguntas, ["aaa1111"])
            self.assertEqual((raiz / "PresupuestosSatelite" / "app.exe").read_text(), "nuevo")   # sin tocar
        self.assertEqual(marcas, {})                    # sin pausa
        self.assertIn("NO abrirían", avisos[0])
        self.assertIn("Se quedan con la versión de ahora", texto)

    def test_si_conoce_la_base_vuelve_sin_advertencia(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            ok, texto, marcas, _avisos, _p = self._volver(self._carpeta(d), True)
        self.assertTrue(ok)
        self.assertEqual(marcas, {act.MARCA_PAUSA: "bbb2222"})
        self.assertNotIn("No se pudo comprobar", texto)

    def test_si_no_se_sabe_vuelve_pero_avisa_como_deshacer(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            ok, texto, _m, _a, _p = self._volver(self._carpeta(d), None)
        self.assertTrue(ok)
        self.assertIn("No se pudo comprobar que esa versión conozca la base", texto)
        self.assertNotIn("abre igual", texto)

    def test_sin_version_anterior_no_toca_nada(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            raiz = self._carpeta(d, con_anterior=False)
            ok, texto = act.volver_kioskos(
                carpeta=raiz, commit_actual="bbb2222", escribir_marca=lambda *_: self.fail("no"),
                avisar=lambda _t: None, decir=lambda _t: None,
            )
            self.assertFalse(ok)
            self.assertIn("No hay una versión anterior", texto)
            self.assertEqual((raiz / "PresupuestosSatelite" / "app.exe").read_text(), "nuevo")

    def test_en_pausa_no_republica_ese_commit_pero_si_el_siguiente(self) -> None:
        f = _Falso(ahora="bbb2222", publicado="aaa1111", pendientes=False)
        f.marcas[act.MARCA_PAUSA] = "bbb2222"
        r = act.actualizar(f.mundo())
        self.assertEqual((r.que, f.hechos), (act.EN_PAUSA, []))
        f.ahora = "ccc3333"                              # llegó el arreglo
        r = act.actualizar(f.mundo())
        self.assertEqual(f.hechos, ["build", "publicar"])
        self.assertNotIn(act.MARCA_PAUSA, f.marcas)

    def test_en_pausa_las_migraciones_si_entran(self) -> None:
        f = _Falso(ahora="bbb2222", publicado="aaa1111", pendientes=True)
        f.marcas[act.MARCA_PAUSA] = "bbb2222"
        r = act.actualizar(f.mundo())
        self.assertEqual(f.hechos, ["respaldo", "migrar"])
        self.assertIn("en pausa", r.texto)


class ProgramaViejoTests(unittest.TestCase):
    """Si la base trae una revisión que este código no conoce, el viejo es el
    programa: migrar no lo arregla (alembic tronaba con un error genérico) y
    publicar mandaría a los kioskos algo que no abre (2026-11-19)."""

    def test_programa_viejo_no_migra_ni_construye_ni_publica_y_dice_que_hacer(self) -> None:
        f = _Falso(pendientes="programa viejo")
        r = act.actualizar(f.mundo())
        self.assertEqual((r.que, f.hechos), (act.PROGRAMA_VIEJO, []))
        self.assertFalse(r.ok)
        self.assertEqual(f.avisos, [r.texto])
        self.assertIn("más viejo que la base", r.texto)
        self.assertIn("NO se migró", r.texto)
        self.assertIn("traer el código más nuevo", r.texto)
        self.assertIn("actualizar_pc_principal.bat", r.texto)
        self.assertIn("zzz9", r.texto)
        self.assertNotIn(act.MARCA_FALLIDA, f.marcas)

    def test_programa_viejo_tras_traer_tampoco_migra(self) -> None:
        f = _Falso(pendientes="programa viejo")
        r = act.actualizar(f.mundo(), traer=True)
        self.assertEqual((r.que, f.hechos), (act.PROGRAMA_VIEJO, ["traer"]))

    def test_sin_base_sigue_siendo_sin_base(self) -> None:
        f = _Falso(pendientes="sin base")
        self.assertEqual(act.actualizar(f.mundo()).que, act.SIN_BASE)


class MigracionesPendientesTests(unittest.TestCase):
    """`_migraciones_pendientes` usa la clasificación del preflight, no la repite."""

    def _con(self, **campos):
        from pos_uniformes.database.preflight import DatabasePreflightStatus

        estado = DatabasePreflightStatus(**campos)
        return mock.patch(
            "pos_uniformes.database.preflight.inspect_database_status", return_value=estado
        )

    def test_base_atrasada_migra(self) -> None:
        with self._con(current_heads=("a1",), expected_heads=("b2",)):
            self.assertTrue(act._migraciones_pendientes())

    def test_base_al_dia_no_migra(self) -> None:
        with self._con(current_heads=("b2",), expected_heads=("b2",)):
            self.assertFalse(act._migraciones_pendientes())

    def test_base_adelante_no_migra(self) -> None:
        with self._con(current_heads=("c3",), expected_heads=("b2",), base_adelante=True):
            self.assertFalse(act._migraciones_pendientes())

    def test_programa_viejo_no_migra_y_truena_con_la_marca(self) -> None:
        from pos_uniformes.database.preflight import TITULO_PROGRAMA_VIEJO, DatabasePreflightError

        with self._con(current_heads=("x9",), expected_heads=("b2",), programa_viejo=True):
            with self.assertRaises(DatabasePreflightError) as ctx:
                act._migraciones_pendientes()
        self.assertTrue(ctx.exception.programa_viejo)
        self.assertEqual(ctx.exception.titulo, TITULO_PROGRAMA_VIEJO)
        self.assertIn("x9", str(ctx.exception))
        self.assertIn("b2", str(ctx.exception))

    def test_de_punta_a_punta_programa_viejo_no_llama_a_migrar(self) -> None:
        f = _Falso()
        mundo = f.mundo()
        mundo.migraciones_pendientes = act._migraciones_pendientes
        with self._con(current_heads=("x9",), expected_heads=("b2",), programa_viejo=True):
            r = act.actualizar(mundo)
        self.assertEqual((r.que, f.hechos), (act.PROGRAMA_VIEJO, []))


class ConoceRevisionesTests(unittest.TestCase):
    """Saber si un commit conoce una revisión: git grep en SUS migraciones."""

    def _git(self, codigos: dict[str, int]):
        llamadas = []

        def git(*args, **_kw):
            llamadas.append(args)
            rev = next(r for r in codigos if r in args[3])
            return codigos[rev], ""
        return git, llamadas

    def test_todas_conocidas(self) -> None:
        git, llamadas = self._git({"c9a4": 0, "d1e2": 0})
        self.assertTrue(act.conoce_revisiones("aaa1111", ("c9a4", "d1e2"), git=git))
        self.assertEqual(llamadas[0][0], "grep")
        self.assertIn("aaa1111", llamadas[0])
        self.assertEqual(llamadas[0][-1], "pos_uniformes/migrations/versions")

    def test_una_desconocida(self) -> None:
        git, _ = self._git({"c9a4": 0, "d1e2": 1})
        self.assertFalse(act.conoce_revisiones("aaa1111", ("c9a4", "d1e2"), git=git))

    def test_git_no_contesta_no_se_sabe(self) -> None:
        git, _ = self._git({"d1e2": 128})
        self.assertIsNone(act.conoce_revisiones("zzz", ("d1e2",), git=git))
        self.assertIsNone(act.conoce_revisiones("", ("d1e2",), git=git))

    def test_el_patron_encuentra_la_revision_en_el_repo_de_verdad(self) -> None:
        # Sin base: solo git sobre el propio repo (HEAD conoce la primera migración).
        import re

        if act._git("rev-parse", "HEAD")[0] != 0:
            self.skipTest("sin git")
        # Una migración que SÍ está en HEAD (no una nueva sin commit del árbol de trabajo).
        codigo, listado = act._git("ls-tree", "--name-only", "HEAD", "pos_uniformes/migrations/versions/")
        archivos = sorted(n for n in listado.splitlines() if n.endswith(".py") and not n.endswith("__init__.py"))
        if codigo != 0 or not archivos:
            self.skipTest("sin migraciones en HEAD")
        codigo, texto = act._git("show", f"HEAD:{archivos[0]}")
        self.assertEqual(codigo, 0)
        m = re.search(r"^revision(?:: *str)? *= *[\"']([0-9a-z_]+)[\"']", texto, re.M)
        self.assertIsNotNone(m)
        self.assertTrue(act.conoce_revisiones("HEAD", (m.group(1),)))
        self.assertFalse(act.conoce_revisiones("HEAD", ("ffffffffffff",)))


class EstadoTests(unittest.TestCase):
    def test_dice_que_trae_la_principal_y_que_corren_los_kioskos(self) -> None:
        f = _Falso()
        texto = act.estado_en_texto(f.mundo())
        self.assertIn("PC principal: 6 nov · bbb2222", texto)
        self.assertIn("publicada aaa1111 (distinta de la principal)", texto)
        f.publicado = "bbb2222"
        self.assertIn("la misma versión", act.estado_en_texto(f.mundo()))


if __name__ == "__main__":
    unittest.main()
