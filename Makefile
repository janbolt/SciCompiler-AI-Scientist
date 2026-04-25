.PHONY: dev api web install

install:
	pip install -e .
	cd apps/web && npm install

api:
	uvicorn services.api.main:app --reload --port 8000

web:
	cd apps/web && npm run dev

dev:
	@echo "Run 'make api' and 'make web' in two terminals"
