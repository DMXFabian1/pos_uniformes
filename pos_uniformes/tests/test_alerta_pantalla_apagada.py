"""Aviso cuando una pantalla de la tienda se apaga en horas de trabajo.

Daniel (2026-10-08): «sí, hazlo lo del aviso de kiosko apagado». Hasta hoy una
pantalla muerta solo se sabía preguntando `/pulso`, y una pantalla muerta es
una muchacha que no puede cotizar ni vender.

Lo que se avisa es el CAMBIO —estaba prendida y se apagó—, no el estado. La
lista de satélites incluye la Mac de Daniel, que casi nunca está, y un kiosko
descompuesto desde hace una semana, que ya se sabe: avisar de ésos sería
enseñar a ignorar los avisos.
"""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

from pos_uniformes.services import alertas_service as al

#: Un jueves a las 11 de la mañana: tienda abierta.
ABIERTA = datetime(2026, 10, 8, 11, 0).astimezone()


def _pantalla(ident="KIOSKO-1", nombre="Kiosko 1", online=True, visto=None):
    """Una fila como la que devuelve el registro de satélites.

    `visto` es el último latido: de ahí sale cuánto lleva muerta, y no de
    cuándo el bot se dio cuenta."""
    return {"identificador": ident, "nombre": nombre, "online": online,
            "ultimo_visto": visto}


class LaPantallaQueSeApagaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.v = al.Vigilante()

    def _revisar(self, pantallas, ahora):
        with patch(
            "pos_uniformes.services.satelite_registry_service.listar_con_estado",
            return_value=pantallas,
        ):
            return self.v._pantalla_apagada(object(), ahora)

    def test_mientras_late_no_dice_nada(self) -> None:
        self.assertEqual(self._revisar([_pantalla(visto=ABIERTA)], ABIERTA), [])

    def test_el_reloj_corre_desde_el_ultimo_latido(self) -> None:
        """Y no desde que el bot se dio cuenta: si el bot se reinicia, lo
        contrario volvería a esperar diez minutos con la pantalla muerta
        desde hace media hora."""
        muerta_hace_rato = _pantalla(online=False, visto=ABIERTA - timedelta(hours=1))
        avisos = self._revisar([muerta_hace_rato], ABIERTA)
        self.assertEqual(len(avisos), 1)
        self.assertIn("60 min", avisos[0])

    def test_un_reinicio_del_bot_no_le_borra_la_memoria(self) -> None:
        """Quién trabajó hoy sale del dato, no solo de lo que este vigilante
        alcanzó a ver: si no, reiniciar el bot a media mañana dejaba sin
        reportar una pantalla que ya estaba muerta."""
        bot_nuevo = al.Vigilante()
        murio = ABIERTA - timedelta(minutes=40)
        with patch(
            "pos_uniformes.services.satelite_registry_service.listar_con_estado",
            return_value=[_pantalla(online=False, visto=murio)],
        ):
            avisos = bot_nuevo._pantalla_apagada(object(), ABIERTA)
        self.assertEqual(len(avisos), 1)

    def test_al_apagarse_avisa_pasado_el_margen(self) -> None:
        self._revisar([_pantalla(visto=ABIERTA)], ABIERTA)
        tarde = ABIERTA + timedelta(minutes=al.MINUTOS_PANTALLA_MUERTA + 1)
        avisos = self._revisar([_pantalla(online=False, visto=ABIERTA)], tarde)
        self.assertEqual(len(avisos), 1)
        self.assertIn("Kiosko 1", avisos[0])
        self.assertIn("sin responder", avisos[0])

    def test_un_reinicio_no_despierta_a_nadie(self) -> None:
        """Un kiosko que se reinicia tarda un par de minutos en volver."""
        self._revisar([_pantalla(visto=ABIERTA)], ABIERTA)
        dos = ABIERTA + timedelta(minutes=2)
        self.assertEqual(
            self._revisar([_pantalla(online=False, visto=ABIERTA)], dos), []
        )
        cuatro = ABIERTA + timedelta(minutes=4)
        self.assertEqual(self._revisar([_pantalla(visto=cuatro)], cuatro), [])

    def test_no_se_repite_cada_vuelta(self) -> None:
        """La vuelta del bot son 25 segundos."""
        self._revisar([_pantalla(visto=ABIERTA)], ABIERTA)
        tarde = ABIERTA + timedelta(minutes=al.MINUTOS_PANTALLA_MUERTA + 1)
        muerta = _pantalla(online=False, visto=ABIERTA)
        self.assertEqual(len(self._revisar([muerta], tarde)), 1)
        self.assertEqual(
            self._revisar([muerta], tarde + timedelta(minutes=1)), []
        )

    def test_cuando_vuelve_lo_dice(self) -> None:
        """Cerrar el aviso vale tanto como darlo: si no, queda la duda de si
        hay que ir a la tienda."""
        self._revisar([_pantalla(visto=ABIERTA)], ABIERTA)
        tarde = ABIERTA + timedelta(minutes=al.MINUTOS_PANTALLA_MUERTA + 1)
        self._revisar([_pantalla(online=False, visto=ABIERTA)], tarde)
        vuelta = tarde + timedelta(minutes=5)
        avisos = self._revisar([_pantalla(visto=vuelta)], vuelta)
        self.assertEqual(len(avisos), 1)
        self.assertIn("ya volvió", avisos[0])

    def test_despues_de_volver_puede_avisar_otra_vez(self) -> None:
        self._revisar([_pantalla(visto=ABIERTA)], ABIERTA)
        t = ABIERTA + timedelta(minutes=11)
        self._revisar([_pantalla(online=False, visto=ABIERTA)], t)
        vuelve = t + timedelta(minutes=1)
        self._revisar([_pantalla(visto=vuelve)], vuelve)
        avisos = self._revisar(
            [_pantalla(online=False, visto=vuelve)], vuelve + timedelta(minutes=20)
        )
        self.assertEqual(len(avisos), 1)


class LoQueNoEsNoticiaTests(unittest.TestCase):
    """Un aviso que sale siempre deja de leerse."""

    def setUp(self) -> None:
        self.v = al.Vigilante()

    def _revisar(self, pantallas, ahora):
        with patch(
            "pos_uniformes.services.satelite_registry_service.listar_con_estado",
            return_value=pantallas,
        ):
            return self.v._pantalla_apagada(object(), ahora)

    def test_la_mac_que_nunca_se_prende_no_molesta(self) -> None:
        """Está en la lista de satélites y casi nunca está encendida.

        Se juntan los avisos de TODAS las vueltas: mirando solo la última, el
        aviso de la primera pasaba inadvertido porque después ya estaba en la
        lista de avisadas y callaba igual.
        """
        mac = _pantalla("MAC-DANIEL", "MacBook de Daniel", online=False,
                        visto=ABIERTA - timedelta(days=3))
        todos = []
        for minuto in (0, 11, 30, 120):
            todos += self._revisar([mac], ABIERTA + timedelta(minutes=minuto))
        self.assertEqual(todos, [])

    def test_el_kiosko_descompuesto_desde_la_semana_pasada_tampoco(self) -> None:
        """Ya se sabe que está muerto; repetirlo cada mañana es ruido."""
        roto = _pantalla("KIOSKO-2", "Kiosko 2", online=False,
                         visto=ABIERTA - timedelta(days=7))
        todos = []
        for minuto in (0, 15, 60):
            todos += self._revisar([roto], ABIERTA + timedelta(minutes=minuto))
        self.assertEqual(todos, [])

    def test_fuera_de_horario_no_avisa(self) -> None:
        """De noche están apagadas a propósito."""
        noche = datetime(2026, 10, 8, 23, 30).astimezone()
        self._revisar([_pantalla(visto=ABIERTA)], ABIERTA)
        self.assertEqual(
            self._revisar([_pantalla(online=False, visto=ABIERTA)], noche), []
        )

    def test_lo_de_ayer_no_se_arrastra(self) -> None:
        """Un kiosko apagado anoche no es noticia hoy en la mañana."""
        self._revisar([_pantalla(visto=ABIERTA)], ABIERTA)
        manana = ABIERTA + timedelta(days=1)
        self.assertEqual(
            self._revisar([_pantalla(online=False, visto=ABIERTA)], manana), []
        )

    def test_si_el_registro_truena_el_bot_sigue(self) -> None:
        with patch(
            "pos_uniformes.services.satelite_registry_service.listar_con_estado",
            side_effect=OSError("sin base"),
        ):
            self.assertEqual(self.v._pantalla_apagada(object(), ABIERTA), [])


class EstaEnLaRondaDelVigilanteTests(unittest.TestCase):
    def test_revisar_lo_incluye(self) -> None:
        from pathlib import Path

        codigo = Path(al.__file__).read_text(encoding="utf-8")
        trozo = codigo[codigo.index("def revisar("):codigo.index("def _movimientos")]
        self.assertIn("_pantalla_apagada", trozo)


if __name__ == "__main__":
    unittest.main()
