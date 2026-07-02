from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from hlm_kg.chapter_sources import ChapterSource, parse_chapter_sources


_SOURCE_SEPARATOR = "<SEP>"


@dataclass(frozen=True)
class EvidenceCandidate:
    kind: str
    title: str
    description: str
    query_mode: str | None
    file_paths: list[str] = field(default_factory=list)
    source_ids: list[str] = field(default_factory=list)
    chapter_sources: list[ChapterSource] = field(default_factory=list)
    reference_id: str | None = None
    chunk_id: str | None = None
    entity_type: str | None = None
    relationship_keywords: str | None = None
    raw: Mapping[str, Any] = field(default_factory=dict)
    score: int = 0


def normalize_query_data_response(response: Mapping[str, Any], question: str = "") -> list[EvidenceCandidate]:
    if response.get("status") == "failure":
        return []
    data = response.get("data")
    if not isinstance(data, Mapping):
        return []

    query_mode = _query_mode(response)
    question_terms = _question_terms(question)
    candidates: list[EvidenceCandidate] = []
    candidates.extend(_entity_candidates(data.get("entities"), query_mode, question_terms))
    candidates.extend(_relationship_candidates(data.get("relationships"), query_mode, question_terms))
    candidates.extend(_chunk_candidates(data.get("chunks"), query_mode, question_terms))
    candidates.extend(_reference_candidates(data.get("references"), query_mode, question_terms))
    return sorted(candidates, key=lambda candidate: candidate.score, reverse=True)


def _entity_candidates(raw_entities: object, query_mode: str | None, question_terms: set[str]) -> list[EvidenceCandidate]:
    if not isinstance(raw_entities, list):
        return []
    candidates: list[EvidenceCandidate] = []
    for item in raw_entities:
        if not isinstance(item, Mapping):
            continue
        title = str(item.get("entity_name") or "").strip()
        if not title:
            continue
        description = str(item.get("description") or "")
        candidate = _candidate(
            kind="entity",
            title=title,
            description=description,
            query_mode=query_mode,
            item=item,
            question_terms=question_terms,
            entity_type=_optional_str(item.get("entity_type")),
        )
        candidates.append(candidate)
    return candidates


def _relationship_candidates(raw_relationships: object, query_mode: str | None, question_terms: set[str]) -> list[EvidenceCandidate]:
    if not isinstance(raw_relationships, list):
        return []
    candidates: list[EvidenceCandidate] = []
    for item in raw_relationships:
        if not isinstance(item, Mapping):
            continue
        src_id = str(item.get("src_id") or "").strip()
        tgt_id = str(item.get("tgt_id") or "").strip()
        if not src_id and not tgt_id:
            continue
        title = f"{src_id} -> {tgt_id}" if src_id and tgt_id else src_id or tgt_id
        candidate = _candidate(
            kind="relationship",
            title=title,
            description=str(item.get("description") or ""),
            query_mode=query_mode,
            item=item,
            question_terms=question_terms,
            relationship_keywords=_optional_str(item.get("keywords")),
        )
        candidates.append(candidate)
    return candidates


def _chunk_candidates(raw_chunks: object, query_mode: str | None, question_terms: set[str]) -> list[EvidenceCandidate]:
    if not isinstance(raw_chunks, list):
        return []
    candidates: list[EvidenceCandidate] = []
    for item in raw_chunks:
        if not isinstance(item, Mapping):
            continue
        content = str(item.get("content") or "")
        file_path = str(item.get("file_path") or "")
        title = file_path or str(item.get("chunk_id") or "").strip()
        if not title and not content:
            continue
        candidate = _candidate(
            kind="chunk",
            title=title,
            description=content,
            query_mode=query_mode,
            item=item,
            question_terms=question_terms,
            reference_id=_optional_str(item.get("reference_id")),
            chunk_id=_optional_str(item.get("chunk_id")),
        )
        candidates.append(candidate)
    return candidates


def _reference_candidates(raw_references: object, query_mode: str | None, question_terms: set[str]) -> list[EvidenceCandidate]:
    if not isinstance(raw_references, list):
        return []
    candidates: list[EvidenceCandidate] = []
    for item in raw_references:
        if not isinstance(item, Mapping):
            continue
        file_path = str(item.get("file_path") or "")
        if not file_path:
            continue
        candidate = _candidate(
            kind="reference",
            title=file_path,
            description=file_path,
            query_mode=query_mode,
            item=item,
            question_terms=question_terms,
            reference_id=_optional_str(item.get("reference_id")),
        )
        candidates.append(candidate)
    return candidates


def _candidate(
    *,
    kind: str,
    title: str,
    description: str,
    query_mode: str | None,
    item: Mapping[str, Any],
    question_terms: set[str],
    reference_id: str | None = None,
    chunk_id: str | None = None,
    entity_type: str | None = None,
    relationship_keywords: str | None = None,
) -> EvidenceCandidate:
    file_paths = _split_sep(item.get("file_path"))
    source_ids = _split_sep(item.get("source_id"))
    chapter_sources = parse_chapter_sources(item.get("file_path") if isinstance(item.get("file_path"), str) else None)
    score = _score_candidate(kind, title, description, chapter_sources, question_terms)
    return EvidenceCandidate(
        kind=kind,
        title=title,
        description=description,
        query_mode=query_mode,
        file_paths=file_paths,
        source_ids=source_ids,
        chapter_sources=chapter_sources,
        reference_id=reference_id,
        chunk_id=chunk_id,
        entity_type=entity_type,
        relationship_keywords=relationship_keywords,
        raw=dict(item),
        score=score,
    )


def _score_candidate(
    kind: str,
    title: str,
    description: str,
    chapter_sources: list[ChapterSource],
    question_terms: set[str],
) -> int:
    score = {"relationship": 30, "entity": 20, "chunk": 15, "reference": 5}.get(kind, 0)
    if chapter_sources:
        score += 20
    haystack = f"{title}\n{description}"
    score += sum(5 for term in question_terms if term and term in haystack)
    return score


def _query_mode(response: Mapping[str, Any]) -> str | None:
    metadata = response.get("metadata")
    if not isinstance(metadata, Mapping):
        return None
    mode = metadata.get("query_mode")
    return str(mode) if mode is not None else None


def _split_sep(value: object) -> list[str]:
    if not isinstance(value, str) or not value:
        return []
    parts: list[str] = []
    seen: set[str] = set()
    for raw_part in value.split(_SOURCE_SEPARATOR):
        part = raw_part.strip()
        if not part or part in seen:
            continue
        seen.add(part)
        parts.append(part)
    return parts


def _question_terms(question: str) -> set[str]:
    compact = question.strip()
    terms = {compact} if compact else set()
    for token in ("宝黛初会", "林黛玉", "贾宝玉", "宝玉", "黛玉", "初会", "章回", "亲密"):
        if token in compact:
            terms.add(token)
    return terms


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None
