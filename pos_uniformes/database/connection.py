"""Configuracion de engine, sesiones y metadata compartida."""

from __future__ import annotations

from sqlalchemy import MetaData, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy import create_engine

from pos_uniformes.utils.config import settings

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def build_connect_args(statement_timeout_ms: int) -> dict:
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
    if statement_timeout_ms > 0:
        # connect_timeout solo acota la fase TCP/auth; una query ya en vuelo
        # no tenía límite y podía congelar la UI hasta que los keepalives
        # mataran la conexión (~60s). Esto la acota del lado del servidor.
        connect_args["options"] = f"-c statement_timeout={statement_timeout_ms}"
    return connect_args


engine: Engine = create_engine(
    settings.database_url,
    echo=settings.db_echo,
    future=True,
    # pool_pre_ping: prueba la conexión (SELECT 1) antes de reutilizarla y
    # reconecta sola si murió — evita el "server closed the connection
    # unexpectedly" cuando la red LAN parpadea o Postgres se reinicia
    # (crítico en el satélite, que va por Wi-Fi a la PC principal).
    pool_pre_ping=True,
    pool_recycle=1800,  # recicla conexiones > 30 min (NAT/firewall las cortan)
    connect_args=build_connect_args(settings.db_statement_timeout_ms),
)

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
