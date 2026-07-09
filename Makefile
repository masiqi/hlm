.PHONY: help env split-chapters analyze-questions dry-run validate-samples validate-ask-quality-dataset generate-chapter-cards generate-all-chapter-materials import-chapter-cards build-topic-index build-kg lightrag-up lightrag-down test web postgres-migrate postgres-import-seed sync-chapter-card-postgres build-entity-trace-cache build-entity-graph-cache sync-entity-graph-cache-postgres build-static-chapter-cache

help:
	@echo "Targets:"
	@echo "  make env               Copy .env.example to .env when .env is missing"
	@echo "  make split-chapters    Split book/红楼梦.txt into 120 chapter files"
	@echo "  make analyze-questions Parse JSONL samples and write docs/question_types.md"
	@echo "  make dry-run           Validate local KG build flow without LightRAG API calls"
	@echo "  make validate-samples  Validate internal calibration sample quality"
	@echo "  make validate-ask-quality-dataset  Validate Ask retrieval quality dataset"
	@echo "  make generate-chapter-cards ARGS='--chapters 3,5,8'"
	@echo "  make generate-all-chapter-materials ARGS='--chapters 1-120'"
	@echo "  make import-chapter-cards INPUT=cards.json OUTPUT=data/app/chapter_review_cards.json DATA_DIR=data/app"
	@echo "  make build-topic-index Build the evidence-backed topic index from chapter cards"
	@echo "  make lightrag-up       Start LightRAG Server/WebUI with Docker Compose"
	@echo "  make build-kg          Run real scan/indexing flow against LightRAG"
	@echo "  make test              Run local tests"
	@echo "  make web               Run the V1 reading assistant web app"
	@echo "  make postgres-migrate  Apply PostgreSQL schema migration using DATABASE_URL"
	@echo "  make postgres-import-seed  Import book/data seed content into PostgreSQL"
	@echo "  make sync-chapter-card-postgres CHAPTER=27 INPUT=generated/chapter_cards_import/027.json"
	@echo "  make build-entity-trace-cache CHAPTERS=1-120  Build page entity trace cache and sync PostgreSQL"
	@echo "  make build-entity-graph-cache CHAPTERS=1-120  Build page entity graph detail cache and sync PostgreSQL"
	@echo "  make sync-entity-graph-cache-postgres  Sync cached entity graph JSON into PostgreSQL"
	@echo "  make build-static-chapter-cache CHAPTERS=1-120  Build static chapter JSON cache"

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

validate-ask-quality-dataset:
	uv run python -m hlm_kg.ask_quality_dataset

generate-chapter-cards:
	python scripts/generate_chapter_cards.py $(ARGS)

generate-all-chapter-materials:
	python scripts/generate_all_chapter_materials.py $(ARGS)

import-chapter-cards:
	python scripts/import_chapter_cards.py $(INPUT) $(OUTPUT) $(or $(DATA_DIR),data/app)

build-topic-index:
	python scripts/build_topic_index.py --data-dir data/app --review-cards data/app/chapter_review_cards.json --write

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

build-entity-trace-cache:
	python scripts/build_entity_trace_cache.py --chapters $(or $(CHAPTERS),1-120) --postgres --sync-postgres --flush-each-chapter $(ARGS)

build-entity-graph-cache:
	python scripts/build_entity_graph_cache.py --chapters $(or $(CHAPTERS),1-120) --postgres --sync-postgres $(ARGS)

sync-entity-graph-cache-postgres:
	python scripts/sync_entity_graph_cache_postgres.py $(ARGS)

build-static-chapter-cache:
	python scripts/build_static_chapter_cache.py --chapters $(or $(CHAPTERS),1-120) $(ARGS)
