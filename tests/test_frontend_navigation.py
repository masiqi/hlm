import json
import re
import threading
from pathlib import Path
from http.server import ThreadingHTTPServer

import pytest
from playwright.sync_api import expect, sync_playwright

from hlm_kg.web_app import create_app_context, make_handler


def topic_id_for_title(title: str) -> str:
    topics = json.loads(Path("data/app/topics.json").read_text(encoding="utf-8"))
    return next(topic["id"] for topic in topics if topic["title"] == title)


@pytest.fixture(scope="module")
def app_url():
    context = create_app_context(
        manifest_path=Path("book/chapters_manifest.json"),
        data_dir=Path("data/app"),
        static_dir=Path("static"),
    )
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(context))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.fixture()
def page():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            yield page
        finally:
            browser.close()


def test_topic_detail_uses_browser_history_back_to_topic_list(app_url, page):
    page.goto(app_url)

    page.get_by_role("navigation").get_by_role("button", name="看专题").click()
    expect(page).to_have_url(re.compile(r"#/topics$"))
    expect(page.locator("#topic-list")).to_contain_text("关键事件")

    page.get_by_text("关键事件").click()
    hulu_card = page.locator("article", has_text="葫芦案").first
    hulu_card.get_by_role("button", name="查看专题").click()
    expect(page).to_have_url(re.compile(r"#/topics/.+"))
    expect(page.locator("#topic-list")).to_contain_text("专题简介")
    expect(page.locator("#topic-list")).to_contain_text("贾雨村")

    page.go_back()
    expect(page).to_have_url(re.compile(r"#/topics$"))
    expect(page.locator("#topic-list")).to_contain_text("关键事件")
    expect(page.locator("#topic-list")).not_to_contain_text("返回专题")


def test_chapter_hash_route_and_chapter_controls_use_browser_history(app_url, page):
    page.goto(f"{app_url}/#/chapters/4")

    expect(page.locator("#chapter-content")).to_contain_text("第 4 回")

    page.get_by_role("button", name="下一回").click()
    expect(page).to_have_url(re.compile(r"#/chapters/5$"))
    expect(page.locator("#chapter-content")).to_contain_text("第 5 回")

    page.go_back()
    expect(page).to_have_url(re.compile(r"#/chapters/4$"))
    expect(page.locator("#chapter-content")).to_contain_text("第 4 回")


def test_direct_topic_detail_hash_route_loads_detail(app_url, page):
    page.goto(f"{app_url}/#/topics/{topic_id_for_title('葫芦案')}")

    expect(page.locator("#topic-list")).to_contain_text("葫芦案")
    expect(page.locator("#topic-list")).to_contain_text("专题简介")
    expect(page.locator("#topic-list")).to_contain_text("贾雨村")


def test_topic_fact_chapter_jump_can_go_back_to_topic_detail(app_url, page):
    page.goto(app_url)
    page.get_by_role("navigation").get_by_role("button", name="看专题").click()
    page.get_by_text("关键事件").click()
    page.locator("article", has_text="葫芦案").first.get_by_role("button", name="查看专题").click()
    expect(page.locator("#topic-list")).to_contain_text("贾雨村")

    page.locator("#topic-list .source button", has_text="第 4 回").first.click()
    expect(page).to_have_url(re.compile(r"#/chapters/4$"))
    expect(page.locator("#chapter-content")).to_contain_text("第 4 回")

    page.go_back()
    expect(page).to_have_url(re.compile(r"#/topics/.+"))
    expect(page.locator("#topic-list")).to_contain_text("葫芦案")
    expect(page.locator("#topic-list")).to_contain_text("贾雨村")


def test_knowledge_card_panel_is_addressable_and_browser_back_closes_it(app_url, page):
    page.goto(app_url)
    page.get_by_role("navigation").get_by_role("button", name="看专题").click()
    page.get_by_text("关键事件").click()
    page.locator("article", has_text="葫芦案").first.get_by_role("button", name="查看专题").click()
    expect(page.locator("#topic-list")).to_contain_text("核心知识卡")

    page.locator("#topic-list [data-card-id]").first.click()
    expect(page).to_have_url(re.compile(r"#/topics/.+\\?card=.+"))
    expect(page.locator("#topic-knowledge-panel")).to_have_class(re.compile(r"open"))

    page.go_back()
    expect(page).to_have_url(re.compile(r"#/topics/.+"))
    expect(page.locator("#topic-knowledge-panel")).not_to_have_class(re.compile(r"open"))


def test_home_common_question_routes_to_ask_and_browser_back_returns_home(app_url, page):
    page.goto(app_url)

    page.locator("#common-entries button", has_text="黛玉葬花").click()
    expect(page).to_have_url(re.compile(r"#/ask\?q=.+"))
    expect(page.locator("#ask")).to_contain_text("依据")

    page.go_back()
    expect(page.locator("#home")).to_have_class(re.compile(r"active"))
    expect(page.locator("#common-entries")).to_contain_text("黛玉葬花")
