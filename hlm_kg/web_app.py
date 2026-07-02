from __future__ import annotations

import json
import os
import re
import socket
from dataclasses import asdict, dataclass
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from hlm_kg.ask_engine import AskEngine
from hlm_kg.content_store import ContentStore
from hlm_kg.lightrag_client import LightRAGClient, LightRAGConfig
from hlm_kg.postgres_config import load_database_url, load_dotenv, parse_bool


@dataclass(frozen=True)
class AppContext:
    store: Any
    ask_engine: AskEngine
    static_dir: Path
    retrieval_client: Any | None = None


def create_app_context(
    manifest_path: Path,
    data_dir: Path,
    static_dir: Path,
    retrieval_client: Any | None = None,
    *,
    use_env_retrieval: bool = False,
    use_postgres_store: bool = False,
) -> AppContext:
    dotenv = load_dotenv()
    json_store = ContentStore.from_paths(manifest_path, data_dir)
    store: Any = json_store
    postgres_setting = str(os.environ.get("HLM_CONTENT_STORE", dotenv.get("HLM_CONTENT_STORE", ""))).strip().lower()
    postgres_enabled = use_postgres_store or postgres_setting == "postgres" or parse_bool(postgres_setting)
    if postgres_enabled:
        database_url = load_database_url() or load_database_url(dotenv)
        if database_url is None:
            raise RuntimeError("DATABASE_URL is not set for PostgreSQL content store")
        store = PostgresContentStore(database_url, fallback_store=json_store)
    if retrieval_client is None and use_env_retrieval:
        retrieval_env = {**dotenv, **os.environ}
        config = LightRAGConfig.from_env(retrieval_env)
        retrieval_client = LightRAGClient(config) if config is not None else None
    return AppContext(store=store, ask_engine=AskEngine(store), static_dir=static_dir, retrieval_client=retrieval_client)


def handle_api_request(
    context: AppContext,
    method: str,
    path: str,
    body: dict[str, Any] | None = None,
) -> tuple[int, dict[str, Any]]:
    parsed_path = urlparse(path).path
    if method == "GET" and parsed_path == "/api/home":
        return 200, {"commonEntries": context.store.common_entries}
    if method == "GET" and parsed_path.startswith("/api/chapters/"):
        number = int(parsed_path.rsplit("/", 1)[1])
        chapter = context.store.chapter(number)
        review_card = context.store.maybe_review_card_for_chapter(number)
        original_text = context.store.chapter_text(number)
        inline_entities = _inline_entities_for_review_card(review_card) if review_card is not None else []
        annotations = _annotations_payload(
            stored_annotations=context.store.annotations_for_chapter(number),
            review_card=review_card,
            original_text=original_text,
            inline_entities=inline_entities,
        )
        knowledge_cards = []
        if review_card is not None:
            knowledge_cards = [context.store.knowledge_card(card_id) for card_id in review_card.key_characters]
        return 200, {
            "chapter": _camel(asdict(chapter)),
            "originalText": original_text,
            "reviewCard": _camel(asdict(review_card)) if review_card is not None else None,
            "knowledgeCards": [_camel(asdict(card)) for card in knowledge_cards],
            "inlineEntities": _camel(inline_entities),
            "annotations": _camel(annotations),
            "materialStatus": {
                "hasReviewCard": review_card is not None,
                "message": "章节资料已加载。" if review_card is not None else "章节资料暂未生成，可先阅读原文。",
            },
        }
    if method == "GET" and parsed_path.startswith("/api/topics/"):
        topic_id = parsed_path.rsplit("/", 1)[1]
        topic = context.store.topic(topic_id)
        cards = [context.store.knowledge_card(card_id) for card_id in topic.card_ids]
        relations = [context.store.graph_relation(relation_id) for relation_id in topic.relation_ids]
        evidence = [context.store.evidence(evidence_id) for evidence_id in topic.evidence_ids]
        return 200, {
            "topic": _camel(asdict(topic)),
            "cards": [_camel(asdict(card)) for card in cards],
            "relations": [_camel(asdict(relation)) for relation in relations],
            "evidence": [_camel(asdict(item)) for item in evidence],
        }
    if method == "GET" and parsed_path == "/api/topics":
        return 200, {"topics": [_camel(asdict(topic)) for topic in context.store.topics]}
    if method == "GET" and parsed_path.startswith("/api/cards/"):
        card_id = parsed_path.rsplit("/", 1)[1]
        card = context.store.knowledge_card(card_id)
        evidence = [context.store.evidence(evidence_id) for evidence_id in card.evidence_ids]
        relation_by_id = {relation.id: relation for relation in context.store.graph_relations}
        relations = [relation_by_id[relation_id] for relation_id in card.graph_relation_ids]
        trace_items = context.store.trace_items_for_entity(card_id)
        return 200, {
            "card": _camel(asdict(card)),
            "evidence": [_camel(asdict(item)) for item in evidence],
            "relations": [_camel(asdict(item)) for item in relations],
            "traceItems": [_camel(asdict(item)) for item in trace_items],
        }
    if method == "POST" and parsed_path == "/api/ask":
        question = str((body or {}).get("question", ""))
        answer = context.ask_engine.ask(question, retrieval_client=context.retrieval_client)
        return 200, _camel(asdict(answer))
    return 404, {"error": "not found"}


def _camel(value: Any) -> Any:
    if isinstance(value, list):
        return [_camel(item) for item in value]
    if isinstance(value, dict):
        return {_camel_key(key): _camel(item) for key, item in value.items()}
    return value


def _camel_key(key: str) -> str:
    head, *tail = key.split("_")
    return head + "".join(part[:1].upper() + part[1:] for part in tail)


def _inline_entities_for_review_card(review_card: ChapterReviewCard) -> list[dict[str, Any]]:
    entities: dict[str, dict[str, Any]] = {}

    def ensure_entity(name: str, entity_type: str, summary: str = "", details: list[str] | None = None) -> dict[str, Any]:
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("inline entity name cannot be empty")
        key = clean_name
        entity = entities.setdefault(
            key,
            {
                "id": f"chapter-{review_card.chapter:03d}-entity-{_entity_slug(clean_name)}",
                "name": clean_name,
                "type": entity_type,
                "summary": summary,
                "details": [],
                "relations": [],
                "laterClues": [],
                "chapterJumps": [],
            },
        )
        if summary and not entity["summary"]:
            entity["summary"] = summary
        if details:
            entity["details"].extend(item for item in details if item)
        return entity

    for character in review_card.characters:
        if not isinstance(character, dict):
            continue
        name = str(character.get("name") or "").strip()
        if not name:
            continue
        details = _flatten_strings(
            character.get("actions"),
            character.get("traits"),
            character.get("evidence"),
            character.get("importance"),
        )
        ensure_entity(name, "person", str(character.get("role") or character.get("importance") or ""), details)

    for place in review_card.places:
        if not isinstance(place, dict):
            continue
        name = str(place.get("name") or "").strip()
        if name:
            ensure_entity(name, "place", str(place.get("function") or ""), _flatten_strings(place.get("scenes")))

    for item in review_card.objects:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if name:
            ensure_entity(name, "object", str(item.get("meaning") or ""), _flatten_strings(item.get("context"), item.get("related_entities")))

    for item in review_card.literary_texts:
        if not isinstance(item, dict):
            continue
        name = str(item.get("title") or "").strip()
        if name:
            ensure_entity(name, "literary_text", str(item.get("function") or ""), _flatten_strings(item.get("short_quote"), item.get("explanation")))

    for relation in review_card.relationships:
        if not isinstance(relation, dict):
            continue
        relation_summary = str(relation.get("description") or relation.get("chapter_evidence") or "").strip()
        for endpoint in (relation.get("source"), relation.get("target")):
            name = str(endpoint or "").strip()
            if not name:
                continue
            entity = ensure_entity(name, "entity")
            entity["relations"].append(
                {
                    "source": relation.get("source"),
                    "type": relation.get("type"),
                    "target": relation.get("target"),
                    "description": relation_summary,
                    "evidence": relation.get("chapter_evidence"),
                }
            )

    for association in review_card.later_associations:
        if not isinstance(association, dict):
            continue
        topic = str(association.get("topic") or "").strip()
        description = str(association.get("description") or association.get("evidence") or "").strip()
        chapters = _int_list(association.get("source_chapters"))
        names = _entity_names_for_association(topic, description, entities)
        if not names and topic:
            names = [topic]
        for name in names:
            entity = ensure_entity(name, "foreshadowing" if name == topic else entities.get(name, {}).get("type", "entity"))
            entity["laterClues"].append({"topic": topic, "description": description, "evidence": association.get("evidence")})
            for chapter in chapters:
                jump = {"chapter": chapter, "label": f"第{chapter}回：{topic or name}"}
                if jump not in entity["chapterJumps"]:
                    entity["chapterJumps"].append(jump)

    for entity in entities.values():
        entity["details"] = _unique_strings(entity["details"])
        entity["relations"] = _unique_dicts(entity["relations"])
        entity["laterClues"] = _unique_dicts(entity["laterClues"])
        entity["chapterJumps"] = sorted(_unique_dicts(entity["chapterJumps"]), key=lambda item: (item.get("chapter") or 0, item.get("label") or ""))
        if not entity["summary"] and entity["details"]:
            entity["summary"] = entity["details"][0]
    return list(entities.values())


def _annotations_payload(
    *,
    stored_annotations: list[ChapterAnnotation],
    review_card: ChapterReviewCard | None,
    original_text: str,
    inline_entities: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    entity_id_by_name = {str(entity["name"]): str(entity["id"]) for entity in inline_entities}
    entity_id_by_id = {str(entity["id"]): str(entity["id"]) for entity in inline_entities}
    if stored_annotations:
        return [
            {
                **asdict(annotation),
                "entity_id": entity_id_by_id.get(str(annotation.entity_id))
                or entity_id_by_name.get(str(annotation.surface_text))
                or annotation.entity_id,
            }
            for annotation in stored_annotations
        ]
    if review_card is None:
        return []
    rows: list[dict[str, Any]] = []
    for annotation in review_card.annotations:
        if not isinstance(annotation, dict):
            continue
        text = str(annotation.get("text") or "").strip()
        if not text:
            continue
        target = str(annotation.get("target") or text).strip()
        entity_id = entity_id_by_name.get(target) or entity_id_by_name.get(text) or entity_id_by_id.get(target)
        if not entity_id:
            continue
        start = 0
        while True:
            index = original_text.find(text, start)
            if index == -1:
                break
            rows.append(
                {
                    "id": f"ann-{review_card.chapter:03d}-{_entity_slug(entity_id)}-{index}",
                    "chapter": review_card.chapter,
                    "start_offset": index,
                    "end_offset": index + len(text),
                    "surface_text": text,
                    "annotation_type": str(annotation.get("kind") or "entity"),
                    "entity_id": entity_id,
                    "relation_id": None,
                    "evidence_id": None,
                    "display_priority": 100,
                }
            )
            start = index + len(text)
    return rows


def _entity_slug(value: str) -> str:
    parts = re.findall(r"[\w\u4e00-\u9fff]+", value.lower())
    return "-".join(parts) or "item"


def _flatten_strings(*values: Any) -> list[str]:
    output: list[str] = []
    for value in values:
        if isinstance(value, list):
            output.extend(str(item) for item in value if str(item).strip())
        elif value is not None and str(value).strip():
            output.append(str(value))
    return output


def _unique_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            output.append(value)
    return output


def _unique_dicts(values: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    output: list[dict[str, Any]] = []
    for value in values:
        key = json.dumps(value, ensure_ascii=False, sort_keys=True)
        if key not in seen:
            seen.add(key)
            output.append(value)
    return output


def _int_list(value: Any) -> list[int]:
    if not isinstance(value, list):
        return []
    output: list[int] = []
    for item in value:
        try:
            output.append(int(item))
        except (TypeError, ValueError):
            continue
    return output


def _entity_names_for_association(topic: str, description: str, entities: dict[str, dict[str, Any]]) -> list[str]:
    text = f"{topic}\n{description}"
    return [name for name in entities if name and name in text]


def PostgresContentStore(database_url: str, fallback_store: Any) -> Any:
    try:
        from hlm_kg.postgres_store import PostgresContentStore as Store
    except ModuleNotFoundError as exc:
        if exc.name == "psycopg":
            raise RuntimeError("psycopg is required for PostgreSQL content store") from exc
        raise
    return Store(database_url, fallback_store=fallback_store)


def make_handler(context: AppContext) -> type[SimpleHTTPRequestHandler]:
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, directory=str(context.static_dir), **kwargs)

        def do_GET(self) -> None:
            if self.path.startswith("/api/"):
                self._handle_api("GET")
                return
            if self.path == "/":
                self.path = "/index.html"
            super().do_GET()

        def do_POST(self) -> None:
            if self.path.startswith("/api/"):
                self._handle_api("POST")
                return
            self.send_error(404)

        def _handle_api(self, method: str) -> None:
            body = None
            if method == "POST":
                length = int(self.headers.get("Content-Length", "0"))
                raw_body = self.rfile.read(length).decode("utf-8") if length else "{}"
                body = json.loads(raw_body or "{}")
            status, payload = handle_api_request(context, method, self.path, body)
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    return Handler


def find_available_port(start_port: int, attempts: int = 20) -> int:
    for offset in range(attempts):
        port = start_port + offset
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    raise OSError(f"no available port from {start_port} across {attempts} attempts")


def main() -> None:
    context = create_app_context(
        manifest_path=Path("book/chapters_manifest.json"),
        data_dir=Path("data/app"),
        static_dir=Path("static"),
        use_env_retrieval=True,
    )
    port = find_available_port(8765)
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(context))
    print(f"Serving at http://127.0.0.1:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
