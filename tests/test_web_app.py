import socket
from pathlib import Path

from hlm_kg.web_app import create_app_context, find_available_port, handle_api_request


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


def test_find_available_port_skips_occupied_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen()
        occupied_port = sock.getsockname()[1]

        assert find_available_port(occupied_port, attempts=2) == occupied_port + 1
