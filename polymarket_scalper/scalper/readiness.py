"""¿Está listo el bot para operar con dinero real?

La pregunta se responde con números, no con ganas. Las métricas salen todas de `evaluacion.py`,
que es la única fuente: así el panel, el informe y este veredicto no pueden contradecirse.

Por cada estrategia se piden siete cosas:

1. **Muestra suficiente.** Menos de 100 posiciones cerradas no dicen nada: las ganancias de estos
   mercados tienen colas largas y unas pocas operaciones afortunadas engañan a cualquiera.
2. **Ganancia neta positiva**, después de comisiones y sin contar los cierres forzados al terminar
   una corrida, que son ruido del simulador.
3. **Que la ganancia no quepa en la suerte.** Se mide con el estadístico t: la media por operación
   dividida entre su error estándar. Por debajo de 2 no se distingue del azar.
4. **Que el intervalo de confianza no toque el cero.** El t supone una campana; el PnL de estos
   mercados no lo es. El bootstrap remuestrea las operaciones que de verdad ocurrieron, y si el
   extremo inferior del 95 % es negativo, la ganancia no está demostrada.
5. **Que se llenen las órdenes.** Para una estrategia que entra poniendo órdenes, la tasa de
   llenado observada tiene que superar el break-even frente a cruzar el libro. Si no, poner la
   orden es peor que pagar la comisión.
6. **Que el modelo aprendido no empeore a la heurística**, cuando ya hay modelo entrenado.
7. **Que aguante escenarios peores.** Con el llenado conservador y con la comisión un 50 % más
   alta, la ganancia debe seguir siendo positiva.

Además, una condición de sentido común: al menos siete días de datos, para haber visto horarios,
días de semana y fines de semana distintos.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import polars as pl

from .evaluacion import CIERRES_EXCLUIDOS, Estrategia, evaluar as evaluar_metricas
from .storage import scan

MIN_POSICIONES = 100
MIN_T = 2.0
MIN_DIAS = 7.0


@dataclass
class Veredicto:
    kind: str                      # identificador de la estrategia
    n: int = 0
    pnl: float = 0.0
    media: float = 0.0
    desviacion: float = 0.0
    t: float = 0.0
    ic95: tuple[float, float] | None = None
    acierto: float = 0.0
    fees: float = 0.0
    tasa_llenado: float | None = None
    break_even_llenado: float | None = None
    estres: dict[str, float] = field(default_factory=dict)
    brier_modelo: float | None = None
    brier_heuristica: float | None = None
    listo: bool = False
    motivos: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = {k: getattr(self, k) for k in
             ("kind", "n", "pnl", "media", "desviacion", "t", "acierto", "fees", "tasa_llenado",
              "break_even_llenado", "estres", "brier_modelo", "brier_heuristica", "listo", "motivos")}
        d["ic95"] = list(self.ic95) if self.ic95 else None
        return d


@dataclass
class Informe:
    dias: float = 0.0
    veredictos: list[Veredicto] = field(default_factory=list)
    listas: list[str] = field(default_factory=list)
    aviso: str = ""

    @property
    def alguna_lista(self) -> bool:
        return bool(self.listas)


def _brier(df: pl.DataFrame) -> tuple[float | None, float | None]:
    """Brier del modelo aprendido y de la heurística sobre las mismas filas. Menor es mejor."""
    if "p_win_model" not in df.columns:
        return None, None
    fm = df.filter(pl.col("p_win_model").is_not_null())
    if fm.height < 20:
        return None, None
    y = (pl.col("realized_pnl") > 0).cast(pl.Float64)
    modelo = round(float(fm.select(((pl.col("p_win_model") - y) ** 2).mean()).item()), 4)
    heur = round(float(fm.select(((pl.col("conf_heuristic") - y) ** 2).mean()).item()), 4)
    return modelo, heur


def _veredicto(e: Estrategia, df_estrategia: pl.DataFrame | None) -> Veredicto:
    x = e.ejecucion
    v = Veredicto(kind=e.strategy, n=e.n, pnl=e.pnl, media=e.media, desviacion=e.desviacion, t=e.t,
                  ic95=e.ic95, acierto=e.acierto, fees=e.fees, tasa_llenado=x.tasa_llenado,
                  break_even_llenado=x.break_even_llenado, estres=dict(e.estres))
    if df_estrategia is not None and df_estrategia.height:
        v.brier_modelo, v.brier_heuristica = _brier(df_estrategia)

    if v.n < MIN_POSICIONES:
        v.motivos.append(f"faltan posiciones: {v.n} de {MIN_POSICIONES}")
    if v.pnl <= 0:
        v.motivos.append(f"la ganancia neta es {v.pnl:+.2f} USD, no positiva")
    if v.t < MIN_T:
        v.motivos.append(f"la ventaja cabe en la suerte (t = {v.t}, hace falta {MIN_T})")
    if v.ic95 is not None and v.ic95[0] <= 0:
        v.motivos.append(f"el intervalo de confianza toca el cero ([{v.ic95[0]:+.3f}, {v.ic95[1]:+.3f}] por operación)")
    if x.ordenes and v.tasa_llenado is not None and v.break_even_llenado is not None \
            and v.tasa_llenado <= v.break_even_llenado:
        v.motivos.append(f"se llena el {v.tasa_llenado * 100:.0f} % de las órdenes y haría falta más del "
                         f"{v.break_even_llenado * 100:.0f} % para que poner la orden gane a cruzar el libro")
    if v.brier_modelo is not None and v.brier_heuristica is not None and v.brier_modelo > v.brier_heuristica:
        v.motivos.append("el modelo aprendido es peor que la heurística")
    for escenario in ("fill_conservador", "fees_x1.5"):
        valor = v.estres.get(escenario)
        if valor is not None and valor <= 0:
            v.motivos.append(f"con {escenario.replace('_', ' ')} la ganancia sería {valor:+.2f} USD")
    v.listo = not v.motivos
    return v


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

    util = df.filter((pl.col("size_filled") > 0) & ~pl.col("exit_reason").is_in(list(CIERRES_EXCLUIDOS)))
    for e in evaluar_metricas(data_dir):
        sub = None
        if "strategy" in util.columns and util.filter(pl.col("strategy") == e.strategy).height:
            sub = util.filter(pl.col("strategy") == e.strategy)
        elif "kind" in util.columns:
            sub = util.filter(pl.col("kind") == e.strategy)
        inf.veredictos.append(_veredicto(e, sub))

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
              f"{'estrategia':22}{'posiciones':>11}{'ganancia':>11}{'por op.':>10}{'t':>7}{'acierto':>9}"
              f"{'llenado':>9}  veredicto",
              "-" * 101]
    for v in inf.veredictos:
        estado = "LISTA" if v.listo else "no"
        llen = "   -  " if v.tasa_llenado is None else f"{v.tasa_llenado * 100:.0f}%"
        lineas.append(f"{(nombre(v.kind) or v.kind)[:22]:22}{v.n:>11}{v.pnl:>11.2f}{v.media:>10.3f}"
                      f"{v.t:>7.2f}{v.acierto * 100:>8.0f}%{llen:>9}  {estado}")
        for m in v.motivos:
            lineas.append(f"{'':22}  · {m}")
    lineas.append("")
    if inf.alguna_lista:
        lineas.append("Estrategias que cumplen todos los criterios: " + ", ".join(inf.listas))
        lineas.append("")
        lineas.append("Aun así, el bot no puede operar solo: la capa que firma órdenes no está construida.")
        lineas.append("Es deliberado. El siguiente paso sería construirla y probarla con el tamaño mínimo,")
        lineas.append("solo con las estrategias de la lista, para comprobar que los llenados reales se")
        lineas.append("parecen a los simulados.")
    else:
        lineas.append("Ninguna estrategia cumple todavía los criterios. Lo único que hace falta es")
        lineas.append("dejar el bot corriendo: cada día que pasa acumula posiciones y el veredicto se afina.")
    return "\n".join(lineas)
