---
name: contract-testing-flywheel
description: Generate a structured onboarding backlog — in Jira, GitHub Issues/Projects, Azure DevOps, or as a manual markdown export — that drives a development team from zero to publishing both consumer and provider contract tests. Use when the user invokes /contract-testing-flywheel or asks to "kick off contract testing for a team", "create the contract-testing onboarding tickets", or "scaffold the BDCT / CDCT rollout backlog for <team>". Asks which scrum tool, and CDCT / BDCT / Both, at runtime and parametrises tickets by stack, broker, CI tool, and consumer/provider pair. Generic — no SmartBear-internal assumptions, no fixed scrum-tool dependency.
argument-hint: <PROJECT-KEY-or-repo-or-blank>
disable-model-invocation: true
---

# contract-testing-flywheel

Generates a one-shot onboarding backlog for a team's contract-testing rollout, modelled on the 7-stage Contract Testing Flywheel (with the Maintenance phase replaced by Lessons-Learned + an optional Management Dashboard, per the plugin's design). Works with Jira, GitHub Issues/Projects, or Azure DevOps — or, if none of those is connected, renders the whole backlog as a markdown export for manual import.

## Step 1 — Choose the scrum tool

Ask: "Which tool should this backlog go into? Jira · GitHub Issues/Projects · Azure DevOps · Other/manual export"

Use `$ARGUMENTS` to skip this question only if it unambiguously names one of the three tools (e.g. `--tool=github`); otherwise ask.

Then check that tool's **availability check** in `lib/scrum-tool-adapters.md`:

- **Available** → note the adapter row (hierarchy terms, idempotency query, create/link/comment mechanism) and continue to Step 2 in live-creation mode.
- **Not available** (tool chosen but its MCP/CLI isn't connected), or **"Other/manual export"** chosen → continue to Step 2 in manual-export mode. This is not an error: if a specific tool was chosen but isn't connected, mention once that connecting it (Atlassian MCP for Jira, `gh auth login` or a GitHub MCP for GitHub, `az login` + `az extension add --name azure-devops` or an Azure DevOps MCP for Azure DevOps) would enable live creation next time, then proceed with the export anyway. Do not hard-stop.

When both an MCP server and a CLI could serve the chosen tool, prefer the MCP's equivalent tools when one is connected; use the CLI otherwise.

## Step 2 — Gather inputs

Resolve each input in order. Use `$ARGUMENTS` for input 1 if present; only ask for what is not already known.

| # | Input | How to resolve |
|---|---|---|
| 1 | Project / workspace identifier | `$ARGUMENTS` first; otherwise ask, shaped by the Step 1 tool: Jira project key (e.g. `PACT`) · GitHub `owner/repo` · Azure DevOps `org/project`. Skip if manual-export mode with no tool chosen. |
| 2 | Team / unit name | Ask. Used to title the root item and label tickets. |
| 3 | Consumer system name | Ask. Single value. |
| 4 | Provider system name | Ask. Single value. |
| 5 | Primary language / stack | Single-choice ask: Node/TS · JVM · Python · Go · .NET · Ruby · Rust · Other |
| 6 | CT mode | Single-choice ask: CDCT · BDCT · Both |
| 7 | Broker URL (optional) | Ask, allow blank. If blank, ticket wording uses "your Pact Broker or PactFlow tenant". |
| 8 | CI tool | Single-choice ask: GitHub Actions · GitLab CI · Buildkite · Jenkins · CircleCI · Other |
| 9 | Include optional Phase 8 (management dashboard)? | Yes/no. |
| 10 | *(Azure DevOps only)* Process template | Single-choice ask: Agile (default) · Scrum · Basic — resolves `{{delivery_term}}` per `lib/scrum-tool-adapters.md`. Skip entirely for every other tool. |

Do not guess. Asking is cheap; mis-filed backlogs are not.

## Step 3 — Idempotency check

Skip this step entirely in manual-export mode.

Otherwise, run the chosen tool's idempotency-check query from `lib/scrum-tool-adapters.md`, substituting the Step 2 project/team values. If a matching root item already exists, stop and tell the user:

> A root {{root_term}} for `<team>` already exists: `<id>` (<url>). Re-run with `--force` if you intend to create a second backlog (e.g. for a different consumer/provider pair under the same team).

Continue if `--force` was passed in `$ARGUMENTS` or no match was found.

## Step 4 — Compose the ticket bundle

Load templates from `templates/` and substitute placeholders. Every template opens with a `# {{title: <text>}}` line — `<text>` (itself containing further placeholders) is the item's title/summary field; strip the `{{title: ...}}` wrapper and use its substituted contents as the title when creating the item, and drop the wrapper line from the item's body.

Placeholder set:

| Token | Source |
|---|---|
| `{{team}}` | Step 2.2 |
| `{{consumer}}` | Step 2.3 |
| `{{provider}}` | Step 2.4 |
| `{{stack}}` | Step 2.5 |
| `{{pact_library}}` + `{{pact_library_url}}` | Lookup in `lib/stack-pact-libraries.md` |
| `{{ct_mode}}` | Step 2.6 — one of `CDCT`, `BDCT`, `Both` |
| `{{broker_url_or_phrase}}` | Step 2.7 — the URL, or "your Pact Broker or PactFlow tenant" |
| `{{ci_tool}}` + `{{ci_docs_url}}` | Step 2.8 + lookup in `lib/ci-snippet-pointers.md` |
| `{{openapi_path}}` | Default `openapi.yaml` (placeholder; provider repo team will adjust) |
| `{{root_term}}` | Step 1's chosen tool, looked up in `lib/scrum-tool-adapters.md` (neutral default "Epic" in manual-export mode) |
| `{{delivery_term}}` | Same lookup (neutral default "Story"; for Azure DevOps, resolved from Step 2.10's process template) |

**CDCT / BDCT block selection.** Templates `03b-design-demo.md`, `04-implementation-consumer.md`, `04b-implementation-provider.md`, and `05-testing.md` contain explicit `<!-- BEGIN CDCT --> ... <!-- END CDCT -->` and `<!-- BEGIN BDCT --> ... <!-- END BDCT -->` sections. Keep:

- `CDCT` only → keep CDCT blocks, strip BDCT blocks.
- `BDCT` only → keep BDCT blocks, strip CDCT blocks.
- `Both` → keep both, in order CDCT then BDCT, with a separating heading `## BDCT track` before the BDCT block.

When BDCT or Both is selected, append the Drift link bundle from `lib/drift-helpful-links.md` to the Helpful links section of those four templates.

Skip `08-management-dashboard.md` entirely if the user answered "no" to Step 2.9.

## Issue-type mapping

Each template maps to a work-item type. Resolve `{{root_term}}` / `{{delivery_term}}` from `lib/scrum-tool-adapters.md`; "Task" is literal in every tool.

| Template | Phase | Item type |
|---|---|---|
| `00-root-epic.md` | Root | `{{root_term}}` |
| `01-planning.md` | 1 | Task |
| `02-requirements.md` | 2 | Task |
| `03a-design-knowledge.md` | 3a | Task |
| `03b-design-demo.md` | 3b | Task |
| `04-implementation-consumer.md` | 4 | `{{delivery_term}}` |
| `04b-implementation-provider.md` | 4b | `{{delivery_term}}` |
| `05-testing.md` | 5 | `{{delivery_term}}` |
| `06-deployment.md` | 6 | `{{delivery_term}}` |
| `07-lessons-learned.md` | 7 | Task |
| `08-management-dashboard.md` | 8 | `{{delivery_term}}` |

Rationale: phases 1, 2, 3a, 3b, 7 are bounded "do this and tick it off" work (planning sessions, metric baselines, learning, demo, doc capture) — Tasks suit them. Phases 4, 4b, 5, 6, 8 are user-value-delivery work — the tool's delivery-item type suits them.

## Markdown caveats

Use plain bullets (`-`) for acceptance criteria in every ticket body, not GitHub-flavoured task-list syntax (`- [ ]`). This is a universal-safety default — some tools (Jira) mangle task-list syntax into literal escaped brackets — rather than something to special-case per tool. The "Acceptance criteria" heading already signals these are conditions to verify. The templates in this plugin already follow this rule.

## Step 5 — Dry-run preview

Print to the terminal. In live-creation mode:

```
About to create in <tool> · <project/workspace>:

  Root  ─ {{root_term}}   ─ "Contract Testing Onboarding: <team> (<consumer> ↔ <provider>)"
  ├──── Task   ─ "1. Planning"
  ├──── Task   ─ "2. Requirements Analysis"
  ├──── Task   ─ "3a. Design — Knowledge ramp-up"
  ├──── Task   ─ "3b. Design — Local CT demo"
  ├──── {{delivery_term}}  ─ "4. Consumer-side contract tests"
  ├──── {{delivery_term}}  ─ "4b. Provider-side verification"
  ├──── {{delivery_term}}  ─ "5. Testing — first CI trigger"
  ├──── {{delivery_term}}  ─ "6. Deployment — can-i-deploy + record-deployment"
  ├──── Task   ─ "7. Internal docs — lessons learned + best practices"
  └──── {{delivery_term}}  ─ "8. Management dashboard"        (only if opted in)

Mode: <ct_mode>      Stack: <stack>      CI: <ci_tool>      Broker: <broker_url_or_phrase>

Each item will be assigned to you, labelled 'contract-testing-flywheel',
'contract-testing-onboarding', and '<cdct|bdct|both>'. Children will be
linked to the root {{root_term}}. Status: Backlog. No sprint assignment.

Proceed? (y/N)
```

In manual-export mode, print instead:

```
No live tool connected (or manual export chosen) — rendering the full
backlog below as markdown. Copy the sections you need into <tool of choice>.

Mode: <ct_mode>      Stack: <stack>      CI: <ci_tool>      Broker: <broker_url_or_phrase>
```

...followed immediately by the full rendered backlog (root item body, then each child in phase order, each under its own `## <phase> — <title>` heading), with no further confirmation prompt needed — nothing is being created, so there's nothing to confirm.

If the user does not answer `y` in live-creation mode, abort cleanly. Print nothing was created.

## Step 6 — Execute

Skip entirely in manual-export mode (Step 5 already produced the full output).

1. Create the root item with the rendered `00-root-epic.md` body.
2. Create each child item (1, 2, 3a, 3b, 4, 4b, 5, 6, 7, optionally 8) via the chosen adapter's create call. These can be issued in parallel.
3. For each child, link it to the root via the chosen adapter's link mechanism.
4. If any single creation fails, continue with the remaining ones. Collect failures into a list to report in Step 7.

## Step 6.5 — Attach the rendered CLAUDE.md to the Implementation tickets

Skip entirely in manual-export mode (Step 5's export already inlines the CLAUDE.md snippets under Phase 4 / 4b).

For each Implementation ticket created in Step 6, post one comment via the chosen adapter's comment mechanism:

- **Consumer ticket (Phase 4)** — the rendered `examples/CLAUDE.md.cdct-consumer.md`, with placeholders substituted from Step 4. Wrap the body in a fenced markdown block so the assignee can copy it straight into the new consumer repo.
- **Provider ticket (Phase 4b)** — the rendered `examples/CLAUDE.md.bdct-drift-provider.md` if `{{ct_mode}}` is `BDCT` or `Both`; otherwise `examples/CLAUDE.md.cdct-provider.md`. Same wrapping.

Each comment should lead with a short heading like `## CLAUDE.md template for the new <repo> repo` and a one-line instruction telling the assignee to copy the fenced block into `CLAUDE.md` at the new repo's root. Include a link back to the source template in the plugin repo so the team can see the canonical version.

This is best-effort: if the comment creation fails for one of the two tickets, continue and report the failure in Step 7 (do not roll back the Implementation ticket itself).

## Step 7 — Print results

In live-creation mode:

```
Created in <tool> · <project/workspace>:

  {{root_term}}   <id-1>   Contract Testing Onboarding: <team> (<consumer> ↔ <provider>)
                   <item-url-1>
  {{delivery_term}}  <id-2>   1. Planning
                   <item-url-2>
  ...

Next steps:
  - Open the root {{root_term}} and triage into your sprint plan.
  - When Phase 4 / 4b kicks off, drop the matching CLAUDE.md from this
    plugin's examples/ folder into the new consumer / provider repo:
      examples/CLAUDE.md.cdct-consumer.md
      examples/CLAUDE.md.cdct-provider.md
      examples/CLAUDE.md.bdct-drift-provider.md
  - For end-to-end help authoring tests, see /swagger-contract-testing.
```

If any creation failed in Step 6, list the failures clearly with the error message, but do not roll back the successful ones — none of the three supported tools' issue creation is transactional, and the partial backlog is still useful.

In manual-export mode, Step 5's output already is the deliverable — Step 7 just prints the same "Next steps" block (minus the item table, since nothing has an id or URL yet).

## Notes for skill maintainers

- **Templates carry the content.** This SKILL.md is orchestration; the actual ticket prose lives in `templates/` and `lib/`. Update there.
- **`lib/scrum-tool-adapters.md` is the tool-abstraction boundary.** Adding a fourth first-class tool (e.g. Linear) means adding one row there plus its availability/idempotency/create/link/comment mechanism — SKILL.md itself shouldn't need to change.
- **CDCT/BDCT block markers are the contract.** If you rename `<!-- BEGIN CDCT -->` etc., update Step 4 to match.
- **Continue-on-error in Step 6 is deliberate.** A flaky create/link call shouldn't sink the whole bundle.
- **No sprint assignment, no estimates.** The backlog is meant to be triaged by the team into their own planning cadence.
