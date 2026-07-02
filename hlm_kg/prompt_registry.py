from __future__ import annotations

import json
from pathlib import Path

from hlm_kg.domain import PromptDefinition


class PromptRegistry:
    def __init__(self, definitions: list[PromptDefinition]) -> None:
        self._definitions = {definition.name: definition for definition in definitions}

    @classmethod
    def from_path(cls, path: Path) -> PromptRegistry:
        payload = json.loads(path.read_text(encoding="utf-8"))
        definitions = [
            PromptDefinition(
                name=str(item["name"]),
                version=str(item["version"]),
                purpose=str(item["purpose"]),
                input_schema=str(item["input_schema"]),
                output_schema=str(item["output_schema"]),
                evidence_rules=list(item.get("evidence_rules", [])),
                refusal_rules=list(item.get("refusal_rules", [])),
                content_requirements=list(item.get("content_requirements", [])),
            )
            for item in payload["prompt_definitions"]
        ]
        return cls(definitions)

    def get(self, name: str) -> PromptDefinition:
        return self._definitions[name]

    def find_by_rule(self, text: str) -> list[PromptDefinition]:
        return [
            definition
            for definition in self._definitions.values()
            if any(text in rule for rule in definition.evidence_rules + definition.refusal_rules)
        ]
