"""T-B25 (E1-B): caracterización de los clientes CON nivel.

Fija, para cada nivel (BASICO, LEAL, PROFESOR, MAYORISTA) con descuento
preferente 0 y mayor que 0, lo que hoy producen todos los caminos que E1-B
protege: Caja antigua (% y etiqueta), Apartados antiguos (precio), edición
(`update_client`), recálculo por ventas, `recalculate_all_clients`, aviso de
transición tras venta y entrada de la credencial.

`ESPERADO` se generó ejecutando `caracterizar()` sobre el código de E1-A,
ANTES de cualquier cambio de E1-B, y no debe cambiar después.

Todo corre sin base de datos: las reglas del programa se fijan a los valores
por omisión del código (5/10/15/20, 365 días, 3000, 3 compras y 2000).
"""

from __future__ import annotations

import contextlib
import json
import unittest
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from pos_uniformes.database.models import Cliente, NivelLealtad, RolUsuario, TipoCliente
from pos_uniformes.services import loyalty_service as loyalty_module
from pos_uniformes.services.client_service import ClientService
from pos_uniformes.services.customer_card_service import CustomerCardService
from pos_uniformes.services.layaway_pricing_service import (
    resolve_layaway_client_discount_percent,
    resolve_layaway_unit_price,
)
from pos_uniformes.services.loyalty_service import LoyaltyProgramRules, LoyaltyService
from pos_uniformes.services.sale_checkout_service import (
    load_sale_client_checkout_snapshot,
    resolve_sale_loyalty_transition_notice,
)
from pos_uniformes.services.sale_discount_service import normalize_discount_value
from pos_uniformes.services.sale_selected_client_service import (
    load_sale_selected_client_benefit,
    load_sale_selected_client_discount_percent,
    resolve_sale_selected_client_sync_state,
)

REGLAS = LoyaltyProgramRules(
    review_window_days=365,
    leal_spend_threshold=Decimal("3000.00"),
    leal_purchase_count_threshold=3,
    leal_purchase_sum_threshold=Decimal("2000.00"),
    discount_basico=Decimal("5.00"),
    discount_leal=Decimal("10.00"),
    discount_profesor=Decimal("15.00"),
    discount_mayorista=Decimal("20.00"),
)

NIVELES = (
    (NivelLealtad.BASICO, TipoCliente.GENERAL),
    (NivelLealtad.LEAL, TipoCliente.GENERAL),
    (NivelLealtad.PROFESOR, TipoCliente.PROFESOR),
    (NivelLealtad.MAYORISTA, TipoCliente.MAYORISTA),
    (NivelLealtad.PROFESOR, TipoCliente.GENERAL),  # nivel manual sobre tipo general
)
PREFERENTES = (Decimal("0.00"), Decimal("7.50"))
COMPRAS = ((0, "0.00"), (1, "3500.00"), (3, "2500.00"), (2, "2500.00"))
ADMIN = SimpleNamespace(id=1, rol=RolUsuario.ADMIN, activo=True)


class _SesionFalsa:
    """Lo mínimo que usan los servicios: get, add, execute().one(), scalars().all()."""

    def __init__(self, clientes, compras=(0, "0.00")):
        self._clientes = {c.id: c for c in clientes}
        self._compras = compras

    def get(self, _modelo, cliente_id):
        return self._clientes.get(int(cliente_id))

    def add(self, _obj):
        pass

    def execute(self, _stmt):
        n, total = self._compras
        return SimpleNamespace(one=lambda: (n, Decimal(total)))

    def scalars(self, _stmt):
        return SimpleNamespace(all=lambda: list(self._clientes.values()))


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
    return {
        "nivel": None if c.nivel_lealtad is None else c.nivel_lealtad.value,
        "descuento": str(Decimal(str(c.descuento_preferente)).quantize(Decimal("0.01"))),
        "asignado_por": c.nivel_asignado_por_user_id,
        "rol": c.nivel_asignado_por_rol,
        "motivo": c.nivel_asignacion_motivo,
    }


@contextlib.contextmanager
def _entorno():
    with patch.object(LoyaltyService, "_load_program_rules", return_value=REGLAS), patch.object(
        loyalty_module, "get_session", lambda: contextlib.nullcontext(None)
    ):
        yield


def caracterizar() -> dict:
    r: dict = {}
    with _entorno():
        for nivel, tipo in NIVELES:
            for pref in PREFERENTES:
                clave = f"{nivel.value}/{tipo.value}/{pref}"
                fila: dict = {}
                c = _cliente(1, nivel, tipo, pref)
                s = _SesionFalsa([c])

                b = load_sale_selected_client_benefit(s, selected_client_id=1, normalize_discount_value=normalize_discount_value)
                fila["caja_pct"] = str(b.discount_percent)
                fila["caja_etiqueta"] = b.source_label
                fila["caja_pct_directo"] = str(
                    load_sale_selected_client_discount_percent(s, selected_client_id=1, normalize_discount_value=normalize_discount_value)
                )
                sync = resolve_sale_selected_client_sync_state(s, selected_client_id=1, normalize_discount_value=normalize_discount_value)
                fila["caja_sync"] = [sync.locked, str(sync.discount_percent), sync.source_label]

                pct = resolve_layaway_client_discount_percent(s, selected_client_id=1)
                fila["apartado_pct"] = str(pct)
                fila["apartado_precio_100"] = str(resolve_layaway_unit_price(Decimal("100.00"), discount_percent=pct))

                for tipo_form in (TipoCliente.GENERAL, TipoCliente.PROFESOR):
                    ce = _cliente(2, nivel, tipo, pref)
                    ClientService.update_client(
                        _SesionFalsa([ce]), ADMIN, ce, "Editado", tipo_cliente=tipo_form,
                        descuento_preferente=Decimal("12.00"), telefono="667 000 1111", notas="n",
                    )
                    fila[f"editar_{tipo_form.value}"] = _estado(ce)

                for n, total in COMPRAS:
                    cr = _cliente(3, nivel, tipo, pref)
                    LoyaltyService.refresh_client_level_from_sales(
                        _SesionFalsa([cr], (n, total)), cr, actor_user=ADMIN, reason="venta_confirmada"
                    )
                    fila[f"recalculo_{n}_{total}"] = _estado(cr)

                cn = _cliente(4, nivel, tipo, pref)
                sn = _SesionFalsa([cn], (1, "3500.00"))
                snap = load_sale_client_checkout_snapshot(sn, selected_client_id=4)
                LoyaltyService.refresh_client_level_from_sales(sn, cn, actor_user=ADMIN, reason="venta_confirmada")
                fila["aviso_transicion"] = resolve_sale_loyalty_transition_notice(
                    snap, build_notice=lambda nombre, antes, despues, d: f"{nombre}|{antes}|{despues}|{d}"
                )

                cc = _cliente(5, nivel, tipo, pref)
                with patch("pos_uniformes.services.customer_card_service.QrGenerator.path_for_client", return_value=Path(__file__)), patch.object(
                    CustomerCardService, "_business_name", return_value="Maximoda"
                ):
                    entrada = CustomerCardService.build_render_input(cc)
                fila["credencial"] = [entrada.loyalty_level, entrada.level_label, entrada.primary_color, entrada.secondary_color]
                r[clave] = fila

        # recalculate_all_clients con todos los niveles juntos
        todos = [_cliente(100 + i, nivel, tipo, pref) for i, ((nivel, tipo), pref) in enumerate(
            [(nt, p) for nt in NIVELES for p in PREFERENTES]
        )]
        resumen = LoyaltyService.recalculate_all_clients(_SesionFalsa(todos, (1, "3500.00")), actor_user=ADMIN, reason="recalculo")
        r["recalcular_todos"] = {"resumen": resumen, "clientes": [_estado(c) for c in todos]}
    return json.loads(json.dumps(r, default=str))


# Generado con caracterizar() sobre el código de E1-A (antes de E1-B), 2026-11-10.
ESPERADO = {'BASICO/GENERAL/0.00': {'apartado_pct': '5.00',
                         'apartado_precio_100': '95.00',
                         'aviso_transicion': 'Cliente 4|Basico|Leal|10.00',
                         'caja_etiqueta': 'Basico',
                         'caja_pct': '5.00',
                         'caja_pct_directo': '5.00',
                         'caja_sync': [True, '5.00', 'Basico'],
                         'credencial': ['BASICO', 'Basico', '#3A3A3A', '#E6E1DB'],
                         'editar_GENERAL': {'asignado_por': 1,
                                            'descuento': '5.00',
                                            'motivo': 'actualizacion_cliente',
                                            'nivel': 'BASICO',
                                            'rol': 'ADMIN'},
                         'editar_PROFESOR': {'asignado_por': 1,
                                             'descuento': '15.00',
                                             'motivo': 'actualizacion_cliente',
                                             'nivel': 'PROFESOR',
                                             'rol': 'ADMIN'},
                         'recalculo_0_0.00': {'asignado_por': 1,
                                              'descuento': '5.00',
                                              'motivo': 'venta_confirmada',
                                              'nivel': 'BASICO',
                                              'rol': 'ADMIN'},
                         'recalculo_1_3500.00': {'asignado_por': 1,
                                                 'descuento': '10.00',
                                                 'motivo': 'venta_confirmada',
                                                 'nivel': 'LEAL',
                                                 'rol': 'ADMIN'},
                         'recalculo_2_2500.00': {'asignado_por': 1,
                                                 'descuento': '5.00',
                                                 'motivo': 'venta_confirmada',
                                                 'nivel': 'BASICO',
                                                 'rol': 'ADMIN'},
                         'recalculo_3_2500.00': {'asignado_por': 1,
                                                 'descuento': '10.00',
                                                 'motivo': 'venta_confirmada',
                                                 'nivel': 'LEAL',
                                                 'rol': 'ADMIN'}},
 'BASICO/GENERAL/7.50': {'apartado_pct': '7.50',
                         'apartado_precio_100': '92.50',
                         'aviso_transicion': 'Cliente 4|Basico|Leal|10.00',
                         'caja_etiqueta': 'Basico',
                         'caja_pct': '7.50',
                         'caja_pct_directo': '7.50',
                         'caja_sync': [True, '7.50', 'Basico'],
                         'credencial': ['BASICO', 'Basico', '#3A3A3A', '#E6E1DB'],
                         'editar_GENERAL': {'asignado_por': 1,
                                            'descuento': '5.00',
                                            'motivo': 'actualizacion_cliente',
                                            'nivel': 'BASICO',
                                            'rol': 'ADMIN'},
                         'editar_PROFESOR': {'asignado_por': 1,
                                             'descuento': '15.00',
                                             'motivo': 'actualizacion_cliente',
                                             'nivel': 'PROFESOR',
                                             'rol': 'ADMIN'},
                         'recalculo_0_0.00': {'asignado_por': 1,
                                              'descuento': '5.00',
                                              'motivo': 'venta_confirmada',
                                              'nivel': 'BASICO',
                                              'rol': 'ADMIN'},
                         'recalculo_1_3500.00': {'asignado_por': 1,
                                                 'descuento': '10.00',
                                                 'motivo': 'venta_confirmada',
                                                 'nivel': 'LEAL',
                                                 'rol': 'ADMIN'},
                         'recalculo_2_2500.00': {'asignado_por': 1,
                                                 'descuento': '5.00',
                                                 'motivo': 'venta_confirmada',
                                                 'nivel': 'BASICO',
                                                 'rol': 'ADMIN'},
                         'recalculo_3_2500.00': {'asignado_por': 1,
                                                 'descuento': '10.00',
                                                 'motivo': 'venta_confirmada',
                                                 'nivel': 'LEAL',
                                                 'rol': 'ADMIN'}},
 'LEAL/GENERAL/0.00': {'apartado_pct': '10.00',
                       'apartado_precio_100': '90.00',
                       'aviso_transicion': 'Cliente 4|Leal|Leal|10.00',
                       'caja_etiqueta': 'Leal',
                       'caja_pct': '10.00',
                       'caja_pct_directo': '10.00',
                       'caja_sync': [True, '10.00', 'Leal'],
                       'credencial': ['LEAL', 'Leal', '#C65A1E', '#F3E1D5'],
                       'editar_GENERAL': {'asignado_por': 1,
                                          'descuento': '5.00',
                                          'motivo': 'actualizacion_cliente',
                                          'nivel': 'BASICO',
                                          'rol': 'ADMIN'},
                       'editar_PROFESOR': {'asignado_por': 1,
                                           'descuento': '15.00',
                                           'motivo': 'actualizacion_cliente',
                                           'nivel': 'PROFESOR',
                                           'rol': 'ADMIN'},
                       'recalculo_0_0.00': {'asignado_por': 1,
                                            'descuento': '5.00',
                                            'motivo': 'venta_confirmada',
                                            'nivel': 'BASICO',
                                            'rol': 'ADMIN'},
                       'recalculo_1_3500.00': {'asignado_por': 1,
                                               'descuento': '10.00',
                                               'motivo': 'venta_confirmada',
                                               'nivel': 'LEAL',
                                               'rol': 'ADMIN'},
                       'recalculo_2_2500.00': {'asignado_por': 1,
                                               'descuento': '5.00',
                                               'motivo': 'venta_confirmada',
                                               'nivel': 'BASICO',
                                               'rol': 'ADMIN'},
                       'recalculo_3_2500.00': {'asignado_por': 1,
                                               'descuento': '10.00',
                                               'motivo': 'venta_confirmada',
                                               'nivel': 'LEAL',
                                               'rol': 'ADMIN'}},
 'LEAL/GENERAL/7.50': {'apartado_pct': '7.50',
                       'apartado_precio_100': '92.50',
                       'aviso_transicion': 'Cliente 4|Leal|Leal|10.00',
                       'caja_etiqueta': 'Leal',
                       'caja_pct': '7.50',
                       'caja_pct_directo': '7.50',
                       'caja_sync': [True, '7.50', 'Leal'],
                       'credencial': ['LEAL', 'Leal', '#C65A1E', '#F3E1D5'],
                       'editar_GENERAL': {'asignado_por': 1,
                                          'descuento': '5.00',
                                          'motivo': 'actualizacion_cliente',
                                          'nivel': 'BASICO',
                                          'rol': 'ADMIN'},
                       'editar_PROFESOR': {'asignado_por': 1,
                                           'descuento': '15.00',
                                           'motivo': 'actualizacion_cliente',
                                           'nivel': 'PROFESOR',
                                           'rol': 'ADMIN'},
                       'recalculo_0_0.00': {'asignado_por': 1,
                                            'descuento': '5.00',
                                            'motivo': 'venta_confirmada',
                                            'nivel': 'BASICO',
                                            'rol': 'ADMIN'},
                       'recalculo_1_3500.00': {'asignado_por': 1,
                                               'descuento': '10.00',
                                               'motivo': 'venta_confirmada',
                                               'nivel': 'LEAL',
                                               'rol': 'ADMIN'},
                       'recalculo_2_2500.00': {'asignado_por': 1,
                                               'descuento': '5.00',
                                               'motivo': 'venta_confirmada',
                                               'nivel': 'BASICO',
                                               'rol': 'ADMIN'},
                       'recalculo_3_2500.00': {'asignado_por': 1,
                                               'descuento': '10.00',
                                               'motivo': 'venta_confirmada',
                                               'nivel': 'LEAL',
                                               'rol': 'ADMIN'}},
 'MAYORISTA/MAYORISTA/0.00': {'apartado_pct': '20.00',
                              'apartado_precio_100': '80.00',
                              'aviso_transicion': 'Cliente 4|Mayorista|Mayorista|20.00',
                              'caja_etiqueta': 'Mayorista',
                              'caja_pct': '20.00',
                              'caja_pct_directo': '20.00',
                              'caja_sync': [True, '20.00', 'Mayorista'],
                              'credencial': ['MAYORISTA', 'Mayorista', '#C2A24A', '#F2E9C9'],
                              'editar_GENERAL': {'asignado_por': 1,
                                                 'descuento': '5.00',
                                                 'motivo': 'actualizacion_cliente',
                                                 'nivel': 'BASICO',
                                                 'rol': 'ADMIN'},
                              'editar_PROFESOR': {'asignado_por': 1,
                                                  'descuento': '15.00',
                                                  'motivo': 'actualizacion_cliente',
                                                  'nivel': 'PROFESOR',
                                                  'rol': 'ADMIN'},
                              'recalculo_0_0.00': {'asignado_por': 1,
                                                   'descuento': '20.00',
                                                   'motivo': 'venta_confirmada',
                                                   'nivel': 'MAYORISTA',
                                                   'rol': 'ADMIN'},
                              'recalculo_1_3500.00': {'asignado_por': 1,
                                                      'descuento': '20.00',
                                                      'motivo': 'venta_confirmada',
                                                      'nivel': 'MAYORISTA',
                                                      'rol': 'ADMIN'},
                              'recalculo_2_2500.00': {'asignado_por': 1,
                                                      'descuento': '20.00',
                                                      'motivo': 'venta_confirmada',
                                                      'nivel': 'MAYORISTA',
                                                      'rol': 'ADMIN'},
                              'recalculo_3_2500.00': {'asignado_por': 1,
                                                      'descuento': '20.00',
                                                      'motivo': 'venta_confirmada',
                                                      'nivel': 'MAYORISTA',
                                                      'rol': 'ADMIN'}},
 'MAYORISTA/MAYORISTA/7.50': {'apartado_pct': '7.50',
                              'apartado_precio_100': '92.50',
                              'aviso_transicion': 'Cliente 4|Mayorista|Mayorista|20.00',
                              'caja_etiqueta': 'Mayorista',
                              'caja_pct': '7.50',
                              'caja_pct_directo': '7.50',
                              'caja_sync': [True, '7.50', 'Mayorista'],
                              'credencial': ['MAYORISTA', 'Mayorista', '#C2A24A', '#F2E9C9'],
                              'editar_GENERAL': {'asignado_por': 1,
                                                 'descuento': '5.00',
                                                 'motivo': 'actualizacion_cliente',
                                                 'nivel': 'BASICO',
                                                 'rol': 'ADMIN'},
                              'editar_PROFESOR': {'asignado_por': 1,
                                                  'descuento': '15.00',
                                                  'motivo': 'actualizacion_cliente',
                                                  'nivel': 'PROFESOR',
                                                  'rol': 'ADMIN'},
                              'recalculo_0_0.00': {'asignado_por': 1,
                                                   'descuento': '20.00',
                                                   'motivo': 'venta_confirmada',
                                                   'nivel': 'MAYORISTA',
                                                   'rol': 'ADMIN'},
                              'recalculo_1_3500.00': {'asignado_por': 1,
                                                      'descuento': '20.00',
                                                      'motivo': 'venta_confirmada',
                                                      'nivel': 'MAYORISTA',
                                                      'rol': 'ADMIN'},
                              'recalculo_2_2500.00': {'asignado_por': 1,
                                                      'descuento': '20.00',
                                                      'motivo': 'venta_confirmada',
                                                      'nivel': 'MAYORISTA',
                                                      'rol': 'ADMIN'},
                              'recalculo_3_2500.00': {'asignado_por': 1,
                                                      'descuento': '20.00',
                                                      'motivo': 'venta_confirmada',
                                                      'nivel': 'MAYORISTA',
                                                      'rol': 'ADMIN'}},
 'PROFESOR/GENERAL/0.00': {'apartado_pct': '15.00',
                           'apartado_precio_100': '85.00',
                           'aviso_transicion': 'Cliente 4|Profesor|Profesor|15.00',
                           'caja_etiqueta': 'Profesor',
                           'caja_pct': '15.00',
                           'caja_pct_directo': '15.00',
                           'caja_sync': [True, '15.00', 'Profesor'],
                           'credencial': ['PROFESOR', 'Profesor', '#1F3A44', '#D7E3E7'],
                           'editar_GENERAL': {'asignado_por': 1,
                                              'descuento': '5.00',
                                              'motivo': 'actualizacion_cliente',
                                              'nivel': 'BASICO',
                                              'rol': 'ADMIN'},
                           'editar_PROFESOR': {'asignado_por': 1,
                                               'descuento': '15.00',
                                               'motivo': 'actualizacion_cliente',
                                               'nivel': 'PROFESOR',
                                               'rol': 'ADMIN'},
                           'recalculo_0_0.00': {'asignado_por': 1,
                                                'descuento': '15.00',
                                                'motivo': 'venta_confirmada',
                                                'nivel': 'PROFESOR',
                                                'rol': 'ADMIN'},
                           'recalculo_1_3500.00': {'asignado_por': 1,
                                                   'descuento': '15.00',
                                                   'motivo': 'venta_confirmada',
                                                   'nivel': 'PROFESOR',
                                                   'rol': 'ADMIN'},
                           'recalculo_2_2500.00': {'asignado_por': 1,
                                                   'descuento': '15.00',
                                                   'motivo': 'venta_confirmada',
                                                   'nivel': 'PROFESOR',
                                                   'rol': 'ADMIN'},
                           'recalculo_3_2500.00': {'asignado_por': 1,
                                                   'descuento': '15.00',
                                                   'motivo': 'venta_confirmada',
                                                   'nivel': 'PROFESOR',
                                                   'rol': 'ADMIN'}},
 'PROFESOR/GENERAL/7.50': {'apartado_pct': '7.50',
                           'apartado_precio_100': '92.50',
                           'aviso_transicion': 'Cliente 4|Profesor|Profesor|15.00',
                           'caja_etiqueta': 'Profesor',
                           'caja_pct': '7.50',
                           'caja_pct_directo': '7.50',
                           'caja_sync': [True, '7.50', 'Profesor'],
                           'credencial': ['PROFESOR', 'Profesor', '#1F3A44', '#D7E3E7'],
                           'editar_GENERAL': {'asignado_por': 1,
                                              'descuento': '5.00',
                                              'motivo': 'actualizacion_cliente',
                                              'nivel': 'BASICO',
                                              'rol': 'ADMIN'},
                           'editar_PROFESOR': {'asignado_por': 1,
                                               'descuento': '15.00',
                                               'motivo': 'actualizacion_cliente',
                                               'nivel': 'PROFESOR',
                                               'rol': 'ADMIN'},
                           'recalculo_0_0.00': {'asignado_por': 1,
                                                'descuento': '15.00',
                                                'motivo': 'venta_confirmada',
                                                'nivel': 'PROFESOR',
                                                'rol': 'ADMIN'},
                           'recalculo_1_3500.00': {'asignado_por': 1,
                                                   'descuento': '15.00',
                                                   'motivo': 'venta_confirmada',
                                                   'nivel': 'PROFESOR',
                                                   'rol': 'ADMIN'},
                           'recalculo_2_2500.00': {'asignado_por': 1,
                                                   'descuento': '15.00',
                                                   'motivo': 'venta_confirmada',
                                                   'nivel': 'PROFESOR',
                                                   'rol': 'ADMIN'},
                           'recalculo_3_2500.00': {'asignado_por': 1,
                                                   'descuento': '15.00',
                                                   'motivo': 'venta_confirmada',
                                                   'nivel': 'PROFESOR',
                                                   'rol': 'ADMIN'}},
 'PROFESOR/PROFESOR/0.00': {'apartado_pct': '15.00',
                            'apartado_precio_100': '85.00',
                            'aviso_transicion': 'Cliente 4|Profesor|Profesor|15.00',
                            'caja_etiqueta': 'Profesor',
                            'caja_pct': '15.00',
                            'caja_pct_directo': '15.00',
                            'caja_sync': [True, '15.00', 'Profesor'],
                            'credencial': ['PROFESOR', 'Profesor', '#1F3A44', '#D7E3E7'],
                            'editar_GENERAL': {'asignado_por': 1,
                                               'descuento': '5.00',
                                               'motivo': 'actualizacion_cliente',
                                               'nivel': 'BASICO',
                                               'rol': 'ADMIN'},
                            'editar_PROFESOR': {'asignado_por': 1,
                                                'descuento': '15.00',
                                                'motivo': 'actualizacion_cliente',
                                                'nivel': 'PROFESOR',
                                                'rol': 'ADMIN'},
                            'recalculo_0_0.00': {'asignado_por': 1,
                                                 'descuento': '15.00',
                                                 'motivo': 'venta_confirmada',
                                                 'nivel': 'PROFESOR',
                                                 'rol': 'ADMIN'},
                            'recalculo_1_3500.00': {'asignado_por': 1,
                                                    'descuento': '15.00',
                                                    'motivo': 'venta_confirmada',
                                                    'nivel': 'PROFESOR',
                                                    'rol': 'ADMIN'},
                            'recalculo_2_2500.00': {'asignado_por': 1,
                                                    'descuento': '15.00',
                                                    'motivo': 'venta_confirmada',
                                                    'nivel': 'PROFESOR',
                                                    'rol': 'ADMIN'},
                            'recalculo_3_2500.00': {'asignado_por': 1,
                                                    'descuento': '15.00',
                                                    'motivo': 'venta_confirmada',
                                                    'nivel': 'PROFESOR',
                                                    'rol': 'ADMIN'}},
 'PROFESOR/PROFESOR/7.50': {'apartado_pct': '7.50',
                            'apartado_precio_100': '92.50',
                            'aviso_transicion': 'Cliente 4|Profesor|Profesor|15.00',
                            'caja_etiqueta': 'Profesor',
                            'caja_pct': '7.50',
                            'caja_pct_directo': '7.50',
                            'caja_sync': [True, '7.50', 'Profesor'],
                            'credencial': ['PROFESOR', 'Profesor', '#1F3A44', '#D7E3E7'],
                            'editar_GENERAL': {'asignado_por': 1,
                                               'descuento': '5.00',
                                               'motivo': 'actualizacion_cliente',
                                               'nivel': 'BASICO',
                                               'rol': 'ADMIN'},
                            'editar_PROFESOR': {'asignado_por': 1,
                                                'descuento': '15.00',
                                                'motivo': 'actualizacion_cliente',
                                                'nivel': 'PROFESOR',
                                                'rol': 'ADMIN'},
                            'recalculo_0_0.00': {'asignado_por': 1,
                                                 'descuento': '15.00',
                                                 'motivo': 'venta_confirmada',
                                                 'nivel': 'PROFESOR',
                                                 'rol': 'ADMIN'},
                            'recalculo_1_3500.00': {'asignado_por': 1,
                                                    'descuento': '15.00',
                                                    'motivo': 'venta_confirmada',
                                                    'nivel': 'PROFESOR',
                                                    'rol': 'ADMIN'},
                            'recalculo_2_2500.00': {'asignado_por': 1,
                                                    'descuento': '15.00',
                                                    'motivo': 'venta_confirmada',
                                                    'nivel': 'PROFESOR',
                                                    'rol': 'ADMIN'},
                            'recalculo_3_2500.00': {'asignado_por': 1,
                                                    'descuento': '15.00',
                                                    'motivo': 'venta_confirmada',
                                                    'nivel': 'PROFESOR',
                                                    'rol': 'ADMIN'}},
 'recalcular_todos': {'clientes': [{'asignado_por': 1,
                                    'descuento': '10.00',
                                    'motivo': 'recalculo',
                                    'nivel': 'LEAL',
                                    'rol': 'ADMIN'},
                                   {'asignado_por': 1,
                                    'descuento': '10.00',
                                    'motivo': 'recalculo',
                                    'nivel': 'LEAL',
                                    'rol': 'ADMIN'},
                                   {'asignado_por': 1,
                                    'descuento': '10.00',
                                    'motivo': 'recalculo',
                                    'nivel': 'LEAL',
                                    'rol': 'ADMIN'},
                                   {'asignado_por': 1,
                                    'descuento': '10.00',
                                    'motivo': 'recalculo',
                                    'nivel': 'LEAL',
                                    'rol': 'ADMIN'},
                                   {'asignado_por': 1,
                                    'descuento': '15.00',
                                    'motivo': 'recalculo',
                                    'nivel': 'PROFESOR',
                                    'rol': 'ADMIN'},
                                   {'asignado_por': 1,
                                    'descuento': '15.00',
                                    'motivo': 'recalculo',
                                    'nivel': 'PROFESOR',
                                    'rol': 'ADMIN'},
                                   {'asignado_por': 1,
                                    'descuento': '20.00',
                                    'motivo': 'recalculo',
                                    'nivel': 'MAYORISTA',
                                    'rol': 'ADMIN'},
                                   {'asignado_por': 1,
                                    'descuento': '20.00',
                                    'motivo': 'recalculo',
                                    'nivel': 'MAYORISTA',
                                    'rol': 'ADMIN'},
                                   {'asignado_por': 1,
                                    'descuento': '15.00',
                                    'motivo': 'recalculo',
                                    'nivel': 'PROFESOR',
                                    'rol': 'ADMIN'},
                                   {'asignado_por': 1,
                                    'descuento': '15.00',
                                    'motivo': 'recalculo',
                                    'nivel': 'PROFESOR',
                                    'rol': 'ADMIN'}],
                      'resumen': {'changed': 10, 'total': 10}}}


# E1-C2 (C10): la credencial pasó a ser estándar para todos (D5): sin nivel,
# con colores fijos y el código del cliente. `ESPERADO` se conserva tal como
# se generó sobre E1-A; solo la sección `credencial` se compara contra esto.
# Todo lo demás (caja, apartados, edición vieja, recálculo) debe seguir igual.
CREDENCIAL_E1C2 = ["", "", "#1F3A44", "#E3EAEC"]

# 2026-11-12 (una sola regla para Leal): la revisión automática por ventas ya
# no baja a nadie de LEAL a BASICO, igual que la subida a Maximoda Leal
# («creo que es la misma», Daniel). Un cliente LEAL sin el gasto del año se
# queda como estaba: nivel, descuento y quién lo asignó. `ESPERADO` se
# conserva tal como se generó sobre E1-A; estos casos se comparan contra esto.
def _leal_sin_tocar(preferente: str) -> dict:
    return {"asignado_por": 99, "descuento": preferente, "motivo": "original", "nivel": "LEAL", "rol": "ADMIN"}


LEAL_NO_BAJA_2026_11_12 = {
    f"LEAL/GENERAL/{pref}": {
        "recalculo_0_0.00": _leal_sin_tocar(pref),
        "recalculo_2_2500.00": _leal_sin_tocar(pref),
    }
    for pref in ("0.00", "7.50")
}


class CaracterizacionClientesConNivelTests(unittest.TestCase):
    def test_los_clientes_con_nivel_se_comportan_igual_que_en_e1a(self) -> None:
        obtenido = caracterizar()
        self.assertIsNotNone(ESPERADO)
        self.assertEqual(set(obtenido), set(ESPERADO))
        for clave in ESPERADO:
            with self.subTest(caso=clave):
                if isinstance(ESPERADO[clave], dict) and "credencial" in ESPERADO[clave]:
                    esperado = {k: v for k, v in ESPERADO[clave].items() if k != "credencial"}
                    esperado.update(LEAL_NO_BAJA_2026_11_12.get(clave, {}))
                    actual = {k: v for k, v in obtenido[clave].items() if k != "credencial"}
                    self.assertEqual(actual, esperado)
                    self.assertEqual(obtenido[clave]["credencial"], CREDENCIAL_E1C2)
                else:
                    self.assertEqual(obtenido[clave], ESPERADO[clave])


if __name__ == "__main__":
    print(json.dumps(caracterizar(), indent=1, ensure_ascii=False, sort_keys=True))
