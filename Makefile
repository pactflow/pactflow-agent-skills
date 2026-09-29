.PHONY: lint format format-check typecheck changelog-check changelog check fix

LINT_PATHS := scripts/ plugins/swagger-contract-testing/skills/

lint:
	uvx ruff check $(LINT_PATHS)

format:
	uvx ruff format $(LINT_PATHS)

format-check:
	uvx ruff format --check $(LINT_PATHS)

typecheck:
	uvx --with mypy mypy $(LINT_PATHS)

changelog-check:
	git cliff --unreleased --strip all >/dev/null

changelog:
	@test -n "$(VERSION)" || (echo "VERSION is required (for example: make changelog VERSION=1.3.0)" && exit 2)
	git cliff --tag v$(VERSION) $(if $(DRY_RUN),--unreleased,--output CHANGELOG.md)

check: lint format-check typecheck changelog-check

fix:
	uvx ruff check --fix $(LINT_PATHS)
	uvx ruff format $(LINT_PATHS)
