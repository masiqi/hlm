from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Mapping


class LightRAGError(RuntimeError):
    """Raised when a LightRAG HTTP request or response cannot be used."""


@dataclass(frozen=True)
class LightRAGConfig:
    base_url: str
    api_key: str | None = None
    timeout_seconds: float = 30.0

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "LightRAGConfig | None":
        base_url = env.get("LIGHTRAG_BASE_URL", "").strip()
        if not base_url:
            return None
        timeout_seconds = 30.0
        timeout_value = env.get("LIGHTRAG_TIMEOUT_SECONDS", "").strip()
        if timeout_value:
            try:
                timeout_seconds = float(timeout_value)
            except ValueError as exc:
                raise LightRAGError("Invalid LIGHTRAG_TIMEOUT_SECONDS; expected a number.") from exc
        api_key = env.get("LIGHTRAG_API_KEY", "").strip() or None
        return cls(base_url=base_url.rstrip("/"), api_key=api_key, timeout_seconds=timeout_seconds)


class LightRAGClient:
    def __init__(self, config: LightRAGConfig):
        self.config = config

    def query_data(self, query: str, mode: str = "hybrid", **options: object) -> dict[str, Any]:
        payload = {"query": query, "mode": mode, **options}
        response = self._post_json("/query/data", payload)
        if not isinstance(response, dict):
            raise LightRAGError("Expected JSON object from /query/data.")
        return response

    def search_labels(self, q: str, limit: int = 10) -> list[str]:
        response = self._get_json("/graph/label/search", {"q": q, "limit": str(limit)})
        if isinstance(response, list):
            return [str(label) for label in response]
        raise LightRAGError("Expected JSON array from /graph/label/search.")

    def entity_exists(self, name: str) -> bool:
        response = self._get_json("/graph/entity/exists", {"name": name})
        if isinstance(response, bool):
            return response
        if isinstance(response, dict) and isinstance(response.get("exists"), bool):
            return bool(response["exists"])
        raise LightRAGError("Expected boolean existence result from /graph/entity/exists.")

    def graph(self, label: str, max_depth: int = 3, max_nodes: int = 1000) -> dict[str, Any]:
        response = self._get_json(
            "/graphs",
            {"label": label, "max_depth": str(max_depth), "max_nodes": str(max_nodes)},
        )
        if isinstance(response, dict):
            return response
        raise LightRAGError("Expected JSON object from /graphs.")

    def _get_json(self, path: str, params: Mapping[str, str]) -> Any:
        query = urllib.parse.urlencode(params)
        url = f"{self.config.base_url}{path}"
        if query:
            url = f"{url}?{query}"
        request = urllib.request.Request(url, headers=self._headers(), method="GET")
        return self._request_json(request)

    def _post_json(self, path: str, payload: Mapping[str, object]) -> Any:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            f"{self.config.base_url}{path}",
            data=data,
            headers=self._headers(content_type="application/json"),
            method="POST",
        )
        return self._request_json(request)

    def _headers(self, *, content_type: str | None = None) -> dict[str, str]:
        headers: dict[str, str] = {}
        if content_type:
            headers["Content-Type"] = content_type
        if self.config.api_key:
            headers["X-API-Key"] = self.config.api_key
        return headers

    def _request_json(self, request: urllib.request.Request) -> Any:
        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
                status = response.getcode()
                body = response.read()
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
            detail = f": {body[:500]}" if body else ""
            raise LightRAGError(f"HTTP {exc.code} from {_safe_url(request.full_url)}{detail}") from exc
        except urllib.error.URLError as exc:
            raise LightRAGError(f"Request failed for {_safe_url(request.full_url)}: {exc.reason}") from exc

        if status < 200 or status >= 300:
            raise LightRAGError(f"HTTP {status} from {_safe_url(request.full_url)}")
        if not body:
            return {}
        try:
            return json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise LightRAGError(f"Invalid JSON from {_safe_url(request.full_url)}.") from exc


def _safe_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit(("", "", parsed.path, parsed.query, ""))
