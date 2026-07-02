from hlm_kg.chapter_sources import parse_chapter_source, parse_chapter_sources


def test_parse_standard_chapter_file_path():
    source = parse_chapter_source("003-第三回-托内兄如海荐西宾 接外孙贾母惜孤女.txt")

    assert source is not None
    assert source.chapter_number == 3
    assert source.chapter_label == "第三回"
    assert source.chapter_title == "托内兄如海荐西宾 接外孙贾母惜孤女"
    assert source.source_file == "003-第三回-托内兄如海荐西宾 接外孙贾母惜孤女.txt"


def test_parse_path_with_directory():
    source = parse_chapter_source("book/chapters/120-第一百二十回-甄士隐详说太虚情 贾雨村归结红楼梦.txt")

    assert source is not None
    assert source.chapter_number == 120
    assert source.chapter_label == "第一百二十回"
    assert source.chapter_title == "甄士隐详说太虚情 贾雨村归结红楼梦"


def test_parse_multiple_sep_sources_deduplicates():
    sources = parse_chapter_sources(
        "003-第三回-托内兄如海荐西宾 接外孙贾母惜孤女.txt<SEP>"
        "003-第三回-托内兄如海荐西宾 接外孙贾母惜孤女.txt<SEP>"
        "027-第二十七回-滴翠亭杨妃戏彩蝶 埋香冢飞燕泣残红.txt"
    )

    assert [source.chapter_number for source in sources] == [3, 27]


def test_non_chapter_source_returns_none():
    assert parse_chapter_source("not-a-chapter.md") is None


def test_parse_blank_multiple_sources_returns_empty_list():
    assert parse_chapter_sources(None) == []
    assert parse_chapter_sources("") == []
