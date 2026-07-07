from dataclasses import dataclass, field

from hlm_kg.entity_resolver import EntityResolver
from hlm_kg.question_planner import QuestionPlanner


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


def make_planner() -> QuestionPlanner:
    resolver = EntityResolver(
        Store(
            [
                Card(id="card-lindaiyu", name="林黛玉", type="person", brief="主要人物。"),
                Card(id="card-daiyu-image", name="黛玉", type="image", brief="黛玉相关意象。"),
                Card(id="card-jiabaoyu", name="贾宝玉", type="person", brief="荣国府公子。"),
                Card(id="card-tonglingbaoyu", name="通灵宝玉", type="object", brief="宝玉所佩之玉。"),
            ]
        )
    )
    return QuestionPlanner(resolver)


def test_planner_maps_death_question_to_evidence_contract():
    plan = make_planner().plan("林黛玉是怎么死的？")

    assert [subject.canonical_name for subject in plan.subjects] == ["林黛玉"]
    assert plan.intent == "ask_fact"
    assert plan.target_property == "death_cause_or_process"
    assert plan.answer_shape == "short_direct"
    assert any("林黛玉" in requirement for requirement in plan.required_evidence)
    assert any("death" in requirement for requirement in plan.required_evidence)


def test_planner_uses_resolver_for_short_name_subject():
    plan = make_planner().plan("黛玉是怎么死的？")

    assert [subject.canonical_name for subject in plan.subjects] == ["林黛玉"]
    assert plan.subject_terms == ("林黛玉", "黛玉")
    assert plan.target_property == "death_cause_or_process"


def test_planner_keeps_object_subject_for_definition_question():
    plan = make_planner().plan("通灵宝玉是什么？")

    assert [subject.canonical_name for subject in plan.subjects] == ["通灵宝玉"]
    assert plan.subjects[0].canonical_type == "object"
    assert plan.target_property == "identity_or_definition"
    assert "贾宝玉" not in plan.subject_terms


def test_planner_records_first_mention_constraint_for_age_question():
    plan = make_planner().plan("贾宝玉第一次在书中出现的时候是几岁？")

    assert [subject.canonical_name for subject in plan.subjects] == ["贾宝玉"]
    assert plan.target_property == "age"
    assert "first_mention" in plan.constraints
