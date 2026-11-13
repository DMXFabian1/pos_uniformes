"""Tarjetas que filtran y «Para atender» (Inventario, tanda 3)."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from pos_uniformes.services.inventario_tarjetas_service import (
    DIAS_CONTEO_AL_DIA,
    EN_NEGATIVO,
    INFO_TARJETAS,
    QUEDAN_POCAS,
    SE_ACABO,
    SIN_CONTAR,
    contar_tarjetas,
    dias_desde_conteo,
    en_tarjeta,
    filtrar_por_tarjeta,
    motivo_para_atender,
    para_atender,
    sin_contar_al_dia,
)

AHORA = datetime(2026, 11, 13, 12, 0, tzinfo=timezone.utc)


def fila(vid: int, stock: int, *, dias: int | None = 5, activa: bool = True, **extra) -> dict:
    datos = {
        "variante_id": vid,
        "stock_actual": stock,
        "stock_minimo": None,
        "variante_activa": activa,
        "ultimo_conteo_at": None if dias is None else AHORA - timedelta(days=dias),
    }
    datos.update(extra)
    return datos


class SinContarAlDiaTests(unittest.TestCase):
    def test_nunca_contada_no_esta_al_dia(self) -> None:
        self.assertTrue(sin_contar_al_dia(fila(1, 4, dias=None), ahora=AHORA))

    def test_el_dia_del_limite_todavia_esta_al_dia(self) -> None:
        self.assertFalse(sin_contar_al_dia(fila(1, 4, dias=DIAS_CONTEO_AL_DIA), ahora=AHORA))
        self.assertTrue(sin_contar_al_dia(fila(1, 4, dias=DIAS_CONTEO_AL_DIA + 1), ahora=AHORA))

    def test_fecha_sin_zona_se_toma_como_utc(self) -> None:
        sin_zona = (AHORA - timedelta(days=3)).replace(tzinfo=None)
        self.assertEqual(dias_desde_conteo({"ultimo_conteo_at": sin_zona}, ahora=AHORA), 3)

    def test_el_limite_es_60_dias_y_lo_dice_la_tarjeta(self) -> None:
        self.assertEqual(DIAS_CONTEO_AL_DIA, 60)
        self.assertIn("60 días", INFO_TARJETAS[SIN_CONTAR].criterio)
        self.assertEqual(INFO_TARJETAS[SIN_CONTAR].tono, "neutral")  # gris, no rojo


class TarjetasTests(unittest.TestCase):
    def setUp(self) -> None:
        self.filas = [
            fila(1, -2),
            fila(2, 0),
            fila(3, 0, dias=None),
            fila(4, 2),
            fila(5, 6, stock_minimo=8),  # bajo su mínimo
            fila(6, 12, dias=90),
            fila(7, 0, es_conjunto=True),  # conjunto: no cuenta en ninguna
            fila(8, -1, dias=None, stock_minimo=-1),  # marcador viejo de virtual
        ]

    def test_cada_tarjeta_cuenta_lo_que_filtra(self) -> None:
        cuentas = contar_tarjetas(self.filas, ahora=AHORA)
        for tarjeta in (EN_NEGATIVO, SE_ACABO, QUEDAN_POCAS, SIN_CONTAR):
            self.assertEqual(cuentas.de(tarjeta), len(filtrar_por_tarjeta(self.filas, tarjeta, ahora=AHORA)), tarjeta)
        self.assertEqual((cuentas.negativo, cuentas.se_acabo, cuentas.pocas, cuentas.sin_contar), (1, 2, 2, 2))

    def test_se_acabo_es_exactamente_cero(self) -> None:
        self.assertTrue(en_tarjeta(fila(1, 0), SE_ACABO, ahora=AHORA))
        self.assertFalse(en_tarjeta(fila(1, -1), SE_ACABO, ahora=AHORA))
        self.assertFalse(en_tarjeta(fila(1, 1), SE_ACABO, ahora=AHORA))

    def test_conjuntos_fuera_de_todas(self) -> None:
        conjunto = fila(7, 0, dias=None, es_conjunto=True)
        for tarjeta in (EN_NEGATIVO, SE_ACABO, QUEDAN_POCAS, SIN_CONTAR):
            self.assertFalse(en_tarjeta(conjunto, tarjeta, ahora=AHORA), tarjeta)

    def test_sin_tarjeta_pasa_todo(self) -> None:
        self.assertEqual(len(filtrar_por_tarjeta(self.filas, None, ahora=AHORA)), len(self.filas))
        self.assertEqual(len(filtrar_por_tarjeta(self.filas, "otra", ahora=AHORA)), len(self.filas))

    def test_filas_incompletas_no_truenan(self) -> None:
        cuentas = contar_tarjetas([{"variante_id": 1}], ahora=AHORA)
        self.assertEqual((cuentas.se_acabo, cuentas.sin_contar), (1, 1))


class ParaAtenderTests(unittest.TestCase):
    def test_negativos_primero_luego_ceros_contados_y_al_final_los_nunca_contados(self) -> None:
        filas = [
            fila(1, 0, dias=None),
            fila(2, 0, dias=40),
            fila(3, -1),
            fila(4, 0, dias=2),
            fila(5, -4),
            fila(6, 5),
        ]
        self.assertEqual([f["variante_id"] for f in para_atender(filas)], [5, 3, 4, 2, 1])

    def test_a_lo_mas_cinco(self) -> None:
        filas = [fila(i, -1) for i in range(1, 9)]
        self.assertEqual(len(para_atender(filas)), 5)
        self.assertEqual(len(para_atender(filas, limite=2)), 2)

    def test_sin_desactivadas_ni_conjuntos(self) -> None:
        filas = [fila(1, -3, activa=False), fila(2, 0, es_conjunto=True), fila(3, -1)]
        self.assertEqual([f["variante_id"] for f in para_atender(filas)], [3])

    def test_motivo_en_palabras_de_la_tienda(self) -> None:
        self.assertEqual(motivo_para_atender(fila(1, -2)), "En negativo (−2)")
        self.assertEqual(motivo_para_atender(fila(1, 0)), "Se acabó")
        self.assertEqual(motivo_para_atender(fila(1, 0, dias=None)), "Se acabó · nunca contada")


if __name__ == "__main__":
    unittest.main()
