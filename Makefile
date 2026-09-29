.PHONY: lint format format-check typecheck changelog-check changelog test check fix

LINT_PATHS := scripts/ plugins/swagger-contract-testing/skills/

lint:
	uvx ruff check $(LINT_PATHS)

format:
	uvx ruff format $(LINT_PATHS)

format-check:
	uvx ruff format --check $(LINT_PATHS)

typecheck:
	uvx --with mypy mypy $(LINT_PATHS)

test:
	uv run --with pytest --with pyyaml pytest -q plugins/swagger-contract-testing/skills/drift-testing/scripts/tests

changelog-check:
	git cliff --unreleased --strip all >/dev/null

changelog:
	@test -n "$(VERSION)" || (echo "VERSION is required (for example: make changelog VERSION=1.3.0)" && exit 2)
	git cliff --tag v$(VERSION) $(if $(DRY_RUN),--unreleased,--output CHANGELOG.md)

check: lint format-check typecheck changelog-check test

fix:
	uvx ruff check --fix $(LINT_PATHS)
	uvx ruff format $(LINT_PATHS)
