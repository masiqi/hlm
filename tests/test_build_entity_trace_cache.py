from types import SimpleNamespace

from hlm_kg.domain import ChapterReviewCard, ProcessedMaterialSource
from scripts.build_entity_trace_cache import (
    build_entity_trace_cache_for_context,
    chapters_to_build,
    initial_cache,
    merge_cache,
    merge_chapter_cache,
    parse_chapter_selection,
)


def _review_card(chapter: int, **overrides):
    values = {
        "id": f"review-{chapter:03d}",
        "chapter": chapter,
        "source": ProcessedMaterialSource(prompt_name="test", prompt_version="v1"),
        "plain_summary": "summary",
        "plot_chain": [],
        "key_events": [],
        "key_characters": [],
        "current_chapter_foreshadowing_signals": [],
        "later_association_relation_ids": [],
        "quotable_fact_ids": [],
        "retrieval_tags": [],
        "understanding_focus": [],
        "characters": [],
        "relationships": [],
        "places": [],
        "objects": [],
        "literary_texts": [],
        "modern_explanations": [],
        "later_associations": [],
        "annotations": [],
    }
    values.update(overrides)
    return ChapterReviewCard(**values)


class FakeStore:
    def __init__(self, cards):
        self.cards = {card.chapter: card for card in cards}

    def maybe_review_card_for_chapter(self, chapter: int):
        return self.cards.get(chapter)

    def review_cards_for_trace_scan(self):
        return [self.cards[key] for key in sorted(self.cards)]


def test_parse_chapter_selection_accepts_ranges_and_lists():
    assert parse_chapter_selection("1-3,3,5") == [1, 2, 3, 5]


def test_build_entity_trace_cache_defaults_to_generated_static_payloads_without_lightrag():
    current = _review_card(
        1,
        characters=[{"name": "林黛玉", "role": "本回人物"}],
    )
    later = _review_card(
        2,
        characters=[{"name": "林黛玉", "actions": ["随雨村读书", "母丧哀痛"]}],
    )
    context = SimpleNamespace(store=FakeStore([current, later]), retrieval_client=None)

    cache = build_entity_trace_cache_for_context(context=context, chapters=[1])

    assert cache["1"]["林黛玉"]["trace_items"] == [
        {
            "chapter": 2,
            "label": "第2回：随雨村读书",
            "description": "随雨村读书；母丧哀痛",
            "importance": 85,
        }
    ]
    assert cache["1"]["林黛玉"]["theme_extensions"] == []


def test_build_entity_trace_cache_writes_empty_static_payload_for_unlinked_place_without_lightrag():
    current = _review_card(
        1,
        places=[{"name": "大荒山无稽崖青埂峰", "function": "神话开端地点"}],
    )
    context = SimpleNamespace(store=FakeStore([current]), retrieval_client=None)

    cache = build_entity_trace_cache_for_context(context=context, chapters=[1])

    assert cache["1"]["大荒山无稽崖青埂峰"] == {
        "trace_items": [],
        "theme_extensions": [],
    }


def test_build_entity_trace_cache_materializes_page_ready_related_trace_for_all_cards():
    current = _review_card(
        1,
        characters=[
            {"name": "贾雨村", "actions": ["见甄家丫鬟回头，误以为知己"]},
            {
                "name": "甄家丫鬟（娇杏）",
                "aliases": ["娇杏（后文可知）"],
                "actions": ["掐花时见窗内贾雨村，两次回头"],
                "importance": "因两次回头被贾雨村错认为知己，后文被娶为妾",
            },
        ],
        relationships=[
            {
                "source": "贾雨村",
                "type": "自作多情",
                "target": "甄家丫鬟",
                "description": "贾雨村见甄家丫鬟回头两次，误以为其有意于己。",
            }
        ],
    )
    later = _review_card(
        2,
        characters=[{"name": "贾雨村", "actions": ["寻访甄士隐旧交", "纳娇杏为二房", "任黛玉西席"]}],
    )
    context = SimpleNamespace(store=FakeStore([current, later]), retrieval_client=None)

    cache = build_entity_trace_cache_for_context(context=context, chapters=[1])

    assert "甄家丫鬟" not in cache["1"]
    assert cache["1"]["甄家丫鬟（娇杏）"]["trace_items"] == [
        {
            "chapter": 2,
            "label": "第2回：寻访甄士隐旧交",
            "description": "寻访甄士隐旧交；纳娇杏为二房；任黛玉西席",
            "importance": 85,
        }
    ]


def test_merge_cache_replaces_selected_chapters_only():
    existing = {"1": {"旧实体": {}}, "4": {"保留": {}}}
    generated = {"1": {"新实体": {"trace_items": []}}, "2": {}}

    assert merge_cache(existing, generated) == {
        "1": {"新实体": {"trace_items": []}},
        "2": {},
        "4": {"保留": {}},
    }


def test_chapters_to_build_can_skip_existing_completed_chapters():
    existing = {"1": {"贾雨村": {}}, "2": {}, "3": {"林黛玉": {}}}

    assert chapters_to_build([1, 2, 3, 4], existing, skip_existing=True) == [2, 4]
    assert chapters_to_build([1, 2, 3, 4], existing, skip_existing=False) == [1, 2, 3, 4]


def test_merge_chapter_cache_updates_one_chapter_without_touching_others():
    existing = {"1": {"旧实体": {}}, "3": {"保留": {}}}
    updated = merge_chapter_cache(existing, 1, {"新实体": {"trace_items": []}})

    assert updated == {"1": {"新实体": {"trace_items": []}}, "3": {"保留": {}}}


def test_replace_mode_starts_from_empty_cache():
    assert initial_cache({"1": {"旧实体": {}}}, replace=True) == {}
    assert initial_cache({"1": {"旧实体": {}}}, replace=False) == {"1": {"旧实体": {}}}


def test_overwrite_chapters_preserves_other_existing_cache():
    assert initial_cache({"1": {"旧实体": {}}, "2": {"保留": {}}}, replace=False) == {
        "1": {"旧实体": {}},
        "2": {"保留": {}},
    }


def test_final_cache_preserves_incremental_existing_cache():
    from scripts.build_entity_trace_cache import final_cache

    generated = {"1": {"新实体": {}}}
    merged = {"1": {"新实体": {}}, "3": {"保留": {}}}

    assert final_cache(merged, generated=generated, replace=False) == merged
    assert final_cache(merged, generated=generated, replace=True) == merged


def test_override_retrieval_timeout_replaces_client_config_timeout():
    from hlm_kg.lightrag_client import LightRAGClient, LightRAGConfig
    from scripts.build_entity_trace_cache import override_retrieval_timeout

    client = LightRAGClient(LightRAGConfig(base_url="http://lightrag.example", timeout_seconds=30))

    updated = override_retrieval_timeout(client, timeout_seconds=180)

    assert updated.config.timeout_seconds == 180
    assert updated.config.base_url == "http://lightrag.example"


def test_context_with_retrieval_timeout_handles_frozen_app_context():
    from dataclasses import FrozenInstanceError

    import pytest

    from hlm_kg.lightrag_client import LightRAGClient, LightRAGConfig
    from hlm_kg.web_app import AppContext
    from scripts.build_entity_trace_cache import context_with_retrieval_timeout

    client = LightRAGClient(LightRAGConfig(base_url="http://lightrag.example", timeout_seconds=30))
    context = AppContext(store=object(), ask_engine=object(), static_dir="static", retrieval_client=client)

    with pytest.raises(FrozenInstanceError):
        context.retrieval_client = client

    updated = context_with_retrieval_timeout(context, timeout_seconds=180)

    assert updated is not context
    assert updated.store is context.store
    assert updated.retrieval_client.config.timeout_seconds == 180
