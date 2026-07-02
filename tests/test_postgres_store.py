from hlm_kg.domain import ChapterAnnotation, TraceItem


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
