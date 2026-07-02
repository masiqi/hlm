from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from hlm_kg.domain import (
    Chapter,
    ChapterAnnotation,
    ChapterReviewCard,
    Evidence,
    GraphRelation,
    KnowledgeCard,
    ProcessedMaterialSource,
    Topic,
    TraceItem,
)


class ContentStore:
    def __init__(
        self,
        *,
        chapters: dict[int, Chapter],
        review_cards: dict[int, ChapterReviewCard],
        knowledge_cards: dict[str, KnowledgeCard],
        graph_relations: dict[str, GraphRelation],
        topics: dict[str, Topic],
        common_entries: list[dict[str, Any]],
        evidence: dict[str, Evidence],
    ) -> None:
        self._chapters = chapters
        self._review_cards = review_cards
        self._knowledge_cards = knowledge_cards
        self._graph_relations = graph_relations
        self._topics = topics
        self.common_entries = common_entries
        self._evidence = evidence

    @classmethod
    def from_paths(cls, manifest_path: Path, data_dir: Path) -> ContentStore:
        manifest = _read_json(manifest_path)
        chapters = {
            int(item["number"]): Chapter(
                id=f"chapter-{int(item['number']):03d}",
                number=int(item["number"]),
                title=str(item["title"]),
                original_text_path=str(item["file_path"]),
                review_card_id=f"review-{int(item['number']):03d}",
            )
            for item in manifest["chapters"]
        }

        review_cards = {
            int(item["chapter"]): ChapterReviewCard(
                id=str(item["id"]),
                chapter=int(item["chapter"]),
                source=ProcessedMaterialSource(
                    prompt_name=str(item["source"]["prompt_name"]),
                    prompt_version=str(item["source"]["prompt_version"]),
                    generated_at=item["source"].get("generated_at"),
                ),
                plain_summary=str(item["plain_summary"]),
                plot_chain=list(item.get("plot_chain", [])),
                key_events=list(item.get("key_events", [])),
                key_characters=list(item.get("key_characters", [])),
                current_chapter_foreshadowing_signals=list(item.get("current_chapter_foreshadowing_signals", [])),
                later_association_relation_ids=list(item.get("later_association_relation_ids", [])),
                quotable_fact_ids=list(item.get("quotable_fact_ids", [])),
                retrieval_tags=list(item.get("retrieval_tags", [])),
                understanding_focus=list(item.get("understanding_focus", [])),
                characters=list(item.get("characters", [])),
                relationships=list(item.get("relationships", [])),
                places=list(item.get("places", [])),
                objects=list(item.get("objects", [])),
                literary_texts=list(item.get("literary_texts", [])),
                modern_explanations=list(item.get("modern_explanations", [])),
                later_associations=list(item.get("later_associations", [])),
                annotations=list(item.get("annotations", [])),
            )
            for item in _read_json(data_dir / "chapter_review_cards.json")
        }
        knowledge_cards = {
            str(item["id"]): KnowledgeCard(
                id=str(item["id"]),
                name=str(item["name"]),
                type=item["type"],
                brief=str(item["brief"]),
                text_understanding=list(item.get("text_understanding", [])),
                understanding_angles=list(item.get("understanding_angles", [])),
                graph_relation_ids=list(item.get("graph_relation_ids", [])),
                evidence_ids=list(item.get("evidence_ids", [])),
                related_card_ids=list(item.get("related_card_ids", [])),
            )
            for item in _read_json(data_dir / "knowledge_cards.json")
        }
        graph_relations = {
            str(item["id"]): GraphRelation(
                id=str(item["id"]),
                subject_id=str(item["subject_id"]),
                predicate=str(item["predicate"]),
                object_id=str(item["object_id"]),
                chapters=[int(chapter) for chapter in item.get("chapters", [])],
                evidence_ids=list(item.get("evidence_ids", [])),
                provenance=item.get("provenance", "curated"),
                description=str(item["description"]),
            )
            for item in _read_json(data_dir / "graph_relations.json")
        }
        topics = {
            str(item["id"]): Topic(
                id=str(item["id"]),
                title=str(item["title"]),
                category=item["category"],
                description=str(item["description"]),
                card_ids=list(item.get("card_ids", [])),
                relation_ids=list(item.get("relation_ids", [])),
                typical_question_patterns=list(item.get("typical_question_patterns", [])),
                quotable_fact_ids=list(item.get("quotable_fact_ids", [])),
                evidence_ids=list(item.get("evidence_ids", [])),
            )
            for item in _read_json(data_dir / "topics.json")
        }
        common_entries = list(_read_json(data_dir / "common_entries.json"))
        evidence = {
            str(item["id"]): Evidence(
                id=str(item["id"]),
                source_type=item["source_type"],
                chapter=item.get("chapter"),
                location=item.get("location"),
                quote=item.get("quote"),
                evidence_text=str(item["evidence_text"]),
                entity_ids=list(item.get("entity_ids", [])),
                relation_id=item.get("relation_id"),
                confidence=item["confidence"],
                provenance=str(item["provenance"]),
                derived_from_ids=list(item.get("derived_from_ids", [])),
            )
            for item in _read_json(data_dir / "evidence.json")
        }
        return cls(
            chapters=chapters,
            review_cards=review_cards,
            knowledge_cards=knowledge_cards,
            graph_relations=graph_relations,
            topics=topics,
            common_entries=common_entries,
            evidence=evidence,
        )

    def chapter(self, number: int) -> Chapter:
        return self._chapters[number]

    def chapter_text(self, number: int) -> str:
        return Path(self.chapter(number).original_text_path).read_text(encoding="utf-8")

    def review_card_for_chapter(self, number: int) -> ChapterReviewCard:
        return self._review_cards[number]

    def maybe_review_card_for_chapter(self, number: int) -> ChapterReviewCard | None:
        return self._review_cards.get(number)

    def evidence_by_id(self) -> dict[str, Evidence]:
        return dict(self._evidence)

    def evidence(self, evidence_id: str) -> Evidence:
        return self._evidence[evidence_id]

    def knowledge_card(self, card_id: str) -> KnowledgeCard:
        return self._knowledge_cards[card_id]

    def topic(self, topic_id: str) -> Topic:
        return self._topics[topic_id]

    def graph_relation(self, relation_id: str) -> GraphRelation:
        return self._graph_relations[relation_id]

    def annotations_for_chapter(self, number: int) -> list[ChapterAnnotation]:
        review_card = self.maybe_review_card_for_chapter(number)
        if review_card is None:
            return []
        text = self.chapter_text(number)
        cards = [self._knowledge_cards[card_id] for card_id in review_card.key_characters if card_id in self._knowledge_cards]
        annotations: list[ChapterAnnotation] = []
        for card in sorted(cards, key=lambda item: len(item.name), reverse=True):
            start = 0
            while True:
                index = text.find(card.name, start)
                if index == -1:
                    break
                annotations.append(
                    ChapterAnnotation(
                        id=f"ann-{number:03d}-{card.id}-{index}",
                        chapter=number,
                        start_offset=index,
                        end_offset=index + len(card.name),
                        surface_text=card.name,
                        annotation_type=card.type,
                        entity_id=card.id,
                        relation_id=None,
                        evidence_id=None,
                        display_priority=100,
                    )
                )
                start = index + len(card.name)
        return sorted(annotations, key=lambda item: (item.start_offset, item.end_offset))

    def trace_items_for_entity(self, entity_id: str) -> list[TraceItem]:
        card = self.knowledge_card(entity_id)
        items: list[TraceItem] = []
        order = 0
        for relation_id in card.graph_relation_ids:
            relation = self._graph_relations.get(relation_id)
            if relation is None:
                continue
            evidence_id = next((item for item in relation.evidence_ids if item in self._evidence), None)
            evidence = self._evidence.get(evidence_id) if evidence_id else None
            chapter = relation.chapters[0] if relation.chapters else evidence.chapter if evidence else None
            if chapter is None:
                continue
            items.append(
                TraceItem(
                    id=f"trace-{entity_id}-{relation.id}",
                    entity_id=entity_id,
                    chapter=int(chapter),
                    relation_id=relation.id,
                    evidence_id=evidence_id,
                    title=f"第{int(chapter)}回线索",
                    description=relation.description,
                    trace_type="relation",
                    sort_order=order,
                    importance=80,
                )
            )
            order += 1
        for evidence_id in card.evidence_ids:
            evidence = self._evidence.get(evidence_id)
            if evidence is None or evidence.chapter is None:
                continue
            trace_id = f"trace-{entity_id}-{evidence.id}"
            if any(item.id == trace_id for item in items):
                continue
            items.append(
                TraceItem(
                    id=trace_id,
                    entity_id=entity_id,
                    chapter=int(evidence.chapter),
                    relation_id=evidence.relation_id,
                    evidence_id=evidence.id,
                    title=f"第{int(evidence.chapter)}回依据",
                    description=evidence.evidence_text,
                    trace_type="evidence",
                    sort_order=order,
                    importance=60,
                )
            )
            order += 1
        return items

    @property
    def topics(self) -> list[Topic]:
        return list(self._topics.values())

    @property
    def knowledge_cards(self) -> list[KnowledgeCard]:
        return list(self._knowledge_cards.values())

    @property
    def graph_relations(self) -> list[GraphRelation]:
        return list(self._graph_relations.values())


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))
