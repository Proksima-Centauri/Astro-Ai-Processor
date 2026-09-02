#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"

PACKAGE_NAME="astro-ai-processor"
APP_NAME="Astro Ai Processor"
VERSION="0.1.0"
ARCH="amd64"
MAINTAINER="Astro Ai Processor Team <support@example.com>"
SOURCE_DIR="${REPO_ROOT}/dist/Astro Ai Processor"
OUTPUT_DIR="${REPO_ROOT}/dist"

print_help() {
  cat <<'EOF'
Build Debian package (.deb) for Astro Ai Processor

Usage:
  ./packaging/deb/build-deb.sh [options]

Options:
  --source DIR         Path to one-dir bundle (contains "Astro Ai Processor" and "_internal").
  --output-dir DIR     Directory for generated .deb (default: ./dist).
  --version VERSION    Debian package version (default: 0.1.0).
  --arch ARCH          Package architecture (default: amd64).
  --maintainer TEXT    Maintainer field for control file.
  --package NAME       Debian package name (default: astro-ai-processor).
  -h, --help           Show help.
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
    --version)
      VERSION="$2"
      shift 2
      ;;
    --arch)
      ARCH="$2"
      shift 2
      ;;
    --maintainer)
      MAINTAINER="$2"
      shift 2
      ;;
    --package)
      PACKAGE_NAME="$2"
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

if [[ ! -x "${SOURCE_DIR}/Astro Ai Processor" || ! -d "${SOURCE_DIR}/_internal" ]]; then
  echo "Error: source directory must contain executable 'Astro Ai Processor' and '_internal'." >&2
  echo "Received: ${SOURCE_DIR}" >&2
  exit 1
fi

if ! command -v dpkg-deb >/dev/null 2>&1; then
  echo "Error: dpkg-deb is required to build .deb packages." >&2
  exit 1
fi

WORKDIR="$(mktemp -d /tmp/opencode/astro-ai-processor-deb-XXXXXX)"
PKGROOT="${WORKDIR}/${PACKAGE_NAME}"
APP_DIR="${PKGROOT}/opt/${PACKAGE_NAME}"
DEBIAN_DIR="${PKGROOT}/DEBIAN"

cleanup() {
  rm -rf "${WORKDIR}"
}
trap cleanup EXIT

install -d "${DEBIAN_DIR}" "${APP_DIR}" "${PKGROOT}/usr/bin" "${PKGROOT}/usr/share/applications"

cp -a "${SOURCE_DIR}/." "${APP_DIR}"
chmod +x "${APP_DIR}/${APP_NAME}"

cat > "${PKGROOT}/usr/bin/${PACKAGE_NAME}" <<EOF
#!/usr/bin/env bash
set -euo pipefail
exec "/opt/${PACKAGE_NAME}/${APP_NAME}" "\$@"
EOF
chmod 755 "${PKGROOT}/usr/bin/${PACKAGE_NAME}"

cp "${SCRIPT_DIR}/astro-ai-processor.desktop" "${PKGROOT}/usr/share/applications/${PACKAGE_NAME}.desktop"

sed \
  -e "s/@PACKAGE_NAME@/${PACKAGE_NAME}/g" \
  -e "s/@VERSION@/${VERSION}/g" \
  -e "s/@ARCH@/${ARCH}/g" \
  -e "s/@MAINTAINER@/${MAINTAINER}/g" \
  "${SCRIPT_DIR}/control.template" > "${DEBIAN_DIR}/control"

cp "${SCRIPT_DIR}/postinst" "${DEBIAN_DIR}/postinst"
cp "${SCRIPT_DIR}/postrm" "${DEBIAN_DIR}/postrm"
chmod 755 "${DEBIAN_DIR}/postinst" "${DEBIAN_DIR}/postrm"

mkdir -p "${OUTPUT_DIR}"
OUTPUT_FILE="${OUTPUT_DIR}/${PACKAGE_NAME}_${VERSION}_${ARCH}.deb"

dpkg-deb --build --root-owner-group "${PKGROOT}" "${OUTPUT_FILE}"

echo "Built package: ${OUTPUT_FILE}"
