from __future__ import annotations

from typing import Any

import psycopg
from psycopg.rows import dict_row

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


class PostgresContentStore:
    def __init__(self, database_url: str, fallback_store: Any | None = None) -> None:
        self.database_url = database_url
        self.fallback_store = fallback_store
        self.common_entries = list(getattr(fallback_store, "common_entries", []))

    def chapter(self, number: int) -> Chapter:
        row = self._fetchone("SELECT * FROM chapters WHERE number = %s", (number,))
        return Chapter(
            id=str(row["id"]),
            number=int(row["number"]),
            title=str(row["title"]),
            original_text_path=str(row["source_file"]),
            review_card_id=f"review-{int(row['number']):03d}",
        )

    def chapter_text(self, number: int) -> str:
        row = self._fetchone("SELECT original_text FROM chapters WHERE number = %s", (number,))
        return str(row["original_text"])

    def review_card_for_chapter(self, number: int) -> ChapterReviewCard:
        card = self.maybe_review_card_for_chapter(number)
        if card is None:
            raise KeyError(number)
        return card

    def maybe_review_card_for_chapter(self, number: int) -> ChapterReviewCard | None:
        row = self._maybe_one(
            """
            SELECT cc.*, c.number AS chapter_number
            FROM chapter_cards cc
            JOIN chapters c ON c.id = cc.chapter_id
            WHERE c.number = %s
            """,
            (number,),
        )
        if row is None:
            return None
        return ChapterReviewCard(
            id=str(row["id"]),
            chapter=int(row["chapter_number"]),
            source=ProcessedMaterialSource(
                prompt_name=str(row["prompt_name"]),
                prompt_version=str(row["prompt_version"]),
                generated_at=row.get("generated_at"),
            ),
            plain_summary=str(row["summary"]),
            plot_chain=list(row["plot_chain"] or []),
            key_events=list(row["key_events"] or []),
            key_characters=list(row["key_characters"] or []),
            current_chapter_foreshadowing_signals=list(row["foreshadowing"] or []),
            later_association_relation_ids=list(row["later_association_relation_ids"] or []),
            quotable_fact_ids=list(row["quotable_fact_ids"] or []),
            retrieval_tags=list(row["retrieval_tags"] or []),
            understanding_focus=list(row["understanding_focus"] or []),
        )

    def evidence_by_id(self) -> dict[str, Evidence]:
        return {item.id: item for item in self._all_evidence()}

    def evidence(self, evidence_id: str) -> Evidence:
        row = self._fetchone(
            """
            SELECT e.*, c.number AS chapter_number
            FROM evidence e
            LEFT JOIN chapters c ON c.id = e.chapter_id
            WHERE e.id = %s
            """,
            (evidence_id,),
        )
        return _evidence_from_row(row)

    def knowledge_card(self, card_id: str) -> KnowledgeCard:
        row = self._fetchone("SELECT * FROM entities WHERE id = %s", (card_id,))
        metadata = dict(row["metadata"] or {})
        return KnowledgeCard(
            id=str(row["id"]),
            name=str(row["name"]),
            type=row["type"],
            brief=str(row["brief"]),
            text_understanding=list(metadata.get("text_understanding", [])),
            understanding_angles=list(metadata.get("understanding_angles", [])),
            graph_relation_ids=[relation.id for relation in self._relations_for_entity(card_id)],
            evidence_ids=[item.id for item in self._evidence_for_entity(card_id)],
            related_card_ids=list(metadata.get("related_card_ids", [])),
        )

    def topic(self, topic_id: str) -> Topic:
        if self.fallback_store is None:
            raise KeyError(topic_id)
        return self.fallback_store.topic(topic_id)

    def graph_relation(self, relation_id: str) -> GraphRelation:
        row = self._fetchone("SELECT * FROM relations WHERE id = %s", (relation_id,))
        return _relation_from_row(row)

    def annotations_for_chapter(self, number: int) -> list[ChapterAnnotation]:
        rows = self._fetchall(
            """
            SELECT ca.*, c.number AS chapter_number
            FROM chapter_annotations ca
            JOIN chapters c ON c.id = ca.chapter_id
            WHERE c.number = %s
            ORDER BY ca.start_offset, ca.end_offset
            """,
            (number,),
        )
        return [
            ChapterAnnotation(
                id=str(row["id"]),
                chapter=int(row["chapter_number"]),
                start_offset=int(row["start_offset"]),
                end_offset=int(row["end_offset"]),
                surface_text=str(row["surface_text"]),
                annotation_type=str(row["annotation_type"]),
                entity_id=row.get("entity_id"),
                relation_id=row.get("relation_id"),
                evidence_id=row.get("evidence_id"),
                display_priority=int(row["display_priority"]),
            )
            for row in rows
        ]

    def trace_items_for_entity(self, entity_id: str) -> list[TraceItem]:
        rows = self._fetchall(
            """
            SELECT ti.*, c.number AS chapter_number
            FROM trace_items ti
            JOIN chapters c ON c.id = ti.chapter_id
            WHERE ti.entity_id = %s
            ORDER BY ti.sort_order, c.number, ti.id
            """,
            (entity_id,),
        )
        return [
            TraceItem(
                id=str(row["id"]),
                entity_id=str(row["entity_id"]),
                chapter=int(row["chapter_number"]),
                relation_id=row.get("relation_id"),
                evidence_id=row.get("evidence_id"),
                title=str(row["title"]),
                description=str(row["description"]),
                trace_type=str(row["trace_type"]),
                sort_order=int(row["sort_order"]),
                importance=int(row["importance"]),
            )
            for row in rows
        ]

    @property
    def topics(self) -> list[Topic]:
        return list(getattr(self.fallback_store, "topics", []))

    @property
    def knowledge_cards(self) -> list[KnowledgeCard]:
        return [self.knowledge_card(str(row["id"])) for row in self._fetchall("SELECT id FROM entities ORDER BY id")]

    @property
    def graph_relations(self) -> list[GraphRelation]:
        return [_relation_from_row(row) for row in self._fetchall("SELECT * FROM relations ORDER BY id")]

    def _relations_for_entity(self, entity_id: str) -> list[GraphRelation]:
        rows = self._fetchall(
            """
            SELECT *
            FROM relations
            WHERE subject_entity_id = %s OR object_entity_id = %s
            ORDER BY id
            """,
            (entity_id, entity_id),
        )
        return [_relation_from_row(row) for row in rows]

    def _evidence_for_entity(self, entity_id: str) -> list[Evidence]:
        rows = self._fetchall(
            """
            SELECT e.*, c.number AS chapter_number
            FROM evidence e
            LEFT JOIN chapters c ON c.id = e.chapter_id
            WHERE e.entity_ids ? %s
            ORDER BY e.id
            """,
            (entity_id,),
        )
        return [_evidence_from_row(row) for row in rows]

    def _all_evidence(self) -> list[Evidence]:
        rows = self._fetchall(
            """
            SELECT e.*, c.number AS chapter_number
            FROM evidence e
            LEFT JOIN chapters c ON c.id = e.chapter_id
            ORDER BY e.id
            """
        )
        return [_evidence_from_row(row) for row in rows]

    def _fetchone(self, query: str, params: tuple[Any, ...] = ()) -> dict[str, Any]:
        row = self._maybe_one(query, params)
        if row is None:
            raise KeyError(query)
        return row

    def _maybe_one(self, query: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        rows = self._fetchall(query, params)
        return rows[0] if rows else None

    def _fetchall(self, query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        with psycopg.connect(self.database_url, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                return list(cur.fetchall())


def _relation_from_row(row: dict[str, Any]) -> GraphRelation:
    return GraphRelation(
        id=str(row["id"]),
        subject_id=str(row["subject_entity_id"]),
        predicate=str(row["predicate"]),
        object_id=str(row["object_entity_id"]),
        chapters=[int(chapter) for chapter in list(row["chapters"] or [])],
        evidence_ids=list(row["evidence_ids"] or []),
        provenance=row.get("provenance", "curated"),
        description=str(row["description"]),
    )


def _evidence_from_row(row: dict[str, Any]) -> Evidence:
    chapter_number = row.get("chapter_number")
    return Evidence(
        id=str(row["id"]),
        source_type=row["source_type"],
        chapter=int(chapter_number) if chapter_number is not None else None,
        location=row.get("location"),
        quote=row.get("quote"),
        evidence_text=str(row["evidence_text"]),
        entity_ids=list(row["entity_ids"] or []),
        relation_id=row.get("relation_id"),
        confidence=row["confidence"],
        provenance=str(row["provenance"]),
        derived_from_ids=list(row["derived_from_ids"] or []),
    )
