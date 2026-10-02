"""¿Hay respaldo de hoy, y sirve?

Todo con carpetas temporales: nada toca la carpeta de respaldos de la máquina.
Lo que se cuida es que el silencio NO se vea igual que el éxito, que era el
hueco: un respaldo que nadie dispara no falla, y por eso no avisaba.
"""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from pos_uniformes.services import respaldo_estado_service as est


def _dump(carpeta: Path, *, nombre="pos_20261001.dump", kb=700, dias=0) -> Path:
    archivo = carpeta / nombre
    archivo.write_bytes(b"x" * (kb * 1024))
    if dias:
        viejo = (datetime.now() - timedelta(days=dias)).timestamp()
        import os

        os.utime(archivo, (viejo, viejo))
    return archivo


class LeerEstadoTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.carpeta = Path(self._tmp.name)

    def test_carpeta_vacia_es_sin_respaldo(self) -> None:
        estado = est.leer_estado(self.carpeta)
        self.assertIsNone(estado.ultimo)
        self.assertIsNone(estado.dias)
        self.assertFalse(estado.al_dia)

    def test_uno_de_hoy_esta_al_dia(self) -> None:
        _dump(self.carpeta)
        estado = est.leer_estado(self.carpeta)
        self.assertEqual(estado.dias, 0)
        self.assertTrue(estado.al_dia)

    def test_uno_de_hace_tres_dias_no_esta_al_dia(self) -> None:
        _dump(self.carpeta, dias=3)
        estado = est.leer_estado(self.carpeta)
        self.assertEqual(estado.dias, 3)
        self.assertFalse(estado.al_dia)

    def test_de_ayer_todavia_pasa(self) -> None:
        # Un domingo cerrado no debe soltar un aviso.
        _dump(self.carpeta, dias=1)
        self.assertTrue(est.leer_estado(self.carpeta).al_dia)

    def test_toma_el_mas_reciente(self) -> None:
        _dump(self.carpeta, nombre="viejo.dump", dias=9)
        _dump(self.carpeta, nombre="nuevo.dump", dias=0)
        estado = est.leer_estado(self.carpeta)
        self.assertEqual(estado.dias, 0)
        self.assertEqual(estado.archivo.name, "nuevo.dump")

    def test_un_dump_de_cero_bytes_no_es_un_respaldo(self) -> None:
        # pg_dump puede "salir bien" y escribir nada. Para el programa es un
        # éxito; para la tienda es no tener respaldo.
        _dump(self.carpeta, kb=0)
        estado = est.leer_estado(self.carpeta)
        self.assertTrue(estado.sospechoso)
        self.assertFalse(estado.al_dia)

    def test_un_dump_diminuto_tampoco(self) -> None:
        _dump(self.carpeta, kb=2)
        self.assertTrue(est.leer_estado(self.carpeta).sospechoso)

    def test_uno_creible_no_es_sospechoso(self) -> None:
        _dump(self.carpeta, kb=700)
        self.assertFalse(est.leer_estado(self.carpeta).sospechoso)

    def test_la_hora_del_archivo_es_local_no_utc(self) -> None:
        # Tomar la hora local por UTC daba un respaldo "del futuro" y lo daba
        # por bueno seis horas de más.
        _dump(self.carpeta)
        self.assertEqual(est.leer_estado(self.carpeta).dias, 0)

    def test_una_carpeta_que_no_existe_no_revienta(self) -> None:
        estado = est.leer_estado(self.carpeta / "no-existe")
        self.assertIsNone(estado.ultimo)


class TextosTests(unittest.TestCase):
    def test_sin_ninguno_dice_lo_que_se_pierde(self) -> None:
        texto = est.texto_sin_respaldo(est.EstadoRespaldo(ultimo=None, archivo=None))
        self.assertIn("TODO", texto)
        self.assertIn("respaldo_diario.bat", texto)

    def test_viejo_dice_cuantos_dias_de_trabajo(self) -> None:
        estado = est.EstadoRespaldo(
            ultimo=datetime.now(timezone.utc) - timedelta(days=5), archivo=None
        )
        texto = est.texto_sin_respaldo(estado)
        self.assertIn("5 días", texto)

    def test_uno_dice_ayer_y_no_1_dias(self) -> None:
        estado = est.EstadoRespaldo(
            ultimo=datetime.now(timezone.utc) - timedelta(days=1, hours=2), archivo=None
        )
        self.assertIn("ayer", est.texto_sin_respaldo(estado))

    def test_el_sospechoso_dice_cuanto_pesa(self) -> None:
        estado = est.EstadoRespaldo(
            ultimo=datetime.now(timezone.utc), archivo=Path("x.dump"), tamano=1024
        )
        texto = est.texto_sin_respaldo(estado)
        self.assertIn("1 KB", texto)
        self.assertIn("no se puede restaurar", texto)

    def test_el_error_del_ultimo_intento_sale_en_el_aviso(self) -> None:
        estado = est.EstadoRespaldo(
            ultimo=datetime.now(timezone.utc) - timedelta(days=4),
            archivo=None,
            error="pg_dump no encontrado",
        )
        self.assertIn("pg_dump no encontrado", est.texto_sin_respaldo(estado))

    def test_resumen_de_una_linea(self) -> None:
        hoy = est.EstadoRespaldo(ultimo=datetime.now(timezone.utc), archivo=None)
        self.assertIn("hoy", est.texto_resumen(hoy))
        self.assertIn("✅", est.texto_resumen(hoy))
        nunca = est.EstadoRespaldo(ultimo=None, archivo=None)
        self.assertIn("ninguno", est.texto_resumen(nunca))

    def test_el_resumen_dice_si_la_copia_aparte_fallo(self) -> None:
        estado = est.EstadoRespaldo(
            ultimo=datetime.now(timezone.utc), archivo=None,
            copia_externa=Path("D:/respaldos"), error_externa="disco lleno",
        )
        self.assertIn("la copia aparte falló", est.texto_resumen(estado))


class VigilanteTests(unittest.TestCase):
    """El bot lo nota desde fuera, aunque la tarea nunca haya corrido."""

    def setUp(self) -> None:
        from pos_uniformes.services import alertas_service as al

        self.al = al
        self.v = al.Vigilante(ultimo_id=0)
        self.ahora = datetime(2026, 10, 1, 12, 0).astimezone()

    def _con_estado(self, estado):
        return patch.object(est, "leer_estado", return_value=estado)

    def test_avisa_si_esta_viejo(self) -> None:
        viejo = est.EstadoRespaldo(
            ultimo=datetime.now(timezone.utc) - timedelta(days=6), archivo=None
        )
        with self._con_estado(viejo):
            textos = self.v._respaldo_viejo(self.ahora)
        self.assertEqual(len(textos), 1)
        self.assertIn("6 días", textos[0])

    def test_no_avisa_si_esta_al_dia(self) -> None:
        with self._con_estado(est.EstadoRespaldo(ultimo=datetime.now(timezone.utc), archivo=None)):
            self.assertEqual(self.v._respaldo_viejo(self.ahora), [])

    def test_avisa_una_sola_vez_al_dia(self) -> None:
        viejo = est.EstadoRespaldo(
            ultimo=datetime.now(timezone.utc) - timedelta(days=6), archivo=None
        )
        with self._con_estado(viejo):
            primera = self.v._respaldo_viejo(self.ahora)
            segunda = self.v._respaldo_viejo(self.ahora + timedelta(minutes=30))
        self.assertEqual(len(primera), 1)
        self.assertEqual(segunda, [])  # el bot da una vuelta cada 25 s

    def test_de_madrugada_se_espera(self) -> None:
        # Un aviso a las 3 de la mañana se lee a las 9 mezclado con todo.
        viejo = est.EstadoRespaldo(ultimo=None, archivo=None)
        madrugada = self.ahora.replace(hour=3)
        with self._con_estado(viejo):
            self.assertEqual(self.v._respaldo_viejo(madrugada), [])
            # Y a las 10 sí.
            self.assertEqual(len(self.v._respaldo_viejo(self.ahora.replace(hour=10))), 1)

    def test_si_no_se_puede_leer_el_bot_sigue(self) -> None:
        with patch.object(est, "leer_estado", side_effect=OSError("disco")):
            self.assertEqual(self.v._respaldo_viejo(self.ahora), [])

    def test_va_en_la_revision_de_cada_vuelta(self) -> None:
        viejo = est.EstadoRespaldo(ultimo=None, archivo=None)
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from pos_uniformes.database.models import LibretaCorte, LibretaVenta

        engine = create_engine("sqlite://")
        for t in (LibretaVenta, LibretaCorte):
            t.__table__.create(engine)
        with sessionmaker(engine)() as session, self._con_estado(viejo):
            textos = self.v.revisar(session, self.ahora)
        self.assertTrue(any("respaldo" in t.lower() for t in textos))


if __name__ == "__main__":
    unittest.main()


class HojaEmergenciaTests(unittest.TestCase):
    """La hoja que se pega junto a la caja: que diga lo que tiene que decir."""

    def setUp(self) -> None:
        from pos_uniformes.scripts import hoja_emergencia as hoja

        self.hoja = hoja
        self.html = hoja.html()

    def test_es_una_pagina_de_carta(self) -> None:
        self.assertIn("size: letter", self.html)

    def test_no_usa_palabras_del_programa(self) -> None:
        # Quien la lee está atendiendo con un cliente enfrente.
        for palabra in ("base de datos", "servidor", "caché", "backup", "SQL", "Postgres"):
            self.assertNotIn(palabra.lower(), self.html.lower(), palabra)

    def test_dice_que_vender_no_se_detiene(self) -> None:
        self.assertIn("vender nunca se detiene", self.html)
        self.assertIn("Sigue vendiendo", self.html)

    def test_estan_los_casos_que_mas_pasan(self) -> None:
        for caso in ("QR", "sin conexión", "ticket", "aviso", "Gasto", "préstamo", "luz"):
            self.assertIn(caso, self.html, caso)

    def test_dice_que_el_corte_se_hace_solo(self) -> None:
        # Si no, alguna va a intentar hacerlo y no puede: el botón solo sale
        # con el gafete de Daniel.
        self.assertIn("corte se hace solo", self.html)

    def test_los_telefonos_van_en_blanco(self) -> None:
        # Se escriben con pluma: un teléfono guardado en el archivo se queda viejo.
        self.assertIn("Daniel", self.html)
        self.assertIn("linea", self.html)

    def test_se_escribe_donde_se_le_dice(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            destino = Path(tmp) / "hoja.html"
            self.hoja.main(["--salida", str(destino)])
            self.assertTrue(destino.exists())
            self.assertIn("Si algo falla", destino.read_text(encoding="utf-8"))
