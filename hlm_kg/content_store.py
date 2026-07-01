from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from hlm_kg.domain import Chapter, ChapterReviewCard, GraphRelation, KnowledgeCard, ProcessedMaterialSource, Topic


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
    ) -> None:
        self._chapters = chapters
        self._review_cards = review_cards
        self._knowledge_cards = knowledge_cards
        self._graph_relations = graph_relations
        self._topics = topics
        self.common_entries = common_entries

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
        return cls(
            chapters=chapters,
            review_cards=review_cards,
            knowledge_cards=knowledge_cards,
            graph_relations=graph_relations,
            topics=topics,
            common_entries=common_entries,
        )

    def chapter(self, number: int) -> Chapter:
        return self._chapters[number]

    def chapter_text(self, number: int) -> str:
        return Path(self.chapter(number).original_text_path).read_text(encoding="utf-8")

    def review_card_for_chapter(self, number: int) -> ChapterReviewCard:
        return self._review_cards[number]

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
