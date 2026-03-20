"""Corre una bateria de regresion para flujos criticos del POS."""

from __future__ import annotations

from collections import OrderedDict
from pathlib import Path
import sys
import unittest

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


FLOW_GROUPS: "OrderedDict[str, dict[str, object]]" = OrderedDict(
    [
        (
            "caja_cobro",
            {
                "title": "Caja y Cobro",
                "covers": (
                    "venta con efectivo, transferencia y mixto",
                    "promo manual",
                    "cliente con y sin QR",
                    "apertura, movimiento y corte de caja",
                ),
                "tests": (
                    "pos_uniformes.tests.test_sale_payment_collection_service",
                    "pos_uniformes.tests.test_sale_payment_context_service",
                    "pos_uniformes.tests.test_sale_payment_validation_service",
                    "pos_uniformes.tests.test_sale_payment_note_service",
                    "pos_uniformes.tests.test_sale_discount_context_service",
                    "pos_uniformes.tests.test_manual_promo_flow_service",
                    "pos_uniformes.tests.test_sale_client_discount_flow",
                    "pos_uniformes.tests.test_sale_client_sync_service",
                    "pos_uniformes.tests.test_sale_client_selection_helper",
                    "pos_uniformes.tests.test_scanned_client_flow_service",
                    "pos_uniformes.tests.test_sale_scanned_client_helper",
                    "pos_uniformes.tests.test_sale_checkout_action_service",
                    "pos_uniformes.tests.test_sale_checkout_service",
                    "pos_uniformes.tests.test_cash_session_action_service",
                    "pos_uniformes.tests.test_cash_session_feedback_helper",
                ),
            },
        ),
        (
            "apartados_tickets",
            {
                "title": "Apartados y Tickets",
                "covers": (
                    "crear, abonar, entregar y cancelar apartados",
                    "ver comprobante y ticket",
                ),
                "tests": (
                    "pos_uniformes.tests.test_layaway_creation_service",
                    "pos_uniformes.tests.test_layaway_payment_action_service",
                    "pos_uniformes.tests.test_layaway_closure_service",
                    "pos_uniformes.tests.test_layaway_detail_service",
                    "pos_uniformes.tests.test_sale_document_service",
                    "pos_uniformes.tests.test_sale_document_view_service",
                    "pos_uniformes.tests.test_printable_document_flow_helper",
                    "pos_uniformes.tests.test_sale_ticket_text_service",
                ),
            },
        ),
    ]
)


def _normalize_requested_groups(raw_groups: list[str]) -> list[str]:
    if not raw_groups:
        return list(FLOW_GROUPS.keys())
    normalized: list[str] = []
    for raw_group in raw_groups:
        group = raw_group.strip().lower()
        if not group:
            continue
        if group not in FLOW_GROUPS:
            raise ValueError(
                f"Grupo desconocido: {raw_group}. Usa uno de: {', '.join(FLOW_GROUPS.keys())}"
            )
        normalized.append(group)
    return normalized


def _build_suite(group_names: list[str]) -> unittest.TestSuite:
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for group_name in group_names:
        tests = FLOW_GROUPS[group_name]["tests"]
        assert isinstance(tests, tuple)
        for module_name in tests:
            suite.addTests(loader.loadTestsFromName(module_name))
    return suite


def _print_plan(group_names: list[str]) -> None:
    print("OPERATIONAL FLOW CHECK")
    for group_name in group_names:
        group = FLOW_GROUPS[group_name]
        print(f"\n[{group_name}] {group['title']}")
        covers = group["covers"]
        tests = group["tests"]
        assert isinstance(covers, tuple)
        assert isinstance(tests, tuple)
        print("  Revisa:")
        for item in covers:
            print(f"  - {item}")
        print("  Tests:")
        for module_name in tests:
            print(f"  - {module_name}")


def main(argv: list[str] | None = None) -> int:
    args = list(argv or sys.argv[1:])
    if "--list" in args:
        print("Grupos disponibles:")
        for group_name, group in FLOW_GROUPS.items():
            print(f"- {group_name}: {group['title']}")
        return 0

    try:
        group_names = _normalize_requested_groups(args)
    except ValueError as exc:
        print(f"CHECK FAILED\n{exc}")
        return 2

    _print_plan(group_names)
    suite = _build_suite(group_names)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        print("\nCHECK FAILED")
        return 1

    print("\nCHECK OK")
    print(f"Grupos revisados: {', '.join(group_names)}")
    print(f"Pruebas ejecutadas: {result.testsRun}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
