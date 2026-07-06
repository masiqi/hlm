from scripts.sync_entity_graph_cache_postgres import (
    graph_cache_rows_for_sync,
    iter_batches,
    sync_rows_to_postgres,
)


class FakeCursor:
    def __init__(self):
        self.executemany_calls = []
        self.execute_calls = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def executemany(self, sql, params):
        self.executemany_calls.append((sql, params))

    def execute(self, sql, params=None):
        self.execute_calls.append((sql, params))


class FakeConnection:
    def __init__(self):
        self.cursor_obj = FakeCursor()
        self.commits = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def cursor(self):
        return self.cursor_obj

    def commit(self):
        self.commits += 1


def test_graph_cache_rows_for_sync_omits_raw_graph_by_default():
    cache = {
        "顽石": {
            "description": "无才补天被弃于青埂峰下的石头。",
            "neighbors": [{"name": "通灵宝玉", "relationship": "前世本体"}],
            "extended_neighbors": [{"via": "通灵宝玉", "to": "贾宝玉", "depth": 2}],
            "raw_graph": {"nodes": [{"id": "顽石"}], "edges": []},
            "metadata": {"source": "lightrag_graph"},
        }
    }

    rows = graph_cache_rows_for_sync(cache)

    assert rows == [
        {
            "entity_name": "顽石",
            "description": "无才补天被弃于青埂峰下的石头。",
            "neighbors": [{"name": "通灵宝玉", "relationship": "前世本体"}],
            "extended_neighbors": [{"via": "通灵宝玉", "to": "贾宝玉", "depth": 2}],
            "raw_graph": {},
            "metadata": {"source": "lightrag_graph", "raw_graph_omitted": True},
        }
    ]


def test_graph_cache_rows_for_sync_can_include_raw_graph_when_requested():
    cache = {
        "顽石": {
            "description": "无才补天被弃于青埂峰下的石头。",
            "neighbors": [],
            "extended_neighbors": [],
            "raw_graph": {"nodes": [{"id": "顽石"}]},
            "metadata": {},
        }
    }

    rows = graph_cache_rows_for_sync(cache, include_raw_graph=True)

    assert rows[0]["raw_graph"] == {"nodes": [{"id": "顽石"}]}
    assert "raw_graph_omitted" not in rows[0]["metadata"]


def test_iter_batches_chunks_items():
    assert list(iter_batches([1, 2, 3, 4, 5], 2)) == [[1, 2], [3, 4], [5]]


def test_sync_rows_to_postgres_batches_commits_and_reports_progress():
    conn = FakeConnection()
    messages = []
    rows = [
        {
            "entity_name": f"实体{i}",
            "description": "",
            "neighbors": [],
            "extended_neighbors": [],
            "raw_graph": {},
            "metadata": {},
        }
        for i in range(5)
    ]

    sync_rows_to_postgres(
        rows,
        "postgresql://example",
        batch_size=2,
        connect=lambda _: conn,
        progress=messages.append,
    )

    assert conn.commits == 3
    assert [len(params) for _, params in conn.cursor_obj.executemany_calls] == [2, 2, 1]
    assert messages == [
        "[1/3] synced entity_graph_cache rows 1-2 of 5",
        "[2/3] synced entity_graph_cache rows 3-4 of 5",
        "[3/3] synced entity_graph_cache rows 5-5 of 5",
    ]


def test_sync_rows_to_postgres_can_delete_existing_and_prune_missing():
    conn = FakeConnection()
    rows = [
        {
            "entity_name": "顽石",
            "description": "",
            "neighbors": [],
            "extended_neighbors": [],
            "raw_graph": {},
            "metadata": {},
        }
    ]

    sync_rows_to_postgres(
        rows,
        "postgresql://example",
        batch_size=10,
        delete_existing=True,
        prune_missing=True,
        connect=lambda _: conn,
        progress=lambda message: None,
    )

    executed_sql = [sql for sql, _ in conn.cursor_obj.execute_calls]
    assert any("DELETE FROM entity_graph_cache WHERE entity_name = ANY" in sql for sql in executed_sql)
    assert any("DELETE FROM entity_graph_cache WHERE NOT (entity_name = ANY" in sql for sql in executed_sql)
    assert conn.commits == 3
