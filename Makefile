.PHONY: dev-db dev-api dev-client stop

dev-db:
	cd infra && docker compose up -d

dev-api:
	cd server && uv run uvicorn src.main:app --reload --port 8000

dev-client:
	cd client && npm run dev

stop:
	cd infra && docker compose down
