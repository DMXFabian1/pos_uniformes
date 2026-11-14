"""El lanzador del kiosko no debe dejar un .exe a medias.

Un robocopy interrumpido (red, antivirus) dejaba el programa truncado y,
como VERSION.txt ya decía la versión nueva, el kiosko quedaba atorado con
"Could not load PyInstaller's embedded PKG archive" (2026-09-10).
"""

from __future__ import annotations

import unittest
from pathlib import Path

_PS1 = Path(__file__).resolve().parents[1] / "scripts" / "lanzador_satelite.ps1"
_FORZAR = Path(__file__).resolve().parents[1] / "scripts" / "forzar_update_satelite.bat"


class LanzadorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.texto = _PS1.read_text(encoding="utf-8", errors="ignore")

    def test_la_version_se_escribe_hasta_el_final(self) -> None:
        # robocopy no copia VERSION.txt...
        self.assertIn("/XF VERSION.txt", self.texto)
        # ...y solo se copia si la copia quedó completa.
        i_ok = self.texto.index("if ($copiaOk)")
        i_version = self.texto.index('Copy-Item (Join-Path $share "VERSION.txt")')
        self.assertLess(i_ok, i_version)

    def test_verifica_el_tamano_del_programa(self) -> None:
        self.assertIn("$exeRemoto.Length", self.texto)
        self.assertIn("$codigo = $LASTEXITCODE", self.texto)
        self.assertIn("-lt 8", self.texto)  # robocopy: 8 o más es error

    def test_recupera_un_exe_incompleto_aunque_la_version_coincida(self) -> None:
        self.assertIn("quedo incompleto", self.texto)
        # La red de seguridad corre antes de arrancar el programa.
        self.assertLess(self.texto.index("quedo incompleto"), self.texto.index("Start-Process $exe.FullName"))


class ReparadorTests(unittest.TestCase):
    """El kiosko se repara solo, sin depender de la PC principal."""

    def test_el_lanzador_se_lleva_el_reparador_al_kiosko(self) -> None:
        texto = _PS1.read_text(encoding="utf-8", errors="ignore")
        self.assertIn("reparar_satelite.bat", texto)

    def test_el_reparador_borra_la_marca_y_abre_el_lanzador(self) -> None:
        rep = _PS1.parent / "reparar_satelite.bat"
        texto = rep.read_text(encoding="utf-8", errors="ignore")
        self.assertIn("VERSION.txt", texto)
        self.assertIn("taskkill", texto)
        self.assertIn("lanzador_satelite.bat", texto)

    def test_el_build_lo_publica(self) -> None:
        # Desde 2026-11-06 la publicación vive en publicar_satelite.ps1 (el
        # build la llama, y el actualizador también, después de migrar).
        build = (_PS1.parent / "build_presupuestos_satelite_windows.ps1").read_text(encoding="utf-8", errors="ignore")
        self.assertIn("publicar_satelite.ps1", build)
        publicar = (_PS1.parent / "publicar_satelite.ps1").read_text(encoding="utf-8", errors="ignore")
        self.assertIn("reparar_satelite.bat", publicar)
        self.assertIn("lanzador_satelite.ps1", publicar)


class ForzarUpdateTests(unittest.TestCase):
    def test_borra_la_marca_de_version(self) -> None:
        texto = _FORZAR.read_text(encoding="utf-8", errors="ignore")
        self.assertIn("VERSION.txt", texto)
        self.assertIn("del /q", texto)


# ---------------------------------------------------------------------------
# 2026-11-13: el Kiosko Principal se apagó mientras el lanzador se copiaba a sí
# mismo y al prender el .ps1 estaba lleno de ceros («El término '' no se
# reconoce… línea 1 carácter 1»). Ningún script escribe ya directo sobre un
# lanzador bueno: temporal «.nuevo» → validar → reemplazo en el mismo disco.
# ---------------------------------------------------------------------------

_SCRIPTS = _PS1.parent
_BAT = _SCRIPTS / "lanzador_satelite.bat"
_REPARAR = _SCRIPTS / "reparar_satelite.bat"
_PUBLICAR = _SCRIPTS / "publicar_satelite.ps1"
_TOCADOS = (_PS1, _BAT, _REPARAR, _FORZAR, _PUBLICAR)

_MARCA_PS1 = "# Lanzador del satelite"
_FIN_PS1 = "# Fin del lanzador del satelite"
_FIN_BAT = "rem Fin del lanzador del satelite"


def _texto(ruta: Path) -> str:
    return ruta.read_bytes().decode("ascii").replace("\r\n", "\n")


def _findstr_b(texto: str, marca: str) -> bool:
    """Lo que hace `findstr /b /l /c:"<marca>"`: alguna línea empieza así."""
    return any(linea.startswith(marca) for linea in texto.split("\n"))


def _bloque(texto: str, etiqueta: str) -> str:
    """Las líneas de una subrutina de .bat, de `:etiqueta` a la siguiente."""
    resto = texto.split(f"\n{etiqueta}\n", 1)[1]
    return resto.split("\n:", 1)[0]


class LanzadorSeEscribeSeguroTests(unittest.TestCase):
    def setUp(self) -> None:
        self.ps1 = _texto(_PS1)

    def test_ya_no_se_copia_a_ciegas_sobre_si_mismo(self) -> None:
        self.assertNotIn("$PSScriptRoot -Force", self.ps1)
        self.assertNotIn("Copy-Item (Join-Path $updatesRoot", self.ps1)

    def test_temporal_a_disco_validar_y_reemplazar(self) -> None:
        copia = self.ps1.split("function Copy-Seguro", 1)[1].split("\nfunction ", 1)[0]
        self.assertIn('$tmp = "$destino.nuevo"', copia)
        self.assertIn("$salida.Flush($true)", copia)
        self.assertIn("[System.IO.File]::Replace($tmp, $destino, [NullString]::Value)", copia)
        self.assertIn("[System.IO.File]::Move($tmp, $destino)", copia)
        # Se valida (tamaño y marcas) ANTES de poner el archivo en su lugar.
        i_replace = copia.index("[System.IO.File]::Replace")
        self.assertLess(copia.index(".Length -ne (Get-Item -LiteralPath $origen).Length"), i_replace)
        self.assertLess(copia.index("Test-ArchivoLanzador $tmp $nombre"), i_replace)
        # Si algo falla, el temporal se borra y el bueno no se toca.
        self.assertIn("Remove-Item -LiteralPath $tmp", copia.split("} catch {", 1)[1])
        self.assertIn('$ErrorActionPreference = "Stop"', copia)

    def test_la_validacion_revisa_marcas_y_sintaxis(self) -> None:
        valida = self.ps1.split("function Test-ArchivoLanzador", 1)[1].split("\nfunction ", 1)[0]
        self.assertIn("$bytes.Length -eq 0", valida)
        self.assertIn(f'StartsWith("{_MARCA_PS1}", $ordinal)', valida)
        self.assertIn('StartsWith("@echo off", $ordinal)', valida)
        self.assertIn("EndsWith($marcaFinPs1, $ordinal)", valida)
        # Ordinal: en comparación cultural .NET ignora los caracteres nulos y
        # un archivo de puros ceros "empezaría" con cualquier cosa.
        self.assertIn("[System.StringComparison]::Ordinal", valida)
        self.assertIn("Language.Parser]::ParseInput", valida)
        self.assertIn(f'$marcaFinPs1 = "{_FIN_PS1}"', self.ps1)

    def test_solo_copia_lo_que_cambio_y_limpia_temporales(self) -> None:
        actualiza = self.ps1.split("function Update-ArchivosLanzador", 1)[1].split("\nfunction ", 1)[0]
        self.assertLess(actualiza.index("Test-MismoArchivo $origen $destino"), actualiza.index("Copy-Seguro"))
        # Lo publicado se valida antes de copiarlo.
        self.assertLess(actualiza.index("Test-ArchivoLanzador $origen $f"), actualiza.index("Copy-Seguro"))
        self.assertIn("Get-FileHash", self.ps1)
        self.assertIn('Remove-Item -LiteralPath "$viejo.nuevo"', self.ps1)
        for nombre in ("lanzador_satelite.ps1", "lanzador_satelite.bat", "reparar_satelite.bat"):
            self.assertIn(f'"{nombre}"', self.ps1.split("$archivosLanzador = @(", 1)[1].split(")", 1)[0])

    def test_respaldo_tras_arrancar_y_antes_de_refrescarse(self) -> None:
        respaldo = self.ps1.split("function Save-RespaldoLanzador", 1)[1].split("\n}\n", 1)[0]
        self.assertIn('$respaldo = "$actual.respaldo"', respaldo)
        self.assertIn("Copy-Seguro $actual $respaldo $f", respaldo)
        i_arranca = self.ps1.index("Start-Process $exe.FullName")
        i_respaldo = self.ps1.index("if ($arranco) { Save-RespaldoLanzador }")
        i_refresca = self.ps1.index("if (Test-Path $share) { Update-ArchivosLanzador $updatesRoot }")
        self.assertLess(i_arranca, i_respaldo)
        self.assertLess(i_respaldo, i_refresca)

    def test_marcas_que_revisa_el_bat(self) -> None:
        lineas = self.ps1.rstrip("\n").split("\n")
        self.assertTrue(lineas[0].startswith(_MARCA_PS1))
        self.assertEqual(lineas[-1], _FIN_PS1)
        # findstr /b no distingue la línea: cada marca debe abrir UNA sola línea.
        self.assertEqual(sum(l.startswith(_MARCA_PS1) for l in lineas), 1)
        self.assertEqual(sum(l.startswith(_FIN_PS1) for l in lineas), 1)
        # Un .ps1 lleno de ceros (el apagón) o cortado no pasa.
        self.assertFalse(_findstr_b("\0" * 4000, _MARCA_PS1))
        cortado = self.ps1[: len(self.ps1) // 2]
        self.assertFalse(_findstr_b(cortado, _FIN_PS1))


class BatSeProtegeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.bat = _texto(_BAT)
        self.crudo = _BAT.read_bytes()

    def test_revisa_el_ps1_antes_de_abrirlo_y_lo_restaura(self) -> None:
        principal = self.bat.split("\n:abrir\n", 1)[0]
        orden = [
            'call :ps1_bueno "%PS1%" && goto :abrir',
            'call :restaurar "%PS1%.respaldo" && goto :abrir',
            'call :restaurar "C:\\pos_updates\\lanzador_satelite.ps1" && goto :abrir',
            'call :restaurar "\\\\%SERVIDOR%\\pos_updates\\lanzador_satelite.ps1" && goto :abrir',
            "pause",
        ]
        posiciones = [principal.index(paso) for paso in orden]
        self.assertEqual(posiciones, sorted(posiciones))
        bueno = _bloque(self.bat, ":ps1_bueno")
        self.assertIn(f'findstr /b /l /c:"{_MARCA_PS1}"', bueno)
        self.assertIn(f'findstr /b /l /c:"{_FIN_PS1}"', bueno)

    def test_servidor_del_env_con_el_mismo_default(self) -> None:
        self.assertIn('set "SERVIDOR=192.168.0.10"', self.bat)
        self.assertIn("POS_UNIFORMES_SERVER_HOST", self.bat)
        self.assertIn(r"%LOCALAPPDATA%\PresupuestosSatelite\app\pos_uniformes.env", self.bat)

    def test_restaurar_usa_temporal_validado_y_move(self) -> None:
        restaurar = _bloque(self.bat, ":restaurar")
        i_copy = restaurar.index('copy /y "%~1" "%PS1%.nuevo"')
        i_valida = restaurar.index('call :ps1_bueno "%PS1%.nuevo"')
        i_move = restaurar.index('move /y "%PS1%.nuevo" "%PS1%"')
        self.assertLess(i_copy, i_valida)
        self.assertLess(i_valida, i_move)
        self.assertIn('if not "%T1%"=="%T2%"', restaurar)

    def test_powershell_y_salida_en_la_misma_linea(self) -> None:
        # cmd.exe relee el .bat tras cada comando y el .ps1 lo reemplaza.
        self.assertIn('powershell -ExecutionPolicy Bypass -File "%PS1%" & exit /b\n', self.bat)

    def test_el_bat_viejo_retoma_en_un_exit(self) -> None:
        # El lanzador.bat viejo medía 216 bytes; el .ps1 viejo lo reemplaza
        # por este mientras cmd espera, y cmd sigue leyendo en el byte 216.
        self.assertTrue(self.crudo[216:].startswith(b"exit /b\r\n"))
        self.assertTrue(self.crudo[:216].endswith(b"\r\ngoto :inicio\r\n"))

    def test_marca_de_fin_del_bat(self) -> None:
        self.assertTrue(self.bat.startswith("@echo off\n"))
        self.assertEqual(self.bat.rstrip("\n").split("\n")[-1].split(" (")[0], _FIN_BAT)


class ReparadorTraeLanzadorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.rep = _texto(_REPARAR)

    def test_trae_el_lanzador_antes_de_abrirlo(self) -> None:
        i_ps1 = self.rep.index("call :traer lanzador_satelite.ps1")
        i_bat = self.rep.index("call :traer lanzador_satelite.bat")
        i_abre = self.rep.index('start "" "%DESTINO%lanzador_satelite.bat" & exit /b 0')
        self.assertLess(i_ps1, i_abre)
        self.assertLess(i_bat, i_abre)
        self.assertIn("goto :sin_lanzador", self.rep[i_ps1:i_abre])
        self.assertIn("pause", _bloque(self.rep, ":sin_lanzador"))

    def test_orden_de_las_fuentes_y_lo_dice_en_pantalla(self) -> None:
        traer = _bloque(self.rep, ":traer")
        orden = [
            r'call :copiar_validado "C:\pos_updates\%~1"',
            r'call :copiar_validado "\\%SERVIDOR%\pos_updates\%~1"',
            'call :copiar_validado "%ARCH%.respaldo"',
            'call :es_bueno "%ARCH%" "%~2" ""',
        ]
        posiciones = [traer.index(paso) for paso in orden]
        self.assertEqual(posiciones, sorted(posiciones))
        self.assertEqual(traer.count("echo   %~1:"), 5)

    def test_copia_validada(self) -> None:
        copia = _bloque(self.rep, ":copiar_validado")
        pasos = ['copy /y "%~1" "%~2.nuevo"', 'if not "%T1%"=="%T2%"',
                 'call :es_bueno "%~2.nuevo"', 'move /y "%~2.nuevo" "%~2"']
        posiciones = [copia.index(p) for p in pasos]
        self.assertEqual(posiciones, sorted(posiciones))

    def test_nunca_escribe_en_la_carpeta_de_red(self) -> None:
        self.assertIn('if "%DESTINO:~0,2%"=="\\\\" set "DESTINO=C:\\PresupuestosSatelite\\"', self.rep)


class ForzarSinPisarTests(unittest.TestCase):
    def setUp(self) -> None:
        self.forzar = _texto(_FORZAR)

    def test_no_copia_a_ciegas(self) -> None:
        self.assertNotIn('copy /y "\\\\', self.forzar)
        copia = _bloque(self.forzar, ":copiar_validado")
        self.assertIn('copy /y "%~1" "%~2.nuevo"', copia)
        self.assertIn('move /y "%~2.nuevo" "%~2"', copia)
        self.assertLess(self.forzar.index("call :traer lanzador_satelite.ps1"),
                        self.forzar.index('start "" C:\\PresupuestosSatelite\\lanzador_satelite.bat'))

    def test_servidor_del_env(self) -> None:
        self.assertIn("POS_UNIFORMES_SERVER_HOST", self.forzar)
        self.assertEqual(self.forzar.count("192.168.0.10"), 1)
        self.assertIn('set "SERVIDOR=192.168.0.10"', self.forzar)


class PublicarSeguroTests(unittest.TestCase):
    def setUp(self) -> None:
        self.pub = _texto(_PUBLICAR)

    def test_publica_con_temporal_y_reemplazo(self) -> None:
        funcion = self.pub.split("function Publicar-Archivo", 1)[1].split("\n}\n", 1)[0]
        self.assertIn('$tmp = "$destino.nuevo"', funcion)
        self.assertIn("$salida.Flush($true)", funcion)
        i_tamano = funcion.index("copia incompleta")
        i_replace = funcion.index("[System.IO.File]::Replace($tmp, $destino, [NullString]::Value)")
        self.assertLess(i_tamano, i_replace)
        self.assertIn("Language.Parser]::ParseInput", funcion)
        self.assertNotIn('Copy-Item (Join-Path $PSScriptRoot "lanzador', self.pub)
        for nombre in ("lanzador_satelite.ps1", "lanzador_satelite.bat", "reparar_satelite.bat",
                       "instalar_servidor_impresion_kiosko.bat"):
            self.assertIn(f'Publicar-Archivo "{nombre}"', self.pub)


class ScriptsDelKioskoSinSecretosTests(unittest.TestCase):
    def test_ninguna_credencial_nueva(self) -> None:
        # Las únicas líneas con usuario de red en scripts/ son las que ya había.
        encontradas = set()
        for ruta in _SCRIPTS.rglob("*"):
            if not ruta.is_file():
                continue
            texto = ruta.read_bytes().decode("utf-8", errors="ignore")
            for linea in texto.splitlines():
                if "/user:" in linea:
                    encontradas.add((ruta.name, linea.strip()))
        self.assertEqual({nombre for nombre, _ in encontradas},
                         {"lanzador_satelite.ps1", "instalar_kiosko_aqui.bat", "preparar_share_updates.bat"})
        self.assertEqual(len(encontradas), 3)
        self.assertEqual(_texto(_PS1).count("/user:"), 1)
        for ruta in (_BAT, _REPARAR, _FORZAR, _PUBLICAR):
            texto = _texto(ruta)
            for prohibido in ("/user:", "net use", "pos2026"):
                self.assertNotIn(prohibido, texto, f"{ruta.name}: {prohibido}")

    def test_sin_ips_nuevas(self) -> None:
        import re

        for ruta in _TOCADOS:
            ips = set(re.findall(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", _texto(ruta)))
            self.assertLessEqual(ips, {"192.168.0.10"}, ruta.name)

    def test_crlf_y_ascii(self) -> None:
        for ruta in _TOCADOS:
            crudo = ruta.read_bytes()
            self.assertTrue(crudo.isascii(), ruta.name)
            self.assertEqual(crudo.count(b"\n"), crudo.count(b"\r\n"), ruta.name)
            self.assertFalse(crudo.startswith(b"\xef\xbb\xbf"), ruta.name)


if __name__ == "__main__":
    unittest.main()
