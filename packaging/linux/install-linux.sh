#!/usr/bin/env bash
set -euo pipefail

APP_NAME="Astro Ai Processor"
APP_ID="astro-ai-processor"

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_INSTALL_DIR="${HOME}/.local/opt/${APP_ID}"
DEFAULT_DESKTOP_DIR="${HOME}/.local/share/applications"

SOURCE_DIR=""
INSTALL_DIR="${DEFAULT_INSTALL_DIR}"
DESKTOP_DIR="${DEFAULT_DESKTOP_DIR}"
FORCE=0
CREATE_DESKTOP=1
UNINSTALL=0

print_help() {
  cat <<'EOF'
Astro Ai Processor Linux installer

Usage:
  ./packaging/linux/install-linux.sh [options]

Options:
  --source DIR         Path to extracted one-dir app bundle (contains "Astro Ai Processor" and "_internal").
  --install-dir DIR    Target install directory (default: ~/.local/opt/astro-ai-processor).
  --desktop-dir DIR    Directory for .desktop entry (default: ~/.local/share/applications).
  --no-desktop         Do not create/update .desktop launcher.
  --force              Replace existing installation directory.
  --uninstall          Remove install directory and desktop entry.
  -h, --help           Show this help.
EOF
}

resolve_source_dir() {
  if [[ -n "${SOURCE_DIR}" ]]; then
    return
  fi

  local candidates=(
    "${SCRIPT_DIR}/../../dist/Astro Ai Processor"
    "${SCRIPT_DIR}/../../Astro Ai Processor"
    "$(pwd)/Astro Ai Processor"
  )

  local candidate
  for candidate in "${candidates[@]}"; do
    if [[ -x "${candidate}/Astro Ai Processor" && -d "${candidate}/_internal" ]]; then
      SOURCE_DIR="${candidate}"
      return
    fi
  done

  echo "Error: could not find app bundle automatically." >&2
  echo "Use --source with a directory that contains 'Astro Ai Processor' and '_internal'." >&2
  exit 1
}

validate_source_dir() {
  if [[ ! -x "${SOURCE_DIR}/Astro Ai Processor" ]]; then
    echo "Error: ${SOURCE_DIR} does not contain executable 'Astro Ai Processor'." >&2
    exit 1
  fi
  if [[ ! -d "${SOURCE_DIR}/_internal" ]]; then
    echo "Error: ${SOURCE_DIR} does not contain '_internal' directory." >&2
    exit 1
  fi
}

resolve_icon_path() {
  if [[ -f "${INSTALL_DIR}/assets/favicon.ico" ]]; then
    printf '%s\n' "${INSTALL_DIR}/assets/favicon.ico"
    return
  fi
  if [[ -f "${INSTALL_DIR}/_internal/assets/favicon.ico" ]]; then
    printf '%s\n' "${INSTALL_DIR}/_internal/assets/favicon.ico"
    return
  fi
  printf '%s\n' ""
}

write_launcher() {
  local launcher_path="${INSTALL_DIR}/${APP_ID}"
  cat > "${launcher_path}" <<EOF
#!/usr/bin/env bash
set -euo pipefail
exec "${INSTALL_DIR}/Astro Ai Processor" "\$@"
EOF
  chmod +x "${launcher_path}"
}

write_desktop_file() {
  local icon_path
  icon_path="$(resolve_icon_path)"

  mkdir -p "${DESKTOP_DIR}"
  local desktop_file="${DESKTOP_DIR}/${APP_ID}.desktop"

  cat > "${desktop_file}" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=${APP_NAME}
Comment=Astrophotography processing application
Exec=${INSTALL_DIR}/${APP_ID} %F
Path=${INSTALL_DIR}
Icon=${icon_path}
Terminal=false
Categories=Graphics;Photography;Science;
StartupNotify=true
EOF

  chmod 644 "${desktop_file}"
}

run_uninstall() {
  rm -rf "${INSTALL_DIR}"
  rm -f "${DESKTOP_DIR}/${APP_ID}.desktop"
  echo "Uninstalled ${APP_NAME}."
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --source)
      SOURCE_DIR="$2"
      shift 2
      ;;
    --install-dir)
      INSTALL_DIR="$2"
      shift 2
      ;;
    --desktop-dir)
      DESKTOP_DIR="$2"
      shift 2
      ;;
    --no-desktop)
      CREATE_DESKTOP=0
      shift
      ;;
    --force)
      FORCE=1
      shift
      ;;
    --uninstall)
      UNINSTALL=1
      shift
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

if [[ ${UNINSTALL} -eq 1 ]]; then
  run_uninstall
  exit 0
fi

resolve_source_dir
validate_source_dir

if [[ -e "${INSTALL_DIR}" ]]; then
  if [[ ${FORCE} -ne 1 ]]; then
    echo "Error: install directory already exists: ${INSTALL_DIR}" >&2
    echo "Use --force to replace it." >&2
    exit 1
  fi
  rm -rf "${INSTALL_DIR}"
fi

mkdir -p "$(dirname "${INSTALL_DIR}")"
cp -a "${SOURCE_DIR}" "${INSTALL_DIR}"
chmod +x "${INSTALL_DIR}/Astro Ai Processor"

write_launcher

if [[ ${CREATE_DESKTOP} -eq 1 ]]; then
  write_desktop_file
fi

echo "Installed ${APP_NAME} to: ${INSTALL_DIR}"
if [[ ${CREATE_DESKTOP} -eq 1 ]]; then
  echo "Desktop entry: ${DESKTOP_DIR}/${APP_ID}.desktop"
fi
