"""`/actualizar`, `/version` y `/volver` desde Telegram, la versión de cada PC
y los `.bat` que ahora pasan por el actualizador (2026-11-06)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from pos_uniformes.scripts import postactualizacion as post
from pos_uniformes.services import satelite_registry_service as reg
from pos_uniformes.services import telegram_actualizar_service as tact
from pos_uniformes.services import telegram_bot_service as bot

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def _texto(nombre: str) -> str:
    return (SCRIPTS / nombre).read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")


class BotTests(unittest.TestCase):
    def setUp(self) -> None:
        self._dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._dir.cleanup)
        parche = patch.object(tact, "_ruta_candado", return_value=Path(self._dir.name) / "actualizando.txt")
        parche.start()
        self.addCleanup(parche.stop)

    def test_sin_si_solo_ensena_como_esta(self) -> None:
        arrancar = MagicMock()
        texto = tact.atender_actualizar("", es_windows=True, arrancar=arrancar, estado=lambda: "PC principal: 6 nov · abc")
        self.assertIn("PC principal: 6 nov · abc", texto)
        self.assertIn("/actualizar si", texto)
        arrancar.assert_not_called()

    def test_con_si_arranca_una_sola_vez(self) -> None:
        arrancar = MagicMock()
        uno = tact.atender_actualizar("si", es_windows=True, arrancar=arrancar, estado=lambda: "x")
        dos = tact.atender_actualizar("sí", es_windows=True, arrancar=arrancar, estado=lambda: "x")
        self.assertIn("Actualizando la tienda", uno)
        self.assertIn("Ya hay una actualización en curso", dos)
        arrancar.assert_called_once()

    def test_el_candado_caduca_y_se_quita_al_terminar(self) -> None:
        tact.poner_candado(ahora=1000.0)
        self.assertTrue(tact.en_curso(ahora=1000.0 + 60))
        self.assertFalse(tact.en_curso(ahora=1000.0 + tact.MINUTOS_EN_CURSO * 60 + 1))
        tact.quitar_candado()
        self.assertFalse(tact.en_curso(ahora=1000.0 + 60))

    def test_si_no_pudo_arrancar_lo_dice_y_suelta_el_candado(self) -> None:
        def _truena() -> None:
            raise OSError("no hay cmd")

        texto = tact.atender_actualizar("si", es_windows=True, arrancar=_truena, estado=lambda: "x")
        self.assertIn("No se pudo arrancar", texto)
        self.assertFalse(tact.en_curso())

    def test_fuera_de_la_tienda_no_arranca_nada(self) -> None:
        arrancar = MagicMock()
        texto = tact.atender_actualizar("si", es_windows=False, arrancar=arrancar, estado=lambda: "x")
        self.assertIn("solo se puede hacer desde el bot de la PC principal", texto)
        arrancar.assert_not_called()

    def test_volver_pide_si(self) -> None:
        volver = MagicMock(return_value=(True, "↩ Los kioskos vuelven a la versión X"))
        self.assertIn("/volver si", tact.atender_volver("", volver=volver))
        volver.assert_not_called()
        self.assertIn("vuelven a la versión X", tact.atender_volver("si", volver=volver))

    def test_la_noche_se_enciende_y_se_apaga(self) -> None:
        creadas, hay = [], {"POS Actualizar": False}

        def crear(t) -> bool:
            creadas.append(t)
            hay[t.nombre] = True
            return True

        def borrar(nombre: str) -> bool:
            hay[nombre] = False
            return True

        texto = tact.atender_noche("", es_windows=True, crear=crear, borrar=borrar, existe=hay.get)
        self.assertIn("19:30", texto)
        self.assertEqual(creadas[0].script, "actualizar_desatendida.bat")
        texto = tact.atender_noche("no", es_windows=True, crear=crear, borrar=borrar, existe=hay.get)
        self.assertIn("ya no se actualiza sola", texto)
        self.assertIn("ya estaba apagada", tact.atender_noche("no", es_windows=True, crear=crear, borrar=borrar, existe=hay.get))

    def test_el_bot_conoce_los_tres_comandos(self) -> None:
        with patch.object(tact, "atender_actualizar", return_value="A") as a, \
                patch.object(tact, "atender_version", return_value="V"), \
                patch.object(tact, "atender_volver", return_value="R") as r:
            self.assertEqual(bot.atender_texto("/actualizar si", session_factory=None), "A")
            self.assertEqual(bot.atender_texto("/version", session_factory=None), "V")
            self.assertEqual(bot.atender_texto("/volver", session_factory=None), "R")
        a.assert_called_once_with("si")
        r.assert_called_once_with("")
        for comando in ("/version", "/actualizar", "/volver"):
            self.assertIn(comando, bot.AYUDA)


class TareaDeNocheTests(unittest.TestCase):
    def test_viene_apagada_y_solo_se_conserva_si_ya_estaba(self) -> None:
        nombres = [t.nombre for t in post.tareas_esperadas(hay_telegram=True, resumen_a_hora_fija=False)]
        self.assertNotIn("POS Actualizar", nombres)
        nombres = [t.nombre for t in post.tareas_esperadas(
            hay_telegram=True, resumen_a_hora_fija=False, actualizar_de_noche=True)]
        self.assertIn("POS Actualizar", nombres)

    def test_corre_despues_del_corte_y_antes_del_respaldo(self) -> None:
        self.assertEqual(post.TAREA_ACTUALIZAR.schedule, ("/SC", "DAILY", "/ST", "19:30"))


class VersionDeCadaPcTests(unittest.TestCase):
    def test_se_lee_como_fecha_y_clave(self) -> None:
        self.assertEqual(reg.version_legible("2026.11.06+6ba73b01"), "6 nov · 6ba73b01")
        self.assertEqual(reg.version_legible("2026.11.11"), "2026.11.11")
        self.assertEqual(reg.version_legible(None), "")

    def test_las_atrasadas_son_las_que_dijeron_otra_version(self) -> None:
        filas = [
            {"nombre": "Entrada", "version": "2026.11.06+bbb2222"},
            {"nombre": "Caja", "version": "2026.11.05+aaa1111"},
            {"nombre": "Vieja", "version": None},              # no ha dicho: no se acusa
        ]
        self.assertEqual([f["nombre"] for f in reg.atrasadas(filas, publicada="2026.11.06+bbb2222")], ["Caja"])
        self.assertEqual(reg.atrasadas(filas, publicada=None), [])

    def test_el_latido_lleva_la_version(self) -> None:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session
        from sqlalchemy.pool import StaticPool

        from pos_uniformes.database.connection import Base

        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
        with Session(engine) as s, patch.object(reg, "es_de_desarrollo", return_value=False), \
                patch.object(reg, "_mi_version", return_value="2026.11.06+bbb2222"), \
                patch.object(reg, "_lo_que_imprime_esta_pc", return_value=""):
            reg.registrar(s, "pc-1", "Entrada")
            s.commit()
            self.assertEqual(reg.listar_con_estado(s)[0]["version"], "2026.11.06+bbb2222")
            with patch.object(reg, "_mi_version", return_value=None):       # sin sello no borra el que había
                reg.registrar(s, "pc-1", "Entrada")
                s.commit()
            self.assertEqual(reg.listar_con_estado(s)[0]["version"], "2026.11.06+bbb2222")


class VentaAMediasTests(unittest.TestCase):
    def test_con_carrito_no_se_ofrece_y_se_pospone(self) -> None:
        from pos_uniformes.ui.quote_satellite_window import QuoteSatelliteWindow

        fake = SimpleNamespace(quote_cart=[{"sku": "X"}], _posponer_actualizacion=MagicMock(),
                               _aplicar_actualizacion=MagicMock())
        with patch("pos_uniformes.ui.quote_satellite_window.QMessageBox") as mb:
            QuoteSatelliteWindow._ofrecer_actualizacion(fake, "2026.11.06+bbb2222")
        fake._posponer_actualizacion.assert_called_once_with("2026.11.06+bbb2222")
        mb.assert_not_called()                          # ni un diálogo encima de la venta
        fake._aplicar_actualizacion.assert_not_called()

    def test_pedido_desde_administracion_dice_por_que_no(self) -> None:
        from pos_uniformes.ui.quote_satellite_window import QuoteSatelliteWindow

        fake = SimpleNamespace(quote_cart=[{"sku": "X"}], _posponer_actualizacion=MagicMock())
        with patch("pos_uniformes.ui.quote_satellite_window.QMessageBox") as mb:
            QuoteSatelliteWindow._ofrecer_actualizacion(fake, "2026.11.06+bbb2222", parent=object())
        mb.information.assert_called_once()
        self.assertIn("venta a medias", mb.information.call_args.args[1])
        fake._posponer_actualizacion.assert_not_called()


class LosBatPasanPorElActualizadorTests(unittest.TestCase):
    def test_actualizar_pc_principal_ya_no_migra_antes_del_build(self) -> None:
        texto = _texto("actualizar_pc_principal.bat")
        self.assertIn("call scripts\\actualizar_seguro.bat", texto)
        self.assertNotIn("alembic upgrade head", texto)                    # eso lo decide actualizar.py
        self.assertNotIn("build_presupuestos_satelite_windows.bat", texto)
        self.assertLess(texto.index("git pull"), texto.index("actualizar_seguro.bat"))
        self.assertLess(texto.index("actualizar_seguro.bat"), texto.index("postactualizacion.bat --pasos-unicos"))
        # Si la actualización no quedó, no sigue con la postactualización.
        tras = texto.split("call scripts\\actualizar_seguro.bat", 1)[1]
        self.assertTrue(tras.lstrip().startswith("if errorlevel 1 goto :error"))

    def test_el_envoltorio_devuelve_el_codigo_de_salida(self) -> None:
        texto = _texto("actualizar_seguro.bat")
        self.assertIn("-m pos_uniformes.scripts.actualizar %*", texto)
        self.assertTrue(texto.rstrip().endswith("exit /b %ERRORLEVEL%"))

    def test_la_desatendida_trae_actualiza_y_solo_entonces_postactualiza(self) -> None:
        texto = _texto("actualizar_desatendida.bat")
        self.assertIn("actualizar_seguro.bat --traer", texto)
        self.assertLess(texto.index("actualizar_seguro.bat --traer"), texto.index("if errorlevel 1 exit /b 1"))
        self.assertLess(texto.index("if errorlevel 1 exit /b 1"), texto.index("postactualizacion.bat --pasos-unicos"))
        self.assertIn("ultimo_update.log", texto)

    def test_el_build_puede_no_publicar_y_publicar_guarda_la_anterior(self) -> None:
        build = _texto("build_presupuestos_satelite_windows.ps1")
        self.assertIn("[switch]$SinPublicar", build)
        # Un PyInstaller que falla tiene que salir con error: de eso depende no migrar.
        tras = build.split("-m PyInstaller", 1)[1]
        self.assertLess(tras.index("if ($LASTEXITCODE -ne 0)"), tras.index("Copy-Item"))
        self.assertIn("publicar_satelite.ps1", build)
        self.assertNotIn("robocopy", build)                                # la copia vive en un solo lugar
        publicar = _texto("publicar_satelite.ps1")
        self.assertIn("PresupuestosSatelite_anterior", publicar)
        # Primero se guarda la anterior y luego se pisa lo publicado.
        self.assertLess(publicar.index("robocopy $publishDir $anteriorDir /MIR"),
                        publicar.index("robocopy $BundleDir $publishDir /MIR"))
        self.assertIn("exit 1", publicar)
        # PowerShell 5.1 lee un .ps1 sin BOM como ANSI: nada de acentos.
        for nombre in ("publicar_satelite.ps1", "build_presupuestos_satelite_windows.ps1"):
            self.assertTrue(_texto(nombre).isascii(), nombre)

    def test_el_actualizador_llama_a_los_scripts_que_existen(self) -> None:
        fuente = (SCRIPTS / "actualizar.py").read_text(encoding="utf-8")
        for nombre in ("build_presupuestos_satelite_windows.ps1", "publicar_satelite.ps1"):
            self.assertIn(f'"{nombre}"', fuente)
            self.assertTrue((SCRIPTS / nombre).exists(), nombre)
        self.assertIn('"-SinPublicar"', fuente)
        self.assertTrue((SCRIPTS / "volver_version_anterior.bat").exists())


if __name__ == "__main__":
    unittest.main()
