from dataclasses import dataclass, field

from hlm_kg.entity_resolver import EntityResolver


@dataclass(frozen=True)
class Card:
    id: str
    name: str
    type: str
    brief: str = ""
    text_understanding: list[str] = field(default_factory=list)
    understanding_angles: list[str] = field(default_factory=list)
    graph_relation_ids: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    related_card_ids: list[str] = field(default_factory=list)


class Store:
    def __init__(self, cards):
        self.knowledge_cards = cards


def test_resolver_maps_short_mention_to_person_canonical_when_exact_card_is_non_person():
    resolver = EntityResolver(
        Store(
            [
                Card(id="card-lindaiyu", name="林黛玉", type="person", brief="主要人物。"),
                Card(id="card-daiyu-image", name="黛玉", type="image", brief="黛玉相关意象。"),
            ]
        )
    )

    resolved = resolver.resolve_mention("黛玉", context_text="黛玉是怎么死的？")

    assert resolved.canonical_name == "林黛玉"
    assert resolved.canonical_type == "person"
    assert resolved.confidence == "high"
    assert "黛玉" in resolved.aliases


def test_resolver_keeps_short_person_mention_ambiguous_without_context():
    resolver = EntityResolver(
        Store(
            [
                Card(id="card-jiabaoyu", name="贾宝玉", type="person", brief="荣国府公子。"),
                Card(id="card-zhenbaoyu", name="甄宝玉", type="person", brief="甄家公子。"),
                Card(id="card-tonglingbaoyu", name="通灵宝玉", type="object", brief="宝玉所佩之玉。"),
            ]
        )
    )

    resolved = resolver.resolve_mention("宝玉")

    assert resolved.canonical_name is None
    assert resolved.confidence == "ambiguous"
    assert {candidate.name for candidate in resolved.ambiguity} == {"贾宝玉", "甄宝玉", "通灵宝玉"}


def test_resolver_uses_person_context_to_select_person_canonical_from_ambiguous_alias():
    resolver = EntityResolver(
        Store(
            [
                Card(id="card-baoyu", name="宝玉", type="person", brief="生成的简称卡。"),
                Card(id="card-jiabaoyu", name="贾宝玉", type="person", brief="荣国府公子。"),
                Card(id="card-zhenbaoyu", name="甄宝玉", type="person", brief="甄家公子。"),
                Card(id="card-tonglingbaoyu", name="通灵宝玉", type="object", brief="宝玉所佩之玉。"),
            ]
        )
    )

    resolved = resolver.resolve_mention("宝玉", context_text="宝玉第一次在书中出现的时候是几岁？")

    assert resolved.canonical_name == "贾宝玉"
    assert resolved.canonical_type == "person"
    assert resolved.confidence == "high"
    assert {candidate.name for candidate in resolved.ambiguity} == {"宝玉", "甄宝玉"}


def test_resolver_does_not_collapse_object_name_to_person():
    resolver = EntityResolver(
        Store(
            [
                Card(id="card-jiabaoyu", name="贾宝玉", type="person", brief="荣国府公子。"),
                Card(id="card-tonglingbaoyu", name="通灵宝玉", type="object", brief="宝玉所佩之玉。"),
            ]
        )
    )

    resolved = resolver.resolve_mention("通灵宝玉", context_text="通灵宝玉是什么？")

    assert resolved.canonical_name == "通灵宝玉"
    assert resolved.canonical_type == "object"
    assert resolved.confidence == "exact"
