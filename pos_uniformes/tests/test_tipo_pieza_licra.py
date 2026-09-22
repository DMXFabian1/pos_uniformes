"""La Licra tiene su tipo de pieza: sin él, el mapa de conteos le hacía un
mosaico "Sin tipo" (Daniel, 2026-09-22)."""

from __future__ import annotations

import unittest

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import Categoria, Marca, Producto, TipoPieza


def _aplicar(session) -> None:
    """Lo mismo que la migración 5a6b7c8d9e0f, en SQL que sqlite entiende."""
    tipo = session.scalar(select(TipoPieza).where(TipoPieza.nombre == "Licra"))
    if tipo is None:
        tipo = TipoPieza(nombre="Licra")
        session.add(tipo)
        session.flush()
    session.execute(
        text("UPDATE producto SET tipo_pieza_id = :t WHERE tipo_pieza_id IS NULL AND lower(nombre) LIKE 'licra%'"),
        {"t": tipo.id},
    )
    session.flush()


class LicraTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.s = Session(engine)
        cat = Categoria(nombre="Básicos"); marca = Marca(nombre="G")
        self.s.add_all([cat, marca]); self.s.flush()
        self.licra = Producto(nombre="Licra", nombre_base="Licra", categoria_id=cat.id, marca_id=marca.id)
        self.otro = Producto(nombre="Mandil", nombre_base="Mandil", categoria_id=cat.id, marca_id=marca.id)
        self.s.add_all([self.licra, self.otro]); self.s.commit()

    def test_le_pone_su_tipo_y_no_toca_a_los_demas(self) -> None:
        _aplicar(self.s); self.s.commit()
        self.s.refresh(self.licra); self.s.refresh(self.otro)
        self.assertEqual(self.licra.tipo_pieza.nombre, "Licra")
        self.assertIsNone(self.otro.tipo_pieza_id)   # lo que no es licra sigue igual

    def test_correrla_dos_veces_no_duplica_el_tipo(self) -> None:
        _aplicar(self.s); _aplicar(self.s); self.s.commit()
        self.assertEqual(len(self.s.scalars(select(TipoPieza).where(TipoPieza.nombre == "Licra")).all()), 1)

    def test_va_junto_a_la_malla_en_la_hoja_y_en_el_tarifario(self) -> None:
        from pos_uniformes.services.conteo_service import _PIEZA_ORDER as hoja
        from pos_uniformes.services.school_tariff_service import _PIEZA_ORDER as tarifario

        for orden in (hoja, tarifario):
            self.assertIn("Licra", orden)
            self.assertEqual(orden["Licra"], orden["Malla"])
