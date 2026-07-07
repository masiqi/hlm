import json
import subprocess
import sys
from pathlib import Path

from hlm_kg.topic_index import build_topic_index


ROOT = Path(__file__).resolve().parents[1]


def _review_card(**overrides):
    card = {
        "id": "review-027",
        "chapter": 27,
        "source": {
            "prompt_name": "hongloumeng_chapter_review_card",
            "prompt_version": "2026-07-01",
        },
        "plain_summary": "第二十七回写黛玉葬花与宝钗扑蝶。",
        "plot_chain": ["宝钗扑蝶", "黛玉葬花"],
        "key_events": ["黛玉葬花并吟《葬花吟》"],
        "key_characters": [],
        "current_chapter_foreshadowing_signals": ["落花意象暗示人物命运"],
        "later_association_relation_ids": [],
        "quotable_fact_ids": [],
        "retrieval_tags": [],
        "understanding_focus": ["把黛玉葬花理解为人物心理、诗意表达和命运线索的交汇点。"],
        "characters": [
            {
                "name": "林黛玉",
                "actions": ["葬花并吟诗"],
                "traits": ["敏感"],
                "importance": "本回情感核心",
            },
            {
                "name": "薛宝钗",
                "actions": ["扑蝶"],
                "traits": ["机敏"],
                "importance": "与黛玉形成对照",
            },
        ],
        "relationships": [
            {
                "source": "林黛玉",
                "type": "情感映照",
                "target": "落花",
                "description": "黛玉借落花寄托身世飘零之感。",
                "chapter_evidence": "黛玉葬花并吟《葬花吟》。",
            }
        ],
        "places": [],
        "objects": [{"name": "落花", "meaning": "身世飘零的意象"}],
        "literary_texts": [{"title": "葬花吟", "quote": "花谢花飞花满天", "explanation": "表现黛玉身世悲感"}],
        "modern_explanations": [],
        "later_associations": [{"topic": "黛玉命运", "description": "葬花与后文命运悲感相关", "source_chapters": [97, 98]}],
        "annotations": [],
    }
    card.update(overrides)
    return card


def _seed_topic():
    return {
        "id": "topic-seed",
        "title": "种子专题",
        "category": "可引用事实",
        "description": "保留人工整理。",
        "card_ids": [],
        "relation_ids": [],
        "typical_question_patterns": [],
        "quotable_fact_ids": [],
        "evidence_ids": [],
    }


def _write_cli_inputs(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    review_cards_path = tmp_path / "chapter_review_cards.json"
    review_cards_path.write_text(json.dumps([_review_card()], ensure_ascii=False), encoding="utf-8")
    (data_dir / "topics.json").write_text(json.dumps([_seed_topic()], ensure_ascii=False), encoding="utf-8")
    (data_dir / "evidence.json").write_text("[]", encoding="utf-8")
    (data_dir / "knowledge_cards.json").write_text("[]", encoding="utf-8")
    (data_dir / "graph_relations.json").write_text("[]", encoding="utf-8")
    return data_dir, review_cards_path


def test_build_topic_index_generates_concrete_topics_with_resolvable_references():
    result = build_topic_index(
        review_cards=[_review_card()],
        topics=[],
        evidence=[],
        knowledge_cards=[],
        graph_relations=[],
    )

    topic_ids = {topic["id"] for topic in result.topics}
    evidence_ids = {item["id"] for item in result.evidence}
    card_ids = {item["id"] for item in result.knowledge_cards}
    relation_ids = {item["id"] for item in result.graph_relations}

    assert any(topic["category"] == "人物关系" and topic["title"] == "林黛玉" for topic in result.topics)
    assert any(topic["category"] == "关键事件" and "黛玉葬花" in topic["title"] for topic in result.topics)
    assert any(topic["category"] == "判词命运" and "葬花吟" in topic["title"] for topic in result.topics)
    assert any(topic["category"] == "意象伏笔" and "落花" in topic["title"] for topic in result.topics)
    assert any(topic["category"] == "可引用事实" for topic in result.topics)

    for topic in result.topics:
        if topic["id"].startswith("topic-auto-"):
            assert topic["evidence_ids"] or topic["card_ids"] or topic["relation_ids"]
            assert set(topic["evidence_ids"]) <= evidence_ids
            assert set(topic["quotable_fact_ids"]) <= evidence_ids
            assert set(topic["card_ids"]) <= card_ids
            assert set(topic["relation_ids"]) <= relation_ids

    assert topic_ids


def test_build_topic_index_preserves_seed_records_and_is_idempotent():
    seed_topic = {
        "id": "topic-image-foreshadowing",
        "title": "意象伏笔",
        "category": "意象伏笔",
        "description": "围绕物件、花木、诗文和跨章照应组织。",
        "card_ids": [],
        "relation_ids": [],
        "typical_question_patterns": [],
        "quotable_fact_ids": [],
        "evidence_ids": [],
    }

    first = build_topic_index([_review_card()], [seed_topic], [], [], [])
    second = build_topic_index(
        [_review_card()],
        first.topics,
        first.evidence,
        first.knowledge_cards,
        first.graph_relations,
    )

    assert first.topics == second.topics
    assert first.evidence == second.evidence
    assert first.knowledge_cards == second.knowledge_cards
    assert first.graph_relations == second.graph_relations
    assert any(topic["id"] == "topic-image-foreshadowing" for topic in second.topics)


def test_build_topic_index_rejects_forbidden_student_terms():
    result = build_topic_index(
        review_cards=[_review_card(key_events=["这是一个题库入口"])],
        topics=[],
        evidence=[],
        knowledge_cards=[],
        graph_relations=[],
    )

    combined = str(result.topics) + str(result.evidence) + str(result.knowledge_cards) + str(result.graph_relations)
    assert "题库" not in combined
    assert result.summary["skipped_candidates"] >= 1


def test_build_topic_index_cli_dry_run_does_not_write(tmp_path, capsys):
    from scripts.build_topic_index import main

    data_dir, review_cards_path = _write_cli_inputs(tmp_path)
    topics_path = data_dir / "topics.json"
    original_topics = json.loads(topics_path.read_text(encoding="utf-8"))

    exit_code = main(["--data-dir", str(data_dir), "--review-cards", str(review_cards_path)])

    assert exit_code == 0
    assert json.loads(topics_path.read_text(encoding="utf-8")) == original_topics
    output = capsys.readouterr().out
    assert "dry-run" in output
    assert "generated_topics" in output


def test_build_topic_index_cli_write_updates_topic_index_files(tmp_path):
    from scripts.build_topic_index import main

    data_dir, review_cards_path = _write_cli_inputs(tmp_path)

    exit_code = main(["--data-dir", str(data_dir), "--review-cards", str(review_cards_path), "--write"])

    assert exit_code == 0
    topics = json.loads((data_dir / "topics.json").read_text(encoding="utf-8"))
    evidence = json.loads((data_dir / "evidence.json").read_text(encoding="utf-8"))
    cards = json.loads((data_dir / "knowledge_cards.json").read_text(encoding="utf-8"))
    relations = json.loads((data_dir / "graph_relations.json").read_text(encoding="utf-8"))
    assert any(topic["id"] == "topic-seed" for topic in topics)
    assert any(topic["id"].startswith("topic-auto-") for topic in topics)
    assert any(item["id"].startswith("ev-topic-auto-") for item in evidence)
    assert any(item["id"].startswith("card-topic-auto-") for item in cards)
    assert any(item["id"].startswith("rel-topic-auto-") for item in relations)


def test_build_topic_index_script_runs_directly_from_project_root(tmp_path):
    data_dir, review_cards_path = _write_cli_inputs(tmp_path)

    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "build_topic_index.py"),
            "--data-dir",
            str(data_dir),
            "--review-cards",
            str(review_cards_path),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "dry-run" in completed.stdout
