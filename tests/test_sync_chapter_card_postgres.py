from __future__ import annotations

import importlib.util
import json
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "sync_chapter_card_postgres.py"


def _import_script_module():
    assert SCRIPT_PATH.exists(), f"{SCRIPT_PATH} does not exist"
    spec = importlib.util.spec_from_file_location("sync_chapter_card_postgres", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _card(chapter: int, **overrides):
    card = {
        "id": f"review-{chapter:03d}",
        "chapter": chapter,
        "source": {
            "prompt_name": "hongloumeng_chapter_review_card",
            "prompt_version": "2026-07-01",
            "generated_at": "2026-07-02",
        },
        "plain_summary": f"第{chapter}回梗概。",
        "plot_chain": [f"第{chapter}回情节"],
        "key_events": [f"第{chapter}回事件"],
        "key_characters": [],
        "current_chapter_foreshadowing_signals": [],
        "later_association_relation_ids": [],
        "quotable_fact_ids": [],
        "retrieval_tags": [f"#第{chapter}回"],
        "understanding_focus": [f"理解第{chapter}回。"],
        "characters": [{"name": "袭人", "actions": ["服侍宝玉"]}],
        "relationships": [],
        "places": [],
        "objects": [],
        "literary_texts": [],
        "modern_explanations": [],
        "later_associations": [],
        "annotations": [{"text": "袭人", "kind": "person", "target": "card-xiren"}],
    }
    card.update(overrides)
    return card


def test_build_chapter_card_row_from_single_json_preserves_raw_card(tmp_path):
    module = _import_script_module()
    input_path = tmp_path / "027.json"
    card = _card(27)
    input_path.write_text(json.dumps(card, ensure_ascii=False), encoding="utf-8")

    row = module.load_single_chapter_card_row(input_path, expected_chapter=27)

    assert row["id"] == "review-027"
    assert row["chapter_number"] == 27
    assert row["summary"] == "第27回梗概。"
    assert row["raw_card"]["characters"] == card["characters"]
    assert row["raw_card"]["annotations"] == card["annotations"]


def test_load_single_chapter_card_row_rejects_chapter_mismatch(tmp_path):
    module = _import_script_module()
    input_path = tmp_path / "027.json"
    input_path.write_text(json.dumps(_card(28), ensure_ascii=False), encoding="utf-8")

    try:
        module.load_single_chapter_card_row(input_path, expected_chapter=27)
    except ValueError as exc:
        assert "does not match --chapter 27" in str(exc)
    else:
        raise AssertionError("expected chapter mismatch failure")


def test_main_requires_database_url_without_printing_secret(monkeypatch, tmp_path, capsys):
    module = _import_script_module()
    input_path = tmp_path / "027.json"
    input_path.write_text(json.dumps(_card(27), ensure_ascii=False), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    code = module.main(["--chapter", "27", "--input", str(input_path)])

    captured = capsys.readouterr()
    assert code == 2
    assert "DATABASE_URL is not set" in captured.err
    assert "postgresql://" not in captured.err


def test_sync_single_chapter_card_uses_scoped_upsert(monkeypatch, tmp_path):
    module = _import_script_module()
    input_path = tmp_path / "027.json"
    input_path.write_text(json.dumps(_card(27), ensure_ascii=False), encoding="utf-8")
    calls = []

    def fake_upsert(database_url, row):
        calls.append((database_url, row))

    monkeypatch.setattr(module, "upsert_single_chapter_card", fake_upsert)
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:secret@example.local:5432/hlm")
    monkeypatch.chdir(tmp_path)

    code = module.main(["--chapter", "27", "--input", str(input_path)])

    assert code == 0
    assert len(calls) == 1
    assert calls[0][0] == "postgresql://user:secret@example.local:5432/hlm"
    assert calls[0][1]["chapter_number"] == 27


def test_replace_generated_annotations_for_single_chapter_is_scoped():
    module = _import_script_module()
    executed = []

    class FakeCursor:
        def execute(self, query, params=None):
            executed.append((query, params))

        def executemany(self, query, rows):
            executed.append((query, rows))

    row = _card(27, annotations=[{"text": "袭人", "kind": "person", "target": "card-xiren"}])

    module.replace_generated_annotations_for_chapter(FakeCursor(), row, original_text="袭人问宝玉。袭人又来。")

    assert "metadata->>'source' = 'chapter_card.annotations'" in executed[0][0]
    assert executed[0][1] == (27,)
    assert len(executed[1][1]) == 2
    assert executed[1][1][0]["chapter_number"] == 27
    assert executed[1][1][0]["entity_id"] == "card-xiren"


def test_annotation_target_lookup_for_sync_maps_ids_and_names():
    module = _import_script_module()

    class FakeCursor:
        def __init__(self):
            self.query = None

        def execute(self, query, params=None):
            self.query = query

        def fetchall(self):
            return [{"id": "card-xiren", "name": "袭人"}]

    cursor = FakeCursor()

    lookup = module._annotation_target_lookup_for_sync(cursor)

    assert "SELECT id, name FROM entities" in cursor.query
    assert lookup == {"card-xiren": "card-xiren", "袭人": "card-xiren"}
