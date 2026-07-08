from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from hlm_kg.lightrag_client import LightRAGClient, LightRAGConfig
from hlm_kg.postgres_config import load_database_url, load_dotenv
from hlm_kg.web_app import (
    _clean_student_text,
    _graph_edges,
    _graph_nodes_by_id,
    _inline_entities_for_review_card,
    _normalize_entity_label,
    create_app_context,
)
from scripts.build_entity_trace_cache import parse_chapter_selection
from scripts.import_postgres_seed import _upsert_entity_graph_cache, entity_graph_cache_rows as _import_entity_graph_cache_rows


ALIAS_RELATION_FRAGMENTS = (
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
GENERIC_RELATION_TOKENS = {"人物关系", "人物关联", "关系", "关联"}
EXTENDED_DESCRIPTION_MAX_LENGTH = 96
RELATIONSHIP_MAX_LENGTH = 12


def graph_payload_from_lightrag_graph(label: str, graph: Mapping[str, Any]) -> dict[str, Any]:
    nodes = _graph_nodes_by_id(graph.get("nodes"))
    node = _matching_node(label, nodes)
    description = _clean_student_text(str((node or {}).get("description") or ""))
    return {
        "description": description,
        "neighbors": _neighbors_for_label(label, graph),
        "extended_neighbors": _extended_neighbors_for_label(label, graph),
        "raw_graph": dict(graph),
        "metadata": {"source": "lightrag_graph"},
    }


def build_entity_graph_cache_for_context(
    *,
    context: Any,
    chapters: list[int],
    max_depth: int = 1,
    max_nodes: int = 100,
    existing: dict[str, Any] | None = None,
    skip_existing: bool = False,
    include_topic_titles: bool = False,
) -> dict[str, dict[str, Any]]:
    if context.retrieval_client is None or not hasattr(context.retrieval_client, "graph"):
        raise RuntimeError("LIGHTRAG_BASE_URL is not set; cannot build entity graph cache")

    cache: dict[str, dict[str, Any]] = dict(existing or {})
    names = graph_cache_names_for_store(context.store, chapters, include_topic_titles=include_topic_titles)
    for index, name in enumerate(names, start=1):
        if skip_existing and isinstance(cache.get(name), dict):
            print(f"[{index}/{len(names)}] skipped graph cache: {name}", flush=True)
            continue
        print(f"[{index}/{len(names)}] fetching graph cache: {name}", flush=True)
        payload = graph_payload_for_name(
            context.retrieval_client,
            name,
            max_depth=max_depth,
            max_nodes=max_nodes,
        )
        if payload is None:
            print(f"[{index}/{len(names)}] skipped empty graph cache: {name}", flush=True)
            continue
        cache[name] = payload
    return cache


def entity_names_for_chapters(store: Any, chapters: list[int]) -> list[str]:
    names: list[str] = []
    for chapter in chapters:
        review_card = store.maybe_review_card_for_chapter(chapter)
        if review_card is None:
            continue
        for entity in _inline_entities_for_review_card(review_card):
            name = str(entity.get("name") or "").strip()
            if name:
                names.append(name)
    return list(dict.fromkeys(names))


def graph_cache_names_for_store(store: Any, chapters: list[int], *, include_topic_titles: bool = False) -> list[str]:
    names = entity_names_for_chapters(store, chapters)
    if include_topic_titles:
        for topic in getattr(store, "topics", []):
            if isinstance(topic, Mapping):
                title = str(topic.get("title") or "").strip()
            else:
                title = str(getattr(topic, "title", "") or "").strip()
            if title:
                names.append(title)
    return list(dict.fromkeys(names))


def entity_graph_cache_rows(cache: Any) -> list[dict[str, Any]]:
    return _import_entity_graph_cache_rows(cache)


def graph_payload_for_name(client: Any, name: str, *, max_depth: int, max_nodes: int) -> dict[str, Any] | None:
    graph = client.graph(name, max_depth=max_depth, max_nodes=max_nodes)
    payload = graph_payload_from_lightrag_graph(name, graph)
    if graph_payload_has_content(payload):
        return payload
    if not hasattr(client, "search_labels"):
        return None
    for label in client.search_labels(name, limit=5):
        candidate_label = str(label or "").strip()
        if not candidate_label or candidate_label == name:
            continue
        graph = client.graph(candidate_label, max_depth=max_depth, max_nodes=max_nodes)
        payload = graph_payload_from_lightrag_graph(candidate_label, graph)
        if graph_payload_has_content(payload):
            metadata = dict(payload.get("metadata") or {})
            metadata["requested_label"] = name
            metadata["source_label"] = candidate_label
            payload["metadata"] = metadata
            return payload
    return None


def graph_payload_has_content(payload: Mapping[str, Any]) -> bool:
    return bool(
        str(payload.get("description") or "").strip()
        or payload.get("neighbors")
        or payload.get("extended_neighbors")
    )


def names_to_sync(selected_names: list[str], existing: dict[str, Any], *, skip_existing: bool) -> list[str]:
    return [
        name
        for name in selected_names
        if not (skip_existing and isinstance(existing.get(name), dict))
    ]


def read_cache(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def write_cache(path: Path, cache: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def sync_cache_to_postgres(cache: dict[str, Any], database_url: str) -> None:
    import psycopg

    rows = entity_graph_cache_rows(cache)
    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            _upsert_entity_graph_cache(cur, rows)
        conn.commit()


def _matching_node(label: str, nodes: dict[str, Mapping[str, Any]]) -> Mapping[str, Any] | None:
    normalized_label = _normalize_entity_label(label)
    for node_id, properties in nodes.items():
        if node_id == label:
            return properties
        if normalized_label and _normalize_entity_label(node_id) == normalized_label:
            return properties
    return next(iter(nodes.values()), None) if len(nodes) == 1 else None


def _neighbors_for_label(label: str, graph: Mapping[str, Any]) -> list[dict[str, Any]]:
    normalized_label = _normalize_entity_label(label)
    neighbors: list[dict[str, Any]] = []
    for edge in _graph_edges(graph.get("edges")):
        source = str(edge.get("source") or "").strip()
        target = str(edge.get("target") or "").strip()
        if not source or not target:
            continue
        source_matches = source == label or (_normalize_entity_label(source) == normalized_label and normalized_label)
        target_matches = target == label or (_normalize_entity_label(target) == normalized_label and normalized_label)
        if not source_matches and not target_matches:
            continue
        neighbor_name = target if source_matches else source
        properties = edge.get("properties")
        if not isinstance(properties, Mapping):
            properties = {}
        relationship = _clean_student_text(str(properties.get("keywords") or properties.get("relationship") or "关联"))
        description = _clean_student_text(str(properties.get("description") or neighbor_name))
        neighbors.append(
            {
                "name": neighbor_name,
                "relationship": relationship or "关联",
                "description": description or neighbor_name,
            }
        )
    return _unique_neighbors(neighbors)


def _extended_neighbors_for_label(label: str, graph: Mapping[str, Any]) -> list[dict[str, Any]]:
    normalized_label = _normalize_entity_label(label)
    edges = _graph_edges(graph.get("edges"))
    direct_neighbors = [
        neighbor["name"]
        for neighbor in _neighbors_for_label(label, graph)
        if str(neighbor.get("name") or "").strip()
    ]
    direct_neighbor_set = set(direct_neighbors)
    extended: list[dict[str, Any]] = []
    for via in direct_neighbors:
        normalized_via = _normalize_entity_label(via)
        for edge in edges:
            source = str(edge.get("source") or "").strip()
            target = str(edge.get("target") or "").strip()
            if not source or not target:
                continue
            source_matches_via = source == via or (_normalize_entity_label(source) == normalized_via and normalized_via)
            target_matches_via = target == via or (_normalize_entity_label(target) == normalized_via and normalized_via)
            if not source_matches_via and not target_matches_via:
                continue
            to_name = target if source_matches_via else source
            normalized_to = _normalize_entity_label(to_name)
            if not normalized_to or normalized_to == normalized_label or normalized_to == normalized_via:
                continue
            if to_name in direct_neighbor_set:
                continue
            properties = edge.get("properties")
            if not isinstance(properties, Mapping):
                properties = {}
            if _is_alias_relation(properties):
                continue
            extended.append(
                {
                    "from": label,
                    "via": via,
                    "to": to_name,
                    "relationship": _readable_relationship(properties),
                    "description": _readable_description(properties.get("description") or to_name),
                    "path": [label, via, to_name],
                    "depth": 2,
                    "weight": _edge_weight(properties),
                }
            )
    return sorted(_unique_neighbors(extended), key=lambda item: (-float(item.get("weight") or 0), str(item.get("via") or ""), str(item.get("to") or "")))


def _is_alias_relation(properties: Mapping[str, Any]) -> bool:
    tokens = _keyword_tokens(properties.get("keywords") or properties.get("relationship") or "")
    if not tokens:
        return False
    alias_count = sum(1 for token in tokens if any(fragment in token for fragment in ALIAS_RELATION_FRAGMENTS))
    return alias_count / len(tokens) >= 0.5


def _readable_relationship(properties: Mapping[str, Any]) -> str:
    tokens = _keyword_tokens(properties.get("keywords") or properties.get("relationship") or "")
    for token in tokens:
        if token in GENERIC_RELATION_TOKENS:
            continue
        if any(fragment in token for fragment in ALIAS_RELATION_FRAGMENTS):
            continue
        return _trim_text(token, RELATIONSHIP_MAX_LENGTH)
    return "关联"


def _readable_description(value: object) -> str:
    clean = _clean_student_text(str(value or ""))
    if not clean:
        return ""
    match = re.match(r"(.+?[。！？；;])", clean)
    sentence = match.group(1) if match else clean
    return _trim_text(sentence, EXTENDED_DESCRIPTION_MAX_LENGTH)


def _keyword_tokens(value: object) -> list[str]:
    clean = _clean_student_text(str(value or ""))
    return [token.strip() for token in re.split(r"[,，、;；\s]+", clean) if token.strip()]


def _trim_text(value: object, max_length: int) -> str:
    clean = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(clean) <= max_length:
        return clean
    return clean[: max_length - 1].rstrip() + "…"


def _edge_weight(properties: Mapping[str, Any]) -> float:
    try:
        return float(properties.get("weight") or 0)
    except (TypeError, ValueError):
        return 0.0


def _unique_neighbors(neighbors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique: dict[tuple[str, ...], dict[str, Any]] = {}
    for neighbor in neighbors:
        if neighbor.get("depth") == 2:
            key = (
                str(neighbor.get("from") or ""),
                str(neighbor.get("via") or ""),
                str(neighbor.get("to") or ""),
                str(neighbor.get("relationship") or ""),
                str(neighbor.get("description") or ""),
            )
        else:
            key = (
                str(neighbor.get("name") or ""),
                str(neighbor.get("relationship") or ""),
                str(neighbor.get("description") or ""),
            )
        unique.setdefault(key, neighbor)
    return list(unique.values())


def _context_with_lightrag_timeout(context: Any, *, timeout_seconds: float | None) -> Any:
    if timeout_seconds is None or not isinstance(context.retrieval_client, LightRAGClient):
        return context
    from dataclasses import replace

    config = context.retrieval_client.config
    return replace(
        context,
        retrieval_client=LightRAGClient(
            LightRAGConfig(
                base_url=config.base_url,
                api_key=config.api_key,
                timeout_seconds=timeout_seconds,
            )
        ),
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build page-ready entity graph detail cache from LightRAG /graphs.")
    parser.add_argument("--chapters", default="1-3", help="Chapter selection, e.g. 1-3 or 1,2,3.")
    parser.add_argument("--manifest", type=Path, default=Path("book/chapters_manifest.json"))
    parser.add_argument("--data-dir", type=Path, default=Path("data/app"))
    parser.add_argument("--static-dir", type=Path, default=Path("static"))
    parser.add_argument("--output", type=Path, default=Path("data/app/entity_graph_cache.json"))
    parser.add_argument("--postgres", action="store_true", help="Read chapter cards from PostgreSQL.")
    parser.add_argument("--sync-postgres", action="store_true", help="Upsert generated graph cache into PostgreSQL.")
    parser.add_argument("--replace", action="store_true", help="Replace the output file instead of merging.")
    parser.add_argument("--skip-existing", action="store_true", help="Skip entities already present in output file.")
    parser.add_argument("--max-depth", type=int, default=1)
    parser.add_argument("--max-nodes", type=int, default=100)
    parser.add_argument("--lightrag-timeout", type=float, default=None, help="Override LightRAG request timeout in seconds.")
    parser.add_argument(
        "--include-topic-titles",
        action="store_true",
        help="Also fetch graph cache entries for published topic titles such as 螃蟹宴.",
    )
    return parser.parse_args(sys.argv[1:] if argv is None else argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        chapters = parse_chapter_selection(args.chapters)
        context = create_app_context(
            manifest_path=args.manifest,
            data_dir=args.data_dir,
            static_dir=args.static_dir,
            use_env_retrieval=True,
            use_env_content_store=args.postgres,
            use_postgres_store=args.postgres,
        )
        context = _context_with_lightrag_timeout(context, timeout_seconds=args.lightrag_timeout)
        existing = {} if args.replace else read_cache(args.output)
        selected_names = graph_cache_names_for_store(
            context.store,
            chapters,
            include_topic_titles=args.include_topic_titles,
        )
        sync_names = names_to_sync(selected_names, existing, skip_existing=args.skip_existing)
        cache = build_entity_graph_cache_for_context(
            context=context,
            chapters=chapters,
            max_depth=args.max_depth,
            max_nodes=args.max_nodes,
            existing=existing,
            skip_existing=args.skip_existing,
            include_topic_titles=args.include_topic_titles,
        )
        write_cache(args.output, cache)
        if args.sync_postgres:
            database_url = load_database_url(load_dotenv()) or load_database_url()
            if database_url is None:
                raise RuntimeError("DATABASE_URL is not set for PostgreSQL sync")
            sync_cache_to_postgres({name: cache[name] for name in sync_names if name in cache}, database_url)
    except Exception as exc:  # noqa: BLE001 - CLI reports actionable failures.
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"Entity graph cache built: {len(cache)} entities")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
