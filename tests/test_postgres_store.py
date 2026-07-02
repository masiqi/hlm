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
