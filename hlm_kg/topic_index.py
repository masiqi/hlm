from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import blake2s
import re
from typing import Any


FORBIDDEN_STUDENT_TERMS = {
    "LightRAG",
    "RAG",
    "知识图谱",
    "向量检索",
    "置信度",
    "模型分数",
    "标准答案",
    "题库",
    "刷题",
    "下一题",
    "提交答案",
    "批改",
}
GENERATED_TOPIC_PREFIX = "topic-auto-"
GENERATED_EVIDENCE_PREFIX = "ev-topic-auto-"
GENERATED_CARD_PREFIX = "card-topic-auto-"
GENERATED_RELATION_PREFIX = "rel-topic-auto-"
HIDDEN_SEED_TOPIC_IDS = {
    "topic-character-relations",
    "topic-key-events",
    "topic-judgement-destiny",
    "topic-image-foreshadowing",
    "topic-quotable-facts",
}
CATEGORY_ORDER = {"人物关系": 0, "关键事件": 1, "判词命运": 2, "意象伏笔": 3, "可引用事实": 4}
TOPIC_CATEGORY_LIMITS = {"人物关系": 70, "关键事件": 35, "判词命运": 35, "意象伏笔": 40, "可引用事实": 0}
CARD_TYPE_BY_SOURCE = {
    "character": "person",
    "relationship_target": "image",
    "event": "event",
    "literary": "expression",
    "destiny": "judgement",
    "object": "image",
    "place": "place",
    "foreshadowing": "image",
    "later": "image",
}
DESTINY_TERMS = ("命运", "判词", "曲", "诗", "花签", "灯谜", "梦", "太虚幻境", "结局", "归宿")
PROMOTED_TOPIC_TERMS = (
    "刘姥姥进大观园",
    "金陵十二钗判词",
    "黛玉葬花",
    "宝钗扑蝶",
    "宝玉挨打",
    "抄检大观园",
    "晴雯之死",
    "晴雯补裘",
    "香菱学诗",
    "元妃省亲",
    "探春理家",
    "黛玉焚稿",
    "宝玉成亲",
    "宝玉出家",
    "尤三姐之死",
    "尤二姐之死",
    "芙蓉女儿诔",
    "木石前盟",
    "金玉良缘",
    "通灵宝玉",
    "葫芦案",
    "好了歌",
    "葬花吟",
    "太虚幻境",
    "大观园",
    "海棠诗社",
    "螃蟹宴",
    "贾府败落",
    "落花",
)


@dataclass(frozen=True)
class TopicIndexResult:
    topics: list[dict[str, Any]]
    evidence: list[dict[str, Any]]
    knowledge_cards: list[dict[str, Any]]
    graph_relations: list[dict[str, Any]]
    summary: dict[str, Any]


@dataclass
class _TopicDraft:
    id: str
    title: str
    category: str
    description: str
    typical_question_patterns: list[str] = field(default_factory=list)
    card_ids: list[str] = field(default_factory=list)
    relation_ids: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    quotable_fact_ids: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "category": self.category,
            "description": self.description,
            "card_ids": _limit_unique(self.card_ids, 12),
            "relation_ids": _limit_unique(self.relation_ids, 12),
            "typical_question_patterns": _limit_unique(self.typical_question_patterns, 8),
            "quotable_fact_ids": _limit_unique(self.quotable_fact_ids, 12),
            "evidence_ids": _limit_unique(self.evidence_ids, 12),
        }


class _TopicIndexBuilder:
    def __init__(
        self,
        *,
        topics: list[dict[str, Any]],
        evidence: list[dict[str, Any]],
        knowledge_cards: list[dict[str, Any]],
        graph_relations: list[dict[str, Any]],
    ) -> None:
        self.seed_topics = [
            item
            for item in topics
            if not _is_generated(item.get("id"), GENERATED_TOPIC_PREFIX)
            and str(item.get("id")) not in HIDDEN_SEED_TOPIC_IDS
        ]
        self.evidence_by_id = {
            str(item["id"]): dict(item)
            for item in evidence
            if not _is_generated(item.get("id"), GENERATED_EVIDENCE_PREFIX)
        }
        self.cards_by_id = {
            str(item["id"]): dict(item)
            for item in knowledge_cards
            if not _is_generated(item.get("id"), GENERATED_CARD_PREFIX)
        }
        self.relations_by_id = {
            str(item["id"]): dict(item)
            for item in graph_relations
            if not _is_generated(item.get("id"), GENERATED_RELATION_PREFIX)
        }
        self.card_id_by_name = {str(item.get("name")): card_id for card_id, item in self.cards_by_id.items()}
        self.topic_drafts: dict[str, _TopicDraft] = {}
        self.skipped_candidates = 0

    def build(self, review_cards: list[dict[str, Any]]) -> TopicIndexResult:
        for card in sorted(review_cards, key=lambda item: int(item.get("chapter") or 0)):
            self._consume_review_card(card)

        candidate_topics = self._merged_generated_topics([draft.as_dict() for draft in self.topic_drafts.values()])
        generated_topics = self._published_generated_topics(candidate_topics)
        topics = self._sorted_topics([*self.seed_topics, *generated_topics])
        evidence = sorted(self.evidence_by_id.values(), key=lambda item: str(item["id"]))
        knowledge_cards = sorted(self.cards_by_id.values(), key=lambda item: str(item["id"]))
        graph_relations = sorted(self.relations_by_id.values(), key=lambda item: str(item["id"]))
        generated_by_category: dict[str, int] = {}
        for topic in generated_topics:
            generated_by_category[topic["category"]] = generated_by_category.get(topic["category"], 0) + 1
        return TopicIndexResult(
            topics=topics,
            evidence=evidence,
            knowledge_cards=knowledge_cards,
            graph_relations=graph_relations,
            summary={
                "input_chapter_cards": len(review_cards),
                "generated_topics": len(generated_topics),
                "candidate_topics": len(candidate_topics),
                "generated_topics_by_category": generated_by_category,
                "generated_evidence": len([item for item in evidence if str(item["id"]).startswith(GENERATED_EVIDENCE_PREFIX)]),
                "generated_knowledge_cards": len([item for item in knowledge_cards if str(item["id"]).startswith(GENERATED_CARD_PREFIX)]),
                "generated_relations": len([item for item in graph_relations if str(item["id"]).startswith(GENERATED_RELATION_PREFIX)]),
                "skipped_candidates": self.skipped_candidates,
            },
        )

    def _consume_review_card(self, card: dict[str, Any]) -> None:
        chapter = _chapter_number(card)
        if chapter is None:
            self.skipped_candidates += 1
            return
        for index, character in enumerate(card.get("characters") or []):
            self._add_character_topic(card, character, index)
        for index, relationship in enumerate(card.get("relationships") or []):
            self._add_relationship_topic(card, relationship, index)
        for index, event in enumerate(card.get("key_events") or []):
            self._add_text_topic(
                card=card,
                category="关键事件",
                source_kind="event",
                field="key_events",
                index=index,
                title=_short_topic(str(event)),
                text=str(event),
                card_type="event",
                typical_question="概括事件并说明人物表现",
            )
        for index, text in enumerate(card.get("literary_texts") or []):
            self._add_literary_topic(card, text, index)
        for index, item in enumerate(card.get("objects") or []):
            self._add_named_image_topic(card, item, index, field="objects", source_kind="object", category="意象伏笔")
        for index, item in enumerate(card.get("places") or []):
            self._add_named_image_topic(card, item, index, field="places", source_kind="place", category="意象伏笔")
        for index, signal in enumerate(card.get("current_chapter_foreshadowing_signals") or []):
            self._add_text_topic(
                card=card,
                category="意象伏笔",
                source_kind="foreshadowing",
                field="current_chapter_foreshadowing_signals",
                index=index,
                title=_short_topic(str(signal)),
                text=str(signal),
                card_type="image",
                typical_question="说明意象和后文关联",
            )
        for index, association in enumerate(card.get("later_associations") or []):
            self._add_later_association_topics(card, association, index)

    def _add_character_topic(self, card: dict[str, Any], character: Any, index: int) -> None:
        if not isinstance(character, dict):
            self.skipped_candidates += 1
            return
        name = str(character.get("name") or "").strip()
        details = _join_parts(
            character.get("importance"),
            "；".join(str(item) for item in character.get("actions") or []),
            "；".join(str(item) for item in character.get("traits") or []),
        )
        if not name or not details:
            self.skipped_candidates += 1
            return
        card_id = self._ensure_card(name=name, card_type="person", brief=details, evidence_id=None)
        evidence_id = self._add_evidence(
            card=card,
            field="characters",
            index=index,
            text=f"{name}：{details}",
            entity_ids=[card_id],
        )
        if not evidence_id:
            return
        self._ensure_card(name=name, card_type="person", brief=details, evidence_id=evidence_id)
        topic = self._topic(
            category="人物关系",
            title=name,
            description=f"围绕{name}的章回表现、人物关系和可引用事实组织。",
            kind="character",
            typical_question="说明人物表现及章回依据",
        )
        self._attach(topic, card_ids=[card_id], evidence_ids=[evidence_id])
        self._attach(topic, quotable_fact_ids=[evidence_id])

    def _add_relationship_topic(self, card: dict[str, Any], relationship: Any, index: int) -> None:
        if not isinstance(relationship, dict):
            self.skipped_candidates += 1
            return
        source = str(relationship.get("source") or "").strip()
        target = str(relationship.get("target") or "").strip()
        relation_type = str(relationship.get("type") or "关系").strip()
        description = _join_parts(relationship.get("description"), relationship.get("chapter_evidence"))
        if not source or not target or not description:
            self.skipped_candidates += 1
            return
        source_card_id = self._ensure_card(name=source, card_type="person", brief=f"{source}相关人物。", evidence_id=None)
        target_card_type = "person" if _looks_like_person(target) else "image"
        target_card_id = self._ensure_card(
            name=target,
            card_type=target_card_type,
            brief=f"{target}相关线索。",
            evidence_id=None,
        )
        relation_id = f"{GENERATED_RELATION_PREFIX}ch{_chapter_number(card):03d}-{_slug(source)}-{_slug(target)}-{index:02d}"
        evidence_id = self._add_evidence(
            card=card,
            field="relationships",
            index=index,
            text=f"{source}与{target}（{relation_type}）：{description}",
            entity_ids=[source_card_id, target_card_id],
            relation_id=relation_id,
        )
        if not evidence_id:
            return
        self.relations_by_id[relation_id] = {
            "id": relation_id,
            "subject_id": source_card_id,
            "predicate": _slug(relation_type),
            "object_id": target_card_id,
            "chapters": [_chapter_number(card)],
            "evidence_ids": [evidence_id],
            "provenance": "curated",
            "description": f"{source}与{target}的{relation_type}关系：{description}",
        }
        self._ensure_card(name=source, card_type="person", brief=f"{source}相关人物。", evidence_id=evidence_id, relation_id=relation_id)
        self._ensure_card(name=target, card_type=target_card_type, brief=f"{target}相关线索。", evidence_id=evidence_id, relation_id=relation_id)
        topic = self._topic(
            category="人物关系",
            title=f"{source}与{target}",
            description=f"围绕{source}与{target}的{relation_type}关系组织。",
            kind="relationship",
            typical_question="说明人物关系及章回依据",
        )
        self._attach(topic, card_ids=[source_card_id, target_card_id], relation_ids=[relation_id], evidence_ids=[evidence_id])
        self._attach(topic, quotable_fact_ids=[evidence_id])
        self._attach_person_relation_topic(
            title=source,
            card_id=source_card_id,
            relation_id=relation_id,
            evidence_id=evidence_id,
        )
        if target_card_type == "person":
            self._attach_person_relation_topic(
                title=target,
                card_id=target_card_id,
                relation_id=relation_id,
                evidence_id=evidence_id,
            )

    def _attach_person_relation_topic(self, *, title: str, card_id: str, relation_id: str, evidence_id: str) -> None:
        topic = self._topic(
            category="人物关系",
            title=title,
            description=f"围绕{title}的章回表现、人物关系和可引用事实组织。",
            kind="character",
            typical_question="说明人物关系及章回依据",
        )
        self._attach(topic, card_ids=[card_id], relation_ids=[relation_id], evidence_ids=[evidence_id], quotable_fact_ids=[evidence_id])

    def _add_literary_topic(self, card: dict[str, Any], item: Any, index: int) -> None:
        if not isinstance(item, dict):
            self.skipped_candidates += 1
            return
        title = str(item.get("title") or item.get("quote") or item.get("name") or "").strip()
        text = _join_parts(item.get("quote"), item.get("explanation"), item.get("function"), item.get("meaning"), item.get("modernText"))
        if not title or not text:
            self.skipped_candidates += 1
            return
        card_type = "judgement" if _has_destiny_term(f"{title} {text}") else "expression"
        self._add_text_topic(
            card=card,
            category="判词命运",
            source_kind="destiny" if card_type == "judgement" else "literary",
            field="literary_texts",
            index=index,
            title=title,
            text=f"{title}：{text}",
            card_type=card_type,
            typical_question="说明诗词曲文与人物命运的关系",
        )

    def _add_named_image_topic(self, card: dict[str, Any], item: Any, index: int, *, field: str, source_kind: str, category: str) -> None:
        if not isinstance(item, dict):
            self.skipped_candidates += 1
            return
        name = str(item.get("name") or item.get("title") or item.get("quote") or "").strip()
        text = _join_parts(item.get("meaning"), item.get("function"), item.get("context"), item.get("description"), item.get("explanation"))
        if not name or not text:
            self.skipped_candidates += 1
            return
        self._add_text_topic(
            card=card,
            category=category,
            source_kind=source_kind,
            field=field,
            index=index,
            title=name,
            text=f"{name}：{text}",
            card_type=CARD_TYPE_BY_SOURCE.get(source_kind, "image"),
            typical_question="说明意象和后文关联",
        )

    def _add_later_association_topics(self, card: dict[str, Any], association: Any, index: int) -> None:
        if not isinstance(association, dict):
            self.skipped_candidates += 1
            return
        title = str(association.get("topic") or "").strip()
        text = _join_parts(association.get("description"), association.get("evidence"))
        if not title or not text:
            self.skipped_candidates += 1
            return
        self._add_text_topic(
            card=card,
            category="意象伏笔",
            source_kind="later",
            field="later_associations",
            index=index,
            title=title,
            text=f"{title}：{text}",
            card_type="image",
            typical_question="说明意象和后文关联",
        )
        if _has_destiny_term(f"{title} {text}"):
            self._add_text_topic(
                card=card,
                category="判词命运",
                source_kind="destiny",
                field="later_associations",
                index=index,
                title=title,
                text=f"{title}：{text}",
                card_type="judgement",
                typical_question="说明人物命运线索及章回依据",
            )

    def _add_text_topic(
        self,
        *,
        card: dict[str, Any],
        category: str,
        source_kind: str,
        field: str,
        index: int,
        title: str,
        text: str,
        card_type: str,
        typical_question: str,
    ) -> None:
        clean_title = str(title or "").strip()
        clean_text = str(text or "").strip()
        if not clean_title or not clean_text:
            self.skipped_candidates += 1
            return
        evidence_id = self._add_evidence(card=card, field=field, index=index, text=clean_text, entity_ids=[])
        if not evidence_id:
            return
        topic_title = _canonical_topic_title(clean_title, clean_text)
        card_id = self._ensure_card(name=clean_title, card_type=card_type, brief=clean_text, evidence_id=evidence_id)
        topic = self._topic(
            category=category,
            title=topic_title,
            description=_topic_description(category, topic_title),
            kind=source_kind,
            typical_question=typical_question,
        )
        self._attach(topic, card_ids=[card_id], evidence_ids=[evidence_id], quotable_fact_ids=[evidence_id])
        if category == "关键事件":
            summary_evidence_id = self._add_topic_summary_evidence(
                card=card,
                field=field,
                index=index,
                title=topic_title,
                alternate_title=clean_title,
                original_text=clean_text,
                entity_ids=[card_id],
            )
            if summary_evidence_id:
                self._attach(topic, evidence_ids=[summary_evidence_id])

    def _add_fact_topic(self, *, title: str, evidence_id: str, card_id: str | None) -> None:
        return

    def _add_topic_summary_evidence(
        self,
        *,
        card: dict[str, Any],
        field: str,
        index: int,
        title: str,
        alternate_title: str,
        original_text: str,
        entity_ids: list[str],
    ) -> str | None:
        summary = _compact_text(card.get("plain_summary"))
        if not summary:
            return None
        excerpt = _excerpt_around_term(summary, title) or _excerpt_around_term(summary, alternate_title)
        if not excerpt:
            return None
        if excerpt == _compact_text(original_text):
            return None
        if len(excerpt) <= len(_compact_text(original_text)) + 8:
            return None
        return self._add_evidence(
            card=card,
            field=f"{field}_summary",
            index=index,
            text=excerpt,
            entity_ids=entity_ids,
        )

    def _add_evidence(
        self,
        *,
        card: dict[str, Any],
        field: str,
        index: int,
        text: str,
        entity_ids: list[str],
        relation_id: str | None = None,
    ) -> str | None:
        chapter = _chapter_number(card)
        if chapter is None or _has_forbidden_term(text):
            self.skipped_candidates += 1
            return None
        evidence_id = f"{GENERATED_EVIDENCE_PREFIX}ch{chapter:03d}-{_slug(field)}-{index:03d}-{_slug(text)}"
        self.evidence_by_id[evidence_id] = {
            "id": evidence_id,
            "source_type": "processed_material",
            "chapter": chapter,
            "location": f"第 {chapter} 回章节资料：{field}",
            "quote": None,
            "evidence_text": text,
            "entity_ids": _limit_unique(entity_ids, 8),
            "relation_id": relation_id,
            "confidence": "explicit",
            "provenance": f"data/app/chapter_review_cards.json:{card.get('id', f'review-{chapter:03d}')}:{field}:{index}",
            "derived_from_ids": [],
        }
        return evidence_id

    def _ensure_card(
        self,
        *,
        name: str,
        card_type: str,
        brief: str,
        evidence_id: str | None,
        relation_id: str | None = None,
    ) -> str:
        existing = self.card_id_by_name.get(name)
        if existing and not existing.startswith(GENERATED_CARD_PREFIX):
            return existing
        card_id = existing or f"{GENERATED_CARD_PREFIX}{_slug(card_type)}-{_slug(name)}"
        current = self.cards_by_id.get(card_id)
        if current is None:
            current = {
                "id": card_id,
                "name": name,
                "type": card_type,
                "brief": brief[:180],
                "text_understanding": [],
                "understanding_angles": [],
                "graph_relation_ids": [],
                "evidence_ids": [],
                "related_card_ids": [],
            }
        if evidence_id:
            current["evidence_ids"] = _limit_unique([*current.get("evidence_ids", []), evidence_id], 12)
            current["text_understanding"] = _limit_unique([*current.get("text_understanding", []), brief[:160]], 6)
        if relation_id:
            current["graph_relation_ids"] = _limit_unique([*current.get("graph_relation_ids", []), relation_id], 12)
        self.cards_by_id[card_id] = current
        self.card_id_by_name[name] = card_id
        return card_id

    def _topic(self, *, category: str, title: str, description: str, kind: str, typical_question: str) -> _TopicDraft:
        if _has_forbidden_term(f"{title} {description} {typical_question}"):
            self.skipped_candidates += 1
            # Return a detached draft that will not be stored; callers only attach after evidence exists.
            return _TopicDraft(id="", title=title, category=category, description=description)
        topic_id = f"{GENERATED_TOPIC_PREFIX}{_slug(category)}-{_slug(kind)}-{_slug(title)}"
        draft = self.topic_drafts.get(topic_id)
        if draft is None:
            draft = _TopicDraft(
                id=topic_id,
                title=title,
                category=category,
                description=description,
                typical_question_patterns=[typical_question],
            )
            self.topic_drafts[topic_id] = draft
        else:
            draft.typical_question_patterns = _limit_unique([*draft.typical_question_patterns, typical_question], 8)
        return draft

    def _attach(
        self,
        topic: _TopicDraft,
        *,
        card_ids: list[str] | None = None,
        relation_ids: list[str] | None = None,
        evidence_ids: list[str] | None = None,
        quotable_fact_ids: list[str] | None = None,
    ) -> None:
        if not topic.id:
            return
        topic.card_ids = _limit_unique([*topic.card_ids, *(card_ids or [])], 12)
        topic.relation_ids = _limit_unique([*topic.relation_ids, *(relation_ids or [])], 12)
        topic.evidence_ids = _limit_unique([*topic.evidence_ids, *(evidence_ids or [])], 12)
        topic.quotable_fact_ids = _limit_unique([*topic.quotable_fact_ids, *(quotable_fact_ids or [])], 12)

    def _sorted_topics(self, topics: list[dict[str, Any]]) -> list[dict[str, Any]]:
        cleaned = []
        for topic in topics:
            if _has_forbidden_term(str(topic)):
                self.skipped_candidates += 1
                continue
            cleaned.append(topic)
        return sorted(cleaned, key=lambda item: (CATEGORY_ORDER.get(str(item.get("category")), 99), str(item.get("title")), str(item.get("id"))))

    def _published_generated_topics(self, topics: list[dict[str, Any]]) -> list[dict[str, Any]]:
        published: list[dict[str, Any]] = []
        for category, limit in TOPIC_CATEGORY_LIMITS.items():
            if limit <= 0:
                continue
            category_topics: list[dict[str, Any]] = []
            for topic in topics:
                if topic.get("category") != category or str(topic.get("title", "")).endswith("可引用事实"):
                    continue
                if not _is_publishable_generated_topic(topic):
                    self.skipped_candidates += 1
                    continue
                category_topics.append(topic)
            ranked = sorted(category_topics, key=_topic_rank_key)
            published.extend(ranked[:limit])
        return published

    def _merged_generated_topics(self, topics: list[dict[str, Any]]) -> list[dict[str, Any]]:
        merged: dict[tuple[str, str], dict[str, Any]] = {}
        for topic in topics:
            category = str(topic.get("category", ""))
            title = str(topic.get("title", ""))
            key = (category, title)
            current = merged.get(key)
            if current is None:
                current = {
                    **topic,
                    "id": f"{GENERATED_TOPIC_PREFIX}{_slug(category)}-{_slug(title)}",
                    "card_ids": [],
                    "relation_ids": [],
                    "typical_question_patterns": [],
                    "quotable_fact_ids": [],
                    "evidence_ids": [],
                }
                merged[key] = current
            current["card_ids"] = _limit_unique([*current["card_ids"], *topic.get("card_ids", [])], 12)
            current["relation_ids"] = _limit_unique([*current["relation_ids"], *topic.get("relation_ids", [])], 12)
            current["typical_question_patterns"] = _limit_unique(
                [*current["typical_question_patterns"], *topic.get("typical_question_patterns", [])],
                8,
            )
            current["quotable_fact_ids"] = _limit_unique([*current["quotable_fact_ids"], *topic.get("quotable_fact_ids", [])], 12)
            current["evidence_ids"] = _limit_unique([*current["evidence_ids"], *topic.get("evidence_ids", [])], 12)
        return list(merged.values())


def build_topic_index(
    review_cards: list[dict[str, Any]],
    topics: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
    knowledge_cards: list[dict[str, Any]],
    graph_relations: list[dict[str, Any]],
) -> TopicIndexResult:
    return _TopicIndexBuilder(
        topics=topics,
        evidence=evidence,
        knowledge_cards=knowledge_cards,
        graph_relations=graph_relations,
    ).build(review_cards)


def _is_generated(value: Any, prefix: str) -> bool:
    return str(value or "").startswith(prefix)


def _chapter_number(card: dict[str, Any]) -> int | None:
    try:
        chapter = int(card.get("chapter"))
    except (TypeError, ValueError):
        return None
    return chapter if chapter > 0 else None


def _has_forbidden_term(value: str) -> bool:
    return any(term in value for term in FORBIDDEN_STUDENT_TERMS)


def _has_destiny_term(value: str) -> bool:
    return any(term in value for term in DESTINY_TERMS)


def _canonical_topic_title(title: str, text: str) -> str:
    haystack = f"{title}\n{text}"
    for term in PROMOTED_TOPIC_TERMS:
        if term in haystack:
            return term
    return title


def _slug(value: Any) -> str:
    text = str(value or "").strip().lower()
    ascii_text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    if ascii_text:
        return ascii_text[:48]
    digest = blake2s(text.encode("utf-8"), digest_size=5).hexdigest()
    return f"zh-{digest}"


def _short_topic(value: str, limit: int = 18) -> str:
    text = re.sub(r"[，。、“”‘’：；！？\s]+", "", str(value or ""))
    return text[:limit] or str(value or "").strip()[:limit]


def _topic_rank_key(topic: dict[str, Any]) -> tuple[int, str, str]:
    return (-_topic_score(topic), str(topic.get("title", "")), str(topic.get("id", "")))


def _topic_score(topic: dict[str, Any]) -> int:
    title = str(topic.get("title", ""))
    category = str(topic.get("category", ""))
    score = 100 * len(topic.get("evidence_ids") or [])
    score += 40 * len(topic.get("relation_ids") or [])
    score += 5 * len(topic.get("card_ids") or [])
    if title in PROMOTED_TOPIC_TERMS:
        score += 10_000
    if category == "人物关系" and "与" not in title:
        score += 300
    if len(title) > 24:
        score -= 100
    if any(mark in title for mark in ("——", "：", "；")):
        score -= 50
    return score


def _is_publishable_generated_topic(topic: dict[str, Any]) -> bool:
    category = str(topic.get("category", ""))
    if category != "关键事件":
        return True
    title = str(topic.get("title", ""))
    if title in PROMOTED_TOPIC_TERMS:
        return True
    if len(topic.get("quotable_fact_ids") or []) >= 2:
        return True
    return bool(topic.get("relation_ids"))


def _join_parts(*parts: Any) -> str:
    values: list[str] = []
    for part in parts:
        if part is None:
            continue
        if isinstance(part, list):
            values.extend(str(item).strip() for item in part if str(item).strip())
            continue
        text = str(part).strip()
        if text:
            values.append(text)
    return "；".join(values)


def _excerpt_around_term(value: str, term: str, limit: int = 360) -> str:
    text = _compact_text(value)
    clean_term = str(term or "").strip()
    if not text or not clean_term:
        return ""
    index = text.find(clean_term)
    if index == -1:
        return ""
    sentence_start = max(text.rfind(mark, 0, index) for mark in ("。", "；", "！", "？", "\n"))
    start = sentence_start + 1 if sentence_start >= 0 else 0
    while start < len(text) and text[start] in " ：，、":
        start += 1
    sentence_end_candidates = [text.find(mark, index) for mark in ("。", "；", "！", "？", "\n")]
    sentence_end = min([candidate for candidate in sentence_end_candidates if candidate != -1], default=-1)
    if sentence_end == -1:
        sentence_end = min(len(text), start + limit)
    excerpt = text[start : sentence_end + 1].strip()
    if len(excerpt) <= limit:
        return excerpt
    boundary = max(excerpt.rfind(mark, 0, limit) for mark in ("。", "；", "！", "？"))
    if boundary >= limit // 2:
        return excerpt[: boundary + 1]
    return excerpt[:limit].rstrip() + "..."


def _compact_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _limit_unique(items: list[str | None], limit: int) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        if item is None:
            continue
        value = str(item)
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
        if len(result) >= limit:
            break
    return result


def _topic_description(category: str, title: str) -> str:
    if category == "人物关系":
        return f"围绕{title}的人物关系与章回依据组织。"
    if category == "关键事件":
        return f"围绕{title}的起因、经过、结果和章回出处组织。"
    if category == "判词命运":
        return f"围绕{title}涉及的诗词曲文、命运线索和章回依据组织。"
    if category == "意象伏笔":
        return f"围绕{title}的意象、伏笔和相关章回组织。"
    return f"整理{title}中可定位到章回的事实材料。"


def _looks_like_person(name: str) -> bool:
    return len(name) <= 4 and not any(term in name for term in ("花", "玉", "梦", "诗", "园", "府", "院", "亭", "石", "镜"))
