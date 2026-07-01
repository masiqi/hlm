.PHONY: help env split-chapters analyze-questions dry-run build-kg lightrag-up lightrag-down test web

help:
	@echo "Targets:"
	@echo "  make env               Copy .env.example to .env when .env is missing"
	@echo "  make split-chapters    Split book/红楼梦.txt into 120 chapter files"
	@echo "  make analyze-questions Parse JSONL samples and write docs/question_types.md"
	@echo "  make dry-run           Validate local KG build flow without LightRAG API calls"
	@echo "  make lightrag-up       Start LightRAG Server/WebUI with Docker Compose"
	@echo "  make build-kg          Run real scan/indexing flow against LightRAG"
	@echo "  make test              Run local tests"
	@echo "  make web               Run the V1 reading assistant web app"

env:
	@test -f .env || cp .env.example .env
	@echo ".env is ready. Fill in LLM and embedding settings before real indexing."

split-chapters:
	python -m hlm_kg.chapters

analyze-questions:
	python -m hlm_kg.questions

dry-run:
	python -m hlm_kg.lightrag_app --dry-run

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
