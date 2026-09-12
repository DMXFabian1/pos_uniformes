"""El fill maker ya no depende de un dado: depende de la cola y del volumen que cruza el precio."""
from scalper.sim.fill_model import FillModel, MakerOrder
from scalper.signals.base import Leg
from conftest import make_book


def _orden(queue=100.0, size=50.0, side="BUY", price=0.41):
    return MakerOrder("t", side, price, size, queue_ahead=queue, ts_placed=0, queue_inicial=queue)


def test_sin_volumen_que_cruce_no_hay_fill_en_ningun_escenario():
    fm = FillModel()
    o = _orden()
    assert fm.maker_on_trade(o, {"token_id": "t", "side": "BUY", "price": 0.41, "size": 1000}, 1) == 0   # no cruza
    assert fm.maker_on_trade(o, {"token_id": "t", "side": "SELL", "price": 0.42, "size": 1000}, 1) == 0  # por encima
    assert o.escenarios() == {"conservador": 0.0, "base": 0.0, "optimista": 0.0}


def test_la_cola_se_consume_antes_que_nosotros_y_los_tres_escenarios_divergen():
    fm = FillModel()
    o = _orden(queue=100, size=50)
    # 30 shares cruzan a nuestro precio: optimista ya tiene 30, base y conservador siguen en cola
    assert fm.maker_on_trade(o, {"token_id": "t", "side": "SELL", "price": 0.41, "size": 30}, 1) == 0
    assert o.escenarios() == {"conservador": 0.0, "base": 0.0, "optimista": 30.0}
    # 90 más: acumulado 120 → conservador 20, base 20 (sin cancelaciones coincide), optimista 50
    assert fm.maker_on_trade(o, {"token_id": "t", "side": "SELL", "price": 0.41, "size": 90}, 2) == 20
    assert o.escenarios() == {"conservador": 20.0, "base": 20.0, "optimista": 50.0}
    assert o.ts_fill["optimista"] == 1 and o.ts_fill["base"] == 2 and o.ts_fill["conservador"] == 2
    assert not o.done and o.fills[0].fee == 0.0


def test_las_cancelaciones_en_el_nivel_acortan_la_cola_solo_en_el_escenario_base():
    fm = FillModel()
    o = _orden(queue=100, size=50)
    b = make_book("t", [(0.41, 100), (0.40, 500)], [(0.43, 100)])
    assert fm.maker_on_book(o, b, 1) == 0
    # el nivel pasa de 100 a 40 sin trades: 60 cancelados delante (BASE los descuenta)
    b.apply_delta("BUY", 0.41, 40, 2)
    assert fm.maker_on_book(o, b, 2) == 0
    assert o.queue_ahead == 40 and o.cancelado_delante == 60
    got = fm.maker_on_trade(o, {"token_id": "t", "side": "SELL", "price": 0.41, "size": 60}, 3)
    assert got == 20                                          # 40 de cola + 20 nuestros
    assert o.escenarios() == {"conservador": 0.0, "base": 20.0, "optimista": 50.0}


def test_trades_y_cancelaciones_no_se_cuentan_dos_veces():
    fm = FillModel()
    o = _orden(queue=100, size=50)
    b = make_book("t", [(0.41, 100)], [(0.43, 100)])
    fm.maker_on_book(o, b, 1)
    fm.maker_on_trade(o, {"token_id": "t", "side": "SELL", "price": 0.41, "size": 30}, 2)   # cola 70
    b.apply_delta("BUY", 0.41, 70, 3)                          # el libro refleja exactamente ese trade
    fm.maker_on_book(o, b, 3)
    assert o.queue_ahead == 70 and o.cancelado_delante == 0    # nada se interpretó como cancelación


def test_un_trade_que_barre_el_nivel_nos_llena_entero_y_queda_marcado():
    fm = FillModel()
    o = _orden(queue=1000, size=50)
    got = fm.maker_on_trade(o, {"token_id": "t", "side": "SELL", "price": 0.39, "size": 5}, 1)
    assert got == 50 and o.done and o.barrido
    assert o.escenarios() == {"conservador": 50.0, "base": 50.0, "optimista": 50.0}


def test_si_el_libro_cruza_nuestro_precio_nos_llenaron_todo():
    fm = FillModel()
    o = _orden(queue=1000, size=50)
    b = make_book("t", [(0.38, 100)], [(0.40, 100)])           # el ask cayó por debajo de nuestro 0.41
    assert fm.maker_on_book(o, b, 1) == 50 and o.barrido


def test_orden_de_venta_simetrica():
    fm = FillModel()
    o = _orden(queue=10, size=20, side="SELL", price=0.60)
    assert fm.maker_on_trade(o, {"token_id": "t", "side": "SELL", "price": 0.60, "size": 100}, 1) == 0
    assert fm.maker_on_trade(o, {"token_id": "t", "side": "BUY", "price": 0.60, "size": 25}, 1) == 15
    assert fm.maker_on_trade(o, {"token_id": "t", "side": "BUY", "price": 0.61, "size": 1}, 2) == 5    # barrido
    assert o.done


def test_place_maker_toma_la_cola_del_nivel():
    fm = FillModel()
    b = make_book("t", [(0.41, 77), (0.40, 500)], [(0.43, 100)])
    o = fm.place_maker(Leg("t", "BUY", 0.41, 50, "maker"), b, 5)
    assert o.queue_ahead == 77 and o.queue_inicial == 77 and o.ts_placed == 5
    o2 = fm.place_maker(Leg("t", "BUY", 0.42, 50, "maker"), b, 5)     # nivel vacío: nadie delante
    assert o2.queue_ahead == 0


def test_un_empate_no_es_un_barrido_y_respeta_la_cola():
    # El mejor vendedor llega exactamente a nuestro precio de compra. Eso es una contrapartida que
    # viene a nuestro precio —el caso bueno del maker—, no que nos pasen por encima. Antes esto
    # llenaba la orden entera al instante y la marcaba como barrida: 301 de los 349 "barridos" de
    # TENNIS_SPREAD_CAPTURE eran esto.
    fm = FillModel()
    o = _orden(queue=100, size=50, price=0.41)
    libro = make_book("t", [(0.41, 100)], [(0.41, 30)])       # empate, 30 ofrecidos
    assert fm.maker_on_book(o, libro, 1) == 0.0               # los 30 se los come la cola de 100
    assert not o.barrido and o.filled == 0.0
    libro2 = make_book("t", [(0.41, 100)], [(0.41, 200)])     # ahora hay 200 ofrecidos
    llenado = fm.maker_on_book(o, libro2, 2)
    assert llenado == 50.0 and o.causa == "empate" and not o.barrido


def test_el_empate_no_se_cuenta_dos_veces_si_dura_varios_libros():
    fm = FillModel()
    o = _orden(queue=0.0, size=50, price=0.41)
    libro = make_book("t", [(0.41, 0)], [(0.41, 20)])
    assert fm.maker_on_book(o, libro, 1) == 20.0
    # el mismo empate en el siguiente libro no vuelve a llenar
    assert fm.maker_on_book(o, make_book("t", [(0.41, 0)], [(0.41, 20)]), 2) == 0.0
    assert o.filled == 20.0


def test_un_libro_atravesado_si_es_un_barrido():
    # El mejor vendedor por DEBAJO de nuestra compra: el precio pasó de largo por nuestro nivel y
    # lo que hubiera ahí se consumió entero, cola incluida.
    fm = FillModel()
    o = _orden(queue=1000, size=50, price=0.41)
    llenado = fm.maker_on_book(o, make_book("t", [(0.39, 100)], [(0.40, 100)]), 1)
    assert llenado == 50.0 and o.barrido and o.causa == "barrido"


def test_un_trade_al_precio_llena_por_cola_y_uno_que_atraviesa_barre():
    fm = FillModel()
    a = _orden(queue=0.0, size=50, price=0.41)
    fm.maker_on_trade(a, {"token_id": "t", "side": "SELL", "price": 0.41, "size": 50}, 1)
    assert a.causa == "trade" and not a.barrido
    b = _orden(queue=1000, size=50, price=0.41)
    fm.maker_on_trade(b, {"token_id": "t", "side": "SELL", "price": 0.40, "size": 10}, 1)
    assert b.causa == "barrido" and b.barrido
