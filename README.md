# PactFlow Agent Skills

AI assistant skills for PactFlow's contract testing tools.

| Skill | Plugin name | What it does |
|---|---|---|
| **Drift** | `swagger-contract-testing-drift` | Expert assistant for Drift — PactFlow's OpenAPI contract testing CLI. Helps write test cases, configure lifecycle hooks, debug failures, and publish results to PactFlow. |
| **OpenAPI Parser** | `swagger-contract-testing-openapi-parser` | Parses complex OpenAPI specs (anyOf/oneOf/allOf, discriminators, polymorphism, $ref chains, enums, regex) and generates Drift test cases covering every viable schema combination. |

The two skills are designed to work together: OpenAPI Parser analyses a spec and generates
test case scaffolding; Drift runs, iterates, and publishes those tests.

---

## Installing in Claude Code

Claude Code uses a plugin marketplace system. Requires Claude Code v1.0.33+.

### From this repo (recommended for teams)

**1. Add the marketplace** inside a Claude Code session:

```
/plugin marketplace add pactflow/pact-agent-skills
```

Or add it to `.claude/settings.json` so teammates are prompted to install it automatically when they open the project:

```json
{
  "extraKnownMarketplaces": {
    "pact-agent-skills": {
      "source": { "source": "github", "repo": "pactflow/pact-agent-skills" }
    }
  }
}
```

**2. Install the plugins:**

```
/plugin install swagger-contract-testing-drift@pact-agent-skills
/plugin install swagger-contract-testing-openapi-parser@pact-agent-skills
```

**Scope options:**

| Scope | Stored in | Who it applies to |
|---|---|---|
| `user` (default) | `~/.claude/settings.json` | You, across all projects |
| `project` | `.claude/settings.json` | Everyone on the team (commit this file) |
| `local` | `.claude/settings.local.json` | You, in this project only (gitignored) |

### From a local clone

```
/plugin marketplace add ./path/to/pact-agent-skills
/plugin install swagger-contract-testing-drift@pact-agent-skills
/plugin install swagger-contract-testing-openapi-parser@pact-agent-skills
```

### For local development (no marketplace needed)

```bash
claude --plugin-dir ./plugins/drift
claude --plugin-dir ./plugins/openapi-parser
# or both at once:
claude --plugin-dir ./plugins/drift --plugin-dir ./plugins/openapi-parser
```

### Managing plugins

```
/plugin                          # open plugin manager (Discover / Installed / Marketplaces / Errors)
/reload-plugins                  # reload without restarting
/plugin disable swagger-contract-testing-drift@pact-agent-skills
/plugin disable swagger-contract-testing-openapi-parser@pact-agent-skills
/plugin uninstall swagger-contract-testing-drift@pact-agent-skills
/plugin uninstall swagger-contract-testing-openapi-parser@pact-agent-skills
```

---

## Installing in OpenCode

OpenCode loads skills from a `SKILL.md` file in a named subdirectory. The agent
automatically selects relevant skills based on task context.

### Global install (available in all projects)

```bash
cp -r skills/drift ~/.config/opencode/skills/drift
cp -r skills/openapi-parser ~/.config/opencode/skills/openapi-parser
```

### Project-level install (this project only)

```bash
mkdir -p .opencode/skills
cp -r skills/drift .opencode/skills/drift
cp -r skills/openapi-parser .opencode/skills/openapi-parser
```

OpenCode will pick up the skills automatically — no restart required.

---

## Installing in GitHub Copilot

GitHub Copilot doesn't have a plugin system, but you can give Copilot Chat the same
context via custom instructions.

### Repo-wide instructions (simplest)

Concatenate all skill files into `.github/copilot-instructions.md`:

```bash
cat skills/drift/SKILL.md skills/drift/references/*.md >> .github/copilot-instructions.md
cat skills/openapi-parser/SKILL.md skills/openapi-parser/references/*.md >> .github/copilot-instructions.md
```

Copilot Chat will apply these instructions automatically to every conversation in the
repository. Commit the file to share it with your team.

### Path-scoped instructions

Create one instructions file per skill, scoped to relevant file patterns:

```bash
# Drift — scoped to Drift config files
echo '---\napplyTo: "**/drift.yaml,**/*.tests.yaml,**/*.dataset.yaml"\n---\n' > .github/instructions/drift.instructions.md
cat skills/drift/SKILL.md skills/drift/references/*.md >> .github/instructions/drift.instructions.md

# OpenAPI Parser — scoped to OpenAPI spec files
echo '---\napplyTo: "**/openapi.yaml,**/openapi.json,**/*.oas.yaml"\n---\n' > .github/instructions/openapi-parser.instructions.md
cat skills/openapi-parser/SKILL.md skills/openapi-parser/references/*.md >> .github/instructions/openapi-parser.instructions.md
```

### Reusable prompts (invoke on demand)

1. Enable prompt files in VS Code settings:
   ```json
   { "chat.promptFiles": true }
   ```
2. Create a prompt file per skill:
   ```bash
   cat skills/drift/SKILL.md skills/drift/references/*.md > .github/prompts/drift.prompt.md
   cat skills/openapi-parser/SKILL.md skills/openapi-parser/references/*.md > .github/prompts/openapi-parser.prompt.md
   ```
3. In Copilot Chat, click **Attach context → Prompt...** and select the skill.

---

## Skill contents

```
skills/
├── drift/
│   ├── SKILL.md                  # Drift CLI usage, test case patterns, auth, CI/CD
│   └── references/
│       ├── test-cases.md         # Full test case YAML schema
│       ├── lua-api.md            # Complete Lua API and lifecycle hooks
│       ├── cli-reference.md      # All CLI commands and flags
│       └── pactflow-and-cicd.md  # BDCT publishing, GitHub Actions, GitLab CI
│
└── openapi-parser/
    ├── SKILL.md                  # Workflow: locate → resolve → enumerate → generate
    └── references/
        ├── schema-patterns.md    # anyOf/oneOf/allOf/discriminator/$ref/enum/pattern/nullable
        └── drift-mapping.md      # Mapping every pattern to Drift YAML with full examples
```

**Drift** documentation: https://pactflow.github.io/drift-docs/
