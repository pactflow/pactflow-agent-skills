#!/usr/bin/env bash
# start_mock.sh — Start a Prism mock server from an OpenAPI spec.
#
# Usage:
#   ./start_mock.sh --spec openapi.yaml
#   ./start_mock.sh --spec openapi.yaml --port 4010
#   ./start_mock.sh --spec openapi.yaml --port 4010 --dynamic
#
# Options:
#   --spec      Path to OpenAPI spec (required)
#   --port      Port to listen on (default: 4010)
#   --dynamic   Enable dynamic response generation (Prism generates values from
#               schema rather than using static examples). Useful when the spec
#               has no examples for some responses.
#
# The script installs @stoplight/prism-cli if not already available, then starts
# the server in the foreground. Ctrl-C to stop.

set -euo pipefail

SPEC=""
PORT="4010"
DYNAMIC_FLAG=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --spec)    SPEC="$2";    shift 2 ;;
    --port)    PORT="$2";    shift 2 ;;
    --dynamic) DYNAMIC_FLAG="--dynamic"; shift ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

if [[ -z "$SPEC" ]]; then
  echo "Usage: $0 --spec openapi.yaml [--port 4010] [--dynamic]" >&2
  exit 1
fi

if [[ ! -f "$SPEC" ]]; then
  echo "ERROR: spec file not found: $SPEC" >&2
  exit 1
fi

# Install prism if needed
if ! command -v prism &>/dev/null; then
  echo "Prism not found — installing @stoplight/prism-cli globally..."
  npm install -g @stoplight/prism-cli
fi

echo "Starting Prism mock server"
echo "  Spec:  $SPEC"
echo "  Port:  $PORT"
echo "  URL:   http://localhost:$PORT"
[[ -n "$DYNAMIC_FLAG" ]] && echo "  Mode:  dynamic (schema-generated responses)"
echo ""
echo "Use 'Prefer: code=<status>' header to force specific response codes."
echo "Press Ctrl-C to stop."
echo ""

# shellcheck disable=SC2086
exec prism mock "$SPEC" --port "$PORT" $DYNAMIC_FLAG
