.PHONY: lint format format-check typecheck test validate changelog-check changelog check fix


LINT_PATHS := scripts/ plugins/swagger-contract-testing/skills/

lint:
	uv run --locked ruff check $(LINT_PATHS) tests/

format:
	uv run --locked ruff format $(LINT_PATHS) tests/

format-check:
	uv run --locked ruff format --check $(LINT_PATHS) tests/

typecheck:
	uv run --locked mypy $(LINT_PATHS) tests/

test:
	uv run --locked pytest -q tests/ plugins/swagger-contract-testing/skills/pact-coverage/scripts/tests/
	uv run --project scripts/generate --locked pytest -q scripts/generate/tests/

validate:
	uv run --locked python scripts/validate-plugins.py

test:
	uv run --with pytest --with pyyaml pytest -q plugins/swagger-contract-testing/skills/drift-testing/scripts/tests

changelog-check:
	git cliff --unreleased --strip all >/dev/null

changelog:
	@test -n "$(VERSION)" || (echo "VERSION is required (for example: make changelog VERSION=1.3.0)" && exit 2)
	git cliff --tag v$(VERSION) $(if $(DRY_RUN),--unreleased,--output CHANGELOG.md)

check: lint format-check typecheck test validate changelog-check

fix:
	uv run --locked ruff check --fix $(LINT_PATHS) tests/
	uv run --locked ruff format $(LINT_PATHS) tests/
