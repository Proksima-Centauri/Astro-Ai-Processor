#!/usr/bin/env python3
"""
Quick update notifier helper.

Use cases:
1) Publish update metadata to your API (admin side).
2) Check for updates at app startup and show Update / Do it later messagebox.

API contract (example):
- POST {api_url}/updates
  body: {
    "app_id": "astro-ai-processor",
    "target_os": "linux",
    "version": "1.4.0",
    "changes": ["New star shrink", "3D FLY fixes"],
    "update_url": "https://..."
  }

- GET {api_url}/updates/latest?app_id=astro-ai-processor&target_os=linux
  response: {
    "version": "1.4.0",
    "changes": ["New star shrink", "3D FLY fixes"],
    "update_url": "https://..."
  }

- POST {api_url}/updates/decision (optional)
  body: {
    "app_id": "astro-ai-processor",
    "target_os": "linux",
    "current_version": "1.3.0",
    "offered_version": "1.4.0",
    "decision": "update" | "later"
  }
"""

from __future__ import annotations

import argparse
import base64
import json
import platform
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import webbrowser

try:
    import tkinter as tk
    from tkinter import messagebox
except Exception:  # pragma: no cover
    tk = None
    messagebox = None


def normalize_os(value: str | None = None) -> str:
    raw = (value or platform.system()).strip().lower()
    if raw in {"linux", "linux2"}:
        return "linux"
    if raw in {"windows", "win32", "cygwin"}:
        return "windows"
    if raw in {"darwin", "mac", "macos", "osx"}:
        return "macos"
    return raw


def parse_version(version: str) -> tuple[int, ...]:
    nums = re.findall(r"\d+", version)
    if not nums:
        return (0,)
    return tuple(int(n) for n in nums)


def is_newer(latest: str, current: str) -> bool:
    return parse_version(latest) > parse_version(current)


def _http_json(url: str, method: str = "GET", payload: dict | None = None, token: str | None = None) -> dict:
    data = None
    headers = {
        "Accept": "application/json",
        "User-Agent": "Astro-AI-Update-Notifier/1.0",
    }
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(url=url, method=method, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=10) as resp:
        raw = resp.read().decode("utf-8")
        if not raw.strip():
            return {}
        return json.loads(raw)


def _friendly_http_error(exc: urllib.error.HTTPError) -> str:
    base = f"HTTP {exc.code}: {exc.reason}"
    if exc.code == 405:
        return (
            f"{base}. Ten URL nie obsluguje metody {exc.get_method()}. "
            "Dla Publish ustaw API URL na backend update API (np. http://127.0.0.1:8787), "
            "a nie na statyczna strone GitHub Pages."
        )
    if exc.code == 401:
        return f"{base}. Token jest nieprawidlowy lub nie ma uprawnien do zapisu."
    if exc.code == 403:
        return f"{base}. Brak uprawnien (albo limit API GitHub)."
    if exc.code == 404:
        return (
            f"{base}. Endpoint nie istnieje. Sprawdz API URL i sciezke /updates/latest lub /updates."
        )
    return base


def _is_github_pages_url(api_url: str) -> bool:
    host = urllib.parse.urlparse(api_url).netloc.lower()
    return host.endswith(".github.io")


def _github_owner_repo_from_pages_url(api_url: str) -> tuple[str, str]:
    parsed = urllib.parse.urlparse(api_url)
    owner = parsed.netloc.split(".", 1)[0].strip()
    repo = parsed.path.strip("/").split("/", 1)[0].strip()
    if not owner or not repo:
        raise ValueError("Dla GitHub Pages URL musi miec format https://<owner>.github.io/<repo>")
    return owner, repo


def _normalize_static_payload(payload: dict, app_id: str, target_os: str) -> dict:
    payload_app_id = str(payload.get("app_id") or "").strip()
    payload_os = normalize_os(str(payload.get("target_os") or "").strip().lower() or target_os)
    wanted_os = normalize_os(target_os)

    if payload_app_id and payload_app_id != app_id:
        return {}
    if payload_os not in {wanted_os, "any", "all"}:
        return {}

    changes = payload.get("changes") or []
    if not isinstance(changes, list):
        changes = [str(changes)]

    return {
        "version": str(payload.get("version") or "").strip(),
        "changes": [str(c) for c in changes],
        "update_url": str(payload.get("update_url") or "").strip(),
    }


def _publish_github_pages_latest(api_url: str, app_id: str, target_os: str, version: str, changes: list[str], update_url: str, token: str | None) -> dict:
    if not token:
        raise ValueError("Dla GitHub Pages (Publish) podaj Token z uprawnieniem Contents: write.")

    owner, repo = _github_owner_repo_from_pages_url(api_url)
    contents_api = f"https://api.github.com/repos/{owner}/{repo}/contents/updates/latest"
    existing_sha = None

    try:
        existing = _http_json(contents_api, method="GET", token=token)
        existing_sha = str(existing.get("sha") or "").strip() or None
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            raise

    metadata = {
        "app_id": app_id,
        "target_os": normalize_os(target_os),
        "version": version,
        "changes": changes,
        "update_url": update_url,
    }
    content_b64 = base64.b64encode((json.dumps(metadata, indent=2, ensure_ascii=True) + "\n").encode("utf-8")).decode("ascii")

    payload = {
        "message": f"chore(update): publish {app_id} {version} ({normalize_os(target_os)})",
        "content": content_b64,
    }
    if existing_sha:
        payload["sha"] = existing_sha

    response = _http_json(contents_api, method="PUT", payload=payload, token=token)
    commit = response.get("commit") if isinstance(response, dict) else {}
    commit_url = str((commit or {}).get("html_url") or "").strip()
    return {
        "ok": True,
        "message": "Update metadata zapisane do GitHub Pages repo (updates/latest)",
        "commit_url": commit_url,
    }


def publish_update(api_url: str, app_id: str, target_os: str, version: str, changes: list[str], update_url: str, token: str | None = None) -> dict:
    if _is_github_pages_url(api_url):
        return _publish_github_pages_latest(
            api_url=api_url,
            app_id=app_id,
            target_os=target_os,
            version=version,
            changes=changes,
            update_url=update_url,
            token=token,
        )

    payload = {
        "app_id": app_id,
        "target_os": normalize_os(target_os),
        "version": version,
        "changes": changes,
        "update_url": update_url,
    }
    return _http_json(f"{api_url.rstrip('/')}/updates", method="POST", payload=payload, token=token)


def fetch_latest_update(api_url: str, app_id: str, target_os: str, token: str | None = None) -> dict:
    if _is_github_pages_url(api_url):
        payload = _http_json(f"{api_url.rstrip('/')}/updates/latest", method="GET", token=token)
        return _normalize_static_payload(payload, app_id=app_id, target_os=target_os)

    query = urllib.parse.urlencode({"app_id": app_id, "target_os": normalize_os(target_os)})
    return _http_json(f"{api_url.rstrip('/')}/updates/latest?{query}", method="GET", token=token)


def send_decision(api_url: str, app_id: str, target_os: str, current_version: str, offered_version: str, decision: str, token: str | None = None) -> None:
    payload = {
        "app_id": app_id,
        "target_os": normalize_os(target_os),
        "current_version": current_version,
        "offered_version": offered_version,
        "decision": decision,
    }
    _http_json(f"{api_url.rstrip('/')}/updates/decision", method="POST", payload=payload, token=token)


def _build_message(version: str, changes: list[str], update_url: str) -> str:
    lines = [f"Nowa wersja: {version}", "", "Zmiany:"]
    for item in changes[:8]:
        lines.append(f"- {item}")
    if update_url:
        lines += ["", f"Link: {update_url}"]
    lines += ["", "Kliknij Yes aby pobrac aktualizacje."]
    return "\n".join(lines)


def ask_update_now(version: str, changes: list[str], update_url: str) -> str:
    if tk is None or messagebox is None:
        return "later"

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    text = _build_message(version, changes, update_url)
    do_update = messagebox.askyesno("Aktualizacja dostepna", text)
    root.destroy()
    return "update" if do_update else "later"


def check_for_updates_on_start(api_url: str, app_id: str, current_version: str, target_os: str | None = None, token: str | None = None) -> bool:
    os_name = normalize_os(target_os)
    try:
        latest = fetch_latest_update(api_url=api_url, app_id=app_id, target_os=os_name, token=token)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return False

    latest_version = str(latest.get("version", "")).strip()
    if not latest_version or not is_newer(latest_version, current_version):
        return False

    changes = latest.get("changes") or []
    if not isinstance(changes, list):
        changes = [str(changes)]
    update_url = str(latest.get("update_url", "")).strip()

    decision = ask_update_now(version=latest_version, changes=[str(c) for c in changes], update_url=update_url)

    try:
        send_decision(
            api_url=api_url,
            app_id=app_id,
            target_os=os_name,
            current_version=current_version,
            offered_version=latest_version,
            decision=decision,
            token=token,
        )
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        pass

    if decision == "update" and update_url:
        webbrowser.open(update_url)
        return True
    return False


def run_simple_gui() -> int:
    if tk is None or messagebox is None:
        print("Tkinter not available.")
        return 1

    root = tk.Tk()
    root.title("Update Notifier")
    root.geometry("760x640")

    frame = tk.Frame(root, padx=12, pady=12)
    frame.pack(fill="both", expand=True)

    api_var = tk.StringVar(value="https://twoje-api.pl")
    app_var = tk.StringVar(value="astro-ai-processor")
    os_var = tk.StringVar(value=normalize_os())
    version_var = tk.StringVar(value="1.0.0")
    current_var = tk.StringVar(value="1.0.0")
    url_var = tk.StringVar(value="https://example.com/download")
    token_var = tk.StringVar(value="")

    def add_row(row: int, label: str, var: tk.StringVar) -> None:
        tk.Label(frame, text=label, anchor="w").grid(row=row, column=0, sticky="w", pady=4)
        tk.Entry(frame, textvariable=var).grid(row=row, column=1, sticky="ew", pady=4)

    frame.columnconfigure(1, weight=1)
    add_row(0, "API URL", api_var)
    add_row(1, "App ID", app_var)

    tk.Label(frame, text="Target OS", anchor="w").grid(row=2, column=0, sticky="w", pady=4)
    tk.OptionMenu(frame, os_var, "linux", "windows", "macos").grid(row=2, column=1, sticky="w", pady=4)

    add_row(3, "New version", version_var)
    add_row(4, "Current version", current_var)
    add_row(5, "Update URL", url_var)
    add_row(6, "Token (optional)", token_var)

    tk.Label(frame, text="Changes (one per line)", anchor="w").grid(row=7, column=0, sticky="nw", pady=4)
    changes_box = tk.Text(frame, height=8)
    changes_box.grid(row=7, column=1, sticky="nsew", pady=4)
    frame.rowconfigure(7, weight=1)

    tk.Label(frame, text="Result", anchor="w").grid(row=8, column=0, sticky="nw", pady=4)
    result_box = tk.Text(frame, height=10)
    result_box.grid(row=8, column=1, sticky="nsew", pady=4)
    frame.rowconfigure(8, weight=1)

    def set_result(text: str) -> None:
        result_box.delete("1.0", "end")
        result_box.insert("1.0", text)

    def on_publish() -> None:
        changes = [line.strip() for line in changes_box.get("1.0", "end").splitlines() if line.strip()]
        try:
            result = publish_update(
                api_url=api_var.get().strip(),
                app_id=app_var.get().strip(),
                target_os=os_var.get().strip(),
                version=version_var.get().strip(),
                changes=changes,
                update_url=url_var.get().strip(),
                token=token_var.get().strip() or None,
            )
            set_result(json.dumps(result, indent=2, ensure_ascii=True))
            messagebox.showinfo("OK", "Update metadata sent.")
        except urllib.error.HTTPError as exc:
            msg = _friendly_http_error(exc)
            set_result(f"ERROR: {msg}")
            messagebox.showerror("Error", msg)
        except Exception as exc:
            set_result(f"ERROR: {exc}")
            messagebox.showerror("Error", str(exc))

    def on_check() -> None:
        try:
            opened = check_for_updates_on_start(
                api_url=api_var.get().strip(),
                app_id=app_var.get().strip(),
                current_version=current_var.get().strip(),
                target_os=os_var.get().strip(),
                token=token_var.get().strip() or None,
            )
            set_result("UPDATE_OPENED" if opened else "NO_UPDATE")
        except urllib.error.HTTPError as exc:
            msg = _friendly_http_error(exc)
            set_result(f"ERROR: {msg}")
            messagebox.showerror("Error", msg)
        except Exception as exc:
            set_result(f"ERROR: {exc}")
            messagebox.showerror("Error", str(exc))

    btns = tk.Frame(frame)
    btns.grid(row=9, column=0, columnspan=2, sticky="w", pady=(8, 0))
    tk.Button(btns, text="Publish", command=on_publish).pack(side="left", padx=(0, 8))
    tk.Button(btns, text="Check update", command=on_check).pack(side="left")

    root.mainloop()
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Publish/check app updates via API JSON.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    pub = sub.add_parser("publish", help="Publish update metadata")
    pub.add_argument("--api-url", required=True)
    pub.add_argument("--app-id", required=True)
    pub.add_argument("--target-os", required=True, choices=["linux", "windows", "macos"])
    pub.add_argument("--version", required=True)
    pub.add_argument("--change", action="append", default=[], help="Repeat for each change")
    pub.add_argument("--update-url", required=True)
    pub.add_argument("--token")

    chk = sub.add_parser("check", help="Check update and show messagebox")
    chk.add_argument("--api-url", required=True)
    chk.add_argument("--app-id", required=True)
    chk.add_argument("--current-version", required=True)
    chk.add_argument("--target-os", choices=["linux", "windows", "macos"])
    chk.add_argument("--token")

    sub.add_parser("gui", help="Open simple GUI")

    args = parser.parse_args(argv)

    if args.cmd == "publish":
        result = publish_update(
            api_url=args.api_url,
            app_id=args.app_id,
            target_os=args.target_os,
            version=args.version,
            changes=args.change,
            update_url=args.update_url,
            token=args.token,
        )
        print(json.dumps(result, indent=2, ensure_ascii=True))
        return 0

    if args.cmd == "gui":
        return run_simple_gui()

    updated = check_for_updates_on_start(
        api_url=args.api_url,
        app_id=args.app_id,
        current_version=args.current_version,
        target_os=args.target_os,
        token=args.token,
    )
    print("UPDATE_OPENED" if updated else "NO_UPDATE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
