"""Tests del calendario de conteos periódicos (Fase 0)."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import (
    Categoria,
    ConfigConteoEscuela,
    ConteoInventario,
    Escuela,
    Marca,
    Producto,
    Variante,
)
from pos_uniformes.services.conteo_calendario_service import (
    escuelas_con_conteo_vencido,
    obtener_calendario_conteo,
)

_AHORA = datetime(2026, 7, 12, 12, 0, tzinfo=timezone.utc)


def _make_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def _seed_escuela(
    session: Session,
    nombre: str,
    *,
    con_productos: bool = True,
    dias_vigencia: int | None = None,
    ultimo_conteo_hace_dias: int | None = None,
) -> Escuela:
    escuela = Escuela(nombre=nombre)
    session.add(escuela)
    session.flush()
    if dias_vigencia is not None:
        session.add(ConfigConteoEscuela(escuela_id=escuela.id, dias_vigencia=dias_vigencia))
    if con_productos:
        cat = Categoria(nombre=f"Cat {nombre}")
        marca = Marca(nombre=f"Marca {nombre}")
        session.add_all([cat, marca])
        session.flush()
        prod = Producto(
            nombre=f"Prod {nombre}",
            nombre_base=f"Prod {nombre}",
            categoria_id=cat.id,
            marca_id=marca.id,
            escuela_id=escuela.id,
        )
        session.add(prod)
        session.flush()
        variante = Variante(
            producto_id=prod.id,
            sku=f"SKU-{nombre}",
            talla="12",
            color="AZUL",
            precio_venta=100,
            stock_actual=5,
        )
        session.add(variante)
        session.flush()
        if ultimo_conteo_hace_dias is not None:
            fecha = _AHORA - timedelta(days=ultimo_conteo_hace_dias)
            session.add(
                ConteoInventario(
                    variante_id=variante.id,
                    escuela_id=escuela.id,
                    stock_sistema=5,
                    stock_fisico=5,
                    diferencia=0,
                    contado_por="test",
                    contado_at=fecha,
                )
            )
    session.flush()
    return escuela


class CalendarioConteoTests(unittest.TestCase):
    def setUp(self) -> None:
        self.session = _make_session()

    def tearDown(self) -> None:
        self.session.close()

    def _de(self, nombre: str):
        cal = obtener_calendario_conteo(self.session, ahora=_AHORA)
        return next(e for e in cal if e.escuela_nombre == nombre)

    def test_nunca_contada_esta_vencida(self) -> None:
        _seed_escuela(self.session, "Nueva", dias_vigencia=30)  # sin conteos
        e = self._de("Nueva")
        self.assertTrue(e.nunca_contada)
        self.assertTrue(e.vencida)
        self.assertIsNone(e.proxima_fecha)
        self.assertIsNone(e.dias_para_vencer)

    def test_contada_reciente_no_vencida(self) -> None:
        _seed_escuela(self.session, "Fresca", dias_vigencia=30, ultimo_conteo_hace_dias=5)
        e = self._de("Fresca")
        self.assertFalse(e.vencida)
        self.assertFalse(e.nunca_contada)
        self.assertEqual(e.dias_para_vencer, 25)  # 30 - 5
        self.assertEqual(e.proxima_fecha, (_AHORA + timedelta(days=25)).date())

    def test_contada_hace_mucho_esta_vencida(self) -> None:
        _seed_escuela(self.session, "Vieja", dias_vigencia=30, ultimo_conteo_hace_dias=45)
        e = self._de("Vieja")
        self.assertTrue(e.vencida)
        self.assertFalse(e.nunca_contada)
        self.assertLessEqual(e.dias_para_vencer, 0)  # 30 - 45 = -15

    def test_usa_dias_vigencia_default_sin_config(self) -> None:
        # Sin ConfigConteoEscuela -> DIAS_VIGENCIA_DEFAULT (90). Contada hace 40 -> vigente.
        _seed_escuela(self.session, "SinConfig", ultimo_conteo_hace_dias=40)
        e = self._de("SinConfig")
        self.assertEqual(e.dias_vigencia, 90)
        self.assertFalse(e.vencida)
        self.assertEqual(e.dias_para_vencer, 50)

    def test_escuela_sin_productos_se_excluye(self) -> None:
        _seed_escuela(self.session, "Vacia", con_productos=False)
        _seed_escuela(self.session, "ConProd", dias_vigencia=30)
        nombres = [e.escuela_nombre for e in obtener_calendario_conteo(self.session, ahora=_AHORA)]
        self.assertIn("ConProd", nombres)
        self.assertNotIn("Vacia", nombres)

    def test_escuela_sin_productos_se_incluye_si_se_pide(self) -> None:
        _seed_escuela(self.session, "Vacia", con_productos=False)
        cal = obtener_calendario_conteo(self.session, ahora=_AHORA, solo_con_productos=False)
        self.assertIn("Vacia", [e.escuela_nombre for e in cal])

    def test_escuelas_vencidas_filtra(self) -> None:
        _seed_escuela(self.session, "AlDia", dias_vigencia=30, ultimo_conteo_hace_dias=1)
        _seed_escuela(self.session, "Atrasada", dias_vigencia=30, ultimo_conteo_hace_dias=60)
        _seed_escuela(self.session, "Nunca", dias_vigencia=30)
        vencidas = {e.escuela_nombre for e in escuelas_con_conteo_vencido(self.session, ahora=_AHORA)}
        self.assertEqual(vencidas, {"Atrasada", "Nunca"})

    def test_orden_por_urgencia(self) -> None:
        _seed_escuela(self.session, "AlDia", dias_vigencia=30, ultimo_conteo_hace_dias=1)
        _seed_escuela(self.session, "Atrasada", dias_vigencia=30, ultimo_conteo_hace_dias=60)
        _seed_escuela(self.session, "Nunca", dias_vigencia=30)
        cal = obtener_calendario_conteo(self.session, ahora=_AHORA)
        # Las vencidas van primero; "AlDia" (no vencida) al final.
        self.assertTrue(cal[0].vencida)
        self.assertEqual(cal[-1].escuela_nombre, "AlDia")


if __name__ == "__main__":
    unittest.main()
