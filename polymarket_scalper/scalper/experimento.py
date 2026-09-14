"""Congelar el motor antes de medir, para que todos los datos vengan de la misma versión.

Comparar operaciones producidas por motores distintos no mide nada: si a mitad del experimento
se cambia un umbral, la muestra pasa a mezclar dos sistemas y el resultado no es de ninguno de
los dos. Este módulo toma una huella de lo que decide el comportamiento:

- el commit del repositorio, y si el árbol de trabajo estaba sucio;
- todos los umbrales que usan los detectores y el simulador;
- la versión de cada modelo aprendido que esté en uso.

De esa huella sale un `experiment_id`. Cada fila del ledger y cada decisión lo llevan. Si algo de
lo anterior cambia, la huella cambia y empieza otro experimento: los datos quedan separados solos,
sin que nadie tenga que acordarse de hacerlo.
"""
from __future__ import annotations

import hashlib
import json
import logging
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import Config
from .storage import ParquetWriter, dumps, scan

log = logging.getLogger(__name__)


def _git(*args: str) -> str:
    try:
        raiz = Path(__file__).resolve().parents[2]
        out = subprocess.run(["git", *args], cwd=raiz, capture_output=True, text=True, timeout=10)
        return out.stdout.strip() if out.returncode == 0 else ""
    except Exception:  # noqa: BLE001 - sin git el experimento sigue siendo válido, solo menos rastreable
        return ""


def version_simulador(raiz: Path | None = None) -> str:
    """Huella del código que simula la ejecución, aparte del commit.

    El commit ya cubre esto cuando el árbol está limpio, pero con el árbol sucio no cubre nada: se
    puede editar el modelo de llenado a mitad de una sesión y seguir informando del mismo commit.
    Estos son los archivos que deciden qué se llena, a qué precio y cuándo se cierra, así que
    cualquier cambio en ellos tiene que mover la huella.
    """
    base = raiz or Path(__file__).resolve().parent
    partes: list[str] = []
    for rel in ("sim/fill_model.py", "sim/engine.py", "sim/ledger.py", "book.py", "fees.py", "pata.py"):
        f = base / rel
        try:
            partes.append(f"{rel}:{hashlib.sha256(f.read_bytes()).hexdigest()[:16]}")
        except OSError:
            partes.append(f"{rel}:ausente")
    return hashlib.sha256("|".join(partes).encode("utf-8")).hexdigest()[:16]


def commit_actual() -> tuple[str, bool]:
    """Hash corto del commit y si había cambios sin comprometer."""
    return _git("rev-parse", "--short", "HEAD"), bool(_git("status", "--porcelain"))


def umbrales(cfg: Config) -> dict[str, Any]:
    """Todo lo que cambia una decisión. Si cambia algo de aquí, es otro experimento."""
    s, sim, u, l = cfg.signals, cfg.sim, cfg.updown, cfg.learn
    return {
        "signals": {
            "maker_first": s.maker_first, "maker_entry_timeout_s": s.maker_entry_timeout_s,
            "min_edge_net": s.min_edge_net, "max_edge_net": s.max_edge_net, "target_size": s.target_size,
            "detect_interval_ms": s.detect_interval_ms,
            "spread": s.spread.model_dump(), "model_deviation": s.model_deviation.model_dump(),
            "smart_money": s.smart_money.model_dump(), "complement": s.complement.model_dump(),
            "multi_outcome": s.multi_outcome.model_dump(),
        },
        "sim": sim.model_dump(),
        "updown": {k: v for k, v in u.model_dump().items() if k not in ("ws_url",)},
        "learn": l.model_dump(),
        "models": cfg.models.model_dump(),
        "discovery": cfg.discovery.model_dump(),
    }


def modelos_en_uso(data_dir: str | Path) -> dict[str, int]:
    """Versión del modelo aprendido que está promovido para cada tipo de señal."""
    try:
        from .learn.registry import ModelStore
        store = ModelStore(data_dir)
        out: dict[str, int] = {}
        for kind in store.kinds():
            b = store.load_current(kind)
            if b is not None:
                out[kind] = b.version
        return out
    except Exception:  # noqa: BLE001
        return {}


@dataclass
class Experimento:
    experiment_id: str
    commit: str
    dirty: bool
    huella: str
    ts_ms: int
    umbrales: dict[str, Any] = field(default_factory=dict)
    modelos: dict[str, int] = field(default_factory=dict)
    nota: str = ""
    simulador: str = ""          # huella del código que simula la ejecución
    reentrenamiento: bool = True  # ¿podía promocionarse un modelo durante la corrida?

    def to_row(self) -> dict[str, Any]:
        return {"ts_ms": self.ts_ms, "experiment_id": self.experiment_id, "commit": self.commit,
                "dirty": self.dirty, "huella": self.huella, "umbrales": dumps(self.umbrales),
                "modelos": dumps(self.modelos), "nota": self.nota,
                "simulador": self.simulador, "reentrenamiento": self.reentrenamiento}

    def resumen(self) -> str:
        sucio = "  (ÁRBOL SUCIO: hay cambios sin comprometer)" if self.dirty else ""
        reentr = "ACTIVO (la muestra puede partirse)" if self.reentrenamiento else "desactivado"
        return (f"experimento {self.experiment_id}\n"
                f"  commit   {self.commit or 'desconocido'}{sucio}\n"
                f"  huella   {self.huella}\n"
                f"  simulador {self.simulador}\n"
                f"  modelos  {self.modelos or 'ninguno promovido'}\n"
                f"  reentren. {reentr}\n"
                f"  nota     {self.nota or '-'}")


def congelar(cfg: Config, nota: str = "", ts_ms: int | None = None) -> Experimento:
    """Calcula la huella del motor tal y como está ahora mismo.

    Entra todo lo que puede cambiar una decisión o una medición: el commit, si el árbol estaba
    sucio, todos los umbrales, la versión de cada modelo promovido, la huella del código de
    simulación y si el reentrenamiento estaba activo. Ese último no cambia nada por sí solo, pero
    determina si el motor **podía** cambiar durante la corrida, que es justo el fallo que dejó
    186 de 680 posiciones de `muestra-3` mezcladas con las de otro motor.
    """
    commit, dirty = commit_actual()
    thr = umbrales(cfg)
    mods = modelos_en_uso(cfg.data_dir)
    sim = version_simulador()
    reentr = bool(cfg.learn.enabled and cfg.learn.retrain_hours > 0)
    crudo = json.dumps({"commit": commit, "umbrales": thr, "modelos": mods,
                        "simulador": sim, "reentrenamiento": reentr}, sort_keys=True, default=str)
    huella = hashlib.sha256(crudo.encode("utf-8")).hexdigest()[:12]
    ts = ts_ms if ts_ms is not None else int(datetime.now(tz=timezone.utc).timestamp() * 1000)
    fecha = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).strftime("%Y%m%d")
    return Experimento(f"exp-{fecha}-{huella[:8]}", commit, dirty, huella, ts, thr, mods, nota,
                       simulador=sim, reentrenamiento=reentr)


class MotorCambiado(RuntimeError):
    """El motor cambió durante una corrida. No es recuperable: la muestra ya está mezclada."""


def assert_engine_frozen(cfg: Config, exp: Experimento) -> None:
    """Comprueba que el motor sigue siendo el que se congeló. Si no, aborta la corrida.

    Se llama periódicamente durante la corrida, no solo al arrancar. Que la huella coincida
    significa que el commit, los umbrales, los modelos promovidos y el código de simulación son los
    mismos que cuando empezó. Si algo se movió, seguir escribiendo filas con el mismo
    `experiment_id` produciría exactamente el dato inservible que esta comprobación existe para
    evitar, así que se corta.
    """
    ahora = congelar(cfg, ts_ms=exp.ts_ms)
    if ahora.huella == exp.huella:
        return
    cambios = cambios_que_deciden(
        {"umbrales": dumps(exp.umbrales), "modelos": dumps(exp.modelos)},
        {"umbrales": dumps(ahora.umbrales), "modelos": dumps(ahora.modelos)}) or []
    if ahora.commit != exp.commit:
        cambios.append(f"commit: {exp.commit} → {ahora.commit}")
    if ahora.simulador != exp.simulador:
        cambios.append(f"código de simulación: {exp.simulador} → {ahora.simulador}")
    raise MotorCambiado(
        f"el motor cambió durante la corrida (huella {exp.huella} → {ahora.huella}): "
        + "; ".join(cambios or ["no se pudo precisar qué"])
        + ". La corrida se aborta: dos motores distintos no pueden compartir experiment_id.")


def registrar(cfg: Config, exp: Experimento, writer: ParquetWriter | None = None) -> None:
    """Guarda el experimento. Si ya estaba registrado con la misma huella, no duplica."""
    ya = scan(cfg.data_dir, "experiments")
    if ya is not None:
        import polars as pl
        if ya.filter(pl.col("huella") == exp.huella).select(pl.len()).collect().item():
            return
    propio = writer is None
    w = writer or ParquetWriter(cfg.data_dir, flush_seconds=10**9, flush_rows=10**9)
    w.append("experiments", exp.to_row())
    if propio:
        w.close()


def diferencias(a: dict[str, Any], b: dict[str, Any], prefijo: str = "") -> list[str]:
    """Qué cambió entre los umbrales de dos experimentos, en lenguaje de rutas."""
    out: list[str] = []
    for k in sorted(set(a) | set(b)):
        va, vb = a.get(k), b.get(k)
        ruta = f"{prefijo}.{k}" if prefijo else k
        if isinstance(va, dict) and isinstance(vb, dict):
            out += diferencias(va, vb, ruta)
        elif va != vb:
            out.append(f"{ruta}: {va} → {vb}")
    return out


def cambios_que_deciden(a: dict[str, Any], b: dict[str, Any]) -> list[str] | None:
    """Diferencias en lo que decide: umbrales y modelos. `None` si no se puede leer.

    Ojo con lo que esto NO dice: que dos experimentos decidan igual no garantiza que midan igual.
    Entre un commit y otro puede haberse arreglado cómo se calcula la selección adversa o cuándo se
    marca el llenado, y entonces los números de los dos no son comparables aunque las señales sí.
    Eso hay que mirarlo en el historial de cambios; la huella no puede saberlo.
    """
    out: list[str] = []
    for campo in ("umbrales", "modelos"):
        try:
            va, vb = json.loads(a.get(campo) or "{}"), json.loads(b.get(campo) or "{}")
        except (json.JSONDecodeError, TypeError):
            return None
        if not isinstance(va, dict) or not isinstance(vb, dict):
            return None
        out += diferencias(va, vb)
    return out


def historial(data_dir: str | Path) -> list[dict[str, Any]]:
    lf = scan(data_dir, "experiments")
    if lf is None:
        return []
    return lf.sort("ts_ms").collect().to_dicts()


def formatear_historial(data_dir: str | Path) -> str:
    filas = historial(data_dir)
    if not filas:
        return "Todavía no hay ningún experimento registrado."
    lineas = ["Experimentos registrados (uno por cada versión del motor que ha operado):", ""]
    previo: dict[str, Any] | None = None
    for r in filas:
        fecha = datetime.fromtimestamp(r["ts_ms"] / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")
        sucio = " [árbol sucio]" if r.get("dirty") else ""
        lineas.append(f"{r['experiment_id']}   {fecha} UTC   commit {r.get('commit') or '?'}{sucio}")
        if r.get("nota"):
            lineas.append(f"   nota: {r['nota']}")
        if previo is not None:
            cambios = cambios_que_deciden(previo, r)
            if cambios is None:
                lineas.append("   no se puede comparar con el anterior: los umbrales no se leen.")
            elif cambios:
                lineas.append("   cambió respecto al anterior:")
                lineas += [f"      {c}" for c in cambios[:20]]
                if len(cambios) > 20:
                    lineas.append(f"      … y {len(cambios) - 20} más")
                lineas.append("   la muestra NO se puede juntar con la del anterior: decide distinto.")
            else:
                # La huella incluye el commit, así que un arreglo del informe o de un test abre un
                # experimento nuevo aunque el motor decida exactamente igual. Cuando es el caso hay
                # que decirlo: si no, la muestra queda partida sin motivo.
                lineas.append("   nada de lo que decide cambió (mismos umbrales y mismos modelos): "
                              "la muestra se puede juntar.")
        previo = r
        lineas.append("")
    return "\n".join(lineas)
