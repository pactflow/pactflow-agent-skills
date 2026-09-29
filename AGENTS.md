# Repository Guide for Agents

## Purpose

This repository publishes agent skills, agent definitions, plugin manifests, and generated Pact SDK DSL references. Keep changes focused and preserve compatibility across the supported agent packaging formats.

## Repository Layout

- `plugins/swagger-contract-testing/`: PactFlow, Drift, OpenAPI, and pact-coverage skills plus specialist agents.
- `plugins/contract-testing-flywheel/`: the contract-testing adoption workflow skill and its templates.
- `.claude-plugin/marketplace.json`: marketplace registration for every plugin under `plugins/`.
- `powers/swagger-contract-testing/`: Kiro Power packaging and steering files.
- `scripts/validate-plugins.py`: dependency-free validation of plugin manifests, marketplace entries, and skill frontmatter.
- `scripts/generate/`: Python 3.12 project that generates Pact SDK DSL reference documents.
- `docs/`: user-facing installation, integration, and release documentation.

## Dependencies

- Python 3.12 or newer.
- [`uv`](https://docs.astral.sh/uv/) for the locked development, test, and generator environments.
- [`git-cliff`](https://git-cliff.org/) for changelog validation and release generation (`brew install git-cliff` on macOS).
- Node.js with `npx` only when reproducing the commitlint CI check locally.

The repository is not an installable Python package. Run `uv sync --locked` and `uv sync --project scripts/generate --locked` after dependency changes.

## Working Conventions

- Follow existing structure and terminology in neighboring skills, agents, references, and templates.
- Keep every `SKILL.md` frontmatter block intact and include a `name:` key.
- When changing plugin identity or metadata, update the relevant root `plugin.json`, `.claude-plugin/plugin.json`, `.codex-plugin/plugin.json`, MCP configuration, and marketplace entry together. Claude and Codex manifests must remain equivalent where both exist.
- Keep portable manifests compliant with the agent-plugins.org schemas already referenced in those files.
- Do not edit `plugins/swagger-contract-testing/skills/pactflow/references/dsl.*.md` by hand. Regenerate them with the matching script under `scripts/generate/`, then format the output with `uvx mdformat`.
- Do not maintain `CHANGELOG.md` manually and do not add release-note fragments. Changelog content is generated from Git history.
- Keep Python compatible with 3.12 and within the Ruff and strict mypy rules in `pyproject.toml`. Tests are exempt from full annotation enforcement.
- Avoid unrelated formatting or generated-file churn.

## Required Checks

Run these from the repository root before handing off a change:

```bash
make check
git diff --check
```

`make check` runs Ruff linting, Ruff formatting verification, strict mypy type checking, unit tests, plugin/package validation, and an unreleased changelog preview. It requires `git-cliff`.

For changes under `plugins/swagger-contract-testing/skills/pact-coverage/`, also run:

```bash
uv run --locked pytest -v plugins/swagger-contract-testing/skills/pact-coverage/scripts/tests/
```

For generated DSL changes, run the corresponding generator from the repository root and format every output it names. For example:

```bash
uv run --project scripts/generate --locked scripts/generate/dsl_python.py
uv run --locked mdformat plugins/swagger-contract-testing/skills/pactflow/references/dsl.python.md
```

Review the resulting generated diff before committing. Generator scripts may fetch upstream Pact SDK source and therefore require network access.

## Commits and Releases

- Use Conventional Commit types accepted by `commitlint.config.mjs`: `build`, `chore`, `ci`, `docs`, `feat`, `fix`, `perf`, `refactor`, `revert`, `style`, or `test`.
- Keep commit headers at or below 120 characters and use lowercase types.
- Use `chore(deps):` for dependency updates. User-visible changes should normally use `feat:`, `fix:`, `docs:`, `perf:`, `refactor:`, or `revert:` so git-cliff includes them in the correct changelog section.
- Follow `docs/releasing.md` for release preparation. Plugin version updates and the generated changelog belong in the same release commit.

To reproduce commitlint for commits on a branch after fetching the base branch:

```bash
npx --yes @commitlint/cli@19.8.1 --from origin/main --to HEAD --verbose
```
