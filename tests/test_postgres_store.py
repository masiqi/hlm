from hlm_kg.domain import ChapterAnnotation, Evidence, GraphRelation, KnowledgeCard, TraceItem
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


def test_postgres_store_reads_entity_trace_payload_cache():
    queries = []

    def fetcher(query, params):
        queries.append((query, params))
        assert params == ("贾雨村", 1)
        return [
            {
                "trace_items": [
                    {
                        "chapter": 2,
                        "label": "第2回：贾雨村复职",
                        "description": "贾雨村后来复职。",
                        "importance": 90,
                    }
                ],
                "theme_extensions": [
                    {
                        "topic": "官场线索",
                        "description": "贾雨村线索映照官场升沉。",
                        "chapter_jumps": [{"chapter": 4, "label": "第4回：葫芦案"}],
                    }
                ],
            }
        ]

    store = PostgresContentStore("postgresql://unused", fetcher=fetcher)

    payload = store.entity_trace_payload("贾雨村", 1)

    assert "entity_trace_cache" in queries[0][0]
    assert payload["trace_items"][0]["chapter"] == 2
    assert payload["theme_extensions"][0]["topic"] == "官场线索"


def test_postgres_store_reads_entity_trace_payloads_for_chapter_once_and_caches():
    calls = []

    def fetcher(query, params):
        calls.append((query, params))
        assert params == (1,)
        return [
            {
                "entity_name": "大荒山无稽崖青埂峰",
                "trace_items": [],
                "theme_extensions": [],
            },
            {
                "entity_name": "贾雨村",
                "trace_items": [{"chapter": 2, "label": "第2回：贾雨村复职"}],
                "theme_extensions": [],
            },
        ]

    store = PostgresContentStore("postgresql://unused", fetcher=fetcher)

    first = store.entity_trace_payloads_for_chapter(1)
    second = store.entity_trace_payloads_for_chapter(1)

    assert len(calls) == 1
    assert "entity_trace_cache" in calls[0][0]
    assert first["大荒山无稽崖青埂峰"] == {"trace_items": [], "theme_extensions": []}
    assert first["贾雨村"]["trace_items"][0]["chapter"] == 2
    assert second == first


def test_postgres_store_reads_entity_graph_payloads_for_names():
    calls = []

    def fetcher(query, params):
        calls.append((query, params))
        assert params == (["顽石", "通灵宝玉"],)
        return [
            {
                "entity_name": "顽石",
                "description": "无才补天被弃于青埂峰下的石头。",
                "neighbors": [{"name": "通灵宝玉", "relationship": "前世本体"}],
                "extended_neighbors": [{"via": "通灵宝玉", "to": "贾宝玉", "depth": 2}],
                "raw_graph": {"nodes": []},
                "metadata": {"source": "lightrag_graph"},
            }
        ]

    store = PostgresContentStore("postgresql://unused", fetcher=fetcher)

    payloads = store.entity_graph_payloads_for_names(["顽石", "通灵宝玉"])

    assert len(calls) == 1
    assert "entity_graph_cache" in calls[0][0]
    assert payloads == {
        "顽石": {
            "description": "无才补天被弃于青埂峰下的石头。",
            "neighbors": [{"name": "通灵宝玉", "relationship": "前世本体"}],
            "extended_neighbors": [{"via": "通灵宝玉", "to": "贾宝玉", "depth": 2}],
            "raw_graph": {"nodes": []},
            "metadata": {"source": "lightrag_graph"},
        }
    }


def test_postgres_store_reads_lightweight_entity_graph_descriptions_for_names():
    calls = []

    def fetcher(query, params):
        calls.append((query, params))
        assert params == (["顽石", "通灵宝玉"],)
        assert "raw_graph" not in query
        assert "neighbors" not in query
        return [
            {
                "entity_name": "顽石",
                "description": "无才补天被弃于青埂峰下的石头。",
            }
        ]

    store = PostgresContentStore("postgresql://unused", fetcher=fetcher)

    payloads = store.entity_graph_descriptions_for_names(["顽石", "通灵宝玉"])

    assert len(calls) == 1
    assert "entity_graph_cache" in calls[0][0]
    assert payloads == {"顽石": "无才补天被弃于青埂峰下的石头。"}


def test_postgres_store_falls_back_for_generated_topic_detail_records():
    fallback_card = KnowledgeCard(
        id="card-topic-auto-person-lindaiyu",
        name="林黛玉",
        type="person",
        brief="林黛玉相关人物。",
        text_understanding=[],
        understanding_angles=[],
        graph_relation_ids=[],
        evidence_ids=["ev-topic-auto-ch027-characters-000-lindaiyu"],
        related_card_ids=[],
    )
    fallback_evidence = Evidence(
        id="ev-topic-auto-ch027-characters-000-lindaiyu",
        source_type="processed_material",
        chapter=27,
        location="第 27 回章节资料：characters",
        quote=None,
        evidence_text="林黛玉：葬花并吟诗。",
        entity_ids=[fallback_card.id],
        relation_id=None,
        confidence="explicit",
        provenance="data/app/chapter_review_cards.json:review-027:characters:0",
        derived_from_ids=[],
    )
    fallback_relation = GraphRelation(
        id="rel-topic-auto-ch027-lindaiyu-flower-00",
        subject_id=fallback_card.id,
        predicate="image",
        object_id="card-topic-auto-image-flower",
        chapters=[27],
        evidence_ids=[fallback_evidence.id],
        provenance="curated",
        description="林黛玉与落花的意象关系。",
    )

    class FallbackStore:
        def knowledge_card(self, card_id):
            assert card_id == fallback_card.id
            return fallback_card

        def evidence(self, evidence_id):
            assert evidence_id == fallback_evidence.id
            return fallback_evidence

        def graph_relation(self, relation_id):
            assert relation_id == fallback_relation.id
            return fallback_relation

    def fetcher(query, params):
        return []

    store = PostgresContentStore("postgresql://unused", fallback_store=FallbackStore(), fetcher=fetcher)

    assert store.knowledge_card(fallback_card.id) == fallback_card
    assert store.evidence(fallback_evidence.id) == fallback_evidence
    assert store.graph_relation(fallback_relation.id) == fallback_relation


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


def test_postgres_store_bulk_review_card_scan_fetches_once_and_caches():
    calls = []
    raw_card = {
        "characters": [{"name": "林黛玉", "actions": ["随雨村读书"]}],
        "relationships": [],
        "places": [],
        "objects": [],
        "literary_texts": [],
        "modern_explanations": [],
        "later_associations": [],
        "annotations": [],
    }

    def fetcher(query, params):
        calls.append((query, params))
        assert params == ()
        return [
            {
                "id": "review-002",
                "chapter_number": 2,
                "summary": "第二回梗概。",
                "plot_chain": ["雨村任西席"],
                "key_events": ["贾雨村任林黛玉西席"],
                "key_characters": [],
                "foreshadowing": [],
                "later_association_relation_ids": [],
                "quotable_fact_ids": [],
                "retrieval_tags": ["#第二回"],
                "understanding_focus": ["理解林家线索"],
                "raw_card": raw_card,
                "prompt_name": "hongloumeng_chapter_review_card",
                "prompt_version": "2026-07-01",
                "generated_at": "2026-07-02",
            }
        ]

    store = PostgresContentStore("postgresql://unused", fetcher=fetcher)

    first = store.review_cards_for_trace_scan()
    second = store.review_cards_for_trace_scan()

    assert len(calls) == 1
    assert "ORDER BY c.number" in calls[0][0]
    assert first[0].chapter == 2
    assert first[0].characters == raw_card["characters"]
    assert second[0].chapter == 2
