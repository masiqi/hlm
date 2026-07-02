from pathlib import Path
import json

from hlm_kg.content_store import ContentStore


def _write_minimal_store_files(tmp_path: Path, review_cards: list[dict]) -> tuple[Path, Path]:
    chapter_path = tmp_path / "book" / "chapters" / "001-第一回-甄士隐梦幻识通灵 贾雨村风尘怀闺秀.txt"
    chapter_path.parent.mkdir(parents=True)
    chapter_path.write_text("第一回 原文", encoding="utf-8")
    manifest_path = tmp_path / "book" / "chapters_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "chapters": [
                    {
                        "number": 1,
                        "title": "甄士隐梦幻识通灵 贾雨村风尘怀闺秀",
                        "file_path": str(chapter_path),
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "chapter_review_cards.json").write_text(json.dumps(review_cards, ensure_ascii=False), encoding="utf-8")
    for filename in ("knowledge_cards.json", "graph_relations.json", "topics.json", "common_entries.json", "evidence.json"):
        (data_dir / filename).write_text("[]", encoding="utf-8")
    return manifest_path, data_dir


def _review_card(**overrides):
    card = {
        "id": "review-001",
        "chapter": 1,
        "source": {
            "prompt_name": "hongloumeng_chapter_review_card",
            "prompt_version": "2026-07-01",
            "generated_at": "2026-07-02",
        },
        "plain_summary": "第一回梗概。",
        "plot_chain": ["甄士隐梦幻识通灵"],
        "key_events": [],
        "key_characters": [],
        "current_chapter_foreshadowing_signals": [],
        "later_association_relation_ids": [],
        "quotable_fact_ids": [],
        "retrieval_tags": ["#第一回"],
        "understanding_focus": ["理解真假有无。"],
        "characters": [],
        "relationships": [],
        "places": [],
        "objects": [],
        "literary_texts": [],
        "modern_explanations": [],
        "later_associations": [],
        "annotations": [],
    }
    card.update(overrides)
    return card


def test_content_store_loads_seed_chapter_review_card():
    store = ContentStore.from_paths(
        manifest_path=Path("book/chapters_manifest.json"),
        data_dir=Path("data/app"),
    )

    card = store.review_card_for_chapter(27)

    assert card.chapter == 27
    assert card.source.prompt_name == "hongloumeng_chapter_review_card"
    assert card.source.prompt_version == "2026-07-01"
    assert "黛玉葬花" in card.plain_summary
    assert card.later_association_relation_ids


def test_content_store_preserves_extended_chapter_review_card_fields(tmp_path):
    extended_card = _review_card(
        characters=[{"name": "袭人", "actions": ["劝慰宝玉"]}],
        annotations=[{"text": "袭人", "kind": "person", "target": "袭人"}],
        later_associations=[{"topic": "袭人归宿", "source_chapters": [120], "evidence": "后文章回证据"}],
    )
    manifest_path, data_dir = _write_minimal_store_files(tmp_path, [extended_card])

    store = ContentStore.from_paths(manifest_path=manifest_path, data_dir=data_dir)
    card = store.review_card_for_chapter(1)

    assert card.characters == extended_card["characters"]
    assert card.annotations == extended_card["annotations"]
    assert card.later_associations == extended_card["later_associations"]


def test_content_store_returns_none_for_missing_review_card():
    store = ContentStore.from_paths(
        manifest_path=Path("book/chapters_manifest.json"),
        data_dir=Path("data/app"),
    )

    assert store.maybe_review_card_for_chapter(1) is None


def test_content_store_reads_original_chapter_text():
    store = ContentStore.from_paths(
        manifest_path=Path("book/chapters_manifest.json"),
        data_dir=Path("data/app"),
    )

    chapter = store.chapter(27)
    text = store.chapter_text(27)

    assert chapter.number == 27
    assert chapter.title
    assert "第二十七回" in text or "第27章" in text


def test_content_store_exposes_seed_knowledge_cards_relations_topics_and_entries():
    store = ContentStore.from_paths(
        manifest_path=Path("book/chapters_manifest.json"),
        data_dir=Path("data/app"),
    )

    assert any(card.id == "card-lindaiyu" for card in store.knowledge_cards)
    assert any(relation.id == "rel-daiyu-burying-flowers-fate" for relation in store.graph_relations)
    assert {topic.category for topic in store.topics} == {
        "人物关系",
        "关键事件",
        "判词命运",
        "意象伏笔",
        "可引用事实",
    }
    assert any(entry["id"] == "entry-daiyu-burying-flowers" for entry in store.common_entries)


def test_common_entries_support_routing_targets():
    store = ContentStore.from_paths(
        manifest_path=Path("book/chapters_manifest.json"),
        data_dir=Path("data/app"),
    )
    card_ids = {card.id for card in store.knowledge_cards}
    topic_ids = {topic.id for topic in store.topics}
    chapter_numbers = set(range(1, 121))

    assert {entry["target_type"] for entry in store.common_entries} >= {"ask", "chapter", "topic", "card"}
    for entry in store.common_entries:
        target_type = entry["target_type"]
        target = entry["target"]
        if target_type == "chapter":
            assert int(target) in chapter_numbers
        elif target_type == "topic":
            assert target in topic_ids
        elif target_type == "card":
            assert target in card_ids
        else:
            assert target_type == "ask"
            assert target


def test_content_store_loads_evidence_lookup():
    store = ContentStore.from_paths(
        manifest_path=Path("book/chapters_manifest.json"),
        data_dir=Path("data/app"),
    )

    evidence = store.evidence("ev-027-daiyu-burying-flowers")

    assert evidence.source_type == "original_text"
    assert store.evidence_by_id()[evidence.id] == evidence


def test_seed_reference_integrity():
    store = ContentStore.from_paths(
        manifest_path=Path("book/chapters_manifest.json"),
        data_dir=Path("data/app"),
    )
    card_ids = {card.id for card in store.knowledge_cards}
    relation_ids = {relation.id for relation in store.graph_relations}
    evidence_ids = set(store.evidence_by_id())

    for card in store.knowledge_cards:
        assert set(card.graph_relation_ids) <= relation_ids
        assert set(card.evidence_ids) <= evidence_ids
        assert set(card.related_card_ids) <= card_ids

    for relation in store.graph_relations:
        assert set(relation.evidence_ids) <= evidence_ids

    for topic in store.topics:
        assert set(topic.card_ids) <= card_ids
        assert set(topic.relation_ids) <= relation_ids
        assert set(topic.evidence_ids) <= evidence_ids
        assert set(topic.quotable_fact_ids) <= evidence_ids

    for chapter_number in [27, 56]:
        review_card = store.review_card_for_chapter(chapter_number)
        assert set(review_card.key_characters) <= card_ids
        assert set(review_card.later_association_relation_ids) <= relation_ids
        assert set(review_card.quotable_fact_ids) <= evidence_ids
