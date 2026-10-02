"""¿Por qué no baja nada cuando le doy al acceso directo?

Daniel (02/10): "lo estoy intentando actualizar con el acceso directo y no pasa
nada". El acceso corre `abrir_pos.bat`, que mira cuántos commits le faltan a la
rama actual **contra su rama remota**. Si esta copia está parada en otra rama
—o en una sin rama remota— no le falta nada *de esa rama*, y el mensaje que
sale es «Ya estás al día»: una respuesta correcta a la pregunta equivocada.

Esto contesta la pregunta de verdad: en qué rama está esta copia, a cuál
remota mira, qué le falta, y si hay algo local estorbando. Y cuando el
problema es la rama, dice el comando exacto que lo arregla.

    python -m pos_uniformes.scripts.revisar_actualizacion
"""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

#: Donde vive el código que de verdad se está trabajando. Si esta copia mira a
#: otra, se dice. (main quedó parada en julio: todo lo nuevo va en esta rama.)
RAMA_BUENA = "chore/reorganizacion-repo"


def _git(*args: str, cwd: Path) -> tuple[int, str]:
    try:
        p = subprocess.run(
            ["git", *args], cwd=str(cwd), capture_output=True, text=True, timeout=60
        )
        return p.returncode, (p.stdout or p.stderr).strip()
    except Exception as exc:  # noqa: BLE001
        return 1, str(exc)


def diagnosticar(repo: Path) -> tuple[list[str], list[str]]:
    """(renglones del reporte, problemas encontrados). Problemas vacío = todo bien."""
    lineas: list[str] = []
    problemas: list[str] = []

    ok, rama = _git("rev-parse", "--abbrev-ref", "HEAD", cwd=repo)
    rama = rama if ok == 0 else "?"
    lineas.append(f"Rama de esta copia : {rama}")

    ok_up, arriba = _git("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}", cwd=repo)
    if ok_up != 0 or not arriba:
        arriba = ""
        lineas.append("Rama remota        : NINGUNA")
        problemas.append(
            f"La rama «{rama}» no está conectada a ninguna rama remota, así que\n"
            f"   `git pull` no sabe de dónde bajar y el acceso directo no hace nada.\n"
            f"   Se arregla con:  git checkout {RAMA_BUENA}"
        )
    else:
        lineas.append(f"Rama remota        : {arriba}")

    _git("fetch", "origin", cwd=repo)

    ok_h, head = _git("log", "-1", "--format=%h  %ad  %s", "--date=short", cwd=repo)
    if ok_h == 0:
        lineas.append(f"Último commit aquí : {head[:90]}")

    if arriba:
        ok_c, falta = _git("rev-list", f"HEAD..{arriba}", "--count", cwd=repo)
        if ok_c == 0 and falta.isdigit():
            lineas.append(f"Le faltan          : {falta} commit(s) de {arriba}")
            if int(falta) == 0 and rama != RAMA_BUENA:
                problemas.append(
                    f"Esta copia está al día CON «{arriba}», pero el código nuevo no vive ahí:\n"
                    f"   vive en «{RAMA_BUENA}». Por eso «Ya estás al día» y no baja nada.\n"
                    f"   Se arregla con:  git checkout {RAMA_BUENA}"
                )
        else:
            problemas.append("No se pudo contar lo que falta (¿sin internet?).")

    ok_r, remoto = _git("log", "-1", f"origin/{RAMA_BUENA}", "--format=%h  %ad  %s", "--date=short", cwd=repo)
    if ok_r == 0:
        lineas.append(f"Lo último de {RAMA_BUENA}:")
        lineas.append(f"   {remoto[:90]}")
        ok_f, faltan_buena = _git("rev-list", f"HEAD..origin/{RAMA_BUENA}", "--count", cwd=repo)
        if ok_f == 0 and faltan_buena.isdigit() and int(faltan_buena) > 0:
            lineas.append(f"   → a esta copia le faltan {faltan_buena} de esos.")

    ok_s, sucio = _git("status", "--porcelain", cwd=repo)
    cambios = [l for l in sucio.splitlines() if l.strip() and not l.startswith("??")]
    if cambios:
        lineas.append(f"Cambios locales    : {len(cambios)} archivo(s) modificados")
        for c in cambios[:5]:
            lineas.append(f"   {c}")
        problemas.append(
            "Hay archivos cambiados aquí; el pull puede estar negándose.\n"
            "   Si no los hiciste a propósito:  git checkout -- ."
        )
    else:
        lineas.append("Cambios locales    : ninguno 👍")

    ok_a, version = _git("rev-parse", "--short", "HEAD", cwd=repo)
    publicado = _version_publicada()
    if publicado:
        lineas.append(f"Kioskos corriendo  : {publicado}")
        if ok_a == 0 and version and version not in publicado:
            lineas.append(f"   (el código aquí va en {version})")

    return lineas, problemas


def _version_publicada() -> str:
    import os

    base = os.getenv("POS_UNIFORMES_UPDATES_DIR") or r"C:\pos_updates"
    ruta = Path(base) / "PresupuestosSatelite" / "VERSION.txt"
    try:
        return ruta.read_text(encoding="utf-8", errors="ignore").strip()
    except Exception:  # noqa: BLE001
        return ""


def main(argv: list[str] | None = None) -> int:
    repo = Path(__file__).resolve().parents[1]
    lineas, problemas = diagnosticar(repo)

    salida = ["=" * 62, "  ¿POR QUÉ NO BAJA NADA?", "=" * 62, ""]
    salida += lineas
    salida.append("")
    if problemas:
        salida.append("-" * 62)
        for p in problemas:
            salida.append(f"⚠️  {p}")
            salida.append("")
        salida.append("Después de arreglarlo, vuelve a darle al acceso directo.")
    else:
        salida.append("✅ No veo nada raro: la rama está bien conectada y sin pendientes.")
        salida.append("   Si aun así no baja, manda este reporte con enviar_reporte.bat")
    salida.append("")
    salida.append(f"({datetime.now():%d/%m/%Y %H:%M})")

    texto = "\n".join(salida)
    print(texto)
    try:
        destino = repo / "reportes" / "actualizacion.txt"
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(texto, encoding="utf-8")
        print(f"\n(También quedó en {destino})")
    except Exception:  # noqa: BLE001
        pass
    return 1 if problemas else 0


if __name__ == "__main__":
    raise SystemExit(main())
