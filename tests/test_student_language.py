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
        "topic.title",
        "topic.description",
        "relation.description",
        "data.topic.title",
        "data.topic.description",
        "data.card.name",
    ]:
        assert f"escapeHtml({expression}" in js
    assert "let annotated = escapeHtml(text)" in js


def test_static_chapter_view_handles_missing_review_card_state():
    js = Path("static/app.js").read_text(encoding="utf-8")

    assert "data.materialStatus?.hasReviewCard" in js
    assert "data.materialStatus?.message" in js
    assert "章节资料暂未生成，可先阅读原文。" in js
    assert "暂无可靠资料" in js


def test_static_chapter_view_has_chapter_selector():
    html = Path("static/index.html").read_text(encoding="utf-8")
    js = Path("static/app.js").read_text(encoding="utf-8")

    assert 'id="chapter-select"' in html
    assert 'for="chapter-select"' in html
    assert "initChapterSelector" in js
    assert "for (let number = 1; number <= 120; number += 1)" in js
    assert 'loadChapter(Number(event.currentTarget.value))' in js
    assert "chapterSelect.value = String(data.chapter.number)" in js


def test_static_common_entries_route_by_target_type():
    js = Path("static/app.js").read_text(encoding="utf-8")

    assert "handleCommonEntry" in js
    assert "data-target-type" in js
    assert "entry.targetType" in js
    assert 'target.dataset.targetType === "ask"' in js
    assert 'target.dataset.targetType === "chapter"' in js
    assert 'target.dataset.targetType === "topic"' in js
    assert 'target.dataset.targetType === "card"' in js


def test_static_chapter_original_text_uses_safe_inline_knowledge_links():
    js = Path("static/app.js").read_text(encoding="utf-8")

    assert "renderAnnotatedOriginalText" in js
    assert "escapeRegExp" in js
    assert "data-card-id" in js
    assert "annotated-original" in js
    assert "renderAnnotatedOriginalText(data.originalText, data.knowledgeCards)" in js
    assert "<pre>${escapeHtml(data.originalText)}</pre>" not in js
