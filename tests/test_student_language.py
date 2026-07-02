from pathlib import Path


FORBIDDEN_STUDENT_TERMS = [
    "LightRAG",
    "RAG",
    "知识图谱",
    "向量检索",
    "置信度",
    "模型分数",
    "标准答案",
    "题库",
    "下一题",
    "提交答案",
    "批改",
]


def test_static_student_ui_does_not_expose_forbidden_terms():
    combined = "\n".join(
        path.read_text(encoding="utf-8")
        for path in [Path("static/index.html"), Path("static/app.js"), Path("static/styles.css")]
    )

    for term in FORBIDDEN_STUDENT_TERMS:
        assert term not in combined


def test_static_ui_contains_three_entry_points():
    html = Path("static/index.html").read_text(encoding="utf-8")

    assert "问一问" in html
    assert "读章节" in html
    assert "看专题" in html


def test_static_ui_has_no_account_or_history_features():
    combined = "\n".join(
        path.read_text(encoding="utf-8")
        for path in [Path("static/index.html"), Path("static/app.js"), Path("static/styles.css")]
    )

    for term in ["登录", "注册", "个人历史", "收藏", "学习档案", "阅读进度", "书架", "评分"]:
        assert term not in combined


def test_static_ui_escapes_api_text_before_rendering_html():
    js = Path("static/app.js").read_text(encoding="utf-8")

    assert "function escapeHtml" in js
    for expression in [
        "answer.refusal.message",
        "claim.text",
        "evidence.evidenceText",
        "entry.target",
        "entry.label",
        "card.name",
        "card.brief",
        "data.chapter.title",
        "data.reviewCard.plainSummary",
        "item",
        "data.originalText",
        "topic.title",
        "topic.description",
        "relation.description",
        "data.topic.title",
        "data.topic.description",
        "data.card.name",
    ]:
        assert f"escapeHtml({expression}" in js


def test_static_ask_view_names_source_conflict_in_student_language():
    js = Path("static/app.js").read_text(encoding="utf-8")

    assert "资料存在不一致，优先查看原文依据" in js
    assert "SOURCE_CONFLICT" not in js
