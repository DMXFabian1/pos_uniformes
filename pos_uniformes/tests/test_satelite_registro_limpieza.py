"""Limpiar el registro de pantallas.

Daniel (02/10): «limpia las pantallas registradas viejas». El registro se
ensucia con el uso —una Mac donde se probó el kiosko una tarde, un equipo
retirado— y una lista con equipos que no existen no se puede leer de un vistazo,
que es justamente para lo que está.
"""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from pos_uniformes.database.connection import Base
from pos_uniformes.services import satelite_registry_service as rsvc


class _Base(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.s = Session(self.engine)
        self.addCleanup(self.s.close)
        self.ahora = datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc)

    def registrar(self, ident: str, nombre: str, *, hace_dias: float | None = 0) -> None:
        rsvc.registrar(self.s, ident, nombre)
        sat = next(x for x in rsvc.listar(self.s) if x.identificador == ident)
        sat.ultimo_visto = (
            None if hace_dias is None else self.ahora - timedelta(days=hace_dias)
        )
        self.s.flush()


class QuienSeVaTests(_Base):
    def test_una_pantalla_de_hoy_se_queda(self) -> None:
        self.registrar("s1", "Entrada", hace_dias=0)
        self.assertEqual(rsvc.retirar_viejos(self.s, ahora=self.ahora), [])

    def test_una_apagada_desde_la_semana_pasada_se_queda(self) -> None:
        # Apagada no es retirada: un kiosko en reparación vuelve.
        self.registrar("s2", "Caja 2", hace_dias=8)
        self.assertEqual(rsvc.retirar_viejos(self.s, ahora=self.ahora), [])

    def test_una_de_hace_un_mes_se_va(self) -> None:
        self.registrar("s9", "MacBook-Air-de-Daniel.local", hace_dias=45)
        self.assertEqual(
            rsvc.retirar_viejos(self.s, ahora=self.ahora), ["MacBook-Air-de-Daniel.local"]
        )
        self.assertEqual(rsvc.listar(self.s), [])

    def test_una_que_nunca_latio_se_va(self) -> None:
        self.registrar("s0", "Fantasma", hace_dias=None)
        self.assertEqual(rsvc.retirar_viejos(self.s, ahora=self.ahora), ["Fantasma"])

    def test_solo_se_lleva_las_viejas(self) -> None:
        self.registrar("s1", "Entrada", hace_dias=0)
        self.registrar("s2", "Caja 2", hace_dias=10)
        self.registrar("s9", "Mac vieja", hace_dias=60)
        quitadas = rsvc.retirar_viejos(self.s, ahora=self.ahora)
        self.assertEqual(quitadas, ["Mac vieja"])
        self.assertEqual(
            sorted(s.nombre for s in rsvc.listar(self.s)), ["Caja 2", "Entrada"]
        )

    def test_listar_viejos_no_borra_nada(self) -> None:
        # El diálogo las enseña antes de preguntar: mirar no puede ser destruir.
        self.registrar("s9", "Mac vieja", hace_dias=60)
        self.assertEqual(len(rsvc.listar_viejos(self.s, ahora=self.ahora)), 1)
        self.assertEqual(len(rsvc.listar(self.s)), 1)


class SeCuraSolaTests(_Base):
    def test_una_que_vuelve_se_registra_de_nuevo(self) -> None:
        # Esta es la razón por la que borrar es seguro.
        self.registrar("s9", "Caja 3", hace_dias=60)
        rsvc.retirar_viejos(self.s, ahora=self.ahora)
        self.assertEqual(rsvc.listar(self.s), [])
        rsvc.registrar(self.s, "s9", "Caja 3")        # la prenden
        self.s.flush()
        self.assertEqual([s.nombre for s in rsvc.listar(self.s)], ["Caja 3"])

    def test_un_registro_vacio_no_revienta(self) -> None:
        self.assertEqual(rsvc.retirar_viejos(self.s, ahora=self.ahora), [])


class EnganchadoTests(unittest.TestCase):
    def test_corre_en_cada_actualizacion_no_solo_al_subir_version(self) -> None:
        # El registro se ensucia con el uso, no con las versiones.
        from pathlib import Path

        codigo = (
            Path(__file__).resolve().parents[1] / "scripts" / "postactualizacion.py"
        ).read_text(encoding="utf-8")
        cuerpo = codigo[codigo.index("def aplicar("):codigo.index("def limpiar_registro_satelites")]
        self.assertIn("hechos.extend(limpiar_registro_satelites())", cuerpo)
        # Fuera del `if` de la versión: al mismo nivel que el return.
        self.assertIn("    hechos.extend(limpiar_registro_satelites())\n    return hechos", cuerpo)

    def test_si_la_base_no_contesta_la_actualizacion_sigue(self) -> None:
        from unittest.mock import patch

        from pos_uniformes.scripts import postactualizacion as post

        with patch(
            "pos_uniformes.database.connection.get_session",
            side_effect=RuntimeError("sin base"),
        ):
            hechos = post.limpiar_registro_satelites()
        self.assertTrue(any("no se pudo limpiar" in h for h in hechos))

    def test_el_dialogo_pregunta_antes_de_borrar(self) -> None:
        from pathlib import Path

        codigo = (
            Path(__file__).resolve().parents[1] / "ui" / "dialogs" / "satellite_admin_dialog.py"
        ).read_text(encoding="utf-8")
        self.assertIn("QMessageBox.question", codigo)
        self.assertIn("se vuelve a registrar sola", codigo)


if __name__ == "__main__":
    unittest.main()
