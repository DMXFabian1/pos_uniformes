"""Recibe cambios remotos del repo sin pisar trabajo local por accidente."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Actualiza la rama local desde el remoto de forma segura.",
    )
    parser.add_argument(
        "--branch",
        help="Rama a recibir. Si no se indica, usa la rama actual.",
    )
    parser.add_argument(
        "--remote",
        default="origin",
        help="Nombre del remoto. Default: origin",
    )
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="Permite continuar aunque existan cambios locales sin commit.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Muestra los comandos sin ejecutarlos.",
    )
    return parser.parse_args(argv)


def run_git(args: list[str], *, root: Path, dry_run: bool, capture_output: bool = False) -> str:
    command = ["git", *args]
    printable = " ".join(command)
    print(f"$ {printable}")
    if dry_run:
        return ""
    completed = subprocess.run(
        command,
        cwd=root,
        check=True,
        text=True,
        capture_output=capture_output,
    )
    return completed.stdout.strip() if capture_output else ""


def current_branch(*, root: Path, dry_run: bool) -> str:
    if dry_run:
        return "main"
    branch = run_git(["branch", "--show-current"], root=root, dry_run=False, capture_output=True)
    if not branch:
        raise RuntimeError("No fue posible detectar la rama actual.")
    return branch


def ensure_clean_worktree(*, root: Path, allow_dirty: bool, dry_run: bool) -> None:
    if dry_run or allow_dirty:
        return
    status = run_git(["status", "--porcelain"], root=root, dry_run=False, capture_output=True)
    if status.strip():
        raise RuntimeError(
            "Hay cambios locales sin commit. Haz commit, stash o usa --allow-dirty si quieres continuar."
        )


def local_branch_exists(branch: str, *, root: Path, dry_run: bool) -> bool:
    if dry_run:
        return True
    result = subprocess.run(
        ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"],
        cwd=root,
        text=True,
    )
    return result.returncode == 0


def remote_branch_exists(branch: str, *, root: Path, remote: str, dry_run: bool) -> bool:
    if dry_run:
        return True
    result = subprocess.run(
        ["git", "ls-remote", "--exit-code", "--heads", remote, branch],
        cwd=root,
        text=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0


def ensure_branch_checked_out(branch: str, *, root: Path, remote: str, dry_run: bool) -> None:
    current = current_branch(root=root, dry_run=dry_run)
    if current == branch:
        return

    if local_branch_exists(branch, root=root, dry_run=dry_run):
        run_git(["checkout", branch], root=root, dry_run=dry_run)
        return

    if not remote_branch_exists(branch, root=root, remote=remote, dry_run=dry_run):
        raise RuntimeError(f"La rama '{branch}' no existe ni localmente ni en {remote}.")

    run_git(
        ["checkout", "-b", branch, "--track", f"{remote}/{branch}"],
        root=root,
        dry_run=dry_run,
    )


def receive_updates(*, root: Path, branch: str, remote: str, dry_run: bool) -> None:
    run_git(["fetch", remote], root=root, dry_run=dry_run)
    ensure_branch_checked_out(branch, root=root, remote=remote, dry_run=dry_run)
    run_git(["pull", "--ff-only", remote, branch], root=root, dry_run=dry_run)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = project_root()
    ensure_clean_worktree(
        root=root,
        allow_dirty=args.allow_dirty,
        dry_run=args.dry_run,
    )
    branch = args.branch or current_branch(root=root, dry_run=args.dry_run)
    print(f"Repo: {root}")
    print(f"Rama objetivo: {branch}")
    print(f"Remoto: {args.remote}")
    receive_updates(
        root=root,
        branch=branch,
        remote=args.remote,
        dry_run=args.dry_run,
    )
    print("")
    print("Actualizacion completada.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
