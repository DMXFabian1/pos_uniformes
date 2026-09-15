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
        self.assertGreaterEqual(post.INFRA_VERSION, 6)

    def test_el_contador_de_afluencia_va_oculto_y_solo_si_esta_instalado(self) -> None:
        sin = [t.nombre for t in post.tareas_esperadas(hay_telegram=False, resumen_a_hora_fija=False)]
        self.assertNotIn("POS Afluencia", sin)
        con = {t.nombre: t for t in post.tareas_esperadas(hay_telegram=False, resumen_a_hora_fija=False, afluencia=True)}
        t = con["POS Afluencia"]
        self.assertEqual(t.schedule, ("/SC", "ONLOGON"))
        comando = " ".join(t.comando(Path("C:/x/scripts")))
        self.assertIn("correr_oculto.vbs", comando)
        self.assertIn("afluencia", comando)
        self.assertIn("contador_afluencia.bat", comando)

    def test_las_tareas_del_corte_van_ocultas_si_estaban_instaladas(self) -> None:
        # 2026-09-14: en la PC principal 'POS Corte 1630/1730' corrian el .bat
        # directo y eran la ventana negra.
        sin = [t.nombre for t in post.tareas_esperadas(hay_telegram=True, resumen_a_hora_fija=False)]
        self.assertNotIn("POS Corte 1630", sin)
        con = {t.nombre: t for t in post.tareas_esperadas(hay_telegram=True, resumen_a_hora_fija=False, corte=True)}
        for nombre, hora in (("POS Corte 1630", "16:30"), ("POS Corte 1730", "17:30"), ("POS Corte recordatorio 1650", "16:50"), ("POS Corte recordatorio 1750", "17:50")):
            t = con[nombre]
            self.assertEqual(t.schedule, ("/SC", "DAILY", "/ST", hora))
            comando = " ".join(t.comando(Path("C:/x/scripts")))
            self.assertIn("correr_oculto.vbs", comando)
            self.assertIn("corte_automatico.bat", comando)
        self.assertIn("--recordar", " ".join(con["POS Corte recordatorio 1650"].comando(Path("C:/x/scripts"))))
        self.assertNotIn("--recordar", " ".join(con["POS Corte 1630"].comando(Path("C:/x/scripts"))))

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


class PythonSinConsolaTests(unittest.TestCase):
    """El bot y la PWA arrancan con pythonw.exe en Windows (sin ventana)."""

    def test_en_windows_usa_pythonw_si_existe(self) -> None:
        import sys
        from unittest.mock import patch

        from pos_uniformes.utils import config

        with patch.object(sys, "platform", "win32"), patch.object(sys, "executable", r"C:\x\.venv\Scripts\python.exe"), \
             patch("os.path.exists", return_value=True):
            self.assertTrue(config.python_sin_consola().lower().endswith("pythonw.exe"))
        with patch.object(sys, "platform", "win32"), patch.object(sys, "executable", r"C:\x\.venv\Scripts\python.exe"), \
             patch("os.path.exists", return_value=False):
            self.assertTrue(config.python_sin_consola().lower().endswith("python.exe"))

    def test_fuera_de_windows_no_cambia(self) -> None:
        import sys

        from pos_uniformes.utils import config

        self.assertEqual(config.python_sin_consola(), sys.executable)

    def test_los_servicios_lo_usan_y_sin_detached(self) -> None:
        import inspect

        from pos_uniformes.scripts import servidor_pwa_vigia, telegram_bot_vigia

        for mod in (servidor_pwa_vigia, telegram_bot_vigia):
            fuente = inspect.getsource(mod)
            self.assertIn("python_sin_consola", fuente)
            self.assertNotIn("DETACHED_PROCESS", fuente.split("def levantar")[1].split("\n\n\ndef")[0])


class PasosUnicosTests(unittest.TestCase):
    """Lo que antes había que correr a mano en la PC principal, una sola vez."""

    def setUp(self) -> None:
        self._dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._dir.cleanup)
        for p in (patch.object(post, "_base", return_value=Path(self._dir.name)),
                  patch.object(post.sys, "platform", "win32")):
            p.start()
            self.addCleanup(p.stop)

    def _pasos(self, resultados: dict[str, bool]) -> tuple:
        corridos: list[str] = []

        def hacer(nombre: str):
            def _f() -> bool:
                corridos.append(nombre)
                return resultados.get(nombre, True)
            return _f

        pasos = tuple(post.PasoUnico(p.nombre, p.que_hace, hacer(p.nombre)) for p in post.PASOS_UNICOS)
        return pasos, corridos

    def test_los_tres_pasos_pendientes_de_septiembre_estan(self) -> None:
        nombres = [p.nombre for p in post.PASOS_UNICOS]
        self.assertEqual(nombres, ["meilisearch_s4u", "descontar_ventas_pasadas", "instalar_afluencia"])

    def test_primera_vez_corre_todo_y_lo_anota(self) -> None:
        pasos, corridos = self._pasos({})
        with patch.object(post, "PASOS_UNICOS", pasos):
            hechos = post.correr_pasos_unicos()
        self.assertEqual(corridos, ["meilisearch_s4u", "descontar_ventas_pasadas", "instalar_afluencia"])
        self.assertEqual(post.pasos_hechos(), set(corridos))
        self.assertTrue(all(h.startswith("hecho: ") for h in hechos))

    def test_segunda_vez_no_repite_nada(self) -> None:
        for p in post.PASOS_UNICOS:
            post.marcar_paso(p.nombre)
        pasos, corridos = self._pasos({})
        with patch.object(post, "PASOS_UNICOS", pasos):
            self.assertEqual(post.correr_pasos_unicos(), [])
        self.assertEqual(corridos, [])

    def test_el_que_falla_no_se_anota_y_se_reintenta_despues(self) -> None:
        pasos, corridos = self._pasos({"instalar_afluencia": False})
        with patch.object(post, "PASOS_UNICOS", pasos):
            hechos = post.correr_pasos_unicos()
        self.assertEqual(post.pasos_hechos(), {"meilisearch_s4u", "descontar_ventas_pasadas"})
        self.assertTrue(any(h.startswith("PENDIENTE") and "instalar_afluencia" in h for h in hechos))
        # siguiente actualización: solo ese
        pasos, corridos = self._pasos({})
        with patch.object(post, "PASOS_UNICOS", pasos):
            post.correr_pasos_unicos()
        self.assertEqual(corridos, ["instalar_afluencia"])

    def test_un_paso_que_truena_cuenta_como_fallido_y_los_demas_siguen(self) -> None:
        def truena() -> bool:
            raise RuntimeError("sin DVR")
        pasos = (post.PasoUnico("a", "a", truena), post.PasoUnico("b", "b", lambda: True))
        with patch.object(post, "PASOS_UNICOS", pasos):
            hechos = post.correr_pasos_unicos()
        self.assertEqual(post.pasos_hechos(), {"b"})
        self.assertEqual(len(hechos), 2)

    def test_en_la_mac_no_corre_nada(self) -> None:
        pasos, corridos = self._pasos({})
        with patch.object(post.sys, "platform", "darwin"), patch.object(post, "PASOS_UNICOS", pasos):
            self.assertEqual(post.correr_pasos_unicos(), [])
        self.assertEqual(corridos, [])

    def test_main_solo_los_corre_con_la_bandera(self) -> None:
        with patch.object(post, "aplicar", return_value=[]), patch.object(post, "reiniciar_servicios"), patch.object(
            post, "_log"
        ), patch.object(post, "correr_pasos_unicos", return_value=["hecho: x"]) as corre:
            post.main([])                       # abrir_pos.bat: nunca
            corre.assert_not_called()
            post.main(["--pasos-unicos"])       # actualizar_pc_principal.bat: sí
            corre.assert_called_once()

    def test_descontar_ventas_corre_el_script_con_aplicar_desde_la_raiz(self) -> None:
        with patch.object(post, "_correr", return_value=True) as correr:
            self.assertTrue(post.paso_descontar_ventas_pasadas())
        cmd = correr.call_args.args[0]
        self.assertEqual(cmd[1:], ["-m", "pos_uniformes.scripts.descontar_ventas_pasadas", "--aplicar"])
        self.assertEqual(correr.call_args.kwargs["cwd"], post._raiz_repo())

    def test_meilisearch_sin_tarea_no_hace_nada(self) -> None:
        with patch.object(post, "existe_tarea", return_value=False), patch.object(post, "_powershell") as ps:
            self.assertTrue(post.paso_meilisearch_oculto())
        ps.assert_not_called()

    def test_meilisearch_con_tarea_la_pasa_a_s4u(self) -> None:
        with patch.object(post, "existe_tarea", return_value=True), patch.object(post, "_powershell", return_value=True) as ps:
            self.assertTrue(post.paso_meilisearch_oculto())
        script = ps.call_args.args[0]
        self.assertIn("-LogonType S4U", script)
        self.assertIn("Start-ScheduledTask -TaskName MeilisearchPOS", script)

    def test_afluencia_sin_instalador_no_hace_nada(self) -> None:
        with patch.object(post, "scripts_dir", return_value=Path(self._dir.name) / "scripts"), patch.object(post, "_correr") as correr:
            self.assertTrue(post.paso_instalar_afluencia())
        correr.assert_not_called()

    def test_afluencia_corre_el_instalador_sin_teclado_y_abre_el_dibujo(self) -> None:
        raiz = Path(self._dir.name)
        (raiz / "afluencia").mkdir()
        (raiz / "afluencia" / "instalar_afluencia.bat").write_text("rem", encoding="utf-8")
        with patch.object(post, "scripts_dir", return_value=raiz / "scripts"), patch.object(
            post, "_correr", return_value=True
        ) as correr, patch.object(post.subprocess, "Popen") as popen:
            self.assertTrue(post.paso_instalar_afluencia())
        self.assertTrue(str(correr.call_args.args[0][-1]).endswith("instalar_afluencia.bat"))
        self.assertEqual(correr.call_args.kwargs["timeout"], 1800)
        self.assertTrue(str(popen.call_args.args[0][-1]).endswith("dibujar_lineas.bat"))

    def test_afluencia_si_el_instalador_falla_no_abre_el_dibujo(self) -> None:
        raiz = Path(self._dir.name)
        (raiz / "afluencia").mkdir()
        (raiz / "afluencia" / "instalar_afluencia.bat").write_text("rem", encoding="utf-8")
        with patch.object(post, "scripts_dir", return_value=raiz / "scripts"), patch.object(
            post, "_correr", return_value=False
        ), patch.object(post.subprocess, "Popen") as popen:
            self.assertFalse(post.paso_instalar_afluencia())
        popen.assert_not_called()
