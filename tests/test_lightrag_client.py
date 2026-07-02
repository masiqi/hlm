import json
import urllib.error

import pytest

from hlm_kg.lightrag_client import LightRAGClient, LightRAGConfig, LightRAGError


class FakeResponse:
    def __init__(self, body: bytes, status: int = 200):
        self.body = body
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return self.body

    def getcode(self):
        return self.status


def header_value(request, name):
    lower_name = name.lower()
    for key, value in request.header_items():
        if key.lower() == lower_name:
            return value
    return None


def test_config_from_env_returns_none_without_base_url():
    assert LightRAGConfig.from_env({}) is None


def test_config_from_env_reads_url_api_key_and_timeout():
    config = LightRAGConfig.from_env(
        {
            "LIGHTRAG_BASE_URL": "http://10.1.0.246:9621/",
            "LIGHTRAG_API_KEY": "secret-key",
            "LIGHTRAG_TIMEOUT_SECONDS": "7.5",
        }
    )

    assert config == LightRAGConfig(
        base_url="http://10.1.0.246:9621",
        api_key="secret-key",
        timeout_seconds=7.5,
    )


def test_query_data_posts_json_with_api_key(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return FakeResponse(json.dumps({"chunks": [{"content": "宝黛初会"}]}).encode("utf-8"))

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    client = LightRAGClient(
        LightRAGConfig(base_url="http://lightrag.example", api_key="secret-key", timeout_seconds=3.0)
    )

    result = client.query_data("宝黛初会", mode="hybrid", top_k=5, only_need_context=True)

    assert result == {"chunks": [{"content": "宝黛初会"}]}
    request = captured["request"]
    assert request.full_url == "http://lightrag.example/query/data"
    assert request.get_method() == "POST"
    assert captured["timeout"] == 3.0
    assert header_value(request, "Content-Type") == "application/json"
    assert header_value(request, "X-API-Key") == "secret-key"
    assert json.loads(request.data.decode("utf-8")) == {
        "query": "宝黛初会",
        "mode": "hybrid",
        "top_k": 5,
        "only_need_context": True,
    }


def test_search_labels_gets_encoded_query_without_api_key(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return FakeResponse(json.dumps(["林黛玉", "林黛玉-人物"]).encode("utf-8"))

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    client = LightRAGClient(LightRAGConfig(base_url="http://lightrag.example", timeout_seconds=12.0))

    labels = client.search_labels("林黛玉 贾宝玉", limit=2)

    assert labels == ["林黛玉", "林黛玉-人物"]
    request = captured["request"]
    assert request.full_url == (
        "http://lightrag.example/graph/label/search?"
        "q=%E6%9E%97%E9%BB%9B%E7%8E%89+%E8%B4%BE%E5%AE%9D%E7%8E%89&limit=2"
    )
    assert request.get_method() == "GET"
    assert captured["timeout"] == 12.0
    assert header_value(request, "X-API-Key") is None


def test_entity_exists_gets_encoded_name_and_returns_bool(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["request"] = request
        return FakeResponse(json.dumps({"exists": True}).encode("utf-8"))

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    client = LightRAGClient(LightRAGConfig(base_url="http://lightrag.example"))

    assert client.entity_exists("林黛玉") is True
    assert captured["request"].full_url == (
        "http://lightrag.example/graph/entity/exists?"
        "name=%E6%9E%97%E9%BB%9B%E7%8E%89"
    )


def test_http_error_raises_lightrag_error_without_sensitive_headers(monkeypatch):
    def fake_urlopen(request, timeout):
        raise urllib.error.HTTPError(
            request.full_url,
            500,
            "Internal Server Error",
            hdrs=None,
            fp=None,
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    client = LightRAGClient(
        LightRAGConfig(base_url="http://lightrag.example", api_key="super-secret-token")
    )

    with pytest.raises(LightRAGError) as exc_info:
        client.query_data("宝黛初会")

    message = str(exc_info.value)
    assert "HTTP 500" in message
    assert "/query/data" in message
    assert "super-secret-token" not in message
    assert "X-API-Key" not in message


def test_non_2xx_response_raises_lightrag_error(monkeypatch):
    def fake_urlopen(request, timeout):
        return FakeResponse(b'{"error":"bad gateway"}', status=502)

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    client = LightRAGClient(LightRAGConfig(base_url="http://lightrag.example"))

    with pytest.raises(LightRAGError) as exc_info:
        client.entity_exists("林黛玉")

    assert "HTTP 502" in str(exc_info.value)
    assert "/graph/entity/exists" in str(exc_info.value)


def test_invalid_json_raises_lightrag_error(monkeypatch):
    def fake_urlopen(request, timeout):
        return FakeResponse(b"not-json")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    client = LightRAGClient(LightRAGConfig(base_url="http://lightrag.example"))

    with pytest.raises(LightRAGError) as exc_info:
        client.search_labels("林黛玉")

    assert "Invalid JSON" in str(exc_info.value)
    assert "/graph/label/search" in str(exc_info.value)
