"""Analítica sobre la Libreta: desglose de cada venta y agregados."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

from pos_uniformes.services import analitica_libreta_service as an

_LUNES = datetime(2026, 9, 7, 11, 30)


def _op(tipo="venta", hora=_LUNES, emp=("VEND-2", "Fanny Ortiz"), tarjeta=False, detalle=None):
    return SimpleNamespace(
        tipo=tipo, created_at=hora, employee_code=emp[0], employee_name=emp[1],
        pago_tarjeta=tarjeta, detalle=detalle or [], privado=False,
    )


def _linea(sku, nombre, talla, cantidad, precio, subtotal=None):
    d = {"sku": sku, "nombre": nombre, "talla": talla, "cantidad": cantidad, "precio": str(precio)}
    if subtotal is not None:
        d["subtotal"] = str(subtotal)
    return d


class DesglosarTests(unittest.TestCase):
    def test_una_fila_por_linea_de_producto(self) -> None:
        rows = [_op(detalle=[
            _linea("SKU1", "Playera Polo Blanca", "6", 3, "89.00", "267.00"),
            _linea("SKU2", "Calceta Escolar Blanca", "13-18", 2, "49.00", "98.00"),
        ])]
        filas = an.desglosar(rows)
        self.assertEqual(len(filas), 2)
        self.assertEqual(filas[0].sku, "SKU1")
        self.assertEqual(filas[0].cantidad, 3)
        self.assertEqual(filas[0].importe, Decimal("267.00"))
        self.assertEqual(filas[0].employee_name, "Fanny Ortiz")
        self.assertEqual(filas[0].dia.isoformat(), "2026-09-07")
        self.assertEqual(filas[0].hora, 11)

    def test_sin_subtotal_lo_calcula(self) -> None:
        filas = an.desglosar([_op(detalle=[_linea("SKU1", "Short", "8", 2, "89.00")])])
        self.assertEqual(filas[0].importe, Decimal("178.00"))

    def test_los_abonos_no_traen_prendas(self) -> None:
        self.assertEqual(an.desglosar([_op(tipo="abono", detalle=[])]), [])

    def test_los_apartados_si_cuentan(self) -> None:
        filas = an.desglosar([_op(tipo="apartado", detalle=[_linea("SKU9", "Jumper", "10", 1, "500")])])
        self.assertEqual(len(filas), 1)
        self.assertEqual(filas[0].tipo, "apartado")

    def test_datos_raros_no_tumban_el_reporte(self) -> None:
        rows = [_op(detalle=[
            {"sku": "SKU1", "cantidad": 0, "precio": "10"},        # cantidad cero
            {"nombre": "sin sku", "cantidad": 1, "precio": "x"},   # precio inválido
            "basura",                                              # ni siquiera es dict
            _linea("SKU3", "Falda", "12", 1, "215.00"),
        ])]
        filas = an.desglosar(rows)
        self.assertEqual([f.nombre for f in filas], ["sin sku", "Falda"])
        self.assertEqual(filas[0].precio, Decimal("0.00"))

    def test_hora_con_zona_pasa_a_local(self) -> None:
        con_zona = datetime(2026, 9, 7, 18, 0, tzinfo=timezone.utc)
        filas = an.desglosar([_op(hora=con_zona, detalle=[_linea("S", "X", "6", 1, "10")])])
        self.assertIsNone(filas[0].momento.tzinfo)


class EnriquecerTests(unittest.TestCase):
    def test_pega_escuela_y_pieza(self) -> None:
        filas = an.desglosar([_op(detalle=[_linea("SKU1", "Playera", "6", 1, "89")])])
        catalogo = {"SKU1": {"escuela": "Benito Juárez", "tipo_pieza": "Playera",
                             "categoria": "Playeras", "genero": "Unisex", "nivel": "Primaria"}}
        enriquecidas = an.enriquecer(filas, catalogo)
        self.assertEqual(enriquecidas[0].escuela, "Benito Juárez")
        self.assertEqual(enriquecidas[0].nivel, "Primaria")
        self.assertEqual(filas[0].escuela, "")  # el original no se muta

    def test_sku_que_ya_no_existe_se_queda_sin_datos(self) -> None:
        filas = an.desglosar([_op(detalle=[_linea("VIEJO", "Algo", "", 1, "10")])])
        self.assertEqual(an.enriquecer(filas, {"OTRO": {}})[0].escuela, "")


class AgregadosTests(unittest.TestCase):
    def setUp(self) -> None:
        rows = [
            _op(detalle=[_linea("SKU1", "Playera Polo", "6", 3, "89.00", "267.00"),
                         _linea("SKU2", "Calceta", "13-18", 2, "49.00", "98.00")]),
            _op(hora=_LUNES + timedelta(hours=3), emp=("VEND-5", "Stayce Chavarria"), tarjeta=True,
                detalle=[_linea("SKU1", "Playera Polo", "8", 1, "89.00", "89.00")]),
            _op(hora=_LUNES + timedelta(days=1), detalle=[_linea("SKU3", "Falda Escolar", "12", 1, "232.00", "232.00")]),
        ]
        catalogo = {
            "SKU1": {"escuela": "", "tipo_pieza": "Playera", "categoria": "P", "genero": "Unisex", "nivel": ""},
            "SKU2": {"escuela": "", "tipo_pieza": "Calceta", "categoria": "C", "genero": "Unisex", "nivel": ""},
            "SKU3": {"escuela": "Benito Juárez", "tipo_pieza": "Falda", "categoria": "F", "genero": "Mujer", "nivel": "Primaria"},
        }
        self.filas = an.enriquecer(an.desglosar(rows), catalogo)

    def test_por_producto_ordena_por_importe(self) -> None:
        top = an.por_producto(self.filas)
        self.assertEqual(top[0].clave, "Playera Polo")
        self.assertEqual(top[0].piezas, 4)
        self.assertEqual(top[0].importe, Decimal("356.00"))
        self.assertEqual(top[0].precio_promedio, Decimal("89.00"))
        self.assertEqual([g.clave for g in top], ["Playera Polo", "Falda Escolar", "Calceta"])

    def test_por_escuela_marca_las_que_no_tienen(self) -> None:
        grupos = {g.clave: g for g in an.por_escuela(self.filas)}
        self.assertEqual(grupos["Benito Juárez"].importe, Decimal("232.00"))
        self.assertEqual(grupos["(sin escuela)"].piezas, 6)

    def test_por_empleada_y_forma_de_pago(self) -> None:
        emp = {g.clave: g for g in an.por_empleada(self.filas)}
        self.assertEqual(emp["Fanny Ortiz"].importe, Decimal("597.00"))
        self.assertEqual(emp["Stayce Chavarria"].piezas, 1)
        pago = {g.clave: g for g in an.por_forma_pago(self.filas)}
        self.assertEqual(pago["Tarjeta"].importe, Decimal("89.00"))
        self.assertEqual(pago["Efectivo"].importe, Decimal("597.00"))

    def test_por_dia_y_por_hora_van_en_orden(self) -> None:
        self.assertEqual([g.clave for g in an.por_dia(self.filas)], ["2026-09-07", "2026-09-08"])
        self.assertEqual([g.clave for g in an.por_hora(self.filas)], ["11:00", "14:00"])

    def test_por_talla_y_pieza(self) -> None:
        self.assertEqual({g.clave for g in an.por_talla(self.filas)}, {"6", "8", "12", "13-18"})
        self.assertEqual(an.por_pieza(self.filas)[0].clave, "Playera")

    def test_resumen(self) -> None:
        r = an.resumen(self.filas)
        self.assertEqual(r.piezas, 7)
        self.assertEqual(r.importe, Decimal("686.00"))
        self.assertEqual(r.lineas, 4)
        self.assertEqual(r.productos_distintos, 3)
        self.assertEqual(r.escuelas_distintas, 1)
        self.assertEqual(r.ticket_promedio_por_pieza, Decimal("98.00"))

    def test_sin_ventas_no_truena(self) -> None:
        vacio = an.resumen([])
        self.assertEqual(vacio.piezas, 0)
        self.assertEqual(vacio.ticket_promedio_por_pieza, Decimal("0.00"))
        self.assertEqual(an.por_producto([]), [])


if __name__ == "__main__":
    unittest.main()
