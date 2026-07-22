# `contract-testing-flywheel`

Takes a development team from zero to publishing both consumer and provider contract tests on **[PactFlow](https://pactflow.io)**, by generating a structured onboarding backlog modelled on the Contract Testing Flywheel: Planning → Requirements → Design → Implementation → Testing → Deployment → Lessons-Learned, with an optional management dashboard.

PactFlow is the target broker — it's what hosts pacticipants, runs `can-i-deploy`, surfaces the cross-contract matrix, and (for BDCT) drives provider-contract verification via Drift. The plugin is language-, CI-, and team-agnostic; it's also **scrum-tool-agnostic**: it drives Jira, GitHub Issues/Projects, or Azure DevOps directly if one is connected, or renders the whole backlog as a markdown export you can import into anything else. Everything else (stack, CI tool, repos, notification channel, even the project/workspace identifier) is asked at runtime and parametrised into the templates.

- **Slash command:** `/contract-testing-flywheel`
- **Depends on:** nothing required — connecting one of the Atlassian (Jira) MCP, `gh` CLI / a GitHub MCP, or `az boards` / an Azure DevOps MCP unlocks live ticket creation for that tool; without any of them, the plugin renders a manual export instead.
- **Skill:** [`skills/contract-testing-flywheel/SKILL.md`](skills/contract-testing-flywheel/SKILL.md)

## What it does

Given a short Q&A — which scrum tool, project/workspace identifier, team name, consumer system, provider system, language/stack, CT mode (CDCT / BDCT / Both), CI tool, optional broker URL — the plugin generates a single backlog:

```
<root item> ── Contract Testing Onboarding: <team> (<consumer> ↔ <provider>)
  ├── Task            ── 1. Planning
  ├── Task            ── 2. Requirements Analysis
  ├── Task            ── 3a. Design — Knowledge ramp-up
  ├── Task            ── 3b. Design — Local CT demo
  ├── <delivery item> ── 4. Consumer-side contract tests
  ├── <delivery item> ── 4b. Provider-side verification
  ├── <delivery item> ── 5. Testing — first CI trigger
  ├── <delivery item> ── 6. Deployment — can-i-deploy + record-deployment
  ├── Task            ── 7. Internal docs — lessons learned + best practices
  └── <delivery item> ── 8. Management dashboard (optional, opt-in)
```

Phases 1, 2, 3a, 3b, 7 are filed as **Tasks** (bounded prep / learning / doc-capture work) in every supported tool. Phases 4, 4b, 5, 6, 8 are filed as the tool's **delivery-work item type** — Story in Jira, Feature in GitHub, User Story/Product Backlog Item/Issue in Azure DevOps depending on process template.

Each ticket has its own **Why**, **What to do**, **Acceptance criteria**, and **Helpful links** sections, parametrised by the inputs. The BDCT variant additionally references the Drift CLI, OpenAPI test-case generation, lifecycle hooks, and cross-contract verification.

## Which scrum tool?

The plugin asks at runtime which tool to target — Jira, GitHub Issues/Projects, Azure DevOps, or a manual markdown export. See [`skills/contract-testing-flywheel/lib/scrum-tool-adapters.md`](skills/contract-testing-flywheel/lib/scrum-tool-adapters.md) for exactly how each tool's hierarchy, idempotency check, and create/link/comment calls work.

- **Jira** — via the Atlassian MCP. Same behavior as the original Jira-only version of this plugin.
- **GitHub Issues/Projects** — via the `gh` CLI (or a GitHub MCP if connected). Delivery items use GitHub's native "Feature" issue type where available, else a label.
- **Azure DevOps / Azure Boards** — via the `az boards` CLI (or an Azure DevOps MCP if connected). Asks which process template (Agile / Scrum / Basic) to resolve the delivery-item type name.
- **Anything else (Linear, Trello, Asana, ClickUp, …)** — not first-class, but still fully usable: choose "Other/manual export" and the plugin renders the complete backlog as one markdown document to copy or import.

## CDCT vs BDCT

The plugin asks at runtime. Choose:

- **CDCT** — consumer-driven contract testing via Pact, published to PactFlow. The Implementation tickets reference the right Pact library for your stack (`@pact-foundation/pact`, `pact-jvm`, `pact-python`, `pact-go`, `PactNet`, `pact-ruby`, `pact-rust`).
- **BDCT** — Bi-Directional Contract Testing via OpenAPI + Drift, published to PactFlow. The Provider-side ticket switches to a Drift-shaped AC list: install Drift CLI, generate test cases from the spec, run them in CI, publish the OpenAPI contract via PactFlow's BDCT flow, cross-verify against the consumer's recorded expectations.
- **Both** — both tracks generated; teams running mixed integrations get one bundle.

## Drop-in CLAUDE.md examples

`examples/` ships three `CLAUDE.md` templates ready to copy into the new consumer or provider repos created during Phase 4 / 4b:

- [`examples/CLAUDE.md.cdct-consumer.md`](examples/CLAUDE.md.cdct-consumer.md) — for a Pact consumer repo. Names the right tooling (`swagger-contract-testing:pact-generator` and `:pact-reviewer` agents, `swagger-contract-testing:pactflow` skill) and house rules.
- [`examples/CLAUDE.md.cdct-provider.md`](examples/CLAUDE.md.cdct-provider.md) — for a Pact provider repo (CDCT). Names the right tooling (`swagger-contract-testing:pactflow` skill, `:pact-reviewer` agent) and provider-state conventions.
- [`examples/CLAUDE.md.bdct-drift-provider.md`](examples/CLAUDE.md.bdct-drift-provider.md) — for a BDCT provider repo using Drift. Names the right tooling (`swagger-contract-testing:drift-testing` and `:openapi-parser` skills, `swagger-contract-testing:pactflow` skill), Drift conventions, and BDCT publish flow.

In live-creation mode, the Implementation tickets (4 and 4b) carry an explicit AC line requiring teams to drop the matching file into the new repo, and the rendered file is posted as a comment on each ticket (Step 6.5). In manual-export mode, the snippets are inlined directly under the Phase 4 / 4b sections of the export.

## Generic across team, stack, CI, and scrum tool

The plugin makes no assumptions about your organisation, language, CI tool, notification channel, or ticket tracker. Generated tickets reference only public docs: [`docs.pactflow.io`](https://docs.pactflow.io) (PactFlow), [`pactflow.github.io`](https://pactflow.github.io) (Drift), [`docs.pact.io`](https://docs.pact.io) (Pact protocol), and [`github.com/pact-foundation`](https://github.com/pact-foundation) (libraries). No internal wiki links. When you supply your PactFlow tenant URL at runtime it's substituted into every ticket; when you don't, ticket wording falls back to "your PactFlow tenant" so the team picks the URL at triage time.

## Prerequisites

None are required — the manual-export path always works. To unlock live ticket creation, connect one of:

- An Atlassian (Jira) MCP server, authenticated, with write access to the target Jira project.
- The `gh` CLI, authenticated (`gh auth login`) with write access to the target repo — or a GitHub MCP server.
- The `az boards` CLI extension, configured (`az devops configure --defaults organization=<org> project=<project>`) with write access — or an Azure DevOps MCP server.

## Idempotency

In live-creation mode, the plugin searches the chosen tool for an existing root item by label/tag (`contract-testing-flywheel`) and team name before creating anything — see `lib/scrum-tool-adapters.md` for the exact query per tool. If one already exists, it bails with a hint to re-run with `--force` (the only way to override). Manual-export mode has no idempotency check — it never creates anything, so there's nothing to collide with.

## Related skills and plugins

Referenced from the footer of every generated ticket so the team has an obvious next step inside Claude Code:

- [`/swagger-contract-testing`](https://github.com/pactflow/pactflow-agent-skills) — end-to-end help authoring and running contract tests (CDCT and BDCT).
- `swagger-contract-testing:pact-generator` / `:pact-reviewer` agents — author and review Pact tests.
- `swagger-contract-testing:pactflow` skill — drive PactFlow operations (publish, can-i-deploy, matrix).
- `swagger-contract-testing:drift-testing` / `:openapi-parser` skills — BDCT-only; write and debug Drift test cases, and generate them from complex OpenAPI schemas.
