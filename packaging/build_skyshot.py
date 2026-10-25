"""Build vendored Skyshot CLI and generate its target-specific binary notices."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys


def _tool(name: str) -> str:
    executable = shutil.which(name)
    if executable:
        return executable
    cargo_home_tool = Path.home() / ".cargo" / "bin" / (name + (".exe" if os.name == "nt" else ""))
    if cargo_home_tool.is_file():
        return str(cargo_home_tool)
    raise RuntimeError(f"Building bundled Skyshot requires Rust/Cargo 1.95.0; {name} was not found.")


def build_skyshot(project_root: Path, scratch_root: Path) -> tuple[Path, Path]:
    project_root = Path(project_root).resolve()
    skyshot_root = project_root / "third_party" / "skyshot"
    cargo = _tool("cargo")
    rustc = _tool("rustc")
    env = os.environ.copy()
    tool_bin = str(Path(cargo).parent)
    env["PATH"] = tool_bin + os.pathsep + env.get("PATH", "")

    cargo_version = subprocess.check_output([cargo, "--version"], text=True, env=env).strip()
    rustc_version = subprocess.check_output([rustc, "--version"], text=True, env=env).strip()
    if "1.95.0" not in cargo_version or "1.95.0" not in rustc_version:
        raise RuntimeError(f"Skyshot source is pinned to Rust/Cargo 1.95.0; found {rustc_version} / {cargo_version}.")
    # The upstream notice inventory uses offline Cargo metadata, so first cache
    # every locked dependency, including build/dev targets.
    subprocess.run([cargo, "fetch", "--locked"], cwd=skyshot_root, env=env, check=True)
    subprocess.run([cargo, "build", "--release", "--locked"], cwd=skyshot_root, env=env, check=True)

    binary = skyshot_root / "target" / "release" / ("skyshot.exe" if os.name == "nt" else "skyshot")
    if not binary.is_file():
        raise RuntimeError(f"Skyshot Cargo build did not produce {binary.name}.")

    tools_dir = skyshot_root / "tools"
    tools_text = str(tools_dir)
    sys.path.insert(0, tools_text)
    package_path = tools_dir / "package_cli.py"
    try:
        spec = importlib.util.spec_from_file_location("astro_skyshot_package_cli", package_path)
        if spec is None or spec.loader is None:
            raise RuntimeError("Could not load Skyshot's upstream package/licensing helper.")
        package_cli = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = package_cli
        spec.loader.exec_module(package_cli)

        host = next(
            line.removeprefix("host: ")
            for line in subprocess.check_output([rustc, "-Vv"], text=True, env=env).splitlines()
            if line.startswith("host: ")
        )
        notices = Path(scratch_root) / "skyshot-third-party-notices"
        if notices.exists():
            shutil.rmtree(notices)
        notices.mkdir(parents=True)
        package_cli.dependency_notices(host, notices / "dependencies")
        package_cli.rust_notices(notices)
    finally:
        sys.path.remove(tools_text)
    return binary, notices
