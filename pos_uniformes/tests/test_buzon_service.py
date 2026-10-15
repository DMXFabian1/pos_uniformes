"""Buzón entre las PCs: lo que se manda en una se lee en la otra."""

from __future__ import annotations

import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import Satelite
from pos_uniformes.services import buzon_service as bz


class _Base(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.s = Session(engine)


class EnviarTests(_Base):
    def test_lo_que_se_manda_queda_tal_cual(self) -> None:
        # Un comando de PowerShell no se toca: comillas, sangría y saltos.
        texto = 'Get-ChildItem "$env:APPDATA"\n    | Select-Object Name\n'
        m = bz.enviar(self.s, texto, de="PC principal", para="Entrada")
        self.assertEqual(m.texto, texto.rstrip())
        self.assertEqual((m.de, m.para), ("PC principal", "Entrada"))

    def test_sin_destino_es_para_todas(self) -> None:
        self.assertIsNone(bz.enviar(self.s, "hola", de="Entrada", para="  ").para)

    def test_vacio_no_se_manda(self) -> None:
        with self.assertRaises(bz.NoSePuede):
            bz.enviar(self.s, "   \n ", de="Entrada")

    def test_lo_demasiado_largo_se_dice(self) -> None:
        with self.assertRaises(bz.NoSePuede):
            bz.enviar(self.s, "x" * (bz.MAXIMO_CARACTERES + 1), de="Entrada")


class RecientesTests(_Base):
    def test_cada_pc_ve_lo_suyo_lo_de_todas_y_lo_que_mando(self) -> None:
        bz.enviar(self.s, "a todas", de="Claude")
        bz.enviar(self.s, "para entrada", de="Claude", para="Entrada")
        bz.enviar(self.s, "para caja", de="Claude", para="Caja")
        bz.enviar(self.s, "respuesta", de="Entrada", para="Claude")
        vistos = [m.texto for m in bz.recientes(self.s, yo="Entrada")]
        self.assertEqual(vistos, ["a todas", "para entrada", "respuesta"])

    def test_el_mas_nuevo_va_hasta_abajo_como_en_un_chat(self) -> None:
        for i in range(5):
            bz.enviar(self.s, f"m{i}", de="Claude")
        self.assertEqual([m.texto for m in bz.recientes(self.s, limite=3)], ["m2", "m3", "m4"])


class DestinosTests(_Base):
    def test_las_pcs_conocidas_menos_esta(self) -> None:
        self.s.add_all([Satelite(identificador="a", nombre="Entrada"),
                        Satelite(identificador="b", nombre="Caja")])
        self.s.flush()
        bz.enviar(self.s, "hola", de="Claude")
        self.assertEqual(bz.destinos(self.s, yo="Entrada"), ["Caja", "Claude"])


if __name__ == "__main__":
    unittest.main()
