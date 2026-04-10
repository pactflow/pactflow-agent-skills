#!/usr/bin/env bash
# Checks that PactFlow is configured at session start.
# Emits a systemMessage if PACT_BROKER_BASE_URL is missing.

if [ -z "$PACT_BROKER_BASE_URL" ]; then
  cat <<'EOF'
{"systemMessage": "PACT_BROKER_BASE_URL is not set — contract-testing_* tools won't work. Set it via the plugin's userConfig (pact_broker_base_url) or export it in your shell profile. See the pactflow skill's references/mcp-setup.md for setup instructions."}
EOF
fi
