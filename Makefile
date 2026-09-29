.PHONY: help install install-diffusion test test-ci lint demo fetch-models clean

help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z_-]+:.*##/ {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: ## Install core + dev (procedural mutator only; no torch)
	uv sync --extra dev

install-diffusion: ## Install with the diffusion extra (torch, diffusers)
	uv sync --extra dev --extra diffusion

test: ## Run the test suite
	uv run pytest -q

test-ci: ## Test gate for CI (deselect known failures here, never skip silently)
	uv run pytest -q -m "not slow"

lint: ## Ruff lint + format check
	uv run ruff check . && uv run ruff format --check .

demo: ## Offline procedural render of the example painting
	uv run illusionframe evolve examples/painting.jpg --mutator procedural --iterations 60

fetch-models: ## Download sd-turbo + TAESD so runs work offline
	uv run illusionframe fetch-models

clean: ## Remove caches
	rm -rf .pytest_cache .ruff_cache **/__pycache__
