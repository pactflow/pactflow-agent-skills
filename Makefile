.PHONY: lint format format-check typecheck check fix

LINT_PATHS := scripts/ plugins/swagger-contract-testing/skills/

lint:
	uvx ruff check $(LINT_PATHS)

format:
	uvx ruff format $(LINT_PATHS)

format-check:
	uvx ruff format --check $(LINT_PATHS)

typecheck:
	uvx --with mypy mypy $(LINT_PATHS)

check: lint format-check typecheck

fix:
	uvx ruff check --fix $(LINT_PATHS)
	uvx ruff format $(LINT_PATHS)
