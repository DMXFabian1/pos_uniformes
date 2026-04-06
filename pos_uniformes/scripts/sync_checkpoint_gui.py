"""Mini app para marcar y subir checkpoints simples desde Windows o Mac."""

from __future__ import annotations

import sys
from pathlib import Path
import tkinter as tk
from tkinter import messagebox

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.sync_checkpoint_helper import (
    commit_sync_checkpoint,
    format_timestamp_display,
    load_sync_checkpoint_state,
    resolve_project_root,
)


class SyncCheckpointApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.project_root = resolve_project_root(Path(__file__).resolve().parents[1])
        self.root.title("Sincronizacion simple")
        self.root.resizable(False, False)

        frame = tk.Frame(root, padx=18, pady=18)
        frame.pack(fill="both", expand=True)

        title = tk.Label(
            frame,
            text="Sincronizacion Mac / Windows",
            font=("Segoe UI", 14, "bold"),
        )
        title.pack(anchor="w")

        hint = tk.Label(
            frame,
            text="Cada boton hace git add -A, commit y push de la rama actual.",
            font=("Segoe UI", 9),
            justify="left",
        )
        hint.pack(anchor="w", pady=(4, 14))

        self.windows_button = tk.Button(
            frame,
            text="Commit en Windows",
            width=28,
            height=2,
            command=lambda: self._handle_commit("windows"),
        )
        self.windows_button.pack(fill="x")

        self.windows_status_label = tk.Label(frame, anchor="w", justify="left")
        self.windows_status_label.pack(fill="x", pady=(6, 14))

        self.mac_button = tk.Button(
            frame,
            text="Commit en Mac",
            width=28,
            height=2,
            command=lambda: self._handle_commit("mac"),
        )
        self.mac_button.pack(fill="x")

        self.mac_status_label = tk.Label(frame, anchor="w", justify="left")
        self.mac_status_label.pack(fill="x", pady=(6, 14))

        self.result_label = tk.Label(
            frame,
            anchor="w",
            justify="left",
            wraplength=420,
            fg="#1f2937",
        )
        self.result_label.pack(fill="x")

        self._refresh_labels()

    def _refresh_labels(self) -> None:
        state = load_sync_checkpoint_state(self.project_root)
        self.windows_status_label.config(
            text=f"Ultimo Windows: {format_timestamp_display(state.windows_updated_at)}"
        )
        self.mac_status_label.config(
            text=f"Ultimo Mac: {format_timestamp_display(state.mac_updated_at)}"
        )

    def _set_busy(self, busy: bool) -> None:
        state = "disabled" if busy else "normal"
        self.windows_button.config(state=state)
        self.mac_button.config(state=state)
        self.root.update_idletasks()

    def _handle_commit(self, platform: str) -> None:
        self._set_busy(True)
        try:
            result = commit_sync_checkpoint(self.project_root, platform=platform)  # type: ignore[arg-type]
        except Exception as exc:
            self.result_label.config(text=f"Error: {exc}", fg="#991b1b")
            messagebox.showerror("Sincronizacion", str(exc))
        else:
            self.result_label.config(
                text=(
                    f"OK: {platform} actualizado.\n"
                    f"Rama: {result.branch}\n"
                    f"Commit: {result.commit_hash}\n"
                    f"Archivos: {len(result.staged_paths)}"
                ),
                fg="#166534",
            )
            self._refresh_labels()
            messagebox.showinfo(
                "Sincronizacion",
                (
                    f"Se hizo commit y push en {result.branch}.\n"
                    f"Commit: {result.commit_hash}\n"
                    f"Archivos incluidos: {len(result.staged_paths)}"
                ),
            )
        finally:
            self._set_busy(False)


def main() -> int:
    root = tk.Tk()
    SyncCheckpointApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
