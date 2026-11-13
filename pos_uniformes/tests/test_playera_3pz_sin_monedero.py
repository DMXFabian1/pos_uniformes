"""La playera de la promo 3pz no genera Monedero (Daniel, 2026-11-13: «Solo la playera»).

La playera a $100 del conjunto 3pz es la parte con descuento (como una
Oferta): no genera Monedero. El pants base del 3pz sí, a su precio. Club/Leal
no cambia. Una playera suelta (sin promo) sí da Monedero, y también la que
regresó a su precio normal porque el pants estaba rebajado.
"""

from __future__ import annotations

import unittest
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

from pos_uniformes.services import beneficios_carrito as bc
from pos_uniformes.services import cambio_service as cs
from pos_uniformes.services import monedero_service as mon
from pos_uniformes.services import sports_uniform_pricing_service as spp
from pos_uniformes.services.beneficios import motivos as M
from pos_uniformes.services.beneficios.fotografia import fotografia
from pos_uniformes.services.beneficios.motor import calcular
from pos_uniformes.services.beneficios_servidor import entrada_desde_plano

D = Decimal
HOY = datetime(2026, 11, 13, 18, 0, tzinfo=UTC)
CLUB = {"id": 1, "programa": "club", "tasa": D("5"), "estado": "activo"}


def _pants_base(**kw):
    return {"sku": "PB-8", "nombre": "Pants 2pz Deportivo", "talla": "8", "precio": D("300"), "cantidad": 1,
            "categoria": "Deportivo", "sports_uniform_role": "base", "sports_uniform_playera_sku": "PLY-8", **kw}


def _playera_promo(**kw):
    return {"sku": "PLY-8", "nombre": "Playera Deportiva" + spp.PROMO_NAME_SUFFIX, "talla": "8",
            "precio": D("100"), "precio_base": D("180"), "cantidad": 1, "categoria": "Deportivo",
            "sports_uniform_role": "playera", "sports_uniform_base_sku": "PB-8", **kw}


def _playera_suelta(**kw):
    return {"sku": "PLY-8", "nombre": "Playera Deportiva", "talla": "8", "precio": D("180"), "cantidad": 1,
            "categoria": "Deportivo", **kw}


def _calculo(items, **kw):
    entrada = bc.entrada_desde_carrito(items, fecha_venta=HOY, cliente=CLUB, **kw)
    return entrada, calcular(entrada)


def _linea(c, sku):
    (l,) = [l for l in c.lineas if l.sku == sku]
    return l


class MotorTests(unittest.TestCase):
    def test_playera_3pz_sin_monedero_y_pants_3pz_con_monedero(self):
        _, c = _calculo([_pants_base(), _playera_promo()])
        self.assertEqual(c.total, D("400.00"))
        self.assertEqual((c.monedero.base, c.monedero.abono), (D("300.00"), D("15.00")))
        playera, pants = _linea(c, "PLY-8"), _linea(c, "PB-8")
        self.assertEqual((playera.base_monedero, playera.abono_linea), (D("0.00"), D("0.00")))
        self.assertIn(M.TRES_PZ_PLAYERA_SIN_MONEDERO, playera.motivos)
        self.assertEqual((pants.base_monedero, pants.abono_linea), (D("300.00"), D("15.00")))
        self.assertNotIn(M.TRES_PZ_PLAYERA_SIN_MONEDERO, pants.motivos)
        # Las dos siguen siendo del 3pz.
        self.assertEqual({playera.clasificacion_al_vender, pants.clasificacion_al_vender}, {"3pz"})

    def test_club_leal_no_cambia(self):
        _, c = _calculo([_pants_base(), _playera_promo()])
        self.assertEqual(c.base_leal_total, D("400.00"))
        self.assertEqual(_linea(c, "PLY-8").base_leal, D("100.00"))

    def test_playera_suelta_si_da_monedero(self):
        _, c = _calculo([_playera_suelta()])
        self.assertEqual((c.monedero.base, c.monedero.abono), (D("180.00"), D("9.00")))
        self.assertNotIn(M.TRES_PZ_PLAYERA_SIN_MONEDERO, _linea(c, "PLY-8").motivos)

    def test_pants_rebajado_la_playera_regresa_a_precio_normal_y_da_monedero(self):
        pants = _pants_base(precio=D("175"), rebaja="oferta", precio_normal=D("250"))
        items = [pants, _playera_promo()]
        avisos, regresadas = spp.quitar_promo_3pz_de_pants_rebajados(items)
        self.assertEqual(len(regresadas), 1)
        self.assertTrue(avisos)
        _, c = _calculo(items)
        # El pants en Oferta no gana; la playera a $180 sí, como cualquier prenda.
        self.assertEqual((c.total, c.monedero.base, c.monedero.abono), (D("355.00"), D("180.00"), D("9.00")))
        self.assertNotIn(M.TRES_PZ_PLAYERA_SIN_MONEDERO, _linea(c, "PLY-8").motivos)

    def test_con_tarjeta_la_base_es_solo_del_pants(self):
        _, c = _calculo([_pants_base(), _playera_promo()], pago_tarjeta=True)
        self.assertLess(c.monedero.base, D("300.00"))
        self.assertEqual(_linea(c, "PLY-8").base_monedero, D("0.00"))

    def test_con_saldo_la_playera_no_gana(self):
        _, c = _calculo([_pants_base(), _playera_promo()], usar_saldo=True, saldo_disponible=D("40"))
        self.assertEqual(c.saldo_usado, D("40.00"))
        self.assertEqual(_linea(c, "PLY-8").base_monedero, D("0.00"))
        self.assertEqual(c.monedero.base, D("300.00") - _linea(c, "PB-8").parte_saldo)

    def test_sin_programa_no_se_marca_el_motivo(self):
        entrada = bc.entrada_desde_carrito([_pants_base(), _playera_promo()], fecha_venta=HOY)
        c = calcular(entrada)
        self.assertIsNone(c.monedero)
        self.assertNotIn(M.TRES_PZ_PLAYERA_SIN_MONEDERO, _linea(c, "PLY-8").motivos)

    def test_el_servidor_calcula_lo_mismo(self):
        entrada, c = _calculo([_pants_base(), _playera_promo()])
        plano = fotografia(entrada, c)["entrada"]
        self.assertTrue([l for l in plano["lineas"] if l["sku"] == "PLY-8"][0]["playera_3pz"])
        c2 = calcular(entrada_desde_plano(plano))
        self.assertEqual((c2.monedero.base, c2.monedero.abono), (c.monedero.base, c.monedero.abono))

    def test_fotografia_de_antes_sin_la_marca(self):
        entrada, c = _calculo([_pants_base(), _playera_promo()])
        plano = fotografia(entrada, c)["entrada"]
        for l in plano["lineas"]:
            l.pop("playera_3pz")
        self.assertFalse(any(l.playera_3pz for l in entrada_desde_plano(plano).lineas))

    def test_reconoce_la_playera_por_el_nombre(self):
        self.assertTrue(spp.es_playera_promo_3pz({"nombre": "Playera" + spp.PROMO_NAME_SUFFIX}))
        self.assertTrue(spp.es_playera_promo_3pz({"sports_uniform_role": "playera"}))
        self.assertFalse(spp.es_playera_promo_3pz({"sports_uniform_role": "base"}))
        self.assertFalse(spp.es_playera_promo_3pz({"nombre": "Playera"}))


class CuentaDeAntesTests(unittest.TestCase):
    """Sin fotografía (cálculo de respaldo): la misma regla."""

    def _venta(self, created_at=HOY):
        detalle = [
            {"sku": "PB-8", "nombre": "Pants 2pz Deportivo", "cantidad": 1, "precio": "300"},
            {"sku": "PLY-8", "nombre": "Playera Deportiva (promo 3pz)", "cantidad": 1, "precio": "100"},
            {"sku": "PO1", "nombre": "Playera polo", "cantidad": 1, "precio": "180"},
        ]
        return SimpleNamespace(id=1, monto_total=D("580"), monto_monedero=None, pago_tarjeta=False,
                               detalle=detalle, calculo=None, created_at=created_at)

    def test_sin_fotografia_la_playera_no_gana(self):
        self.assertEqual(mon.base_cashback_de_venta(self._venta()), (D("480.00"), False))

    def test_venta_de_antes_no_se_recalcula(self):
        venta = self._venta(created_at=datetime(2026, 11, 12, 18, 0, tzinfo=UTC))
        self.assertEqual(mon.base_cashback_legada(venta), (D("580.00"), False))

    def test_con_saldo_no_resta_dos_veces_el_saldo_de_la_playera(self):
        # Pants 3pz $350 + playera $100 = $450 con $100 de saldo: el motor da
        # 350 − 77.78 = 272.22; la cuenta de antes debe decir lo mismo.
        _, c = _calculo([_pants_base(precio=D("350")), _playera_promo()],
                        usar_saldo=True, saldo_disponible=D("100"))
        self.assertEqual((c.total, c.saldo_usado), (D("450.00"), D("100.00")))
        detalle = [{"sku": "PB-8", "nombre": "Pants 2pz Deportivo", "cantidad": 1, "precio": "350"},
                   {"sku": "PLY-8", "nombre": "Playera Deportiva (promo 3pz)", "cantidad": 1, "precio": "100"}]
        venta = SimpleNamespace(id=2, monto_total=D("450"), monto_monedero=D("100"), pago_tarjeta=False,
                                detalle=detalle, calculo=None, created_at=HOY)
        base, _ = mon.base_cashback_legada(venta)
        self.assertLessEqual(abs(base - c.monedero.base), D("0.01"))
        self.assertEqual(base, D("272.22"))
        # La cuenta de una venta de antes no cambia.
        self.assertEqual(mon.base_cashback_legada(venta, excluir_playeras=False)[0], D("350.00"))

    def test_kiosko_cuenta_de_antes_con_saldo(self):
        from pos_uniformes.ui.helpers.quick_sale_monedero_helper import MonederoVentaMixin

        w = SimpleNamespace(_items=[_pants_base(precio=D("350")), _playera_promo()],
                            _importe_rebajado_carrito=lambda: D("0"))
        self.assertEqual(MonederoVentaMixin._base_cashback_legada(w, D("450"), D("100")), D("272.22"))

    def test_playera_rebajada_no_se_cuenta_dos_veces(self):
        detalle = [{"nombre": "Playera (promo 3pz)", "precio": "100", "cantidad": 1, "rebaja": "oferta"}]
        self.assertEqual(spp.importe_playeras_promo_3pz(detalle), D("0.00"))

    def test_kiosko_cuenta_de_antes(self):
        from pos_uniformes.ui.helpers.quick_sale_monedero_helper import MonederoVentaMixin

        w = SimpleNamespace(_items=[_pants_base(), _playera_promo()], _importe_rebajado_carrito=lambda: D("0"))
        self.assertEqual(MonederoVentaMixin._base_cashback_legada(w, D("400"), D("0")), D("300.00"))


class CambioTests(unittest.TestCase):
    DETALLE = [
        {"sku": "PB-8", "nombre": "Pants 2pz Deportivo", "linea_uid": "u-pants", "precio": "300", "cantidad": 1},
        {"sku": "PLY-8", "nombre": "Playera Deportiva (promo 3pz)", "linea_uid": "u-playera", "precio": "100",
         "cantidad": 1},
    ]

    @staticmethod
    def _calc(motivo_playera: bool, bloqueado: bool = False):
        return {"monedero": None if bloqueado else {"base": "300.00"},
                "motivos_ticket": [M.CLIENTE_INACTIVO] if bloqueado else [],
                "lineas": [
                    {"lineas_origen": [["u-pants", 1]], "motivos": []},
                    {"lineas_origen": [["u-playera", 1]],
                     "motivos": [M.TRES_PZ_PLAYERA_SIN_MONEDERO] if motivo_playera else []},
                ]}

    def _foto(self, motivo_playera: bool):
        return {"entrada": {"lineas": [{"linea_uid": "u-pants", "promo_3pz": True},
                                       {"linea_uid": "u-playera", "promo_3pz": True}]},
                "calculo": self._calc(motivo_playera)}

    def _flags(self, foto, vendida_en=HOY):
        roles = cs.roles_promo_3pz(self.DETALLE, foto)
        return cs.playeras_sin_monedero(self.DETALLE, foto, roles, vendida_en)

    def test_sigue_lo_que_dijo_la_fotografia(self):
        self.assertEqual(self._flags(self._foto(True)), [False, True])
        # Fotografía de antes de la regla: la playera ganó.
        self.assertEqual(self._flags(self._foto(False)), [False, False])

    def test_sin_fotografia_por_fecha(self):
        self.assertEqual(self._flags(None), [False, True])
        self.assertEqual(self._flags(None, datetime(2026, 11, 10, tzinfo=UTC)), [False, False])

    def test_servidor_bloqueado_se_lee_el_calculo_del_kiosko(self):
        # El servidor recalculó con el monedero inactivo (sin parte del
        # Monedero ni motivo en la playera); el abono sale del kiosko, que
        # sí excluyó la playera: el reparto debe seguir al kiosko.
        foto = self._foto(True)
        foto["servidor"] = {"calculo": self._calc(False, bloqueado=True)}
        self.assertEqual(self._flags(foto), [False, True])
        # Los dos bloqueados: ningún cálculo manda, se va por la fecha.
        foto["calculo"] = self._calc(False, bloqueado=True)
        self.assertEqual(self._flags(foto), [False, True])
        self.assertEqual(self._flags(foto, datetime(2026, 11, 10, tzinfo=UTC)), [False, False])

    def test_sin_fotografia_manda_con_que_se_abono(self):
        roles = cs.roles_promo_3pz(self.DETALLE, None)
        # Venta del 13/11 abonada por el servidor viejo con la playera: ganó.
        self.assertEqual(cs.playeras_sin_monedero(self.DETALLE, None, roles, HOY, False), [False, False])
        self.assertEqual(cs.playeras_sin_monedero(self.DETALLE, None, roles, HOY, True), [False, True])

    def test_segun_abono_compara_con_las_dos_cuentas(self):
        from unittest import mock

        venta = SimpleNamespace(id=7, monto_total=D("400"), monto_monedero=None, pago_tarjeta=False,
                                detalle=self.DETALLE, calculo=None, created_at=HOY)

        def con_base(base):
            movs = [SimpleNamespace(tipo=mon.CASHBACK, base_calculo=base)] if base is not None else []
            with mock.patch.object(mon, "movimientos_de_operacion", return_value=movs):
                return cs.playera_sin_monedero_segun_abono(None, venta)

        self.assertIs(con_base(D("400.00")), False)   # abonado con la playera (antes de instalar)
        self.assertIs(con_base(D("300.00")), True)    # abonado ya sin la playera
        self.assertIsNone(con_base(D("123.00")))      # no se distingue: por fecha
        self.assertIsNone(con_base(None))             # sin abono

    def _renglones(self, playera_sin_monedero: bool):
        return [
            cs.RenglonVendido(0, "PB-8", "Pants", "8", 1, 0, D("300"), False, rol_3pz=cs.BASE_3PZ),
            cs.RenglonVendido(1, "PLY-8", "Playera (promo 3pz)", "8", 1, 0, D("100"), False,
                              rol_3pz=cs.PLAYERA_3PZ, playera_sin_monedero=playera_sin_monedero),
        ]

    def test_regresar_la_playera_3pz_no_quita_monedero(self):
        renglones = self._renglones(True)
        # El abono ($15) salió solo del pants.
        self.assertEqual(cs.cashback_proporcional(D("15"), D("0"), renglones, {1: 1}), D("0.00"))
        self.assertEqual(cs.cashback_proporcional(D("15"), D("0"), renglones, {0: 1}), D("15.00"))
        c = cs.cuenta(D("100"), cs.cashback_proporcional(D("15"), D("0"), renglones, {1: 1}), D("180"))
        self.assertEqual((c.reconocido, c.a_pagar), (D("100.00"), D("80.00")))

    def test_venta_de_antes_reparte_como_antes(self):
        renglones = self._renglones(False)
        self.assertEqual(cs.cashback_proporcional(D("20"), D("0"), renglones, {1: 1}), D("5.00"))
        self.assertEqual(cs.cashback_proporcional(D("20"), D("0"), renglones, {0: 1}), D("15.00"))


if __name__ == "__main__":
    unittest.main()
