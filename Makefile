-include .env

MERIDIAN_WEB ?= ../meridian-web

.PHONY: chat chat-dev build-frontend

# Full stack with static assets (UI is default)
chat:
	uv run meridian chat --open

# Full stack with dev mode (Vite hot reload)
chat-dev:
	uv run meridian chat --dev --open

# Build frontend assets and copy to CLI package
build-frontend:
	cd $(MERIDIAN_WEB) && pnpm build
	rsync -a --delete $(MERIDIAN_WEB)/dist/ src/meridian/web_dist/
	@echo "Frontend assets copied to src/meridian/web_dist/"
