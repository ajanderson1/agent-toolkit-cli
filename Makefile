# Makefile

.DEFAULT_GOAL := help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

## Documentation -------------------------------------------------------

.PHONY: docs docs-build docs-fast

docs: ## Serve MkDocs documentation locally (restarts if already running)
	@PORT=$$(grep -E '^dev_addr:' mkdocs.yml 2>/dev/null | sed 's/.*://;s/[^0-9]//g'); \
	PORT=$${PORT:-8400}; \
	EXISTING=$$(lsof -ti :$$PORT 2>/dev/null); \
	if [ -n "$$EXISTING" ]; then \
	    echo "  Stopping existing server on port $$PORT (PID $$EXISTING)..."; \
	    kill $$EXISTING 2>/dev/null; \
	    sleep 1; \
	fi; \
	echo ""; \
	echo "  📖  Documentation server starting..."; \
	echo ""; \
	echo "  ➜  http://localhost:$$PORT"; \
	echo ""; \
	uv run mkdocs serve

docs-build: ## Build static documentation site
	uv run mkdocs build --strict

docs-fast: ## Serve docs without mkdocstrings (faster reload)
	ENABLE_MKDOCSTRINGS=false uv run mkdocs serve
