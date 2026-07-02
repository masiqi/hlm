import socket
import json
from pathlib import Path

from hlm_kg.web_app import create_app_context, find_available_port, handle_api_request

ROOT = Path(__file__).resolve().parents[1]


def _write_minimal_app_context_files(tmp_path: Path, review_cards: list[dict]) -> tuple[Path, Path, Path]:
    chapter_path = tmp_path / "book" / "chapters" / "001-第一回-甄士隐梦幻识通灵 贾雨村风尘怀闺秀.txt"
    chapter_path.parent.mkdir(parents=True)
    chapter_path.write_text("第一回 原文", encoding="utf-8")
    manifest_path = tmp_path / "book" / "chapters_manifest.json"
    manifest_path.write_text(
        json.dumps({"chapters": [{"number": 1, "title": "甄士隐梦幻识通灵 贾雨村风尘怀闺秀", "file_path": str(chapter_path)}]}, ensure_ascii=False),
        encoding="utf-8",
    )
    data_dir = tmp_path / "data"
    static_dir = tmp_path / "static"
    data_dir.mkdir()
    static_dir.mkdir()
    (data_dir / "chapter_review_cards.json").write_text(json.dumps(review_cards, ensure_ascii=False), encoding="utf-8")
    for filename in ("knowledge_cards.json", "graph_relations.json", "topics.json", "common_entries.json", "evidence.json"):
        (data_dir / filename).write_text("[]", encoding="utf-8")
    return manifest_path, data_dir, static_dir


def _review_card(**overrides):
    card = {
        "id": "review-001",
        "chapter": 1,
        "source": {
            "prompt_name": "hongloumeng_chapter_review_card",
            "prompt_version": "2026-07-01",
            "generated_at": "2026-07-02",
        },
        "plain_summary": "第一回梗概。",
        "plot_chain": ["甄士隐梦幻识通灵"],
        "key_events": [],
        "key_characters": [],
        "current_chapter_foreshadowing_signals": [],
        "later_association_relation_ids": [],
        "quotable_fact_ids": [],
        "retrieval_tags": ["#第一回"],
        "understanding_focus": ["理解真假有无。"],
        "characters": [],
        "relationships": [],
        "places": [],
        "objects": [],
        "literary_texts": [],
        "modern_explanations": [],
        "later_associations": [],
        "annotations": [],
    }
    card.update(overrides)
    return card


def test_api_chapter_returns_chapter_evidence_page_payload():
    context = create_app_context(
        manifest_path=Path("book/chapters_manifest.json"),
        data_dir=Path("data/app"),
        static_dir=Path("static"),
    )

    status, payload = handle_api_request(context, "GET", "/api/chapters/27")

    assert status == 200
    assert payload["chapter"]["number"] == 27
    assert "originalText" in payload
    assert "reviewCard" in payload
    assert "knowledgeCards" in payload
    assert "annotations" in payload
    assert "LightRAG" not in str(payload)


def test_api_chapter_returns_extended_review_card_fields(tmp_path):
    review_card = _review_card(
        characters=[{"name": "袭人", "actions": ["劝慰宝玉"]}],
        annotations=[{"text": "袭人", "kind": "person", "target": "袭人"}],
        later_associations=[{"topic": "袭人归宿", "source_chapters": [120], "evidence": "后文章回证据"}],
    )
    manifest_path, data_dir, static_dir = _write_minimal_app_context_files(tmp_path, [review_card])
    context = create_app_context(manifest_path=manifest_path, data_dir=data_dir, static_dir=static_dir)

    status, payload = handle_api_request(context, "GET", "/api/chapters/1")

    assert status == 200
    assert payload["reviewCard"]["characters"] == review_card["characters"]
    assert payload["reviewCard"]["annotations"] == review_card["annotations"]
    assert payload["reviewCard"]["laterAssociations"] == [
        {"topic": "袭人归宿", "sourceChapters": [120], "evidence": "后文章回证据"}
    ]


def test_api_chapter_returns_original_text_when_review_card_is_missing():
    context = create_app_context(
        manifest_path=Path("book/chapters_manifest.json"),
        data_dir=Path("data/app"),
        static_dir=Path("static"),
    )

    status, payload = handle_api_request(context, "GET", "/api/chapters/1")

    assert status == 200
    assert payload["chapter"]["number"] == 1
    assert payload["originalText"]
    assert payload["reviewCard"] is None
    assert payload["knowledgeCards"] == []
    assert payload["materialStatus"] == {
        "hasReviewCard": False,
        "message": "章节资料暂未生成，可先阅读原文。",
    }
    assert "LightRAG" not in str(payload)


def test_api_ask_returns_structured_answer():
    context = create_app_context(
        manifest_path=Path("book/chapters_manifest.json"),
        data_dir=Path("data/app"),
        static_dir=Path("static"),
    )

    status, payload = handle_api_request(context, "POST", "/api/ask", {"question": "黛玉葬花体现了什么？"})

    assert status == 200
    assert payload["status"] == "answered"
    assert payload["evidence"]
    assert "quotableFacts" in payload
    assert payload["quotableFacts"]["title"] == "可引用事实"
    assert payload["quotableFacts"]["claims"]
    assert payload["continuationLinks"]


class FakeRetrievalClient:
    def query_data(self, query: str, mode: str = "hybrid", **options):
        return {
            "status": "success",
            "data": {
                "entities": [],
                "relationships": [
                    {
                        "src_id": "宝黛初会",
                        "tgt_id": "第三回",
                        "keywords": "发生章回",
                        "description": "宝黛初会发生在第三回，林黛玉进贾府后与贾宝玉在贾母处相见。",
                        "source_id": "doc-003-chunk-001",
                        "file_path": "003-第三回-托内兄如海荐西宾 接外孙贾母惜孤女.txt",
                    }
                ],
                "chunks": [],
                "references": [],
            },
            "metadata": {"query_mode": mode},
        }


def test_api_ask_uses_configured_retrieval_client_for_chapter_location():
    context = create_app_context(
        manifest_path=Path("book/chapters_manifest.json"),
        data_dir=Path("data/app"),
        static_dir=Path("static"),
        retrieval_client=FakeRetrievalClient(),
    )

    status, payload = handle_api_request(context, "POST", "/api/ask", {"question": "宝黛初会发生在哪一回？"})

    assert status == 200
    assert payload["status"] == "answered"
    assert "第三回" in payload["shortConclusion"][0]["text"]
    assert payload["evidence"][0]["chapter"] == 3
    assert payload["continuationLinks"][0]["targetId"] == "3"
    assert "LightRAG" not in str(payload)


def test_create_app_context_does_not_build_retrieval_client_from_env_by_default(monkeypatch):
    monkeypatch.setenv("LIGHTRAG_BASE_URL", "http://10.1.0.246:9621")

    context = create_app_context(
        manifest_path=Path("book/chapters_manifest.json"),
        data_dir=Path("data/app"),
        static_dir=Path("static"),
    )

    assert context.retrieval_client is None


def test_create_app_context_can_build_retrieval_client_from_env_when_enabled(monkeypatch):
    monkeypatch.setenv("LIGHTRAG_BASE_URL", "http://10.1.0.246:9621")

    context = create_app_context(
        manifest_path=Path("book/chapters_manifest.json"),
        data_dir=Path("data/app"),
        static_dir=Path("static"),
        use_env_retrieval=True,
    )

    assert context.retrieval_client is not None
    assert context.retrieval_client.config.base_url == "http://10.1.0.246:9621"


def test_create_app_context_reads_postgres_database_url_from_dotenv(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    Path(".env").write_text("DATABASE_URL=postgresql://user:p*ss@example.local:5432/hlm\n", encoding="utf-8")
    monkeypatch.setattr("hlm_kg.web_app.PostgresContentStore", lambda database_url, fallback_store: ("postgres", database_url, fallback_store))

    context = create_app_context(
        manifest_path=ROOT / "book/chapters_manifest.json",
        data_dir=ROOT / "data/app",
        static_dir=ROOT / "static",
        use_postgres_store=True,
    )

    assert context.store[0] == "postgres"
    assert context.store[1] == "postgresql://user:p*ss@example.local:5432/hlm"


def test_create_app_context_enables_postgres_from_dotenv_flag(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    Path(".env").write_text(
        "DATABASE_URL=postgresql://user:p*ss@example.local:5432/hlm\n"
        "HLM_CONTENT_STORE=postgres\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("hlm_kg.web_app.PostgresContentStore", lambda database_url, fallback_store: ("postgres", database_url, fallback_store))

    context = create_app_context(
        manifest_path=ROOT / "book/chapters_manifest.json",
        data_dir=ROOT / "data/app",
        static_dir=ROOT / "static",
    )

    assert context.store[0] == "postgres"
    assert context.store[1] == "postgresql://user:p*ss@example.local:5432/hlm"


def test_create_app_context_fails_fast_when_postgres_enabled_without_database_url(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("HLM_CONTENT_STORE", raising=False)

    try:
        create_app_context(
            manifest_path=ROOT / "book/chapters_manifest.json",
            data_dir=ROOT / "data/app",
            static_dir=ROOT / "static",
            use_postgres_store=True,
        )
    except RuntimeError as exc:
        assert "DATABASE_URL is not set" in str(exc)
    else:
        raise AssertionError("expected explicit PostgreSQL configuration failure")


def test_api_ask_returns_partial_answer_with_refusal_and_links():
    context = create_app_context(
        manifest_path=Path("book/chapters_manifest.json"),
        data_dir=Path("data/app"),
        static_dir=Path("static"),
    )

    status, payload = handle_api_request(
        context,
        "POST",
        "/api/ask",
        {"question": "黛玉葬花体现了什么？再说明一个没有资料的后文细节"},
    )

    assert status == 200
    assert payload["status"] == "partial"
    assert payload["shortConclusion"]
    assert payload["refusal"]["message"]
    assert payload["continuationLinks"]


def test_api_ask_returns_refusal_without_internal_reason_code_in_message():
    context = create_app_context(
        manifest_path=Path("book/chapters_manifest.json"),
        data_dir=Path("data/app"),
        static_dir=Path("static"),
    )

    status, payload = handle_api_request(context, "POST", "/api/ask", {"question": "请帮我写一篇作文"})

    assert status == 200
    assert payload["status"] == "refused"
    assert payload["refusal"]["message"]
    assert "OUT_OF_SCOPE" not in payload["refusal"]["message"]


def test_api_topics_returns_five_categories():
    context = create_app_context(
        manifest_path=Path("book/chapters_manifest.json"),
        data_dir=Path("data/app"),
        static_dir=Path("static"),
    )

    status, payload = handle_api_request(context, "GET", "/api/topics")

    assert status == 200
    assert {topic["category"] for topic in payload["topics"]} == {
        "人物关系",
        "关键事件",
        "判词命运",
        "意象伏笔",
        "可引用事实",
    }


def test_api_card_returns_student_facing_knowledge_panel_payload():
    context = create_app_context(
        manifest_path=Path("book/chapters_manifest.json"),
        data_dir=Path("data/app"),
        static_dir=Path("static"),
    )

    status, payload = handle_api_request(context, "GET", "/api/cards/card-lindaiyu")

    assert status == 200
    assert payload["card"]["name"] == "林黛玉"
    assert "textUnderstanding" in payload["card"]
    assert "understandingAngles" in payload["card"]
    assert "graphRelationIds" in payload["card"]
    assert payload["evidence"]
    assert payload["relations"]
    assert payload["traceItems"]
    assert payload["traceItems"][0]["chapter"]
    assert "LightRAG" not in str(payload)


def test_api_topic_detail_links_cards_relations_and_quotable_facts():
    context = create_app_context(
        manifest_path=Path("book/chapters_manifest.json"),
        data_dir=Path("data/app"),
        static_dir=Path("static"),
    )

    status, payload = handle_api_request(context, "GET", "/api/topics/topic-image-foreshadowing")

    assert status == 200
    assert payload["topic"]["category"] == "意象伏笔"
    assert payload["topic"]["typicalQuestionPatterns"]
    assert payload["cards"]
    assert payload["relations"]
    assert payload["evidence"]


def test_static_topic_view_has_visible_knowledge_panel_target():
    js = Path("static/app.js").read_text(encoding="utf-8")
    html = Path("static/index.html").read_text(encoding="utf-8")

    assert "topic-knowledge-panel" in html
    assert "loadKnowledgeCard(target.dataset.cardId, panel)" in js
    assert "#topic-knowledge-panel" in js


def test_static_chapter_view_uses_offset_annotations_not_name_replacement():
    js = Path("static/app.js").read_text(encoding="utf-8")

    assert "renderAnnotatedOriginalText(text, annotations)" in js
    assert "data-annotation-id" in js
    assert "data-card-id" in js
    assert "sort((left, right) => left.startOffset - right.startOffset" in js


def test_static_knowledge_panel_renders_trace_jump_buttons():
    js = Path("static/app.js").read_text(encoding="utf-8")

    assert "renderTraceItems" in js
    assert "data-trace-chapter-number" in js
    assert "traceItems" in js


def test_static_styles_include_trace_and_annotation_states():
    css = Path("static/styles.css").read_text(encoding="utf-8")

    assert ".trace-list" in css
    assert ".annotation-link" in css


def test_find_available_port_skips_occupied_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen()
        occupied_port = sock.getsockname()[1]

        assert find_available_port(occupied_port, attempts=2) == occupied_port + 1
