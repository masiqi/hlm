from types import SimpleNamespace

from hlm_kg.domain import ChapterReviewCard, ProcessedMaterialSource
from scripts.build_entity_graph_cache import (
    build_entity_graph_cache_for_context,
    entity_graph_cache_rows,
    graph_payload_from_lightrag_graph,
    names_to_sync,
)


def _review_card(chapter: int, **overrides):
    values = {
        "id": f"review-{chapter:03d}",
        "chapter": chapter,
        "source": ProcessedMaterialSource(prompt_name="test", prompt_version="v1"),
        "plain_summary": "summary",
        "plot_chain": [],
        "key_events": [],
        "key_characters": [],
        "current_chapter_foreshadowing_signals": [],
        "later_association_relation_ids": [],
        "quotable_fact_ids": [],
        "retrieval_tags": [],
        "understanding_focus": [],
        "characters": [],
        "relationships": [],
        "places": [],
        "objects": [],
        "literary_texts": [],
        "modern_explanations": [],
        "later_associations": [],
        "annotations": [],
    }
    values.update(overrides)
    return ChapterReviewCard(**values)


class FakeStore:
    def __init__(self, cards):
        self.cards = {card.chapter: card for card in cards}

    def maybe_review_card_for_chapter(self, chapter: int):
        return self.cards.get(chapter)


class FakeLightRAGGraphClient:
    def __init__(self):
        self.labels = []

    def graph(self, label, max_depth=1, max_nodes=100):
        self.labels.append((label, max_depth, max_nodes))
        return {
            "nodes": [
                {
                    "id": "顽石",
                    "properties": {
                        "description": "无才补天被弃于青埂峰下的石头。<SEP>通灵宝玉的前世本体。",
                        "file_path": "001-第一回.txt",
                    },
                },
                {"id": "通灵宝玉", "properties": {"description": "宝玉所衔之玉。"}},
            ],
            "edges": [
                {
                    "source": "顽石",
                    "target": "通灵宝玉",
                    "properties": {
                        "keywords": "前世本体",
                        "description": "顽石与通灵宝玉互为前身后身。",
                        "file_path": "001-第一回.txt",
                    },
                }
            ],
        }


def test_graph_payload_from_lightrag_graph_extracts_description_and_neighbors():
    graph = {
        "nodes": [
            {
                "id": "顽石",
                "properties": {
                    "description": "无才补天被弃于青埂峰下的石头。<SEP>通灵宝玉的前世本体。",
                },
            },
            {"id": "女娲", "properties": {"description": "补天者。"}},
        ],
        "edges": [
            {
                "source": "顽石",
                "target": "女娲",
                "properties": {"keywords": "补天遗石", "description": "女娲炼石补天，顽石为遗石。"},
            }
        ],
    }

    payload = graph_payload_from_lightrag_graph("顽石", graph)

    assert payload["description"] == "无才补天被弃于青埂峰下的石头。；通灵宝玉的前世本体。"
    assert payload["neighbors"] == [
        {
            "name": "女娲",
            "relationship": "补天遗石",
            "description": "女娲炼石补天，顽石为遗石。",
        }
    ]
    assert payload["raw_graph"] == graph


def test_graph_payload_from_lightrag_graph_extracts_second_hop_extended_neighbors():
    graph = {
        "nodes": [
            {"id": "顽石", "properties": {"description": "补天遗石。"}},
            {"id": "通灵宝玉", "properties": {"description": "顽石入世后的物象。"}},
            {"id": "贾宝玉", "properties": {"description": "衔玉而生。"}},
        ],
        "edges": [
            {
                "source": "顽石",
                "target": "通灵宝玉",
                "properties": {"keywords": "前世本体", "description": "顽石是通灵宝玉的前身。", "weight": 0.4},
            },
            {
                "source": "通灵宝玉",
                "target": "贾宝玉",
                "properties": {"keywords": "随身物象", "description": "通灵宝玉随贾宝玉入世。", "weight": 0.95},
            },
            {
                "source": "顽石",
                "target": "女娲",
                "properties": {"keywords": "补天遗石", "description": "女娲炼石补天。", "weight": 0.3},
            },
        ],
    }

    payload = graph_payload_from_lightrag_graph("顽石", graph)

    assert [neighbor["name"] for neighbor in payload["neighbors"]] == ["通灵宝玉", "女娲"]
    assert payload["extended_neighbors"] == [
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


def test_graph_payload_filters_alias_extended_neighbors_and_shortens_text():
    graph = {
        "nodes": [
            {"id": "通灵宝玉", "properties": {"description": "宝玉所衔之玉。"}},
            {"id": "王熙凤", "properties": {"description": "贾府理家人物。"}},
            {"id": "凤姐", "properties": {"description": "王熙凤俗称。"}},
            {"id": "协理宁国府", "properties": {"description": "王熙凤理家才能的重要情节。"}},
        ],
        "edges": [
            {
                "source": "通灵宝玉",
                "target": "王熙凤",
                "properties": {"keywords": "人物关联", "description": "通灵宝玉相关人物链。", "weight": 0.4},
            },
            {
                "source": "王熙凤",
                "target": "凤姐",
                "properties": {
                    "keywords": "人物俗称,人物别名,人物别称,人物昵称,人物称呼,人物称谓,指代关系",
                    "description": "凤姐是《红楼梦》中王熙凤最为普遍且稳固的俗称、昵称与别名。",
                    "weight": 0.99,
                },
            },
            {
                "source": "王熙凤",
                "target": "协理宁国府",
                "properties": {
                    "keywords": "理家权力,办事才能",
                    "description": (
                        "王熙凤协理宁国府，显示其理家才能。"
                        "她整顿宁府弊端、分派事务，表现出强势管理能力和权力手腕。"
                    ),
                    "weight": 0.6,
                },
            },
        ],
    }

    payload = graph_payload_from_lightrag_graph("通灵宝玉", graph)

    assert payload["extended_neighbors"] == [
        {
            "from": "通灵宝玉",
            "via": "王熙凤",
            "to": "协理宁国府",
            "relationship": "理家权力",
            "description": "王熙凤协理宁国府，显示其理家才能。",
            "path": ["通灵宝玉", "王熙凤", "协理宁国府"],
            "depth": 2,
            "weight": 0.6,
        }
    ]


def test_build_entity_graph_cache_collects_relation_endpoint_entities():
    card = _review_card(
        1,
        relationships=[
            {
                "source": "顽石",
                "type": "被僧道携入红尘",
                "target": "一僧一道",
                "description": "女娲补天遗石经一僧一道缩小镌字后带入红尘经历",
            }
        ],
    )
    client = FakeLightRAGGraphClient()
    context = SimpleNamespace(store=FakeStore([card]), retrieval_client=client)

    cache = build_entity_graph_cache_for_context(context=context, chapters=[1], max_depth=1, max_nodes=50)

    assert "顽石" in cache
    assert cache["顽石"]["description"] == "无才补天被弃于青埂峰下的石头。；通灵宝玉的前世本体。"
    assert cache["顽石"]["neighbors"][0]["name"] == "通灵宝玉"
    assert client.labels[0] == ("顽石", 1, 50)


def test_entity_graph_cache_rows_turn_json_cache_into_pg_rows():
    cache = {
        "顽石": {
            "description": "无才补天被弃于青埂峰下的石头。",
            "neighbors": [{"name": "通灵宝玉", "relationship": "前世本体"}],
            "raw_graph": {"nodes": []},
            "metadata": {"source": "lightrag_graph"},
        }
    }

    assert entity_graph_cache_rows(cache) == [
        {
            "entity_name": "顽石",
            "description": "无才补天被弃于青埂峰下的石头。",
            "neighbors": [{"name": "通灵宝玉", "relationship": "前世本体"}],
            "extended_neighbors": [],
            "raw_graph": {"nodes": []},
            "metadata": {"source": "lightrag_graph"},
        }
    ]


def test_names_to_sync_skips_existing_only_when_requested():
    selected = ["顽石", "通灵宝玉"]
    existing = {"顽石": {"description": "旧缓存"}}

    assert names_to_sync(selected, existing, skip_existing=True) == ["通灵宝玉"]
    assert names_to_sync(selected, existing, skip_existing=False) == ["顽石", "通灵宝玉"]
