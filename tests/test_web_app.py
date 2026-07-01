from pathlib import Path

from hlm_kg.web_app import create_app_context, handle_api_request


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
