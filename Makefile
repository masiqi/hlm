.PHONY: help env split-chapters analyze-questions dry-run validate-samples generate-chapter-cards import-chapter-cards build-kg lightrag-up lightrag-down test web postgres-migrate postgres-import-seed sync-chapter-card-postgres

help:
	@echo "Targets:"
	@echo "  make env               Copy .env.example to .env when .env is missing"
	@echo "  make split-chapters    Split book/红楼梦.txt into 120 chapter files"
	@echo "  make analyze-questions Parse JSONL samples and write docs/question_types.md"
	@echo "  make dry-run           Validate local KG build flow without LightRAG API calls"
	@echo "  make validate-samples  Validate internal calibration sample quality"
	@echo "  make generate-chapter-cards ARGS='--chapters 3,5,8'"
	@echo "  make import-chapter-cards INPUT=cards.json OUTPUT=data/app/chapter_review_cards.json DATA_DIR=data/app"
	@echo "  make lightrag-up       Start LightRAG Server/WebUI with Docker Compose"
	@echo "  make build-kg          Run real scan/indexing flow against LightRAG"
	@echo "  make test              Run local tests"
	@echo "  make web               Run the V1 reading assistant web app"
	@echo "  make postgres-migrate  Apply PostgreSQL schema migration using DATABASE_URL"
	@echo "  make postgres-import-seed  Import book/data seed content into PostgreSQL"
	@echo "  make sync-chapter-card-postgres CHAPTER=27 INPUT=generated/chapter_cards_import/027.json"

env:
	@test -f .env || cp .env.example .env
	@echo ".env is ready. Fill in LLM and embedding settings before real indexing."

split-chapters:
	python -m hlm_kg.chapters

analyze-questions:
	python -m hlm_kg.questions

dry-run:
	python -m hlm_kg.lightrag_app --dry-run

validate-samples:
	python -m hlm_kg.validation_samples

generate-chapter-cards:
	python scripts/generate_chapter_cards.py $(ARGS)

import-chapter-cards:
	python scripts/import_chapter_cards.py $(INPUT) $(OUTPUT) $(or $(DATA_DIR),data/app)

lightrag-up: env
	docker compose up -d lightrag

lightrag-down:
	docker compose down

build-kg:
	python -m hlm_kg.lightrag_app --real --start-server

test:
	pytest -q

web:
	python -m hlm_kg.web_app

postgres-migrate:
	python scripts/migrate_postgres.py

postgres-import-seed:
	python scripts/import_postgres_seed.py

sync-chapter-card-postgres:
	python scripts/sync_chapter_card_postgres.py --chapter $(CHAPTER) --input $(INPUT)
