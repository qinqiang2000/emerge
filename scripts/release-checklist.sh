#!/usr/bin/env bash
# release-checklist.sh — pre-release / dogfood gate for emerge.
#
# Runs the same checks the per-phase manual gate does:
#   1. frontend lint           (cd frontend && npm run lint)
#   2. frontend unit tests     (cd frontend && npm test)
#   3. frontend production build (cd frontend && npm run build)
#   4. backend tests           (cd backend  && uv run pytest -q)
#   5. (optional, EMERGE_E2E=1) Playwright walking-skeleton against a live backend
#
# Behaviour:
#   - Each step's full output streams to a per-step log under .release-checklist-logs/.
#   - The terminal only sees PASS / FAIL summary lines so secrets can't leak even if
#     a step accidentally prints a header that mentions a key. Logs stay on disk
#     under a gitignored path so the operator can grep them locally; do not paste
#     them anywhere shared without scrubbing.
#   - Exit 0 only when every required step passes. EMERGE_E2E is opt-in; when not
#     set, the E2E line reads SKIP and does not affect exit code.
#
# Usage:
#   ./scripts/release-checklist.sh
#   EMERGE_E2E=1 ./scripts/release-checklist.sh
#
# This script does NOT read or print any secret values. It does not source
# backend/.env. The Playwright spec gate (EMERGE_E2E=1) requires a backend
# already running on :8000 with provider keys configured by the operator;
# this script does not start that backend itself, on purpose, so it cannot
# be tricked into printing the env it would have used.

set -u
set -o pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="${ROOT}/.release-checklist-logs"
mkdir -p "${LOG_DIR}"

PASS=0
FAIL=0
SKIP=0
declare -a RESULTS=()

run_step() {
  local label="$1"
  local cwd="$2"
  local cmd="$3"
  local log="${LOG_DIR}/${label}.log"

  printf "  → %-26s ... " "${label}"
  if ( cd "${cwd}" && eval "${cmd}" ) >"${log}" 2>&1; then
    printf "PASS\n"
    RESULTS+=("PASS  ${label}")
    PASS=$((PASS + 1))
  else
    printf "FAIL  (log: %s)\n" "${log#${ROOT}/}"
    RESULTS+=("FAIL  ${label}  (log: ${log#${ROOT}/})")
    FAIL=$((FAIL + 1))
  fi
}

skip_step() {
  local label="$1"
  local reason="$2"
  printf "  → %-26s ... SKIP  (%s)\n" "${label}" "${reason}"
  RESULTS+=("SKIP  ${label}  (${reason})")
  SKIP=$((SKIP + 1))
}

echo "release-checklist  (root: ${ROOT})"
echo "  log dir: ${LOG_DIR#${ROOT}/}/"
echo

run_step "frontend-lint"   "${ROOT}/frontend" "npm run lint"
run_step "frontend-test"   "${ROOT}/frontend" "npm test --silent"
run_step "frontend-build"  "${ROOT}/frontend" "npm run build"
run_step "backend-pytest"  "${ROOT}/backend"  "uv run pytest -q"

if [[ "${EMERGE_E2E:-}" == "1" ]]; then
  run_step "e2e-walking-skeleton" "${ROOT}/frontend" "EMERGE_E2E=1 npx playwright test walking_skeleton"
else
  skip_step "e2e-walking-skeleton" "set EMERGE_E2E=1 with backend on :8000 to enable"
fi

echo
echo "summary  ${PASS} pass · ${FAIL} fail · ${SKIP} skip"
for line in "${RESULTS[@]}"; do
  echo "  ${line}"
done

if [[ "${FAIL}" -gt 0 ]]; then
  exit 1
fi
exit 0
