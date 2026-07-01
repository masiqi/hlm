from pathlib import Path

from hlm_kg.content_store import ContentStore


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
