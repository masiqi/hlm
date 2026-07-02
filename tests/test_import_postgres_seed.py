from pathlib import Path

from scripts.import_postgres_seed import annotation_rows_for_chapter, build_seed_records, trace_rows_for_card


def test_build_seed_records_loads_existing_json_and_chapters():
    records = build_seed_records(Path("book/chapters_manifest.json"), Path("data/app"))

    assert len(records.chapters) == 120
    assert any(row["number"] == 27 and "黛玉" in row["original_text"] for row in records.chapters)
    assert any(row["id"] == "card-lindaiyu" for row in records.entities)
    assert any(row["id"] == "rel-daiyu-burying-flowers-fate" for row in records.relations)
    assert any(row["id"] == "ev-027-daiyu-burying-flowers" for row in records.evidence)
    assert any(row["chapter_number"] == 27 for row in records.chapter_cards)


def test_annotation_rows_for_chapter_uses_card_names_and_offsets():
    text = "袭人见宝玉回来。宝玉问袭人。"
    cards = [
        {"id": "card-xiren", "name": "袭人", "type": "person"},
        {"id": "card-baoyu", "name": "宝玉", "type": "person"},
    ]

    rows = annotation_rows_for_chapter(8, text, cards)

    assert [row["surface_text"] for row in rows] == ["袭人", "宝玉", "宝玉", "袭人"]
    assert rows[0]["start_offset"] == 0
    assert rows[0]["end_offset"] == 2
    assert rows[0]["entity_id"] == "card-xiren"
    assert rows[0]["annotation_type"] == "person"


def test_trace_rows_for_card_turns_relations_and_evidence_into_chapter_links():
    card = {
        "id": "card-lindaiyu",
        "name": "林黛玉",
        "graph_relation_ids": ["rel-daiyu-burying-flowers-fate"],
        "evidence_ids": ["ev-027-daiyu-burying-flowers"],
    }
    relation_lookup = {
        "rel-daiyu-burying-flowers-fate": {
            "id": "rel-daiyu-burying-flowers-fate",
            "description": "黛玉葬花表现身世悲感。",
            "chapters": [27],
            "evidence_ids": ["ev-027-daiyu-burying-flowers"],
        }
    }
    evidence_lookup = {
        "ev-027-daiyu-burying-flowers": {
            "id": "ev-027-daiyu-burying-flowers",
            "chapter": 27,
            "evidence_text": "黛玉葬花并吟唱《葬花吟》。",
        }
    }

    rows = trace_rows_for_card(card, relation_lookup, evidence_lookup)

    assert rows[0]["entity_id"] == "card-lindaiyu"
    assert rows[0]["chapter_number"] == 27
    assert rows[0]["relation_id"] == "rel-daiyu-burying-flowers-fate"
    assert rows[0]["evidence_id"] == "ev-027-daiyu-burying-flowers"
    assert "黛玉葬花" in rows[0]["description"]
