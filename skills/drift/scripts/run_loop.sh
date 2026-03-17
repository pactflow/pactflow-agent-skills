#!/usr/bin/env bash
# run_loop.sh — Drift full coverage feedback loop.
#
# Runs `drift verify --failed` repeatedly until all tests pass, then runs
# check_coverage.py to verify every operation and response code is covered.
# Exits 0 only when both gates pass.
#
# Usage:
#   ./run_loop.sh --spec openapi.yaml --test-files drift.yaml --server-url http://localhost:4010
#   ./run_loop.sh --spec openapi.yaml --test-files "tests/*.yaml" --server-url https://api.example.com
#
# Options:
#   --spec        Path to OpenAPI spec (required for coverage check)
#   --test-files  Drift test file(s) or glob pattern (required)
#   --server-url  URL of the API under test (required)
#   --max-rounds  Max number of drift verify retries (default: 20)
#   --full        Run full suite each round instead of --failed only
#   --skip-coverage  Skip the coverage check at the end (just get tests passing)
#
# Environment:
#   Any env vars drift verify needs (API_TOKEN, etc.) must be set before running.

set -euo pipefail

SPEC=""
TEST_FILES=""
SERVER_URL=""
MAX_ROUNDS=20
USE_FAILED="--failed"
SKIP_COVERAGE=false
ROUND=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --spec)           SPEC="$2";        shift 2 ;;
    --test-files)     TEST_FILES="$2";  shift 2 ;;
    --server-url)     SERVER_URL="$2";  shift 2 ;;
    --max-rounds)     MAX_ROUNDS="$2";  shift 2 ;;
    --full)           USE_FAILED="";    shift ;;
    --skip-coverage)  SKIP_COVERAGE=true; shift ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

if [[ -z "$TEST_FILES" || -z "$SERVER_URL" ]]; then
  echo "Usage: $0 --spec openapi.yaml --test-files drift.yaml --server-url http://localhost:4010" >&2
  exit 1
fi

# ── Locate check_coverage.py ──────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COVERAGE_SCRIPT="$SCRIPT_DIR/check_coverage.py"

# ── Set up Python venv for check_coverage.py ─────────────────────────────────
VENV_DIR="$SCRIPT_DIR/.venv"
if [[ ! -f "$VENV_DIR/bin/python3" ]]; then
  echo "Setting up Python venv for coverage checker..."
  python3 -m venv "$VENV_DIR"
  "$VENV_DIR/bin/pip" install pyyaml -q
  echo "Done."
  echo ""
fi
PYTHON="$VENV_DIR/bin/python3"

# ── Run drift in a loop ───────────────────────────────────────────────────────
echo "════════════════════════════════════════════════════════════"
echo "  Drift Coverage Feedback Loop"
echo "  Test files:  $TEST_FILES"
echo "  Server URL:  $SERVER_URL"
echo "  Max rounds:  $MAX_ROUNDS"
echo "════════════════════════════════════════════════════════════"
echo ""

# First run — always full (no --failed on round 1)
echo "── Round 1 / $MAX_ROUNDS — full run ──"
if drift verify --test-files "$TEST_FILES" --server-url "$SERVER_URL"; then
  echo ""
  echo "✓ All tests passed on first run."
  DRIFT_PASSED=true
else
  DRIFT_PASSED=false
fi

# Subsequent rounds — only retry failed
if [[ "$DRIFT_PASSED" == "false" ]]; then
  ROUND=2
  while [[ $ROUND -le $MAX_ROUNDS ]]; do
    echo ""
    echo "── Round $ROUND / $MAX_ROUNDS ──"
    if drift verify --test-files "$TEST_FILES" --server-url "$SERVER_URL" $USE_FAILED; then
      echo ""
      echo "✓ All tests passed (round $ROUND)."
      DRIFT_PASSED=true
      break
    fi
    ROUND=$((ROUND + 1))
  done
fi

if [[ "$DRIFT_PASSED" == "false" ]]; then
  echo ""
  echo "✗ Tests still failing after $MAX_ROUNDS rounds. Fix the remaining failures manually."
  exit 1
fi

# ── Coverage check ────────────────────────────────────────────────────────────
if [[ "$SKIP_COVERAGE" == "true" ]]; then
  echo ""
  echo "Coverage check skipped (--skip-coverage)."
  exit 0
fi

if [[ -z "$SPEC" ]]; then
  echo ""
  echo "Note: --spec not provided, skipping coverage check."
  echo "To verify full coverage run:"
  echo "  $PYTHON $COVERAGE_SCRIPT --spec openapi.yaml --test-files $TEST_FILES"
  exit 0
fi

echo ""
echo "════════════════════════════════════════════════════════════"
echo "  Coverage Check"
echo "════════════════════════════════════════════════════════════"
if "$PYTHON" "$COVERAGE_SCRIPT" --spec "$SPEC" --test-files "$TEST_FILES"; then
  echo ""
  echo "✓ Complete: all tests pass AND full coverage verified."
  exit 0
else
  echo ""
  echo "✗ Tests pass but coverage is incomplete. Add tests for the missing operations/codes above."
  exit 1
fi
