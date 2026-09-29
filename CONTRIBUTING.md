# Contributing

Thank you for improving the PactFlow agent skills. Changes should remain focused and preserve compatibility across the supported plugin formats.

## Development setup

Install Python 3.12 or newer, [uv](https://docs.astral.sh/uv/), and [git-cliff](https://git-cliff.org/). Then install the locked development environment:

```bash
uv sync --locked
uv sync --project scripts/generate --locked
```

The repository is not an installable application. The environments provide its validation, test, and generator tools.

## Making changes

- Follow the detailed repository conventions in [AGENTS.md](AGENTS.md).
- Preserve the frontmatter in skills, agents, and Power definitions.
- Keep portable, Claude, and Codex plugin metadata synchronized.
- Do not edit generated `dsl.*.md` references or `CHANGELOG.md` manually.
- Add focused tests for executable behavior and regression fixes.
- Avoid unrelated formatting and generated-file churn.

## Validation

Run the complete local gate before opening a pull request:

```bash
make check
git diff --check
```

The gate runs linting, formatting verification, strict type checking, unit tests, plugin/package validation, and changelog validation. Generator scripts may require network access when regenerating DSL references.

## Commits and pull requests

Use a Conventional Commit type accepted by `commitlint.config.mjs`, keep the header within 120 characters, and explain behavior changes in the pull request. Link the relevant issue when one exists and call out checks that could not be run.

User-visible commits should normally use `feat:`, `fix:`, `docs:`, `perf:`, `refactor:`, or `revert:` so they appear in the generated changelog. Use `chore(deps):` for dependency updates.

By participating, you agree to follow [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md). Report vulnerabilities through [SECURITY.md](SECURITY.md), not a public issue.