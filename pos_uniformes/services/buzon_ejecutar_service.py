"""Correr en ESTA PC un comando que llegó por el buzón, y regresar lo que salió.

Para los comandos que Claude y Daniel arman en la Mac (Daniel, 2026-10-15). El
camino a mano era de ocho pasos —copiar, abrir PowerShell, pegar, seleccionar lo
que salió, copiar, volver, pegar, enviar— y en uno se mandó el script en vez del
resultado. Aquí es un botón, con tres candados:

- Solo se ofrece en mensajes de remitentes de confianza (Claude, la PC principal).
- Antes de correr se enseña el comando completo y se pide el PIN de admin.
- Tiene tiempo límite: un comando trabado no congela el kiosko.

Lo que sale se manda de regreso al chat de quien lo pidió. Nada corre solo.
"""

from __future__ import annotations

import base64
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass

#: Quién puede mandar algo que se ofrezca para ejecutar.
REMITENTES_DE_CONFIANZA = ("Claude", "PC principal")
#: Segundos antes de cortar un comando que no termina.
TIEMPO_LIMITE = 120
#: Ancho de las tablas de PowerShell: sin esto las corta a 80 columnas.
ANCHO_SALIDA = 220


@dataclass(frozen=True)
class Resultado:
    salida: str
    codigo: int | None          # None = no terminó (tiempo límite) o no corrió
    segundos: float
    error: str = ""             # por qué no corrió, dicho para enseñarlo

    @property
    def ok(self) -> bool:
        return not self.error and self.codigo == 0


def puede_ejecutarse(de: str) -> bool:
    return (de or "").strip() in REMITENTES_DE_CONFIANZA


def _powershell() -> str | None:
    for nombre in ("powershell", "pwsh"):
        ruta = shutil.which(nombre)
        if ruta:
            return ruta
    return None


def armar_comando(script: str, ejecutable: str = "powershell") -> list[str]:
    """El comando listo para `subprocess`, sin problemas de comillas.

    Va en `-EncodedCommand` (UTF-16 en base64): así las comillas, los `$` y los
    saltos del script llegan tal cual, sin que nadie los reinterprete. Todo lo
    que escriba (también los errores) sale en UTF-8 y a lo ancho."""
    envuelto = (
        "try { $OutputEncoding = [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch {}\n"
        "& {\n" + script + "\n} *>&1 | Out-String -Width " + str(ANCHO_SALIDA)
    )
    codificado = base64.b64encode(envuelto.encode("utf-16-le")).decode("ascii")
    return [ejecutable, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
            "-EncodedCommand", codificado]


def _matar_arbol(proc) -> None:
    """Mata al proceso Y a lo que haya lanzado. `kill()` solo no basta en
    Windows: un hijo de PowerShell vivo deja todo colgado."""
    if sys.platform.startswith("win"):
        try:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=15, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except Exception:  # noqa: BLE001
            pass
    try:
        proc.kill()
    except Exception:  # noqa: BLE001
        pass


def ejecutar(script: str, *, tiempo_limite: int = TIEMPO_LIMITE) -> Resultado:
    """Corre el script en PowerShell y devuelve lo que salió. Nunca lanza.

    Blindado tras la primera prueba en la tienda (2026-10-15): el botón se quedó
    en «Ejecutando…» para siempre y ni el tiempo límite avisó. Tres cambios:

    - La entrada va cerrada (`DEVNULL`). El kiosko instalado no tiene consola, y
      un PowerShell lanzado sin entrada propia puede quedarse esperándola.
    - La salida va a un ARCHIVO, no a una tubería: leer una tubería se cuelga
      si queda vivo cualquier proceso que la tenga abierta, aun después de
      matar a PowerShell. Un archivo se lee siempre.
    - Al pasar del límite se mata el árbol completo, no solo PowerShell.
    """
    import os
    import tempfile

    ejecutable = _powershell()
    if ejecutable is None:
        return Resultado("", None, 0.0, error="Esta PC no tiene PowerShell.")
    inicio = time.monotonic()
    extra = {}
    if sys.platform.startswith("win"):
        extra["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    fd, ruta = tempfile.mkstemp(prefix="buzon_", suffix=".txt")
    error = ""
    codigo: int | None = None
    try:
        with os.fdopen(fd, "wb") as archivo:
            try:
                proc = subprocess.Popen(
                    armar_comando(script, ejecutable),
                    stdin=subprocess.DEVNULL,
                    stdout=archivo,
                    stderr=subprocess.STDOUT,
                    **extra,
                )
            except Exception as exc:  # noqa: BLE001 — se reporta, no se truena
                return Resultado("", None, time.monotonic() - inicio, error=f"No se pudo correr: {exc}")
            try:
                codigo = proc.wait(timeout=tiempo_limite)
            except subprocess.TimeoutExpired:
                _matar_arbol(proc)
                try:
                    proc.wait(timeout=10)
                except Exception:  # noqa: BLE001 — ya se le mató; no se espera más
                    pass
                error = f"Se cortó: pasó de {tiempo_limite} segundos sin terminar."
        with open(ruta, "rb") as leido:
            salida = leido.read().decode("utf-8", errors="replace")
    finally:
        try:
            os.remove(ruta)
        except Exception:  # noqa: BLE001
            pass
    return Resultado(salida, None if error else codigo, time.monotonic() - inicio, error=error)


def texto_de_resultado(resultado: Resultado, *, pc: str, maximo: int) -> str:
    """El mensaje que regresa al chat: de qué PC, cómo le fue y lo que salió."""
    if resultado.error:
        cabeza = f"⚠️ {pc}: {resultado.error}"
    elif resultado.codigo == 0:
        cabeza = f"▶ Resultado en {pc} (terminó bien, {resultado.segundos:.1f} s)"
    else:
        cabeza = f"⚠️ Resultado en {pc} (terminó con código {resultado.codigo}, {resultado.segundos:.1f} s)"
    cuerpo = (resultado.salida or "").strip() or "(no escribió nada)"
    texto = f"{cabeza}\n\n{cuerpo}"
    if len(texto) > maximo:
        aviso = "\n\n[…se cortó: era más largo de lo que cabe en un mensaje]"
        texto = texto[: maximo - len(aviso)] + aviso
    return texto
