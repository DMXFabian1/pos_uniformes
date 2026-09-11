"""Evaluación única de la ejecución y del resultado, por estrategia.

Este módulo es la **única** fuente de métricas: el veredicto de "listo", el panel y los informes
lo consumen, para que no puedan contradecirse.

Responde, con números del ledger y sin suposiciones, a las preguntas que deciden si una
estrategia sirve:

- ¿Qué fracción de las órdenes se llenó de verdad? (observada, y en los escenarios conservador
  y optimista). El 60 % de referencia se muestra al lado, nunca como resultado.
- ¿A partir de qué tasa de llenado compensa poner la orden en vez de cruzar el libro?
  (**break-even**: `edge_taker / edge_maker`; si cruzar da un edge negativo, cualquier llenado gana).
- ¿Cuál es el **edge mínimo requerido** para que una señal tenga sentido? Coste de salida más
  selección adversa medida más un margen. Por debajo de eso, NO TRADE por construcción.
- ¿Cuánto se mueve el precio en contra justo después de llenarnos? (selección adversa a 100 ms…10 s).
- ¿Cuánto del edge aparente llega al bolsillo? (aparente vs realizado).
- ¿La ganancia media cabe en la suerte? (t de Student y intervalo por bootstrap).
"""
from __future__ import annotations

import json
import math
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import polars as pl

from .storage import scan

# Cierres que no dicen nada de la señal: corte de la corrida, o que nunca se llegó a operar.
CIERRES_EXCLUIDOS = {"end", "end_stuck", "unfilled", "expired_unfilled", "spread_gone", "no_book", "price_moved"}
# Cierres que sí cuentan como "la orden se puso y no se llenó": son coste de oportunidad, no pérdida.
CIERRES_SIN_LLENAR = {"sin_llenar"}
HORIZONTES = ["adverse_100ms", "adverse_500ms", "adverse_1s", "adverse_2s", "adverse_5s", "adverse_10s"]
MARGEN_POR_DEFECTO = 0.005      # USD por share de holgura sobre el coste medido


@dataclass
class Ejecucion:
    """Qué pasó con las órdenes: cuántas se llenaron y si compensaba ponerlas."""
    ordenes: int = 0
    llenadas: int = 0
    tasa_llenado: float | None = None
    tasa_conservadora: float | None = None
    tasa_optimista: float | None = None
    tasa_baseline: float = 0.6
    llenado_parcial_medio: float | None = None    # fracción del tamaño pedido que se llenó
    barridas: int = 0                             # fills por barrido del nivel (los más expuestos)
    break_even_llenado: float | None = None
    margen_sobre_break_even: float | None = None
    edge_maker_medio: float | None = None
    edge_taker_medio: float | None = None
    cola_media: float | None = None
    espera_media_s: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


@dataclass
class Estrategia:
    strategy: str
    n: int = 0                        # posiciones llenadas y válidas
    pnl: float = 0.0
    media: float = 0.0
    desviacion: float = 0.0
    t: float = 0.0
    ic95: tuple[float, float] | None = None
    acierto: float = 0.0
    fees: float = 0.0
    duracion_media_s: float | None = None
    edge_bruto: float | None = None        # USD por share antes de cualquier coste
    edge_aparente: float | None = None     # USD por share prometidos por el detector (ejecutable)
    edge_conservador: float | None = None  # USD por share si hubiera que salir al bid de ese momento
    edge_realizado: float | None = None    # USD por share efectivamente obtenidos
    captura: float | None = None           # realizado / aparente
    adversa: dict[str, float | None] = field(default_factory=dict)
    coste_salida: float | None = None
    edge_minimo_requerido: float | None = None
    senales_sobre_minimo: float | None = None
    ejecucion: Ejecucion = field(default_factory=Ejecucion)
    salidas: dict[str, int] = field(default_factory=dict)
    deciles: list[dict[str, Any]] = field(default_factory=list)
    estres: dict[str, float] = field(default_factory=dict)
    descartadas_del_dado: int = 0     # filas viejas, generadas cuando el llenado salía de un dado

    def to_dict(self) -> dict[str, Any]:
        d = dict(self.__dict__)
        d["ejecucion"] = self.ejecucion.to_dict()
        d["ic95"] = list(self.ic95) if self.ic95 else None
        return d


# --------------------------------------------------------------------------- utilidades
def _media(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def bootstrap_ic(xs: list[float], repeticiones: int = 2000, semilla: int = 7,
                 alfa: float = 0.05) -> tuple[float, float] | None:
    """Intervalo de confianza de la media por remuestreo. None con menos de 20 observaciones.

    El t de Student supone normalidad; el PnL de estos mercados tiene colas largas y no la cumple.
    El bootstrap no la supone: solo vuelve a sortear las operaciones que de verdad ocurrieron.
    """
    if len(xs) < 20:
        return None
    rng = random.Random(semilla)
    n = len(xs)
    medias = []
    for _ in range(repeticiones):
        medias.append(sum(xs[rng.randrange(n)] for _ in range(n)) / n)
    medias.sort()
    lo = medias[int(repeticiones * alfa / 2)]
    hi = medias[min(repeticiones - 1, int(repeticiones * (1 - alfa / 2)))]
    return (round(lo, 4), round(hi, 4))


def _meta(row: dict[str, Any]) -> dict[str, Any]:
    try:
        return json.loads(row.get("meta") or "{}")
    except json.JSONDecodeError:
        return {}


def es_del_dado(row: dict[str, Any]) -> bool:
    """¿Esta fila la generó el modelo de llenado por azar que ya no existe?

    Una entrada maker anterior al modelo de cola no trae los escenarios de llenado. Su resultado
    depende de una probabilidad inventada, así que no puede contar como evidencia de nada. Las
    entradas taker no usaban el dado y sí cuentan.
    """
    rol = row.get("entry_role") or _meta(row).get("entry_role")
    return rol == "maker" and row.get("fill_conservador") is None


def _strategy(row: dict[str, Any]) -> str:
    s = row.get("strategy")
    if s:
        return str(s)
    return _meta(row).get("strategy") or str(row.get("kind") or "?")


# --------------------------------------------------------------------------- ejecución
def _ejecucion(filas: list[dict[str, Any]], baseline: float) -> Ejecucion:
    """Órdenes maker: cuántas se llenaron, en qué escenario, y si compensaba ponerlas.

    Solo cuentan las filas con rol de entrada maker: una entrada taker se llena por definición y
    mezclarlas inflaría la tasa.
    """
    e = Ejecucion(tasa_baseline=baseline)
    maker = [r for r in filas if (r.get("entry_role") or _meta(r).get("entry_role")) == "maker"]
    e.ordenes = len(maker)
    if not maker:
        return e
    llenadas = [r for r in maker if (r.get("size_filled") or 0) > 0]
    e.llenadas = len(llenadas)
    e.tasa_llenado = round(len(llenadas) / len(maker), 4)
    cons = [r for r in maker if (r.get("fill_conservador") or 0) > 0]
    opt = [r for r in maker if (r.get("fill_optimista") or 0) > 0]
    if any(r.get("fill_conservador") is not None for r in maker):
        e.tasa_conservadora = round(len(cons) / len(maker), 4)
        e.tasa_optimista = round(len(opt) / len(maker), 4)
    parciales = [min((r.get("size_filled") or 0) / r["size_target"], 1.0) for r in maker if r.get("size_target")]
    e.llenado_parcial_medio = round(_media(parciales), 4) if parciales else None
    e.barridas = sum(1 for r in llenadas if r.get("barrido"))
    colas = [r["queue_inicial"] for r in maker if r.get("queue_inicial") is not None]
    e.cola_media = round(_media(colas), 2) if colas else None
    esperas = [(r["ts_fill"] - r["ts_placed"]) / 1000 for r in llenadas
               if r.get("ts_placed") and r.get("ts_fill") and r["ts_fill"] >= r["ts_placed"]]
    e.espera_media_s = round(_media(esperas), 2) if esperas else None

    # break-even: poner la orden gana si  p_llenado × edge_maker  >  edge_taker
    em = [r["predicted_edge"] for r in maker if r.get("predicted_edge") is not None]
    et = [r["edge_taker"] if r.get("edge_taker") is not None else _meta(r).get("edge_taker") for r in maker]
    et = [x for x in et if x is not None]
    e.edge_maker_medio = round(_media(em), 5) if em else None
    e.edge_taker_medio = round(_media(et), 5) if et else None
    if e.edge_maker_medio and e.edge_maker_medio > 0 and e.edge_taker_medio is not None:
        if e.edge_taker_medio <= 0:
            e.break_even_llenado = 0.0          # cruzar el libro pierde: cualquier llenado es mejor
        else:
            e.break_even_llenado = round(min(e.edge_taker_medio / e.edge_maker_medio, 1.0), 4)
        if e.tasa_llenado is not None:
            e.margen_sobre_break_even = round(e.tasa_llenado - e.break_even_llenado, 4)
    return e


def _adversa(filas: list[dict[str, Any]]) -> dict[str, float | None]:
    """Movimiento medio del mid tras el fill, por horizonte. Negativo = el precio se fue en contra."""
    out: dict[str, float | None] = {}
    for h in HORIZONTES:
        xs = [r[h] for r in filas if r.get(h) is not None]
        out[h] = round(_media(xs), 5) if xs else None
    return out


def _deciles(filas: list[dict[str, Any]], n: int = 5) -> list[dict[str, Any]]:
    """PnL por tramo de edge prometido: si el edge no ordena el resultado, el detector no mide nada."""
    datos = [r for r in filas if r.get("predicted_edge") is not None]
    if len(datos) < n * 4:
        return []
    datos.sort(key=lambda r: r["predicted_edge"])
    tam = len(datos) // n
    out = []
    for i in range(n):
        tramo = datos[i * tam:(i + 1) * tam] if i < n - 1 else datos[i * tam:]
        pnl = [r["realized_pnl"] for r in tramo]
        out.append({"tramo": i + 1, "n": len(tramo),
                    "edge_min": round(tramo[0]["predicted_edge"], 5),
                    "edge_max": round(tramo[-1]["predicted_edge"], 5),
                    "pnl_medio": round(_media(pnl), 4),
                    "acierto": round(sum(1 for x in pnl if x > 0) / len(pnl), 3)})
    return out


def _estres(filas: list[dict[str, Any]], pnl_base: float) -> dict[str, float]:
    """Tres escenarios adversos sobre las mismas operaciones.

    - `fill_conservador`: solo cuentan las que se habrían llenado con la cola entera delante, y
      su ganancia se escala por la fracción llenada. Es una aproximación: el PnL de una posición
      direccional es casi proporcional al tamaño.
    - `fees_x1.5`: la comisión sube un 50 % (cambio de tarifa o peor precio de salida).
    - `latencia`: se descartan las operaciones que se llenaron en menos de un segundo, que son
      las que más dependen de llegar antes que los demás.
    """
    out = {"base": round(pnl_base, 4)}
    cons = 0.0
    for r in filas:
        llen = r.get("size_filled") or 0
        c = r.get("fill_conservador")
        if c is None:
            cons += r["realized_pnl"]
        elif llen > 0 and c > 0:
            cons += r["realized_pnl"] * min(c / llen, 1.0)
    out["fill_conservador"] = round(cons, 4)
    out["fees_x1.5"] = round(pnl_base - 0.5 * sum(r.get("fees") or 0 for r in filas), 4)
    lentas = [r for r in filas if not (r.get("ts_placed") and r.get("ts_fill")
                                       and 0 <= r["ts_fill"] - r["ts_placed"] < 1000)]
    out["sin_fills_rapidos"] = round(sum(r["realized_pnl"] for r in lentas), 4)
    return out


# --------------------------------------------------------------------------- por estrategia
def evaluar_filas(filas: list[dict[str, Any]], baseline: float = 0.6,
                  margen: float = MARGEN_POR_DEFECTO) -> Estrategia:
    """Todas las métricas de un grupo de filas del ledger que comparten estrategia."""
    nombre = _strategy(filas[0]) if filas else "?"
    e = Estrategia(strategy=nombre)
    # lo primero: fuera las filas que produjo el modelo de llenado por azar
    viejas = [r for r in filas if es_del_dado(r)]
    e.descartadas_del_dado = len(viejas)
    filas = [r for r in filas if not es_del_dado(r)]
    if not filas:
        return e
    validas = [r for r in filas if (r.get("size_filled") or 0) > 0
               and r.get("exit_reason") not in CIERRES_EXCLUIDOS]
    e.ejecucion = _ejecucion(filas, baseline)
    e.salidas = {}
    for r in filas:
        k = str(r.get("exit_reason") or "")
        e.salidas[k] = e.salidas.get(k, 0) + 1
    if not validas:
        return e
    pnl = [r["realized_pnl"] for r in validas]
    e.n = len(pnl)
    e.pnl = round(sum(pnl), 2)
    e.media = round(e.pnl / e.n, 4)
    if e.n > 1:
        var = sum((x - e.media) ** 2 for x in pnl) / (e.n - 1)
        e.desviacion = round(math.sqrt(var), 4)
        if e.desviacion > 0:
            e.t = round(e.media / (e.desviacion / math.sqrt(e.n)), 2)
    e.ic95 = bootstrap_ic(pnl)
    e.acierto = round(sum(1 for x in pnl if x > 0) / e.n, 3)
    e.fees = round(sum(r.get("fees") or 0 for r in validas), 2)
    dur = [r["hold_s"] for r in validas if r.get("hold_s") is not None]
    e.duracion_media_s = round(_media(dur), 1) if dur else None

    # edge aparente vs realizado, ambos en USD por share
    aparentes = [r["predicted_edge"] for r in validas if r.get("predicted_edge") is not None]
    reales = [r["realized_pnl"] / r["size_filled"] for r in validas if r.get("size_filled")]
    brutos = [_meta(r).get("edge_raw") for r in validas]
    brutos = [x for x in brutos if x is not None]
    conserv = [_meta(r).get("edge_conservador") for r in validas]
    conserv = [x for x in conserv if x is not None]
    e.edge_bruto = round(_media(brutos), 5) if brutos else None
    e.edge_conservador = round(_media(conserv), 5) if conserv else None
    e.edge_aparente = round(_media(aparentes), 5) if aparentes else None
    e.edge_realizado = round(_media(reales), 5) if reales else None
    if e.edge_aparente and abs(e.edge_aparente) > 1e-9 and e.edge_realizado is not None:
        e.captura = round(e.edge_realizado / e.edge_aparente, 3)

    e.adversa = _adversa(validas)
    costes = [(r.get("fees") or 0) / r["size_filled"] for r in validas if r.get("size_filled")]
    e.coste_salida = round(_media(costes), 5) if costes else 0.0
    adv = e.adversa.get("adverse_10s") or e.adversa.get("adverse_5s") or 0.0
    e.edge_minimo_requerido = round((e.coste_salida or 0.0) + max(-adv, 0.0) + margen, 5)
    if aparentes:
        e.senales_sobre_minimo = round(sum(1 for x in aparentes if x >= e.edge_minimo_requerido) / len(aparentes), 3)
    e.deciles = _deciles(validas)
    e.estres = _estres(validas, e.pnl)
    return e


def evaluar(data_dir: str | Path, run_id: str | None = None, baseline: float = 0.6,
            margen: float = MARGEN_POR_DEFECTO) -> list[Estrategia]:
    lf = scan(data_dir, "ledger")
    if lf is None:
        return []
    if run_id:
        lf = lf.filter(pl.col("run_id") == run_id)
    df = lf.collect()
    if not df.height:
        return []
    grupos: dict[str, list[dict[str, Any]]] = {}
    for r in df.to_dicts():
        grupos.setdefault(_strategy(r), []).append(r)
    return sorted((evaluar_filas(v, baseline, margen) for v in grupos.values()), key=lambda e: e.strategy)


def minimos_requeridos(data_dir: str | Path, min_n: int = 20) -> dict[str, float]:
    """Edge mínimo medido de cada estrategia, para que el motor pueda usarlo como filtro.

    Solo se devuelven estrategias con al menos `min_n` posiciones cerradas: con menos, el mínimo
    sería una opinión disfrazada de medición y filtraría señales por ruido.
    """
    try:
        return {e.strategy: e.edge_minimo_requerido for e in evaluar(data_dir)
                if e.edge_minimo_requerido is not None and e.n >= min_n}
    except Exception:  # noqa: BLE001 - un informe roto nunca debe impedir operar
        return {}


# --------------------------------------------------------------------------- presentación
def formatear(ests: list[Estrategia]) -> str:
    if not ests:
        return "Todavía no hay ledger. Deja el bot corriendo."
    out: list[str] = []
    out.append(f"{'estrategia':24}{'n':>5}{'ganancia':>10}{'por op.':>9}{'t':>6}{'IC 95 %':>20}{'acierto':>9}")
    out.append("-" * 83)
    for e in ests:
        ic = f"[{e.ic95[0]:+.3f}, {e.ic95[1]:+.3f}]" if e.ic95 else "pocos datos"
        out.append(f"{e.strategy[:24]:24}{e.n:>5}{e.pnl:>10.2f}{e.media:>9.3f}{e.t:>6.2f}{ic:>20}"
                   f"{e.acierto * 100:>8.0f}%")
    out.append("")
    out.append("== Ejecución: ¿se llenan las órdenes que ponemos? ==")
    out.append(f"{'estrategia':24}{'órdenes':>9}{'llenadas':>10}{'conserv.':>10}{'optim.':>9}"
               f"{'break-even':>12}{'margen':>9}{'referencia':>12}")
    out.append("-" * 95)
    for e in ests:
        x = e.ejecucion
        if not x.ordenes:
            continue
        f = lambda v: "  -  " if v is None else f"{v * 100:.0f}%"   # noqa: E731
        out.append(f"{e.strategy[:24]:24}{x.ordenes:>9}{f(x.tasa_llenado):>10}{f(x.tasa_conservadora):>10}"
                   f"{f(x.tasa_optimista):>9}{f(x.break_even_llenado):>12}{f(x.margen_sobre_break_even):>9}"
                   f"{f(x.tasa_baseline):>12}")
    out.append("")
    out.append("La columna 'referencia' es el 60 % que se suponía antes de medir. No es un resultado:")
    out.append("es el número que había que comprobar. Lo que decide es 'llenadas' contra 'break-even'.")
    descartadas = sum(e.descartadas_del_dado for e in ests)
    if descartadas:
        out.append("")
        out.append(f"Se dejaron fuera {descartadas} posiciones anteriores a esta medición: su llenado salía")
        out.append("de una probabilidad inventada, así que no dicen nada sobre si la estrategia funciona.")
    out.append("")
    out.append("== ¿Cuánta ventaja hace falta y cuánta llega al bolsillo? ==")
    out.append(f"{'estrategia':24}{'edge mín.':>11}{'% señales':>11}{'bruto':>9}{'ejecutable':>12}"
               f"{'conservador':>13}{'realizado':>11}{'captura':>9}{'adversa 10 s':>14}")
    out.append("-" * 114)
    for e in ests:
        if not e.n:
            continue
        g = lambda v, d=4: "   -   " if v is None else f"{v:+.{d}f}"   # noqa: E731
        pct = "  -  " if e.senales_sobre_minimo is None else f"{e.senales_sobre_minimo * 100:.0f}%"
        cap = "  -  " if e.captura is None else f"{e.captura * 100:.0f}%"
        out.append(f"{e.strategy[:24]:24}{e.edge_minimo_requerido or 0:>11.4f}{pct:>11}{g(e.edge_bruto):>9}"
                   f"{g(e.edge_aparente):>12}{g(e.edge_conservador):>13}{g(e.edge_realizado):>11}{cap:>9}"
                   f"{g(e.adversa.get('adverse_10s'), 5):>14}")
    out.append("")
    for e in ests:
        if not e.deciles:
            continue
        out.append(f"== {e.strategy}: ganancia por tramo de ventaja prometida ==")
        for d in e.deciles:
            out.append(f"   tramo {d['tramo']}  n={d['n']:<4} edge {d['edge_min']:+.4f}…{d['edge_max']:+.4f}  "
                       f"pnl medio {d['pnl_medio']:+.4f}  acierto {d['acierto'] * 100:.0f}%")
        out.append("")
    out.append("== Resistencia: las mismas operaciones en escenarios peores ==")
    for e in ests:
        if not e.estres:
            continue
        partes = "  ".join(f"{k}={v:+.2f}" for k, v in e.estres.items())
        out.append(f"{e.strategy[:24]:24}{partes}")
    return "\n".join(out)
