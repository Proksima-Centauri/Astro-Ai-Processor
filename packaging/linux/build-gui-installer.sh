#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"

SOURCE_DIR="${REPO_ROOT}/dist/Astro AI Processor"
OUTPUT_DIR="${REPO_ROOT}/dist"
INSTALLER_NAME="Astro-Ai-Processor-Installer-Linux"
PYTHON_BIN=""

print_help() {
  cat <<'EOF'
Build GUI Linux installer (single clickable file)

Usage:
  ./packaging/linux/build-gui-installer.sh [options]

Options:
  --source DIR         Path to one-dir app bundle (default: dist/Astro AI Processor)
  --output-dir DIR     Output directory for installer (default: dist)
  --name NAME          Installer executable name
  -h, --help           Show help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --source)
      SOURCE_DIR="$2"
      shift 2
      ;;
    --output-dir)
      OUTPUT_DIR="$2"
      shift 2
      ;;
    --name)
      INSTALLER_NAME="$2"
      shift 2
      ;;
    -h|--help)
      print_help
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      print_help
      exit 1
      ;;
  esac
done

SOURCE_DIR="$(realpath -m "${SOURCE_DIR}")"
OUTPUT_DIR="$(realpath -m "${OUTPUT_DIR}")"

if [[ -x "${REPO_ROOT}/.venv/bin/python3" ]] && "${REPO_ROOT}/.venv/bin/python3" -c "import PyInstaller" >/dev/null 2>&1; then
  PYTHON_BIN="${REPO_ROOT}/.venv/bin/python3"
elif python3 -c "import PyInstaller" >/dev/null 2>&1; then
  PYTHON_BIN="python3"
else
  echo "Error: PyInstaller is required. Install with: pip install pyinstaller" >&2
  exit 1
fi

if [[ ! -x "${SOURCE_DIR}/Astro AI Processor" || ! -d "${SOURCE_DIR}/_internal" ]]; then
  echo "Error: source bundle not valid: ${SOURCE_DIR}" >&2
  echo "Expected executable 'Astro AI Processor' and '_internal' directory." >&2
  exit 1
fi

mkdir -p "${OUTPUT_DIR}"
"${PYTHON_BIN}" -m PyInstaller \
  --noconfirm \
  --clean \
  --onefile \
  --windowed \
  --name "${INSTALLER_NAME}" \
  --distpath "${OUTPUT_DIR}" \
  --workpath "/tmp/opencode/pyinstaller-work" \
  --specpath "/tmp/opencode/pyinstaller-spec" \
  --add-data "${SOURCE_DIR}:Astro AI Processor" \
  "${SCRIPT_DIR}/gui_installer.py"

echo "Built clickable installer: ${OUTPUT_DIR}/${INSTALLER_NAME}"
