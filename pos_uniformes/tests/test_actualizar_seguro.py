"""Actualizar la tienda con cuidado: build → respaldo → migraciones → publicar.

Daniel, 2026-11-06: «¿el sistema de actualizaciones tiene rango de mejora?» →
«hazlo completo». Antes se migraba sin respaldo, y si el build fallaba la base
ya había cambiado. Aquí se fija el ORDEN y qué pasa en cada tropiezo.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pos_uniformes.scripts import actualizar as act


class _Falso:
    """Un mundo de mentira que anota lo que se le pide, en orden."""

    def __init__(self, *, ahora="bbb2222", publicado="aaa1111", pendientes=True, share=True,
                 build=True, respaldo=True, migrar=True, publicar=True, volver=True, traer=True):
        self.hechos: list[str] = []
        self.avisos: list[str] = []
        self.marcas: dict[str, str] = {}
        self.ahora, self.publicado = ahora, publicado
        self._r = dict(build=build, respaldo=respaldo, migrar=migrar, publicar=publicar, volver=volver, traer=traer)
        self.pendientes, self.share = pendientes, share

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
        return bool(self.pendientes)

    def _volver(self, commit: str) -> bool:
        self.hechos.append(f"volver:{commit}")
        if self._r["volver"]:
            self.ahora = commit
        return self._r["volver"]

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
