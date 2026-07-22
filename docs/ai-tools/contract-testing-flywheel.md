# Contract Testing Flywheel plugin

## What it is

`contract-testing-flywheel` is a workflow plugin, not a knowledge skill — instead of standing by to answer contract-testing questions, it does one job on demand: turn a short Q&A into a complete onboarding backlog that takes a team from "we've never written a contract test" to "consumer and provider contracts are published, verified, and gating deploys on PactFlow."

It's invoked as a slash command, `/contract-testing-flywheel`, and it's scrum-tool-agnostic — it can create the backlog live in Jira, GitHub Issues/Projects, or Azure DevOps, or (if none of those is connected) render the whole thing as a markdown document you paste into whatever tool your team actually uses.

The backlog follows the Contract Testing Flywheel methodology: Planning → Requirements → Design (knowledge + demo) → Implementation (consumer + provider) → Testing → Deployment → Lessons-Learned, with an optional Management Dashboard phase.

## Installing

See the root [README's install section](../../README.md#installing-contract-testing-flywheel) for the exact commands. Short version:

```claude
/plugin marketplace add pactflow/pactflow-agent-skills
/plugin install contract-testing-flywheel@pactflow-agent-skills
```

No credentials or MCP server are required to install it — it has no bundled MCP of its own. Live ticket creation is unlocked separately, per scrum tool, as described below.

## Using it

Run the slash command:

```claude
/contract-testing-flywheel
```

It asks a short, ordered set of questions — answer each, or supply the project/repo identifier as an argument (`/contract-testing-flywheel PACT`, `/contract-testing-flywheel my-org/my-repo`, `/contract-testing-flywheel my-ado-org/my-ado-project`):

1. Which scrum tool — Jira, GitHub Issues/Projects, Azure DevOps, or Other/manual export.
2. Project or workspace identifier (shaped by the tool you picked).
3. Team / unit name.
4. Consumer system name.
5. Provider system name.
6. Primary language / stack (Node/TS, JVM, Python, Go, .NET, Ruby, Rust, Other).
7. CT mode — CDCT, BDCT, or Both.
8. Broker URL (optional — falls back to "your Pact Broker or PactFlow tenant" if left blank).
9. CI tool (GitHub Actions, GitLab CI, Buildkite, Jenkins, CircleCI, Other).
10. Whether to include the optional management-dashboard ticket.
11. If you picked Azure DevOps: which process template (Agile / Scrum / Basic), since that decides what the delivery-item type is called.

It then checks whether a matching backlog already exists (so reruns don't duplicate work), shows a dry-run preview of exactly what it's about to create, and — once you confirm — creates the root item and every child item, links them together, and (for the two Implementation tickets) posts the matching `CLAUDE.md` drop-in file as a comment so whoever picks up that ticket can copy it straight into the new repo.

If you picked "Other/manual export," or the tool you picked isn't actually connected, it skips straight to rendering the entire backlog as one markdown document instead — nothing is created, there's nothing to confirm, and the `CLAUDE.md` snippets are inlined directly under the relevant sections rather than posted as comments.

## Which scrum tool

- **Jira** — via the Atlassian MCP. Root item is an Epic, delivery-phase items are Stories, idempotency is a JQL search on a `contract-testing-flywheel` label.
- **GitHub Issues/Projects** — via the `gh` CLI (or a GitHub MCP if one is connected). Root item is a tracking issue; delivery-phase items use GitHub's native "Feature" issue type where available, else a label.
- **Azure DevOps / Azure Boards** — via the `az boards` CLI (or an Azure DevOps MCP if connected). Root item is an Epic; delivery-phase item type depends on the process template you name (User Story for Agile, Product Backlog Item for Scrum, Issue for Basic).
- **Anything else** (Linear, Trello, Asana, ClickUp, …) — pick "Other/manual export." Not first-class, but fully usable: you get the same backlog as one markdown document to import by hand.

The full mechanics — exact idempotency queries, create/link/comment calls per tool — live in the plugin's [`lib/scrum-tool-adapters.md`](../../plugins/contract-testing-flywheel/skills/contract-testing-flywheel/lib/scrum-tool-adapters.md) reference file, which is also where you'd add a new tool as a first-class adapter later.

## CDCT vs BDCT

- **CDCT** (consumer-driven contract testing via Pact) — the Implementation tickets reference the right Pact library for your stack automatically (`@pact-foundation/pact`, `pact-jvm`, `pact-python`, `pact-go`, `PactNet`, `pact-ruby`, `pact-rust`).
- **BDCT** (Bi-Directional Contract Testing via OpenAPI + Drift) — the provider-side ticket switches to a Drift-shaped checklist: install the Drift CLI, generate test cases from the OpenAPI spec, run them in CI, publish the spec via PactFlow's BDCT flow, and cross-verify against the consumer's recorded expectations.
- **Both** — generates both tracks in one bundle, for teams running mixed integrations.

## The generated backlog

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

Every item carries its own **Why**, **What to do**, **Acceptance criteria**, and **References** sections, filled in from your answers. Phases 1, 2, 3a, 3b, and 7 are bounded prep/learning/doc-capture work (filed as Tasks in every tool); phases 4, 4b, 5, 6, and 8 are user-value delivery work (filed as the tool's delivery-item type).

## CLAUDE.md drop-in examples

The plugin ships three ready-made `CLAUDE.md` templates, one per repo role, so a future Claude Code session in the new consumer or provider repo inherits the right skills and house rules automatically:

- `CLAUDE.md.cdct-consumer.md` — Pact consumer repo.
- `CLAUDE.md.cdct-provider.md` — Pact provider repo (CDCT).
- `CLAUDE.md.bdct-drift-provider.md` — Drift-based provider repo (BDCT).

In live-creation mode these get posted as a comment on the matching Implementation ticket; in manual-export mode they're inlined directly in the export.

## Prerequisites

None are required — the manual-export path always works with nothing connected. To unlock live ticket creation, connect one of:

- An Atlassian (Jira) MCP server, authenticated, with write access to the target Jira project.
- The `gh` CLI, authenticated (`gh auth login`), with write access to the target repo — or a GitHub MCP server.
- The `az boards` CLI extension, configured (`az devops configure --defaults organization=<org> project=<project>`) — or an Azure DevOps MCP server.

## Idempotency

Before creating anything, the plugin searches the chosen tool for an existing root item labelled `contract-testing-flywheel` for the same team name. If one already exists, it stops and tells you where, with a hint to re-run with `--force` if you actually want a second backlog (e.g. a different consumer/provider pair for the same team). Manual-export mode skips this check entirely — it never creates anything, so there's nothing to collide with.

## Troubleshooting

- **"A root item already exists" but you wanted a fresh one** — pass `--force`, or use a different team name if this is genuinely a different rollout.
- **You picked a tool but got the manual-export output anyway** — the plugin couldn't confirm that tool's MCP/CLI is connected. Connect it (see Prerequisites) and re-run for live creation next time; the export you already got is still valid to import by hand.
- **Azure DevOps items come out with an unexpected type name** — double check the process template you named (Agile/Scrum/Basic); each maps to a different delivery-item type name.

## Related skills and plugins

The backlog's Implementation and Testing tickets point teams at:

- [`/swagger-contract-testing`](../../plugins/swagger-contract-testing) — end-to-end help authoring and running contract tests (CDCT and BDCT).
- `swagger-contract-testing:pact-generator` / `:pact-reviewer` agents — author and review Pact tests.
- `swagger-contract-testing:pactflow` skill — publish contracts, run can-i-deploy, inspect the matrix.
- `swagger-contract-testing:drift-testing` / `:openapi-parser` skills — BDCT-only; write and debug Drift test cases, and generate them from complex OpenAPI schemas.

For the full technical reference (exact placeholders, per-tool adapter mechanics, template layout), see the plugin's own [README](../../plugins/contract-testing-flywheel/README.md) and [SKILL.md](../../plugins/contract-testing-flywheel/skills/contract-testing-flywheel/SKILL.md).
