"""El informe de la pata suelta: ¿cuánto cuesta salir, y cuándo aparece ese coste?

Una sola pregunta, con número al lado y sin adornos:

    Cuando la captura de spread llena un solo lado, ¿cuánto cuesta cerrarlo enseguida, y cómo
    cambia ese coste con el tiempo?

Todo lo que sale de aquí es **contrafactual**: qué habría pasado si hubiéramos cerrado en tal
instante. No es una operación que ocurriera, no toca el efectivo y no se suma a ningún resultado
realizado. Los nombres lo dicen en todas partes para que no se pueda confundir al leerlo deprisa.

Lo que este informe **no** hace: proponer un stop, elegir un horizonte, cambiar un umbral ni
declarar la estrategia buena o mala. Mide el problema. Decidir viene después, y con esto delante.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import polars as pl

from .pata import CADUCADA, CERRADA, FRACCIONES, HORIZONTES_MS, RECUPERADA
from .storage import scan
from .validacion import nivel

# Cortes para la segmentación descriptiva. No son umbrales de decisión.
TRAMOS_VENTAJA = (("0-1 %", 0.0, 0.01), ("1-2 %", 0.01, 0.02), ("2-3 %", 0.02, 0.03),
                  ("3-5 %", 0.03, 0.05), ("5 %+", 0.05, float("inf")))
TRAMOS_SPREAD = (("1 tick", 0.0, 0.015), ("2 ticks", 0.015, 0.025),
                 ("3 ticks", 0.025, 0.035), ("4+ ticks", 0.035, float("inf")))


def _mediana(xs: list[float]) -> float | None:
    ys = sorted(x for x in xs if x is not None)
    if not ys:
        return None
    n = len(ys)
    return ys[n // 2] if n % 2 else (ys[n // 2 - 1] + ys[n // 2]) / 2


def _pct(xs: list[float], q: float) -> float | None:
    ys = sorted(x for x in xs if x is not None)
    if not ys:
        return None
    return ys[min(len(ys) - 1, int(q * len(ys)))]


def _media(xs: list[float]) -> float | None:
    ys = [x for x in xs if x is not None]
    return sum(ys) / len(ys) if ys else None


@dataclass
class Datos:
    patas: list[dict[str, Any]] = field(default_factory=list)
    track: list[dict[str, Any]] = field(default_factory=list)

    def por_pata(self) -> dict[str, list[dict[str, Any]]]:
        out: dict[str, list[dict[str, Any]]] = {}
        for r in self.track:
            out.setdefault(r["partial_leg_id"], []).append(r)
        for v in out.values():
            v.sort(key=lambda r: r["horizonte_ms"])
        return out


def cargar(data_dir: str | Path, experiment: str | None = None) -> Datos:
    d = Datos()
    for tabla, destino in (("partial_legs", "patas"), ("partial_leg_track", "track")):
        lf = scan(data_dir, tabla)
        if lf is None:
            continue
        if experiment and "experiment" in lf.collect_schema().names():
            lf = lf.filter(pl.col("experiment") == experiment)
        setattr(d, destino, lf.collect().to_dicts())
    return d


def resumen(d: Datos) -> dict[str, Any]:
    """Cuántas patas hubo y cómo terminaron."""
    n = len(d.patas)
    por = {}
    for r in d.patas:
        por[r.get("desenlace") or "?"] = por.get(r.get("desenlace") or "?", 0) + 1
    recuperadas = por.get(RECUPERADA, 0)
    tiempos = [r["time_to_second_leg_ms"] / 1000 for r in d.patas
               if r.get("time_to_second_leg_ms") is not None]
    duraciones = [r["duracion_ms"] / 1000 for r in d.patas if r.get("duracion_ms")]
    reales = [r["pnl_realizado_final"] for r in d.patas if r.get("pnl_realizado_final") is not None]
    sin_realizado = sum(1 for r in d.patas if r.get("pnl_realizado_final") is None)
    return {
        "patas": n, "desenlaces": por,
        "tasa_recuperacion": round(recuperadas / n, 4) if n else None,
        "mediana_segunda_pata_s": _mediana(tiempos),
        "mediana_duracion_s": _mediana(duraciones),
        "pnl_realizado_total": round(sum(reales), 2) if reales else None,
        "pnl_realizado_medio": round(_media(reales), 3) if reales else None,
        "n_con_realizado": len(reales), "n_sin_realizado": sin_realizado,
        "nivel": nivel(n),
    }


def coste_por_horizonte(d: Datos) -> list[dict[str, Any]]:
    """La tabla central: qué habría costado cerrar en cada instante.

    Solo entran las patas que **no** se recuperaron. Meter las recuperadas mezclaría dos poblaciones
    distintas: en una la segunda pata llegó y el resultado es el spread cobrado; en la otra nunca
    llegó. La pregunta es sobre la segunda.
    """
    sueltas = {r["partial_leg_id"] for r in d.patas if r.get("desenlace") in (CERRADA, CADUCADA)}
    por_h: dict[int, list[float]] = {}
    incompletos: dict[int, int] = {}
    for r in d.track:
        if r["partial_leg_id"] not in sueltas:
            continue
        h = r["horizonte_ms"]
        if r.get("contrafactual_pnl") is None:
            incompletos[h] = incompletos.get(h, 0) + 1
            continue
        por_h.setdefault(h, []).append(r["contrafactual_pnl"])
    out = []
    for h in HORIZONTES_MS:
        xs = por_h.get(h, [])
        out.append({
            "horizonte_ms": h, "n": len(xs),
            "mediana": round(_mediana(xs), 3) if xs else None,
            "media": round(_media(xs), 3) if xs else None,
            "p25": round(_pct(xs, 0.25), 3) if xs else None,
            "p75": round(_pct(xs, 0.75), 3) if xs else None,
            "peor": round(min(xs), 3) if xs else None,
            "sin_dato": incompletos.get(h, 0),
            "nivel": nivel(len(xs)),
        })
    return out


def punto_de_no_retorno(d: Datos) -> dict[str, Any]:
    """Cuándo aparece la pérdida: ¿de golpe, en el primer minuto, o poco a poco?

    Para cada pata que acabó perdiendo se busca el primer horizonte en el que el coste de salir ya
    alcanzaba el 25, 50, 75 y 90 % de la pérdida final. La mediana de esos instantes dice si el
    problema se decide al principio o se cuece despacio.
    """
    finales = {r["partial_leg_id"]: r.get("pnl_realizado_final") for r in d.patas
               if r.get("desenlace") in (CERRADA, CADUCADA)}
    por_pata = d.por_pata()
    momentos: dict[float, list[int]] = {f: [] for f in FRACCIONES}
    perdedoras = 0
    ya_en_t1 = 0
    for pid, final in finales.items():
        if final is None or final >= 0:
            continue
        perdedoras += 1
        puntos = [p for p in por_pata.get(pid, []) if p.get("contrafactual_pnl") is not None]
        if not puntos:
            continue
        primero = puntos[0]
        if primero["contrafactual_pnl"] <= final * 0.9:
            ya_en_t1 += 1
        for f in FRACCIONES:
            objetivo = final * f
            for p in puntos:
                if p["contrafactual_pnl"] <= objetivo:
                    momentos[f].append(p["horizonte_ms"])
                    break
    return {
        "perdedoras": perdedoras,
        "ya_perdida_en_el_primer_punto": ya_en_t1,
        "fracciones": {f"{int(f * 100)} %": {
            "n": len(momentos[f]),
            "mediana_ms": _mediana([float(x) for x in momentos[f]]),
        } for f in FRACCIONES},
        "nivel": nivel(perdedoras),
    }


def ahorro_hipotetico(d: Datos) -> list[dict[str, Any]]:
    """Cuánto se habría ahorrado cerrando en cada horizonte, frente a lo que pasó de verdad.

    Es una resta entre un número hipotético y uno real. Sirve como orden de magnitud y nada más: la
    salida de verdad habría movido el libro, y sobre todo habría cambiado lo que pasó después.
    """
    finales = {r["partial_leg_id"]: r.get("pnl_realizado_final") for r in d.patas
               if r.get("desenlace") in (CERRADA, CADUCADA)}
    por_pata = d.por_pata()
    out = []
    for h in HORIZONTES_MS:
        difs = []
        for pid, final in finales.items():
            if final is None:
                continue
            p = next((x for x in por_pata.get(pid, []) if x["horizonte_ms"] == h), None)
            if p is None or p.get("contrafactual_pnl") is None:
                continue
            difs.append(p["contrafactual_pnl"] - final)
        out.append({
            "horizonte_ms": h, "n": len(difs),
            "ahorro_medio": round(_media(difs), 3) if difs else None,
            "ahorro_mediano": round(_mediana(difs), 3) if difs else None,
            "mejor_en_pct": round(sum(1 for x in difs if x > 0) / len(difs), 3) if difs else None,
            "nivel": nivel(len(difs)),
        })
    return out


def _tramo(v: float | None, tramos) -> str | None:
    if v is None:
        return None
    for nombre, lo, hi in tramos:
        if lo <= v < hi:
            return nombre
    return tramos[-1][0]


def segmentacion(d: Datos) -> dict[str, list[dict[str, Any]]]:
    """Descriptiva y nada más: cómo se reparten recuperación y coste según las condiciones.

    Explícitamente **no** se toca ningún umbral con esto. Está aquí para saber si el problema es
    uniforme o se concentra en algún sitio, que es distinto de usarlo para filtrar.
    """
    por_pata = d.por_pata()

    def bloque(clave) -> list[dict[str, Any]]:
        cajones: dict[str, dict[str, Any]] = {}
        for r in d.patas:
            k = clave(r)
            if k is None:
                continue
            c = cajones.setdefault(k, {"tramo": k, "n": 0, "recuperadas": 0,
                                       "coste_60s": [], "final": []})
            c["n"] += 1
            if r.get("desenlace") == RECUPERADA:
                c["recuperadas"] += 1
            if r.get("pnl_realizado_final") is not None:
                c["final"].append(r["pnl_realizado_final"])
            p = next((x for x in por_pata.get(r["partial_leg_id"], [])
                      if x["horizonte_ms"] == 60_000), None)
            if p and p.get("contrafactual_pnl") is not None:
                c["coste_60s"].append(p["contrafactual_pnl"])
        out = []
        for c in cajones.values():
            out.append({"tramo": c["tramo"], "n": c["n"],
                        "recuperacion": round(c["recuperadas"] / c["n"], 3) if c["n"] else None,
                        "coste_60s_mediano": round(_mediana(c["coste_60s"]), 3) if c["coste_60s"] else None,
                        "final_mediano": round(_mediana(c["final"]), 3) if c["final"] else None,
                        "nivel": nivel(c["n"])})
        return sorted(out, key=lambda r: r["tramo"])

    return {
        "ventaja_prometida": bloque(lambda r: _tramo(r.get("ventaja_prometida"), TRAMOS_VENTAJA)),
        "spread_en_t0": bloque(lambda r: _tramo(r.get("t0_spread"), TRAMOS_SPREAD)),
        "lado": bloque(lambda r: r.get("lado")),
        "mercado": bloque(lambda r: (r.get("condition_id") or "")[:10] or None),
    }


@dataclass
class InformePatas:
    experimento: str | None
    datos: Datos
    resumen: dict[str, Any]
    coste: list[dict[str, Any]]
    no_retorno: dict[str, Any]
    ahorro: list[dict[str, Any]]
    segmentos: dict[str, list[dict[str, Any]]]

    def to_dict(self) -> dict[str, Any]:
        return {"experimento": self.experimento, "resumen": self.resumen, "coste": self.coste,
                "punto_de_no_retorno": self.no_retorno, "ahorro_hipotetico": self.ahorro,
                "segmentacion": self.segmentos}


def analizar(data_dir: str | Path, experiment: str | None = None) -> InformePatas:
    d = cargar(data_dir, experiment)
    return InformePatas(experiment, d, resumen(d), coste_por_horizonte(d),
                        punto_de_no_retorno(d), ahorro_hipotetico(d), segmentacion(d))


def _ms(x: float | None) -> str:
    if x is None:
        return "-"
    return f"{x / 1000:.0f} s" if x >= 1000 else f"{x:.0f} ms"


def _n(x: float | None, ancho: int = 9, dec: int = 2) -> str:
    return ("-" if x is None else f"{x:+.{dec}f}").rjust(ancho)


def formatear(inf: InformePatas) -> str:  # noqa: C901 - es un informe, se lee de arriba abajo
    L: list[str] = []
    L.append("=" * 100)
    L.append("  PATA SUELTA: ¿CUÁNTO CUESTA SALIR, Y CUÁNDO APARECE ESE COSTE?")
    L.append("=" * 100)
    if inf.experimento:
        L.append(f"Experimento: {inf.experimento}")
    L.append("")
    L.append("Todo lo que sigue es CONTRAFACTUAL: qué habría costado cerrar en ese instante.")
    L.append("No ocurrió, no toca el efectivo y no se suma a ningún resultado realizado.")
    L.append("")

    r = inf.resumen
    L.append("-- RESUMEN ------------------------------------------------------------------------")
    if not r["patas"]:
        L.append("Todavía no hay ninguna pata suelta registrada.")
        return "\n".join(L)
    L.append(f"Patas sueltas: {r['patas']}   ({r['nivel']})")
    L.append("Desenlaces: " + "  ".join(f"{k} {v}" for k, v in sorted(r["desenlaces"].items())))
    L.append(f"Se recupera la segunda pata: {r['tasa_recuperacion'] * 100:.0f} %"
             if r["tasa_recuperacion"] is not None else "Se recupera la segunda pata: -")
    L.append(f"Mediana hasta la segunda pata: {_ms(r['mediana_segunda_pata_s'] * 1000) if r['mediana_segunda_pata_s'] else '-'}"
             f"   ·   mediana de duración: {_ms(r['mediana_duracion_s'] * 1000) if r['mediana_duracion_s'] else '-'}")
    if r["pnl_realizado_medio"] is not None:
        L.append(f"Resultado REALIZADO de {r['n_con_realizado']} de las {r['patas']} patas: "
                 f"{r['pnl_realizado_total']:+.2f} USD ({r['pnl_realizado_medio']:+.3f} por pata)")
        if r["n_sin_realizado"]:
            L.append(f"  ({r['n_sin_realizado']} sin resultado registrado: no entran en esa media)")
    L.append("")

    L.append("-- COSTE DE SALIR, POR HORIZONTE --------------------------------------------------")
    L.append("Solo patas que NO se recuperaron: son la población sobre la que se pregunta.")
    L.append(f"{'horizonte':>10}{'n':>6}{'mediana':>10}{'media':>10}{'p25':>10}{'p75':>10}"
             f"{'peor':>10}{'sin dato':>10}  confianza")
    L.append("-" * 100)
    for x in inf.coste:
        L.append(f"{_ms(x['horizonte_ms']):>10}{x['n']:>6}{_n(x['mediana'], 10)}{_n(x['media'], 10)}"
                 f"{_n(x['p25'], 10)}{_n(x['p75'], 10)}{_n(x['peor'], 10)}{x['sin_dato']:>10}  {x['nivel']}")
    L.append("")

    nr = inf.no_retorno
    L.append("-- ¿CUÁNDO APARECE LA PÉRDIDA? ----------------------------------------------------")
    L.append(f"Patas que acabaron perdiendo: {nr['perdedoras']}   ({nr['nivel']})")
    if nr["perdedoras"]:
        ya = nr["ya_perdida_en_el_primer_punto"]
        L.append(f"Ya tenían el 90 % de la pérdida en el primer punto medido: {ya} "
                 f"({ya / nr['perdedoras'] * 100:.0f} %)")
        L.append("Momento en que el coste de salir alcanza cada fracción de la pérdida final:")
        for k, v in nr["fracciones"].items():
            L.append(f"  {k:>5} de la pérdida   n={v['n']:>4}   mediana {_ms(v['mediana_ms'])}")
        L.append("")
        L.append("Lectura: si las medianas están en el primer segundo, la pérdida se decide al")
        L.append("entrar y cerrar rápido no la evita. Si suben con el horizonte, se cuece despacio")
        L.append("y salir pronto la recorta.")
    L.append("")

    L.append("-- AHORRO HIPOTÉTICO FRENTE A LO QUE PASÓ ------------------------------------------")
    L.append("Diferencia entre cerrar en ese instante y el resultado realizado. Orden de magnitud:")
    L.append("una salida de verdad habría movido el libro y cambiado lo que vino después.")
    L.append(f"{'horizonte':>10}{'n':>6}{'ahorro medio':>15}{'mediano':>12}{'mejor en':>11}  confianza")
    L.append("-" * 100)
    for x in inf.ahorro:
        mejor = "-" if x["mejor_en_pct"] is None else f"{x['mejor_en_pct'] * 100:.0f} %"
        L.append(f"{_ms(x['horizonte_ms']):>10}{x['n']:>6}{_n(x['ahorro_medio'], 15)}"
                 f"{_n(x['ahorro_mediano'], 12)}{mejor:>11}  {x['nivel']}")
    L.append("")

    L.append("-- SEGMENTACIÓN (DESCRIPTIVA) -----------------------------------------------------")
    L.append("Para saber si el problema es uniforme o se concentra. NO se mueve ningún umbral con esto.")
    for nombre, filas in inf.segmentos.items():
        if not filas:
            continue
        L.append(f"  por {nombre}:")
        L.append(f"    {'tramo':<14}{'n':>5}{'recupera':>11}{'coste 60 s':>13}{'final':>10}  confianza")
        for x in filas[:12]:
            rec = "-" if x["recuperacion"] is None else f"{x['recuperacion'] * 100:.0f} %"
            L.append(f"    {str(x['tramo'])[:14]:<14}{x['n']:>5}{rec:>11}"
                     f"{_n(x['coste_60s_mediano'], 13)}{_n(x['final_mediano'], 10)}  {x['nivel']}")
    L.append("")
    L.append("Esta fase mide el problema. No lo resuelve: no hay stop, ni take profit, ni cobertura.")
    return "\n".join(L)
