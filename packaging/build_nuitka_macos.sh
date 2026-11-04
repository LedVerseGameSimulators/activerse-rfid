#!/usr/bin/env bash
# Build the RFID operator package with Nuitka (macOS): ONE executable with roles
# (supervisor / --role api / --selftest / --stop), staged next to ui/, zipped.
# Windows twin: packaging/build_nuitka_windows.ps1 (CI: .github/workflows/package.yml)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

EXE_NAME="${EXE_NAME:-Activerse-RFID}"
TAG="${TAG:-dev}"
VENV="${ROOT}/packaging/.venv"
PYTHON="${VENV}/bin/python"

if [[ ! -x "${PYTHON}" ]]; then
  echo "==> Creating packaging/.venv"
  python3 -m venv "${VENV}"
fi

echo "==> Installing Nuitka + deps"
"${PYTHON}" -m pip install -q -U pip wheel
"${PYTHON}" -m pip install -q -r requirements-packaging.txt
"${PYTHON}" -m pip install -q -r requirements.txt

echo "==> Building UI"
(cd frontend && npm ci --silent && npm run build)

OUT="${ROOT}/dist/nuitka"
rm -rf "${OUT}"
mkdir -p "${OUT}"
export PYTHONPATH="${ROOT}${PYTHONPATH:+:$PYTHONPATH}"

NOFOLLOW=(tkinter numpy PIL cv2 mysql pytest tests)
NOFOLLOW_ARGS=()
for m in "${NOFOLLOW[@]}"; do NOFOLLOW_ARGS+=("--nofollow-import-to=${m}"); done

echo "==> Nuitka ${EXE_NAME} (this can take a long time)"
"${PYTHON}" -m nuitka \
  --standalone \
  --static-libpython=no \
  --assume-yes-for-downloads \
  --output-dir="${OUT}" \
  --output-filename="${EXE_NAME}" \
  --include-package=api \
  --include-package=floor_launcher \
  --include-package=fastapi \
  --include-package=starlette \
  --include-package=uvicorn \
  --include-package=pydantic \
  --include-package=pydantic_core \
  --include-package=httpx \
  --include-package=httpcore \
  --include-package=anyio \
  --include-package=h11 \
  --include-package=annotated_types \
  --include-package=idna \
  --include-package=certifi \
  --include-package-data=certifi \
  --include-package=loguru \
  --include-package=dotenv \
  --include-package=openpyxl \
  --include-package=et_xmlfile \
  --include-package=multipart \
  --include-package=python_multipart \
  --include-module=sqlite3 \
  "${NOFOLLOW_ARGS[@]}" \
  floor_launcher/entry.py

DIST="${OUT}/entry.dist"
[[ -d "${DIST}" ]] || { echo "ERROR: missing ${DIST}"; exit 1; }

STAGE="${ROOT}/dist/release/Activerse-RFID-${TAG#v}-macos"
mkdir -p "${ROOT}/dist/release"
"${PYTHON}" packaging/stage_release.py "${STAGE}" "${DIST}" --macos

ZIP_NAME="$(basename "${STAGE}")-nuitka.zip"
( cd "${ROOT}/dist/release" && rm -f "${ZIP_NAME}" && zip -qy -r "${ZIP_NAME}" "$(basename "${STAGE}")" )
echo "==> Wrote dist/release/${ZIP_NAME}"
