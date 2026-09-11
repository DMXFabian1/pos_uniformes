"""Carga y validación de config.yaml."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class CategoryCfg(BaseModel):
    tag_id: int
    default_fee_rate: float = 0.0


class DiscoveryCfg(BaseModel):
    refresh_seconds: int = 300
    events_per_category: int = 300
    min_volume_24h: float = 2000
    max_markets: int = 400
    exclude_sports_market_types: list[str] = Field(default_factory=list)
    only_market_types: list[str] = Field(default_factory=list)   # vacío = todos; "" = mercados sin tipo (futuros)


class CollectorCfg(BaseModel):
    gamma_url: str = "https://gamma-api.polymarket.com"
    clob_url: str = "https://clob.polymarket.com"
    ws_url: str = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
    assets_per_connection: int = 150
    flush_seconds: int = 30
    flush_rows: int = 5000
    quote_sample_seconds: int = 5
    rest_resync_seconds: int = 900
    resolution_poll_seconds: int = 600
    prevent_sleep: bool = True    # Windows/macOS: impedir que el equipo se suspenda mientras corre


class SportsFeedCfg(BaseModel):
    enabled: bool = True
    ws_url: str = "wss://sports-api.polymarket.com/ws"
    store_all_leagues: bool = False   # False: solo partidos enlazados a mercados seguidos


class FlowCfg(BaseModel):
    enabled: bool = True
    data_api_url: str = "https://data-api.polymarket.com"
    poll_seconds: float = 10
    page_size: int = 2000             # máximo que acepta data-api; con 1000 se perdían trades
    min_usd_global: float = 500       # trades fuera de los mercados seguidos se guardan si superan esto
    whale_min_usd: float = 2000       # a partir de aquí se perfila la wallet
    profile_max_pages: int = 10       # 50 posiciones cerradas por página
    profile_refresh_hours: float = 12
    per_wallet_delay_seconds: float = 1.5
    smart_min_score: float = 0.65
    smart_min_closed: int = 20
    # data-api va 2-3 min por detrás en condiciones normales; más que esto es que se detuvo
    stale_warn_seconds: int = 420


class ComplementCfg(BaseModel):
    enabled: bool = True


class MultiOutcomeCfg(BaseModel):
    enabled: bool = True
    max_legs: int = 12


class SpreadCfg(BaseModel):
    enabled: bool = True
    min_spread_ticks: int = 3
    max_spread_ticks: int = 8         # más ancho que esto no es oportunidad, es falta de liquidez
    min_trades_per_minute: float = 0.3
    trade_window_seconds: int = 300
    vol_window_seconds: int = 300


class ModelDeviationCfg(BaseModel):
    enabled: bool = True
    min_edge_net: float = 0.02
    min_deviation: float = 0.04
    max_deviation: float = 0.35
    stop_fraction: float = 1.5
    min_tau: float = 0.02
    require_pregame: bool = False


class SmartMoneyCfg(BaseModel):
    enabled: bool = True
    min_edge_net: float = 0.01
    min_score: float = 0.65
    min_closed: int = 20
    min_usd: float = 1000
    max_chase_ticks: int = 3
    edge_fraction_of_roi: float = 0.5
    max_price: float = 0.9


class ModelsCfg(BaseModel):
    sigma_basketball: float = 16.2   # calibrado con NBA 2023-24 (1230 partidos)
    sigma_by_league: dict[str, float] = Field(default_factory=dict)
    soccer_total_goals: float = 2.7
    pregame_proxy_max_progress: float = 0.15   # si el partido ya avanzó más que esto sin precio previo, no se modela


class UpDownCfg(BaseModel):
    """Mercados "Up or Down" de cripto: viven 5 o 15 minutos y se resuelven contra el precio real."""
    enabled: bool = True
    tag_id: int = 102127                     # tag "Up or Down"
    series: list[str] = Field(default_factory=lambda: ["btc-up-or-down-5m", "btc-up-or-down-15m"])
    refresh_seconds: float = 20              # viven minutos: hay que descubrirlos rápido
    max_markets: int = 12
    ws_url: str = "wss://ws-live-data.polymarket.com"
    price_sample_seconds: float = 1.0        # muestreo que se guarda en disco
    strike_tolerance_seconds: float = 10     # margen tras la apertura para tomar el strike
    min_seconds_left: float = 45             # no entrar en el tramo final
    min_edge_net: float = 0.03               # el fee de cripto es 7 %: hace falta ventaja grande
    max_edge_net: float = 0.45               # más que esto suele ser un strike mal leído
    annual_vol: dict[str, float] = Field(default_factory=dict)   # p.ej. {btc: 0.48}
    default_annual_vol: float = 0.6


class SaludCfg(BaseModel):
    """Umbrales que definen cuándo el feed deja de servir. Son hipótesis: se miden y se revisan."""
    sano_ms: int = 1000
    degradado_ms: int = 5000
    sin_mensajes_viejo_s: float = 15
    sin_mensajes_congelado_s: float = 60
    registro_segundos: float = 15        # cada cuánto se guarda una fila de salud del feed
    # El retraso se mide sobre los mensajes de los últimos segundos, no sobre los últimos N
    # mensajes: el feed llega a ráfagas y un recuento fijo mezcla lo viejo con lo recién llegado.
    ventana_latencia_s: float = 5.0
    minimo_muestras: int = 20            # si en la ventana hay menos, se usan las últimas de todas


class ValidacionCfg(BaseModel):
    """Cuánto se sigue el precio después de un fill. Solo mide: no cambia ninguna decisión."""
    seguimiento_s: float = 900          # hasta dónde se sigue la trayectoria (el time stop actual)
    ledger_horizonte_s: float = 60      # MAE/MFE del ledger: la ventana de scalping que importa
    horizontes_ms: list[int] = Field(default_factory=lambda: [
        100, 500, 1_000, 2_000, 5_000, 10_000, 30_000, 60_000, 120_000, 300_000, 600_000, 900_000])
    ticks_movimiento: list[float] = Field(default_factory=lambda: [0.5, 1.0, 2.0, 3.0])
    sombras: bool = True                # seguir las señales rechazadas para saber qué nos perdimos
    max_sombras: int = 60


class RetentionCfg(BaseModel):
    enabled: bool = True
    run_hours: float = 24            # cada cuánto corre dentro del recolector
    compact: bool = True             # un archivo por tabla y día en días ya cerrados
    min_quiet_seconds: int = 3600    # no tocar particiones con escrituras recientes
    keep_days: dict[str, int] = Field(default_factory=lambda: {"book_deltas": 3, "book_snapshots": 14, "markets": 30,
                                                               "decisions": 30})
    # tablas sin entrada en keep_days se conservan para siempre (quotes, trades, games, flow, wallets, ledger…)


class LearnCfg(BaseModel):
    enabled: bool = True            # usar el modelo promovido para puntuar señales
    backend: str = "auto"           # auto | hgb | logistic
    shrink_n: int = 50              # peso del modelo = n_train / (n_train + shrink_n)
    min_train: int = 30             # por debajo, el modelo no filtra ni dimensiona
    min_p_win: float = 0.5          # con modelo confiable, señales por debajo se descartan
    size_floor: float = 0.2
    min_examples: int = 40
    val_fraction: float = 0.3
    retrain_hours: float = 6        # en paper: reentrenar y recargar cada tanto


class SignalsCfg(BaseModel):
    # Poner órdenes en vez de cruzarlas: la comisión solo la paga quien cruza el libro.
    maker_first: bool = True
    maker_entry_timeout_s: float = 90     # si la orden no se llena en este tiempo, se cancela
    min_edge_net: float = 0.004
    max_edge_net: float = 0.25          # más que esto casi siempre es un dato roto, no una oportunidad
    target_size: float = 50
    detect_interval_ms: int = 250
    complement: ComplementCfg = Field(default_factory=ComplementCfg)
    multi_outcome: MultiOutcomeCfg = Field(default_factory=MultiOutcomeCfg)
    spread: SpreadCfg = Field(default_factory=SpreadCfg)
    model_deviation: ModelDeviationCfg = Field(default_factory=ModelDeviationCfg)
    smart_money: SmartMoneyCfg = Field(default_factory=SmartMoneyCfg)


class SimCfg(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    latency_ms: int = 400
    slippage_ticks: int = 1
    # El 60 % es solo una REFERENCIA para comparar con la tasa de llenado observada. No decide
    # ningún fill: las órdenes maker se llenan por cola (ver sim/fill_model.py).
    fill_baseline_prob: float = Field(0.6, validation_alias=AliasChoices("fill_baseline_prob", "maker_fill_prob"))
    max_hold_seconds: int = 600
    time_stop_directional_seconds: int = 900       # scalping: si no convergió en 15 min, fuera
    max_hold_directional_seconds: int = 4 * 3600   # tope duro por si el time stop no puede ejecutarse (sin libro)
    max_entry_slip_ticks: int = 3
    start_cash: float = 1000
    max_position_usd: float = 60
    max_market_exposure_usd: float = 120           # suma de colateral abierto en el mismo mercado
    max_game_exposure_usd: float = 180             # suma en mercados del mismo partido/evento
    max_open_positions: int = 15
    adverse_horizons_ms: list[int] = Field(default_factory=lambda: [100, 500, 1000, 2000, 5000, 10000,
                                                                   30000, 60000])
    seed: int = 7


class Config(BaseModel):
    data_dir: str = "data"
    categories: dict[str, CategoryCfg]
    discovery: DiscoveryCfg = Field(default_factory=DiscoveryCfg)
    collector: CollectorCfg = Field(default_factory=CollectorCfg)
    sports_feed: SportsFeedCfg = Field(default_factory=SportsFeedCfg)
    flow: FlowCfg = Field(default_factory=FlowCfg)
    models: ModelsCfg = Field(default_factory=ModelsCfg)
    learn: LearnCfg = Field(default_factory=LearnCfg)
    retention: RetentionCfg = Field(default_factory=RetentionCfg)
    salud: SaludCfg = Field(default_factory=SaludCfg)
    validacion: ValidacionCfg = Field(default_factory=ValidacionCfg)
    updown: UpDownCfg = Field(default_factory=UpDownCfg)
    signals: SignalsCfg = Field(default_factory=SignalsCfg)
    sim: SimCfg = Field(default_factory=SimCfg)

    @property
    def data_path(self) -> Path:
        return Path(self.data_dir)


def load_config(path: str | Path = "config.yaml") -> Config:
    raw: dict[str, Any] = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return Config.model_validate(raw)
