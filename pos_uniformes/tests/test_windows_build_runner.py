from __future__ import annotations

import unittest
from unittest.mock import patch

from pos_uniformes.scripts import windows_build_runner


class WindowsBuildRunnerTests(unittest.TestCase):
    def test_parse_args_defaults(self) -> None:
        args = windows_build_runner.parse_args([])

        self.assertEqual(args.branch, "")
        self.assertFalse(args.skip_git)
        self.assertFalse(args.skip_install)
        self.assertFalse(args.with_precheck)
        self.assertFalse(args.create_seed_backup)
        self.assertEqual(args.seed_backup_path, "")
        self.assertEqual(args.brother_driver_installer_path, "")
        self.assertFalse(args.dry_run)

    def test_build_bundle_command_includes_selected_options(self) -> None:
        args = windows_build_runner.parse_args(
            [
                "--with-precheck",
                "--seed-backup-path",
                r"C:\respaldos\seed.dump",
                "--brother-driver-installer-path",
                r"C:\drivers\Brother.exe",
            ]
        )

        command = windows_build_runner.build_bundle_command(windows_build_runner.project_root(), args)

        self.assertIn("-WithPrecheck", command)
        self.assertIn("-SeedBackupPath", command)
        self.assertIn(r"C:\respaldos\seed.dump", command)
        self.assertIn("-BrotherDriverInstallerPath", command)
        self.assertIn(r"C:\drivers\Brother.exe", command)

    def test_build_git_commands_uses_checkout_existing_branch(self) -> None:
        with patch("pos_uniformes.scripts.windows_build_runner.local_branch_exists", return_value=True):
            commands = windows_build_runner.build_git_commands(windows_build_runner.project_root(), "codex/etiquetas-windows")

        self.assertEqual(commands[0], ["git", "fetch", "origin", "codex/etiquetas-windows"])
        self.assertEqual(commands[1], ["git", "checkout", "codex/etiquetas-windows"])
        self.assertEqual(commands[2], ["git", "pull", "--ff-only", "origin", "codex/etiquetas-windows"])

    def test_build_git_commands_bootstraps_missing_local_branch(self) -> None:
        with patch("pos_uniformes.scripts.windows_build_runner.local_branch_exists", return_value=False):
            commands = windows_build_runner.build_git_commands(windows_build_runner.project_root(), "codex/etiquetas-windows")

        self.assertEqual(commands[1], ["git", "checkout", "-B", "codex/etiquetas-windows", "origin/codex/etiquetas-windows"])

    def test_validate_args_rejects_duplicate_seed_sources(self) -> None:
        args = windows_build_runner.parse_args(
            [
                "--create-seed-backup",
                "--seed-backup-path",
                r"C:\respaldos\seed.dump",
            ]
        )

        with self.assertRaises(SystemExit):
            windows_build_runner.validate_args(args)


if __name__ == "__main__":
    unittest.main()
