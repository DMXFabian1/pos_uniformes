"""Postactualización: la infraestructura (tareas, servicios) se aplica sola al actualizar."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pos_uniformes.scripts import postactualizacion as post


class TareasEsperadasTests(unittest.TestCase):
    def test_sin_telegram_solo_el_supervisor(self) -> None:
        nombres = [t.nombre for t in post.tareas_esperadas(hay_telegram=False, resumen_a_hora_fija=False)]
        self.assertEqual(nombres, ["POS Supervisor", "POS Supervisor check"])

    def test_con_telegram_agrega_resumen_y_pendientes(self) -> None:
        nombres = [t.nombre for t in post.tareas_esperadas(hay_telegram=True, resumen_a_hora_fija=False)]
        self.assertEqual(nombres, ["POS Supervisor", "POS Supervisor check", "POS Resumen 1645", "POS Resumen 1745", "POS Pendientes", "POS Asistencia"])

    def test_hora_fija_elegida_por_daniel_se_respeta(self) -> None:
        nombres = [t.nombre for t in post.tareas_esperadas(hay_telegram=True, resumen_a_hora_fija=True)]
        self.assertNotIn("POS Resumen 1645", nombres)
        self.assertNotIn("POS Resumen 1745", nombres)
        self.assertIn("POS Pendientes", nombres)  # el recordatorio sí

    def test_comando_es_oculto_y_con_argumentos(self) -> None:
        tarea = post.Tarea("POS Pendientes", ("/SC", "DAILY", "/ST", "13:30"), "resumen_diario_telegram.bat", ("--pendientes",))
        cmd = tarea.comando(Path("C:/pos/scripts"))
        self.assertEqual(cmd[:5], ["schtasks", "/Create", "/F", "/TN", "POS Pendientes"])
        self.assertIn("/SC", cmd)
        accion = cmd[cmd.index("/TR") + 1]
        self.assertTrue(accion.startswith("wscript.exe "))          # sin ventana negra
        self.assertIn("correr_oculto.vbs", accion)
        self.assertTrue(accion.endswith("resumen_diario_telegram.bat --pendientes"))


class AplicarTests(unittest.TestCase):
    def setUp(self) -> None:
        self._dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._dir.cleanup)
        for p in (patch.object(post, "_base", return_value=Path(self._dir.name)),
                  patch.object(post.sys, "platform", "win32"),
                  patch.object(post, "hay_telegram", return_value=True)):
            p.start()
            self.addCleanup(p.stop)

    def test_primera_vez_limpia_lo_viejo_y_crea_lo_nuevo(self) -> None:
        creadas: list[str] = []
        borradas: list[str] = []
        with patch.object(post, "existe_tarea", side_effect=lambda n: n in post.TAREAS_OBSOLETAS), patch.object(
            post, "borrar_tarea", side_effect=lambda n: borradas.append(n) or True
        ), patch.object(post, "crear_tarea", side_effect=lambda t: creadas.append(t.nombre) or True):
            hechos = post.aplicar()
        self.assertEqual(borradas, list(post.TAREAS_OBSOLETAS))
        self.assertIn("POS Supervisor", creadas)
        self.assertIn("POS Resumen 1745", creadas)
        self.assertEqual(post.version_aplicada(), post.INFRA_VERSION)
        self.assertIn(f"infraestructura en la version {post.INFRA_VERSION}", hechos)

    def test_el_snapshot_a_casa_se_conserva_pero_oculto(self) -> None:
        """La ventana negra del 2026-09-12: "POS Snapshot Casa" se creaba directo,
        sin correr_oculto.vbs, y la v2 no la conocía. Si existe, se recrea oculta."""
        creadas: list[post.Tarea] = []
        with patch.object(post, "existe_tarea", side_effect=lambda n: n == "POS Snapshot Casa"), patch.object(
            post, "borrar_tarea", return_value=True
        ), patch.object(post, "crear_tarea", side_effect=lambda t: creadas.append(t) or True):
            post.aplicar()
        snap = next(t for t in creadas if t.nombre == "POS Snapshot Casa")
        self.assertEqual(snap.schedule, ("/SC", "MINUTE", "/MO", "15"))
        comando = " ".join(snap.comando(Path("C:/x/scripts")))
        self.assertIn("correr_oculto.vbs", comando)
        self.assertIn("enviar_snapshot_casa.bat", comando)

    def test_sin_snapshot_previo_no_se_inventa(self) -> None:
        nombres = [t.nombre for t in post.tareas_esperadas(hay_telegram=False, resumen_a_hora_fija=False)]
        self.assertNotIn("POS Snapshot Casa", nombres)
        con = [t.nombre for t in post.tareas_esperadas(hay_telegram=False, resumen_a_hora_fija=False, snapshot_casa=True)]
        self.assertIn("POS Snapshot Casa", con)

    def test_la_version_subio_para_que_se_aplique_al_actualizar(self) -> None:
        self.assertGreaterEqual(post.INFRA_VERSION, 4)

    def test_con_telegram_manda_la_asistencia_a_las_11(self) -> None:
        tareas = {t.nombre: t for t in post.tareas_esperadas(hay_telegram=True, resumen_a_hora_fija=False)}
        self.assertIn("POS Asistencia", tareas)
        self.assertEqual(tareas["POS Asistencia"].schedule, ("/SC", "DAILY", "/ST", "11:00"))
        self.assertEqual(tareas["POS Asistencia"].args, ("--asistencia",))
        sin = [t.nombre for t in post.tareas_esperadas(hay_telegram=False, resumen_a_hora_fija=False)]
        self.assertNotIn("POS Asistencia", sin)

    def test_segunda_vez_no_toca_nada(self) -> None:
        post.marcar_aplicada()
        with patch.object(post, "crear_tarea") as crear, patch.object(post, "borrar_tarea") as borrar:
            hechos = post.aplicar()
        crear.assert_not_called()
        borrar.assert_not_called()
        self.assertIn(f"ya en la version {post.INFRA_VERSION}", hechos[0])

    def test_forzar_reaplica(self) -> None:
        post.marcar_aplicada()
        with patch.object(post, "existe_tarea", return_value=False), patch.object(post, "crear_tarea", return_value=True) as crear:
            post.aplicar(forzar=True)
        self.assertTrue(crear.called)

    def test_una_tarea_que_falla_se_anota_y_sigue(self) -> None:
        with patch.object(post, "existe_tarea", return_value=False), patch.object(
            post, "crear_tarea", side_effect=lambda t: t.nombre != "POS Supervisor check"
        ):
            hechos = post.aplicar()
        self.assertIn("NO se pudo crear: POS Supervisor check", hechos)
        self.assertIn("tarea al dia: POS Supervisor", hechos)


class FueraDeWindowsTests(unittest.TestCase):
    def test_en_la_mac_no_hace_nada(self) -> None:
        with patch.object(post.sys, "platform", "darwin"), patch.object(post, "crear_tarea") as crear:
            self.assertEqual(post.aplicar(), ["fuera de Windows: nada que hacer"])
        crear.assert_not_called()


class MainTests(unittest.TestCase):
    def test_nunca_truena_y_reinicia_servicios(self) -> None:
        with patch.object(post, "aplicar", side_effect=RuntimeError("schtasks se cayó")), patch.object(
            post, "reiniciar_servicios"
        ) as rein, patch.object(post, "_log"):
            self.assertEqual(post.main([]), 0)  # la actualización sigue pese al error
        rein.assert_not_called()
        with patch.object(post, "aplicar", return_value=["ok"]), patch.object(post, "reiniciar_servicios") as rein, patch.object(post, "_log"):
            self.assertEqual(post.main([]), 0)
        rein.assert_called_once()

    def test_reiniciar_servicios_deja_la_bandera(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            from pos_uniformes.scripts import supervisor

            with patch.object(supervisor, "_base", return_value=Path(d)), patch.object(post.sys, "platform", "darwin"):
                post.reiniciar_servicios()
                self.assertTrue(supervisor.hay_bandera())


if __name__ == "__main__":
    unittest.main()
