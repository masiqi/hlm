from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CandidateEntity:
    name: str
    type: str
    card_id: str | None = None
    aliases: tuple[str, ...] = ()
    score: int = 0


@dataclass(frozen=True)
class ResolvedEntity:
    mention: str
    canonical_id: str | None
    canonical_name: str | None
    canonical_type: str | None
    aliases: tuple[str, ...]
    confidence: str
    ambiguity: tuple[CandidateEntity, ...] = ()


class EntityResolver:
    def __init__(self, store: Any) -> None:
        self._cards = _knowledge_cards_for_resolution(store)

    def mentions_in_text(self, text: str) -> tuple[str, ...]:
        content = str(text or "")
        mentions: list[str] = []
        for card in self._cards:
            name = _card_name(card)
            if name and name in content:
                mentions.append(name)
        mentions.sort(key=len, reverse=True)
        deduped: list[str] = []
        for mention in mentions:
            if any(mention in existing for existing in deduped):
                continue
            deduped.append(mention)
        return tuple(deduped)

    def resolve_mention(self, mention: str, *, context_text: str = "") -> ResolvedEntity:
        clean_mention = str(mention or "").strip()
        if not clean_mention:
            return ResolvedEntity(
                mention=clean_mention,
                canonical_id=None,
                canonical_name=None,
                canonical_type=None,
                aliases=(),
                confidence="unresolved",
            )

        exact = [_candidate_from_card(card, clean_mention) for card in self._cards if _card_name(card) == clean_mention]
        containing = [
            _candidate_from_card(card, clean_mention)
            for card in self._cards
            if clean_mention in _card_name(card) and _card_name(card) != clean_mention
        ]
        candidates = _dedupe_candidates(exact + containing)
        if not candidates:
            return ResolvedEntity(
                mention=clean_mention,
                canonical_id=None,
                canonical_name=None,
                canonical_type=None,
                aliases=(clean_mention,),
                confidence="unresolved",
            )

        exact_structural = [candidate for candidate in exact if _is_structurally_exact(clean_mention, candidate)]
        if exact_structural:
            return _resolved(
                clean_mention,
                exact_structural[0],
                "exact",
                extra_aliases=_aliases_for_candidate(exact_structural[0], self._cards),
            )

        preferred_type = _preferred_type_from_context(context_text)
        if preferred_type:
            typed = [candidate for candidate in candidates if candidate.type == preferred_type]
            if typed:
                selection_pool = _selection_pool_for_typed_context(clean_mention, typed)
                ranked = sorted(selection_pool, key=lambda candidate: -candidate.score)
                selected = ranked[0]
                ambiguity = tuple(candidate for candidate in typed if candidate.name != selected.name)
                return _resolved(
                    clean_mention,
                    selected,
                    "high",
                    ambiguity=ambiguity,
                    extra_aliases=_aliases_for_candidate(selected, self._cards),
                )

        selected, ambiguity = _select_with_ambiguity(clean_mention, candidates)
        if selected is not None and not ambiguity:
            confidence = "exact" if selected.name == clean_mention else "high"
            return _resolved(
                clean_mention,
                selected,
                confidence,
                extra_aliases=_aliases_for_candidate(selected, self._cards),
            )

        return ResolvedEntity(
            mention=clean_mention,
            canonical_id=None,
            canonical_name=None,
            canonical_type=None,
            aliases=(clean_mention,),
            confidence="ambiguous",
            ambiguity=tuple(candidates),
        )


def _knowledge_cards_for_resolution(store: Any) -> list[Any]:
    fallback_store = getattr(store, "fallback_store", None)
    if fallback_store is not None and fallback_store is not store:
        return _knowledge_cards_for_resolution(fallback_store)
    try:
        cards = getattr(store, "knowledge_cards")
    except Exception:  # noqa: BLE001 - resolver should degrade to unresolved
        return []
    if callable(cards):
        try:
            cards = cards()
        except Exception:  # noqa: BLE001 - resolver should degrade to unresolved
            return []
    if isinstance(cards, dict):
        cards = list(cards.values())
    if not isinstance(cards, list):
        return []
    return [card for card in cards if _card_name(card)]


def _card_name(card: Any) -> str:
    return str(getattr(card, "name", "") or "").strip()


def _card_type(card: Any) -> str:
    return str(getattr(card, "type", "") or "").strip()


def _candidate_from_card(card: Any, mention: str) -> CandidateEntity:
    name = _card_name(card)
    aliases = tuple(item for item in (mention, name) if item)
    return CandidateEntity(
        name=name,
        type=_card_type(card),
        card_id=str(getattr(card, "id", "") or "") or None,
        aliases=_dedupe_strings(aliases),
        score=_candidate_score(mention, name, _card_type(card)),
    )


def _candidate_score(mention: str, name: str, entity_type: str) -> int:
    score = 0
    if name == mention:
        score += 100
    if name.endswith(mention) and name != mention:
        score += max(10, 50 - (len(name) * 3))
    if entity_type == "person":
        score += 20
    if name != mention:
        score += max(0, 8 - len(name))
    return score


def _is_structurally_exact(mention: str, candidate: CandidateEntity) -> bool:
    if candidate.name != mention:
        return False
    if len(mention) >= 3 and candidate.type != "person":
        return True
    return len(mention) >= 3 and candidate.type == "person"


def _preferred_type_from_context(context_text: str) -> str | None:
    context = str(context_text or "")
    if any(term in context for term in ("几岁", "多大", "年纪", "年龄", "怎么死", "死因", "去世", "性格", "为人")):
        return "person"
    return None


def _select_with_ambiguity(
    mention: str,
    candidates: list[CandidateEntity],
) -> tuple[CandidateEntity | None, list[CandidateEntity]]:
    if not candidates:
        return None, []
    ranked = sorted(candidates, key=lambda candidate: -candidate.score)
    if len(ranked) == 1:
        return ranked[0], []
    top = ranked[0]
    same_type_contenders = [
        candidate
        for candidate in ranked[1:]
        if candidate.type == top.type and (candidate.name.endswith(mention) or candidate.name == mention)
    ]
    if same_type_contenders:
        return None, ranked
    return top, ranked[1:]


def _selection_pool_for_typed_context(mention: str, candidates: list[CandidateEntity]) -> list[CandidateEntity]:
    if len(mention) > 2:
        return candidates
    expanded = [
        candidate
        for candidate in candidates
        if candidate.name != mention and candidate.name.endswith(mention) and candidate.type == "person"
    ]
    return expanded or candidates


def _resolved(
    mention: str,
    candidate: CandidateEntity,
    confidence: str,
    *,
    ambiguity: tuple[CandidateEntity, ...] = (),
    extra_aliases: tuple[str, ...] = (),
) -> ResolvedEntity:
    aliases = _dedupe_strings((mention, *candidate.aliases, candidate.name, *extra_aliases))
    return ResolvedEntity(
        mention=mention,
        canonical_id=candidate.card_id,
        canonical_name=candidate.name,
        canonical_type=candidate.type,
        aliases=aliases,
        confidence=confidence,
        ambiguity=ambiguity,
    )


def _aliases_for_candidate(candidate: CandidateEntity, cards: list[Any]) -> tuple[str, ...]:
    if candidate.type != "person":
        return ()
    aliases: list[str] = []
    for card in cards:
        alias = _card_name(card)
        if not alias or alias == candidate.name:
            continue
        if 2 <= len(alias) < len(candidate.name) and candidate.name.endswith(alias):
            aliases.append(alias)
    return _dedupe_strings(tuple(aliases))


def _dedupe_candidates(candidates: list[CandidateEntity]) -> list[CandidateEntity]:
    deduped: list[CandidateEntity] = []
    seen: set[tuple[str, str, str | None]] = set()
    for candidate in candidates:
        key = (candidate.name, candidate.type, candidate.card_id)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
    return deduped


def _dedupe_strings(items: tuple[str, ...]) -> tuple[str, ...]:
    deduped: list[str] = []
    for item in items:
        if item and item not in deduped:
            deduped.append(item)
    return tuple(deduped)
