from hlm_kg.evidence_adapter import normalize_query_data_response


def test_normalize_hybrid_entity_and_relationship_candidates():
    response = {
        "status": "success",
        "data": {
            "entities": [
                {
                    "entity_name": "宝黛初会",
                    "entity_type": "chapterepisode",
                    "description": "贾宝玉与林黛玉在贾府初次见面的经典情节。",
                    "source_id": "doc-abc-chunk-009",
                    "file_path": "003-第三回-托内兄如海荐西宾 接外孙贾母惜孤女.txt",
                }
            ],
            "relationships": [
                {
                    "src_id": "宝黛初会",
                    "tgt_id": "贾宝玉",
                    "keywords": "参与情节",
                    "description": "贾宝玉在贾母处与林黛玉初次相见。",
                    "source_id": "doc-abc-chunk-010",
                    "file_path": "003-第三回-托内兄如海荐西宾 接外孙贾母惜孤女.txt",
                }
            ],
            "chunks": [],
            "references": [],
        },
        "metadata": {"query_mode": "hybrid"},
    }

    candidates = normalize_query_data_response(response, question="宝黛初会发生在哪一回")

    assert [candidate.kind for candidate in candidates] == ["relationship", "entity"]
    assert candidates[0].title == "宝黛初会 -> 贾宝玉"
    assert candidates[0].relationship_keywords == "参与情节"
    assert candidates[0].chapter_sources[0].chapter_number == 3
    assert candidates[0].query_mode == "hybrid"
    assert candidates[0].score > candidates[1].score


def test_normalize_naive_chunk_and_reference_candidates():
    response = {
        "status": "success",
        "data": {
            "entities": [],
            "relationships": [],
            "chunks": [
                {
                    "reference_id": "2",
                    "content": "第5章 贾宝玉神游太虚境。宝玉黛玉二人的亲密友爱，也较别人不同。",
                    "file_path": "005-第五回-贾宝玉神游太虚境 警幻仙曲演红楼梦.txt",
                    "chunk_id": "doc-005-chunk-000",
                }
            ],
            "references": [
                {
                    "reference_id": "2",
                    "file_path": "005-第五回-贾宝玉神游太虚境 警幻仙曲演红楼梦.txt",
                }
            ],
        },
        "metadata": {"query_mode": "naive"},
    }

    candidates = normalize_query_data_response(response, question="宝玉黛玉亲密")

    assert [candidate.kind for candidate in candidates] == ["chunk", "reference"]
    assert candidates[0].chunk_id == "doc-005-chunk-000"
    assert candidates[0].reference_id == "2"
    assert candidates[0].chapter_sources[0].chapter_number == 5
    assert candidates[1].title == "005-第五回-贾宝玉神游太虚境 警幻仙曲演红楼梦.txt"


def test_normalize_sep_file_paths_and_source_ids():
    response = {
        "data": {
            "entities": [
                {
                    "entity_name": "宝黛亲密",
                    "entity_type": "relationship",
                    "description": "两人多处情节显示亲密。",
                    "source_id": "doc-a<SEP>doc-b",
                    "file_path": (
                        "005-第五回-贾宝玉神游太虚境 警幻仙曲演红楼梦.txt<SEP>"
                        "027-第二十七回-滴翠亭杨妃戏彩蝶 埋香冢飞燕泣残红.txt"
                    ),
                }
            ],
            "relationships": [],
            "chunks": [],
            "references": [],
        },
        "metadata": {"query_mode": "mix"},
    }

    [candidate] = normalize_query_data_response(response)

    assert candidate.source_ids == ["doc-a", "doc-b"]
    assert [source.chapter_number for source in candidate.chapter_sources] == [5, 27]


def test_normalize_ignores_unusable_top_level_response():
    assert normalize_query_data_response({"status": "failure", "data": {}}) == []
    assert normalize_query_data_response({"data": "not a dict"}) == []
