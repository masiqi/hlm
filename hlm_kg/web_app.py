from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from hlm_kg.ask_engine import AskEngine
from hlm_kg.content_store import ContentStore


@dataclass(frozen=True)
class AppContext:
    store: ContentStore
    ask_engine: AskEngine
    static_dir: Path


def create_app_context(manifest_path: Path, data_dir: Path, static_dir: Path) -> AppContext:
    store = ContentStore.from_paths(manifest_path, data_dir)
    return AppContext(store=store, ask_engine=AskEngine(store), static_dir=static_dir)


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
        review_card = context.store.review_card_for_chapter(number)
        knowledge_cards = [context.store.knowledge_card(card_id) for card_id in review_card.key_characters]
        return 200, {
            "chapter": _camel(asdict(chapter)),
            "originalText": context.store.chapter_text(number),
            "reviewCard": _camel(asdict(review_card)),
            "knowledgeCards": [_camel(asdict(card)) for card in knowledge_cards],
        }
    if method == "GET" and parsed_path == "/api/topics":
        return 200, {"topics": [_camel(asdict(topic)) for topic in context.store.topics]}
    if method == "GET" and parsed_path.startswith("/api/cards/"):
        card_id = parsed_path.rsplit("/", 1)[1]
        card = context.store.knowledge_card(card_id)
        return 200, {"card": _camel(asdict(card))}
    if method == "POST" and parsed_path == "/api/ask":
        question = str((body or {}).get("question", ""))
        answer = context.ask_engine.ask(question)
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


def main() -> None:
    context = create_app_context(
        manifest_path=Path("book/chapters_manifest.json"),
        data_dir=Path("data/app"),
        static_dir=Path("static"),
    )
    server = ThreadingHTTPServer(("127.0.0.1", 8765), make_handler(context))
    print("Serving at http://127.0.0.1:8765")
    server.serve_forever()


if __name__ == "__main__":
    main()
