"""Tests de la generación automática de órdenes de conteo (Fase 3)."""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

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
    TipoPieza,
    TipoTrabajo,
    Variante,
)
from pos_uniformes.services import trabajos_service as svc
from pos_uniformes.services.conteo_auto_orden_service import generar_ordenes_automaticas

_AHORA = datetime(2026, 7, 12, tzinfo=timezone.utc)
_SDD = "pos_uniformes.services.conteo_auto_orden_cache_service.satellite_data_dir"


def _seed(session: Session, nombre: str, *, dias_vigencia=30, ultimo_hace=None):
    e = Escuela(nombre=nombre)
    session.add(e)
    session.flush()
    session.add(ConfigConteoEscuela(escuela_id=e.id, dias_vigencia=dias_vigencia))
    cat = Categoria(nombre=f"C{nombre}")
    marca = Marca(nombre=f"M{nombre}")
    pieza = TipoPieza(nombre=f"Pz{nombre}")
    session.add_all([cat, marca, pieza])
    session.flush()
    prod = Producto(
        nombre=f"P{nombre}", nombre_base=f"P{nombre}",
        categoria_id=cat.id, marca_id=marca.id, escuela_id=e.id, tipo_pieza_id=pieza.id,
    )
    session.add(prod)
    session.flush()
    v = Variante(producto_id=prod.id, sku=f"S{nombre}", talla="12", color="AZUL",
                 precio_venta=100, stock_actual=5)
    session.add(v)
    session.flush()
    if ultimo_hace is not None:
        session.add(ConteoInventario(
            variante_id=v.id, escuela_id=e.id, stock_sistema=5, stock_fisico=5,
            diferencia=0, contado_por="t", contado_at=_AHORA - timedelta(days=ultimo_hace),
        ))
    session.flush()
    return e, v


class AutoOrdenTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.tmp = tempfile.TemporaryDirectory()
        self.patcher = patch(_SDD, return_value=Path(self.tmp.name))
        self.patcher.start()

    def tearDown(self) -> None:
        self.patcher.stop()
        self.tmp.cleanup()

    def _session(self) -> Session:
        return Session(self.engine)

    def test_encola_orden_para_escuela_vencida(self) -> None:
        s = self._session()
        _seed(s, "Vencida", ultimo_hace=60)
        _seed(s, "AlDia", ultimo_hace=1)
        s.commit()
        s.close()

        s = self._session()
        generadas = generar_ordenes_automaticas(s, ahora=_AHORA)
        s.close()
        self.assertEqual(generadas, ["Vencida"])

        s = self._session()
        conteos = svc.listar(s, tipos=[TipoTrabajo.CONTEO])
        self.assertEqual(len(conteos), 1)
        self.assertEqual(conteos[0].origen, "auto-conteo")
        s.close()

    def test_no_reimprime_el_mismo_ciclo(self) -> None:
        s = self._session()
        _seed(s, "Vencida", ultimo_hace=60)
        s.commit()
        s.close()

        # Primera corrida encola; la segunda no (candado).
        s = self._session()
        self.assertEqual(generar_ordenes_automaticas(s, ahora=_AHORA), ["Vencida"])
        s.close()
        s = self._session()
        self.assertEqual(generar_ordenes_automaticas(s, ahora=_AHORA), [])
        s.close()

        s = self._session()
        self.assertEqual(len(svc.listar(s, tipos=[TipoTrabajo.CONTEO])), 1)
        s.close()

    def test_reimprime_tras_nuevo_conteo(self) -> None:
        s = self._session()
        e, v = _seed(s, "Vencida", ultimo_hace=60)
        s.commit()
        vid = v.id
        eid = e.id
        s.close()

        s = self._session()
        self.assertEqual(generar_ordenes_automaticas(s, ahora=_AHORA), ["Vencida"])
        s.close()

        # Registrar un conteo reciente: la próxima fecha se recorre.
        s = self._session()
        s.add(ConteoInventario(
            variante_id=vid, escuela_id=eid, stock_sistema=5, stock_fisico=5,
            diferencia=0, contado_por="t", contado_at=_AHORA,
        ))
        s.commit()
        s.close()

        # 40 días después vuelve a estar vencida (vigencia 30) -> nueva orden.
        futuro = _AHORA + timedelta(days=40)
        s = self._session()
        self.assertEqual(generar_ordenes_automaticas(s, ahora=futuro), ["Vencida"])
        s.close()

        s = self._session()
        self.assertEqual(len(svc.listar(s, tipos=[TipoTrabajo.CONTEO])), 2)
        s.close()

    def test_sin_vencidas_no_hace_nada(self) -> None:
        s = self._session()
        _seed(s, "AlDia", ultimo_hace=1)
        s.commit()
        s.close()
        s = self._session()
        self.assertEqual(generar_ordenes_automaticas(s, ahora=_AHORA), [])
        s.close()


if __name__ == "__main__":
    unittest.main()
