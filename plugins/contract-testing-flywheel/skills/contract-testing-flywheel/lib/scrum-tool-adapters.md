# Scrum-tool adapters

Used by SKILL.md Steps 1, 2, 3, 4, 6, 6.5, 7 to resolve `{{root_term}}` / `{{delivery_term}}`, check integration availability, run the idempotency search, and dispatch create/link/comment calls. Pick the row matching the tool chosen in Step 1.

## Jira

- **`{{root_term}}`:** Epic
- **`{{delivery_term}}`:** Story
- **Availability check:** Atlassian MCP is connected (e.g. `getAccessibleAtlassianResources` succeeds).
- **Idempotency check (JQL):**
  ```
  project = <KEY> AND issuetype = Epic AND labels = "contract-testing-flywheel" AND summary ~ "<team>"
  ```
- **Create:** `createJiraIssue` for the Epic and each child, with `labels: ["contract-testing-flywheel", "contract-testing-onboarding", "<cdct|bdct|both>"]` set on every issue (the root Epic's label is what the idempotency JQL above searches on); issue type per the Step-4 mapping table (Epic / Task / Story).
- **Link:** `createIssueLink` with link type "is part of", child → root.
- **Comment (Step 6.5):** `addCommentToJiraIssue`.
- **Item URL (Step 7):** `https://<site>/browse/<KEY-N>`.

## GitHub Issues/Projects

- **`{{root_term}}`:** Tracking issue
- **`{{delivery_term}}`:** Feature (use GitHub's native "Feature" issue type if the repo has custom issue types enabled; otherwise apply a `type:feature` label instead — check with `gh issue-type list` if available, else default to the label).
- **Availability check:** `gh auth status` succeeds, or a GitHub MCP server is connected — prefer the MCP's equivalent tools when present.
- **Idempotency check:**
  ```
  gh issue list --repo <owner>/<repo> --label contract-testing-flywheel --state all --search "<team> in:title"
  ```
- **Create:** `gh issue create --repo <owner>/<repo> --title "<title>" --body "<body>" --label contract-testing-flywheel,contract-testing-onboarding,<cdct|bdct|both>` for the tracking issue and each child. Child items also get `type:task` or `type:feature` labels per the Step-4 mapping table.
- **Link:** if the repo's GitHub plan supports native sub-issues, add each child as a sub-issue of the tracking issue; otherwise add a task-list line (`- [ ] #<child-number>`) to the tracking issue body for each child, and update the tracking issue after all children are created.
- **Comment (Step 6.5):** `gh issue comment <number> --body "<body>"`.
- **Item URL (Step 7):** the URL `gh issue create` prints (`https://github.com/<owner>/<repo>/issues/<n>`).

## Azure DevOps / Azure Boards

- **`{{root_term}}`:** Epic
- **`{{delivery_term}}`:** depends on the process template — ask which only when Azure DevOps is chosen in Step 1:
  - Agile (default) → User Story
  - Scrum → Product Backlog Item
  - Basic → Issue
- **Availability check:** the `az boards` extension is installed and `az devops configure --defaults organization=<org> project=<project>` has been run, or an Azure DevOps MCP server is connected — prefer the MCP's equivalent tools when present.
- **Idempotency check (WIQL):**
  ```
  az boards query --wiql "SELECT [System.Id] FROM WorkItems WHERE [System.TeamProject] = '<project>' AND [System.WorkItemType] = 'Epic' AND [System.Tags] CONTAINS 'contract-testing-flywheel' AND [System.Title] CONTAINS '<team>'"
  ```
- **Create:** `az boards work-item create --title "<title>" --type <type> --org <org> --project <project> --description "<body>" --fields "System.Tags=contract-testing-flywheel; contract-testing-onboarding; <cdct|bdct|both>"` for the Epic and each child (the `contract-testing-flywheel` tag on the root Epic is what the idempotency WIQL above searches on); work item type per the Step-4 mapping table, substituting `{{delivery_term}}` for the delivery-phase rows.
- **Link:** `az boards work-item relation add --id <child-id> --relation-type parent --target-id <root-id>`.
- **Comment (Step 6.5):** `az boards work-item update --id <id> --discussion "<body>"`.
- **Item URL (Step 7):** `https://dev.azure.com/<org>/<project>/_workitems/edit/<id>`.

## Other / manual export

- No availability check, no idempotency check — this path always proceeds.
- No create/link/comment calls. Instead, render the entire backlog (root item + all 10 children, every placeholder substituted, in the order of the Step-4 mapping table) as one markdown document. Use "Epic" / "Story" / "Task" as the neutral default vocabulary — they're the most widely understood triad regardless of the reader's tool.
- Inline the relevant `examples/CLAUDE.md.*` snippet under the Phase 4 and Phase 4b sections instead of posting it as a separate comment (there's no ticket to comment on).
- No item URLs — the export is copy/paste/import material, not a live link.
