"""Configuracion de engine, sesiones y metadata compartida."""

from __future__ import annotations

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
    """¿La PC principal sigue ahí? Si no, fallar al instante en vez de esperar.

    Daniel, 2026-11-25: «apago la PC principal antes y el kiosko
    inmediatamente se pone lento». Cada intento de conectar a un host
    apagado esperaba `connect_timeout` (2 s), una y otra vez, en el hilo de
    la pantalla, hasta que el watchdog (cada 5 min) pasaba a modo local.

    Primera versión (a6ea7b42): antes de cada uso se tocaba el puerto con un
    connect TCP de medio segundo. Al día siguiente el kiosko «perdía la
    conexión seguido»: su bitácora decía «no contesta» cada 30–60 s mientras
    una medición desde PowerShell, en el mismo kiosko y el mismo minuto,
    tenía 60 de 60 respuestas en 4 ms (2026-11-26). Dentro del programa el
    sondeo fallaba solo: el hilo no recuperaba el GIL a tiempo y su
    medio segundo vencía con la respuesta ya ahí. Ya no se sondea nada.

    Ahora solo cuentan los intentos de conexión DE VERDAD: con
    `FALLAS_PARA_CORTAR` seguidos fallidos se da por caída y, por
    `ESPERA_TRAS_CAIDA_SEG`, todo intento falla al instante (y el pre-ping no
    toca las conexiones guardadas). El primer intento que entra la levanta.
    """

    FALLAS_PARA_CORTAR = 2
    ESPERA_TRAS_CAIDA_SEG = 10.0

    def __init__(self, host: str, port: int, *, reloj=time.monotonic) -> None:
        self.host = host
        self.port = int(port)
        self._reloj = reloj
        self._lock = threading.Lock()
        self._caida_en: float | None = None
        self._fallas = 0

    def anotar_falla(self, motivo: object = None) -> None:
        with self._lock:
            self._fallas += 1
            corta = self._fallas >= self.FALLAS_PARA_CORTAR
            nueva = corta and self._caida_en is None
            if corta:
                self._caida_en = self._reloj()
        if nueva:
            import logging

            logging.getLogger(__name__).warning(
                "La PC principal (%s:%s) no contestó %d veces seguidas; %d s sin intentar. Último error: %s",
                self.host, self.port, self.FALLAS_PARA_CORTAR, int(self.ESPERA_TRAS_CAIDA_SEG), motivo,
            )

    def anotar_exito(self) -> None:
        with self._lock:
            self._fallas = 0
            self._caida_en = None

    def recien_caida(self) -> bool:
        """Se dio por caída hace poco: ni intentarlo (falla al instante)."""
        with self._lock:
            return self._caida_en is not None and self._reloj() - self._caida_en < self.ESPERA_TRAS_CAIDA_SEG


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
        # Ya se sabe que no contesta: no esperar a que el SELECT 1 de una
        # conexión guardada se dé por vencido. False = SQLAlchemy tira el pool
        # y la reconexión cae en el corte de abajo (al instante).
        if corte.recien_caida():
            return False
        return ping_original(dbapi_connection)

    dialecto.do_ping = do_ping  # type: ignore[method-assign]

    @event.listens_for(engine_pg, "do_connect")
    def _conectar(_dialect, _conn_rec, cargs, cparams):
        if corte.recien_caida():
            raise _base_no_contesta(corte)
        try:
            conexion = dialecto.connect(*cargs, **cparams)
        except dialecto.loaded_dbapi.OperationalError as exc:
            corte.anotar_falla(exc)
            raise
        corte.anotar_exito()
        return conexion

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
