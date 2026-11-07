"""El bot cuenta su propio silencio al volver.

El 02/10 la PC de la tienda se quedó sin internet y el bot llevaba horas
muerto; Daniel se enteró por accidente, al intentar actualizar. Con él fuera
una semana, eso se habría visto igual que una tienda tranquila.
"""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from pos_uniformes.services import bot_conexion_service as con


class _Base(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        parche = patch.object(
            con, "ruta_estado", return_value=Path(self._tmp.name) / "bot_conexion.json"
        )
        parche.start()
        self.addCleanup(parche.stop)
        self.t0 = datetime(2026, 10, 5, 9, 0, tzinfo=timezone.utc)

    def _sin_linea(self, desde: datetime, hasta: datetime) -> None:
        """El bot vivo y sin red reintenta cada pocos segundos (aquí, cada 5 min)."""
        t = desde
        while t <= hasta:
            con.anotar_fallo(t)
            t += timedelta(minutes=5)


class CuentaElHuecoTests(_Base):
    def test_sin_nada_previo_no_dice_nada(self) -> None:
        self.assertIsNone(con.anotar_ok(self.t0))

    def test_un_parpadeo_no_se_reporta(self) -> None:
        # La red parpadea; un sondeo suelto que falla no es un apagón.
        con.anotar_fallo(self.t0)
        self.assertIsNone(con.anotar_ok(self.t0 + timedelta(seconds=40)))

    def test_un_apagon_de_verdad_si(self) -> None:
        self._sin_linea(self.t0, self.t0 + timedelta(hours=2, minutes=10))
        texto = con.anotar_ok(self.t0 + timedelta(hours=2, minutes=15))
        self.assertIsNotNone(texto)
        self.assertIn("2 h 15 min", texto)

    def test_el_hueco_empieza_en_el_PRIMER_fallo(self) -> None:
        # Cada vuelta del bot vuelve a fallar; el hueco no se reinicia.
        self._sin_linea(self.t0, self.t0 + timedelta(hours=2, minutes=55))
        texto = con.anotar_ok(self.t0 + timedelta(hours=3))
        self.assertIn("3 h", texto)

    def test_sobrevive_a_que_reinicien_el_bot(self) -> None:
        # El supervisor lo reinicia cada rato: si el estado viviera en memoria,
        # un hueco de dos horas se reportaría como de cinco minutos.
        self._sin_linea(self.t0, self.t0 + timedelta(hours=1))
        # (aquí el proceso muere y arranca otro: solo queda el archivo)
        self._sin_linea(self.t0 + timedelta(hours=1, minutes=5), self.t0 + timedelta(hours=1, minutes=55))
        texto = con.anotar_ok(self.t0 + timedelta(hours=2))
        self.assertIn("2 h", texto)

    def test_despues_de_contarlo_no_lo_repite(self) -> None:
        self._sin_linea(self.t0, self.t0 + timedelta(minutes=55))
        self.assertIsNotNone(con.anotar_ok(self.t0 + timedelta(hours=1)))
        self.assertIsNone(con.anotar_ok(self.t0 + timedelta(hours=1, minutes=1)))

    def test_la_noche_no_cuenta(self) -> None:
        # Si la PC se apaga al cerrar, ninguna consulta falla. Avisar «estuve
        # 15 h callado» cada mañana sería ruido, y el ruido se ignora.
        con.anotar_ok(datetime(2026, 10, 5, 18, 0, tzinfo=timezone.utc))
        self.assertIsNone(con.anotar_ok(datetime(2026, 10, 6, 9, 0, tzinfo=timezone.utc)))

    def test_sin_red_al_cerrar_y_la_pc_apagada_no_cuenta_la_noche(self) -> None:
        """Se fue la red a las 18:30, la PC se apagó a las 19:00 y prendió al
        otro día: decía «Estuve 14 h sin poder hablar» (auditoría 2026-11-07)."""
        caida = datetime(2026, 10, 5, 18, 30).astimezone()
        self._sin_linea(caida, caida + timedelta(minutes=30))
        texto = con.anotar_ok(caida + timedelta(hours=14, minutes=30))
        self.assertIn("Estuve 30 min sin poder hablar", texto)
        self.assertIn("de las 18:30 a las 19:00 (después la PC estuvo apagada)", texto)

    def test_un_rato_corto_antes_de_apagar_no_se_dice(self) -> None:
        caida = datetime(2026, 10, 5, 18, 58).astimezone()
        self._sin_linea(caida, caida + timedelta(minutes=1))
        self.assertIsNone(con.anotar_ok(caida + timedelta(hours=14)))

    def test_un_hueco_viejo_sin_cerrar_no_se_suma_al_nuevo(self) -> None:
        ayer = datetime(2026, 10, 5, 18, 30).astimezone()
        self._sin_linea(ayer, ayer + timedelta(minutes=2))
        hoy = ayer + timedelta(hours=15)
        self._sin_linea(hoy, hoy + timedelta(minutes=40))
        texto = con.anotar_ok(hoy + timedelta(minutes=45))
        self.assertIn("Estuve 45 min", texto)

    def test_un_archivo_corrupto_no_tumba_el_bot(self) -> None:
        con.ruta_estado().parent.mkdir(parents=True, exist_ok=True)
        con.ruta_estado().write_text("{roto", encoding="utf-8")
        self.assertIsNone(con.anotar_ok(self.t0))
        self._sin_linea(self.t0, self.t0 + timedelta(minutes=55))
        self.assertIsNotNone(con.anotar_ok(self.t0 + timedelta(hours=1)))

    def test_un_disco_de_solo_lectura_tampoco(self) -> None:
        # Se parchea la ESCRITURA, no `_guardar`: lo que hay que probar es que
        # el bot sobrevive a un disco que no deja escribir, no que una función
        # mía atrape lo que yo mismo le lanzo.
        with patch.object(Path, "write_text", side_effect=OSError("solo lectura")):
            con.anotar_fallo(self.t0)
            con.anotar_ok(self.t0)   # no debe propagar


class ComoSeLeeTests(unittest.TestCase):
    def test_duraciones(self) -> None:
        d = con.duracion_legible
        self.assertEqual(d(timedelta(seconds=90)), "1 min")
        self.assertEqual(d(timedelta(minutes=45)), "45 min")
        self.assertEqual(d(timedelta(hours=2)), "2 h")
        self.assertEqual(d(timedelta(hours=2, minutes=15)), "2 h 15 min")
        self.assertEqual(d(timedelta(days=1, hours=3)), "1 día")
        self.assertEqual(d(timedelta(days=3)), "3 días")

    def test_el_mensaje_dice_el_rango_y_que_revisar(self) -> None:
        desde = datetime(2026, 10, 5, 9, 14).astimezone()
        hasta = datetime(2026, 10, 5, 11, 30).astimezone()
        texto = con.texto_del_hueco(desde, hasta)
        self.assertIn("09:14", texto)
        self.assertIn("11:30", texto)
        self.assertIn("2 h 16 min", texto)
        # Lo que importa no es que se cayó: es qué no le llegó.
        self.assertIn("no te llegó nada", texto)
        self.assertIn("/cortes", texto)

    def test_si_cruza_la_medianoche_dice_el_dia(self) -> None:
        desde = datetime(2026, 10, 4, 22, 0).astimezone()
        hasta = datetime(2026, 10, 5, 9, 0).astimezone()
        texto = con.texto_del_hueco(desde, hasta)
        self.assertIn("04/10", texto)


class EnganchadoAlBotTests(unittest.TestCase):
    def test_el_bucle_anota_el_fallo_y_el_regreso(self) -> None:
        codigo = (
            Path(__file__).resolve().parents[1] / "services" / "telegram_bot_service.py"
        ).read_text(encoding="utf-8")
        self.assertIn("conexion.anotar_fallo()", codigo)
        self.assertIn("de_regreso = conexion.anotar_ok()", codigo)
        self.assertIn("_mandar(de_regreso)", codigo)


if __name__ == "__main__":
    unittest.main()
