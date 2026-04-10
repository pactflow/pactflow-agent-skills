#!/usr/bin/env bash
# Reads the Bash tool input from stdin and emits a reminder if the command
# looks like a deployment operation, prompting the user to run can-i-deploy
# before deploying and record-deployment after.

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('tool_input', {}).get('command', ''))
except Exception:
    print('')
" 2>/dev/null || echo "")

if echo "$COMMAND" | grep -qiE '(kubectl apply|helm upgrade|helm install|terraform apply|deploy\.sh|release\.sh|npm publish|docker push|eb deploy|serverless deploy|flyctl deploy|railway up|vercel --prod|render deploy)'; then
  cat <<'EOF'
{"systemMessage": "Deployment detected — remember to:\n1. Run can-i-deploy BEFORE deploying: contract-testing_can_i_deploy\n2. Run record-deployment AFTER deploying: contract-testing_record_deployment\nSkipping these breaks the Pact Matrix and can-i-deploy checks for other services."}
EOF
fi
