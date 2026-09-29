# Contributing

Thank you for improving the PactFlow agent skills. Changes should remain focused and preserve compatibility across the supported plugin formats.

## Development setup

Install Python 3.12 or newer, [uv](https://docs.astral.sh/uv/), and [git-cliff](https://git-cliff.org/). Then install the locked development environment:

```bash
uv sync --locked
uv sync --project scripts/generate --locked
```

The repository distributes skills, agents, and plugin manifests rather than an installable Python package. The root environment provides Ruff, mypy, pytest, mdformat, plugin validation, and security tooling. The separate `scripts/generate` environment contains the Pact SDK parser dependencies.

## Making changes

- Follow the detailed repository conventions in [AGENTS.md](AGENTS.md).
- Preserve the frontmatter in skills, agents, and Power definitions.
- Keep `plugins/<name>/plugin.json`, `.claude-plugin/plugin.json`, and `.codex-plugin/plugin.json` metadata synchronized.
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

For focused pact-coverage work, run its tests with coverage details:

```bash
uv run --locked pytest -v \
	--cov=parse_pact_coverage \
	--cov=build_filtered_oas \
	--cov-report=term-missing \
	--cov-fail-under=75 \
	plugins/swagger-contract-testing/skills/pact-coverage/scripts/tests/
```

To regenerate a DSL reference, run its matching `scripts/generate/dsl_*.py` script and format every output it names. For example:

```bash
uv run --project scripts/generate --locked scripts/generate/dsl_python.py
uv run --locked mdformat plugins/swagger-contract-testing/skills/pactflow/references/dsl.python.md
```

DSL generators clone upstream Pact SDK source and therefore require network access unless you pass their supported local-repository option. Review the generated diff before committing it.

## Commits and pull requests

Use one of the Conventional Commit types accepted by `commitlint.config.mjs`: `build`, `chore`, `ci`, `docs`, `feat`, `fix`, `perf`, `refactor`, `revert`, `style`, or `test`. Keep the header within 120 characters, use a lowercase type, and explain behavior changes in the pull request. Link the relevant issue when one exists and call out checks that could not be run.

User-visible commits should normally use `feat:`, `fix:`, `docs:`, `perf:`, `refactor:`, or `revert:` so they appear in the generated changelog. Use `chore(deps):` for dependency updates.

After fetching the base branch, reproduce the commit-message check locally with Node.js and `npx`:

```bash
npx --yes @commitlint/cli@19.8.1 --from origin/main --to HEAD --verbose
```

Maintainers should follow the [release process](docs/releasing.md) when preparing a version.

By participating, you agree to follow [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md). Report vulnerabilities through [SECURITY.md](SECURITY.md), not a public issue.
