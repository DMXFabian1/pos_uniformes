"""Configuracion de engine, sesiones y metadata compartida."""

from __future__ import annotations

import socket
import threading
import time

from sqlalchemy import MetaData, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy import create_engine

from pos_uniformes.utils.config import modo_pwa, settings

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def build_connect_args(statement_timeout_ms: int, solo_lectura: bool = False) -> dict:
    connect_args = {
        # 2s: en LAN el connect es <100ms; solo importa cuando el host está
        # apagado, y ahí acota cuánto puede bloquear un intento de conexión.
        "connect_timeout": 2,
        # TCP keepalives: mantienen viva la conexión inactiva y detectan
        # cortes de red rápido en vez de colgarse.
        "keepalives": 1,
        "keepalives_idle": 30,
        "keepalives_interval": 10,
        "keepalives_count": 3,
    }
    opciones = []
    if statement_timeout_ms > 0:
        # connect_timeout solo acota la fase TCP/auth; una query ya en vuelo
        # no tenía límite y podía congelar la UI hasta que los keepalives
        # mataran la conexión (~60s). Esto la acota del lado del servidor.
        opciones.append(f"-c statement_timeout={statement_timeout_ms}")
    if solo_lectura:
        # PWA de la casa (POS_PWA_MODO=casa): toda transacción nace de solo
        # lectura; un INSERT/UPDATE que se escape lo rechaza el propio Postgres.
        opciones.append("-c default_transaction_read_only=on")
    if opciones:
        connect_args["options"] = " ".join(opciones)
    return connect_args


class CorteDeBase:
    """¿La PC principal sigue ahí? Contestarlo rápido, sin esperar a Postgres.

    Daniel, 2026-11-25: «apago la PC principal antes y el kiosko
    inmediatamente se pone lento; me ha obligado a encenderla de nuevo o a
    cerrar el programa». Dos esperas se sumaban en cada toque:

    - Las conexiones que el pool ya tenía abiertas: el pre-ping (SELECT 1)
      se manda a un host apagado y nadie contesta. Windows tarda ~20 s en
      darse por vencido, una vez por cada conexión guardada. La simulación
      con un proxy mudo (2026-11-25) se quedó esperando las tres.
    - Cada conexión nueva: hasta `connect_timeout` (2 s), una y otra vez.

    Con esto, antes de reusar una conexión se toca el puerto con un connect
    TCP de medio segundo (en la LAN tarda milisegundos; no se recuerda el
    «sí»: la simulación apagó a los pocos segundos de una consulta buena y
    con el «sí» guardado el pre-ping volvía a esperar para siempre). Si
    no contesta, el pool se tira y por `ESPERA_TRAS_CAIDA_SEG` todo intento
    de conectar falla al instante, como si no hubiera red. Lo que ya sabía
    trabajar sin la PC principal (catálogo local, cola de la Libreta) lo
    hace sin que la empleada espere.
    """

    TIEMPO_SONDEO_SEG = 0.5
    ESPERA_TRAS_CAIDA_SEG = 15.0

    def __init__(self, host: str, port: int, *, reloj=time.monotonic, sondear=None) -> None:
        self.host = host
        self.port = int(port)
        self._reloj = reloj
        self._sondear = sondear or self._sondeo_tcp
        self._lock = threading.Lock()
        self._caida_en: float | None = None

    def _sondeo_tcp(self) -> bool:
        try:
            with socket.create_connection((self.host, self.port), timeout=self.TIEMPO_SONDEO_SEG):
                return True
        except OSError:
            return False

    def anotar_caida(self) -> None:
        with self._lock:
            self._caida_en = self._reloj()

    def recien_caida(self) -> bool:
        """Falló hace poco: ni intentarlo (falla al instante)."""
        with self._lock:
            return self._caida_en is not None and self._reloj() - self._caida_en < self.ESPERA_TRAS_CAIDA_SEG

    def host_contesta(self) -> bool:
        """Sondeo TCP corto. Si contesta, se olvida la caída."""
        if self._sondear():
            with self._lock:
                self._caida_en = None
            return True
        self.anotar_caida()
        return False


def _base_no_contesta(corte: CorteDeBase) -> Exception:
    import psycopg

    return psycopg.OperationalError(
        f"La PC principal ({corte.host}:{corte.port}) no contesta; se reintenta en unos segundos."
    )


def instalar_corte(engine_pg: Engine, corte: CorteDeBase) -> CorteDeBase:
    """Engancha el corte al engine: el pre-ping y cada conexión nueva."""
    dialecto = engine_pg.dialect
    ping_original = dialecto.do_ping

    def do_ping(dbapi_connection) -> bool:
        # False = conexión muerta: SQLAlchemy tira TODO el pool y reconecta,
        # y la reconexión cae en el corte de abajo (al instante).
        if not corte.host_contesta():
            return False
        return ping_original(dbapi_connection)

    dialecto.do_ping = do_ping  # type: ignore[method-assign]

    @event.listens_for(engine_pg, "do_connect")
    def _conectar(_dialect, _conn_rec, cargs, cparams):
        if corte.recien_caida() or not corte.host_contesta():
            raise _base_no_contesta(corte)
        try:
            return dialecto.connect(*cargs, **cparams)
        except dialecto.loaded_dbapi.OperationalError:
            corte.anotar_caida()
            raise

    engine_pg.corte_de_base = corte  # type: ignore[attr-defined]
    return corte


def crear_engine(url: str) -> Engine:
    if url.startswith("sqlite"):
        # Modo snapshot (servidor PWA de la casa): SQLite no entiende los
        # keepalives/timeouts de psycopg — engine simple.
        return create_engine(url, echo=settings.db_echo, future=True)
    nuevo = create_engine(
        url,
        echo=settings.db_echo,
        future=True,
        # pool_pre_ping: prueba la conexión (SELECT 1) antes de reutilizarla y
        # reconecta sola si murió — evita el "server closed the connection
        # unexpectedly" cuando la red LAN parpadea o Postgres se reinicia
        # (crítico en el satélite, que va por Wi-Fi a la PC principal).
        pool_pre_ping=True,
        pool_recycle=1800,  # recicla conexiones > 30 min (NAT/firewall las cortan)
        connect_args=build_connect_args(
            settings.db_statement_timeout_ms, solo_lectura=modo_pwa() == "casa"
        ),
    )
    from sqlalchemy.engine import make_url

    destino = make_url(url)
    instalar_corte(nuevo, CorteDeBase(destino.host or "localhost", destino.port or 5432))
    return nuevo


_DB_URL = settings.database_url
engine: Engine = crear_engine(_DB_URL)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
    class_=Session,
)


def get_session() -> Session:
    return SessionLocal()


def init_db() -> None:
    """Importa los modelos y crea las tablas iniciales."""
    import pos_uniformes.database.models  # noqa: F401

    Base.metadata.create_all(bind=engine)


def test_connection() -> bool:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return True
