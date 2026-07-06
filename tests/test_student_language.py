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
    assert "html += escapeHtml(text.slice(cursor))" in js
    assert "escapeHtml(label)" in js


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




def test_static_chapter_selector_labels_include_chapter_titles():
    js = Path("static/app.js").read_text(encoding="utf-8")

    assert "CHAPTER_TITLES" in js
    assert "甄士隐梦幻识通灵 贾雨村风尘怀闺秀" in js
    assert "凸碧堂品笛感凄清 凹晶馆联诗悲寂寞" in js
    assert 'option.textContent = chapterOptionLabel(number)' in js
    assert "`第 ${number} 回：${title}`" in js
    assert "`第 ${number} 回`" in js

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
    assert "data-annotation-id" in js
    assert "data-card-id" in js
    assert "annotated-original" in js
    assert "renderAnnotatedOriginalText(data.originalText, data.annotations || [])" in js
    assert "<pre>${escapeHtml(data.originalText)}</pre>" not in js


def test_static_ask_view_renders_answer_states_and_continuation_links():
    js = Path("static/app.js").read_text(encoding="utf-8")

    assert "renderContinuationLinks" in js
    assert "短结论" in js
    assert "已支持部分" in js
    assert "资料不足部分" in js
    assert "继续查看" in js
    assert "answer.continuationLinks" in js
    assert "data-chapter-number" in js
    assert "data-card-id" in js
    assert "data-topic-id" in js


def test_static_ask_view_uses_student_facing_evidence_labels():
    js = Path("static/app.js").read_text(encoding="utf-8")

    assert "function sourceLabel" in js
    assert "原文依据" in js
    assert "章节资料" in js
    assert "关系线索" in js
    assert "evidence.sourceType" in js
    assert "sourceType" not in Path("static/index.html").read_text(encoding="utf-8")


def test_static_chapter_view_renders_fast_reading_sections_from_review_card():
    js = Path("static/app.js").read_text(encoding="utf-8")

    assert "本回梗概" in js
    assert "关键情节" in js
    assert "关键事件" in js
    assert "本回怎么读" in js
    assert "data.reviewCard.keyEvents" in js
    assert "data.reviewCard.understandingFocus" in js


def test_static_ask_view_names_source_conflict_in_student_language():
    js = Path("static/app.js").read_text(encoding="utf-8")

    assert "资料存在不一致，优先查看原文依据" in js
    assert "SOURCE_CONFLICT" not in js


def test_static_mobile_knowledge_panel_has_open_and_close_controls():
    html = Path("static/index.html").read_text(encoding="utf-8")
    js = Path("static/app.js").read_text(encoding="utf-8")
    css = Path("static/styles.css").read_text(encoding="utf-8")

    assert 'data-panel-close="knowledge-panel"' in html
    assert 'data-panel-close="topic-knowledge-panel"' in html
    assert "openKnowledgePanel" in js
    assert "closeKnowledgePanel" in js
    assert "knowledge-panel open" in js
    assert "[data-panel-close]" in js
    assert ".knowledge-panel.open" in css
    assert "position: fixed" in css
