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
    assert "读一读" in html
    assert "读章节" not in html
    assert "看专题" in html


def test_static_home_contains_primary_navigation_entries():
    html = Path("static/index.html").read_text(encoding="utf-8")
    home = html[html.index('<section id="home"') : html.index('<section id="ask"')]

    assert 'class="home-actions"' in home
    assert '<button data-view="ask" type="button">问一问</button>' in home
    assert '<button data-target-type="chapter" data-target="1" type="button">读一读</button>' in home
    assert '<button data-view="topics" type="button">看专题</button>' in home


def test_static_ask_view_contains_question_form():
    html = Path("static/index.html").read_text(encoding="utf-8")
    home = html[html.index('<section id="home"') : html.index('<section id="ask"')]
    ask = html[html.index('<section id="ask"') : html.index('<section id="chapters"')]

    assert 'id="ask-form"' not in home
    assert 'id="ask-form"' in ask
    assert 'id="question"' in ask
    assert 'id="answer"' in ask


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
            "item.name",
            "item.importance || item.role || \"\"",
            "data.chapter.title",
            "data.reviewCard.plainSummary",
            "item",
        "topic.title",
        "topic.description",
        "relation.description",
        "data.topic.title",
        "data.topic.description",
        "data.card.name",
        "extension.topic",
        "extension.description",
    ]:
        assert f"escapeHtml({expression}" in js
    assert "html += escapeHtml(text.slice(cursor))" in js
    assert "escapeHtml(label)" in js


def test_static_chapter_view_handles_missing_review_card_state():
    js = Path("static/app.js").read_text(encoding="utf-8")

    assert "data.materialStatus?.hasReviewCard" in js
    assert "data.materialStatus?.message" not in js
    assert "章节资料暂未生成，可先阅读原文。" not in js
    assert "章节资料已加载" not in js
    assert "暂无可靠资料" in js


def test_static_chapter_view_has_chapter_selector():
    html = Path("static/index.html").read_text(encoding="utf-8")
    js = Path("static/app.js").read_text(encoding="utf-8")

    assert 'id="chapter-select"' in html
    assert 'id="previous-chapter"' in html
    assert 'id="next-chapter"' in html
    assert 'for="chapter-select"' in html
    assert "initChapterSelector" in js
    assert "for (let number = 1; number <= 120; number += 1)" in js
    assert 'loadChapter(Number(event.currentTarget.value))' in js
    assert "chapterSelect.value = String(data.chapter.number)" in js
    assert "async function loadChapter(number = 1)" in js
    assert "updateChapterNavigation" in js
    assert "previousChapterButton.disabled = chapterNumber <= 1" in js
    assert "nextChapterButton.disabled = chapterNumber >= 120" in js


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


def test_static_topic_detail_renders_real_navigation_buttons():
    js = Path("static/app.js").read_text(encoding="utf-8")
    helper_start = js.index("function renderChapterJumpButton")
    start = js.index("async function loadTopicDetail")
    end = js.index("document.addEventListener", start)
    topic_helpers = js[helper_start:end]
    topic_detail = js[start:end]

    assert "renderChapterJumpButton" in topic_detail
    assert "relation.chapters?.[0]" in topic_detail
    assert "item.chapter" in topic_detail
    assert "data-chapter-number" in topic_helpers
    assert "data-topic-list-return" in topic_detail


def test_static_entity_popover_renders_theme_extensions_separately():
    js = Path("static/app.js").read_text(encoding="utf-8")

    assert "主题延展" in js
    assert "themeExtensions" in js


def test_static_entity_popover_renders_extended_neighbors_separately():
    js = Path("static/app.js").read_text(encoding="utf-8")

    assert "延伸关联" in js
    assert "extendedNeighbors" in js
    assert "由${escapeHtml(neighbor.via)}延伸到" in js
    function_body = js.split("function renderExtendedNeighbors", 1)[1].split("function renderEntityPopover", 1)[0]
    assert " -> " not in function_body
    assert "renderThemeExtensions" in js
    assert "mergeThemeExtensions" in js


def test_static_entity_popover_renders_previous_and_later_chapter_clues():
    js = Path("static/app.js").read_text(encoding="utf-8")

    assert "前文关联" in js
    assert "后文关联" in js
    assert "previousChapterJumps" in js
    assert "laterChapterJumps" in js


def test_static_entity_popover_uses_prefetched_trace_before_live_request():
    js = Path("static/app.js").read_text(encoding="utf-8")

    assert "hasPrefetchedEntityTrace" in js
    assert "if (hasPrefetchedEntityTrace(entity)) return" in js


def test_static_entity_popover_does_not_treat_static_jumps_as_prefetched_trace():
    js = Path("static/app.js").read_text(encoding="utf-8")
    start = js.index("function hasPrefetchedEntityTrace")
    end = js.index("async function loadEntityTrace", start)
    function_body = js[start:end]

    assert "entity.tracePrefetched" in function_body
    assert "chapterJumps" not in function_body
    assert "laterChapterJumps" not in function_body
    assert "previousChapterJumps" not in function_body


def test_static_entity_trace_does_not_merge_static_jumps_into_related_chapters():
    js = Path("static/app.js").read_text(encoding="utf-8")
    start = js.index("function mergeTraceItems")
    end = js.index("function mergeThemeExtensions", start)
    function_body = js[start:end]

    assert "let later = entity.laterChapterJumps || [];" in function_body
    assert "entity.chapterJumps || []" not in function_body


def test_static_entity_popover_ignores_stale_trace_responses():
    js = Path("static/app.js").read_text(encoding="utf-8")

    assert "activeEntityPopoverId" in js
    assert "activeEntityPopoverId = entityId" in js
    assert "if (activeEntityPopoverId !== entity.id) return" in js


def test_static_click_handlers_use_closest_for_nested_entity_buttons():
    js = Path("static/app.js").read_text(encoding="utf-8")

    assert 'target.closest("[data-inline-entity-id]")' in js
    assert 'target.matches("[data-inline-entity-id]")' not in js


def test_static_entity_popover_marks_active_entity_controls():
    js = Path("static/app.js").read_text(encoding="utf-8")

    assert "function markActiveEntityControls" in js
    assert "aria-pressed" in js
    assert "entity-chip-active" in js
    assert "annotation-link-active" in js


def test_static_entity_popover_hides_prefetched_empty_trace_status():
    js = Path("static/app.js").read_text(encoding="utf-8")

    assert "traceStatusText" not in js
    assert "已加载" not in js
    assert "暂无更多线索" not in js


def test_static_entity_chapter_jumps_do_not_repeat_description_below_button():
    js = Path("static/app.js").read_text(encoding="utf-8")
    start = js.index("function renderChapterJumps")
    end = js.index("function mergeTraceItems", start)
    function_body = js[start:end]

    assert "jump.description ? `<p>" not in function_body
    assert "${description}" not in function_body


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

    assert 'let activeChapterTab = "plot"' in js
    assert "renderChapterTabs" in js
    assert "setActiveChapterTab" in js
    assert "data-chapter-tab" in js
    assert "renderChapterSummary" in js
    assert "展示全部" in js
    assert "本回梗概" in js
    assert "关键情节" in js
    assert "关键事件" in js
    assert "本回怎么读" in js
    assert "data.reviewCard.keyEvents" in js
    assert "data.reviewCard.understandingFocus" in js
    assert '{ id: "summary"' not in js


def test_static_chapter_loader_prefers_static_cache_and_falls_back_to_api():
    js = Path("static/app.js").read_text(encoding="utf-8")

    assert "chapterCacheUrl" in js
    assert 'return `/chapter_cache/${String(number).padStart(3, "0")}.json`' in js
    assert "loadChapterPayload" in js
    assert "getJson(chapterCacheUrl(number))" in js
    assert "getJson(`/api/chapters/${number}`)" in js


def test_static_chapter_view_supports_best_effort_source_scrolling():
    js = Path("static/app.js").read_text(encoding="utf-8")

    assert "scrollOriginalTextToNeedle" in js
    assert "data-source-needle" in js
    assert "original-hit-highlight" in js


def test_static_chapter_loading_ignores_stale_responses():
    js = Path("static/app.js").read_text(encoding="utf-8")

    assert "let chapterLoadRequestId = 0" in js
    assert "const requestId = ++chapterLoadRequestId" in js
    assert "if (requestId !== chapterLoadRequestId) return" in js


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
