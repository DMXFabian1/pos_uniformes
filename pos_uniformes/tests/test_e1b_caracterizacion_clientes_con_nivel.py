"""T-B25 (E1-B): caracterización de los clientes CON nivel viejo.

2026-11-12: «el nivel viejo retíralo» (Daniel). La caracterización de E1-A
(descuento 5/10/15/20 en la Caja y los Apartados antiguos, edición que
regresaba al nivel del tipo, recálculo por ventas y aviso de transición) ya
no aplica: esos caminos se retiraron. Lo que queda fijado aquí, para cada
nivel (BASICO, LEAL, PROFESOR, MAYORISTA) con descuento preferente 0 y mayor
que 0:

- Caja antigua: 0 % y etiqueta «Cliente».
- Apartados antiguos: precio de lista.
- Edición (`update_client`): no toca nivel, descuento ni metadatos.
- Credencial: estándar (E1-C2), sin nivel.

Todo corre sin base de datos.
"""

from __future__ import annotations

import unittest
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from pos_uniformes.database.models import Cliente, NivelLealtad, RolUsuario, TipoCliente
from pos_uniformes.services.client_service import ClientService
from pos_uniformes.services.customer_card_service import CustomerCardService
from pos_uniformes.services.layaway_pricing_service import (
    resolve_layaway_client_discount_percent,
    resolve_layaway_unit_price,
)
from pos_uniformes.services.sale_discount_service import normalize_discount_value
from pos_uniformes.services.sale_selected_client_service import (
    load_sale_selected_client_benefit,
    load_sale_selected_client_discount_percent,
    resolve_sale_selected_client_sync_state,
)

NIVELES = (
    (NivelLealtad.BASICO, TipoCliente.GENERAL),
    (NivelLealtad.LEAL, TipoCliente.GENERAL),
    (NivelLealtad.PROFESOR, TipoCliente.PROFESOR),
    (NivelLealtad.MAYORISTA, TipoCliente.MAYORISTA),
    (NivelLealtad.PROFESOR, TipoCliente.GENERAL),  # nivel manual sobre tipo general
)
PREFERENTES = (Decimal("0.00"), Decimal("7.50"))
ADMIN = SimpleNamespace(id=1, rol=RolUsuario.ADMIN, activo=True)
# E1-C2 (C10): la credencial es estándar para todos (D5).
CREDENCIAL_E1C2 = ["", "", "#1F3A44", "#E3EAEC"]


class _SesionFalsa:
    def __init__(self, clientes):
        self._clientes = {c.id: c for c in clientes}

    def get(self, _modelo, cliente_id):
        return self._clientes.get(int(cliente_id))

    def add(self, _obj):
        pass


def _cliente(i, nivel, tipo, preferente):
    return Cliente(
        id=i,
        codigo_cliente=f"CLI-{i:06d}",
        nombre=f"Cliente {i}",
        tipo_cliente=tipo,
        descuento_preferente=preferente,
        nivel_lealtad=nivel,
        telefono="6671234567",
        nivel_asignado_por_user_id=99,
        nivel_asignado_por_rol="ADMIN",
        nivel_asignacion_motivo="original",
        activo=True,
    )


def _estado(c):
    return (
        None if c.nivel_lealtad is None else c.nivel_lealtad.value,
        str(Decimal(str(c.descuento_preferente)).quantize(Decimal("0.01"))),
        c.nivel_asignado_por_user_id,
        c.nivel_asignado_por_rol,
        c.nivel_asignacion_motivo,
    )


class CaracterizacionClientesConNivelTests(unittest.TestCase):
    def test_caja_y_apartados_antiguos_sin_descuento_por_nivel(self) -> None:
        for nivel, tipo in NIVELES:
            for pref in PREFERENTES:
                with self.subTest(nivel=nivel.value, tipo=tipo.value, preferente=str(pref)):
                    s = _SesionFalsa([_cliente(1, nivel, tipo, pref)])
                    b = load_sale_selected_client_benefit(s, selected_client_id=1, normalize_discount_value=normalize_discount_value)
                    self.assertEqual((b.discount_percent, b.source_label), (Decimal("0.00"), "Cliente"))
                    self.assertEqual(
                        load_sale_selected_client_discount_percent(
                            s, selected_client_id=1, normalize_discount_value=normalize_discount_value
                        ),
                        Decimal("0.00"),
                    )
                    sync = resolve_sale_selected_client_sync_state(
                        s, selected_client_id=1, normalize_discount_value=normalize_discount_value
                    )
                    self.assertEqual((sync.locked, sync.discount_percent, sync.source_label), (True, Decimal("0.00"), "Cliente"))
                    pct = resolve_layaway_client_discount_percent(s, selected_client_id=1)
                    self.assertEqual(pct, Decimal("0.00"))
                    self.assertEqual(resolve_layaway_unit_price(Decimal("100.00"), discount_percent=pct), Decimal("100.00"))

    def test_editar_no_toca_el_nivel(self) -> None:
        for nivel, tipo in NIVELES:
            for pref in PREFERENTES:
                for tipo_form in (TipoCliente.GENERAL, TipoCliente.PROFESOR, TipoCliente.MAYORISTA):
                    with self.subTest(nivel=nivel.value, tipo=tipo.value, preferente=str(pref), form=tipo_form.value):
                        c = _cliente(2, nivel, tipo, pref)
                        antes = _estado(c)
                        ClientService.update_client(
                            _SesionFalsa([c]), ADMIN, c, "Editado", tipo_cliente=tipo_form,
                            descuento_preferente=Decimal("12.00"), telefono="667 000 1111", notas="n",
                        )
                        self.assertEqual(_estado(c), antes)
                        self.assertEqual(c.nombre, "Editado")
                        self.assertEqual(c.tipo_cliente, tipo_form)  # el tipo de E1 sí se edita
                        self.assertEqual(c.notas, "n")

    def test_editar_sigue_validando_el_rango_del_descuento(self) -> None:
        c = _cliente(3, NivelLealtad.BASICO, TipoCliente.GENERAL, Decimal("0.00"))
        with self.assertRaises(ValueError):
            ClientService.update_client(_SesionFalsa([c]), ADMIN, c, "X", descuento_preferente=Decimal("120.00"))

    def test_credencial_estandar(self) -> None:
        for nivel, tipo in NIVELES:
            with self.subTest(nivel=nivel.value, tipo=tipo.value):
                cc = _cliente(5, nivel, tipo, Decimal("7.50"))
                with patch(
                    "pos_uniformes.services.customer_card_service.QrGenerator.path_for_client", return_value=Path(__file__)
                ), patch.object(CustomerCardService, "_business_name", return_value="Maximoda"):
                    entrada = CustomerCardService.build_render_input(cc)
                self.assertEqual(
                    [entrada.loyalty_level, entrada.level_label, entrada.primary_color, entrada.secondary_color],
                    CREDENCIAL_E1C2,
                )


if __name__ == "__main__":
    unittest.main()
