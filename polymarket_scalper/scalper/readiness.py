"""¿Está listo el bot para operar con dinero real?

La pregunta se responde con números, no con ganas. Por cada tipo de señal se piden cuatro cosas:

1. **Muestra suficiente.** Menos de 100 posiciones cerradas no dicen nada: las ganancias de estos
   mercados tienen colas largas y unas pocas operaciones afortunadas engañan a cualquiera.
2. **Ganancia neta positiva**, después de comisiones y sin contar los cierres forzados al terminar
   una corrida, que son ruido del simulador.
3. **Que la ganancia no quepa en la suerte.** Se mide con el estadístico t: la media por operación
   dividida entre su error estándar. Por debajo de 2 no se distingue del azar.
4. **Que el modelo aprendido no empeore a la heurística**, cuando ya hay modelo entrenado.

Además, una condición de sentido común: al menos siete días de datos, para haber visto horarios,
días de semana y fines de semana distintos.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import polars as pl

from .learn.train import EXCLUDED_EXITS
from .storage import scan

MIN_POSICIONES = 100
MIN_T = 2.0
MIN_DIAS = 7.0


@dataclass
class Veredicto:
    kind: str
    n: int = 0
    pnl: float = 0.0
    media: float = 0.0
    desviacion: float = 0.0
    t: float = 0.0
    acierto: float = 0.0
    fees: float = 0.0
    brier_modelo: float | None = None
    brier_heuristica: float | None = None
    listo: bool = False
    motivos: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {k: getattr(self, k) for k in
                ("kind", "n", "pnl", "media", "desviacion", "t", "acierto", "fees",
                 "brier_modelo", "brier_heuristica", "listo", "motivos")}


@dataclass
class Informe:
    dias: float = 0.0
    veredictos: list[Veredicto] = field(default_factory=list)
    listas: list[str] = field(default_factory=list)
    aviso: str = ""

    @property
    def alguna_lista(self) -> bool:
        return bool(self.listas)


def evaluar(data_dir: str | Path) -> Informe:
    inf = Informe()
    lf = scan(data_dir, "ledger")
    if lf is None:
        inf.aviso = "todavía no hay ledger: deja el bot corriendo"
        return inf
    df = lf.collect()
    if not df.height:
        inf.aviso = "el ledger está vacío"
        return inf
    inf.dias = (df["ts_signal"].max() - df["ts_signal"].min()) / 86_400_000

    util = df.filter((pl.col("size_filled") > 0) & ~pl.col("exit_reason").is_in(list(EXCLUDED_EXITS)))
    for kind in sorted(df["kind"].unique().to_list()):
        sub = util.filter(pl.col("kind") == kind)
        v = Veredicto(kind=kind, n=sub.height)
        if sub.height:
            pnl = sub["realized_pnl"].to_list()
            v.pnl = round(sum(pnl), 2)
            v.media = round(v.pnl / len(pnl), 4)
            if len(pnl) > 1:
                var = sum((x - v.media) ** 2 for x in pnl) / (len(pnl) - 1)
                v.desviacion = round(math.sqrt(var), 4)
                if v.desviacion > 0:
                    v.t = round(v.media / (v.desviacion / math.sqrt(len(pnl))), 2)
            v.acierto = round(sum(1 for x in pnl if x > 0) / len(pnl), 3)
            v.fees = round(float(sub["fees"].sum()), 2)
            if "p_win_model" in sub.columns:
                fm = sub.filter(pl.col("p_win_model").is_not_null())
                if fm.height >= 20:
                    y = (pl.col("realized_pnl") > 0).cast(pl.Float64)
                    v.brier_modelo = round(float(fm.select(((pl.col("p_win_model") - y) ** 2).mean()).item()), 4)
                    v.brier_heuristica = round(float(fm.select(((pl.col("conf_heuristic") - y) ** 2).mean()).item()), 4)

        if v.n < MIN_POSICIONES:
            v.motivos.append(f"faltan posiciones: {v.n} de {MIN_POSICIONES}")
        if v.pnl <= 0:
            v.motivos.append(f"la ganancia neta es {v.pnl:+.2f} USD, no positiva")
        if v.t < MIN_T:
            v.motivos.append(f"la ventaja cabe en la suerte (t = {v.t}, hace falta {MIN_T})")
        if v.brier_modelo is not None and v.brier_heuristica is not None and v.brier_modelo > v.brier_heuristica:
            v.motivos.append("el modelo aprendido es peor que la heurística")
        v.listo = not v.motivos
        inf.veredictos.append(v)

    if inf.dias < MIN_DIAS:
        for v in inf.veredictos:
            if v.listo:
                v.listo = False
                v.motivos.append(f"solo hay {inf.dias:.1f} días de datos, hacen falta {MIN_DIAS:.0f}")
    inf.listas = [v.kind for v in inf.veredictos if v.listo]
    return inf


def formatear(inf: Informe, etiquetas: dict[str, str] | None = None) -> str:
    if inf.aviso:
        return f"¿Listo para dinero real? No: {inf.aviso}."
    nombre = (etiquetas or {}).get
    lineas = [f"Días de datos: {inf.dias:.1f} de {MIN_DIAS:.0f} necesarios", "",
              f"{'señal':22}{'posiciones':>11}{'ganancia':>11}{'por op.':>10}{'t':>7}{'acierto':>9}  veredicto",
              "-" * 92]
    for v in inf.veredictos:
        estado = "LISTA" if v.listo else "no"
        lineas.append(f"{(nombre(v.kind) or v.kind)[:22]:22}{v.n:>11}{v.pnl:>11.2f}{v.media:>10.3f}"
                      f"{v.t:>7.2f}{v.acierto * 100:>8.0f}%  {estado}")
        for m in v.motivos:
            lineas.append(f"{'':22}  · {m}")
    lineas.append("")
    if inf.alguna_lista:
        lineas.append("Señales que cumplen los cuatro criterios: " + ", ".join(inf.listas))
        lineas.append("")
        lineas.append("Aun así, el bot no puede operar solo: la capa que firma órdenes no está construida.")
        lineas.append("Es deliberado. El siguiente paso sería construirla y probarla con el tamaño mínimo,")
        lineas.append("solo con las señales de la lista, para comprobar que los llenados reales se parecen")
        lineas.append("a los simulados.")
    else:
        lineas.append("Ninguna señal cumple todavía los cuatro criterios. Lo único que hace falta es")
        lineas.append("dejar el bot corriendo: cada día que pasa acumula posiciones y el veredicto se afina.")
    return "\n".join(lineas)
