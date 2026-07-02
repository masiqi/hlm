from hlm_kg.domain import ChapterAnnotation, TraceItem
from hlm_kg.postgres_store import PostgresContentStore


def test_chapter_annotation_exposes_jump_target_fields():
    annotation = ChapterAnnotation(
        id="ann-008-card-xiren-0",
        chapter=8,
        start_offset=0,
        end_offset=2,
        surface_text="袭人",
        annotation_type="person",
        entity_id="card-xiren",
        relation_id=None,
        evidence_id=None,
        display_priority=100,
    )

    assert annotation.chapter == 8
    assert annotation.surface_text == "袭人"
    assert annotation.entity_id == "card-xiren"


def test_trace_item_exposes_chapter_jump_and_evidence():
    item = TraceItem(
        id="trace-card-xiren-001",
        entity_id="card-xiren",
        chapter=8,
        relation_id="rel-xiren-baoyu",
        evidence_id="ev-008-xiren",
        title="第8回线索",
        description="袭人与宝玉相关。",
        trace_type="relation",
        sort_order=1,
        importance=80,
    )

    assert item.chapter == 8
    assert item.evidence_id == "ev-008-xiren"


def test_postgres_store_reads_annotations_from_query_rows():
    queries = []

    def fetcher(query, params):
        queries.append((query, params))
        return [
            {
                "id": "ann-008-card-xiren-0",
                "chapter_number": 8,
                "start_offset": 0,
                "end_offset": 2,
                "surface_text": "袭人",
                "annotation_type": "person",
                "entity_id": "card-xiren",
                "relation_id": None,
                "evidence_id": "ev-008-xiren",
                "display_priority": 100,
            }
        ]

    store = PostgresContentStore("postgresql://unused", fetcher=fetcher)

    annotations = store.annotations_for_chapter(8)

    assert queries[0][1] == (8,)
    assert annotations == [
        ChapterAnnotation(
            id="ann-008-card-xiren-0",
            chapter=8,
            start_offset=0,
            end_offset=2,
            surface_text="袭人",
            annotation_type="person",
            entity_id="card-xiren",
            relation_id=None,
            evidence_id="ev-008-xiren",
            display_priority=100,
        )
    ]


def test_postgres_store_reads_trace_items_from_query_rows():
    def fetcher(query, params):
        assert params == ("card-lindaiyu",)
        return [
            {
                "id": "trace-card-lindaiyu-rel-027",
                "entity_id": "card-lindaiyu",
                "chapter_number": 27,
                "relation_id": "rel-daiyu-burying-flowers-fate",
                "evidence_id": "ev-027-daiyu-burying-flowers",
                "title": "第27回线索",
                "description": "黛玉葬花表现身世悲感。",
                "trace_type": "relation",
                "sort_order": 0,
                "importance": 80,
            }
        ]

    store = PostgresContentStore("postgresql://unused", fetcher=fetcher)

    items = store.trace_items_for_entity("card-lindaiyu")

    assert items == [
        TraceItem(
            id="trace-card-lindaiyu-rel-027",
            entity_id="card-lindaiyu",
            chapter=27,
            relation_id="rel-daiyu-burying-flowers-fate",
            evidence_id="ev-027-daiyu-burying-flowers",
            title="第27回线索",
            description="黛玉葬花表现身世悲感。",
            trace_type="relation",
            sort_order=0,
            importance=80,
        )
    ]


def test_postgres_store_preserves_expanded_review_card_fields_from_raw_card():
    raw_card = {
        "id": "review-008",
        "chapter": 8,
        "source": {
            "prompt_name": "hongloumeng_chapter_review_card",
            "prompt_version": "2026-07-01",
            "generated_at": "2026-07-02",
        },
        "plain_summary": "第八回梗概。",
        "plot_chain": ["宝玉看金锁"],
        "key_events": ["宝玉看金锁"],
        "key_characters": ["card-xiren"],
        "current_chapter_foreshadowing_signals": ["金玉关系线索出现"],
        "later_association_relation_ids": [],
        "quotable_fact_ids": [],
        "retrieval_tags": ["#第八回"],
        "understanding_focus": ["理解金玉线索"],
        "characters": [{"name": "袭人", "actions": ["服侍宝玉"]}],
        "relationships": [{"source": "袭人", "type": "主仆", "target": "宝玉", "description": "袭人与宝玉有主仆照应。"}],
        "places": [{"name": "梨香院", "scenes": ["探望宝钗"]}],
        "objects": [{"name": "金锁", "meaning": "姻缘线索"}],
        "literary_texts": [{"title": "金锁铭文", "explanation": "与通灵宝玉照应"}],
        "modern_explanations": [{"quote": "原句", "modern_text": "现代解释"}],
        "later_associations": [{"topic": "金玉良缘", "source_chapters": [8], "evidence": "金锁与通灵宝玉照应"}],
        "annotations": [{"text": "袭人", "kind": "person", "target": "card-xiren"}],
    }

    def fetcher(query, params):
        assert params == (8,)
        return [
            {
                "id": "review-008",
                "chapter_number": 8,
                "summary": "第八回梗概。",
                "plot_chain": ["宝玉看金锁"],
                "key_events": ["宝玉看金锁"],
                "key_characters": ["card-xiren"],
                "foreshadowing": ["金玉关系线索出现"],
                "later_association_relation_ids": [],
                "quotable_fact_ids": [],
                "retrieval_tags": ["#第八回"],
                "understanding_focus": ["理解金玉线索"],
                "raw_card": raw_card,
                "prompt_name": "hongloumeng_chapter_review_card",
                "prompt_version": "2026-07-01",
                "generated_at": "2026-07-02",
            }
        ]

    store = PostgresContentStore("postgresql://unused", fetcher=fetcher)

    card = store.review_card_for_chapter(8)

    assert card.characters == raw_card["characters"]
    assert card.relationships == raw_card["relationships"]
    assert card.places == raw_card["places"]
    assert card.objects == raw_card["objects"]
    assert card.literary_texts == raw_card["literary_texts"]
    assert card.modern_explanations == raw_card["modern_explanations"]
    assert card.later_associations == raw_card["later_associations"]
    assert card.annotations == raw_card["annotations"]
