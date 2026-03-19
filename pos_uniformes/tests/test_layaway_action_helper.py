from __future__ import annotations

import unittest

from pos_uniformes.ui.helpers.layaway_action_helper import (
    LayawayActionState,
    build_layaway_action_state,
)


class LayawayActionHelperTests(unittest.TestCase):
    def test_build_layaway_action_state(self) -> None:
        state = build_layaway_action_state(
            can_manage_layaways=True,
            can_operate_open_cash=False,
            is_admin=False,
            has_selected_layaway=True,
            has_sale_cart=True,
        )

        self.assertEqual(
            state,
            LayawayActionState(
                create_enabled=False,
                payment_enabled=False,
                deliver_enabled=False,
                cancel_enabled=False,
                receipt_enabled=True,
                sale_ticket_enabled=True,
                whatsapp_enabled=True,
                convert_sale_enabled=False,
                convert_sale_visible=True,
            ),
        )


if __name__ == "__main__":
    unittest.main()
