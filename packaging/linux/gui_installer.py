#!/usr/bin/env python3
from __future__ import annotations

import os
import shutil
import stat
import sys
from pathlib import Path
from tkinter import BooleanVar, StringVar, Tk, filedialog, messagebox, ttk


APP_NAME = "Astro AI Processor"
APP_DISPLAY_NAME = "Astro AI Processor"
APP_ID = "astro-ai-processor"
BUNDLE_DIR_NAME = "Astro AI Processor"


def source_candidates() -> list[Path]:
    candidates: list[Path] = []

    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass) / BUNDLE_DIR_NAME)

    if getattr(sys, "frozen", False):
        base = Path(sys.executable).resolve().parent
    else:
        base = Path(__file__).resolve().parent

    candidates.extend(
        [
            base / BUNDLE_DIR_NAME,
            base / "dist" / BUNDLE_DIR_NAME,
            Path.cwd() / BUNDLE_DIR_NAME,
        ]
    )
    return candidates


def find_source_dir() -> Path | None:
    for candidate in source_candidates():
        if (candidate / APP_NAME).is_file() and (candidate / "_internal").is_dir():
            return candidate
    return None


def write_launcher(install_dir: Path) -> Path:
    launcher_path = install_dir / APP_ID
    launcher_path.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        f'exec "{install_dir / APP_NAME}" "$@"\n',
        encoding="utf-8",
    )
    launcher_path.chmod(0o755)
    return launcher_path


def resolve_icon(install_dir: Path) -> Path | None:
    first = install_dir / "assets" / "favicon.ico"
    if first.is_file():
        return first
    second = install_dir / "_internal" / "assets" / "favicon.ico"
    if second.is_file():
        return second
    return None


def desktop_entry_content(launcher_path: Path, install_dir: Path, icon_path: Path | None) -> str:
    icon_value = str(icon_path) if icon_path else ""
    return "\n".join(
        [
            "[Desktop Entry]",
            "Version=1.0",
            "Type=Application",
            f"Name={APP_DISPLAY_NAME}",
            "Comment=Astrophotography processing application",
            f"Exec={launcher_path} %F",
            f"Path={install_dir}",
            f"Icon={icon_value}",
            "Terminal=false",
            "Categories=Graphics;Photography;Science;",
            "StartupNotify=true",
            "",
        ]
    )


def write_desktop_file(path: Path, launcher_path: Path, install_dir: Path, icon_path: Path | None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(desktop_entry_content(launcher_path, install_dir, icon_path), encoding="utf-8")
    path.chmod(0o644)


def copy_bundle(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, symlinks=True)

    app_exec = dst / APP_NAME
    mode = app_exec.stat().st_mode
    app_exec.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


class InstallerUI:
    def __init__(self) -> None:
        self.root = Tk()
        self.root.title(f"{APP_DISPLAY_NAME} - Instalator")
        self.root.resizable(False, False)
        self.root.geometry("640x320")

        self.install_path = StringVar(value=str(Path.home() / ".local" / "opt" / APP_ID))
        self.shortcut_desktop = BooleanVar(value=True)
        self.status = StringVar(value="Gotowe do instalacji.")

        frame = ttk.Frame(self.root, padding=20)
        frame.pack(fill="both", expand=True)

        ttk.Label(
            frame,
            text="Instalator Astro AI Processor",
            font=("Sans", 14, "bold"),
        ).grid(row=0, column=0, columnspan=3, sticky="w")

        ttk.Label(
            frame,
            text="Wybierz miejsce instalacji i kliknij Zainstaluj.",
        ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(8, 16))

        ttk.Label(frame, text="Folder instalacji:").grid(row=2, column=0, sticky="w")
        ttk.Entry(frame, textvariable=self.install_path, width=58).grid(row=3, column=0, columnspan=2, sticky="we", pady=(4, 8))
        ttk.Button(frame, text="Przegladaj", command=self.on_browse).grid(row=3, column=2, sticky="e", padx=(8, 0), pady=(4, 8))

        ttk.Checkbutton(
            frame,
            text="Utworz skrot .desktop na pulpicie",
            variable=self.shortcut_desktop,
        ).grid(row=4, column=0, columnspan=3, sticky="w", pady=(8, 16))

        ttk.Label(frame, textvariable=self.status).grid(row=5, column=0, columnspan=3, sticky="w")

        actions = ttk.Frame(frame)
        actions.grid(row=6, column=0, columnspan=3, sticky="e", pady=(20, 0))

        ttk.Button(actions, text="Anuluj", command=self.root.destroy).pack(side="right")
        ttk.Button(actions, text="Zainstaluj", command=self.on_install).pack(side="right", padx=(0, 8))

        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)

    def on_browse(self) -> None:
        selected = filedialog.askdirectory(initialdir=str(Path.home()))
        if selected:
            self.install_path.set(selected)

    def on_install(self) -> None:
        src = find_source_dir()
        if src is None:
            messagebox.showerror(
                "Blad",
                "Nie znaleziono paczki aplikacji. Instalator musi miec dostep do folderu 'Astro AI Processor'.",
            )
            return

        install_dir = Path(self.install_path.get()).expanduser().resolve()
        if install_dir.exists():
            replace = messagebox.askyesno(
                "Folder istnieje",
                "Folder instalacji juz istnieje. Nadpisac istniejaca instalacje?",
            )
            if not replace:
                return

        self.status.set("Instalowanie... To moze potrwac chwile.")
        self.root.update_idletasks()

        try:
            install_dir.parent.mkdir(parents=True, exist_ok=True)
            copy_bundle(src, install_dir)

            launcher_path = write_launcher(install_dir)
            icon_path = resolve_icon(install_dir)

            app_dir = Path.home() / ".local" / "share" / "applications"
            app_entry = app_dir / f"{APP_ID}.desktop"
            write_desktop_file(app_entry, launcher_path, install_dir, icon_path)

            if self.shortcut_desktop.get():
                desktop_dir = Path.home() / "Desktop"
                desktop_entry = desktop_dir / f"{APP_NAME}.desktop"
                write_desktop_file(desktop_entry, launcher_path, install_dir, icon_path)
                desktop_entry.chmod(0o755)

            self.status.set("Instalacja zakonczona.")
            messagebox.showinfo(
                "Gotowe",
                "Instalacja zakonczona pomyslnie. Aplikacja jest dostepna w menu systemu.",
            )
        except Exception as exc:  # noqa: BLE001
            self.status.set("Instalacja nie powiodla sie.")
            messagebox.showerror("Blad instalacji", str(exc))

    def run(self) -> None:
        self.root.mainloop()


def main() -> int:
    InstallerUI().run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
