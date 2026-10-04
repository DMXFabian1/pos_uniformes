"""Los últimos cortes, con lo que faltó o sobró.

Un corte con $300 de diferencia no enteraba a nadie hasta que alguien lo
buscaba en la PC (Daniel, 2026-09-25). Al estrenarlo salió que 9 de 10 cortes
quedaban cortos... y resultó que eran los ajustes del propio Daniel con
«Ajustar la venta», no dinero perdido (2026-10-01). Por eso el ajuste se
nombra ajuste y no enciende la alarma.
"""

from __future__ import annotations

import unittest
from datetime import date
from decimal import Decimal

from pos_uniformes.services import telegram_cortes_service as ct


def _fila(dia=18, contado="16082", esperado="17082", quien="Daniel", ops=11, ajustado=False):
    return ct.CorteFila(
        fecha=date(2026, 9, dia), hora="17:49", quien=quien,
        contado=Decimal(contado), esperado=Decimal(esperado), operaciones=ops,
        ajustado=ajustado,
    )


class LaCuentaTest(unittest.TestCase):
    def test_la_diferencia_es_contado_menos_esperado(self):
        self.assertEqual(_fila(contado="900", esperado="1000").diferencia, Decimal("-100.00"))
        self.assertEqual(_fila(contado="1100", esperado="1000").diferencia, Decimal("100.00"))

    def test_lo_chico_no_llama_la_atencion(self):
        self.assertFalse(_fila(contado="999", esperado="1000").llama_la_atencion)
        self.assertTrue(_fila(contado="900", esperado="1000").llama_la_atencion)


class ComoSeLeeTest(unittest.TestCase):
    def test_sin_cortes_lo_dice(self):
        self.assertIn("No hay cortes", ct.texto([], dias=14))

    def test_dice_si_falto_o_sobro_y_cuanto(self):
        r = ct.texto([_fila(contado="900", esperado="1000")])
        self.assertIn("faltó $100.00", r)
        r = ct.texto([_fila(contado="1100", esperado="1000")])
        self.assertIn("sobró $100.00", r)

    def test_el_que_cuadra_se_celebra(self):
        r = ct.texto([_fila(contado="1000", esperado="1000")])
        self.assertIn("✅ cuadró", r)
        self.assertIn("ninguno se pasa", r)

    def test_dice_quien_y_cuantas_operaciones(self):
        r = ct.texto([_fila(quien="Fanny Ortiz", ops=32)])
        self.assertIn("Fanny Ortiz", r)
        self.assertIn("32 ops", r)

    def test_señala_el_peor(self):
        filas = [_fila(contado="900", esperado="1000"), _fila(dia=19, contado="0", esperado="2149")]
        self.assertIn("$2,149.00", ct.texto(filas))


class ElAjusteNoEsUnDescuadreTest(unittest.TestCase):
    """Daniel bajaba la cifra del corte a mano con «Ajustar la venta», y el
    bot lo contaba como «faltó $2,000» — dinero perdido donde no lo había
    (2026-10-01). Un ajuste lo decidió él; un descuadre, nadie."""

    def test_el_ajuste_se_dice_ajuste(self):
        r = ct.texto([_fila(contado="16082", esperado="17082", ajustado=True)])
        self.assertIn("✏️ ajustado −$1,000.00", r)
        self.assertNotIn("faltó", r)

    def test_el_ajuste_no_enciende_la_alarma(self):
        self.assertFalse(_fila(contado="900", esperado="1000", ajustado=True).llama_la_atencion)
        self.assertTrue(_fila(contado="900", esperado="1000").llama_la_atencion)

    def test_sin_ajuste_sigue_diciendo_falto(self):
        self.assertIn("faltó", ct.texto([_fila(contado="900", esperado="1000")]))

    def test_dice_cuanto_sumaron_los_ajustes(self):
        filas = [
            _fila(dia=18, contado="16082", esperado="17082", ajustado=True),
            _fila(dia=19, contado="20548", esperado="22548", ajustado=True),
        ]
        r = ct.texto(filas)
        self.assertIn("2 con ajuste tuyo, −$3,000.00", r)

    def test_sin_ajustes_no_menciona_el_tema(self):
        self.assertNotIn("ajuste tuyo", ct.texto([_fila(contado="1000", esperado="1000")]))


class ElBotLoConoceTest(unittest.TestCase):
    def test_esta_en_la_ayuda_el_despachador_y_el_menu(self):
        from pathlib import Path

        from pos_uniformes.services.telegram_bot_service import AYUDA

        self.assertIn("/cortes", AYUDA)
        base = Path(__file__).resolve().parent.parent / "services"
        self.assertIn('cmd.nombre == "cortes"', (base / "telegram_bot_service.py").read_text(encoding="utf-8"))
        menu = (base / "telegram_menu_service.py").read_text(encoding="utf-8")
        self.assertIn('"m:cortes"', menu)


if __name__ == "__main__":
    unittest.main()


class TocarUnCorteTests(unittest.TestCase):
    """Ajustar, quitar el ajuste y borrar — desde el celular (2026-10-04).

    El diálogo «Cortes anteriores» del kiosko sabía hacerlo y el bot no. Lo que
    se cuida aquí sobre todo es que borrar **no** sea de un toque: es lo único
    de esta pantalla que no se puede deshacer, y se hace en la calle.
    """

    def setUp(self) -> None:
        from datetime import datetime
        from decimal import Decimal

        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session, sessionmaker

        from pos_uniformes.database.connection import Base
        from pos_uniformes.database.models import LibretaCorte

        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.s = Session(self.engine)
        self.addCleanup(self.s.close)
        self.factory = sessionmaker(self.engine)
        ahora = datetime.now().astimezone()
        # `desde` no es adorno: sin él el corte cuenta como de los viejos
        # (es_legacy) y el servicio dice que no guarda la cifra real.
        self.corte = LibretaCorte(
            fecha=ahora.date(), creado_por="VEND-1", desde=ahora,
            monto_final=Decimal("10000"), monto_esperado=Decimal("12000"),
            reactivo_inicial=Decimal("1000"), reactivo_final=Decimal("1000"),
            operaciones=20, created_at=ahora, hasta=ahora, nota="depósito al banco",
        )
        self.s.add(self.corte)
        self.s.flush()
        self.s.commit()

    def test_la_lista_trae_un_boton_por_corte(self) -> None:
        texto, botones = ct.texto_y_botones(self.s)
        self.assertIn(f"co:ver:{self.corte.id}", botones)

    def test_el_detalle_enseña_el_ajuste_y_su_motivo(self) -> None:
        from pos_uniformes.services.historial_cortes_service import venta_oficial, venta_real

        texto, filas = ct.detalle(self.s, self.corte.id)
        # Las cifras que se enseñan son las de VENTA, no los montos crudos del
        # corte: el reactivo y los pagos ya están descontados.
        self.assertIn(f"${venta_oficial(self.corte):,.2f}", texto)
        self.assertIn(f"${venta_real(self.corte):,.2f}", texto)
        self.assertIn("depósito al banco", texto)
        datos = [d for fila in filas for _, d in fila]
        self.assertIn(f"co:quitar:{self.corte.id}", datos)
        self.assertIn(f"co:borrar:{self.corte.id}", datos)

    def test_sin_ajuste_no_se_ofrece_quitarlo(self) -> None:
        from decimal import Decimal

        self.corte.monto_esperado = Decimal("10000")
        self.s.commit()
        _, filas = ct.detalle(self.s, self.corte.id)
        datos = [d for fila in filas for _, d in fila]
        self.assertNotIn(f"co:quitar:{self.corte.id}", datos)

    def test_borrar_pide_confirmacion_antes(self) -> None:
        # Un solo toque no puede borrar un corte.
        _, texto, botones = ct.atender(
            f"co:borrar:{self.corte.id}", session_factory=self.factory, quien="VEND-1"
        )
        self.assertIn("no se puede deshacer", texto)
        self.assertIn(f"co:borrarok:{self.corte.id}", botones)
        from pos_uniformes.database.models import LibretaCorte

        self.s.expire_all()
        self.assertIsNotNone(self.s.get(LibretaCorte, self.corte.id))

    def test_el_segundo_toque_si_borra(self) -> None:
        from pos_uniformes.database.models import LibretaCorte

        cid = self.corte.id
        aviso, _, _ = ct.atender(
            f"co:borrarok:{cid}", session_factory=self.factory, quien="VEND-1"
        )
        self.assertEqual(aviso, "Borrado")
        self.s.expire_all()
        self.assertIsNone(self.s.get(LibretaCorte, cid))

    def test_quitar_el_ajuste(self) -> None:
        aviso, _, _ = ct.atender(
            f"co:quitar:{self.corte.id}", session_factory=self.factory, quien="VEND-1"
        )
        self.assertEqual(aviso, "Ajuste quitado")

    def test_un_boton_mal_formado_no_revienta(self) -> None:
        aviso, _, _ = ct.atender("co:ver:abc", session_factory=self.factory, quien="VEND-1")
        self.assertEqual(aviso, "No conozco ese botón")

    def test_es_de_cortes(self) -> None:
        self.assertTrue(ct.es_de_cortes("co:ver:1"))
        self.assertFalse(ct.es_de_cortes("cj:pago:1"))


class AjustarPorTextoTests(unittest.TestCase):
    """La cifra se escribe, porque un botón no puede llevar una cantidad."""

    def setUp(self) -> None:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session

        from pos_uniformes.database.connection import Base

        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.s = Session(self.engine)
        self.addCleanup(self.s.close)

    def test_sin_argumentos_explica_como_se_usa(self) -> None:
        self.assertIn("/ajustar 12", ct.ajustar(self.s, "", quien="VEND-1"))

    def test_una_cifra_que_no_es_cifra(self) -> None:
        self.assertIn("No entendí", ct.ajustar(self.s, "12 muchos", quien="VEND-1"))

    def test_un_corte_que_no_existe_lo_dice(self) -> None:
        r = ct.ajustar(self.s, "99999 12500 depósito", quien="VEND-1")
        self.assertTrue(r)
        self.assertNotIn("ahora dice", r)


class SalidasDelPeriodoTests(unittest.TestCase):
    """Cada corte ya decía lo suyo; lo que faltaba era el acumulado, que es el
    número con el que Daniel puede rastrear el dinero que saca del cajón
    ("sólo necesito que sea trazable para mí", 2026-10-04)."""

    def _fila(self, dia, contado, esperado, *, ajustado=False):
        return ct.CorteFila(
            id=dia, fecha=date(2026, 10, dia), hora="17:40", quien="Daniel",
            contado=Decimal(contado), esperado=Decimal(esperado),
            operaciones=20, ajustado=ajustado,
        )

    def test_dice_cuanto_salio_y_en_cuantos_cortes(self) -> None:
        filas = [self._fila(2, "16438", "17438"), self._fila(1, "13591", "14716")]
        salidas = ct.SalidasPeriodo(cortes=13, salio=Decimal("14825.00"), cortes_que_faltaron=11)
        texto = ct.texto(filas, dias=14, salidas=salidas)
        self.assertIn("11 de 13 con diferencia, −$14,825.00 en total", texto)
        self.assertIn("no solo los 2 de arriba", texto)
        self.assertIn("/retiro", texto)

    def test_el_total_no_depende_de_cuantos_se_enseñan(self) -> None:
        """Sumar solo lo visible daría un número más chico que el real, y un
        número de dinero que depende del tamaño de la pantalla no sirve."""
        filas = [self._fila(2, "16438", "17438")]   # un solo corte en la lista
        salidas = ct.SalidasPeriodo(cortes=13, salio=Decimal("14825.00"), cortes_que_faltaron=11)
        texto = ct.texto(filas, dias=14, salidas=salidas)
        self.assertIn("−$14,825.00", texto)          # el total del periodo
        self.assertNotIn("−$1,000.00 en total", texto)   # no el del único visible

    def test_cuando_todo_cuadra_no_se_habla_de_diferencias(self) -> None:
        filas = [self._fila(3, "17596", "17596")]
        texto = ct.texto(filas, dias=14, salidas=ct.SalidasPeriodo(cortes=1))
        self.assertNotIn("con diferencia", texto)
        self.assertNotIn("/retiro", texto)

    def test_tambien_dice_lo_que_sobro(self) -> None:
        filas = [self._fila(2, "16438", "17438")]
        salidas = ct.SalidasPeriodo(
            cortes=5, salio=Decimal("1000.00"), cortes_que_faltaron=1,
            sobro=Decimal("40.00"), cortes_que_sobraron=2,
        )
        texto = ct.texto(filas, dias=14, salidas=salidas)
        self.assertIn("Salió $1,000.00 · sobró $40.00", texto)
        self.assertIn("−$960.00 en total", texto)   # el neto, no una de las dos


class DiasDeArgumentoTests(unittest.TestCase):
    """`/cortes 30` para poder mirar más atrás de la quincena."""

    def test_un_numero_son_dias(self) -> None:
        self.assertEqual(ct.dias_de_argumento("30"), 30)

    def test_sin_argumento_se_queda_como_estaba(self) -> None:
        self.assertEqual(ct.dias_de_argumento(""), 14)
        self.assertEqual(ct.dias_de_argumento("   "), 14)

    def test_lo_que_no_es_numero_no_rompe_el_comando(self) -> None:
        self.assertEqual(ct.dias_de_argumento("del mes"), 14)

    def test_no_se_piden_dos_años_de_cortes(self) -> None:
        self.assertEqual(ct.dias_de_argumento("9999"), 180)
        self.assertEqual(ct.dias_de_argumento("0"), 1)


class NoFelicitarConElDineroFueraTests(unittest.TestCase):
    """El mensaje decía "ninguno se pasa de $50 👍" justo encima de "−$14,825
    en total", porque aquí «ajustado» solo significa «tuvo diferencia» y
    entonces nada llama la atención nunca (2026-10-04)."""

    def _fila(self, dia, contado, esperado):
        return ct.CorteFila(
            id=dia, fecha=date(2026, 10, dia), hora="17:40", quien="Daniel",
            contado=Decimal(contado), esperado=Decimal(esperado),
            operaciones=20, ajustado=Decimal(contado) != Decimal(esperado),
        )

    def test_con_dinero_fuera_no_hay_pulgar_arriba(self) -> None:
        filas = [self._fila(2, "16438", "17438"), self._fila(3, "17596", "17596")]
        salidas = ct.SalidasPeriodo(cortes=13, salio=Decimal("14825.00"), cortes_que_faltaron=11)
        texto = ct.texto(filas, dias=14, salidas=salidas)
        self.assertNotIn("👍", texto)
        self.assertNotIn("ninguno se pasa", texto)
        self.assertIn("1 de 2 cuadraron exacto.", texto)
        self.assertIn("−$14,825.00", texto)

    def test_cuando_de_verdad_cuadro_todo_si_lo_dice(self) -> None:
        filas = [self._fila(3, "17596", "17596")]
        texto = ct.texto(filas, dias=14, salidas=ct.SalidasPeriodo(cortes=1))
        self.assertIn("👍", texto)
