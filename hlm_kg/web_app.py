from __future__ import annotations

import json
import os
import re
import socket
from dataclasses import asdict, dataclass, field
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import parse_qs, urlparse

from hlm_kg.ask_engine import AskEngine
from hlm_kg.chapter_sources import ChapterSource, parse_chapter_sources
from hlm_kg.content_store import ContentStore
from hlm_kg.domain import ChapterReviewCard
from hlm_kg.evidence_adapter import EvidenceCandidate, normalize_query_data_response
from hlm_kg.evidence_judge import build_evidence_judge_from_env
from hlm_kg.lightrag_client import LightRAGClient, LightRAGConfig
from hlm_kg.postgres_config import load_database_url, load_dotenv, parse_bool
from hlm_kg.semantic_question_analyzer import build_question_analyzer_from_env


INLINE_ENTITY_MAX_CHAPTER_JUMPS = 12
INLINE_ENTITY_CLUE_DESCRIPTION_LENGTH = 240
INLINE_ENTITY_JUMP_DESCRIPTION_LENGTH = 96
INLINE_ENTITY_MAX_GRAPH_NEIGHBORS = 16
INLINE_ENTITY_MAX_EXTENDED_NEIGHBORS = 8
GRAPH_ALIAS_RELATION_FRAGMENTS = (
    "别名",
    "别称",
    "俗称",
    "昵称",
    "称呼",
    "称谓",
    "指代",
    "指称",
    "绰号",
    "雅号",
    "尊称",
    "敬称",
    "简称",
    "本名",
    "等同",
)
GRAPH_GENERIC_RELATION_TOKENS = {"人物关系", "人物关联", "关系", "关联"}
TOPIC_CATEGORY_ORDER = ["人物关系", "关键事件", "判词命运", "意象伏笔", "可引用事实"]
TOPIC_CATEGORY_DESCRIPTIONS = {
    "人物关系": "围绕人物、亲属、婚恋、主仆、称谓和对照关系组织。",
    "关键事件": "围绕重要情节的起因、经过、结果和章回出处组织。",
    "判词命运": "围绕诗词判语、命运照应和人物归宿组织。",
    "意象伏笔": "围绕物件、场景、诗文意象和跨章伏笔组织。",
    "可引用事实": "围绕可直接引用的事实依据组织。",
}


@dataclass(frozen=True)
class AppContext:
    store: Any
    ask_engine: AskEngine
    static_dir: Path
    retrieval_client: Any | None = None
    chapter_response_cache: dict[int, dict[str, Any]] = field(default_factory=dict)


def create_app_context(
    manifest_path: Path,
    data_dir: Path,
    static_dir: Path,
    retrieval_client: Any | None = None,
    semantic_analyzer: Any | None = None,
    evidence_judge: Any | None = None,
    *,
    use_env_retrieval: bool = False,
    use_env_question_analyzer: bool = False,
    use_env_evidence_judge: bool = False,
    use_env_content_store: bool = False,
    use_postgres_store: bool = False,
) -> AppContext:
    dotenv = load_dotenv()
    postgres_setting = ""
    if use_env_content_store:
        postgres_setting = str(os.environ.get("HLM_CONTENT_STORE", dotenv.get("HLM_CONTENT_STORE", ""))).strip().lower()
    postgres_enabled = use_postgres_store or postgres_setting == "postgres" or parse_bool(postgres_setting)
    database_url = (load_database_url() or load_database_url(dotenv)) if postgres_enabled else None
    if postgres_enabled and database_url is None:
        raise RuntimeError("DATABASE_URL is not set for PostgreSQL content store")
    json_store = ContentStore.from_paths(manifest_path, data_dir, load_entity_caches=not postgres_enabled)
    store: Any = json_store
    if postgres_enabled:
        store = PostgresContentStore(database_url, fallback_store=json_store)
    if retrieval_client is None and use_env_retrieval:
        retrieval_env = {**dotenv, **os.environ}
        config = LightRAGConfig.from_env(retrieval_env)
        retrieval_client = LightRAGClient(config) if config is not None else None
    if semantic_analyzer is None and use_env_question_analyzer:
        semantic_analyzer = build_question_analyzer_from_env({**dotenv, **os.environ})
    if evidence_judge is None and use_env_evidence_judge:
        evidence_judge = build_evidence_judge_from_env({**dotenv, **os.environ})
    return AppContext(
        store=store,
        ask_engine=AskEngine(store, semantic_analyzer=semantic_analyzer, evidence_judge=evidence_judge),
        static_dir=static_dir,
        retrieval_client=retrieval_client,
    )


def handle_api_request(
    context: AppContext,
    method: str,
    path: str,
    body: dict[str, Any] | None = None,
) -> tuple[int, dict[str, Any]]:
    parsed_url = urlparse(path)
    parsed_path = parsed_url.path
    if method == "GET" and parsed_path == "/api/home":
        return 200, {"commonEntries": _camel(context.store.common_entries)}
    if method == "GET" and parsed_path.startswith("/api/chapters/"):
        number = int(parsed_path.rsplit("/", 1)[1])
        return 200, chapter_payload(context, number)
    if method == "GET" and parsed_path.startswith("/api/topics/"):
        topic_id = parsed_path.rsplit("/", 1)[1]
        topic = context.store.topic(topic_id)
        cards = [context.store.knowledge_card(card_id) for card_id in topic.card_ids]
        relations = [context.store.graph_relation(relation_id) for relation_id in topic.relation_ids]
        evidence = [context.store.evidence(evidence_id) for evidence_id in topic.evidence_ids]
        graph_payload = _topic_graph_payload(context.store, topic, cards=cards)
        return 200, {
            "topic": _topic_api_payload(topic, graph_payload=graph_payload, cards=cards, evidence=evidence),
            "topicContext": _camel(_topic_context_payload(graph_payload, topic=topic, evidence=evidence)),
            "cards": [_camel(asdict(card)) for card in cards],
            "relations": [_camel(asdict(relation)) for relation in relations],
            "evidence": [_camel(asdict(item)) for item in evidence],
        }
    if method == "GET" and parsed_path == "/api/topics":
        return 200, _topic_list_payload(context.store)
    if method == "GET" and parsed_path.startswith("/api/cards/"):
        card_id = parsed_path.rsplit("/", 1)[1]
        card = context.store.knowledge_card(card_id)
        evidence = [context.store.evidence(evidence_id) for evidence_id in card.evidence_ids]
        relation_by_id = {relation.id: relation for relation in context.store.graph_relations}
        relations = [relation_by_id[relation_id] for relation_id in card.graph_relation_ids]
        trace_items = context.store.trace_items_for_entity(card_id)
        return 200, {
            "card": _camel(asdict(card)),
            "evidence": [_camel(asdict(item)) for item in evidence],
            "relations": [_camel(asdict(item)) for item in relations],
            "traceItems": [_camel(asdict(item)) for item in trace_items],
        }
    if method == "GET" and parsed_path == "/api/entity-trace":
        params = parse_qs(parsed_url.query)
        name = str(params.get("name", [""])[0]).strip()
        if not name:
            return 400, {"error": "missing name"}
        current_chapter = _optional_int(params.get("chapter", [""])[0])
        entity_type = str(params.get("type", [""])[0]).strip()
        trace_payload = _entity_trace_payload(
            name,
            store=context.store,
            retrieval_client=context.retrieval_client,
            current_chapter=current_chapter,
            entity_type=entity_type,
        )
        return 200, _clean_student_payload({
            "traceItems": _camel(trace_payload["trace_items"]),
            "themeExtensions": _camel(trace_payload["theme_extensions"]),
        })
    if method == "POST" and parsed_path == "/api/ask":
        question = str((body or {}).get("question", ""))
        answer = context.ask_engine.ask(question, retrieval_client=context.retrieval_client)
        return 200, _camel(asdict(answer))
    return 404, {"error": "not found"}


def chapter_payload(context: AppContext, number: int) -> dict[str, Any]:
    cached_payload = context.chapter_response_cache.get(number)
    if cached_payload is not None:
        return cached_payload
    chapter = context.store.chapter(number)
    review_card = context.store.maybe_review_card_for_chapter(number)
    original_text = context.store.chapter_text(number)
    inline_entities = _inline_entities_for_review_card(review_card) if review_card is not None else []
    _attach_graph_entity_details(inline_entities, store=context.store)
    _attach_generated_chapter_jumps(inline_entities, store=context.store, current_chapter=number)
    annotations = _annotations_payload(
        stored_annotations=context.store.annotations_for_chapter(number),
        review_card=review_card,
        original_text=original_text,
        inline_entities=inline_entities,
    )
    knowledge_cards = []
    if review_card is not None:
        knowledge_cards = [context.store.knowledge_card(card_id) for card_id in review_card.key_characters]
    payload = {
        "chapter": _camel(asdict(chapter)),
        "originalText": original_text,
        "reviewCard": _camel(asdict(review_card)) if review_card is not None else None,
        "knowledgeCards": [_camel(asdict(card)) for card in knowledge_cards],
        "inlineEntities": _camel(inline_entities),
        "annotations": _camel(annotations),
        "materialStatus": {
            "hasReviewCard": review_card is not None,
            "message": "章节资料已加载。" if review_card is not None else "章节资料暂未生成，可先阅读原文。",
        },
    }
    cleaned_payload = _clean_student_payload(payload)
    context.chapter_response_cache[number] = cleaned_payload
    return cleaned_payload


def _topic_list_payload(store: Any) -> dict[str, Any]:
    topics = list(store.topics)
    graph_payloads = _topic_graph_payloads(store, topics)
    topic_payloads = [_topic_api_payload(topic, graph_payload=graph_payloads.get(topic.title)) for topic in topics]
    grouped_by_category: dict[str, list[dict[str, Any]]] = {}
    for topic in topic_payloads:
        category = str(topic.get("category") or "")
        grouped_by_category.setdefault(category, []).append(topic)

    topic_groups: list[dict[str, Any]] = []
    known_categories = [category for category in TOPIC_CATEGORY_ORDER if category in grouped_by_category]
    extra_categories = sorted(category for category in grouped_by_category if category not in TOPIC_CATEGORY_ORDER)
    for category in [*known_categories, *extra_categories]:
        grouped_topics = grouped_by_category[category]
        if not grouped_topics:
            continue
        topic_groups.append(
            {
                "category": category,
                "description": TOPIC_CATEGORY_DESCRIPTIONS.get(category, "围绕相关专题线索组织。"),
                "count": len(grouped_topics),
                "topics": grouped_topics,
            }
        )

    return {"topics": topic_payloads, "topicGroups": topic_groups}


def _topic_api_payload(
    topic: Any,
    *,
    graph_payload: dict[str, Any] | None = None,
    store: Any | None = None,
    cards: list[Any] | None = None,
    evidence: list[Any] | None = None,
) -> dict[str, Any]:
    payload = _camel(asdict(topic))
    summary = _topic_summary(topic, graph_payload=graph_payload, store=store, cards=cards, evidence=evidence)
    if summary:
        payload["description"] = summary
    return payload


def _topic_summary(
    topic: Any,
    *,
    graph_payload: dict[str, Any] | None = None,
    store: Any | None = None,
    cards: list[Any] | None = None,
    evidence: list[Any] | None = None,
) -> str:
    graph_description = _graph_description(graph_payload)
    if graph_description:
        return _truncate_topic_text(graph_description, 150)

    title = getattr(topic, "title", "")
    topic_evidence = evidence if evidence is not None else _topic_evidence(store, getattr(topic, "evidence_ids", []), limit=6)
    evidence_snippets = [
        snippet
        for item in topic_evidence
        if (snippet := _topic_focused_text(getattr(item, "evidence_text", ""), title, 150))
    ]
    self_contained_evidence = next((snippet for snippet in evidence_snippets if not _starts_with_context_pronoun(snippet)), "")
    if self_contained_evidence:
        return self_contained_evidence

    topic_cards = cards if cards is not None else _topic_cards(store, getattr(topic, "card_ids", []), limit=6)
    card_snippets = [
        snippet
        for card in topic_cards
        if (snippet := _topic_focused_text(getattr(card, "brief", ""), title, 150))
    ]
    self_contained_card = next((snippet for snippet in card_snippets if not _starts_with_context_pronoun(snippet)), "")
    if self_contained_card:
        return self_contained_card
    if evidence_snippets:
        return evidence_snippets[0]
    if card_snippets:
        return card_snippets[0]

    for card in topic_cards:
        brief = _compact_topic_text(getattr(card, "brief", ""))
        if brief and not _is_template_topic_text(brief, getattr(topic, "title", "")):
            return _truncate_topic_text(brief, 150)

    return str(getattr(topic, "description", "") or "")


def _topic_context_payload(
    graph_payload: dict[str, Any] | None,
    *,
    topic: Any | None = None,
    evidence: list[Any] | None = None,
) -> dict[str, Any]:
    introduction = _graph_description(graph_payload)
    if not introduction and topic is not None:
        introduction = _topic_evidence_introduction(topic, evidence=evidence)
    return {
        "introduction": _truncate_topic_text(introduction, 900),
        "graph_relations": _topic_graph_relations(graph_payload),
    }


def _topic_graph_payloads(store: Any, topics: list[Any]) -> dict[str, dict[str, Any]]:
    names = [str(getattr(topic, "title", "") or "").strip() for topic in topics]
    if store is not None and hasattr(store, "entity_graph_descriptions_for_names"):
        try:
            return {
                name: {"description": description}
                for name, description in store.entity_graph_descriptions_for_names(names).items()
                if description
            }
        except KeyError:
            return {}
    return _entity_graph_payloads(store, names)


def _topic_graph_payload(store: Any, topic: Any, *, cards: list[Any] | None = None) -> dict[str, Any] | None:
    del cards
    name = str(getattr(topic, "title", "") or "").strip()
    if not name:
        return None
    return _entity_graph_payloads(store, [name]).get(name)


def _entity_graph_payloads(store: Any, names: list[str]) -> dict[str, dict[str, Any]]:
    if store is None or not hasattr(store, "entity_graph_payloads_for_names"):
        return {}
    clean_names = [name for name in dict.fromkeys(str(item or "").strip() for item in names) if name]
    if not clean_names:
        return {}
    try:
        return store.entity_graph_payloads_for_names(clean_names)
    except KeyError:
        return {}


def _topic_cards(store: Any | None, card_ids: list[str], *, limit: int) -> list[Any]:
    if store is None:
        return []
    cards: list[Any] = []
    for card_id in card_ids[:limit]:
        try:
            cards.append(store.knowledge_card(card_id))
        except KeyError:
            continue
    return cards


def _topic_evidence(store: Any | None, evidence_ids: list[str], *, limit: int) -> list[Any]:
    if store is None:
        return []
    evidence: list[Any] = []
    for evidence_id in evidence_ids[:limit]:
        try:
            evidence.append(store.evidence(evidence_id))
        except KeyError:
            continue
    return evidence


def _graph_description(graph_payload: dict[str, Any] | None) -> str:
    if not graph_payload:
        return ""
    return _compact_topic_text(graph_payload.get("description"))


def _topic_evidence_introduction(topic: Any, *, evidence: list[Any] | None = None) -> str:
    title = getattr(topic, "title", "")
    snippets = [
        snippet
        for item in evidence or []
        if (snippet := _topic_focused_text(getattr(item, "evidence_text", ""), title, 240))
    ]
    self_contained = [snippet for snippet in snippets if not _starts_with_context_pronoun(snippet)]
    return "；".join(_limit_topic_snippets(self_contained or snippets, 4))


def _topic_graph_relations(graph_payload: dict[str, Any] | None, *, limit: int = 12) -> list[dict[str, str]]:
    if not graph_payload:
        return []
    relations: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in graph_payload.get("neighbors") or []:
        if not isinstance(item, Mapping):
            continue
        name = _compact_topic_text(item.get("name"))
        if not name or name in seen:
            continue
        relationship = _truncate_topic_text(item.get("relationship"), 48)
        description = _truncate_topic_text(item.get("description"), 180)
        if not relationship and not description:
            continue
        seen.add(name)
        relations.append({"name": name, "relationship": relationship, "description": description})
        if len(relations) >= limit:
            break
    return relations


def _compact_topic_text(value: Any) -> str:
    return re.sub(r"\s+", " ", _clean_student_text(str(value or ""))).strip()


def _truncate_topic_text(value: Any, limit: int) -> str:
    text = _compact_topic_text(value)
    if len(text) <= limit:
        return text
    boundary = max(text.rfind(mark, 0, limit) for mark in ("。", "；", "！", "？"))
    if boundary >= limit // 2:
        return text[: boundary + 1]
    return text[:limit].rstrip() + "…"


def _topic_focused_text(value: Any, title: str, limit: int) -> str:
    text = _compact_topic_text(value)
    clean_title = str(title or "").strip()
    if not text:
        return ""
    if not clean_title:
        return _truncate_topic_text(text, limit)
    index = text.find(clean_title)
    if index == -1:
        return ""
    sentence_start = max(text.rfind(mark, 0, index) for mark in ("。", "；", "！", "？"))
    start = sentence_start + 1 if sentence_start >= 0 else 0
    while start < len(text) and text[start] in " ：，、":
        start += 1
    sentence_end_candidates = [text.find(mark, index) for mark in ("。", "；", "！", "？")]
    sentence_end = min([candidate for candidate in sentence_end_candidates if candidate != -1], default=-1)
    if sentence_end == -1:
        sentence_end = min(len(text), start + limit)
    excerpt = text[start : sentence_end + 1].strip()
    return _truncate_topic_text(excerpt, limit)


def _limit_topic_snippets(snippets: list[str], limit: int) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for snippet in snippets:
        text = _compact_topic_text(snippet)
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
        if len(result) >= limit:
            break
    return result


def _starts_with_context_pronoun(text: str) -> bool:
    return text.startswith(("他", "她", "其", "此", "这", "那"))


def _is_template_topic_text(text: str, title: str) -> bool:
    return text.startswith(f"围绕{title}") or text.startswith("围绕相关专题")


def _camel(value: Any) -> Any:
    if isinstance(value, list):
        return [_camel(item) for item in value]
    if isinstance(value, dict):
        return {_camel_key(key): _camel(item) for key, item in value.items()}
    return value


def _camel_key(key: str) -> str:
    head, *tail = key.split("_")
    return head + "".join(part[:1].upper() + part[1:] for part in tail)


def _clean_student_payload(value: Any) -> Any:
    if isinstance(value, list):
        return [_clean_student_payload(item) for item in value]
    if isinstance(value, dict):
        return {key: _clean_student_payload(item) for key, item in value.items()}
    if isinstance(value, str):
        return _clean_student_text(value)
    return value


def _clean_student_text(value: str) -> str:
    parts = [part.strip() for part in str(value).split("<SEP>") if part.strip()]
    if not parts:
        return ""
    return "；".join(parts)


def _resolve_inline_entity_key(name: str, entities: dict[str, dict[str, Any]]) -> str:
    clean_name = str(name or "").strip()
    normalized_name = _normalize_entity_label(clean_name)
    for key, entity in entities.items():
        if normalized_name in _inline_entity_match_keys(entity):
            return key
    return clean_name


def _inline_entity_match_keys(entity: dict[str, Any]) -> set[str]:
    keys: set[str] = set()
    for value in [entity.get("name"), *_flatten_strings(entity.get("aliases"), entity.get("traceMatchTerms"))]:
        keys.update(_trace_match_terms_for_entity_name(str(value or "")))
    return {key for key in keys if key}


def _inline_entities_for_review_card(review_card: ChapterReviewCard) -> list[dict[str, Any]]:
    entities: dict[str, dict[str, Any]] = {}

    def ensure_entity(name: str, entity_type: str, summary: str = "", details: list[str] | None = None) -> dict[str, Any]:
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("inline entity name cannot be empty")
        key = _resolve_inline_entity_key(clean_name, entities)
        entity = entities.setdefault(
            key,
            {
                "id": f"chapter-{review_card.chapter:03d}-entity-{_entity_slug(clean_name)}",
                "name": clean_name,
                "type": entity_type,
                "summary": summary,
                "aliases": [],
                "details": [],
                "relations": [],
                "laterClues": [],
                "previousChapterJumps": [],
                "laterChapterJumps": [],
                "chapterJumps": [],
                "themeExtensions": [],
                "traceAnchorAliases": [],
                "relatedTraceAnchors": [],
                "traceMatchTerms": [],
            },
        )
        if summary and not entity["summary"]:
            entity["summary"] = summary
        if details:
            entity["details"].extend(item for item in details if item)
        entity["traceMatchTerms"].extend(_trace_match_terms_for_entity_name(clean_name))
        return entity

    for character in review_card.characters:
        if not isinstance(character, dict):
            continue
        name = str(character.get("name") or "").strip()
        if not name:
            continue
        details = _flatten_strings(
            character.get("actions"),
            character.get("traits"),
            character.get("evidence"),
            character.get("importance"),
        )
        aliases = _flatten_strings(character.get("aliases"))
        entity = ensure_entity(name, "person", str(character.get("role") or character.get("importance") or ""), details)
        entity.setdefault("aliases", []).extend(aliases)
        entity.setdefault("traceMatchTerms", []).extend(_trace_match_terms_for_values(aliases))

    for place in review_card.places:
        if not isinstance(place, dict):
            continue
        name = str(place.get("name") or "").strip()
        if name:
            ensure_entity(name, "place", str(place.get("function") or ""), _flatten_strings(place.get("scenes")))

    for item in review_card.objects:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if name:
            ensure_entity(name, "object", str(item.get("meaning") or ""), _flatten_strings(item.get("context"), item.get("related_entities")))

    for item in review_card.literary_texts:
        if not isinstance(item, dict):
            continue
        name = str(item.get("title") or "").strip()
        if name:
            ensure_entity(name, "literary_text", str(item.get("function") or ""), _flatten_strings(item.get("short_quote"), item.get("explanation")))

    for title in _literary_titles_mentioned_in_review_card(review_card):
        ensure_entity(
            title,
            "literary_text",
            "本回章节资料提及的文本线索。",
            _flatten_strings(_review_card_text_mention_context(title, review_card)),
        )

    for relation in review_card.relationships:
        if not isinstance(relation, dict):
            continue
        relation_summary = str(relation.get("description") or relation.get("chapter_evidence") or "").strip()
        endpoints = [str(endpoint or "").strip() for endpoint in (relation.get("source"), relation.get("target")) if str(endpoint or "").strip()]
        for endpoint in (relation.get("source"), relation.get("target")):
            name = str(endpoint or "").strip()
            if not name:
                continue
            entity = ensure_entity(name, "entity")
            for related_name in endpoints:
                if related_name != name:
                    _record_related_trace_anchor(entity, related_name)
            entity["relations"].append(
                {
                    "source": relation.get("source"),
                    "type": relation.get("type"),
                    "target": relation.get("target"),
                    "description": relation_summary,
                    "evidence": relation.get("chapter_evidence"),
                }
            )

    for association in review_card.later_associations:
        if not isinstance(association, dict):
            continue
        topic = str(association.get("topic") or "").strip()
        description = str(association.get("description") or association.get("evidence") or "").strip()
        display_description = _trim_text(description, INLINE_ENTITY_CLUE_DESCRIPTION_LENGTH)
        chapters = _int_list(association.get("source_chapters"))
        names = _entity_names_for_association(topic, description, entities)
        if not names and topic:
            names = [topic]
        for name in names:
            entity = ensure_entity(name, "foreshadowing" if name == topic else entities.get(name, {}).get("type", "entity"))
            _record_entity_trace_anchor(entity, topic=topic)
            entity["laterClues"].append({"topic": topic, "description": display_description, "evidence": display_description})
            for chapter in chapters:
                jump = {
                    "chapter": chapter,
                    "label": f"第{chapter}回：{topic or name}",
                    "description": _trim_text(description, INLINE_ENTITY_JUMP_DESCRIPTION_LENGTH),
                    "importance": 90,
                }
                if jump not in entity["chapterJumps"]:
                    entity["chapterJumps"].append(jump)

    for entity in entities.values():
        entity["details"] = _unique_strings(entity["details"])
        entity["aliases"] = _unique_strings(list(entity.get("aliases") or []))
        entity["relations"] = _unique_dicts(entity["relations"])
        entity["laterClues"] = _unique_dicts(entity["laterClues"])
        entity["traceAnchorAliases"] = _unique_strings(list(entity.get("traceAnchorAliases") or []))
        entity["relatedTraceAnchors"] = _unique_strings(list(entity.get("relatedTraceAnchors") or []))
        entity["traceMatchTerms"] = _unique_strings(list(entity.get("traceMatchTerms") or []))
        entity["chapterJumps"] = _sort_trace_items(_unique_dicts(entity["chapterJumps"]))
        _split_entity_chapter_jumps(entity, review_card.chapter)
        _limit_inline_entity_chapter_jumps(entity)
        if not entity["summary"] and entity["details"]:
            entity["summary"] = entity["details"][0]
    return list(entities.values())


def _attach_generated_chapter_jumps(inline_entities: list[dict[str, Any]], *, store: Any, current_chapter: int) -> None:
    if not inline_entities:
        return
    bulk_payloads = _cached_entity_trace_payloads_for_chapter(store=store, current_chapter=current_chapter)
    if bulk_payloads is not None:
        for entity in inline_entities:
            name = str(entity.get("name") or "")
            payload = _prefetched_trace_payload_for_entity(entity, bulk_payloads)
            if isinstance(payload, dict):
                _apply_prefetched_entity_trace(entity, payload=payload, current_chapter=current_chapter)
    else:
        for entity in inline_entities:
            _attach_prefetched_entity_trace(entity, store=store, current_chapter=current_chapter)
    for entity in inline_entities:
        entity["chapterJumps"] = _sort_trace_items(_unique_dicts(entity["chapterJumps"]))
        _split_entity_chapter_jumps(entity, current_chapter)


def _record_entity_trace_anchor(entity: dict[str, Any], *, topic: str) -> None:
    clean_topic = str(topic or "").strip()
    if not clean_topic:
        return
    clean_name = str(entity.get("name") or "").strip()
    if clean_topic == clean_name:
        return
    if clean_topic not in clean_name:
        return
    entity.setdefault("traceAnchorAliases", []).append(clean_topic)


def _record_related_trace_anchor(entity: dict[str, Any], related_name: str) -> None:
    clean_related = str(related_name or "").strip()
    clean_name = str(entity.get("name") or "").strip()
    if not clean_related or clean_related == clean_name:
        return
    entity.setdefault("relatedTraceAnchors", []).append(clean_related)


def _prefetched_trace_payload_for_entity(
    entity: dict[str, Any], payloads: dict[str, dict[str, Any]]
) -> dict[str, Any] | None:
    name = str(entity.get("name") or "").strip()
    candidate_names = _unique_strings([name, *_flatten_strings(entity.get("traceAnchorAliases"))])
    empty_payload: dict[str, Any] | None = None
    for candidate in candidate_names:
        payload = payloads.get(candidate)
        if not isinstance(payload, dict):
            continue
        if _prefetched_trace_payload_has_items(payload):
            return payload
        if empty_payload is None:
            empty_payload = payload
    related_payload = _related_prefetched_trace_payload_for_entity(entity, payloads)
    if related_payload is not None:
        return related_payload
    return empty_payload


def _related_prefetched_trace_payload_for_entity(
    entity: dict[str, Any], payloads: dict[str, dict[str, Any]]
) -> dict[str, Any] | None:
    match_terms = _trace_match_terms_for_entity(entity)
    if not match_terms:
        return None
    trace_items: list[dict[str, Any]] = []
    theme_extensions: list[dict[str, Any]] = []
    for anchor in _flatten_strings(entity.get("relatedTraceAnchors")):
        payload = payloads.get(anchor)
        if not isinstance(payload, dict):
            continue
        trace_items.extend(_trace_items_matching_terms(list(payload.get("trace_items") or []), match_terms))
        theme_extensions.extend(_theme_extensions_matching_terms(list(payload.get("theme_extensions") or []), match_terms))
    if not trace_items and not theme_extensions:
        return None
    return {"trace_items": _unique_dicts(trace_items), "theme_extensions": _unique_dicts(theme_extensions)}


def _trace_items_matching_terms(items: list[Any], match_terms: list[str]) -> list[dict[str, Any]]:
    matched: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        text = "\n".join(str(item.get(key) or "") for key in ("label", "description", "topic", "title"))
        if _text_matches_any_trace_term(text, match_terms):
            matched.append(item)
    return matched


def _theme_extensions_matching_terms(items: list[Any], match_terms: list[str]) -> list[dict[str, Any]]:
    matched: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        text = json.dumps(item, ensure_ascii=False)
        if _text_matches_any_trace_term(text, match_terms):
            matched.append(item)
    return matched


def _text_matches_any_trace_term(text: str, match_terms: list[str]) -> bool:
    normalized_text = _normalize_entity_label(text)
    return any(term and term in normalized_text for term in match_terms)


def _trace_match_terms_for_entity(entity: dict[str, Any]) -> list[str]:
    values = [
        str(entity.get("name") or ""),
        *_flatten_strings(entity.get("aliases"), entity.get("traceMatchTerms")),
    ]
    return _trace_match_terms_for_values(values)


def _trace_match_terms_for_values(values: Any) -> list[str]:
    terms: list[str] = []
    for value in _flatten_strings(values):
        terms.extend(_trace_match_terms_for_entity_name(value))
    return _unique_strings([term for term in terms if len(term) >= 2])


def _trace_match_terms_for_entity_name(value: str) -> list[str]:
    clean = str(value or "").strip()
    if not clean:
        return []
    candidates = [clean]
    candidates.extend(re.findall(r"[（(]([^（）()]{2,20})[）)]", clean))
    candidates.append(re.sub(r"[（(][^（）()]*[）)]", "", clean).strip())
    terms: list[str] = []
    for candidate in candidates:
        normalized = _normalize_entity_label(_strip_future_alias_note(candidate))
        if normalized:
            terms.append(normalized)
    return _unique_strings(terms)


def _strip_future_alias_note(value: str) -> str:
    return re.sub(r"(后文可知|后文称|后称|又称|即|可知|后来称)$", "", str(value or "").strip())


def _prefetched_trace_payload_has_items(payload: dict[str, Any]) -> bool:
    if list(payload.get("trace_items") or []):
        return True
    for extension in list(payload.get("theme_extensions") or []):
        if not isinstance(extension, dict):
            continue
        for key in ("chapter_jumps", "chapterJumps", "previous_chapter_jumps", "previousChapterJumps"):
            if list(extension.get(key) or []):
                return True
    return False


def _attach_graph_entity_details(inline_entities: list[dict[str, Any]], *, store: Any) -> None:
    if not inline_entities or not hasattr(store, "entity_graph_payloads_for_names"):
        return
    names = [str(entity.get("name") or "").strip() for entity in inline_entities if str(entity.get("name") or "").strip()]
    try:
        payloads = store.entity_graph_payloads_for_names(names)
    except Exception:
        return
    if not isinstance(payloads, dict):
        return
    for entity in inline_entities:
        name = str(entity.get("name") or "").strip()
        payload = payloads.get(name)
        if not isinstance(payload, dict):
            continue
        _apply_graph_entity_details(entity, payload=payload)


def _apply_graph_entity_details(entity: dict[str, Any], *, payload: dict[str, Any]) -> None:
    descriptions = _graph_cache_descriptions(payload)
    if descriptions:
        if not str(entity.get("summary") or "").strip():
            entity["summary"] = _trim_text(descriptions[0], INLINE_ENTITY_CLUE_DESCRIPTION_LENGTH)
        entity.setdefault("details", []).extend(_graph_cache_detail_items(descriptions))

    name = str(entity.get("name") or "").strip()
    for neighbor in _graph_cache_neighbors(payload)[:INLINE_ENTITY_MAX_GRAPH_NEIGHBORS]:
        neighbor_name = str(neighbor.get("name") or "").strip()
        if not neighbor_name:
            continue
        relationship = str(neighbor.get("relationship") or neighbor.get("type") or "关联").strip()
        description = str(neighbor.get("description") or neighbor_name).strip()
        entity.setdefault("relations", []).append(
            {
                "source": name,
                "type": relationship,
                "target": neighbor_name,
                "description": _trim_text(description, INLINE_ENTITY_CLUE_DESCRIPTION_LENGTH),
            }
        )

    entity["extended_neighbors"] = _sort_extended_neighbors(
        _unique_dicts(list(entity.get("extended_neighbors") or []) + _graph_cache_extended_neighbors(payload))
    )[:INLINE_ENTITY_MAX_EXTENDED_NEIGHBORS]
    entity["details"] = _unique_strings(entity.get("details") or [])
    entity["relations"] = _unique_dicts(entity.get("relations") or [])


def _graph_cache_descriptions(payload: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for key in ("description", "descriptions"):
        value = payload.get(key)
        if isinstance(value, list):
            values.extend(str(item).strip() for item in value if str(item).strip())
        else:
            values.extend(_split_sep(value))
    return _unique_strings(values)


def _graph_cache_detail_items(descriptions: list[str]) -> list[str]:
    items: list[str] = []
    for description in descriptions:
        clean = str(description or "").strip()
        if not clean:
            continue
        first_clause = re.split(r"[，。；\n]", clean, maxsplit=1)[0].strip()
        items.append(first_clause or _short_topic(clean))
    return _unique_strings(items)


def _graph_cache_neighbors(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw_neighbors = payload.get("neighbors")
    if not isinstance(raw_neighbors, list):
        return []
    return [neighbor for neighbor in raw_neighbors if isinstance(neighbor, dict)]


def _graph_cache_extended_neighbors(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw_neighbors = payload.get("extended_neighbors")
    if not isinstance(raw_neighbors, list):
        return []
    neighbors: list[dict[str, Any]] = []
    for neighbor in raw_neighbors:
        if not isinstance(neighbor, dict):
            continue
        to_name = str(neighbor.get("to") or "").strip()
        via_name = str(neighbor.get("via") or "").strip()
        if not to_name or not via_name:
            continue
        if _graph_relation_is_alias_like(neighbor.get("relationship")):
            continue
        relationship = _readable_graph_relationship(neighbor.get("relationship"))
        description = _readable_graph_description(neighbor.get("description") or to_name)
        neighbors.append(
            {
                "from": str(neighbor.get("from") or "").strip(),
                "via": via_name,
                "to": to_name,
                "relationship": relationship,
                "description": description,
                "path": list(neighbor.get("path") or []),
                "depth": _optional_int(neighbor.get("depth")) or 2,
                "weight": neighbor.get("weight") or 0,
            }
        )
    return neighbors


def _graph_relation_is_alias_like(value: object) -> bool:
    tokens = _graph_relation_tokens(value)
    if not tokens:
        return False
    alias_count = sum(1 for token in tokens if any(fragment in token for fragment in GRAPH_ALIAS_RELATION_FRAGMENTS))
    return alias_count / len(tokens) >= 0.5


def _readable_graph_relationship(value: object) -> str:
    for token in _graph_relation_tokens(value):
        if token in GRAPH_GENERIC_RELATION_TOKENS:
            continue
        if any(fragment in token for fragment in GRAPH_ALIAS_RELATION_FRAGMENTS):
            continue
        return _trim_text(token, 12)
    return "关联"


def _readable_graph_description(value: object) -> str:
    clean = _clean_student_text(str(value or ""))
    if not clean:
        return ""
    match = re.match(r"(.+?[。！？；;])", clean)
    sentence = match.group(1) if match else clean
    return _trim_text(sentence, INLINE_ENTITY_JUMP_DESCRIPTION_LENGTH)


def _graph_relation_tokens(value: object) -> list[str]:
    clean = _clean_student_text(str(value or ""))
    return [token.strip() for token in re.split(r"[,，、;；\s]+", clean) if token.strip()]


def _sort_extended_neighbors(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def rank(item: dict[str, Any]) -> tuple[float, str, str]:
        try:
            weight = float(item.get("weight") or 0)
        except (TypeError, ValueError):
            weight = 0.0
        return (-weight, str(item.get("via") or ""), str(item.get("to") or ""))

    return sorted(items, key=rank)


def _split_entity_chapter_jumps(entity: dict[str, Any], current_chapter: int) -> None:
    jumps = _sort_trace_items(_unique_dicts(list(entity.get("chapterJumps") or [])))
    previous = [jump for jump in jumps if (_optional_int(jump.get("chapter")) or 0) < current_chapter]
    later = [jump for jump in jumps if (_optional_int(jump.get("chapter")) or 0) > current_chapter]
    entity["previousChapterJumps"] = previous
    entity["laterChapterJumps"] = later
    entity["chapterJumps"] = later


def _limit_inline_entity_chapter_jumps(entity: dict[str, Any]) -> None:
    for key in ("previousChapterJumps", "laterChapterJumps", "chapterJumps"):
        entity[key] = _sort_trace_items(_unique_dicts(list(entity.get(key) or [])))[:INLINE_ENTITY_MAX_CHAPTER_JUMPS]


def _attach_prefetched_entity_trace(entity: dict[str, Any], *, store: Any, current_chapter: int) -> None:
    payload = _cached_entity_trace_payload(
        str(entity.get("name") or ""),
        store=store,
        current_chapter=current_chapter,
    )
    if payload is None:
        return
    _apply_prefetched_entity_trace(entity, payload=payload, current_chapter=current_chapter)


def _apply_prefetched_entity_trace(entity: dict[str, Any], *, payload: dict[str, Any], current_chapter: int) -> None:
    entity["tracePrefetched"] = True
    existing_jumps = [
        *list(entity.get("chapterJumps") or []),
        *list(entity.get("previousChapterJumps") or []),
        *list(entity.get("laterChapterJumps") or []),
    ]
    entity["chapterJumps"] = []
    entity["previousChapterJumps"] = []
    entity["laterChapterJumps"] = []
    trace_items = list(payload.get("trace_items") or [])
    theme_extensions = list(payload.get("theme_extensions") or [])
    for item in trace_items:
        jump = {
            "chapter": item.get("chapter"),
            "label": item.get("label") or f"第{item.get('chapter')}回：{item.get('topic') or entity.get('name')}",
            "description": item.get("description") or "",
            "importance": item.get("importance") or 0,
        }
        entity.setdefault("chapterJumps", []).append(jump)
        clue = _later_clue_from_trace_item(item)
        if clue is not None:
            entity.setdefault("laterClues", []).append(clue)
    for extension in theme_extensions:
        if not isinstance(extension, dict):
            continue
        entity.setdefault("chapterJumps", []).extend(list(extension.get("chapter_jumps") or []))
        entity.setdefault("chapterJumps", []).extend(list(extension.get("chapterJumps") or []))
        entity.setdefault("chapterJumps", []).extend(list(extension.get("previous_chapter_jumps") or []))
        entity.setdefault("chapterJumps", []).extend(list(extension.get("previousChapterJumps") or []))
    if not entity["chapterJumps"]:
        entity["chapterJumps"] = existing_jumps
    entity["themeExtensions"] = _unique_dicts([*list(entity.get("themeExtensions") or []), *theme_extensions])
    entity["laterClues"] = _unique_dicts(list(entity.get("laterClues") or []))
    entity["chapterJumps"] = _sort_trace_items(_unique_dicts(list(entity.get("chapterJumps") or [])))
    _split_entity_chapter_jumps(entity, current_chapter)
    _limit_inline_entity_chapter_jumps(entity)


def _later_clue_from_trace_item(item: dict[str, Any]) -> dict[str, str] | None:
    label = str(item.get("label") or "").strip()
    description = str(item.get("description") or "").strip()
    if not label and not description:
        return None
    topic = label or str(item.get("topic") or item.get("title") or "后文关联").strip()
    clean_description = description or topic
    return {"topic": topic, "description": clean_description, "evidence": clean_description}


def _entity_trace_items(
    name: str,
    *,
    store: Any,
    retrieval_client: Any | None,
    current_chapter: int | None,
) -> list[dict[str, Any]]:
    return _entity_trace_payload(
        name,
        store=store,
        retrieval_client=retrieval_client,
        current_chapter=current_chapter,
    )["trace_items"]


def _entity_trace_payload(
    name: str,
    *,
    store: Any,
    retrieval_client: Any | None,
    current_chapter: int | None,
    entity_type: str | None = None,
    use_cache: bool = True,
    include_generated: bool = True,
) -> dict[str, list[dict[str, Any]]]:
    should_skip_live_for_ui = _skip_live_entity_trace_for_ui(entity_type)
    cached_payload = (
        _cached_entity_trace_payload(name, store=store, current_chapter=current_chapter)
        if use_cache and not _prefer_generated_trace_for_ui(entity_type) and not should_skip_live_for_ui
        else None
    )
    if cached_payload is not None:
        return {
            "trace_items": _one_trace_item_per_chapter(_sort_trace_items(_unique_dicts(list(cached_payload.get("trace_items") or []))))[:12],
            "theme_extensions": [
                _without_importance(item)
                for item in _sort_theme_extensions(_unique_dicts(list(cached_payload.get("theme_extensions") or [])))[:8]
            ],
        }

    aliases = _local_entity_trace_aliases(name)
    items = _generated_trace_items_for_entity(name, aliases=aliases, store=store, current_chapter=current_chapter) if include_generated else []
    if items:
        return {
            "trace_items": _one_trace_item_per_chapter(_sort_trace_items(_unique_dicts(items)))[:12],
            "theme_extensions": [],
        }
    if should_skip_live_for_ui:
        return {"trace_items": [], "theme_extensions": []}

    aliases = _entity_trace_aliases(name, retrieval_client)
    items = _generated_trace_items_for_entity(name, aliases=aliases, store=store, current_chapter=current_chapter) if include_generated else []
    if items:
        return {
            "trace_items": _one_trace_item_per_chapter(_sort_trace_items(_unique_dicts(items)))[:12],
            "theme_extensions": [],
        }

    graph_extensions = _graph_theme_extensions_for_entity(
        name,
        aliases=aliases,
        retrieval_client=retrieval_client,
        current_chapter=current_chapter,
    )
    candidates = [] if graph_extensions else _retrieved_candidates_for_entity(name, aliases=aliases, retrieval_client=retrieval_client)
    items.extend(_retrieved_trace_items_for_entity(aliases=aliases, candidates=candidates, current_chapter=current_chapter))
    return {
        "trace_items": _one_trace_item_per_chapter(_sort_trace_items(_unique_dicts(items)))[:12],
        "theme_extensions": [
            _without_importance(item)
            for item in (graph_extensions or _theme_extensions_for_entity(aliases=aliases, candidates=candidates, current_chapter=current_chapter))[:8]
        ],
    }


def _cached_entity_trace_payload(name: str, *, store: Any, current_chapter: int | None) -> dict[str, Any] | None:
    if not name or not hasattr(store, "entity_trace_payload"):
        return None
    try:
        payload = store.entity_trace_payload(name, current_chapter)
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _cached_entity_trace_payloads_for_chapter(
    *, store: Any, current_chapter: int | None
) -> dict[str, dict[str, Any]] | None:
    if not hasattr(store, "entity_trace_payloads_for_chapter"):
        return None
    try:
        payloads = store.entity_trace_payloads_for_chapter(current_chapter)
    except Exception:
        return None
    return payloads if isinstance(payloads, dict) else None


def _local_entity_trace_aliases(name: str) -> set[str]:
    text = str(name or "").strip()
    normalized = _normalize_entity_label(text)
    aliases = {text, normalized}
    if _looks_like_chinese_person_name(normalized):
        aliases.add(normalized[1:])
    return {alias for alias in aliases if alias}


def _looks_like_chinese_person_name(value: str) -> bool:
    return bool(re.fullmatch(r"[\u4e00-\u9fff]{3,4}", value or "") and value[0] in "赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华金魏陶姜戚谢邹喻柏水窦章云苏潘葛奚范彭郎鲁韦昌马苗凤花方俞任袁柳鲍史唐费廉岑薛雷贺倪汤滕殷罗毕郝邬安常乐于时傅皮卞齐康伍余元卜顾孟平黄和穆萧尹林贾甄")


def _skip_live_entity_trace_for_ui(entity_type: str | None) -> bool:
    clean_type = str(entity_type or "").strip()
    if not clean_type:
        return False
    return clean_type not in {"person", "object", "foreshadowing"}


def _prefer_generated_trace_for_ui(entity_type: str | None) -> bool:
    return str(entity_type or "").strip() in {"person", "object", "foreshadowing"}


def _entity_trace_aliases(name: str, retrieval_client: Any | None) -> set[str]:
    aliases = _local_entity_trace_aliases(name)
    if retrieval_client is None or not hasattr(retrieval_client, "search_labels"):
        return {alias for alias in aliases if alias}
    try:
        labels = retrieval_client.search_labels(name, limit=12)
    except Exception:
        return {alias for alias in aliases if alias}
    normalized_name = _normalize_entity_label(name)
    for label in labels:
        text = str(label).strip()
        normalized = _normalize_entity_label(text)
        if not text or not normalized:
            continue
        if normalized_name in normalized or normalized in normalized_name:
            aliases.add(text)
            aliases.add(normalized)
    return {alias for alias in aliases if alias}


def _generated_trace_items_for_entity(
    name: str,
    *,
    aliases: set[str],
    store: Any,
    current_chapter: int | None,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for card in _review_cards_for_trace_scan(store):
        if card is None:
            continue
        if current_chapter is not None and card.chapter == current_chapter:
            continue
        jump = _chapter_jump_for_entity(name, card, aliases=aliases)
        if jump is not None:
            items.append(jump)
    return items


def _review_cards_for_trace_scan(store: Any) -> list[ChapterReviewCard]:
    if hasattr(store, "review_cards_for_trace_scan"):
        try:
            cards = store.review_cards_for_trace_scan()
        except Exception:
            cards = []
        return [card for card in cards if isinstance(card, ChapterReviewCard)]
    cards: list[ChapterReviewCard] = []
    for chapter_number in range(1, 121):
        try:
            card = store.maybe_review_card_for_chapter(chapter_number)
        except (KeyError, AttributeError):
            continue
        if isinstance(card, ChapterReviewCard):
            cards.append(card)
    return cards


def _literary_titles_mentioned_in_review_card(review_card: ChapterReviewCard) -> list[str]:
    text = "\n".join(
        str(item or "")
        for item in [
            review_card.plain_summary,
            *review_card.plot_chain,
            *review_card.key_events,
            *review_card.understanding_focus,
            *review_card.current_chapter_foreshadowing_signals,
        ]
    )
    return _unique_strings(match.group(0) for match in re.finditer(r"《[^》]{2,30}》", text))


def _review_card_text_mention_context(title: str, review_card: ChapterReviewCard) -> str:
    for text in [review_card.plain_summary, *review_card.key_events, *review_card.plot_chain]:
        value = str(text or "").strip()
        if title in value:
            return _trim_text(value, 96)
    return ""


def _retrieved_candidates_for_entity(
    name: str,
    *,
    aliases: set[str],
    retrieval_client: Any | None,
) -> list[EvidenceCandidate]:
    if retrieval_client is None:
        return []
    query = (
        f"实体：{name}。检索两类资料：一是直接出现或直接关联该实体的章回事件；"
        "二是能帮助理解该实体的主题延展，尤其盛衰变化、世事无常、荣辱转换、家族衰败、命运伏笔及其后文章回。"
    )
    try:
        response = retrieval_client.query_data(
            query,
            mode="hybrid",
            top_k=30,
            only_need_context=True,
            enable_rerank=True,
            hl_keywords=["主题延展", "盛衰变化", "世事无常", "荣辱转换", "家族衰败", "命运伏笔", "后文关联"],
            ll_keywords=[name, *sorted(aliases)[:4]],
        )
    except Exception:
        return []
    return normalize_query_data_response(response, question=name)


def _retrieved_trace_items_for_entity(
    *,
    aliases: set[str],
    candidates: list[EvidenceCandidate],
    current_chapter: int | None,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for candidate in candidates:
        if not _candidate_directly_mentions_entity(candidate, aliases):
            continue
        if not candidate.chapter_sources:
            continue
        if len(candidate.chapter_sources) != 1:
            continue
        for source in candidate.chapter_sources:
            if current_chapter is not None and source.chapter_number <= current_chapter:
                continue
            topic = _trace_topic(candidate)
            description = _candidate_description(candidate, aliases)
            if not description:
                continue
            items.append(
                {
                    "chapter": source.chapter_number,
                    "label": f"第{source.chapter_number}回：{topic}",
                    "topic": topic,
                    "description": description,
                    "importance": _candidate_importance(candidate),
                }
            )
    return items


def _graph_theme_extensions_for_entity(
    name: str,
    *,
    aliases: set[str],
    retrieval_client: Any | None,
    current_chapter: int | None,
) -> list[dict[str, Any]]:
    if retrieval_client is None or not hasattr(retrieval_client, "graph"):
        return []
    graph = _graph_for_entity_label(name, aliases=aliases, retrieval_client=retrieval_client)
    if not isinstance(graph, Mapping):
        return []
    nodes = _graph_nodes_by_id(graph.get("nodes"))
    edges = _graph_edges(graph.get("edges"))
    extensions: list[dict[str, Any]] = []
    for edge in edges:
        source = str(edge.get("source") or "").strip()
        target = str(edge.get("target") or "").strip()
        if not source or not target:
            continue
        source_matches = _matches_any_alias(source, aliases)
        target_matches = _matches_any_alias(target, aliases)
        if not source_matches and not target_matches:
            continue
        topic = target if source_matches else source
        if _matches_any_alias(topic, aliases):
            continue
        properties = edge.get("properties")
        if not isinstance(properties, Mapping):
            properties = {}
        descriptions = _split_sep(properties.get("description"))
        chapter_sources = parse_chapter_sources(str(properties.get("file_path") or ""))
        current_description = descriptions[0] if descriptions else _graph_node_description(nodes.get(topic))
        description = _graph_extension_description(
            keywords=str(properties.get("keywords") or "").strip(),
            description=current_description,
        )
        if not description:
            continue
        previous_jumps = _graph_chapter_jumps(
            descriptions=descriptions,
            chapter_sources=chapter_sources,
            current_chapter=current_chapter,
            direction="previous",
        )
        jumps = _graph_chapter_jumps(
            descriptions=descriptions,
            chapter_sources=chapter_sources,
            current_chapter=current_chapter,
            direction="later",
        )
        if not jumps:
            jumps = _graph_neighbor_jumps(
                topic=topic,
                edges=edges,
                current_chapter=current_chapter,
            )
        if not jumps:
            node_descriptions = _split_sep((nodes.get(topic) or {}).get("description"))
            node_chapter_sources = parse_chapter_sources(str((nodes.get(topic) or {}).get("file_path") or ""))
            if not previous_jumps:
                previous_jumps = _graph_chapter_jumps(
                    descriptions=node_descriptions,
                    chapter_sources=node_chapter_sources,
                    current_chapter=current_chapter,
                    direction="previous",
                )
            jumps = _graph_chapter_jumps(
                descriptions=node_descriptions,
                chapter_sources=node_chapter_sources,
                current_chapter=current_chapter,
                direction="later",
            )
        extension = {
            "topic": topic,
            "description": description,
            "previous_chapter_jumps": previous_jumps,
            "chapter_jumps": jumps,
            "importance": _graph_edge_importance(properties),
        }
        extensions.append(extension)
    return _sort_theme_extensions(_merge_theme_extensions_by_topic(extensions))


def _graph_for_entity_label(name: str, *, aliases: set[str], retrieval_client: Any) -> Mapping[str, Any] | None:
    labels = _graph_label_candidates(name, aliases)
    fallback_graph: Mapping[str, Any] | None = None
    for label in labels:
        try:
            graph = retrieval_client.graph(label, max_depth=3, max_nodes=1000)
        except Exception:
            continue
        if not isinstance(graph, Mapping):
            continue
        if _graph_edges(graph.get("edges")) or _graph_nodes_by_id(graph.get("nodes")):
            return graph
        if fallback_graph is None:
            fallback_graph = graph
    return fallback_graph


def _graph_label_candidates(name: str, aliases: set[str]) -> list[str]:
    candidates = [name, *sorted(aliases, key=lambda item: (item != name, len(item)))]
    normalized = _normalize_entity_label(name)
    if normalized:
        candidates.append(normalized)
    return _unique_strings([candidate for candidate in candidates if str(candidate or "").strip()])


def _theme_extensions_for_entity(
    *,
    aliases: set[str],
    candidates: list[EvidenceCandidate],
    current_chapter: int | None,
) -> list[dict[str, Any]]:
    extensions: list[dict[str, Any]] = []
    for candidate in candidates:
        if not _candidate_is_theme_extension(candidate, aliases):
            continue
        chapters = [
            source.chapter_number
            for source in candidate.chapter_sources
            if current_chapter is None or source.chapter_number > current_chapter
        ]
        if not chapters:
            continue
        topic = _trace_topic(candidate)
        description = _candidate_description(candidate, aliases)
        if not description:
            continue
        extensions.append(
            {
                "topic": topic,
                "description": description,
                "chapter_jumps": [
                    {"chapter": chapter, "label": f"第{chapter}回：{topic}"}
                    for chapter in sorted(dict.fromkeys(chapters))[:6]
                ],
                "importance": _candidate_importance(candidate),
            }
        )
    return _sort_theme_extensions(_unique_dicts(extensions))


def _candidate_is_theme_extension(candidate: EvidenceCandidate, aliases: set[str]) -> bool:
    if candidate.kind != "entity":
        return False
    entity_type = str(candidate.entity_type or "").lower()
    if entity_type not in {"themeconcept", "fateforeshadowing"}:
        return False
    if not candidate.chapter_sources or len(candidate.chapter_sources) < 2:
        return False
    return _candidate_directly_mentions_entity(candidate, aliases)


def _graph_nodes_by_id(raw_nodes: object) -> dict[str, Mapping[str, Any]]:
    if not isinstance(raw_nodes, list):
        return {}
    nodes: dict[str, Mapping[str, Any]] = {}
    for raw_node in raw_nodes:
        if not isinstance(raw_node, Mapping):
            continue
        node_id = str(raw_node.get("id") or "").strip()
        if not node_id:
            continue
        properties = raw_node.get("properties")
        nodes[node_id] = properties if isinstance(properties, Mapping) else {}
    return nodes


def _graph_edges(raw_edges: object) -> list[Mapping[str, Any]]:
    if not isinstance(raw_edges, list):
        return []
    return [edge for edge in raw_edges if isinstance(edge, Mapping)]


def _matches_any_alias(value: str, aliases: set[str]) -> bool:
    text = str(value or "").strip()
    normalized_text = _normalize_entity_label(text)
    for alias in aliases:
        normalized_alias = _normalize_entity_label(alias)
        if alias and alias == text:
            return True
        if normalized_alias and normalized_alias == normalized_text:
            return True
    return False


def _split_sep(value: object) -> list[str]:
    if not isinstance(value, str) or not value.strip():
        return []
    return _unique_strings(part.strip() for part in value.split("<SEP>") if part.strip())


def _graph_node_description(properties: Mapping[str, Any] | None) -> str:
    if not properties:
        return ""
    descriptions = _split_sep(properties.get("description"))
    return descriptions[0] if descriptions else ""


def _graph_extension_description(*, keywords: str, description: str) -> str:
    clean_description = _trim_text(description, 96)
    if not clean_description:
        return ""
    clean_keywords = _trim_text(keywords, 24)
    if clean_keywords:
        return f"{clean_keywords}：{clean_description}"
    return clean_description


def _graph_chapter_jumps(
    *,
    descriptions: list[str],
    chapter_sources: list[ChapterSource],
    current_chapter: int | None,
    direction: str = "later",
) -> list[dict[str, Any]]:
    jumps: list[dict[str, Any]] = []
    seen_chapters: set[int] = set()
    for index, source in enumerate(chapter_sources):
        if current_chapter is not None:
            if direction == "previous" and source.chapter_number >= current_chapter:
                continue
            if direction != "previous" and source.chapter_number <= current_chapter:
                continue
        if source.chapter_number in seen_chapters:
            continue
        seen_chapters.add(source.chapter_number)
        description = descriptions[index] if index < len(descriptions) else (descriptions[-1] if descriptions else source.chapter_title)
        description = _trim_text(description, 96)
        jumps.append(
            {
                "chapter": source.chapter_number,
                "label": f"第{source.chapter_number}回：{description or source.chapter_title}",
                "description": description,
            }
        )
    return jumps[:6]


def _graph_neighbor_jumps(
    *,
    topic: str,
    edges: list[Mapping[str, Any]],
    current_chapter: int | None,
) -> list[dict[str, Any]]:
    jumps: list[dict[str, Any]] = []
    seen_chapters: set[int] = set()
    for edge in edges:
        source = str(edge.get("source") or "").strip()
        target = str(edge.get("target") or "").strip()
        if source != topic and target != topic:
            continue
        properties = edge.get("properties")
        if not isinstance(properties, Mapping):
            continue
        descriptions = _split_sep(properties.get("description"))
        if not descriptions:
            continue
        chapter_sources = parse_chapter_sources(str(properties.get("file_path") or ""))
        for index, chapter_source in enumerate(chapter_sources):
            if current_chapter is not None and chapter_source.chapter_number <= current_chapter:
                continue
            if chapter_source.chapter_number in seen_chapters:
                continue
            seen_chapters.add(chapter_source.chapter_number)
            description = descriptions[index] if index < len(descriptions) else descriptions[-1]
            description = _trim_text(description, 96)
            jumps.append(
                {
                    "chapter": chapter_source.chapter_number,
                    "label": f"第{chapter_source.chapter_number}回：{description}",
                    "description": description,
                }
            )
    return jumps[:6]


def _graph_edge_importance(properties: Mapping[str, Any]) -> int:
    raw_weight = properties.get("weight")
    try:
        weight = float(raw_weight)
    except (TypeError, ValueError):
        weight = 0.0
    return 82 + int(weight * 8)


def _one_trace_item_per_chapter(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_chapter: dict[int, dict[str, Any]] = {}
    for item in items:
        chapter = _optional_int(item.get("chapter"))
        if chapter is None:
            continue
        current = by_chapter.get(chapter)
        if current is None or _trace_rank(item) > _trace_rank(current):
            by_chapter[chapter] = item
    return _sort_trace_items(list(by_chapter.values()))


def _trace_rank(item: dict[str, Any]) -> tuple[int, int, int]:
    description = str(item.get("description") or "")
    topic = str(item.get("topic") or item.get("label") or "")
    return (
        int(item.get("importance") or 0),
        1 if "<SEP>" not in description else 0,
        min(len(topic), 40),
    )


def _candidate_directly_mentions_entity(candidate: EvidenceCandidate, aliases: set[str]) -> bool:
    raw = candidate.raw
    if candidate.kind == "relationship":
        fields = [
            candidate.title,
            str(raw.get("src_id") or ""),
            str(raw.get("tgt_id") or ""),
        ]
    elif candidate.kind == "entity":
        fields = [
            candidate.title,
            candidate.description,
            str(raw.get("entity_name") or ""),
        ]
    else:
        fields = [
            candidate.title,
            candidate.description,
        ]
    haystack = "\n".join(fields)
    normalized_haystack = _normalize_entity_label(haystack)
    for alias in aliases:
        if alias and alias in haystack:
            return True
        normalized = _normalize_entity_label(alias)
        if normalized and normalized in normalized_haystack:
            return True
    return False


def _candidate_importance(candidate: EvidenceCandidate) -> int:
    raw_weight = candidate.raw.get("weight")
    try:
        weight = float(raw_weight)
    except (TypeError, ValueError):
        weight = 0.0
    base = {"relationship": 74, "entity": 82, "chunk": 62, "reference": 45}.get(candidate.kind, 50)
    if len(candidate.chapter_sources) > 1:
        base -= min(20, len(candidate.chapter_sources) * 2)
    return min(120, base + int(weight * 4) + min(candidate.score, 20))


def _trace_topic(candidate: EvidenceCandidate) -> str:
    raw = candidate.raw
    if candidate.kind == "relationship":
        keywords = str(raw.get("keywords") or "").strip()
        title = candidate.title
        return _trim_text(keywords or title, 24)
    entity_name = str(raw.get("entity_name") or "").strip()
    return _trim_text(entity_name or candidate.title, 24)


def _candidate_description(candidate: EvidenceCandidate, aliases: set[str]) -> str:
    parts = [part.strip() for part in str(candidate.description or "").split("<SEP>") if part.strip()]
    if not parts:
        return ""
    normalized_aliases = {_normalize_entity_label(alias) for alias in aliases if _normalize_entity_label(alias)}
    for part in parts:
        normalized_part = _normalize_entity_label(part)
        if any(alias and alias in normalized_part for alias in normalized_aliases):
            return _trim_text(part, 96)
    return _trim_text(parts[0], 96)


def _chapter_jump_for_entity(name: str, card: ChapterReviewCard, *, aliases: set[str] | None = None) -> dict[str, Any] | None:
    description = _entity_description_in_review_card(name, card, aliases=aliases)
    if not description:
        return None
    topic = _short_topic(description)
    return {
        "chapter": card.chapter,
        "label": f"第{card.chapter}回：{topic}",
        "description": description,
        "importance": 85,
    }


def _entity_description_in_review_card(name: str, card: ChapterReviewCard, *, aliases: set[str] | None = None) -> str:
    aliases = aliases or {name, _normalize_entity_label(name)}
    for character in card.characters:
        if not isinstance(character, dict) or not _matches_any_entity_name(aliases, character.get("name")):
            continue
        return _first_nonempty(
            _join_strings(character.get("actions")),
            str(character.get("importance") or ""),
            str(character.get("role") or ""),
        )
    for relation in card.relationships:
        if not isinstance(relation, dict):
            continue
        if not any(_matches_any_entity_name(aliases, endpoint) for endpoint in (relation.get("source"), relation.get("target"))):
            continue
        return str(relation.get("description") or relation.get("chapter_evidence") or "").strip()
    for field, key, detail_keys in (
        ("literary_texts", "title", ("explanation", "function", "short_quote")),
        ("objects", "name", ("context", "meaning", "related_entities")),
        ("places", "name", ("scenes", "function")),
    ):
        for item in getattr(card, field, []):
            if not isinstance(item, dict) or not _matches_any_entity_name(aliases, item.get(key)):
                continue
            return _first_nonempty(*(_string_or_join(item.get(detail_key)) for detail_key in detail_keys))
    for text in [*card.key_events, *card.plot_chain, card.plain_summary]:
        value = str(text or "").strip()
        if value and _review_text_mentions_entity(value, name=name, aliases=aliases):
            return _trim_text(value, 96)
    return ""


def _matches_any_entity_name(aliases: set[str], actual: Any) -> bool:
    return any(_matches_entity_name(alias, actual) for alias in aliases)


def _review_text_mentions_entity(value: str, *, name: str, aliases: set[str]) -> bool:
    normalized_value = _normalize_entity_label(value)
    normalized_name = _normalize_entity_label(name)
    for alias in aliases:
        normalized_alias = _normalize_entity_label(alias)
        if not normalized_alias:
            continue
        if normalized_alias == "宝玉" and normalized_name == "贾宝玉":
            if _mentions_baoyu_as_person(normalized_value):
                return True
            continue
        if alias and alias in value:
            return True
        if normalized_alias and normalized_alias in normalized_value:
            return True
    return False


def _mentions_baoyu_as_person(normalized_value: str) -> bool:
    for match in re.finditer("宝玉", normalized_value):
        if normalized_value[max(0, match.start() - 2) : match.start()] != "通灵":
            return True
    return False


def _matches_entity_name(expected: str, actual: Any) -> bool:
    if actual is None:
        return False
    expected_text = str(expected).strip()
    actual_text = str(actual).strip()
    if not expected_text or not actual_text:
        return False
    if expected_text == actual_text:
        return True
    expected_normalized = _normalize_entity_label(expected_text)
    actual_normalized = _normalize_entity_label(actual_text)
    return bool(expected_normalized and actual_normalized and (expected_normalized == actual_normalized))


def _normalize_entity_label(value: str) -> str:
    return re.sub(r"[《》〈〉“”\"'’‘\s]", "", str(value or ""))


def _short_topic(text: str) -> str:
    clean = str(text or "").strip()
    for separator in ("；", "。", "\n", "，"):
        if separator in clean:
            clean = clean.split(separator, 1)[0].strip()
            break
    return _trim_text(clean, 24) or "相关线索"


def _trim_text(text: str, max_length: int) -> str:
    clean = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(clean) <= max_length:
        return clean
    return clean[: max_length - 1].rstrip() + "…"


def _join_strings(value: Any) -> str:
    if isinstance(value, list):
        return "；".join(str(item).strip() for item in value if str(item).strip())
    return str(value or "").strip()


def _string_or_join(value: Any) -> str:
    return _join_strings(value)


def _first_nonempty(*values: str) -> str:
    for value in values:
        clean = str(value or "").strip()
        if clean:
            return clean
    return ""


def _sort_trace_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        items,
        key=lambda item: (-(int(item.get("importance") or 0)), int(item.get("chapter") or 0), str(item.get("label") or "")),
    )


def _sort_theme_extensions(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        items,
        key=lambda item: (
            -(int(item.get("importance") or 0)),
            _optional_int((item.get("chapter_jumps") or [{}])[0].get("chapter")) or 0,
            str(item.get("topic") or ""),
        ),
    )


def _merge_theme_extensions_by_topic(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for item in items:
        topic = str(item.get("topic") or "").strip()
        if not topic:
            continue
        current = merged.get(topic)
        if current is None:
            merged[topic] = {**item, "chapter_jumps": list(item.get("chapter_jumps") or [])}
            continue
        current_jumps = list(current.get("chapter_jumps") or [])
        current["chapter_jumps"] = _unique_dicts([*current_jumps, *list(item.get("chapter_jumps") or [])])
        if _theme_extension_rank(item) > _theme_extension_rank(current):
            current["description"] = item.get("description")
            current["importance"] = item.get("importance")
    return list(merged.values())


def _theme_extension_rank(item: dict[str, Any]) -> tuple[int, int, int]:
    return (
        int(item.get("importance") or 0),
        len(item.get("chapter_jumps") or []),
        len(str(item.get("description") or "")),
    )


def _without_importance(item: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in item.items() if key != "importance" and value != []}


def _entity_names_in_review_card(review_card: ChapterReviewCard) -> set[str]:
    names: set[str] = set()
    for field, key in (
        ("characters", "name"),
        ("places", "name"),
        ("objects", "name"),
        ("literary_texts", "title"),
    ):
        for item in getattr(review_card, field, []):
            if not isinstance(item, dict):
                continue
            name = str(item.get(key) or "").strip()
            if name:
                names.add(name)
    for relation in review_card.relationships:
        if not isinstance(relation, dict):
            continue
        for endpoint in (relation.get("source"), relation.get("target")):
            name = str(endpoint or "").strip()
            if name:
                names.add(name)
    return names


def _annotations_payload(
    *,
    stored_annotations: list[ChapterAnnotation],
    review_card: ChapterReviewCard | None,
    original_text: str,
    inline_entities: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    entity_id_by_name = {str(entity["name"]): str(entity["id"]) for entity in inline_entities}
    entity_id_by_id = {str(entity["id"]): str(entity["id"]) for entity in inline_entities}
    rows: list[dict[str, Any]] = []
    if stored_annotations:
        rows = [
            {
                **asdict(annotation),
                "entity_id": entity_id_by_id.get(str(annotation.entity_id))
                or entity_id_by_name.get(str(annotation.surface_text))
                or annotation.entity_id,
            }
            for annotation in stored_annotations
        ]
    elif review_card is not None:
        rows = _review_card_annotation_rows(
            review_card=review_card,
            original_text=original_text,
            entity_id_by_name=entity_id_by_name,
            entity_id_by_id=entity_id_by_id,
        )
    if review_card is None:
        return rows
    return _merge_annotation_rows(
        [
            *rows,
            *_auto_inline_entity_annotation_rows(
                review_card=review_card,
                original_text=original_text,
                inline_entities=inline_entities,
            ),
        ]
    )


def _review_card_annotation_rows(
    *,
    review_card: ChapterReviewCard,
    original_text: str,
    entity_id_by_name: dict[str, str],
    entity_id_by_id: dict[str, str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for annotation in review_card.annotations:
        if not isinstance(annotation, dict):
            continue
        text = str(annotation.get("text") or "").strip()
        if not text:
            continue
        target = str(annotation.get("target") or text).strip()
        entity_id = entity_id_by_name.get(target) or entity_id_by_name.get(text) or entity_id_by_id.get(target)
        if not entity_id:
            continue
        start = 0
        while True:
            index = original_text.find(text, start)
            if index == -1:
                break
            rows.append(
                {
                    "id": f"ann-{review_card.chapter:03d}-{_entity_slug(entity_id)}-{index}",
                    "chapter": review_card.chapter,
                    "start_offset": index,
                    "end_offset": index + len(text),
                    "surface_text": text,
                    "annotation_type": str(annotation.get("kind") or "entity"),
                    "entity_id": entity_id,
                    "inline_entity_id": entity_id,
                    "relation_id": None,
                    "evidence_id": None,
                    "display_priority": 100,
                }
            )
            start = index + len(text)
    return rows


def _auto_inline_entity_annotation_rows(
    *,
    review_card: ChapterReviewCard,
    original_text: str,
    inline_entities: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for entity in sorted(inline_entities, key=lambda item: len(str(item.get("name") or "")), reverse=True):
        entity_id = str(entity.get("id") or "").strip()
        entity_name = str(entity.get("name") or "").strip()
        if not entity_id or len(entity_name) < 2:
            continue
        surfaces = _unique_strings(
            [
                surface
                for value in [entity_name, *list(entity.get("aliases") or [])]
                for surface in _annotation_surfaces_for_entity(str(value))
            ]
        )
        found = 0
        for surface in surfaces:
            start = 0
            while found < 8:
                index = original_text.find(surface, start)
                if index == -1:
                    break
                rows.append(
                    {
                        "id": f"ann-{review_card.chapter:03d}-auto-{_entity_slug(entity_id)}-{index}",
                        "chapter": review_card.chapter,
                        "start_offset": index,
                        "end_offset": index + len(surface),
                        "surface_text": surface,
                        "annotation_type": str(entity.get("type") or "entity"),
                        "entity_id": entity_id,
                        "inline_entity_id": entity_id,
                        "relation_id": None,
                        "evidence_id": None,
                        "display_priority": 70,
                    }
                )
                found += 1
                start = index + len(surface)
    return rows


def _annotation_surfaces_for_entity(name: str) -> list[str]:
    surfaces = [name]
    normalized = name.strip("《》〈〉")
    if normalized and normalized != name:
        surfaces.append(normalized)
    if not name.startswith("《") and len(name) >= 2:
        surfaces.append(f"《{name}》")
    return _unique_strings([surface for surface in surfaces if len(surface) >= 2])


def _merge_annotation_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for row in rows:
        start = _optional_int(row.get("start_offset"))
        end = _optional_int(row.get("end_offset"))
        entity_id = row.get("entity_id")
        if start is None or end is None or end <= start or not entity_id:
            continue
        normalized.append(row)
    sorted_rows = sorted(
        normalized,
        key=lambda item: (
            int(item["start_offset"]),
            -int(item["end_offset"]) + int(item["start_offset"]),
            -int(item.get("display_priority") or 0),
            str(item.get("id") or ""),
        ),
    )
    output: list[dict[str, Any]] = []
    occupied: list[tuple[int, int]] = []
    seen: set[tuple[int, int, str]] = set()
    for row in sorted_rows:
        start = int(row["start_offset"])
        end = int(row["end_offset"])
        key = (start, end, str(row.get("entity_id") or ""))
        if key in seen:
            continue
        if any(start < occupied_end and end > occupied_start for occupied_start, occupied_end in occupied):
            continue
        seen.add(key)
        occupied.append((start, end))
        output.append(row)
    return sorted(output, key=lambda item: (int(item["start_offset"]), int(item["end_offset"]), str(item.get("id") or "")))


def _entity_slug(value: str) -> str:
    parts = re.findall(r"[\w\u4e00-\u9fff]+", value.lower())
    return "-".join(parts) or "item"


def _flatten_strings(*values: Any) -> list[str]:
    output: list[str] = []
    for value in values:
        if isinstance(value, list):
            output.extend(str(item) for item in value if str(item).strip())
        elif value is not None and str(value).strip():
            output.append(str(value))
    return output


def _unique_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            output.append(value)
    return output


def _unique_dicts(values: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    output: list[dict[str, Any]] = []
    for value in values:
        key = json.dumps(value, ensure_ascii=False, sort_keys=True)
        if key not in seen:
            seen.add(key)
            output.append(value)
    return output


def _int_list(value: Any) -> list[int]:
    if not isinstance(value, list):
        return []
    output: list[int] = []
    for item in value:
        try:
            output.append(int(item))
        except (TypeError, ValueError):
            continue
    return output


def _optional_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _entity_names_for_association(topic: str, description: str, entities: dict[str, dict[str, Any]]) -> list[str]:
    topic_names = [name for name in entities if name and name in topic]
    text = f"{topic}\n{description}"
    direct_names = [name for name in entities if name and name in text]
    inherited_names = [
        name
        for name, entity in entities.items()
        if _entity_can_inherit_association_from_context(entity, topic=topic, description=description)
    ]
    if topic_names:
        return _unique_strings([*topic_names, *inherited_names])
    if direct_names:
        return _unique_strings([*direct_names, *inherited_names])
    return inherited_names


def _entity_can_inherit_association_from_context(entity: dict[str, Any], *, topic: str, description: str) -> bool:
    if str(entity.get("type") or "") not in {"literary_text", "object", "place", "foreshadowing"}:
        return False
    topic_text = str(topic or "").strip()
    if not topic_text:
        return False
    anchor_text = "\n".join(
        [
            str(entity.get("name") or ""),
            *_flatten_strings(entity.get("aliases")),
        ]
    )
    context_text = "\n".join([anchor_text, str(entity.get("summary") or ""), *_flatten_strings(entity.get("details"))])
    if topic_text not in anchor_text:
        return False
    if topic_text not in context_text:
        return False
    return any(term in context_text for term in ("后文", "后续", "后来", "预示", "暗示", "伏笔", "命运", "发迹"))


def PostgresContentStore(database_url: str, fallback_store: Any) -> Any:
    try:
        from hlm_kg.postgres_store import PostgresContentStore as Store
    except ModuleNotFoundError as exc:
        if exc.name == "psycopg":
            raise RuntimeError("psycopg is required for PostgreSQL content store") from exc
        raise
    return Store(database_url, fallback_store=fallback_store)


def make_handler(context: AppContext) -> type[SimpleHTTPRequestHandler]:
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, directory=str(context.static_dir), **kwargs)

        def do_GET(self) -> None:
            if self.path.startswith("/api/"):
                self._handle_api("GET")
                return
            if self.path == "/":
                self.path = "/index.html"
            super().do_GET()

        def do_POST(self) -> None:
            if self.path.startswith("/api/"):
                self._handle_api("POST")
                return
            self.send_error(404)

        def _handle_api(self, method: str) -> None:
            body = None
            if method == "POST":
                length = int(self.headers.get("Content-Length", "0"))
                raw_body = self.rfile.read(length).decode("utf-8") if length else "{}"
                body = json.loads(raw_body or "{}")
            status, payload = handle_api_request(context, method, self.path, body)
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    return Handler


def find_available_port(start_port: int, attempts: int = 20) -> int:
    for offset in range(attempts):
        port = start_port + offset
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    raise OSError(f"no available port from {start_port} across {attempts} attempts")


def main() -> None:
    context = create_app_context(
        manifest_path=Path("book/chapters_manifest.json"),
        data_dir=Path("data/app"),
        static_dir=Path("static"),
        use_env_retrieval=True,
        use_env_question_analyzer=True,
        use_env_evidence_judge=True,
        use_env_content_store=True,
    )
    port = find_available_port(8765)
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(context))
    print(f"Serving at http://127.0.0.1:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
