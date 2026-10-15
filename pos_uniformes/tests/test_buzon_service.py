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

    def test_el_separador_de_linea_de_qt_se_vuelve_salto_normal(self) -> None:
        m = bz.enviar(self.s, "uno\u2028dos", de="Entrada")
        self.assertEqual(m.texto, "uno\ndos")

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

    def test_un_chat_que_solo_tiene_lo_que_mande_yo_tambien_existe(self) -> None:
        bz.enviar(self.s, "hola", de="Entrada", para="Claude")
        self.assertEqual(bz.destinos(self.s, yo="Entrada"), ["Claude"])



class ConversacionTests(_Base):
    def test_un_chat_privado_trae_lo_de_ida_y_vuelta_y_nada_mas(self) -> None:
        bz.enviar(self.s, "script", de="Claude", para="Entrada")
        bz.enviar(self.s, "resultado", de="Entrada", para="Claude")
        bz.enviar(self.s, "a todas", de="Claude")
        bz.enviar(self.s, "otra cosa", de="Claude", para="Caja")
        textos = [m.texto for m in bz.conversacion(self.s, yo="Entrada", con="Claude")]
        self.assertEqual(textos, ["script", "resultado"])

    def test_el_grupo_son_los_que_van_a_todas(self) -> None:
        bz.enviar(self.s, "privado", de="Claude", para="Entrada")
        bz.enviar(self.s, "a todas", de="Claude")
        textos = [m.texto for m in bz.conversacion(self.s, yo="Entrada", con=bz.GRUPO)]
        self.assertEqual(textos, ["a todas"])

    def test_renombrar_se_lleva_el_historial(self) -> None:
        self.s.add(Satelite(identificador="a", nombre="DESKTOP-AT4V4QO"))
        bz.enviar(self.s, "hola", de="Claude", para="DESKTOP-AT4V4QO")
        bz.enviar(self.s, "respuesta", de="DESKTOP-AT4V4QO", para="Claude")
        self.assertEqual(bz.renombrar(self.s, "DESKTOP-AT4V4QO", "Entrada"), 2)
        textos = [m.texto for m in bz.conversacion(self.s, yo="Entrada", con="Claude")]
        self.assertEqual(textos, ["hola", "respuesta"])
        self.assertIn("Entrada", bz.destinos(self.s, yo="Claude"))

    def test_lo_que_parece_comando_va_en_letra_fija(self) -> None:
        self.assertTrue(bz.parece_codigo('Get-Content "$env:APPDATA"'))
        self.assertTrue(bz.parece_codigo("Total: 2\nVEND-4 venta"))
        self.assertFalse(bz.parece_codigo("Ya actualicé, revisen sus kioskos."))



class ValidarNombreTests(_Base):
    def test_limpia_espacios(self) -> None:
        self.assertEqual(bz.validar_nombre(self.s, "  Caja   dos "), "Caja dos")

    def test_reservados(self) -> None:
        for nombre in ("Claude", "CLAUDE", "Todas las PCs", "*", ""):
            with self.assertRaises(bz.NoSePuede):
                bz.validar_nombre(self.s, nombre)

    def test_el_mismo_nombre_de_otra_pc_no_pero_el_propio_si(self) -> None:
        self.s.add(Satelite(identificador="a", nombre="Entrada"))
        self.s.flush()
        with self.assertRaises(bz.NoSePuede):
            bz.validar_nombre(self.s, "entrada", identificador="b")
        self.assertEqual(bz.validar_nombre(self.s, "Entrada", identificador="a"), "Entrada")


class ElLatidoSeLlevaElHistorialTests(_Base):
    """Renombrar desde el menú admin (o sin red) también se lleva el chat."""

    def test_al_latir_con_otro_nombre_los_mensajes_se_van_con_la_pc(self) -> None:
        from unittest.mock import patch

        from pos_uniformes.services import satelite_registry_service as reg

        self.s.add(Satelite(identificador="a", nombre="DESKTOP-AT4V4QO"))
        bz.enviar(self.s, "hola", de="Claude", para="DESKTOP-AT4V4QO")
        bz.enviar(self.s, "resultado", de="DESKTOP-AT4V4QO", para="Claude")
        self.s.flush()
        with patch.object(reg, "es_de_desarrollo", return_value=False):
            reg.registrar(self.s, "a", "Entrada")
        textos = [m.texto for m in bz.conversacion(self.s, yo="Entrada", con="Claude")]
        self.assertEqual(textos, ["hola", "resultado"])

    def test_renombrar_esta_pc_no_toca_a_otra_que_se_llamaba_igual(self) -> None:
        self.s.add_all([Satelite(identificador="a", nombre="Kiosko"),
                        Satelite(identificador="b", nombre="Kiosko")])
        self.s.flush()
        bz.renombrar_esta_pc(self.s, "Entrada", viejo="Kiosko", identificador="a")
        nombres = {x.identificador: x.nombre for x in self.s.query(Satelite).all()}
        self.assertEqual(nombres, {"a": "Entrada", "b": "Kiosko"})


if __name__ == "__main__":
    unittest.main()
