from __future__ import annotations

import unittest
from types import SimpleNamespace

from pos_uniformes.ui.helpers.login_user_list_helper import (
    LoginUserOption,
    build_login_user_options,
)


class LoginUserListHelperTests(unittest.TestCase):
    def test_build_login_user_options_filters_inactive_users(self) -> None:
        users = [
            SimpleNamespace(
                id=1,
                username="admin",
                nombre_completo="Admin Uno POS Uniformes",
                rol="ADMIN",
                activo=True,
            ),
            SimpleNamespace(
                id=2,
                username="caja",
                nombre_completo="Caja Dos",
                rol="CAJERO",
                activo=False,
            ),
        ]

        self.assertEqual(
            build_login_user_options(users),
            [
                LoginUserOption(
                    user_id=1,
                    username="admin",
                    display_label="Admin Uno",
                )
            ],
        )

    def test_build_login_user_options_falls_back_to_username(self) -> None:
        users = [
            SimpleNamespace(
                id=7,
                username="mostrador",
                nombre_completo="",
                rol="RolUsuario.CAJERO",
                activo=True,
            )
        ]

        self.assertEqual(
            build_login_user_options(users),
            [
                LoginUserOption(
                    user_id=7,
                    username="mostrador",
                    display_label="mostrador",
                )
            ],
        )

    def test_build_login_user_options_strips_pos_uniformes_suffix(self) -> None:
        users = [
            SimpleNamespace(
                id=3,
                username="supervisor",
                nombre_completo="Administrador POS Uniformes",
                rol="ADMIN",
                activo=True,
            )
        ]

        self.assertEqual(
            build_login_user_options(users),
            [
                LoginUserOption(
                    user_id=3,
                    username="supervisor",
                    display_label="Administrador",
                )
            ],
        )


if __name__ == "__main__":
    unittest.main()
