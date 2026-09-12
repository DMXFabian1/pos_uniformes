"""Persistencia en Parquet particionado por día + lectura con Polars/DuckDB.

Diseño: el recolector escribe archivos pequeños (buffer -> parquet) y cualquier
proceso puede leerlos en paralelo sin locks. `data/<tabla>/date=YYYY-MM-DD/*.parquet`.
"""
from __future__ import annotations

import json
import logging
import os
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import polars as pl
import pyarrow as pa
import pyarrow.parquet as pq

log = logging.getLogger(__name__)

S = pa.string
F = pa.float64
I = pa.int64
B = pa.bool_

SCHEMAS: dict[str, pa.Schema] = {
    "markets": pa.schema([
        ("ts_ms", I()), ("status", S()), ("condition_id", S()), ("gamma_id", S()), ("question", S()), ("slug", S()),
        ("event_id", S()), ("event_slug", S()), ("event_title", S()), ("category", S()), ("tokens", S()),
        ("neg_risk", B()), ("event_neg_risk", B()), ("tick_size", F()), ("min_order_size", F()),
        ("fee_rate", F()), ("fee_type", S()), ("volume_24h", F()), ("liquidity", F()), ("end_date", S()),
        ("accepting_orders", B()), ("sports_market_type", S()), ("game_start_time", S()), ("tags", S()),
        ("event_market_count", I()), ("event_neg_risk_augmented", B()),
        ("event_game_id", S()), ("event_start_time", S()),
    ]),
    "games": pa.schema([
        ("ts_ms", I()), ("game_id", S()), ("league", S()), ("sport", S()), ("home", S()), ("away", S()),
        ("status", S()), ("live", B()), ("ended", B()), ("score", S()), ("period", S()), ("elapsed", S()), ("raw", S()),
    ]),
    "crypto_prices": pa.schema([
        ("ts_ms", I()), ("symbol", S()), ("price", F()),
    ]),
    "updown_windows": pa.schema([
        ("ts_ms", I()), ("condition_id", S()), ("slug", S()), ("symbol", S()), ("window_s", I()),
        ("start_ms", I()), ("end_ms", I()), ("strike", F()), ("strike_ts_ms", I()),
        ("settle_price", F()), ("up_won", B()), ("status", S()),
    ]),
    "flow_trades": pa.schema([
        ("ts_ms", I()), ("wallet", S()), ("name", S()), ("pseudonym", S()), ("side", S()), ("size", F()),
        ("price", F()), ("usd", F()), ("token_id", S()), ("condition_id", S()), ("outcome", S()),
        ("outcome_index", I()), ("title", S()), ("slug", S()), ("event_slug", S()), ("tx_hash", S()),
    ]),
    "wallet_profiles": pa.schema([
        ("ts_ms", I()), ("wallet", S()), ("name", S()), ("n_closed", I()), ("wins", I()), ("losses", I()),
        ("total_bought", F()), ("realized_pnl", F()), ("roi", F()), ("win_rate", F()), ("win_rate_adj", F()),
        ("roi_adj", F()), ("score", F()), ("biggest_win", F()), ("biggest_loss", F()), ("n_open", I()),
        ("open_value", F()), ("open_pnl", F()), ("first_ts", I()), ("last_ts", I()), ("truncated", B()),
    ]),
    "wallet_closed": pa.schema([
        ("ts_ms", I()), ("wallet", S()), ("condition_id", S()), ("token_id", S()), ("outcome", S()), ("title", S()),
        ("event_slug", S()), ("avg_price", F()), ("total_bought", F()), ("realized_pnl", F()), ("cur_price", F()),
        ("end_date", S()), ("closed_ts", I()),
    ]),
    # ts_ms es el reloj del exchange; recv_ms el nuestro al recibirlo. La diferencia es la latencia del feed.
    "book_snapshots": pa.schema([
        ("ts_ms", I()), ("token_id", S()), ("condition_id", S()), ("bids", S()), ("asks", S()),
        ("hash", S()), ("source", S()), ("recv_ms", I()),
    ]),
    "book_deltas": pa.schema([
        ("ts_ms", I()), ("token_id", S()), ("condition_id", S()), ("side", S()), ("price", F()), ("size", F()),
        ("best_bid", F()), ("best_ask", F()), ("hash", S()), ("recv_ms", I()),
        ("delta_size", F()),      # cambio firmado del nivel: + puso, - quitó/llenaron (flujo de órdenes)
    ]),
    "trades": pa.schema([
        ("ts_ms", I()), ("token_id", S()), ("condition_id", S()), ("price", F()), ("size", F()), ("side", S()),
        ("fee_rate_bps", F()), ("tx_hash", S()), ("recv_ms", I()),
    ]),
    "quotes": pa.schema([
        ("ts_ms", I()), ("token_id", S()), ("condition_id", S()), ("best_bid", F()), ("best_ask", F()),
        ("bid_size", F()), ("ask_size", F()), ("mid", F()), ("spread", F()), ("bid_depth_5t", F()), ("ask_depth_5t", F()),
    ]),
    "resolutions": pa.schema([
        ("ts_ms", I()), ("condition_id", S()), ("token_id", S()), ("outcome", S()), ("winner", B()), ("final_price", F()),
    ]),
    "signals": pa.schema([
        ("ts_ms", I()), ("signal_id", S()), ("kind", S()), ("condition_id", S()), ("event_id", S()), ("legs", S()),
        ("size", F()), ("edge_gross", F()), ("fee_est", F()), ("edge_net", F()), ("confidence", F()),
        ("horizon", S()), ("meta", S()), ("run_id", S()),
    ]),
    "ledger": pa.schema([
        ("run_id", S()), ("mode", S()), ("signal_id", S()), ("kind", S()), ("condition_id", S()), ("event_id", S()),
        ("ts_signal", I()), ("ts_fill", I()), ("ts_exit", I()), ("status", S()), ("exit_reason", S()),
        ("size_target", F()), ("size_filled", F()), ("cost", F()), ("fees", F()), ("payout", F()),
        ("predicted_edge", F()), ("predicted_pnl", F()), ("realized_pnl", F()), ("error", F()),
        ("confidence", F()), ("meta", S()), ("conf_heuristic", F()), ("p_win_model", F()), ("model_version", I()),
        # ejecución: estrategia, rol de entrada y los tres escenarios de llenado de la orden maker
        ("strategy", S()), ("entry_role", S()), ("ts_placed", I()), ("hold_s", F()),
        ("fill_conservador", F()), ("fill_optimista", F()), ("queue_inicial", F()), ("vol_cruzado", F()),
        ("barrido", B()), ("causa_fill", S()), ("edge_taker", F()),
        # selección adversa: mid - precio de entrada a cada horizonte tras el primer fill (negativo = en contra)
        ("adverse_100ms", F()), ("adverse_500ms", F()), ("adverse_1s", F()), ("adverse_2s", F()),
        ("adverse_5s", F()), ("adverse_10s", F()), ("adverse_30s", F()), ("adverse_60s", F()),
        # qué versión del motor produjo esta fila, y con qué calidad de datos se decidió
        ("experiment", S()), ("freshness_ms", I()), ("feed_state", S()), ("contaminado", B()),
        # recorrido del precio tras el fill: lo mejor y lo peor que llegó a estar, y cuándo
        ("mfe", F()), ("mae", F()), ("t_mfe_ms", I()), ("t_mae_ms", I()),
        # cuánto tardó en moverse medio tick, uno, dos y tres, a favor y en contra
        ("t_fav_05t_ms", I()), ("t_fav_1t_ms", I()), ("t_fav_2t_ms", I()), ("t_fav_3t_ms", I()),
        ("t_adv_05t_ms", I()), ("t_adv_1t_ms", I()), ("t_adv_2t_ms", I()), ("t_adv_3t_ms", I()),
        # cuándo se tocó el objetivo y cuándo el stop (aunque la salida ocurriera por otra causa)
        ("t_target_ms", I()), ("t_stop_ms", I()), ("target_antes_que_stop", B()),
        # la cadena de retrasos, separada: feed, proceso, decisión y ejecución
        ("proc_delay_ms", I()), ("decision_delay_ms", I()), ("exec_delay_ms", I()),
        ("sombra", B()),        # posición hipotética: se rechazó y se sigue solo para medir
        ("motivo_rechazo", S()),
    ]),
    # trayectoria del precio tras cada llenado, un punto por horizonte. En formato largo para no
    # multiplicar columnas y para poder preguntar "¿dónde aparece la ventaja?" sin suposiciones.
    "post_fill": pa.schema([
        ("ts_ms", I()), ("run_id", S()), ("experiment", S()), ("signal_id", S()), ("strategy", S()),
        ("condition_id", S()), ("token_id", S()), ("horizonte_ms", I()), ("entrada", F()),
        ("mid", F()), ("best_bid", F()), ("best_ask", F()), ("delta", F()), ("delta_bid", F()),
        ("sombra", B()), ("contaminado", B()), ("feed_state", S()),
    ]),
    # una versión congelada del motor: mientras la huella no cambie, los datos son comparables
    "experiments": pa.schema([
        ("ts_ms", I()), ("experiment_id", S()), ("commit", S()), ("dirty", B()), ("huella", S()),
        ("umbrales", S()), ("modelos", S()), ("nota", S()),
    ]),
    # una fila por orden puesta: las condiciones del momento y si acabó llenándose. Es el conjunto
    # de datos con el que después se puede estimar P(fill | condiciones) sin suponer nada.
    "fill_observations": pa.schema([
        ("ts_ms", I()), ("run_id", S()), ("experiment", S()), ("signal_id", S()), ("strategy", S()),
        ("condition_id", S()), ("token_id", S()), ("precio", F()), ("size", F()),
        ("distancia_bid_ticks", F()), ("distancia_ask_ticks", F()), ("spread_ticks", F()),
        ("profundidad_propia", F()), ("profundidad_contraria", F()), ("cola_delante", F()),
        ("imbalance_1t", F()), ("imbalance_3t", F()), ("vel_1s", F()), ("vel_5s", F()), ("vol_60s", F()),
        ("trades_por_minuto", F()), ("freshness_ms", I()), ("feed_state", S()), ("hora_utc", I()),
        ("tau_partido", F()), ("seconds_left", F()), ("edge_net", F()),
        # resultado
        ("llenada", B()), ("fraccion_llenada", F()), ("espera_ms", I()), ("vol_cruzado", F()),
        ("barrido", B()), ("causa_fill", S()), ("llenada_conservador", B()), ("llenada_optimista", B()), ("sombra", B()),
    ]),
    # cada decisión del motor, incluidas las de NO operar: sin esto no se sabe si los filtros sobran o faltan
    "decisions": pa.schema([
        ("ts_ms", I()), ("run_id", S()), ("condition_id", S()), ("kind", S()), ("strategy", S()),
        ("decision", S()), ("motivo", S()), ("edge_net", F()), ("detalle", S()),
        ("experiment", S()), ("freshness_ms", I()), ("feed_state", S()), ("contaminado", B()),
        ("signal_id", S()),     # si la señal llegó a existir, enlaza con su posición sombra
    ]),
    # salud del feed a lo largo del tiempo: sin esto no se puede separar el dato bueno del sucio
    "feed_health": pa.schema([
        ("ts_ms", I()), ("run_id", S()), ("experiment", S()), ("estado", S()), ("freshness_ms", I()),
        ("min_ms", I()),
        ("p95_ms", I()), ("mensajes_por_segundo", F()), ("ultimo_mensaje_hace_ms", I()),
        ("libros_validos", I()), ("libros_totales", I()), ("reconexiones", I()),
        ("trade_feed_lag_s", I()), ("paginas_llenas", I()),
    ]),
    # Market Reaction Engine: cuánto tarda el precio en moverse tras un cambio en el partido
    "reactions": pa.schema([
        ("ts_ms", I()), ("game_id", S()), ("league", S()), ("condition_id", S()), ("token_id", S()),
        ("evento", S()), ("ts_evento", I()), ("mid_antes", F()), ("mid_despues", F()), ("lag_ms", I()),
        ("movimiento", F()), ("reacciono", B()), ("run_id", S()), ("experiment", S()),
    ]),
}


def day_str(ts_ms: int) -> str:
    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")


class ParquetWriter:
    """Buffer en memoria por tabla que se vuelca a Parquet por tiempo o por filas."""

    def __init__(self, data_dir: str | Path, flush_seconds: int = 30, flush_rows: int = 5000, subdir: str = ""):
        self.root = Path(data_dir)
        self.subdir = subdir
        self.flush_seconds = flush_seconds
        self.flush_rows = flush_rows
        self._buf: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._last_flush = time.time()
        self.rows_written: dict[str, int] = defaultdict(int)

    def append(self, table: str, row: dict[str, Any]) -> None:
        if table not in SCHEMAS:
            raise KeyError(f"tabla desconocida: {table}")
        self._buf[table].append(row)
        if len(self._buf[table]) >= self.flush_rows:
            self.flush(table)

    def maybe_flush(self) -> None:
        if time.time() - self._last_flush >= self.flush_seconds:
            self.flush()

    def flush(self, table: str | None = None) -> None:
        tables = [table] if table else list(self._buf)
        for t in tables:
            rows = self._buf.get(t)
            if not rows:
                continue
            self._buf[t] = []
            self._write(t, rows)
        self._last_flush = time.time()

    def _write(self, table: str, rows: list[dict[str, Any]]) -> None:
        schema = SCHEMAS[table]
        by_day: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for r in rows:
            by_day[day_str(int(r["ts_ms"] if "ts_ms" in r else r.get("ts_signal", 0)))].append(r)
        for day, drows in by_day.items():
            cols = {f.name: [r.get(f.name) for r in drows] for f in schema}
            tbl = pa.table(cols, schema=schema)
            d = self.root / table
            if self.subdir:
                d = d / self.subdir
            d = d / f"date={day}"
            d.mkdir(parents=True, exist_ok=True)
            fname = d / f"{int(time.time() * 1000)}_{os.getpid()}_{len(drows)}.parquet"
            pq.write_table(tbl, fname, compression="zstd")
            self.rows_written[table] += len(drows)

    def close(self) -> None:
        self.flush()


def scan(data_dir: str | Path, table: str, subdir: str = "") -> pl.LazyFrame | None:
    """LazyFrame sobre todos los parquet de una tabla. None si no hay datos."""
    d = Path(data_dir) / table
    if subdir:
        d = d / subdir
    files = sorted(d.rglob("*.parquet"))
    if not files:
        return None
    paths = [str(f) for f in files]
    schema = SCHEMAS.get(table)
    if schema is None:
        return pl.scan_parquet(paths)
    # el esquema puede crecer con el tiempo: archivos viejos sin columnas nuevas se rellenan con null
    pl_schema = pl.Schema({f.name: _PL_TYPES[str(f.type)] for f in schema})
    try:
        return pl.scan_parquet(paths, schema=pl_schema, missing_columns="insert", extra_columns="ignore")
    except TypeError:  # versiones de polars sin esos parámetros
        return pl.scan_parquet(paths)


_PL_TYPES = {"string": pl.String, "double": pl.Float64, "int64": pl.Int64, "bool": pl.Boolean}


def latest_profiles(data_dir: str | Path) -> pl.DataFrame | None:
    """Último perfil conocido de cada wallet."""
    lf = scan(data_dir, "wallet_profiles")
    if lf is None:
        return None
    return lf.sort("ts_ms").group_by("wallet").last().collect()


def latest_markets(data_dir: str | Path) -> pl.DataFrame | None:
    """Última fila conocida de cada mercado (tabla markets)."""
    lf = scan(data_dir, "markets")
    if lf is None:
        return None
    return (lf.sort("ts_ms").group_by("condition_id").last().collect())


def dumps(obj: Any) -> str:
    return json.dumps(obj, separators=(",", ":"), default=str)
