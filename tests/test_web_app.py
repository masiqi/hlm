import socket
import json
from pathlib import Path

from hlm_kg.web_app import create_app_context, find_available_port, handle_api_request

ROOT = Path(__file__).resolve().parents[1]


def _write_minimal_app_context_files(tmp_path: Path, review_cards: list[dict]) -> tuple[Path, Path, Path]:
    chapter_path = tmp_path / "book" / "chapters" / "001-第一回-甄士隐梦幻识通灵 贾雨村风尘怀闺秀.txt"
    chapter_path.parent.mkdir(parents=True)
    chapter_path.write_text("第一回 原文", encoding="utf-8")
    manifest_path = tmp_path / "book" / "chapters_manifest.json"
    manifest_path.write_text(
        json.dumps({"chapters": [{"number": 1, "title": "甄士隐梦幻识通灵 贾雨村风尘怀闺秀", "file_path": str(chapter_path)}]}, ensure_ascii=False),
        encoding="utf-8",
    )
    data_dir = tmp_path / "data"
    static_dir = tmp_path / "static"
    data_dir.mkdir()
    static_dir.mkdir()
    (data_dir / "chapter_review_cards.json").write_text(json.dumps(review_cards, ensure_ascii=False), encoding="utf-8")
    for filename in ("knowledge_cards.json", "graph_relations.json", "topics.json", "common_entries.json", "evidence.json"):
        (data_dir / filename).write_text("[]", encoding="utf-8")
    return manifest_path, data_dir, static_dir


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


def test_api_chapter_returns_chapter_evidence_page_payload():
    context = create_app_context(
        manifest_path=Path("book/chapters_manifest.json"),
        data_dir=Path("data/app"),
        static_dir=Path("static"),
    )

    status, payload = handle_api_request(context, "GET", "/api/chapters/27")

    assert status == 200
    assert payload["chapter"]["number"] == 27
    assert "originalText" in payload
    assert "reviewCard" in payload
    assert "knowledgeCards" in payload
    assert "annotations" in payload
    assert "LightRAG" not in str(payload)


def test_api_chapter_returns_extended_review_card_fields(tmp_path):
    review_card = _review_card(
        characters=[{"name": "袭人", "actions": ["劝慰宝玉"]}],
        annotations=[{"text": "袭人", "kind": "person", "target": "袭人"}],
        later_associations=[{"topic": "袭人归宿", "source_chapters": [120], "evidence": "后文章回证据"}],
    )
    manifest_path, data_dir, static_dir = _write_minimal_app_context_files(tmp_path, [review_card])
    context = create_app_context(manifest_path=manifest_path, data_dir=data_dir, static_dir=static_dir)

    status, payload = handle_api_request(context, "GET", "/api/chapters/1")

    assert status == 200
    assert payload["reviewCard"]["characters"] == review_card["characters"]
    assert payload["reviewCard"]["annotations"] == review_card["annotations"]
    assert payload["reviewCard"]["laterAssociations"] == [
        {"topic": "袭人归宿", "sourceChapters": [120], "evidence": "后文章回证据"}
    ]


def test_api_chapter_returns_inline_entity_payload_from_review_card(tmp_path):
    review_card = _review_card(
        plain_summary="第一回主要写袭人与宝玉在房中一问一答，借日常照看与劝慰显出主仆之间的亲近关系。人物行动虽小，却能帮助学生理解贾府日常生活中的照料、规劝和情感依附。袭人既是服侍宝玉的人，也常以较稳妥的方式提醒宝玉，这种关系不是单纯事务关系，而是牵连宝玉性情、房中秩序和后来多处情节的重要线索。本回阅读时应先抓住谁在照看谁，再看人物语言如何显出关系的亲疏与权力位置。",
        characters=[
            {
                "name": "袭人",
                "aliases": ["花袭人"],
                "role": "宝玉房中丫鬟",
                "actions": ["劝慰宝玉"],
                "traits": ["稳妥细心"],
                "evidence": ["袭人见宝玉回来"],
                "importance": "帮助理解宝玉房中日常关系",
            }
        ],
        relationships=[
            {
                "source": "袭人",
                "type": "照料",
                "target": "宝玉",
                "description": "袭人在本回照看并劝慰宝玉。",
                "chapter_evidence": "袭人见宝玉回来。",
            }
        ],
        objects=[
            {
                "name": "扇子",
                "context": "房中日常物件",
                "meaning": "衬托生活场景",
                "related_entities": ["袭人"],
            }
        ],
        later_associations=[
            {
                "topic": "袭人归宿",
                "description": "袭人线索需要联系后文章回继续理解。",
                "source_chapters": [120],
                "evidence": "后文章回证据",
            }
        ],
        annotations=[{"text": "袭人", "kind": "person", "target": "袭人", "note": "宝玉房中丫鬟"}],
    )
    manifest_path, data_dir, static_dir = _write_minimal_app_context_files(tmp_path, [review_card])
    chapter_path = tmp_path / "book" / "chapters" / "001-第一回-甄士隐梦幻识通灵 贾雨村风尘怀闺秀.txt"
    chapter_path.write_text("袭人见宝玉回来。宝玉问袭人。", encoding="utf-8")
    context = create_app_context(manifest_path=manifest_path, data_dir=data_dir, static_dir=static_dir)

    status, payload = handle_api_request(context, "GET", "/api/chapters/1")

    assert status == 200
    assert payload["inlineEntities"][0]["name"] == "袭人"
    assert payload["inlineEntities"][0]["summary"]
    assert payload["inlineEntities"][0]["relations"]
    assert payload["inlineEntities"][0]["chapterJumps"] == [
        {
            "chapter": 120,
            "label": "第120回：袭人归宿",
            "description": "袭人线索需要联系后文章回继续理解。",
            "importance": 90,
        }
    ]
    assert payload["annotations"][0]["entityId"] == payload["inlineEntities"][0]["id"]
    assert payload["annotations"][0]["startOffset"] == 0


def test_api_chapter_later_association_topic_does_not_leak_to_mentioned_people(tmp_path):
    review_card = _review_card(
        characters=[
            {"name": "林黛玉", "actions": ["与宝玉初会"]},
            {"name": "贾宝玉", "actions": ["摔通灵宝玉"]},
        ],
        later_associations=[
            {
                "topic": "林黛玉",
                "description": "林黛玉与表兄贾宝玉青梅竹马，后文多次互为知己。",
                "source_chapters": [5],
                "evidence": "林黛玉与表兄贾宝玉青梅竹马。",
            }
        ],
    )
    manifest_path, data_dir, static_dir = _write_minimal_app_context_files(tmp_path, [review_card])
    context = create_app_context(manifest_path=manifest_path, data_dir=data_dir, static_dir=static_dir)

    status, payload = handle_api_request(context, "GET", "/api/chapters/1")

    assert status == 200
    by_name = {entity["name"]: entity for entity in payload["inlineEntities"]}
    assert by_name["林黛玉"]["laterClues"]
    assert by_name["贾宝玉"]["laterClues"] == []
    assert by_name["贾宝玉"]["chapterJumps"] == []


def test_api_chapter_attaches_later_association_to_foreshadowing_literary_text(tmp_path):
    review_card = _review_card(
        characters=[
            {
                "name": "贾雨村",
                "role": "寄居葫芦庙的穷儒",
                "actions": ["中秋对月吟诗"],
            }
        ],
        literary_texts=[
            {
                "title": "贾雨村中秋对月寓怀绝句",
                "short_quote": "时逢三五便团圆，满把清光护玉栏。",
                "explanation": "写贾雨村借月抒怀。",
                "function": "展现贾雨村的抱负与野心，被甄士隐赞为飞腾之兆，也为后文发迹埋下伏笔",
            }
        ],
        later_associations=[
            {
                "topic": "甄士隐",
                "description": "甄士隐后文出家悟道。",
                "source_chapters": [120],
                "evidence": "甄士隐后文出家悟道。",
            },
            {
                "topic": "贾雨村",
                "description": "贾雨村得甄士隐资助后进京赶考，后文起复为官并徇私判案。",
                "source_chapters": [2, 4],
                "evidence": "贾雨村后文起复为官并徇私判案。",
            }
        ],
    )
    manifest_path, data_dir, static_dir = _write_minimal_app_context_files(tmp_path, [review_card])
    context = create_app_context(manifest_path=manifest_path, data_dir=data_dir, static_dir=static_dir)

    status, payload = handle_api_request(context, "GET", "/api/chapters/1")

    assert status == 200
    by_name = {item["name"]: item for item in payload["inlineEntities"]}
    assert by_name["贾雨村"]["laterClues"] == [
        {
            "topic": "贾雨村",
            "description": "贾雨村得甄士隐资助后进京赶考，后文起复为官并徇私判案。",
            "evidence": "贾雨村得甄士隐资助后进京赶考，后文起复为官并徇私判案。",
        }
    ]
    assert by_name["贾雨村中秋对月寓怀绝句"]["laterClues"] == [
        {
            "topic": "贾雨村",
            "description": "贾雨村得甄士隐资助后进京赶考，后文起复为官并徇私判案。",
            "evidence": "贾雨村得甄士隐资助后进京赶考，后文起复为官并徇私判案。",
        }
    ]
    assert [item["topic"] for item in by_name["贾雨村中秋对月寓怀绝句"]["laterClues"]] == ["贾雨村"]
    assert by_name["贾雨村中秋对月寓怀绝句"]["chapterJumps"] == [
        {
            "chapter": 2,
            "label": "第2回：贾雨村",
            "description": "贾雨村得甄士隐资助后进京赶考，后文起复为官并徇私判案。",
            "importance": 90,
        },
        {
            "chapter": 4,
            "label": "第4回：贾雨村",
            "description": "贾雨村得甄士隐资助后进京赶考，后文起复为官并徇私判案。",
            "importance": 90,
        },
    ]


def test_api_chapter_does_not_attach_later_association_to_plain_literary_mention(tmp_path):
    review_card = _review_card(
        literary_texts=[
            {
                "title": "贾雨村窗前所见",
                "short_quote": "窗外有女子嗽声。",
                "explanation": "写贾雨村在甄家书房外听见动静。",
                "function": "帮助理解本回人物初次照面",
            }
        ],
        later_associations=[
            {
                "topic": "贾雨村",
                "description": "贾雨村后文起复为官并徇私判案。",
                "source_chapters": [4],
                "evidence": "贾雨村后文起复为官并徇私判案。",
            }
        ],
    )
    manifest_path, data_dir, static_dir = _write_minimal_app_context_files(tmp_path, [review_card])
    context = create_app_context(manifest_path=manifest_path, data_dir=data_dir, static_dir=static_dir)

    status, payload = handle_api_request(context, "GET", "/api/chapters/1")

    assert status == 200
    entity = next(item for item in payload["inlineEntities"] if item["name"] == "贾雨村窗前所见")
    assert entity["laterClues"] == []
    assert entity["chapterJumps"] == []


def test_api_chapter_keeps_review_card_later_association_when_prefetched_trace_is_empty(tmp_path):
    review_card = _review_card(
        literary_texts=[
            {
                "title": "贾雨村中秋对月寓怀绝句",
                "short_quote": "时逢三五便团圆，满把清光护玉栏。",
                "explanation": "写贾雨村借月抒怀。",
                "function": "展现贾雨村的抱负与野心，也为后文发迹埋下伏笔",
            }
        ],
        later_associations=[
            {
                "topic": "贾雨村",
                "description": "贾雨村得甄士隐资助后进京赶考，后文起复为官并徇私判案。",
                "source_chapters": [2, 4],
                "evidence": "贾雨村后文起复为官并徇私判案。",
            }
        ],
    )
    manifest_path, data_dir, static_dir = _write_minimal_app_context_files(tmp_path, [review_card])
    (data_dir / "entity_trace_cache.json").write_text(
        json.dumps(
            {
                "贾雨村中秋对月寓怀绝句": {
                    "trace_items": [],
                    "theme_extensions": [],
                    "metadata": {"chapter": 1},
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    context = create_app_context(manifest_path=manifest_path, data_dir=data_dir, static_dir=static_dir)

    status, payload = handle_api_request(context, "GET", "/api/chapters/1")

    assert status == 200
    entity = next(item for item in payload["inlineEntities"] if item["name"] == "贾雨村中秋对月寓怀绝句")
    assert entity["laterClues"]
    assert entity["chapterJumps"] == [
        {
            "chapter": 2,
            "label": "第2回：贾雨村",
            "description": "贾雨村得甄士隐资助后进京赶考，后文起复为官并徇私判案。",
            "importance": 90,
        },
        {
            "chapter": 4,
            "label": "第4回：贾雨村",
            "description": "贾雨村得甄士隐资助后进京赶考，后文起复为官并徇私判案。",
            "importance": 90,
        },
    ]


def test_api_chapter_limits_inline_entity_later_association_jumps(tmp_path):
    long_description = "荣国府线索" * 80
    review_card = _review_card(
        characters=[{"name": "荣国府", "actions": ["冷子兴演说荣国府"]}],
        later_associations=[
            {
                "topic": "荣国府",
                "description": long_description,
                "source_chapters": list(range(2, 32)),
                "evidence": long_description,
            }
        ],
    )
    manifest_path, data_dir, static_dir = _write_minimal_app_context_files(tmp_path, [review_card])
    context = create_app_context(manifest_path=manifest_path, data_dir=data_dir, static_dir=static_dir)

    status, payload = handle_api_request(context, "GET", "/api/chapters/1")

    assert status == 200
    entity = next(item for item in payload["inlineEntities"] if item["name"] == "荣国府")
    assert len(entity["chapterJumps"]) == 12
    assert all(len(jump.get("description", "")) <= 100 for jump in entity["chapterJumps"])
    assert len(json.dumps(entity, ensure_ascii=False)) < 5000


def test_api_chapter_sanitizes_sep_from_student_payload(tmp_path):
    review_card = _review_card(
        characters=[
            {
                "name": "贾宝玉",
                "role": "荣国府公子<SEP>神瑛侍者下凡",
                "actions": ["衔玉而生<SEP>与通灵宝玉相伴"],
                "importance": "身份线索<SEP>命运线索",
            }
        ],
        objects=[
            {
                "name": "通灵宝玉",
                "context": "本回出现<SEP>后文反复照应",
                "meaning": "身份象征<SEP>命运象征",
            }
        ],
        later_associations=[
            {
                "topic": "贾宝玉 -> 通灵宝玉",
                "description": "贾宝玉衔玉而生<SEP>失玉后痴傻",
                "source_chapters": [3, 94],
                "evidence": "含玉而生<SEP>通灵宝玉丢失",
            }
        ],
        annotations=[{"text": "通灵宝玉", "kind": "object", "target": "通灵宝玉"}],
    )
    manifest_path, data_dir, static_dir = _write_minimal_app_context_files(tmp_path, [review_card])
    chapter_path = tmp_path / "book" / "chapters" / "001-第一回-甄士隐梦幻识通灵 贾雨村风尘怀闺秀.txt"
    chapter_path.write_text("通灵宝玉出现。", encoding="utf-8")
    context = create_app_context(manifest_path=manifest_path, data_dir=data_dir, static_dir=static_dir)

    status, payload = handle_api_request(context, "GET", "/api/chapters/1")

    assert status == 200
    assert "<SEP>" not in json.dumps(payload, ensure_ascii=False)
    assert "贾宝玉衔玉而生；失玉后痴傻" in json.dumps(payload, ensure_ascii=False)


def test_api_chapter_auto_adds_inline_entity_annotations_when_card_annotations_are_sparse(tmp_path):
    review_card = _review_card(
        characters=[{"name": "贾雨村", "actions": ["接受甄士隐资助"]}],
        objects=[{"name": "通灵宝玉", "context": "梦中得见"}],
        annotations=[],
    )
    manifest_path, data_dir, static_dir = _write_minimal_app_context_files(tmp_path, [review_card])
    chapter_path = tmp_path / "book" / "chapters" / "001-第一回-甄士隐梦幻识通灵 贾雨村风尘怀闺秀.txt"
    chapter_path.write_text("贾雨村见甄士隐。通灵宝玉在梦中一闪。贾雨村后来进京。", encoding="utf-8")
    context = create_app_context(manifest_path=manifest_path, data_dir=data_dir, static_dir=static_dir)

    status, payload = handle_api_request(context, "GET", "/api/chapters/1")

    assert status == 200
    annotations = payload["annotations"]
    assert [annotation["surfaceText"] for annotation in annotations] == ["贾雨村", "通灵宝玉", "贾雨村"]
    assert {annotation["inlineEntityId"] for annotation in annotations} == {
        "chapter-001-entity-贾雨村",
        "chapter-001-entity-通灵宝玉",
    }


def test_api_chapter_adds_literary_text_entities_mentioned_in_review_text(tmp_path):
    review_card = _review_card(
        plain_summary="空空道人抄录《石头记》，后来又题作《金陵十二钗》。",
        key_events=["空空道人传抄《石头记》"],
        characters=[{"name": "贾雨村", "aliases": ["贾化"], "actions": ["中秋咏怀"]}],
        annotations=[],
    )
    manifest_path, data_dir, static_dir = _write_minimal_app_context_files(tmp_path, [review_card])
    chapter_path = tmp_path / "book" / "chapters" / "001-第一回-甄士隐梦幻识通灵 贾雨村风尘怀闺秀.txt"
    chapter_path.write_text("贾化又名贾雨村。空空道人看见《石头记》。", encoding="utf-8")
    context = create_app_context(manifest_path=manifest_path, data_dir=data_dir, static_dir=static_dir)

    status, payload = handle_api_request(context, "GET", "/api/chapters/1")

    assert status == 200
    names = {entity["name"] for entity in payload["inlineEntities"]}
    assert "《石头记》" in names
    assert "《金陵十二钗》" in names
    surfaces = [annotation["surfaceText"] for annotation in payload["annotations"]]
    assert "贾化" in surfaces
    assert "《石头记》" in surfaces


def test_api_entity_trace_adds_related_chapter_jumps_from_generated_chapter_cards(tmp_path):
    review_card = _review_card(
        characters=[{"name": "贾雨村", "actions": ["接受资助"]}],
        annotations=[{"text": "贾雨村", "kind": "person", "target": "贾雨村"}],
    )
    later_card = _review_card(
        id="review-002",
        chapter=2,
        characters=[{"name": "贾雨村", "actions": ["复职授官"]}],
        annotations=[{"text": "贾雨村", "kind": "person", "target": "贾雨村"}],
    )
    manifest_path, data_dir, static_dir = _write_minimal_app_context_files(tmp_path, [review_card, later_card])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    second_path = tmp_path / "book" / "chapters" / "002-第二回-贾夫人仙逝扬州城 冷子兴演说荣国府.txt"
    second_path.write_text("第二回 原文", encoding="utf-8")
    manifest["chapters"].append(
        {
            "number": 2,
            "title": "贾夫人仙逝扬州城 冷子兴演说荣国府",
            "file_path": str(second_path),
        }
    )
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    context = create_app_context(manifest_path=manifest_path, data_dir=data_dir, static_dir=static_dir)

    status, payload = handle_api_request(context, "GET", "/api/chapters/1")

    assert status == 200
    entity = payload["inlineEntities"][0]
    assert entity["name"] == "贾雨村"
    assert entity["chapterJumps"] == []

    status, payload = handle_api_request(context, "GET", "/api/entity-trace?name=%E8%B4%BE%E9%9B%A8%E6%9D%91&chapter=1")

    assert status == 200
    assert payload["traceItems"] == [
        {
            "chapter": 2,
            "label": "第2回：复职授官",
            "description": "复职授官",
            "importance": 85,
        }
    ]


def test_api_chapter_leaves_generated_chapter_jumps_to_entity_trace_endpoint(tmp_path):
    first_card = _review_card(
        characters=[{"name": "贾雨村", "actions": ["接受资助"]}],
    )
    current_card = _review_card(
        id="review-002",
        chapter=2,
        characters=[{"name": "贾雨村", "actions": ["革职后遇冷子兴"]}],
    )
    later_card = _review_card(
        id="review-003",
        chapter=3,
        characters=[{"name": "贾雨村", "actions": ["由林如海推荐入都"]}],
    )
    manifest_path, data_dir, static_dir = _write_minimal_app_context_files(tmp_path, [first_card, current_card, later_card])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for number in (2, 3):
        chapter_path = tmp_path / "book" / "chapters" / f"{number:03d}-test.txt"
        chapter_path.write_text(f"第{number}回 原文", encoding="utf-8")
        manifest["chapters"].append({"number": number, "title": f"第{number}回", "file_path": str(chapter_path)})
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    context = create_app_context(manifest_path=manifest_path, data_dir=data_dir, static_dir=static_dir)

    status, payload = handle_api_request(context, "GET", "/api/chapters/2")

    assert status == 200
    entity = payload["inlineEntities"][0]
    assert entity["previousChapterJumps"] == []
    assert entity["laterChapterJumps"] == []
    assert entity["chapterJumps"] == []

    status, payload = handle_api_request(context, "GET", "/api/entity-trace?name=%E8%B4%BE%E9%9B%A8%E6%9D%91&chapter=2")

    assert status == 200
    assert [item["chapter"] for item in payload["traceItems"]] == [1, 3]


def test_api_entity_trace_uses_generated_events_without_live_retrieval(tmp_path):
    current_card = _review_card(
        chapter=3,
        id="review-003",
        characters=[{"name": "林黛玉", "actions": ["与宝玉初会"]}],
    )
    previous_card = _review_card(
        chapter=2,
        id="review-002",
        characters=[{"name": "林黛玉", "actions": ["随雨村读书", "母丧哀痛"]}],
    )
    later_card = _review_card(
        chapter=5,
        id="review-005",
        characters=[{"name": "林黛玉", "actions": ["因宝钗到来而心中不忿"]}],
    )
    manifest_path, data_dir, static_dir = _write_minimal_app_context_files(tmp_path, [previous_card, current_card, later_card])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for number in (2, 3, 5):
        chapter_path = tmp_path / "book" / "chapters" / f"{number:03d}-test.txt"
        chapter_path.write_text(f"第{number}回 原文", encoding="utf-8")
        manifest["chapters"].append({"number": number, "title": f"第{number}回", "file_path": str(chapter_path)})
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")

    class LiveClientShouldNotBeUsed:
        def __init__(self):
            self.search_calls = 0
            self.graph_calls = 0
            self.query_calls = 0

        def search_labels(self, q: str, limit: int = 10):
            self.search_calls += 1
            return []

        def graph(self, label: str, max_depth: int = 3, max_nodes: int = 1000):
            self.graph_calls += 1
            return {"nodes": [], "edges": []}

        def query_data(self, query: str, mode: str = "hybrid", **options):
            self.query_calls += 1
            return {}

    client = LiveClientShouldNotBeUsed()
    context = create_app_context(
        manifest_path=manifest_path,
        data_dir=data_dir,
        static_dir=static_dir,
        retrieval_client=client,
    )

    status, payload = handle_api_request(context, "GET", "/api/entity-trace?name=%E6%9E%97%E9%BB%9B%E7%8E%89&chapter=3&type=person")

    assert status == 200
    assert [item["chapter"] for item in payload["traceItems"]] == [2, 5]
    assert payload["traceItems"][0]["label"] == "第2回：随雨村读书"
    assert payload["traceItems"][1]["label"] == "第5回：因宝钗到来而心中不忿"
    assert client.search_calls == 0
    assert client.graph_calls == 0
    assert client.query_calls == 0


def test_api_entity_trace_short_person_alias_does_not_match_embedded_object_name(tmp_path):
    first_card = _review_card(
        chapter=1,
        id="review-001",
        objects=[{"name": "通灵宝玉", "meaning": "神话物件"}],
        plot_chain=["女娲补天遗石后来化为通灵宝玉"],
    )
    current_card = _review_card(
        chapter=3,
        id="review-003",
        characters=[{"name": "贾宝玉", "actions": ["与黛玉初会"]}],
    )
    second_card = _review_card(
        chapter=2,
        id="review-002",
        characters=[{"name": "贾宝玉", "actions": ["衔玉而生"]}],
    )
    manifest_path, data_dir, static_dir = _write_minimal_app_context_files(tmp_path, [first_card, second_card, current_card])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for number in (2, 3):
        chapter_path = tmp_path / "book" / "chapters" / f"{number:03d}-test.txt"
        chapter_path.write_text(f"第{number}回 原文", encoding="utf-8")
        manifest["chapters"].append({"number": number, "title": f"第{number}回", "file_path": str(chapter_path)})
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    context = create_app_context(manifest_path=manifest_path, data_dir=data_dir, static_dir=static_dir)

    status, payload = handle_api_request(context, "GET", "/api/entity-trace?name=%E8%B4%BE%E5%AE%9D%E7%8E%89&chapter=3&type=person")

    assert status == 200
    assert [item["chapter"] for item in payload["traceItems"]] == [2]
    assert payload["traceItems"][0]["label"] == "第2回：衔玉而生"
    assert "通灵宝玉" not in str(payload)


def test_api_entity_trace_ui_person_ignores_empty_stale_cache(tmp_path):
    current_card = _review_card(
        chapter=3,
        id="review-003",
        characters=[{"name": "林黛玉", "actions": ["与宝玉初会"]}],
    )
    previous_card = _review_card(
        chapter=2,
        id="review-002",
        characters=[{"name": "林黛玉", "actions": ["随雨村读书"]}],
    )
    later_card = _review_card(
        chapter=5,
        id="review-005",
        characters=[{"name": "林黛玉", "actions": ["因宝钗到来而心中不忿"]}],
    )
    manifest_path, data_dir, static_dir = _write_minimal_app_context_files(tmp_path, [previous_card, current_card, later_card])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for number in (2, 3, 5):
        chapter_path = tmp_path / "book" / "chapters" / f"{number:03d}-test.txt"
        chapter_path.write_text(f"第{number}回 原文", encoding="utf-8")
        manifest["chapters"].append({"number": number, "title": f"第{number}回", "file_path": str(chapter_path)})
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    context = create_app_context(manifest_path=manifest_path, data_dir=data_dir, static_dir=static_dir)

    class StoreWithStaleTraceCache:
        common_entries = []

        def __init__(self, wrapped_store):
            self.wrapped_store = wrapped_store

        def __getattr__(self, name):
            return getattr(self.wrapped_store, name)

        def entity_trace_payload(self, name: str, current_chapter: int | None):
            return {
                "trace_items": [],
                "theme_extensions": [
                    {
                        "topic": "林姑娘",
                        "description": "人物别名：林姑娘是林黛玉的称呼。",
                        "chapter_jumps": [{"chapter": 8, "label": "第8回：林姑娘"}],
                    }
                ],
            }

    object.__setattr__(context, "store", StoreWithStaleTraceCache(context.store))

    status, payload = handle_api_request(context, "GET", "/api/entity-trace?name=%E6%9E%97%E9%BB%9B%E7%8E%89&chapter=3&type=person")

    assert status == 200
    assert [item["chapter"] for item in payload["traceItems"]] == [2, 5]
    assert payload["themeExtensions"] == []
    assert "林姑娘" not in str(payload)


def test_api_entity_trace_uses_bulk_review_card_scan_when_available(tmp_path):
    current_card = _review_card(
        chapter=3,
        id="review-003",
        characters=[{"name": "林黛玉", "actions": ["与宝玉初会"]}],
    )
    later_card = _review_card(
        chapter=5,
        id="review-005",
        characters=[{"name": "林黛玉", "actions": ["因宝钗到来而心中不忿"]}],
    )
    manifest_path, data_dir, static_dir = _write_minimal_app_context_files(tmp_path, [current_card, later_card])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for number in (3, 5):
        chapter_path = tmp_path / "book" / "chapters" / f"{number:03d}-test.txt"
        chapter_path.write_text(f"第{number}回 原文", encoding="utf-8")
        manifest["chapters"].append({"number": number, "title": f"第{number}回", "file_path": str(chapter_path)})
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    context = create_app_context(manifest_path=manifest_path, data_dir=data_dir, static_dir=static_dir)
    cards = [context.store.maybe_review_card_for_chapter(3), context.store.maybe_review_card_for_chapter(5)]

    class BulkOnlyStore:
        common_entries = []

        def __init__(self, cards):
            self.cards = cards
            self.bulk_calls = 0

        def entity_trace_payload(self, name: str, current_chapter: int | None):
            return None

        def review_cards_for_trace_scan(self):
            self.bulk_calls += 1
            return list(self.cards)

        def maybe_review_card_for_chapter(self, number: int):
            raise AssertionError("trace scan should use the bulk review-card API")

    store = BulkOnlyStore(cards)
    object.__setattr__(context, "store", store)

    status, payload = handle_api_request(context, "GET", "/api/entity-trace?name=%E6%9E%97%E9%BB%9B%E7%8E%89&chapter=3&type=person")

    assert status == 200
    assert [item["chapter"] for item in payload["traceItems"]] == [5]
    assert store.bulk_calls == 1


def test_api_entity_trace_skips_live_retrieval_for_non_person_empty_ui_card(tmp_path):
    manifest_path, data_dir, static_dir = _write_minimal_app_context_files(tmp_path, [_review_card()])

    class LiveClientShouldNotBeUsed:
        def __init__(self):
            self.graph_calls = 0
            self.query_calls = 0

        def search_labels(self, q: str, limit: int = 10):
            raise AssertionError("empty UI cards should not search live labels")

        def graph(self, label: str, max_depth: int = 3, max_nodes: int = 1000):
            self.graph_calls += 1
            return {"nodes": [], "edges": []}

        def query_data(self, query: str, mode: str = "hybrid", **options):
            self.query_calls += 1
            return {}

    client = LiveClientShouldNotBeUsed()
    context = create_app_context(
        manifest_path=manifest_path,
        data_dir=data_dir,
        static_dir=static_dir,
        retrieval_client=client,
    )

    status, payload = handle_api_request(
        context,
        "GET",
        "/api/entity-trace?name=%E8%8D%A3%E7%A6%A7%E5%A0%82%E5%AF%B9%E8%81%94&chapter=3&type=literary_text",
    )

    assert status == 200
    assert payload == {"traceItems": [], "themeExtensions": []}
    assert client.graph_calls == 0
    assert client.query_calls == 0


def test_api_entity_trace_non_person_ui_card_skips_stale_store_cache(tmp_path):
    manifest_path, data_dir, static_dir = _write_minimal_app_context_files(tmp_path, [_review_card()])
    context = create_app_context(manifest_path=manifest_path, data_dir=data_dir, static_dir=static_dir)

    class StoreWithStaleTraceCache:
        common_entries = []

        def __init__(self, wrapped_store):
            self.wrapped_store = wrapped_store
            self.cache_calls = 0

        def __getattr__(self, name):
            return getattr(self.wrapped_store, name)

        def entity_trace_payload(self, name: str, current_chapter: int | None):
            self.cache_calls += 1
            return {
                "trace_items": [
                    {
                        "chapter": 4,
                        "label": "第4回：旧缓存噪声",
                        "topic": "旧缓存噪声",
                        "description": "这段旧缓存不应该进入非人物 UI 卡片。",
                        "importance": 90,
                    }
                ],
                "theme_extensions": [
                    {
                        "topic": "旧主题",
                        "description": "旧主题不应该进入非人物 UI 卡片。",
                    }
                ],
            }

    store = StoreWithStaleTraceCache(context.store)
    object.__setattr__(context, "store", store)

    status, payload = handle_api_request(
        context,
        "GET",
        "/api/entity-trace?name=%E8%8D%A3%E7%A6%A7%E5%A0%82%E5%AF%B9%E8%81%94&chapter=3&type=literary_text",
    )

    assert status == 200
    assert payload == {"traceItems": [], "themeExtensions": []}
    assert store.cache_calls == 0


class FakeCachedEntityTraceStore:
    common_entries = []

    def __init__(self, wrapped_store=None):
        self.wrapped_store = wrapped_store

    def __getattr__(self, name):
        if self.wrapped_store is None:
            raise AttributeError(name)
        return getattr(self.wrapped_store, name)

    def entity_trace_payload(self, name: str, current_chapter: int | None):
        assert name == "贾雨村"
        assert current_chapter == 1
        return {
            "trace_items": [
                {
                    "chapter": 2,
                    "label": "第2回：贾雨村复职",
                    "topic": "贾雨村复职",
                    "description": "贾雨村在第二回交代革职与复起。",
                    "importance": 90,
                }
            ],
            "theme_extensions": [
                {
                    "topic": "官场线索",
                    "description": "贾雨村线索映照官场升沉。",
                    "previous_chapter_jumps": [{"chapter": 1, "label": "第1回：甄士隐资助贾雨村"}],
                    "chapter_jumps": [{"chapter": 4, "label": "第4回：葫芦案"}],
                }
            ],
        }


class FakeEmptyCachedEntityTraceStore:
    def __init__(self, wrapped_store):
        self.wrapped_store = wrapped_store
        self.common_entries = wrapped_store.common_entries

    def __getattr__(self, name):
        return getattr(self.wrapped_store, name)

    def entity_trace_payload(self, name: str, current_chapter: int | None):
        assert name == "贾雨村"
        return {"trace_items": [], "theme_extensions": []}


class FakeCacheOnlyChapterJumpStore:
    def __init__(self, current_card, later_card, wrapped_store=None):
        self.current_card = current_card
        self.later_card = later_card
        self.wrapped_store = wrapped_store
        self.common_entries = getattr(wrapped_store, "common_entries", [])
        self.looked_up_chapters = []

    def __getattr__(self, name):
        if self.wrapped_store is None:
            raise AttributeError(name)
        return getattr(self.wrapped_store, name)

    def maybe_review_card_for_chapter(self, number: int):
        self.looked_up_chapters.append(number)
        if number == 1:
            return self.wrapped_store.maybe_review_card_for_chapter(number) if self.wrapped_store is not None else self.current_card
        if number == 2:
            if self.wrapped_store is not None:
                raise AssertionError("chapter endpoint should not scan later chapters")
            return self.later_card
        return None

    def entity_trace_payload(self, name: str, current_chapter: int | None):
        return {"trace_items": [], "theme_extensions": []}


class FakeNoCachedEntityTraceStore(FakeCacheOnlyChapterJumpStore):
    def entity_trace_payload(self, name: str, current_chapter: int | None):
        return None


class CountingChapterStore:
    def __init__(self, wrapped_store):
        self.wrapped_store = wrapped_store
        self.common_entries = wrapped_store.common_entries
        self.chapter_text_calls = 0
        self.review_card_calls = 0

    def __getattr__(self, name):
        return getattr(self.wrapped_store, name)

    def chapter_text(self, number: int):
        self.chapter_text_calls += 1
        return self.wrapped_store.chapter_text(number)

    def maybe_review_card_for_chapter(self, number: int):
        self.review_card_calls += 1
        return self.wrapped_store.maybe_review_card_for_chapter(number)


class FailingLiveTraceClient:
    def search_labels(self, q: str, limit: int = 10):
        raise AssertionError("cached entity trace should not call live search")

    def graph(self, label: str, max_depth: int = 3, max_nodes: int = 1000):
        raise AssertionError("cached entity trace should not call live graph")

    def query_data(self, query: str, mode: str = "hybrid", **options):
        raise AssertionError("cached entity trace should not call live query")


def test_api_entity_trace_uses_store_cache_before_live_retrieval():
    context = create_app_context(
        manifest_path=Path("book/chapters_manifest.json"),
        data_dir=Path("data/app"),
        static_dir=Path("static"),
        retrieval_client=FailingLiveTraceClient(),
    )
    context = context.__class__(
        store=FakeCachedEntityTraceStore(),
        ask_engine=context.ask_engine,
        static_dir=context.static_dir,
        retrieval_client=context.retrieval_client,
    )

    status, payload = handle_api_request(context, "GET", "/api/entity-trace?name=%E8%B4%BE%E9%9B%A8%E6%9D%91&chapter=1")

    assert status == 200
    assert payload["traceItems"][0]["chapter"] == 2
    assert payload["themeExtensions"][0]["topic"] == "官场线索"


def test_api_chapter_prefetches_empty_entity_trace_to_skip_live_click_lookup(tmp_path):
    review_card = _review_card(characters=[{"name": "贾雨村", "actions": ["接受资助"]}])
    manifest_path, data_dir, static_dir = _write_minimal_app_context_files(tmp_path, [review_card])
    chapter_path = tmp_path / "book" / "chapters" / "001-第一回-甄士隐梦幻识通灵 贾雨村风尘怀闺秀.txt"
    chapter_path.write_text("贾雨村接受资助。", encoding="utf-8")
    base_context = create_app_context(manifest_path=manifest_path, data_dir=data_dir, static_dir=static_dir)
    context = base_context.__class__(
        store=FakeEmptyCachedEntityTraceStore(base_context.store),
        ask_engine=base_context.ask_engine,
        static_dir=base_context.static_dir,
        retrieval_client=None,
    )

    status, payload = handle_api_request(context, "GET", "/api/chapters/1")

    assert status == 200
    assert payload["inlineEntities"][0]["tracePrefetched"] is True
    assert payload["inlineEntities"][0]["chapterJumps"] == []
    assert payload["inlineEntities"][0]["themeExtensions"] == []


def test_api_chapter_prefetches_entity_trace_cache_in_bulk(tmp_path):
    review_card = _review_card(
        characters=[{"name": "贾雨村", "actions": ["接受资助"]}],
        places=[{"name": "大荒山无稽崖青埂峰", "function": "神话开端地点"}],
    )
    manifest_path, data_dir, static_dir = _write_minimal_app_context_files(tmp_path, [review_card])
    chapter_path = tmp_path / "book" / "chapters" / "001-第一回-甄士隐梦幻识通灵 贾雨村风尘怀闺秀.txt"
    chapter_path.write_text("贾雨村在大荒山无稽崖青埂峰故事中出现。", encoding="utf-8")
    base_context = create_app_context(manifest_path=manifest_path, data_dir=data_dir, static_dir=static_dir)

    class BulkTraceCacheStore:
        def __init__(self, wrapped_store):
            self.wrapped_store = wrapped_store
            self.common_entries = wrapped_store.common_entries
            self.bulk_calls = 0

        def __getattr__(self, name):
            return getattr(self.wrapped_store, name)

        def entity_trace_payloads_for_chapter(self, current_chapter: int | None):
            self.bulk_calls += 1
            assert current_chapter == 1
            return {
                "贾雨村": {
                    "trace_items": [{"chapter": 2, "label": "第2回：贾雨村复职"}],
                    "theme_extensions": [],
                },
                "大荒山无稽崖青埂峰": {"trace_items": [], "theme_extensions": []},
            }

        def entity_trace_payload(self, name: str, current_chapter: int | None):
            raise AssertionError("chapter endpoint should use bulk entity trace cache")

    store = BulkTraceCacheStore(base_context.store)
    context = base_context.__class__(
        store=store,
        ask_engine=base_context.ask_engine,
        static_dir=base_context.static_dir,
        retrieval_client=None,
    )

    status, payload = handle_api_request(context, "GET", "/api/chapters/1")

    assert status == 200
    assert store.bulk_calls == 1
    entities = {entity["name"]: entity for entity in payload["inlineEntities"]}
    assert entities["贾雨村"]["tracePrefetched"] is True
    assert entities["贾雨村"]["chapterJumps"][0]["label"] == "第2回：贾雨村复职"
    assert entities["大荒山无稽崖青埂峰"]["tracePrefetched"] is True
    assert entities["大荒山无稽崖青埂峰"]["chapterJumps"] == []


def test_api_chapter_prefetched_trace_replaces_static_broad_chapter_jumps(tmp_path):
    review_card = _review_card(
        characters=[{"name": "林黛玉", "actions": ["与宝玉初会"]}],
        later_associations=[
            {
                "topic": "林黛玉",
                "description": "林黛玉是全书核心人物的泛化介绍。",
                "source_chapters": [4],
            }
        ],
    )
    manifest_path, data_dir, static_dir = _write_minimal_app_context_files(tmp_path, [review_card])
    chapter_path = tmp_path / "book" / "chapters" / "001-第一回-甄士隐梦幻识通灵 贾雨村风尘怀闺秀.txt"
    chapter_path.write_text("林黛玉与宝玉初会。", encoding="utf-8")
    base_context = create_app_context(manifest_path=manifest_path, data_dir=data_dir, static_dir=static_dir)

    class SpecificTraceCacheStore:
        def __init__(self, wrapped_store):
            self.wrapped_store = wrapped_store
            self.common_entries = wrapped_store.common_entries

        def __getattr__(self, name):
            return getattr(self.wrapped_store, name)

        def entity_trace_payloads_for_chapter(self, current_chapter: int | None):
            return {
                "林黛玉": {
                    "trace_items": [
                        {
                            "chapter": 4,
                            "label": "第4回：黛玉见王夫人计议家务",
                            "description": "黛玉见王夫人计议家务，引出薛家人命官司",
                            "importance": 85,
                        }
                    ],
                    "theme_extensions": [],
                }
            }

    context = base_context.__class__(
        store=SpecificTraceCacheStore(base_context.store),
        ask_engine=base_context.ask_engine,
        static_dir=base_context.static_dir,
        retrieval_client=None,
    )

    status, payload = handle_api_request(context, "GET", "/api/chapters/1")

    assert status == 200
    entity = payload["inlineEntities"][0]
    assert entity["tracePrefetched"] is True
    assert entity["laterClues"] == [
        {
            "topic": "林黛玉",
            "description": "林黛玉是全书核心人物的泛化介绍。",
            "evidence": "林黛玉是全书核心人物的泛化介绍。",
        },
        {
            "topic": "第4回：黛玉见王夫人计议家务",
            "description": "黛玉见王夫人计议家务，引出薛家人命官司",
            "evidence": "黛玉见王夫人计议家务，引出薛家人命官司",
        }
    ]
    assert entity["chapterJumps"] == [
        {
            "chapter": 4,
            "label": "第4回：黛玉见王夫人计议家务",
            "description": "黛玉见王夫人计议家务，引出薛家人命官司",
            "importance": 85,
        }
    ]


def test_api_chapter_enriches_relation_endpoint_from_graph_cache(tmp_path):
    review_card = _review_card(
        relationships=[
            {
                "source": "顽石",
                "type": "被僧道携入红尘",
                "target": "一僧一道",
                "description": "女娲补天遗石经一僧一道缩小镌字后带入红尘经历",
            }
        ]
    )
    manifest_path, data_dir, static_dir = _write_minimal_app_context_files(tmp_path, [review_card])
    chapter_path = tmp_path / "book" / "chapters" / "001-第一回-甄士隐梦幻识通灵 贾雨村风尘怀闺秀.txt"
    chapter_path.write_text("顽石被僧道携入红尘。", encoding="utf-8")
    base_context = create_app_context(manifest_path=manifest_path, data_dir=data_dir, static_dir=static_dir)

    class GraphCacheStore:
        def __init__(self, wrapped_store):
            self.wrapped_store = wrapped_store
            self.common_entries = wrapped_store.common_entries

        def __getattr__(self, name):
            return getattr(self.wrapped_store, name)

        def entity_trace_payloads_for_chapter(self, current_chapter: int | None):
            return {"顽石": {"trace_items": [], "theme_extensions": []}}

        def entity_graph_payloads_for_names(self, names):
            return {
                "顽石": {
                    "description": "无才补天被弃于青埂峰下的石头，后幻形入世，是小说的核心线索。",
                    "neighbors": [
                        {"name": "通灵宝玉", "relationship": "前世本体"},
                        {"name": "女娲", "relationship": "补天遗石"},
                    ],
                    "extended_neighbors": [
                        {
                            "from": "顽石",
                            "via": "王熙凤",
                            "to": "凤姐",
                            "relationship": "人物俗称,人物别名,人物称呼,指代关系",
                            "description": "凤姐是《红楼梦》中王熙凤最为普遍且稳固的俗称、昵称与别名。",
                            "path": ["顽石", "王熙凤", "凤姐"],
                            "depth": 2,
                            "weight": 0.99,
                        },
                        {
                            "from": "顽石",
                            "via": "通灵宝玉",
                            "to": "贾宝玉",
                            "relationship": "随身物象",
                            "description": "通灵宝玉随贾宝玉入世。",
                            "path": ["顽石", "通灵宝玉", "贾宝玉"],
                            "depth": 2,
                            "weight": 0.95,
                        }
                    ],
                }
            }

    context = base_context.__class__(
        store=GraphCacheStore(base_context.store),
        ask_engine=base_context.ask_engine,
        static_dir=base_context.static_dir,
        retrieval_client=None,
    )

    status, payload = handle_api_request(context, "GET", "/api/chapters/1")

    assert status == 200
    entity = payload["inlineEntities"][0]
    assert entity["name"] == "顽石"
    assert entity["summary"] == "无才补天被弃于青埂峰下的石头，后幻形入世，是小说的核心线索。"
    assert "无才补天被弃于青埂峰下的石头" in entity["details"]
    assert {
        "source": "顽石",
        "type": "前世本体",
        "target": "通灵宝玉",
        "description": "通灵宝玉",
    } in entity["relations"]
    assert entity["extendedNeighbors"] == [
        {
            "from": "顽石",
            "via": "通灵宝玉",
            "to": "贾宝玉",
            "relationship": "随身物象",
            "description": "通灵宝玉随贾宝玉入世。",
            "path": ["顽石", "通灵宝玉", "贾宝玉"],
            "depth": 2,
            "weight": 0.95,
        }
    ]


def test_api_entity_trace_flattens_prefetched_theme_chapter_jumps_into_popover_sections(tmp_path):
    review_card = _review_card(characters=[{"name": "贾雨村", "actions": ["接受资助"]}])
    manifest_path, data_dir, static_dir = _write_minimal_app_context_files(tmp_path, [review_card])
    chapter_path = tmp_path / "book" / "chapters" / "001-第一回-甄士隐梦幻识通灵 贾雨村风尘怀闺秀.txt"
    chapter_path.write_text("贾雨村接受资助。", encoding="utf-8")
    base_context = create_app_context(manifest_path=manifest_path, data_dir=data_dir, static_dir=static_dir)
    context = base_context.__class__(
        store=FakeCachedEntityTraceStore(base_context.store),
        ask_engine=base_context.ask_engine,
        static_dir=base_context.static_dir,
        retrieval_client=None,
    )

    status, payload = handle_api_request(context, "GET", "/api/entity-trace?name=%E8%B4%BE%E9%9B%A8%E6%9D%91&chapter=1")

    assert status == 200
    assert [jump["chapter"] for jump in payload["traceItems"]] == [2]
    assert payload["themeExtensions"][0]["previousChapterJumps"][0]["chapter"] == 1


def test_prefetched_entity_trace_skips_generated_full_book_scan():
    current_card = _review_card(characters=[{"name": "贾雨村", "actions": ["接受资助"]}])
    later_card = _review_card(id="review-002", chapter=2, characters=[{"name": "贾雨村", "actions": ["复职"]}])
    store = FakeCacheOnlyChapterJumpStore(current_card, later_card)
    inline_entities = [{"name": "贾雨村", "chapterJumps": [], "themeExtensions": []}]

    from hlm_kg.web_app import _attach_generated_chapter_jumps

    _attach_generated_chapter_jumps(inline_entities, store=store, current_chapter=1)

    assert store.looked_up_chapters == []
    assert inline_entities[0]["tracePrefetched"] is True
    assert inline_entities[0]["chapterJumps"] == []


def test_empty_prefetched_entity_trace_keeps_existing_chapter_jumps():
    current_card = _review_card(
        later_associations=[
            {
                "topic": "贾雨村",
                "description": "贾雨村后文起复为官并徇私判案。",
                "source_chapters": [2],
            }
        ]
    )
    store = FakeCacheOnlyChapterJumpStore(current_card, _review_card(id="review-002", chapter=2))
    inline_entities = [
        {
            "name": "贾雨村中秋对月寓怀绝句",
            "chapterJumps": [
                {
                    "chapter": 2,
                    "label": "第2回：贾雨村",
                    "description": "贾雨村后文起复为官并徇私判案。",
                    "importance": 90,
                }
            ],
            "laterChapterJumps": [
                {
                    "chapter": 2,
                    "label": "第2回：贾雨村",
                    "description": "贾雨村后文起复为官并徇私判案。",
                    "importance": 90,
                }
            ],
            "themeExtensions": [],
        }
    ]
    store.payloads = {"贾雨村中秋对月寓怀绝句": {"trace_items": [], "theme_extensions": []}}

    from hlm_kg.web_app import _attach_generated_chapter_jumps

    _attach_generated_chapter_jumps(inline_entities, store=store, current_chapter=1)

    assert inline_entities[0]["tracePrefetched"] is True
    assert inline_entities[0]["laterChapterJumps"] == [
        {
            "chapter": 2,
            "label": "第2回：贾雨村",
            "description": "贾雨村后文起复为官并徇私判案。",
            "importance": 90,
        }
    ]


def test_foreshadowing_literary_text_reuses_anchor_entity_prefetched_trace(tmp_path):
    review_card = _review_card(
        characters=[{"name": "贾雨村", "actions": ["中秋对月吟诗"]}],
        literary_texts=[
            {
                "title": "贾雨村中秋对月寓怀绝句",
                "short_quote": "时逢三五便团圆，满把清光护玉栏。",
                "explanation": "写贾雨村借月抒怀。",
                "function": "展现贾雨村的抱负与野心，也为后文发迹埋下伏笔",
            }
        ],
        later_associations=[
            {
                "topic": "贾雨村",
                "description": "贾雨村泛化人物介绍。",
                "source_chapters": [2],
            }
        ],
    )
    manifest_path, data_dir, static_dir = _write_minimal_app_context_files(tmp_path, [review_card])
    base_context = create_app_context(manifest_path=manifest_path, data_dir=data_dir, static_dir=static_dir)

    class AnchorTraceCacheStore:
        common_entries = []

        def __init__(self, wrapped_store):
            self.wrapped_store = wrapped_store
            self.common_entries = wrapped_store.common_entries

        def __getattr__(self, name):
            return getattr(self.wrapped_store, name)

        def entity_trace_payloads_for_chapter(self, current_chapter: int | None):
            return {
                "贾雨村中秋对月寓怀绝句": {
                    "trace_items": [],
                    "theme_extensions": [],
                },
                "贾雨村": {
                    "trace_items": [
                        {
                            "chapter": 2,
                            "label": "第2回：寻访甄士隐旧交",
                            "description": "寻访甄士隐旧交；纳娇杏为二房；任黛玉西席",
                            "importance": 85,
                        }
                    ],
                    "theme_extensions": [],
                }
            }

    context = base_context.__class__(
        store=AnchorTraceCacheStore(base_context.store),
        ask_engine=base_context.ask_engine,
        static_dir=base_context.static_dir,
        retrieval_client=None,
    )

    status, payload = handle_api_request(context, "GET", "/api/chapters/1")

    assert status == 200
    entity = next(item for item in payload["inlineEntities"] if item["name"] == "贾雨村中秋对月寓怀绝句")
    assert entity["tracePrefetched"] is True
    assert entity["chapterJumps"] == [
        {
            "chapter": 2,
            "label": "第2回：寻访甄士隐旧交",
            "description": "寻访甄士隐旧交；纳娇杏为二房；任黛玉西席",
            "importance": 85,
        }
    ]


def test_entity_with_future_alias_reuses_related_entity_prefetched_trace_when_trace_mentions_alias(tmp_path):
    review_card = _review_card(
        characters=[
            {
                "name": "贾雨村",
                "actions": ["见甄家丫鬟回头，误以为知己"],
            },
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
    manifest_path, data_dir, static_dir = _write_minimal_app_context_files(tmp_path, [review_card])
    base_context = create_app_context(manifest_path=manifest_path, data_dir=data_dir, static_dir=static_dir)

    class RelatedTraceCacheStore:
        def __init__(self, wrapped_store):
            self.wrapped_store = wrapped_store
            self.common_entries = wrapped_store.common_entries

        def __getattr__(self, name):
            return getattr(self.wrapped_store, name)

        def entity_trace_payloads_for_chapter(self, current_chapter: int | None):
            return {
                "甄家丫鬟（娇杏）": {"trace_items": [], "theme_extensions": []},
                "贾雨村": {
                    "trace_items": [
                        {
                            "chapter": 2,
                            "label": "第2回：寻访甄士隐旧交",
                            "description": "寻访甄士隐旧交；纳娇杏为二房；任黛玉西席",
                            "importance": 85,
                        }
                    ],
                    "theme_extensions": [],
                },
            }

    context = base_context.__class__(
        store=RelatedTraceCacheStore(base_context.store),
        ask_engine=base_context.ask_engine,
        static_dir=base_context.static_dir,
        retrieval_client=None,
    )

    status, payload = handle_api_request(context, "GET", "/api/chapters/1")

    assert status == 200
    assert [item["name"] for item in payload["inlineEntities"]].count("甄家丫鬟") == 0
    entity = next(item for item in payload["inlineEntities"] if item["name"] == "甄家丫鬟（娇杏）")
    assert entity["relations"] == [
        {
            "source": "贾雨村",
            "type": "自作多情",
            "target": "甄家丫鬟",
            "description": "贾雨村见甄家丫鬟回头两次，误以为其有意于己。",
            "evidence": None,
        }
    ]
    assert entity["tracePrefetched"] is True
    assert entity["laterClues"] == [
        {
            "topic": "第2回：寻访甄士隐旧交",
            "description": "寻访甄士隐旧交；纳娇杏为二房；任黛玉西席",
            "evidence": "寻访甄士隐旧交；纳娇杏为二房；任黛玉西席",
        }
    ]
    assert entity["chapterJumps"] == [
        {
            "chapter": 2,
            "label": "第2回：寻访甄士隐旧交",
            "description": "寻访甄士隐旧交；纳娇杏为二房；任黛玉西席",
            "importance": 85,
        }
    ]


def test_api_chapter_does_not_scan_all_chapters_for_entity_jumps(tmp_path):
    review_card = _review_card(characters=[{"name": "贾雨村", "actions": ["接受资助"]}])
    later_card = _review_card(id="review-002", chapter=2, characters=[{"name": "贾雨村", "actions": ["复职"]}])
    manifest_path, data_dir, static_dir = _write_minimal_app_context_files(tmp_path, [review_card])
    chapter_path = tmp_path / "book" / "chapters" / "001-第一回-甄士隐梦幻识通灵 贾雨村风尘怀闺秀.txt"
    chapter_path.write_text("贾雨村接受资助。", encoding="utf-8")
    base_context = create_app_context(manifest_path=manifest_path, data_dir=data_dir, static_dir=static_dir)
    context = base_context.__class__(
        store=FakeNoCachedEntityTraceStore(review_card, later_card, wrapped_store=base_context.store),
        ask_engine=base_context.ask_engine,
        static_dir=base_context.static_dir,
        retrieval_client=None,
    )

    status, payload = handle_api_request(context, "GET", "/api/chapters/1")

    assert status == 200
    assert payload["inlineEntities"][0]["chapterJumps"] == []
    assert context.store.looked_up_chapters == [1]


def test_api_chapter_response_is_cached_per_context(tmp_path):
    review_card = _review_card(characters=[{"name": "贾雨村", "actions": ["接受资助"]}])
    manifest_path, data_dir, static_dir = _write_minimal_app_context_files(tmp_path, [review_card])
    base_context = create_app_context(manifest_path=manifest_path, data_dir=data_dir, static_dir=static_dir)
    store = CountingChapterStore(base_context.store)
    context = base_context.__class__(
        store=store,
        ask_engine=base_context.ask_engine,
        static_dir=base_context.static_dir,
        retrieval_client=None,
    )

    first_status, first_payload = handle_api_request(context, "GET", "/api/chapters/1")
    second_status, second_payload = handle_api_request(context, "GET", "/api/chapters/1")

    assert first_status == 200
    assert second_status == 200
    assert second_payload == first_payload
    assert store.chapter_text_calls == 1
    assert store.review_card_calls == 1


class FakeEntityTraceClient:
    def search_labels(self, q: str, limit: int = 10):
        assert q == "贾雨村"
        return ["贾雨村", "贾雨村被参革职"]

    def query_data(self, query: str, mode: str = "hybrid", **options):
        assert "贾雨村" in query
        assert mode == "hybrid"
        assert options["enable_rerank"] is True
        return {
            "status": "success",
            "data": {
                "entities": [
                    {
                        "entity_name": "贾雨村被参革职",
                        "entity_type": "ChapterEpisode",
                        "description": "贾雨村后来因贪酷被参革职，是其仕途沉浮的重要节点。",
                        "file_path": "002-第二回-贾夫人仙逝扬州城 冷子兴演说荣国府.txt",
                        "source_id": "doc-002",
                    },
                    {
                        "entity_name": "林黛玉",
                        "entity_type": "Person",
                        "description": "无关人物。",
                        "file_path": "003-第三回-托内兄如海荐西宾 接外孙贾母惜孤女.txt",
                        "source_id": "doc-003",
                    },
                ],
                "relationships": [
                    {
                        "src_id": "贾宝玉",
                        "tgt_id": "贾雨村",
                        "keywords": "会面",
                        "description": "贾政令宝玉会见贾雨村，宝玉不喜仕途经济之谈。",
                        "file_path": "033-第三十三回-手足眈眈小动唇舌 不肖种种大承苔挞.txt",
                        "source_id": "doc-033",
                        "weight": 5.0,
                    },
                    {
                        "src_id": "林黛玉",
                        "tgt_id": "贾宝玉",
                        "keywords": "情感关系",
                        "description": "这条关系不应进入贾雨村线索。",
                        "file_path": "097-第九十七回-林黛玉焚稿断痴情 薛宝钗出闺成大礼.txt",
                        "source_id": "doc-097",
                        "weight": 99.0,
                    },
                ],
                "chunks": [],
                "references": [],
            },
            "metadata": {"query_mode": mode},
        }


def test_api_entity_trace_filters_to_direct_entity_evidence(tmp_path):
    manifest_path, data_dir, static_dir = _write_minimal_app_context_files(tmp_path, [_review_card()])
    context = create_app_context(
        manifest_path=manifest_path,
        data_dir=data_dir,
        static_dir=static_dir,
        retrieval_client=FakeEntityTraceClient(),
    )

    status, payload = handle_api_request(context, "GET", "/api/entity-trace?name=%E8%B4%BE%E9%9B%A8%E6%9D%91&chapter=1")

    assert status == 200
    assert [item["chapter"] for item in payload["traceItems"]] == [33, 2]
    assert "贾政令宝玉会见贾雨村" in payload["traceItems"][0]["description"]
    assert "被参革职" in payload["traceItems"][1]["topic"]
    assert "林黛玉" not in str(payload)
    assert "LightRAG" not in str(payload)


class FakeSingleChapterTraceClient:
    def search_labels(self, q: str, limit: int = 10):
        return [q]

    def query_data(self, query: str, mode: str = "hybrid", **options):
        return {
            "status": "success",
            "data": {
                "entities": [
                    {
                        "entity_name": "村肆偶遇",
                        "entity_type": "PlotAction",
                        "description": "贾雨村退出智通寺后，在村肆中偶遇冷子兴，引出后文演说荣国府。",
                        "file_path": "002-第二回-贾夫人仙逝扬州城 冷子兴演说荣国府.txt",
                        "source_id": "doc-002",
                    }
                ],
                "relationships": [
                    {
                        "src_id": "贾政",
                        "tgt_id": "贾雨村",
                        "keywords": "交游关系",
                        "description": "贾政与贾雨村的关系跨越多处章回，这类泛关系不能拆成每回事件。",
                        "file_path": (
                            "003-第三回-托内兄如海荐西宾 接外孙贾母惜孤女.txt<SEP>"
                            "004-第四回-薄命女偏逢簿命郎 葫芦僧判断葫芦案.txt"
                        ),
                        "source_id": "doc-003<SEP>doc-004",
                        "weight": 8.0,
                    }
                ],
                "chunks": [],
                "references": [],
            },
            "metadata": {"query_mode": mode},
        }


def test_api_entity_trace_prefers_single_chapter_events_over_broad_relationships(tmp_path):
    manifest_path, data_dir, static_dir = _write_minimal_app_context_files(tmp_path, [_review_card()])
    context = create_app_context(
        manifest_path=manifest_path,
        data_dir=data_dir,
        static_dir=static_dir,
        retrieval_client=FakeSingleChapterTraceClient(),
    )

    status, payload = handle_api_request(context, "GET", "/api/entity-trace?name=%E8%B4%BE%E9%9B%A8%E6%9D%91&chapter=1")

    assert status == 200
    assert len(payload["traceItems"]) == 1
    assert payload["traceItems"][0]["chapter"] == 2
    assert payload["traceItems"][0]["label"] == "第2回：村肆偶遇"
    assert payload["traceItems"][0]["topic"] == "村肆偶遇"
    assert payload["traceItems"][0]["description"] == "贾雨村退出智通寺后，在村肆中偶遇冷子兴，引出后文演说荣国府。"
    assert payload["traceItems"][0]["importance"] > 0


class FakeThemeExtensionClient:
    def search_labels(self, q: str, limit: int = 10):
        return ["好了歌", "好了歌注"]

    def query_data(self, query: str, mode: str = "hybrid", **options):
        return {
            "status": "success",
            "data": {
                "entities": [
                    {
                        "entity_name": "看破红尘",
                        "entity_type": "ThemeConcept",
                        "description": (
                            "看破红尘主题直接关联《好了歌》，甄士隐听闻后悟彻，"
                            "贾宝玉后文也在和尚点化下认清红尘虚幻。"
                        ),
                        "file_path": (
                            "001-第一回-甄士隐梦幻识通灵 贾雨村风尘怀闺秀.txt<SEP>"
                            "117-第一百十七回-阻超凡佳人双护玉 欣聚党恶子独承家.txt<SEP>"
                            "118-第一百十八回-记微嫌舅兄欺弱女 惊谜语妻妾谏痴人.txt"
                        ),
                        "source_id": "doc-001<SEP>doc-117<SEP>doc-118",
                    },
                    {
                        "entity_name": "好了歌",
                        "entity_type": "LiteraryText",
                        "description": "跛足道人所唱，直接出现于第一回。",
                        "file_path": "001-第一回-甄士隐梦幻识通灵 贾雨村风尘怀闺秀.txt",
                        "source_id": "doc-001",
                    },
                ],
                "relationships": [],
                "chunks": [],
                "references": [],
            },
            "metadata": {"query_mode": mode},
        }


def test_api_entity_trace_returns_theme_extensions_separate_from_direct_chapter_traces():
    context = create_app_context(
        manifest_path=Path("book/chapters_manifest.json"),
        data_dir=Path("data/app"),
        static_dir=Path("static"),
        retrieval_client=FakeThemeExtensionClient(),
    )

    status, payload = handle_api_request(context, "GET", "/api/entity-trace?name=%E5%A5%BD%E4%BA%86%E6%AD%8C&chapter=1")

    assert status == 200
    assert payload["traceItems"] == []
    assert payload["themeExtensions"] == [
        {
            "topic": "看破红尘",
            "description": (
                "看破红尘主题直接关联《好了歌》，甄士隐听闻后悟彻，"
                "贾宝玉后文也在和尚点化下认清红尘虚幻。"
            ),
            "chapterJumps": [
                {"chapter": 117, "label": "第117回：看破红尘"},
                {"chapter": 118, "label": "第118回：看破红尘"},
            ],
        }
    ]


class FakeGraphTraceClient:
    def search_labels(self, q: str, limit: int = 10):
        return ["好了歌", "好了歌注"]

    def graph(self, label: str, max_depth: int = 3, max_nodes: int = 1000):
        assert label == "好了歌"
        assert max_depth == 3
        assert max_nodes == 1000
        return {
            "nodes": [
                {
                    "id": "好了歌",
                    "properties": {
                        "entity_type": "literarytext",
                        "description": (
                            "跛足道人所唱的言词。<SEP>"
                            "以“好”与“了”的辩证关系点化世人。"
                        ),
                        "file_path": "001-第一回-甄士隐梦幻识通灵 贾雨村风尘怀闺秀.txt",
                    },
                },
                {
                    "id": "看破红尘",
                    "properties": {
                        "entity_type": "themeconcept",
                        "description": (
                            "甄士隐听闻《好了歌》后心中悟彻。<SEP>"
                            "贾宝玉在和尚点化下，认清红尘虚幻，决定将通灵宝玉归还。"
                        ),
                        "file_path": (
                            "001-第一回-甄士隐梦幻识通灵 贾雨村风尘怀闺秀.txt<SEP>"
                            "117-第一百十七回-阻超凡佳人双护玉 欣聚党恶子独承家.txt"
                        ),
                    },
                },
                {
                    "id": "石头记",
                    "properties": {
                        "entity_type": "literarytext",
                        "description": "《红楼梦》的本名。<SEP>空空道人从石上抄录的奇文。",
                        "file_path": (
                            "001-第一回-甄士隐梦幻识通灵 贾雨村风尘怀闺秀.txt<SEP>"
                            "120-第一百二十回-甄士隐详说太虚情 贾雨村归结红楼梦.txt"
                        ),
                    },
                },
                {
                    "id": "跛足道人",
                    "properties": {
                        "entity_type": "person",
                        "description": (
                            "跛足道人是《红楼梦》中的神秘道士，常与癞头和尚结伴度化世人。<SEP>"
                            "跛足道人在第十二回将风月宝鉴交给贾瑞。"
                        ),
                        "file_path": (
                            "001-第一回-甄士隐梦幻识通灵 贾雨村风尘怀闺秀.txt<SEP>"
                            "012-第十二回-王熙凤毒设相思局 贾天祥正照风月鉴.txt"
                        ),
                    },
                },
            ],
            "edges": [
                {
                    "source": "好了歌",
                    "target": "跛足道人",
                    "properties": {
                        "weight": 2.0,
                        "keywords": "创作演唱",
                        "description": "跛足道人在街前为落魄的甄士隐吟唱《好了歌》。",
                        "file_path": "001-第一回-甄士隐梦幻识通灵 贾雨村风尘怀闺秀.txt",
                    },
                },
                {
                    "source": "跛足道人",
                    "target": "风月宝鉴",
                    "properties": {
                        "weight": 2.0,
                        "keywords": "赠予物件",
                        "description": "跛足道人将风月宝鉴交给贾瑞，并叮嘱其只能照背面。",
                        "file_path": "012-第十二回-王熙凤毒设相思局 贾天祥正照风月鉴.txt",
                    },
                },
                {
                    "source": "好了歌",
                    "target": "看破红尘",
                    "properties": {
                        "weight": 3.0,
                        "keywords": "主题表达",
                        "description": (
                            "甄士隐听《好了歌》后悟彻“好便是了”。<SEP>"
                            "贾宝玉在和尚点化下，把红尘看破，最终决定还玉。"
                        ),
                        "file_path": (
                            "001-第一回-甄士隐梦幻识通灵 贾雨村风尘怀闺秀.txt<SEP>"
                            "117-第一百十七回-阻超凡佳人双护玉 欣聚党恶子独承家.txt"
                        ),
                    },
                },
                {
                    "source": "石头记",
                    "target": "好了歌",
                    "properties": {
                        "weight": 1.0,
                        "keywords": "主题呼应",
                        "description": (
                            "《石头记》开篇以《好了歌》点明世事虚幻。<SEP>"
                            "第一百二十回归结《石头记》的流传。"
                        ),
                        "file_path": (
                            "001-第一回-甄士隐梦幻识通灵 贾雨村风尘怀闺秀.txt<SEP>"
                            "120-第一百二十回-甄士隐详说太虚情 贾雨村归结红楼梦.txt"
                        ),
                    },
                },
                {
                    "source": "好了歌",
                    "target": "看破红尘",
                    "properties": {
                        "weight": 1.0,
                        "keywords": "思想关联",
                        "description": "《好了歌》也从思想上关联看破红尘。",
                        "file_path": "001-第一回-甄士隐梦幻识通灵 贾雨村风尘怀闺秀.txt",
                    },
                },
            ],
            "is_truncated": False,
        }

    def query_data(self, query: str, mode: str = "hybrid", **options):
        raise AssertionError("graph-backed trace should not need query_data")


def test_api_entity_trace_prefers_graph_edges_for_theme_extensions_and_cleans_sep():
    context = create_app_context(
        manifest_path=Path("book/chapters_manifest.json"),
        data_dir=Path("data/app"),
        static_dir=Path("static"),
        retrieval_client=FakeGraphTraceClient(),
    )

    status, payload = handle_api_request(context, "GET", "/api/entity-trace?name=%E5%A5%BD%E4%BA%86%E6%AD%8C&chapter=1")

    assert status == 200
    assert payload["themeExtensions"][0] == {
        "topic": "看破红尘",
        "description": "主题表达：甄士隐听《好了歌》后悟彻“好便是了”。",
        "chapterJumps": [
            {
                "chapter": 117,
                "label": "第117回：贾宝玉在和尚点化下，把红尘看破，最终决定还玉。",
                "description": "贾宝玉在和尚点化下，把红尘看破，最终决定还玉。",
            }
        ],
    }
    assert [item["topic"] for item in payload["themeExtensions"]].count("看破红尘") == 1
    shitouji = next(item for item in payload["themeExtensions"] if item["topic"] == "石头记")
    assert shitouji["chapterJumps"] == [
        {
            "chapter": 120,
            "label": "第120回：第一百二十回归结《石头记》的流传。",
            "description": "第一百二十回归结《石头记》的流传。",
        }
    ]
    daoren = next(item for item in payload["themeExtensions"] if item["topic"] == "跛足道人")
    assert daoren["chapterJumps"] == [
        {
            "chapter": 12,
            "label": "第12回：跛足道人将风月宝鉴交给贾瑞，并叮嘱其只能照背面。",
            "description": "跛足道人将风月宝鉴交给贾瑞，并叮嘱其只能照背面。",
        }
    ]
    assert "<SEP>" not in str(payload)
    assert "贵族家庭衰亡" not in str(payload)


class FakeGraphAliasFallbackClient:
    def __init__(self):
        self.graph_labels = []

    def search_labels(self, q: str, limit: int = 10):
        return ["好了歌"]

    def graph(self, label: str, max_depth: int = 3, max_nodes: int = 1000):
        self.graph_labels.append(label)
        if label == "《好了歌》":
            return {"nodes": [], "edges": []}
        if label == "好了歌":
            return {
                "nodes": [{"id": "好了歌", "properties": {"description": "跛足道人所唱。"}}],
                "edges": [
                    {
                        "source": "好了歌",
                        "target": "跛足道人",
                        "properties": {
                            "keywords": "吟唱作品",
                            "description": "跛足道人在街前为落魄的甄士隐吟唱《好了歌》。<SEP>跛足道人后文持风月宝鉴点化贾瑞。",
                            "file_path": (
                                "001-第一回-甄士隐梦幻识通灵 贾雨村风尘怀闺秀.txt<SEP>"
                                "012-第十二回-王熙凤毒设相思局 贾天祥正照风月鉴.txt"
                            ),
                            "weight": 2.0,
                        },
                    }
                ],
            }
        return {"nodes": [], "edges": []}

    def query_data(self, query: str, mode: str = "hybrid", **options):
        raise AssertionError("graph alias fallback should not need query_data")


def test_api_entity_trace_graph_lookup_falls_back_to_normalized_alias_label(tmp_path):
    client = FakeGraphAliasFallbackClient()
    manifest_path, data_dir, static_dir = _write_minimal_app_context_files(tmp_path, [_review_card()])
    context = create_app_context(
        manifest_path=manifest_path,
        data_dir=data_dir,
        static_dir=static_dir,
        retrieval_client=client,
    )

    status, payload = handle_api_request(context, "GET", "/api/entity-trace?name=%E3%80%8A%E5%A5%BD%E4%BA%86%E6%AD%8C%E3%80%8B&chapter=1")

    assert status == 200
    assert client.graph_labels[:2] == ["《好了歌》", "好了歌"]
    assert payload["themeExtensions"][0]["topic"] == "跛足道人"
    assert payload["themeExtensions"][0]["chapterJumps"][0]["chapter"] == 12


def test_api_entity_trace_graph_returns_previous_chapter_jumps_separately(tmp_path):
    class FakePreviousGraphClient:
        def search_labels(self, q: str, limit: int = 10):
            return [q]

        def graph(self, label: str, max_depth: int = 3, max_nodes: int = 1000):
            return {
                "nodes": [{"id": "林黛玉", "properties": {}}, {"id": "贾雨村", "properties": {}}],
                "edges": [
                    {
                        "source": "林黛玉",
                        "target": "贾雨村",
                        "properties": {
                            "keywords": "师生关系",
                            "description": "第二回交代贾雨村为林黛玉授课。<SEP>第三回林如海托贾雨村送黛玉入都。",
                            "file_path": (
                                "002-第二回-贾夫人仙逝扬州城 冷子兴演说荣国府.txt<SEP>"
                                "003-第三回-托内兄如海荐西宾 接外孙贾母惜孤女.txt"
                            ),
                        },
                    }
                ],
            }

    manifest_path, data_dir, static_dir = _write_minimal_app_context_files(tmp_path, [_review_card()])
    context = create_app_context(
        manifest_path=manifest_path,
        data_dir=data_dir,
        static_dir=static_dir,
        retrieval_client=FakePreviousGraphClient(),
    )

    status, payload = handle_api_request(context, "GET", "/api/entity-trace?name=%E6%9E%97%E9%BB%9B%E7%8E%89&chapter=3")

    assert status == 200
    extension = payload["themeExtensions"][0]
    assert extension["previousChapterJumps"] == [
        {
            "chapter": 2,
            "label": "第2回：第二回交代贾雨村为林黛玉授课。",
            "description": "第二回交代贾雨村为林黛玉授课。",
        }
    ]
    assert "chapterJumps" not in extension


def test_api_chapter_returns_original_text_when_review_card_is_missing(tmp_path):
    manifest_path, data_dir, static_dir = _write_minimal_app_context_files(tmp_path, [])
    context = create_app_context(manifest_path=manifest_path, data_dir=data_dir, static_dir=static_dir)

    status, payload = handle_api_request(context, "GET", "/api/chapters/1")

    assert status == 200
    assert payload["chapter"]["number"] == 1
    assert payload["originalText"]
    assert payload["reviewCard"] is None
    assert payload["knowledgeCards"] == []
    assert payload["materialStatus"] == {
        "hasReviewCard": False,
        "message": "章节资料暂未生成，可先阅读原文。",
    }
    assert "LightRAG" not in str(payload)


def test_api_ask_returns_structured_answer():
    context = create_app_context(
        manifest_path=Path("book/chapters_manifest.json"),
        data_dir=Path("data/app"),
        static_dir=Path("static"),
    )

    status, payload = handle_api_request(context, "POST", "/api/ask", {"question": "黛玉葬花体现了什么？"})

    assert status == 200
    assert payload["status"] == "answered"
    assert payload["evidence"]
    assert "quotableFacts" in payload
    assert payload["quotableFacts"]["title"] == "可引用事实"
    assert payload["quotableFacts"]["claims"]
    assert payload["continuationLinks"]


class FakeRetrievalClient:
    def query_data(self, query: str, mode: str = "hybrid", **options):
        return {
            "status": "success",
            "data": {
                "entities": [],
                "relationships": [
                    {
                        "src_id": "宝黛初会",
                        "tgt_id": "第三回",
                        "keywords": "发生章回",
                        "description": "宝黛初会发生在第三回，林黛玉进贾府后与贾宝玉在贾母处相见。",
                        "source_id": "doc-003-chunk-001",
                        "file_path": "003-第三回-托内兄如海荐西宾 接外孙贾母惜孤女.txt",
                    }
                ],
                "chunks": [],
                "references": [],
            },
            "metadata": {"query_mode": mode},
        }


def test_api_ask_uses_configured_retrieval_client_for_chapter_location():
    context = create_app_context(
        manifest_path=Path("book/chapters_manifest.json"),
        data_dir=Path("data/app"),
        static_dir=Path("static"),
        retrieval_client=FakeRetrievalClient(),
    )

    status, payload = handle_api_request(context, "POST", "/api/ask", {"question": "宝黛初会发生在哪一回？"})

    assert status == 200
    assert payload["status"] == "answered"
    assert "第三回" in payload["shortConclusion"][0]["text"]
    assert payload["evidence"][0]["chapter"] == 3
    assert payload["continuationLinks"][0]["targetId"] == "3"
    assert "LightRAG" not in str(payload)


def test_create_app_context_does_not_build_retrieval_client_from_env_by_default(monkeypatch):
    monkeypatch.setenv("LIGHTRAG_BASE_URL", "http://10.1.0.246:9621")

    context = create_app_context(
        manifest_path=Path("book/chapters_manifest.json"),
        data_dir=Path("data/app"),
        static_dir=Path("static"),
    )

    assert context.retrieval_client is None


def test_create_app_context_can_build_retrieval_client_from_env_when_enabled(monkeypatch):
    monkeypatch.setenv("LIGHTRAG_BASE_URL", "http://10.1.0.246:9621")

    context = create_app_context(
        manifest_path=Path("book/chapters_manifest.json"),
        data_dir=Path("data/app"),
        static_dir=Path("static"),
        use_env_retrieval=True,
    )

    assert context.retrieval_client is not None
    assert context.retrieval_client.config.base_url == "http://10.1.0.246:9621"


def test_create_app_context_reads_postgres_database_url_from_dotenv(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    Path(".env").write_text("DATABASE_URL=postgresql://user:p*ss@example.local:5432/hlm\n", encoding="utf-8")
    monkeypatch.setattr("hlm_kg.web_app.PostgresContentStore", lambda database_url, fallback_store: ("postgres", database_url, fallback_store))

    context = create_app_context(
        manifest_path=ROOT / "book/chapters_manifest.json",
        data_dir=ROOT / "data/app",
        static_dir=ROOT / "static",
        use_postgres_store=True,
    )

    assert context.store[0] == "postgres"
    assert context.store[1] == "postgresql://user:p*ss@example.local:5432/hlm"


def test_create_app_context_enables_postgres_from_dotenv_flag(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    Path(".env").write_text(
        "DATABASE_URL=postgresql://user:p*ss@example.local:5432/hlm\n"
        "HLM_CONTENT_STORE=postgres\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("hlm_kg.web_app.PostgresContentStore", lambda database_url, fallback_store: ("postgres", database_url, fallback_store))

    context = create_app_context(
        manifest_path=ROOT / "book/chapters_manifest.json",
        data_dir=ROOT / "data/app",
        static_dir=ROOT / "static",
        use_env_content_store=True,
    )

    assert context.store[0] == "postgres"
    assert context.store[1] == "postgresql://user:p*ss@example.local:5432/hlm"


def test_create_app_context_defaults_to_json_store_when_dotenv_enables_postgres(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    Path(".env").write_text(
        "DATABASE_URL=postgresql://user:p*ss@example.local:5432/hlm\n"
        "HLM_CONTENT_STORE=postgres\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("hlm_kg.web_app.PostgresContentStore", lambda database_url, fallback_store: ("postgres", database_url, fallback_store))
    review_card = _review_card(characters=[{"name": "袭人", "actions": ["劝慰宝玉"]}])
    manifest_path, data_dir, static_dir = _write_minimal_app_context_files(tmp_path, [review_card])

    context = create_app_context(manifest_path=manifest_path, data_dir=data_dir, static_dir=static_dir)
    status, payload = handle_api_request(context, "GET", "/api/chapters/1")

    assert status == 200
    assert payload["reviewCard"]["characters"] == review_card["characters"]


def test_create_app_context_fails_fast_when_postgres_enabled_without_database_url(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("HLM_CONTENT_STORE", raising=False)

    try:
        create_app_context(
            manifest_path=ROOT / "book/chapters_manifest.json",
            data_dir=ROOT / "data/app",
            static_dir=ROOT / "static",
            use_postgres_store=True,
        )
    except RuntimeError as exc:
        assert "DATABASE_URL is not set" in str(exc)
    else:
        raise AssertionError("expected explicit PostgreSQL configuration failure")


def test_api_ask_returns_partial_answer_with_refusal_and_links():
    context = create_app_context(
        manifest_path=Path("book/chapters_manifest.json"),
        data_dir=Path("data/app"),
        static_dir=Path("static"),
    )

    status, payload = handle_api_request(
        context,
        "POST",
        "/api/ask",
        {"question": "黛玉葬花体现了什么？再说明一个没有资料的后文细节"},
    )

    assert status == 200
    assert payload["status"] == "partial"
    assert payload["shortConclusion"]
    assert payload["refusal"]["message"]
    assert payload["continuationLinks"]


def test_api_ask_returns_refusal_without_internal_reason_code_in_message():
    context = create_app_context(
        manifest_path=Path("book/chapters_manifest.json"),
        data_dir=Path("data/app"),
        static_dir=Path("static"),
    )

    status, payload = handle_api_request(context, "POST", "/api/ask", {"question": "请帮我写一篇作文"})

    assert status == 200
    assert payload["status"] == "refused"
    assert payload["refusal"]["message"]
    assert "OUT_OF_SCOPE" not in payload["refusal"]["message"]


def test_api_topics_returns_five_categories():
    context = create_app_context(
        manifest_path=Path("book/chapters_manifest.json"),
        data_dir=Path("data/app"),
        static_dir=Path("static"),
    )

    status, payload = handle_api_request(context, "GET", "/api/topics")

    assert status == 200
    assert {topic["category"] for topic in payload["topics"]} == {
        "人物关系",
        "关键事件",
        "判词命运",
        "意象伏笔",
        "可引用事实",
    }


def test_api_card_returns_student_facing_knowledge_panel_payload():
    context = create_app_context(
        manifest_path=Path("book/chapters_manifest.json"),
        data_dir=Path("data/app"),
        static_dir=Path("static"),
    )

    status, payload = handle_api_request(context, "GET", "/api/cards/card-lindaiyu")

    assert status == 200
    assert payload["card"]["name"] == "林黛玉"
    assert "textUnderstanding" in payload["card"]
    assert "understandingAngles" in payload["card"]
    assert "graphRelationIds" in payload["card"]
    assert payload["evidence"]
    assert payload["relations"]
    assert payload["traceItems"]
    assert payload["traceItems"][0]["chapter"]
    assert "LightRAG" not in str(payload)


def test_api_topic_detail_links_cards_relations_and_quotable_facts():
    context = create_app_context(
        manifest_path=Path("book/chapters_manifest.json"),
        data_dir=Path("data/app"),
        static_dir=Path("static"),
    )

    status, payload = handle_api_request(context, "GET", "/api/topics/topic-image-foreshadowing")

    assert status == 200
    assert payload["topic"]["category"] == "意象伏笔"
    assert payload["topic"]["typicalQuestionPatterns"]
    assert payload["cards"]
    assert payload["relations"]
    assert payload["evidence"]


def test_static_topic_view_has_visible_knowledge_panel_target():
    js = Path("static/app.js").read_text(encoding="utf-8")
    html = Path("static/index.html").read_text(encoding="utf-8")

    assert "topic-knowledge-panel" in html
    assert 'cardTarget.closest("#topics") ? "#topic-knowledge-panel" : "#knowledge-panel"' in js
    assert "loadKnowledgeCard(cardTarget.dataset.cardId, panel)" in js
    assert "#topic-knowledge-panel" in js


def test_static_chapter_view_uses_offset_annotations_not_name_replacement():
    js = Path("static/app.js").read_text(encoding="utf-8")

    assert "renderAnnotatedOriginalText(text, annotations)" in js
    assert "data-annotation-id" in js
    assert "data-card-id" in js
    assert "sort((left, right) => left.startOffset - right.startOffset" in js


def test_static_knowledge_panel_renders_trace_jump_buttons():
    js = Path("static/app.js").read_text(encoding="utf-8")

    assert "renderTraceItems" in js
    assert "data-trace-chapter-number" in js
    assert "traceItems" in js


def test_static_chapter_page_renders_rich_sections_and_entity_popover():
    js = Path("static/app.js").read_text(encoding="utf-8")
    css = Path("static/styles.css").read_text(encoding="utf-8")

    assert "renderEntityPopover" in js
    assert "data-inline-entity-id" in js
    assert "renderRichSection" in js
    assert "renderChapterTabs" in js
    assert "chapter-tab-panel" in css
    assert "characters" in js
    assert "relationships" in js
    assert "laterAssociations" in js
    assert ".entity-popover" in css
    assert ".entity-popover-backdrop" in css
    assert "align-items: center" in css
    assert "justify-content: center" in css
    assert ".chapter-section-grid" in css


def test_static_chapter_focus_panel_uses_review_card_characters():
    js = Path("static/app.js").read_text(encoding="utf-8")

    assert "const focusCards = (reviewCard.characters || [])" in js
    assert "data.knowledgeCards\n    .map((card)" not in js


def test_static_styles_include_trace_and_annotation_states():
    css = Path("static/styles.css").read_text(encoding="utf-8")

    assert ".trace-list" in css
    assert ".annotation-link" in css
    assert ".knowledge-panel" in css
    assert "overflow: auto" in css


def test_find_available_port_skips_occupied_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen()
        occupied_port = sock.getsockname()[1]

        assert find_available_port(occupied_port, attempts=2) == occupied_port + 1
