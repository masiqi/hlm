from __future__ import annotations

from typing import Any, Protocol

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


class RowFetcher(Protocol):
    def __call__(self, query: str, params: tuple[Any, ...]) -> list[dict[str, Any]]: ...


class PostgresContentStore:
    def __init__(self, database_url: str, fallback_store: Any | None = None, fetcher: RowFetcher | None = None) -> None:
        self.database_url = database_url
        self.fallback_store = fallback_store
        self._fetcher = fetcher
        self.common_entries = list(getattr(fallback_store, "common_entries", []))
        self._review_card_scan_cache: list[ChapterReviewCard] | None = None
        self._entity_trace_chapter_cache: dict[int, dict[str, dict[str, Any]]] = {}
        self._entity_graph_cache: dict[str, dict[str, Any]] = {}
        self._entity_graph_description_cache: dict[str, str] = {}

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
        return _review_card_from_row(row)

    def review_cards_for_trace_scan(self) -> list[ChapterReviewCard]:
        if self._review_card_scan_cache is None:
            rows = self._fetchall(
                """
                SELECT cc.*, c.number AS chapter_number
                FROM chapter_cards cc
                JOIN chapters c ON c.id = cc.chapter_id
                ORDER BY c.number
                """
            )
            self._review_card_scan_cache = [_review_card_from_row(row) for row in rows]
        return list(self._review_card_scan_cache)

    def evidence_by_id(self) -> dict[str, Evidence]:
        return {item.id: item for item in self._all_evidence()}

    def evidence(self, evidence_id: str) -> Evidence:
        row = self._maybe_one(
            """
            SELECT e.*, c.number AS chapter_number
            FROM evidence e
            LEFT JOIN chapters c ON c.id = e.chapter_id
            WHERE e.id = %s
            """,
            (evidence_id,),
        )
        if row is None:
            if self.fallback_store is not None:
                return self.fallback_store.evidence(evidence_id)
            raise KeyError(evidence_id)
        return _evidence_from_row(row)

    def knowledge_card(self, card_id: str) -> KnowledgeCard:
        row = self._maybe_one("SELECT * FROM entities WHERE id = %s", (card_id,))
        if row is None:
            if self.fallback_store is not None:
                return self.fallback_store.knowledge_card(card_id)
            raise KeyError(card_id)
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
        row = self._maybe_one("SELECT * FROM relations WHERE id = %s", (relation_id,))
        if row is None:
            if self.fallback_store is not None:
                return self.fallback_store.graph_relation(relation_id)
            raise KeyError(relation_id)
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

    def entity_trace_payload(self, name: str, current_chapter: int | None) -> dict[str, Any] | None:
        if current_chapter is None:
            return None
        row = self._maybe_one(
            """
            SELECT etc.trace_items, etc.theme_extensions
            FROM entity_trace_cache etc
            JOIN chapters c ON c.id = etc.chapter_id
            WHERE etc.entity_name = %s AND c.number = %s
            """,
            (name, current_chapter),
        )
        if row is None:
            return None
        return {
            "trace_items": list(row.get("trace_items") or []),
            "theme_extensions": list(row.get("theme_extensions") or []),
        }

    def entity_trace_payloads_for_chapter(self, current_chapter: int | None) -> dict[str, dict[str, Any]] | None:
        if current_chapter is None:
            return None
        chapter = int(current_chapter)
        if chapter not in self._entity_trace_chapter_cache:
            rows = self._fetchall(
                """
                SELECT etc.entity_name, etc.trace_items, etc.theme_extensions
                FROM entity_trace_cache etc
                JOIN chapters c ON c.id = etc.chapter_id
                WHERE c.number = %s
                """,
                (chapter,),
            )
            self._entity_trace_chapter_cache[chapter] = {
                str(row["entity_name"]): {
                    "trace_items": list(row.get("trace_items") or []),
                    "theme_extensions": list(row.get("theme_extensions") or []),
                }
                for row in rows
            }
        return dict(self._entity_trace_chapter_cache[chapter])

    def entity_graph_payloads_for_names(self, names: list[str]) -> dict[str, dict[str, Any]]:
        clean_names = [str(name or "").strip() for name in names if str(name or "").strip()]
        unique_names = list(dict.fromkeys(clean_names))
        missing_names = [name for name in unique_names if name not in self._entity_graph_cache]
        if missing_names:
            rows = self._fetchall(
                """
                SELECT entity_name, description, neighbors, extended_neighbors, raw_graph, metadata
                FROM entity_graph_cache
                WHERE entity_name = ANY(%s)
                """,
                (missing_names,),
            )
            for row in rows:
                self._entity_graph_cache[str(row["entity_name"])] = {
                    "description": str(row.get("description") or ""),
                    "neighbors": list(row.get("neighbors") or []),
                    "extended_neighbors": list(row.get("extended_neighbors") or []),
                    "raw_graph": dict(row.get("raw_graph") or {}),
                    "metadata": dict(row.get("metadata") or {}),
                }
        return {
            name: dict(self._entity_graph_cache[name])
            for name in unique_names
            if name in self._entity_graph_cache
        }

    def entity_graph_descriptions_for_names(self, names: list[str]) -> dict[str, str]:
        clean_names = [str(name or "").strip() for name in names if str(name or "").strip()]
        unique_names = list(dict.fromkeys(clean_names))
        missing_names = [name for name in unique_names if name not in self._entity_graph_description_cache]
        if missing_names:
            rows = self._fetchall(
                """
                SELECT entity_name, description
                FROM entity_graph_cache
                WHERE entity_name = ANY(%s)
                """,
                (missing_names,),
            )
            for row in rows:
                description = str(row.get("description") or "").strip()
                if description:
                    self._entity_graph_description_cache[str(row["entity_name"])] = description
        return {
            name: self._entity_graph_description_cache[name]
            for name in unique_names
            if name in self._entity_graph_description_cache
        }

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
        if self._fetcher is not None:
            return self._fetcher(query, params)
        import psycopg
        from psycopg.rows import dict_row

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


def _review_card_from_row(row: dict[str, Any]) -> ChapterReviewCard:
    raw_card = dict(row.get("raw_card") or {})
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
        characters=list(raw_card.get("characters", [])),
        relationships=list(raw_card.get("relationships", [])),
        places=list(raw_card.get("places", [])),
        objects=list(raw_card.get("objects", [])),
        literary_texts=list(raw_card.get("literary_texts", [])),
        modern_explanations=list(raw_card.get("modern_explanations", [])),
        later_associations=list(raw_card.get("later_associations", [])),
        annotations=list(raw_card.get("annotations", [])),
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
