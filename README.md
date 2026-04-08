# PactFlow Agent Skills

AI assistant skills for PactFlow's contract testing tools.

| Plugin name                | What it does                                                                                                                                                                                                                                                                                       |
| -------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `swagger-contract-testing` | Expert assistant for PactFlow's OpenAPI contract testing tools. Includes two skills: **Drift** (write test cases, configure lifecycle hooks, debug failures, publish results to PactFlow) and **OpenAPI Parser** (parse complex specs with anyOf/oneOf/allOf, discriminators, $ref chains, regex). |

The two skills are designed to work together: OpenAPI Parser analyses a spec and generates
test case scaffolding; Drift runs, iterates, and publishes those tests.

---

## Installation guide for Agentic IDEs/Coding agents

- [Claude Code](#installing-in-claude-code)
- [OpenCode](#installing-in-opencode)
- [GitHub Copilot (VS Code)](#installing-in-github-copilot-vs-code)
- [Cursor](#installing-in-cursor)
- [Windsurf](#installing-in-windsurf)
- [Codex](#installing-in-codex)
- [Kiro](#installing-in-kiro)
- [Antigravity](#installing-in-antigravity)

### Windows users

The install commands throughout this guide use Unix shell syntax. In PowerShell, replace:

| Unix                                     | PowerShell                                              |
| ---------------------------------------- | ------------------------------------------------------- |
| `mkdir -p path/to/dir`                   | `New-Item -ItemType Directory -Force -Path path\to\dir` |
| `cp -r skills/drift-testing path/to/dir` | `Copy-Item -Recurse skills\drift-testing path\to\dir`   |

`~` (home directory) works in PowerShell 3+. In older environments use `$HOME` instead.

---

## Installing in Claude Code

Claude Code supports [Skills](https://code.claude.com/docs/en/skills) via a plugin marketplace system. Requires Claude Code v1.0.33+.

### From this repo (recommended for teams)

> **Note:** Because these skills are not listed in Anthropic's official plugin registry, the `.claude/settings.json` configuration below is **mandatory** — without it Claude Code won't know where to find the marketplace and the `/plugin install` commands will fail.

**1. Add the marketplace** inside a Claude Code session:

```claude
/plugin marketplace add pactflow/pactflow-agent-skills
```

Or add it to `.claude/settings.json` so teammates are prompted to install it automatically when they open the project:

```json
{
  "extraKnownMarketplaces": {
    "pactflow-agent-skills": {
      "source": {
        "source": "github",
        "repo": "pactflow/pactflow-agent-skills"
      }
    }
  }
}
```

**2. Install the plugin:**

```claude
/plugin install swagger-contract-testing@pactflow-agent-skills
```

**Scope options:**

| Scope            | Stored in                     | Who it applies to                       |
| ---------------- | ----------------------------- | --------------------------------------- |
| `user` (default) | `~/.claude/settings.json`     | You, across all projects                |
| `project`        | `.claude/settings.json`       | Everyone on the team (commit this file) |
| `local`          | `.claude/settings.local.json` | You, in this project only (gitignored)  |

### From a local clone

```claude
/plugin marketplace add ./path/to/pactflow-agent-skills/.claude-plugin/marketplace.json
/plugin install swagger-contract-testing@pactflow-agent-skills
```

### For local development (no marketplace needed)

```bash
claude --plugin-dir ./plugins/swagger-contract-testing
```

### Managing plugins

```claude
/plugin                          # open plugin manager (Discover / Installed / Marketplaces / Errors)
/reload-plugins                  # reload without restarting
/plugin disable swagger-contract-testing@pactflow-agent-skills
/plugin uninstall swagger-contract-testing@pactflow-agent-skills
```

---

## Installing in OpenCode

OpenCode supports [Agent Skills](https://opencode.ai/docs/skills) loaded from `SKILL.md` files in named subdirectories. The agent
automatically selects relevant skills based on task context.

### Global install (available in all projects)

```bash
cp -r skills/drift-testing ~/.config/opencode/skills/drift-testing
cp -r skills/openapi-parser ~/.config/opencode/skills/openapi-parser
```

### Project-level install (this project only)

```bash
mkdir -p .opencode/skills
cp -r skills/drift-testing .opencode/skills/drift-testing
cp -r skills/openapi-parser .opencode/skills/openapi-parser
```

OpenCode will pick up the skills automatically — no restart required.

---

## Installing in GitHub Copilot (VS Code)

VS Code Copilot supports [Agent Skills](https://code.visualstudio.com/docs/copilot/customization/agent-skills)
natively. Skills are loaded from `SKILL.md` files in named subdirectories and invoked as slash commands
in Copilot Chat (`/drift-testing`, `/openapi-parser`). Copilot also auto-loads relevant skills based on context.

### Project-level install (recommended for teams)

Copy the skill folders into any of the standard discovery locations — Copilot checks all of them:

```bash
# .github/skills  (most common for GitHub projects)
mkdir -p .github/skills
cp -r skills/drift-testing .github/skills/drift-testing
cp -r skills/openapi-parser .github/skills/openapi-parser

# or .agents/skills
mkdir -p .agents/skills
cp -r skills/drift-testing .agents/skills/drift-testing
cp -r skills/openapi-parser .agents/skills/openapi-parser

# or .claude/skills (already used by Claude Code)
mkdir -p .claude/skills
cp -r skills/drift-testing .claude/skills/drift-testing
cp -r skills/openapi-parser .claude/skills/openapi-parser
```

Commit the chosen directory to share the skills with your team. No VS Code configuration required.

### Personal install (all your projects)

Copy to a personal skills directory so the skills are available in every repo you open:

```bash
mkdir -p ~/.copilot/skills
cp -r skills/drift-testing ~/.copilot/skills/drift-testing
cp -r skills/openapi-parser ~/.copilot/skills/openapi-parser
```

### Custom location

Point Copilot at any directory via VS Code settings:

```json
{
  "chat.agentSkillsLocations": ["/path/to/your/skills"]
}
```

### Using the skills in Copilot Chat

Once installed, open Copilot Chat and invoke a skill by name:

```claude
/drift-testing write a test case for POST /orders returning 201
/openapi-parser generate Drift tests for the payments spec
```

You can also type `/skills` in chat to browse and configure installed skills. Copilot will
auto-load a skill when it detects a relevant task even without an explicit slash command.

---

### Fallback: custom instructions (older Copilot versions)

If your version of Copilot doesn't support Agent Skills yet, use custom instructions instead.

**Repo-wide** — applies to every conversation in the repository:

```bash
cat skills/drift-testing/SKILL.md skills/drift-testing/references/*.md >> .github/copilot-instructions.md
cat skills/openapi-parser/SKILL.md skills/openapi-parser/references/*.md >> .github/copilot-instructions.md
```

**Path-scoped** — loads only when relevant files are open:

```bash
# Drift — scoped to Drift config files
echo '---\napplyTo: "**/drift.yaml,**/*.tests.yaml,**/*.dataset.yaml"\n---\n' > .github/instructions/drift.instructions.md
cat skills/drift-testing/SKILL.md skills/drift-testing/references/*.md >> .github/instructions/drift.instructions.md

# OpenAPI Parser — scoped to OpenAPI spec files
echo '---\napplyTo: "**/openapi.yaml,**/openapi.json,**/*.oas.yaml"\n---\n' > .github/instructions/openapi-parser.instructions.md
cat skills/openapi-parser/SKILL.md skills/openapi-parser/references/*.md >> .github/instructions/openapi-parser.instructions.md
```

**Reusable prompts** — attach on demand in chat:

1. Enable prompt files in VS Code settings: `{ "chat.promptFiles": true }`write a Drift test for POST /orders
2. Create prompt files:
   ```bash
   cat skills/drift-testing/SKILL.md skills/drift-testing/references/*.md > .github/prompts/drift.prompt.md
   cat skills/openapi-parser/SKILL.md skills/openapi-parser/references/*.md > .github/prompts/openapi-parser.prompt.md
   ```
3. In Copilot Chat, click **Attach context → Prompt...** and select the skill.

---

## Installing in Cursor

Cursor supports [Agent Skills](https://cursor.com/docs/skills) loaded from `SKILL.md` files in named subdirectories. Skills can be project-scoped or global.

### Remote install from GitHub

1. Open **Cursor Settings → Rules**
2. Click **Add Rule** in Project Rules
3. Select **Remote Rule (GitHub)**
4. Enter the URL to each skill folder:
   - `https://github.com/pactflow/pactflow-agent-skills/tree/main/skills/drift-testing`
   - `https://github.com/pactflow/pactflow-agent-skills/tree/main/skills/openapi-parser`

### Project-level install (manual)

```bash
mkdir -p .cursor/skills
cp -r skills/drift-testing .cursor/skills/drift-testing
cp -r skills/openapi-parser .cursor/skills/openapi-parser
```

Commit `.cursor/skills/` to share the skills with your team. Cursor also discovers skills from `.agents/skills/`.

### Global install (all your projects)

```bash
mkdir -p ~/.cursor/skills
cp -r skills/drift-testing ~/.cursor/skills/drift-testing
cp -r skills/openapi-parser ~/.cursor/skills/openapi-parser
```

---

## Installing in Windsurf

Windsurf supports [Skills](https://docs.windsurf.com/windsurf/cascade/skills) loaded from `SKILL.md` files in named subdirectories. Skills can be workspace-scoped or global.

### From the UI

1. Open the **Cascade** panel
2. Click the **⋯** menu → **Skills**
3. Choose **+ Workspace** (project) or **+ Global**
4. Copy the contents of each `SKILL.md` into the new skill

### Project-level install (manual)

```bash
mkdir -p .windsurf/skills
cp -r skills/drift-testing .windsurf/skills/drift-testing
cp -r skills/openapi-parser .windsurf/skills/openapi-parser
```

Commit `.windsurf/skills/` to share the skills with your team.

### Global install (all your projects)

```bash
mkdir -p ~/.codeium/windsurf/skills
cp -r skills/drift-testing ~/.codeium/windsurf/skills/drift-testing
cp -r skills/openapi-parser ~/.codeium/windsurf/skills/openapi-parser
```

---

## Installing in Codex

Codex supports [Skills](https://developers.openai.com/codex/skills/) loaded from `SKILL.md` files in named subdirectories.

### Using the skill installer

```bash
$skill-installer pactflow/pactflow-agent-skills/skills/drift-testing
$skill-installer pactflow/pactflow-agent-skills/skills/openapi-parser
```

### Project-level install (manual)

```bash
mkdir -p .agents/skills
cp -r skills/drift-testing .agents/skills/drift-testing
cp -r skills/openapi-parser .agents/skills/openapi-parser
```

Commit `.agents/skills/` to share the skills with your team.

### Global install (all your projects)

```bash
mkdir -p ~/.agents/skills
cp -r skills/drift-testing ~/.agents/skills/drift-testing
cp -r skills/openapi-parser ~/.agents/skills/openapi-parser
```

---

## Installing in Kiro

Kiro supports [Agent Skills](https://kiro.dev/docs/skills/) loaded from `SKILL.md` files in named subdirectories. Skills can be workspace-scoped or global.

### Import from GitHub (recommended)

1. Open the **Agent Steering & Skills** panel in Kiro
2. Click **+** → **Import a skill**
3. Select **GitHub** and paste the URL to each skill folder:
   - `https://github.com/pactflow/pactflow-agent-skills/tree/main/skills/drift-testing`
   - `https://github.com/pactflow/pactflow-agent-skills/tree/main/skills/openapi-parser`

Imported skills are copied to your skills directory and work immediately.

### Project-level install (manual)

```bash
mkdir -p .kiro/skills
cp -r skills/drift-testing .kiro/skills/drift-testing
cp -r skills/openapi-parser .kiro/skills/openapi-parser
```

Commit `.kiro/skills/` to share the skills with your team.

### Global install (all your projects)

```bash
mkdir -p ~/.kiro/skills
cp -r skills/drift-testing ~/.kiro/skills/drift-testing
cp -r skills/openapi-parser ~/.kiro/skills/openapi-parser
```

> When both locations contain a skill with the same name, the workspace skill takes priority.

---

## Installing in Antigravity

Antigravity supports [Agent Skills](https://antigravity.google/docs/skills) loaded from `SKILL.md` files in named subdirectories. Skills can be workspace-scoped or global.

### Project-level install (recommended for teams)

```bash
mkdir -p .agents/skills
cp -r skills/drift-testing .agents/skills/drift-testing
cp -r skills/openapi-parser .agents/skills/openapi-parser
```

Commit `.agents/skills/` to share the skills with your team.

### Global install (all your projects)

```bash
mkdir -p ~/.gemini/antigravity/skills
cp -r skills/drift-testing ~/.gemini/antigravity/skills/drift-testing
cp -r skills/openapi-parser ~/.gemini/antigravity/skills/openapi-parser
```

> Antigravity also supports `.agent/skills/` (singular) for backward compatibility.

---

## Skill contents

```
skills/
├── drift-testing/
│   ├── SKILL.md                  # Drift CLI usage, test case patterns, auth, CI/CD
│   ├── references/
│   │   ├── test-cases.md         # Full test case YAML schema
│   │   ├── lua-api.md            # Complete Lua API and lifecycle hooks
│   │   ├── cli-reference.md      # All CLI commands and flags
│   │   ├── auth.md               # Authentication patterns and credential handling
│   │   ├── mock-server.md        # Mock server setup and configuration
│   │   └── pactflow-and-cicd.md  # BDCT publishing, GitHub Actions, GitLab CI
│   ├── evals/
│   │   ├── 01-basic-get-endpoint.json        # Eval: write a test for a GET endpoint
│   │   ├── 02-stateful-delete-endpoint.json  # Eval: write a test for a stateful DELETE endpoint
│   │   ├── 03-debug-failing-test.json        # Eval: debug a failing test
│   │   └── fixtures/
│   │       ├── simple-products-api.yaml      # OpenAPI fixture for basic evals
│   │       └── products-api-with-failures.md # Fixture describing a failing API
│   └── scripts/
│       ├── check_coverage.py     # Coverage analysis script
│       ├── extract_endpoints.py  # Extract endpoints from OpenAPI specs
│       ├── run_loop.sh           # Feedback loop runner (macOS/Linux)
│       ├── run_loop.ps1          # Feedback loop runner (Windows)
│       ├── start_mock.sh         # Start mock server (macOS/Linux)
│       └── start_mock.ps1        # Start mock server (Windows)
│
└── openapi-parser/
    ├── SKILL.md                  # Workflow: locate → resolve → enumerate → generate
    ├── evals/
    │   ├── 01-anyof-parameter-variants.json   # Eval: generate tests for anyOf parameter variants
    │   ├── 02-discriminator-with-allof.json   # Eval: generate tests for discriminator + allOf
    │   ├── 03-regex-pattern-field.json        # Eval: generate tests for regex pattern fields
    │   └── fixtures/
    │       ├── anyof-parameter-variants.yaml  # OpenAPI fixture with anyOf parameters
    │       ├── discriminator-with-allof.yaml  # OpenAPI fixture with discriminator and allOf
    │       └── regex-pattern-field.yaml       # OpenAPI fixture with regex pattern fields
    └── references/
        ├── schema-patterns.md    # anyOf/oneOf/allOf/discriminator/$ref/enum/pattern/nullable
        ├── drift-mapping.md      # Mapping every pattern to Drift YAML with full examples
        └── example-repos.md      # Commands for navigating large OpenAPI spec repositories
```
