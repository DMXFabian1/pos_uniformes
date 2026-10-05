"""`/pulso` — ¿está todo en pie?

Antes había que mandar cinco comandos y adivinar el resto. Lo que se cuida: que
cada renglón se gane su marca, que lo que no se pudo averiguar se diga en vez de
asumirse bien, y que un bloque caído no se lleve la vista entera.
"""

from __future__ import annotations

import unittest
from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import LibretaVenta
from pos_uniformes.services import telegram_pulso_service as pul


class _Base(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.s = Session(self.engine)
        self.addCleanup(self.s.close)
        self.hoy = date(2026, 10, 2)
        self.medio_dia = datetime.combine(self.hoy, datetime.min.time()).replace(hour=12).astimezone()
        # El respaldo mira el disco de la máquina; se fija para no depender de él.
        from pos_uniformes.services import respaldo_estado_service as est

        parche = patch.object(
            est, "leer_estado",
            return_value=est.EstadoRespaldo(ultimo=datetime.now().astimezone(), archivo=None),
        )
        parche.start()
        self.addCleanup(parche.stop)

    def _pulso(self) -> str:
        return pul.pulso(self.s, hoy=self.hoy, ahora=self.medio_dia)


class SeLeeDeUnVistazoTests(_Base):
    def test_trae_todo_lo_que_importa(self) -> None:
        texto = self._pulso()
        for pedazo in ("La tienda ahora", "Vendido", "corte", "Pantallas", "Respaldo"):
            self.assertIn(pedazo, texto, pedazo)

    def test_cada_renglon_trae_su_marca(self) -> None:
        # Se tiene que poder leer sin entender ninguna cifra.
        cuerpo = [l for l in self._pulso().splitlines()[2:] if l.strip()]
        for linea in cuerpo:
            self.assertTrue(
                linea.lstrip().startswith((pul.BIEN, pul.OJO, pul.MUDO)) or linea.startswith("   "),
                f"renglón sin marca: {linea}",
            )

    def test_sin_nada_pendiente_lo_dice(self) -> None:
        # Que no haya noticias es una noticia.
        self.assertIn("Nada esperando tu respuesta", self._pulso())


class CuandoAlgoFallaTests(_Base):
    def test_un_bloque_caido_no_se_lleva_los_demas(self) -> None:
        with patch.object(pul, "_pantallas", side_effect=RuntimeError("sin registro")):
            texto = self._pulso()
        self.assertIn("no se pudo leer este dato", texto)
        self.assertIn("Respaldo", texto)       # los de después salieron igual
        self.assertIn("Vendido", texto)        # los de antes también

    def test_lo_que_no_se_sabe_no_se_asume_bien(self) -> None:
        with patch.object(pul, "_respaldo", side_effect=RuntimeError("disco")):
            texto = self._pulso()
        self.assertIn(pul.OJO, texto)
        self.assertNotIn("✅ Respaldo", texto)

    def test_hace_rollback_para_no_envenenar_la_sesion(self) -> None:
        # En Postgres una consulta que falla deja la transacción abortada y
        # TODO lo que venga después falla también.
        llamadas = []
        self.s.rollback = lambda: llamadas.append(1)
        with patch.object(pul, "_corte", side_effect=RuntimeError("boom")):
            self._pulso()
        self.assertTrue(llamadas, "no se hizo rollback tras el bloque caído")

    def test_todo_caido_sigue_contestando(self) -> None:
        with patch.object(pul, "_tienda", side_effect=RuntimeError()), \
             patch.object(pul, "_venta", side_effect=RuntimeError()), \
             patch.object(pul, "_corte", side_effect=RuntimeError()), \
             patch.object(pul, "_pantallas", side_effect=RuntimeError()), \
             patch.object(pul, "_respaldo", side_effect=RuntimeError()), \
             patch.object(pul, "_esperando", side_effect=RuntimeError()):
            texto = self._pulso()
        self.assertIn("La tienda ahora", texto)


class LoQueDiceCadaBloqueTests(_Base):
    def test_cerrada_fuera_de_horario(self) -> None:
        madrugada = datetime.combine(self.hoy, datetime.min.time()).replace(hour=3).astimezone()
        self.assertIn("Cerrada", pul.pulso(self.s, hoy=self.hoy, ahora=madrugada))

    def test_abierta_y_sin_movimiento_pide_atencion(self) -> None:
        self.assertIn("nadie ha movido nada", self._pulso())

    def test_sin_corte_nunca(self) -> None:
        self.assertIn("Nunca se ha hecho un corte", self._pulso())

    def test_la_venta_trae_su_comparacion(self) -> None:
        for semanas in (1, 2):
            self.s.add(LibretaVenta(
                employee_code="VEND-3", employee_name="Evelyn", tipo="venta", piezas=1,
                monto_total=Decimal("1000"),
                created_at=(self.medio_dia - timedelta(weeks=semanas)).replace(hour=10),
            ))
        self.s.add(LibretaVenta(
            employee_code="VEND-3", employee_name="Evelyn", tipo="venta", piezas=1,
            monto_total=Decimal("2000"), created_at=self.medio_dia.replace(hour=10),
        ))
        self.s.flush()
        texto = self._pulso()
        self.assertIn("$2,000.00", texto)
        self.assertIn("viernes", texto)


class EnganchadoAlBotTests(_Base):
    def test_el_comando_existe(self) -> None:
        from sqlalchemy.orm import sessionmaker

        from pos_uniformes.services import telegram_bot_service as bot

        factory = sessionmaker(self.engine)
        with patch.object(pul, "_respaldo", return_value=["✅ Respaldo: hoy"]):
            texto = bot.atender_texto("/pulso", session_factory=factory)
        self.assertIn("La tienda ahora", texto)

    def test_esta_en_la_ayuda_y_en_el_menu(self) -> None:
        from pos_uniformes.services import telegram_bot_service as bot
        from pos_uniformes.services import telegram_menu_service as menu

        self.assertIn("/pulso", bot.AYUDA)
        self.assertIn("m:pulso", {d for fila in menu._RAIZ for _, d in fila})


if __name__ == "__main__":
    unittest.main()


class ImpresionEnElPulsoTests(unittest.TestCase):
    """El renglón que delata que el Servidor de impresión está apagado.

    Con una sola PC conectada a las impresoras, apagarla no da ningún error:
    el papel no sale y el que vendió cree que su ticket salió (2026-10-05)."""

    _AHORA = datetime(2026, 10, 5, 18, 0).astimezone()

    def _lineas(self, atorados):
        with patch("pos_uniformes.services.trabajos_service.esperando_impresion",
                   return_value=atorados):
            return pul._impresion(object(), self._AHORA)

    def _trabajo(self, tipo, *, hace_minutos):
        from types import SimpleNamespace

        return SimpleNamespace(
            tipo=SimpleNamespace(value=tipo),
            created_at=self._AHORA - timedelta(minutes=hace_minutos),
        )

    def test_sin_nada_esperando_lo_dice(self) -> None:
        linea, = self._lineas([])
        self.assertIn("al día", linea)
        self.assertIn("✅", linea)

    def test_dice_cuantos_de_cada_cosa_y_cuanto_llevan(self) -> None:
        texto = "\n".join(self._lineas([
            self._trabajo("ETIQUETA", hace_minutos=95),
            self._trabajo("ETIQUETA", hace_minutos=40),
            self._trabajo("TICKET", hace_minutos=30),
        ]))
        self.assertIn("2 etiqueta", texto)
        self.assertIn("1 ticket", texto)
        self.assertIn("95 min", texto)
        self.assertIn("Servidor de impresión", texto)

    def test_con_horas_no_dice_cientos_de_minutos(self) -> None:
        self.assertIn("5 h", "\n".join(self._lineas([self._trabajo("TICKET", hace_minutos=300)])))

    def test_si_la_cola_no_se_puede_leer_el_pulso_sigue(self) -> None:
        """Un bloque caído no se lleva la vista entera."""
        lineas = [""]
        with patch("pos_uniformes.services.trabajos_service.esperando_impresion",
                   side_effect=RuntimeError("sin base")):
            pul._bloque(object(), lineas, lambda: pul._impresion(object(), self._AHORA))
        self.assertIn("no se pudo leer", "\n".join(lineas))
