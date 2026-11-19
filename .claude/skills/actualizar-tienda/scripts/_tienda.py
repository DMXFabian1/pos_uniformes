"""Piezas de la skill actualizar-tienda. Nada aquí escribe ni se conecta a la base.

- git del tronco que corre la tienda (`origin/chore/reorganizacion-repo`, NUNCA la rama local).
- La cadena de migraciones de Alembic leída del propio git (sin `alembic`, sin base):
  revisión, de qué sale, primera línea del docstring y si usa `get_bind` (esas truenan
  en el modo `--sql` y rellenan datos al migrar).
- ¿Un commit conoce tal revisión? (mismo criterio que `scripts/actualizar.py`: si no la
  conoce, ese programa NO abre contra la base migrada).
"""
from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "alta-productos" / "scripts"))
import _comun  # noqa: E402

RAIZ = _comun.RAIZ
RAMA_TRONCO = "chore/reorganizacion-repo"
TRONCO = f"origin/{RAMA_TRONCO}"
CARPETA_MIG = "pos_uniformes/migrations/versions"

_REV = re.compile(r"^revision\s*(?::[^=\n]+)?=\s*['\"]([^'\"]+)['\"]", re.M)
_DOWN = re.compile(r"^down_revision\s*(?::[^=\n]+)?=\s*(.+)$", re.M)
_DOC = re.compile(r"\A\s*(?:#[^\n]*\n\s*)*[rRuU]?(?:\"\"\"|''')\s*(.*)")
_HASH = re.compile(r"\+([0-9a-f]{6,40})\s*$")


def leer_env(ruta: str) -> dict[str, str]:
    """Lee un pos_uniformes.env a un dict SIN tocar os.environ (trae token de Telegram, etc.)."""
    archivo = Path(ruta).expanduser()
    if not archivo.is_file():
        raise SystemExit(f"ERROR: no existe el env «{archivo}».")
    res: dict[str, str] = {}
    for linea in archivo.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if linea and not linea.startswith("#") and "=" in linea:
            k, v = linea.split("=", 1)
            res[k.strip()] = v.strip().strip('"').strip("'")
    return res


def carpeta_igual_a(ref: str) -> str | None:
    """Alembic lee los archivos del DISCO: deben ser idénticos a `ref`. Devuelve el problema o None."""
    rc, _ = git("diff", "--quiet", ref, "--", CARPETA_MIG)
    if rc != 0:
        return f"las migraciones de esta carpeta no son las de {ref} (cambios sin commit o en otro commit)"
    rc, out = git("status", "--porcelain", "--untracked-files=all", "--", CARPETA_MIG)
    if rc == 0 and out:
        return f"hay migraciones sin rastrear en la carpeta: {out.splitlines()[0][3:]}"
    return None


def entorno_alembic(url: str) -> dict[str, str]:
    """Entorno mínimo para un subproceso de alembic: solo PATH/HOME y la URL dada.
    POS_UNIFORMES_DB_URL gana sobre cualquier pos_uniformes.env que Settings encuentre."""
    import os

    env = {k: os.environ[k] for k in ("PATH", "HOME", "LANG", "TMPDIR") if k in os.environ}
    env["POS_UNIFORMES_DB_URL"] = url
    return env


def git(*args: str, timeout: float = 90) -> tuple[int, str]:
    r = subprocess.run(
        ["git", *args], cwd=str(RAIZ), capture_output=True, text=True,
        timeout=timeout, stdin=subprocess.DEVNULL,
    )
    return r.returncode, (r.stdout or "").strip() or (r.stderr or "").strip()


def traer_tronco() -> str | None:
    """`git fetch` del tronco (solo mueve referencias remotas). Devuelve el error o None."""
    rc, out = git("fetch", "-q", "origin", RAMA_TRONCO)
    return None if rc == 0 else out


def sello(ref: str) -> str:
    """«2026.11.19+12842fea»: el mismo formato que late cada PC en `satelite.version`."""
    rc, out = git("log", "-1", "--format=%cd+%h", "--date=format:%Y.%m.%d", ref)
    return out if rc == 0 else ""


def hash_de(version: str | None) -> str | None:
    m = _HASH.search(version or "")
    return m.group(1) if m else None


def existe(commit: str) -> bool:
    return git("cat-file", "-e", f"{commit}^{{commit}}")[0] == 0


def mismo_commit(a: str | None, b: str | None) -> bool:
    """Por prefijo: Windows puede dar 7 caracteres y la Mac 8."""
    if not a or not b:
        return False
    n = min(len(a), len(b))
    return a[:n] == b[:n]


def commits_atras(commit: str, ref: str = TRONCO) -> int | None:
    rc, out = git("rev-list", "--count", f"{commit}..{ref}")
    return int(out) if rc == 0 and out.isdigit() else None


def es_ancestro(commit: str, ref: str = TRONCO) -> bool:
    return git("merge-base", "--is-ancestor", commit, ref)[0] == 0


def conoce_revision(commit: str, rev: str) -> bool:
    """¿El código de ese commit trae la migración `rev`? (git grep, sin base)."""
    rc, _ = git("grep", "-q", "-E", rf"^revision.*['\"]{re.escape(rev)}['\"]", commit, "--", CARPETA_MIG)
    return rc == 0


@dataclass
class Migracion:
    rev: str
    down: tuple[str, ...]
    titulo: str
    archivo: str
    usa_get_bind: bool


def migraciones(ref: str = TRONCO) -> dict[str, Migracion]:
    rc, out = git("ls-tree", "-r", "--name-only", ref, "--", CARPETA_MIG)
    if rc != 0:
        raise SystemExit(f"ERROR: no pude listar las migraciones de {ref}: {out}")
    res: dict[str, Migracion] = {}
    for ruta in out.splitlines():
        if not ruta.endswith(".py") or ruta.endswith("__init__.py"):
            continue
        rc, src = git("show", f"{ref}:{ruta}")
        m = _REV.search(src) if rc == 0 else None
        if not m:
            continue
        d = _DOWN.search(src)
        down = tuple(re.findall(r"['\"]([^'\"]+)['\"]", d.group(1))) if d else ()
        doc = _DOC.match(src)
        titulo = (doc.group(1).strip().rstrip('"').rstrip("'").strip() if doc else "") or Path(ruta).stem
        res[m.group(1)] = Migracion(m.group(1), down, titulo, ruta, "get_bind" in src)
    return res


def cabezas(migs: dict[str, Migracion]) -> list[str]:
    usadas = {d for m in migs.values() for d in m.down}
    return sorted(r for r in migs if r not in usadas)


def ancestros(migs: dict[str, Migracion], rev: str) -> set[str]:
    """`rev` y todas las anteriores."""
    vistos: set[str] = set()
    pila = [rev]
    while pila:
        r = pila.pop()
        if r in vistos or r not in migs:
            continue
        vistos.add(r)
        pila.extend(migs[r].down)
    return vistos


def pendientes(migs: dict[str, Migracion], aplicadas: list[str], heads: list[str]) -> list[Migracion]:
    """Lo que falta para llegar a las cabezas, en orden de aplicación."""
    hechas: set[str] = set()
    for a in aplicadas:
        hechas |= ancestros(migs, a)
    faltan: set[str] = set()
    for h in heads:
        faltan |= ancestros(migs, h)
    faltan -= hechas
    prof: dict[str, int] = {}

    def profundidad(r: str) -> int:
        if r not in prof:
            prof[r] = 1 + max((profundidad(d) for d in migs[r].down if d in migs), default=0)
        return prof[r]

    return [migs[r] for r in sorted(faltan, key=lambda r: (profundidad(r), r))]
