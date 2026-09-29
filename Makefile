.PHONY: lint format format-check typecheck test check fix

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

check: lint format-check typecheck test

fix:
	uvx ruff check --fix $(LINT_PATHS)
	uvx ruff format $(LINT_PATHS)
