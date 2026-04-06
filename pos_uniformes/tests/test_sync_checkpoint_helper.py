from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from utils.sync_checkpoint_helper import (
    SyncCheckpointState,
    format_timestamp_display,
    list_changed_repo_paths,
    load_sync_checkpoint_state,
    resolve_project_root,
    resolve_repo_root,
    save_sync_checkpoint_state,
    stage_sync_checkpoint_changes,
    _is_sync_candidate_path,
)


class SyncCheckpointHelperTests(unittest.TestCase):
    def test_load_sync_checkpoint_state_returns_empty_when_file_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            (project_root / "docs").mkdir()
            (project_root / "scripts").mkdir()

            state = load_sync_checkpoint_state(project_root)

            self.assertEqual(
                state,
                SyncCheckpointState(windows_updated_at=None, mac_updated_at=None),
            )

    def test_save_and_load_sync_checkpoint_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            (project_root / "docs").mkdir()
            (project_root / "scripts").mkdir()

            save_sync_checkpoint_state(
                project_root,
                windows_updated_at="2026-04-06T10:00:00-06:00",
                mac_updated_at="2026-04-06T11:00:00-06:00",
            )

            state = load_sync_checkpoint_state(project_root)

            self.assertEqual(state.windows_updated_at, "2026-04-06T10:00:00-06:00")
            self.assertEqual(state.mac_updated_at, "2026-04-06T11:00:00-06:00")

    def test_format_timestamp_display_returns_never_for_empty(self) -> None:
        self.assertEqual(format_timestamp_display(None), "Nunca")

    def test_resolve_project_root_and_repo_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir) / "repo"
            project_root = repo_root / "pos_uniformes"
            repo_root.mkdir()
            project_root.mkdir()
            (repo_root / ".git").mkdir()
            (project_root / "docs").mkdir()
            (project_root / "scripts").mkdir()
            fake_file = project_root / "scripts" / "sync_checkpoint_gui.py"
            fake_file.write_text("# test\n", encoding="utf-8")

            self.assertEqual(resolve_project_root(fake_file), project_root)
            self.assertEqual(resolve_repo_root(project_root), repo_root)

    def test_is_sync_candidate_path_filters_generated_noise(self) -> None:
        self.assertFalse(_is_sync_candidate_path("pos_uniformes/__pycache__/main.cpython-312.pyc"))
        self.assertFalse(_is_sync_candidate_path("pos_uniformes/generated/labels/standard/SKU000001.png"))
        self.assertFalse(_is_sync_candidate_path("pos_uniformes/packaging/windows/seed/initial.dump"))
        self.assertTrue(_is_sync_candidate_path("pos_uniformes/docs/sync_checkpoint_status.json"))
        self.assertTrue(_is_sync_candidate_path("pos_uniformes/scripts/sync_checkpoint_gui.py"))

    def test_stage_sync_checkpoint_changes_adds_only_useful_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir) / "repo"
            project_root = repo_root / "pos_uniformes"
            repo_root.mkdir()
            project_root.mkdir()
            (repo_root / ".git").mkdir()
            (project_root / "docs").mkdir()
            (project_root / "scripts").mkdir()

            recorded: list[tuple[str, ...]] = []

            def fake_run_git(_repo_root: Path, *args: str) -> str:
                recorded.append(args)
                if args[:3] == ("status", "--porcelain", "--untracked-files=all"):
                    return "\n".join(
                        (
                            " M pos_uniformes/docs/sync_checkpoint_status.json",
                            " M pos_uniformes/scripts/sync_checkpoint_gui.py",
                            " M pos_uniformes/__pycache__/main.cpython-312.pyc",
                            "?? pos_uniformes/generated/labels/standard/SKU000001.png",
                        )
                    )
                return ""

            from utils import sync_checkpoint_helper as helper_module

            original_run_git = helper_module._run_git
            try:
                helper_module._run_git = fake_run_git
                staged = stage_sync_checkpoint_changes(project_root)
            finally:
                helper_module._run_git = original_run_git

            self.assertEqual(
                staged,
                (
                    "pos_uniformes/docs/sync_checkpoint_status.json",
                    "pos_uniformes/scripts/sync_checkpoint_gui.py",
                ),
            )
            add_calls = [args for args in recorded if args[:2] == ("add", "--")]
            self.assertEqual(
                add_calls,
                [
                    ("add", "--", "pos_uniformes/docs/sync_checkpoint_status.json"),
                    ("add", "--", "pos_uniformes/scripts/sync_checkpoint_gui.py"),
                ],
            )

    def test_list_changed_repo_paths_parses_rename(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir) / "repo"
            repo_root.mkdir()

            def fake_run_git(_repo_root: Path, *args: str) -> str:
                self.assertEqual(args, ("status", "--porcelain", "--untracked-files=all"))
                return "R  old_name.py -> pos_uniformes/scripts/new_name.py\n"

            from utils import sync_checkpoint_helper as helper_module

            original_run_git = helper_module._run_git
            try:
                helper_module._run_git = fake_run_git
                changed = list_changed_repo_paths(repo_root)
            finally:
                helper_module._run_git = original_run_git

            self.assertEqual(changed, ("pos_uniformes/scripts/new_name.py",))


if __name__ == "__main__":
    unittest.main()
