"""Informe de validación: convertir lo capturado en respuestas, sin tocar ninguna decisión.

Este módulo no cambia el comportamiento del bot. Lee lo que el motor dejó escrito y responde
diez preguntas, cada una con el tamaño de muestra al lado, porque una respuesta con siete
operaciones no es una respuesta:

1. ¿Qué fracción de las órdenes se llena de verdad?
2. ¿Qué fracción haría falta para que poner la orden gane a cruzar el libro?
3. ¿Cuánta ventaja hace falta para que la estrategia tenga valor esperado positivo?
4. ¿Cuánta de la ventaja prometida acaba en el bolsillo?
5. ¿Qué hace el precio justo después de llenarnos?
6. ¿Cuánto tarda en aparecer el movimiento a favor?
7. ¿Cuánto tarda en aparecer el movimiento en contra?
8. ¿Cómo cambia todo según la frescura del libro?
9. ¿Qué parte de las señales ocurre con datos demasiado viejos?
10. ¿Cuántas oportunidades buenas estamos rechazando?

Regla de lectura que atraviesa todo el informe: **un resultado negativo con pocas operaciones no
demuestra que una estrategia no sirva**. Demuestra que todavía no se sabe.
"""
from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import polars as pl

from .evaluacion import CIERRES_EXCLUIDOS, bootstrap_ic, es_del_dado
from .salud import CONTAMINADOS, bucket, corregir, desfase_reloj, freshness_score
from .storage import scan

# --------------------------------------------------------------------------- etiquetas de confianza
NIVELES: tuple[tuple[int, str], ...] = (
    (500, "EVIDENCIA ROBUSTA"),
    (250, "EVIDENCIA MÁS FIRME"),
    (100, "MEDIBLE"),
    (20, "PRELIMINAR"),
    (0, "SOLO DESCRIPTIVO"),
)

# Semáforo. No es verde por ganar dinero: es verde cuando la ganancia está demostrada.
VERDE = "🟢 EVIDENCIA POSITIVA"
AMARILLO = "🟡 DATOS INSUFICIENTES"
NARANJA = "🟠 PROBLEMA DE EJECUCIÓN"
ROJO = "🔴 VALOR ESPERADO NEGATIVO"
NEGRO = "⚫ DATO NO VÁLIDO"

# Tramos fijos de ventaja, en porcentaje sobre el precio de entrada.
TRAMOS_EDGE: tuple[tuple[str, float, float], ...] = (
    ("0-1 %", 0.0, 0.01), ("1-2 %", 0.01, 0.02), ("2-3 %", 0.02, 0.03), ("3-4 %", 0.03, 0.04),
    ("4-5 %", 0.04, 0.05), ("5-7 %", 0.05, 0.07), ("7-10 %", 0.07, 0.10), ("10 %+", 0.10, float("inf")),
)
TASAS_FILL = (0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90, 1.00)
EDGES_PRUEBA = (0.005, 0.01, 0.015, 0.02, 0.03, 0.04, 0.05)
UMBRALES_FRESCURA_MS = (250, 500, 1_000, 2_000, 5_000, 10_000)


def nivel(n: int) -> str:
    for minimo, etiqueta in NIVELES:
        if n >= minimo:
            return etiqueta
    return NIVELES[-1][1]


def _media(xs: list[float]) -> float | None:
    return sum(xs) / len(xs) if xs else None


def _mediana(xs: list[float]) -> float | None:
    if not xs:
        return None
    ys = sorted(xs)
    m = len(ys) // 2
    return ys[m] if len(ys) % 2 else (ys[m - 1] + ys[m]) / 2


def _meta(row: dict[str, Any]) -> dict[str, Any]:
    try:
        return json.loads(row.get("meta") or "{}")
    except (json.JSONDecodeError, TypeError):
        return {}


def _entrada(row: dict[str, Any]) -> float | None:
    """Precio de entrada de una posición llenada."""
    if row.get("size_filled"):
        coste = row.get("cost") or 0.0
        if coste > 0:
            return coste / row["size_filled"]
    e = _meta(row).get("entry")
    return float(e) if e is not None else None


def _drawdown_esperado(pnls: list[float], p: float, sims: int = 200, semilla: int = 7) -> float | None:
    """Caída típica si solo se hubiera llenado una fracción `p` de las órdenes.

    Se conserva el orden en que ocurrieron y se sortea cuáles entran. No inventa resultados: usa
    los que hubo. Lo que supone es que las órdenes que hoy no se llenan darían lo mismo que las
    que sí, que es optimista cuando hay selección adversa.
    """
    if not pnls:
        return None
    rng = random.Random(semilla)
    caidas = [_drawdown([x for x in pnls if rng.random() < p]) for _ in range(sims)]
    m = _mediana(caidas)
    return None if m is None else round(m, 4)


def _drawdown(pnls: list[float]) -> float:
    """Mayor caída acumulada de la serie de resultados, en el orden en que ocurrieron."""
    pico = acumulado = 0.0
    peor = 0.0
    for x in pnls:
        acumulado += x
        pico = max(pico, acumulado)
        peor = min(peor, acumulado - pico)
    return round(peor, 4)


# --------------------------------------------------------------------------- carga
@dataclass
class Datos:
    """Todo lo que el motor dejó escrito, ya separado en limpio, contaminado y sombra."""
    ledger: list[dict[str, Any]] = field(default_factory=list)          # reales, no contaminadas
    contaminadas: list[dict[str, Any]] = field(default_factory=list)    # reales con feed sucio
    sombras: list[dict[str, Any]] = field(default_factory=list)         # rechazadas, seguidas para medir
    descartadas_del_dado: int = 0
    post: list[dict[str, Any]] = field(default_factory=list)
    decisiones: list[dict[str, Any]] = field(default_factory=list)
    fills: list[dict[str, Any]] = field(default_factory=list)
    salud: list[dict[str, Any]] = field(default_factory=list)
    reacciones: list[dict[str, Any]] = field(default_factory=list)
    experimentos: list[dict[str, Any]] = field(default_factory=list)
    desfase_ms: float = 0.0            # desfase de reloj estimado; se descuenta de toda frescura

    @property
    def estrategias(self) -> list[str]:
        """Toda estrategia que aparezca en cualquier parte, incluidas las que solo dejaron dato sucio."""
        todas = self.ledger + self.sombras + self.contaminadas
        return sorted({r.get("strategy") or r.get("kind") or "?" for r in todas})


def _filas(data_dir: str | Path, tabla: str, experiment: str | None = None) -> list[dict[str, Any]]:
    lf = scan(data_dir, tabla)
    if lf is None:
        return []
    if experiment and "experiment" in lf.collect_schema().names():
        lf = lf.filter(pl.col("experiment") == experiment)
    return lf.collect().to_dicts()


def cargar(data_dir: str | Path, experiment: str | None = None) -> Datos:
    d = Datos()
    d.experimentos = _filas(data_dir, "experiments")
    todas = _filas(data_dir, "ledger")
    if experiment:
        todas = [r for r in todas if r.get("experiment") == experiment]
    for r in todas:
        if es_del_dado(r):
            d.descartadas_del_dado += 1
            continue
        if r.get("sombra"):
            d.sombras.append(r)
        elif r.get("feed_state") in CONTAMINADOS or r.get("contaminado"):
            d.contaminadas.append(r)
        else:
            d.ledger.append(r)
    d.post = _filas(data_dir, "post_fill", experiment)
    d.decisiones = _filas(data_dir, "decisions", experiment)
    d.fills = _filas(data_dir, "fill_observations", experiment)
    d.salud = _filas(data_dir, "feed_health", experiment)
    d.reacciones = _filas(data_dir, "reactions", experiment)
    # El desfase de reloj se estima con todo lo observado: el mínimo por ventana cuando está
    # registrado y, si no, las propias medianas. Sin descontarlo, una frescura negativa se leía como
    # el libro más viejo posible en vez de como el más fresco.
    suelos = [r.get("min_ms") for r in d.salud if r.get("min_ms") is not None]
    if not suelos:
        suelos = ([r.get("freshness_ms") for r in d.salud]
                  + [r.get("freshness_ms") for r in d.ledger + d.contaminadas + d.sombras]
                  + [r.get("freshness_ms") for r in d.decisiones])
    d.desfase_ms = desfase_reloj(suelos)
    return d


def _validas(filas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Posiciones que llegaron a operarse y cuyo cierre dice algo de la señal."""
    return [r for r in filas if (r.get("size_filled") or 0) > 0
            and r.get("exit_reason") not in CIERRES_EXCLUIDOS]


def _por_estrategia(filas: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for r in filas:
        out.setdefault(r.get("strategy") or r.get("kind") or "?", []).append(r)
    return out


# --------------------------------------------------------------------------- 1 y 2: llenado
@dataclass
class Llenado:
    estrategia: str
    ordenes: int = 0
    llenadas: int = 0
    tasa: float | None = None
    tasa_conservadora: float | None = None
    tasa_optimista: float | None = None
    requerida: float | None = None
    espera_mediana_s: float | None = None
    cola_mediana: float | None = None
    barridas: int = 0
    estado: str = AMARILLO
    sensibilidad: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


def llenado(d: Datos) -> list[Llenado]:
    """Tasa observada frente a la necesaria, y qué pasaría con otras tasas de llenado."""
    por_est = _por_estrategia([r for r in d.fills if not r.get("sombra")])
    pnl_por_est = {k: _validas(v) for k, v in _por_estrategia(d.ledger).items()}
    out: list[Llenado] = []
    for est in sorted(set(por_est) | set(pnl_por_est)):
        obs = por_est.get(est, [])
        L = Llenado(estrategia=est, ordenes=len(obs))
        if obs:
            L.llenadas = sum(1 for r in obs if r.get("llenada"))
            L.tasa = round(L.llenadas / len(obs), 4)
            L.tasa_conservadora = round(sum(1 for r in obs if r.get("llenada_conservador")) / len(obs), 4)
            L.tasa_optimista = round(sum(1 for r in obs if r.get("llenada_optimista")) / len(obs), 4)
            L.espera_mediana_s = _mediana([r["espera_ms"] / 1000 for r in obs
                                           if r.get("espera_ms") and r["espera_ms"] >= 0])
            L.cola_mediana = _mediana([r["cola_delante"] for r in obs if r.get("cola_delante") is not None])
            L.barridas = sum(1 for r in obs if r.get("barrido"))
        validas = pnl_por_est.get(est, [])
        maker = [r for r in validas if (r.get("entry_role") or _meta(r).get("entry_role")) == "maker"]
        pnls = [r["realized_pnl"] for r in maker]
        media_llenada = _media(pnls)
        # lo que daría cruzar el libro: la ventaja taker que el detector calculó, por el tamaño
        cruzar = _media([(r.get("edge_taker") if r.get("edge_taker") is not None else _meta(r).get("edge_taker") or 0.0)
                         * (r.get("size_filled") or 0) for r in maker])
        if media_llenada and media_llenada > 0:
            L.requerida = round(max(0.0, min((cruzar or 0.0) / media_llenada, 1.0)), 4)
        elif media_llenada is not None and media_llenada <= 0:
            L.requerida = 1.0 if (cruzar or 0) <= 0 else 1.0     # perdiendo por operación, ninguna tasa salva
        # sensibilidad: qué valor esperado por orden daría cada tasa de llenado
        limpios = [r["realized_pnl"] for r in maker if not r.get("barrido")]
        media_limpia = _media(limpios)
        for p in TASAS_FILL:
            L.sensibilidad.append({
                "tasa": p,
                "ev_por_orden": None if media_llenada is None else round(p * media_llenada, 4),
                "ev_sin_barridos": None if media_limpia is None else round(p * media_limpia, 4),
                "pnl_esperado": None if media_llenada is None else round(p * media_llenada * max(len(obs), len(maker)), 2),
                "drawdown": _drawdown_esperado(pnls, p),
            })
        L.estado = _semaforo_llenado(L, len(validas))
        out.append(L)
    return out


def _semaforo_llenado(L: Llenado, n_validas: int) -> str:
    if L.ordenes >= 3 and L.tasa is not None and L.requerida is not None and L.tasa < L.requerida:
        return NARANJA
    if n_validas < 20:
        return AMARILLO
    return VERDE


# --------------------------------------------------------------------------- 3: edge mínimo
def barrido_de_edge(d: Datos) -> list[dict[str, Any]]:
    """Con cada umbral de ventaja, ¿qué habría quedado y cuánto habría dado por operación?"""
    out: list[dict[str, Any]] = []
    for est, filas in sorted(_por_estrategia(d.ledger).items()):
        validas = _validas(filas)
        for umbral in EDGES_PRUEBA:
            sub = [r for r in validas if (r.get("predicted_edge") or 0) >= umbral]
            pnls = [r["realized_pnl"] for r in sub]
            por_share = [r["realized_pnl"] / r["size_filled"] for r in sub if r.get("size_filled")]
            out.append({"estrategia": est, "umbral": umbral, "n": len(sub),
                        "pnl": round(sum(pnls), 4) if pnls else 0.0,
                        "media": None if not pnls else round(sum(pnls) / len(pnls), 4),
                        "por_share": None if not por_share else round(sum(por_share) / len(por_share), 5),
                        "nivel": nivel(len(sub))})
    return out


# --------------------------------------------------------------------------- 4: tramos de ventaja
def _tramo_de(pct: float) -> str:
    for nombre, lo, hi in TRAMOS_EDGE:
        if lo <= pct < hi:
            return nombre
    return TRAMOS_EDGE[-1][0]


def _ordenes_por_tramo(fills: list[dict[str, Any]]) -> dict[tuple[str, str], tuple[int, int]]:
    """Órdenes puestas y llenadas en cada tramo de ventaja, para poder cruzarlo con el resultado."""
    acc: dict[tuple[str, str], list[int]] = {}
    for r in fills:
        if r.get("sombra") or not r.get("precio"):
            continue
        pct = (r.get("edge_net") or 0.0) / r["precio"]
        k = (r.get("strategy") or "?", _tramo_de(pct))
        c = acc.setdefault(k, [0, 0])
        c[0] += 1
        c[1] += 1 if r.get("llenada") else 0
    return {k: (v[0], v[1]) for k, v in acc.items()}


def tramos_de_edge(d: Datos) -> list[dict[str, Any]]:
    """Ventaja prometida contra resultado, por tramos fijos. No se supone que más sea mejor."""
    out: list[dict[str, Any]] = []
    ordenes = _ordenes_por_tramo(d.fills)
    for est, filas in sorted(_por_estrategia(d.ledger).items()):
        validas = _validas(filas)
        con_pct: list[tuple[float, dict[str, Any]]] = []
        for r in validas:
            ent = _entrada(r)
            if ent and ent > 0 and r.get("predicted_edge") is not None:
                con_pct.append((r["predicted_edge"] / ent, r))
        for nombre, lo, hi in TRAMOS_EDGE:
            sub = [r for pct, r in con_pct if lo <= pct < hi]
            pnls = [r["realized_pnl"] for r in sub]
            adv = [r["adverse_10s"] for r in sub if r.get("adverse_10s") is not None]
            tfav = [r["t_fav_1t_ms"] for r in sub if r.get("t_fav_1t_ms") is not None]
            puestas, llenas = ordenes.get((est, nombre), (0, 0))
            out.append({"estrategia": est, "tramo": nombre, "n": len(sub),
                        "ordenes": puestas, "llenadas": llenas,
                        "tasa_llenado": round(llenas / puestas, 3) if puestas else None,
                        "pnl": round(sum(pnls), 4) if pnls else 0.0,
                        "media": _media(pnls) and round(_media(pnls), 4),
                        "acierto": None if not pnls else round(sum(1 for x in pnls if x > 0) / len(pnls), 3),
                        "adversa_10s": _media(adv) and round(_media(adv), 5),
                        "t_favorable_1t_s": _mediana(tfav) and round(_mediana(tfav) / 1000, 2),
                        "drawdown": _drawdown(pnls), "nivel": nivel(len(sub))})
    return out


# --------------------------------------------------------------------------- 5: después del fill
def despues_del_fill(d: Datos) -> list[dict[str, Any]]:
    """Selección adversa y recorrido: ¿el mercado se mueve a favor o nos usan como liquidez?"""
    horizontes = ["adverse_100ms", "adverse_500ms", "adverse_1s", "adverse_2s", "adverse_5s",
                  "adverse_10s", "adverse_30s", "adverse_60s"]
    out: list[dict[str, Any]] = []
    for est, filas in sorted(_por_estrategia(d.ledger).items()):
        validas = _validas(filas)
        fila: dict[str, Any] = {"estrategia": est, "n": len(validas), "nivel": nivel(len(validas))}
        for h in horizontes:
            xs = [r[h] for r in validas if r.get(h) is not None]
            fila[h] = None if not xs else round(sum(xs) / len(xs), 5)
        mfe = [r["mfe"] for r in validas if r.get("mfe") is not None]
        mae = [r["mae"] for r in validas if r.get("mae") is not None]
        fila["mfe_medio"] = _media(mfe) and round(_media(mfe), 5)
        fila["mae_medio"] = _media(mae) and round(_media(mae), 5)
        fila["t_mfe_s"] = _mediana([r["t_mfe_ms"] / 1000 for r in validas if r.get("t_mfe_ms") is not None])
        fila["t_mae_s"] = _mediana([r["t_mae_ms"] / 1000 for r in validas if r.get("t_mae_ms") is not None])
        if mfe and mae:
            suma = sum(mfe) + abs(sum(mae))
            fila["razon_mfe_mae"] = round(sum(mfe) / abs(sum(mae)), 3) if sum(mae) else None
            fila["a_favor"] = round(sum(mfe) / suma, 3) if suma else None
        out.append(fila)
    return out


# --------------------------------------------------------------------------- 6 y 7: tiempos
def tiempos_de_movimiento(d: Datos) -> list[dict[str, Any]]:
    """Cuánto tarda el precio en moverse medio tick, uno, dos y tres, a favor y en contra."""
    out: list[dict[str, Any]] = []
    for est, filas in sorted(_por_estrategia(d.ledger).items()):
        validas = _validas(filas)
        fila: dict[str, Any] = {"estrategia": est, "n": len(validas), "nivel": nivel(len(validas))}
        for etiqueta, col in (("05t", "05t"), ("1t", "1t"), ("2t", "2t"), ("3t", "3t")):
            for lado in ("fav", "adv"):
                c = f"t_{lado}_{col}_ms"
                xs = [r[c] / 1000 for r in validas if r.get(c) is not None]
                fila[f"{lado}_{etiqueta}_s"] = _mediana(xs) and round(_mediana(xs), 2)
                fila[f"{lado}_{etiqueta}_pct"] = round(len(xs) / len(validas), 3) if validas else None
        out.append(fila)
    return out


def pnl_por_horizonte(d: Datos) -> list[dict[str, Any]]:
    """¿En qué intervalo aparece de verdad la ventaja? Del recorrido del precio tras el fill."""
    por: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for r in d.post:
        if r.get("sombra") or r.get("contaminado"):
            continue
        por.setdefault((r.get("strategy") or "?", int(r["horizonte_ms"])), []).append(r)
    out: list[dict[str, Any]] = []
    for (est, h), filas in sorted(por.items()):
        deltas = [r["delta"] for r in filas if r.get("delta") is not None]
        bids = [r["delta_bid"] for r in filas if r.get("delta_bid") is not None]
        if not deltas:
            continue
        out.append({"estrategia": est, "horizonte_ms": h, "n": len(deltas),
                    "delta_medio": round(sum(deltas) / len(deltas), 5),
                    "delta_bid_medio": None if not bids else round(sum(bids) / len(bids), 5),
                    "a_favor": round(sum(1 for x in deltas if x > 0) / len(deltas), 3),
                    "nivel": nivel(len(deltas))})
    return out


# --------------------------------------------------------------------------- 8 y 9: frescura
def por_frescura(d: Datos) -> list[dict[str, Any]]:
    """Todo lo anterior, cortado por la antigüedad del libro con el que se decidió."""
    cajones: dict[str, dict[str, Any]] = {}
    for r in d.ledger + d.contaminadas:
        b = bucket(r.get("freshness_ms"), d.desfase_ms)
        c = cajones.setdefault(b, {"tramo": b, "senales": 0, "llenadas": 0, "pnl": 0.0,
                                   "adversa": [], "n_validas": 0, "scores": []})
        c["senales"] += 1
        sc = freshness_score(r.get("freshness_ms"), desfase_ms=d.desfase_ms)
        if sc is not None:
            c["scores"].append(sc)
        if (r.get("size_filled") or 0) > 0:
            c["llenadas"] += 1
        if r in d.ledger and r.get("exit_reason") not in CIERRES_EXCLUIDOS and (r.get("size_filled") or 0) > 0:
            c["pnl"] += r["realized_pnl"]
            c["n_validas"] += 1
            if r.get("adverse_10s") is not None:
                c["adversa"].append(r["adverse_10s"])
    for r in d.decisiones:
        if r.get("decision") != "no_trade":
            continue
        b = bucket(r.get("freshness_ms"), d.desfase_ms)
        c = cajones.setdefault(b, {"tramo": b, "senales": 0, "llenadas": 0, "pnl": 0.0,
                                   "adversa": [], "n_validas": 0})
        c.setdefault("no_trade", 0)
        c["no_trade"] = c.get("no_trade", 0) + 1
    orden = [n for n, _, _ in __import__("scalper.salud", fromlist=["BUCKETS"]).BUCKETS] + ["desconocida"]
    out = []
    for b in orden:
        c = cajones.get(b)
        if not c:
            continue
        out.append({"tramo": b, "senales": c["senales"], "no_trade": c.get("no_trade", 0),
                    "llenadas": c["llenadas"],
                    "tasa_llenado": round(c["llenadas"] / c["senales"], 3) if c["senales"] else None,
                    "n_validas": c["n_validas"], "pnl": round(c["pnl"], 4),
                    "pnl_medio": round(c["pnl"] / c["n_validas"], 4) if c["n_validas"] else None,
                    "adversa_10s": _media(c["adversa"]) and round(_media(c["adversa"]), 5),
                    "score_medio": _media(c.get("scores") or []) and round(_media(c["scores"]), 3),
                    "nivel": nivel(c["n_validas"])})
    return out


def umbral_de_frescura(d: Datos) -> list[dict[str, Any]]:
    """Qué habría dejado pasar cada umbral posible. El actual es una hipótesis, no una verdad."""
    reales = _validas(d.ledger + d.contaminadas)
    sombras_feed = [r for r in _validas(d.sombras) if r.get("motivo_rechazo") == "feed_atrasado"]
    out = []
    for t in UMBRALES_FRESCURA_MS:
        dentro = [r for r in reales + sombras_feed
                  if (corregir(r.get("freshness_ms"), d.desfase_ms) or 0.0) <= t]
        pnl = sum(r["realized_pnl"] for r in dentro)
        out.append({"umbral_ms": t, "operaciones": len(dentro), "pnl": round(pnl, 4),
                    "media": round(pnl / len(dentro), 4) if dentro else None, "nivel": nivel(len(dentro))})
    return out


def salud_del_feed(d: Datos) -> dict[str, Any]:
    """Cuánto tiempo estuvo el feed en cada estado y qué parte del dato queda contaminada."""
    por_estado: dict[str, int] = {}
    for r in d.salud:
        por_estado[r["estado"]] = por_estado.get(r["estado"], 0) + 1
    total = sum(por_estado.values())
    decisiones_sucias = sum(1 for r in d.decisiones if r.get("contaminado"))
    return {
        "muestras": total,
        "reparto": {k: round(v / total, 3) for k, v in sorted(por_estado.items())} if total else {},
        "posiciones_validas": len(d.ledger),
        "posiciones_contaminadas": len(d.contaminadas),
        "decisiones_contaminadas": decisiones_sucias,
        "decisiones": len(d.decisiones),
        "freshness_mediana_ms": _mediana([corregir(r["freshness_ms"], d.desfase_ms) for r in d.salud]),
        "freshness_p95_ms": _mediana([corregir(r["p95_ms"], d.desfase_ms) for r in d.salud]),
        "desfase_reloj_ms": d.desfase_ms,
        "descartadas_del_dado": d.descartadas_del_dado,
    }


# --------------------------------------------------------------------------- 10: lo que se rechaza
def oportunidades_rechazadas(d: Datos) -> list[dict[str, Any]]:
    """Qué habría pasado con lo que no se operó. Nunca se mezcla con el resultado real."""
    motivos: dict[tuple[str, str], dict[str, Any]] = {}
    for r in d.decisiones:
        if r.get("decision") != "no_trade":
            continue
        k = (r.get("strategy") or "?", r.get("motivo") or "?")
        c = motivos.setdefault(k, {"estrategia": k[0], "motivo": k[1], "rechazos": 0,
                                   "seguidas": 0, "llenadas": 0, "pnl": 0.0, "pnls": []})
        c["rechazos"] += 1
    for r in _validas(d.sombras):
        k = (r.get("strategy") or "?", r.get("motivo_rechazo") or "?")
        c = motivos.setdefault(k, {"estrategia": k[0], "motivo": k[1], "rechazos": 0,
                                  "seguidas": 0, "llenadas": 0, "pnl": 0.0, "pnls": []})
        c["seguidas"] += 1
        c["llenadas"] += 1
        c["pnl"] += r["realized_pnl"]
        c["pnls"].append(r["realized_pnl"])
    out = []
    for c in motivos.values():
        pnls = c.pop("pnls")
        c["media"] = round(sum(pnls) / len(pnls), 4) if pnls else None
        c["pnl"] = round(c["pnl"], 4)
        c["acierto"] = round(sum(1 for x in pnls if x > 0) / len(pnls), 3) if pnls else None
        c["nivel"] = nivel(len(pnls))
        c["veredicto"] = _veredicto_rechazo(c["media"], len(pnls))
        out.append(c)
    return sorted(out, key=lambda x: (-x["rechazos"], x["estrategia"]))


def _veredicto_rechazo(media: float | None, n: int) -> str:
    if n < 20:
        return "muestra insuficiente"
    if media is None:
        return "sin seguimiento"
    return "se rechazaban buenas" if media > 0 else "bien rechazadas"


# --------------------------------------------------------------------------- salidas
def probabilidad_de_salida(d: Datos) -> list[dict[str, Any]]:
    """P(objetivo | llenada), P(stop | llenada) y cuál llegó antes. Solo se mide: no cambia nada."""
    out = []
    for est, filas in sorted(_por_estrategia(d.ledger).items()):
        validas = [r for r in _validas(filas) if r.get("t_target_ms") is not None or r.get("t_stop_ms") is not None
                   or r.get("exit_reason") in ("target", "stop", "time_stop", "max_hold")]
        if not validas:
            continue
        n = len(validas)
        target = sum(1 for r in validas if r.get("t_target_ms") is not None)
        stop = sum(1 for r in validas if r.get("t_stop_ms") is not None)
        antes = sum(1 for r in validas if r.get("target_antes_que_stop"))
        out.append({"estrategia": est, "n": n,
                    "p_target": round(target / n, 3), "p_stop": round(stop / n, 3),
                    "p_target_antes": round(antes / n, 3),
                    "t_target_s": _mediana([r["t_target_ms"] / 1000 for r in validas if r.get("t_target_ms")]),
                    "t_stop_s": _mediana([r["t_stop_ms"] / 1000 for r in validas if r.get("t_stop_ms")]),
                    "nivel": nivel(n)})
    return out


def cadena_de_tiempos(d: Datos) -> dict[str, Any]:
    """Evento → reacción del mercado → llenado → movimiento a favor → salida, en medianas."""
    reaccion = _mediana([r["lag_ms"] / 1000 for r in d.reacciones if r.get("lag_ms") is not None])
    validas = _validas(d.ledger)
    espera = _mediana([(r["ts_fill"] - r["ts_placed"]) / 1000 for r in validas
                       if r.get("ts_placed") and r.get("ts_fill") and r["ts_fill"] >= r["ts_placed"]])
    favorable = _mediana([r["t_fav_1t_ms"] / 1000 for r in validas if r.get("t_fav_1t_ms") is not None])
    salida = _mediana([r["hold_s"] for r in validas if r.get("hold_s") is not None])
    return {
        "evento_a_reaccion_s": reaccion,
        "orden_a_llenado_s": espera,
        "llenado_a_favorable_s": favorable,
        "llenado_a_salida_s": salida,
        "retraso_feed_ms": _mediana([corregir(r["freshness_ms"], d.desfase_ms)
                                     for r in validas if r.get("freshness_ms") is not None]),
        "retraso_proceso_ms": _mediana([r["proc_delay_ms"] for r in validas if r.get("proc_delay_ms")]),
        "retraso_decision_ms": _mediana([r["decision_delay_ms"] for r in validas if r.get("decision_delay_ms")]),
        "retraso_ejecucion_ms": _mediana([r["exec_delay_ms"] for r in validas if r.get("exec_delay_ms")]),
        "n_reacciones": sum(1 for r in d.reacciones if r.get("lag_ms") is not None),
        "n": len(validas),
    }


# --------------------------------------------------------------------------- semáforo y madurez
@dataclass
class Estado:
    estrategia: str
    n: int
    nivel: str
    semaforo: str
    motivo: str
    listo_para_medir: bool = False
    faltan: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


def estado_por_estrategia(d: Datos, lls: list[Llenado]) -> list[Estado]:
    """Semáforo honesto: verde solo cuando la ganancia está demostrada, no cuando es positiva."""
    por_ll = {l.estrategia: l for l in lls}
    out: list[Estado] = []
    for est in d.estrategias:
        filas = [r for r in d.ledger if (r.get("strategy") or r.get("kind")) == est]
        sucias = [r for r in d.contaminadas if (r.get("strategy") or r.get("kind")) == est]
        validas = _validas(filas)
        n = len(validas)
        pnls = [r["realized_pnl"] for r in validas]
        ic = bootstrap_ic(pnls)
        L = por_ll.get(est)
        if not validas and sucias:
            semaforo, motivo = NEGRO, "todas las posiciones se tomaron con el feed viejo o congelado"
        elif L is not None and L.estado == NARANJA:
            semaforo = NARANJA
            motivo = (f"se llena el {L.tasa * 100:.0f} % de las órdenes y haría falta el "
                      f"{L.requerida * 100:.0f} %")
        elif n < 20:
            semaforo, motivo = AMARILLO, f"solo hay {n} operaciones: no alcanza para concluir nada"
        elif ic is not None and ic[1] < 0:
            semaforo, motivo = ROJO, f"el intervalo de confianza queda entero por debajo de cero {ic}"
        elif ic is not None and ic[0] > 0:
            semaforo, motivo = VERDE, f"el intervalo de confianza queda entero por encima de cero {ic}"
        else:
            semaforo, motivo = AMARILLO, "la ganancia no se distingue del azar todavía"
        e = Estado(estrategia=est, n=n, nivel=nivel(n), semaforo=semaforo, motivo=motivo)
        e.faltan = _faltan_para_medir(d, est, L, n)
        e.listo_para_medir = not e.faltan
        out.append(e)
    return out


def _faltan_para_medir(d: Datos, est: str, L: Llenado | None, n: int) -> list[str]:
    """Criterio MEDIBLE: no dice que la estrategia gane, dice que ya se puede juzgar."""
    faltan: list[str] = []
    if n < 100:
        faltan.append(f"faltan operaciones: {n} de 100")
    if L is None or L.ordenes == 0:
        faltan.append("no hay observaciones de llenado")
    elif L.tasa is None:
        faltan.append("no se pudo calcular la tasa de llenado")
    sucias = sum(1 for r in d.contaminadas if (r.get("strategy") or r.get("kind")) == est)
    validas = [r for r in _validas(d.ledger) if (r.get("strategy") or r.get("kind")) == est]
    if validas and sucias / max(len(validas) + sucias, 1) > 0.3:
        faltan.append("más de un tercio de las operaciones se tomaron con datos sucios")
    if not any(r.get("adverse_10s") is not None for r in validas):
        faltan.append("falta medir la selección adversa")
    if not any(r.get("freshness_ms") is not None for r in validas):
        faltan.append("falta registrar la frescura del libro")
    return faltan


# --------------------------------------------------------------------------- informe
@dataclass
class Informe:
    experimento: str | None
    datos: Datos
    llenado: list[Llenado]
    barrido_edge: list[dict[str, Any]]
    tramos: list[dict[str, Any]]
    post_fill: list[dict[str, Any]]
    tiempos: list[dict[str, Any]]
    horizontes: list[dict[str, Any]]
    frescura: list[dict[str, Any]]
    umbrales_frescura: list[dict[str, Any]]
    salud: dict[str, Any]
    rechazos: list[dict[str, Any]]
    salidas: list[dict[str, Any]]
    cadena: dict[str, Any]
    estados: list[Estado]

    def to_dict(self) -> dict[str, Any]:
        return {
            "experimento": self.experimento,
            "llenado": [l.to_dict() for l in self.llenado],
            "barrido_edge": self.barrido_edge, "tramos": self.tramos, "post_fill": self.post_fill,
            "tiempos": self.tiempos, "horizontes": self.horizontes, "frescura": self.frescura,
            "umbrales_frescura": self.umbrales_frescura, "salud": self.salud, "rechazos": self.rechazos,
            "salidas": self.salidas, "cadena": self.cadena,
            "estados": [e.to_dict() for e in self.estados],
        }


def analizar(data_dir: str | Path, experiment: str | None = None) -> Informe:
    d = cargar(data_dir, experiment)
    lls = llenado(d)
    return Informe(
        experimento=experiment, datos=d, llenado=lls, barrido_edge=barrido_de_edge(d),
        tramos=tramos_de_edge(d), post_fill=despues_del_fill(d), tiempos=tiempos_de_movimiento(d),
        horizontes=pnl_por_horizonte(d), frescura=por_frescura(d), umbrales_frescura=umbral_de_frescura(d),
        salud=salud_del_feed(d), rechazos=oportunidades_rechazadas(d), salidas=probabilidad_de_salida(d),
        cadena=cadena_de_tiempos(d), estados=estado_por_estrategia(d, lls),
    )


def _f(x: Any, d: int = 4, ancho: int = 10) -> str:
    if x is None:
        return "-".rjust(ancho)
    if isinstance(x, float):
        return f"{x:+.{d}f}".rjust(ancho)
    return str(x).rjust(ancho)


def _p(x: float | None, ancho: int = 8) -> str:
    return ("-" if x is None else f"{x * 100:.0f} %").rjust(ancho)


def formatear(inf: Informe) -> str:  # noqa: C901 - es un informe, se lee de arriba abajo
    d = inf.datos
    L: list[str] = []
    L.append("=" * 100)
    L.append("  INFORME DE VALIDACIÓN DE EJECUCIÓN")
    L.append("=" * 100)
    if inf.experimento:
        L.append(f"Experimento: {inf.experimento}")
    elif d.experimentos:
        L.append(f"Experimentos en los datos: {len(d.experimentos)} "
                 f"(usa --experimento para quedarte con uno solo)")
    L.append("")
    L.append("Este informe no busca que el bot gane más. Busca saber qué es verdad.")
    L.append("Cada bloque lleva el tamaño de muestra: con menos de 20 operaciones nada de esto concluye.")
    L.append("")

    # ---- 0. calidad del dato
    s = inf.salud
    L.append("-- CALIDAD DEL DATO ---------------------------------------------------------------")
    L.append(f"Posiciones válidas: {s['posiciones_validas']}   contaminadas (feed viejo o congelado): "
             f"{s['posiciones_contaminadas']}   descartadas del modelo viejo: {s['descartadas_del_dado']}")
    if s["muestras"]:
        reparto = "  ".join(f"{k} {v * 100:.0f} %" for k, v in s["reparto"].items())
        L.append(f"Tiempo del feed en cada estado: {reparto}")
        L.append(f"Frescura mediana {s['freshness_mediana_ms']:.0f} ms   p95 típico "
                 f"{s['freshness_p95_ms']:.0f} ms   (sobre el suelo observado)")
        if s.get("desfase_reloj_ms"):
            L.append(f"Desfase de reloj estimado: {s['desfase_reloj_ms']:.0f} ms. La frescura de arriba es "
                     f"relativa a ese suelo:")
            L.append("  sin relojes sincronizados no hay retraso absoluto, solo comparación entre momentos.")
    L.append(f"Decisiones registradas: {s['decisiones']}  (con datos sucios: {s['decisiones_contaminadas']})")
    L.append("")

    # ---- 1 y 2
    L.append("-- 1 y 2. ¿SE LLENAN LAS ÓRDENES, Y HACEN FALTA MÁS? -------------------------------")
    L.append(f"{'estrategia':24}{'órdenes':>9}{'llenado':>9}{'conserv.':>10}{'optim.':>9}"
             f"{'necesario':>11}{'espera':>9}{'cola':>8}  estado")
    L.append("-" * 100)
    for x in inf.llenado:
        espera = "-" if x.espera_mediana_s is None else f"{x.espera_mediana_s:.1f} s"
        cola = "-" if x.cola_mediana is None else f"{x.cola_mediana:.0f}"
        L.append(f"{x.estrategia[:24]:24}{x.ordenes:>9}{_p(x.tasa, 9)}{_p(x.tasa_conservadora, 10)}"
                 f"{_p(x.tasa_optimista, 9)}{_p(x.requerida, 11)}{espera:>9}{cola:>8}  {x.estado}")
    L.append("")
    L.append("Sensibilidad al llenado: valor esperado por orden si la tasa fuera otra.")
    L.append("Supone que las órdenes que hoy no se llenan se comportarían como las que sí. Es")
    L.append("optimista si hay selección adversa, y por eso al lado va la columna sin barridos.")
    for x in inf.llenado:
        if not any(s_["ev_por_orden"] for s_ in x.sensibilidad):
            continue
        L.append(f"  {x.estrategia}")
        L.append("     " + "".join(f"{s_['tasa'] * 100:>9.0f}%" for s_ in x.sensibilidad))
        L.append("  ev " + "".join(_f(s_["ev_por_orden"], 3, 10) for s_ in x.sensibilidad))
        L.append("  sb " + "".join(_f(s_["ev_sin_barridos"], 3, 10) for s_ in x.sensibilidad))
        L.append("  dd " + "".join(_f(s_.get("drawdown"), 2, 10) for s_ in x.sensibilidad))
    L.append("")

    # ---- 3
    L.append("-- 3. ¿CUÁNTA VENTAJA HACE FALTA? --------------------------------------------------")
    L.append(f"{'estrategia':24}{'umbral':>9}{'n':>6}{'pnl':>10}{'por op.':>10}{'por share':>12}  confianza")
    L.append("-" * 100)
    for r in inf.barrido_edge:
        if not r["n"]:
            continue
        L.append(f"{r['estrategia'][:24]:24}{r['umbral']:>9.3f}{r['n']:>6}{_f(r['pnl'], 2, 10)}"
                 f"{_f(r['media'], 3, 10)}{_f(r['por_share'], 5, 12)}  {r['nivel']}")
    L.append("")

    # ---- 4
    L.append("-- 4. VENTAJA PROMETIDA CONTRA RESULTADO, POR TRAMOS -------------------------------")
    L.append(f"{'estrategia':22}{'tramo':>9}{'órdenes':>9}{'llenado':>9}{'n':>5}{'pnl':>10}{'por op.':>10}"
             f"{'acierto':>9}{'adversa':>10}{'a favor en':>12}{'caída':>9}  confianza")
    L.append("-" * 124)
    for r in inf.tramos:
        if not r["n"] and not r.get("ordenes"):
            continue
        tf = "-" if r["t_favorable_1t_s"] is None else f"{r['t_favorable_1t_s']:.1f} s"
        L.append(f"{r['estrategia'][:22]:22}{r['tramo']:>9}{r.get('ordenes', 0):>9}"
                 f"{_p(r.get('tasa_llenado'), 9)}{r['n']:>5}{_f(r['pnl'], 2, 10)}"
                 f"{_f(r['media'], 3, 10)}{_p(r['acierto'], 9)}{_f(r['adversa_10s'], 5, 10)}{tf:>12}"
                 f"{_f(r['drawdown'], 2, 9)}  {r['nivel']}")
    L.append("")

    # ---- 5
    L.append("-- 5. QUÉ PASA DESPUÉS DE LLENARNOS ------------------------------------------------")
    L.append("Movimiento medio del mid respecto al precio de entrada. Negativo = se va en contra.")
    L.append(f"{'estrategia':22}{'n':>5}{'100ms':>9}{'500ms':>9}{'1s':>9}{'2s':>9}{'5s':>9}{'10s':>9}"
             f"{'30s':>9}{'60s':>9}")
    L.append("-" * 100)
    for r in inf.post_fill:
        if not r["n"]:
            continue
        L.append(f"{r['estrategia'][:22]:22}{r['n']:>5}" + "".join(
            _f(r.get(c), 4, 9) for c in ("adverse_100ms", "adverse_500ms", "adverse_1s", "adverse_2s",
                                         "adverse_5s", "adverse_10s", "adverse_30s", "adverse_60s")))
    L.append("")
    L.append(f"{'estrategia':22}{'MFE medio':>12}{'MAE medio':>12}{'t MFE':>9}{'t MAE':>9}"
             f"{'reparto a favor':>18}  confianza")
    L.append("-" * 100)
    for r in inf.post_fill:
        if not r["n"]:
            continue
        tmfe = "-" if r.get("t_mfe_s") is None else f"{r['t_mfe_s']:.1f} s"
        tmae = "-" if r.get("t_mae_s") is None else f"{r['t_mae_s']:.1f} s"
        L.append(f"{r['estrategia'][:22]:22}{_f(r.get('mfe_medio'), 5, 12)}{_f(r.get('mae_medio'), 5, 12)}"
                 f"{tmfe:>9}{tmae:>9}{_p(r.get('a_favor'), 18)}  {r['nivel']}")
    L.append("")

    # ---- 6 y 7
    L.append("-- 6 y 7. CUÁNTO TARDA EL MOVIMIENTO -----------------------------------------------")
    L.append("Mediana del tiempo hasta cada movimiento, y qué parte de las operaciones lo alcanza.")
    L.append(f"{'estrategia':22}{'n':>5}" + "".join(f"{c:>12}" for c in
             ("+0.5t", "+1t", "+2t", "+3t", "-0.5t", "-1t", "-2t", "-3t")))
    L.append("-" * 120)
    for r in inf.tiempos:
        if not r["n"]:
            continue
        celdas = []
        for lado, et in (("fav", "05t"), ("fav", "1t"), ("fav", "2t"), ("fav", "3t"),
                         ("adv", "05t"), ("adv", "1t"), ("adv", "2t"), ("adv", "3t")):
            s_ = r.get(f"{lado}_{et}_s")
            p_ = r.get(f"{lado}_{et}_pct")
            celdas.append((f"{s_:.1f}s/{p_ * 100:.0f}%" if s_ is not None and p_ is not None else "-").rjust(12))
        L.append(f"{r['estrategia'][:22]:22}{r['n']:>5}" + "".join(celdas))
    L.append("")
    L.append("¿Dónde aparece la ventaja? Movimiento medio del mid tras el fill, por horizonte:")
    por_est: dict[str, list[dict[str, Any]]] = {}
    for r in inf.horizontes:
        por_est.setdefault(r["estrategia"], []).append(r)
    for est, filas in sorted(por_est.items()):
        filas.sort(key=lambda x: x["horizonte_ms"])
        L.append(f"  {est}")
        L.append("     " + "".join(f"{_hms(x['horizonte_ms']):>10}" for x in filas))
        L.append("  mid" + "".join(_f(x["delta_medio"], 4, 10) for x in filas))
        L.append("  bid" + "".join(_f(x["delta_bid_medio"], 4, 10) for x in filas))
        L.append("  n  " + "".join(str(x["n"]).rjust(10) for x in filas))
    L.append("")

    # ---- 8 y 9
    L.append("-- 8 y 9. ¿CÓMO AFECTA LA FRESCURA DEL LIBRO? --------------------------------------")
    L.append(f"{'antigüedad':14}{'señales':>9}{'no opera':>10}{'llenadas':>10}{'válidas':>9}"
             f"{'pnl':>10}{'por op.':>10}{'adversa':>10}  confianza")
    L.append("-" * 100)
    for r in inf.frescura:
        L.append(f"{r['tramo']:14}{r['senales']:>9}{r['no_trade']:>10}{r['llenadas']:>10}{r['n_validas']:>9}"
                 f"{_f(r['pnl'], 2, 10)}{_f(r['pnl_medio'], 3, 10)}{_f(r['adversa_10s'], 5, 10)}  {r['nivel']}")
    L.append("")
    L.append("Qué habría dejado pasar cada umbral posible (el actual es una hipótesis):")
    L.append(f"{'umbral':>10}{'operaciones':>13}{'pnl':>10}{'por op.':>10}  confianza")
    for r in inf.umbrales_frescura:
        L.append(f"{r['umbral_ms']:>8} ms{r['operaciones']:>13}{_f(r['pnl'], 2, 10)}"
                 f"{_f(r['media'], 3, 10)}  {r['nivel']}")
    L.append("")
    L.append("No se elige el umbral que más ganancia dé en estos datos: eso sería ajustar al ruido.")
    L.append("")

    # ---- 10
    L.append("-- 10. ¿QUÉ ESTAMOS RECHAZANDO? ----------------------------------------------------")
    L.append("Cada señal rechazada se sigue como sombra. Su resultado nunca entra en el dinero.")
    L.append(f"{'estrategia':22}{'motivo':26}{'rechazos':>10}{'seguidas':>10}{'pnl':>10}{'por op.':>10}  veredicto")
    L.append("-" * 112)
    for r in inf.rechazos:
        L.append(f"{r['estrategia'][:22]:22}{r['motivo'][:26]:26}{r['rechazos']:>10}{r['seguidas']:>10}"
                 f"{_f(r['pnl'], 2, 10)}{_f(r['media'], 3, 10)}  {r['veredicto']}")
    L.append("")

    # ---- salidas y cadena
    if inf.salidas:
        L.append("-- SALIDAS: ¿SE TOCA ANTES EL OBJETIVO O EL STOP? ----------------------------------")
        L.append(f"{'estrategia':22}{'n':>5}{'P(objetivo)':>13}{'P(stop)':>10}{'P(obj. antes)':>15}"
                 f"{'t obj.':>9}{'t stop':>9}  confianza")
        L.append("-" * 100)
        for r in inf.salidas:
            to = "-" if r["t_target_s"] is None else f"{r['t_target_s']:.0f} s"
            ts = "-" if r["t_stop_s"] is None else f"{r['t_stop_s']:.0f} s"
            L.append(f"{r['estrategia'][:22]:22}{r['n']:>5}{_p(r['p_target'], 13)}{_p(r['p_stop'], 10)}"
                     f"{_p(r['p_target_antes'], 15)}{to:>9}{ts:>9}  {r['nivel']}")
        L.append("")
    c = inf.cadena
    L.append("-- LA CADENA DE TIEMPOS ------------------------------------------------------------")
    L.append(f"  evento del partido → reacción del mercado : {_seg(c['evento_a_reaccion_s'])}  "
             f"(n={c['n_reacciones']})")
    L.append(f"  orden puesta       → llenada             : {_seg(c['orden_a_llenado_s'])}")
    L.append(f"  llenada            → primer tick a favor : {_seg(c['llenado_a_favorable_s'])}")
    L.append(f"  llenada            → salida              : {_seg(c['llenado_a_salida_s'])}")
    L.append(f"  retrasos separados: feed {_ms(c['retraso_feed_ms'])}, proceso {_ms(c['retraso_proceso_ms'])}, "
             f"decisión {_ms(c['retraso_decision_ms'])}, ejecución {_ms(c['retraso_ejecucion_ms'])}")
    L.append("")

    # ---- semáforo
    L.append("-- SEMÁFORO ------------------------------------------------------------------------")
    for e in inf.estados:
        L.append(f"{e.estrategia[:26]:26}{e.semaforo:28}n={e.n:<5}{e.nivel}")
        L.append(f"{'':26}{e.motivo}")
        if e.faltan:
            L.append(f"{'':26}para poder juzgarla falta: " + "; ".join(e.faltan))
        L.append("")
    L.append("Verde no significa que gane: significa que se ha demostrado que gana.")
    L.append("Naranja no significa que pierda: significa que la ejecución se come la ventaja.")
    L.append("Amarillo es la respuesta honesta la mayor parte del tiempo.")
    return "\n".join(L)


def _hms(ms: int) -> str:
    if ms < 1000:
        return f"{ms}ms"
    if ms < 60_000:
        return f"{ms // 1000}s"
    return f"{ms // 60_000}m"


def _seg(x: float | None) -> str:
    return "sin datos" if x is None else f"{x:.2f} s"


def _ms(x: float | None) -> str:
    return "sin datos" if x is None else f"{x:.0f} ms"
