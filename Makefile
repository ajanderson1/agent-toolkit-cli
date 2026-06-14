# Makefile

.DEFAULT_GOAL := help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

## Documentation -------------------------------------------------------

.PHONY: docs docs-build

docs: ## Serve MkDocs documentation locally + on the meshnet (restarts if running)
	@PORT=$$(grep -E '^dev_addr:' mkdocs.yml 2>/dev/null | sed 's/.*://;s/[^0-9]//g'); \
	PORT=$${PORT:-8400}; \
	EXISTING=$$(lsof -ti :$$PORT 2>/dev/null); \
	if [ -n "$$EXISTING" ]; then \
	    echo "  Stopping existing server on port $$PORT (PID $$EXISTING)..."; \
	    kill $$EXISTING 2>/dev/null; \
	    sleep 1; \
	fi; \
	MESH_IP=$$( (tailscale ip -4 2>/dev/null || true) | head -1); \
	[ -n "$$MESH_IP" ] || MESH_IP=$$(ifconfig 2>/dev/null | awk '/inet 100\.(6[4-9]|[7-9][0-9]|1[01][0-9]|12[0-7])\./ {print $$2; exit}'); \
	echo ""; \
	echo "  📖  Documentation server starting (bound to all interfaces)..."; \
	echo ""; \
	echo "  ➜  local:    http://localhost:$$PORT"; \
	if [ -n "$$MESH_IP" ]; then \
	    echo "  ➜  meshnet:  http://$$MESH_IP:$$PORT"; \
	else \
	    echo "  (no meshnet/Tailscale address detected — reachable on any LAN IP at port $$PORT)"; \
	fi; \
	echo ""; \
	uv run mkdocs serve -a 0.0.0.0:$$PORT

docs-build: ## Build static documentation site
	uv run mkdocs build --strict
