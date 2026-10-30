import os
import base64
from types import SimpleNamespace

import pytest

from wing_stock.browser import check_access, download_report, launch_context, login, navigate_inventory, read_table, require_wing_url
from wing_stock.report import ReportError, parse_report


@pytest.mark.parametrize("url", ["http://wing.coupang.com/", "https://other.example/", "https://wing.coupang.com.evil.test/", "https://user:pass@wing.coupang.com/"])
def test_reject_unrelated_start_urls(url):
    with pytest.raises(ReportError):
        require_wing_url(url)


def test_installed_browser_selection_only_falls_back_if_missing(tmp_path):
    from playwright.sync_api import Error
    calls = []
    sentinel = object()

    def launch(profile, **options):
        calls.append(options.get("channel"))
        if options.get("channel") == "chrome":
            raise Error("Chromium distribution 'chrome' is not found")
        return sentinel

    pw = SimpleNamespace(chromium=SimpleNamespace(launch_persistent_context=launch))
    assert launch_context(pw, tmp_path) is sentinel
    assert calls == ["chrome", "msedge"]


def test_browser_start_error_is_not_retried(tmp_path):
    from playwright.sync_api import Error
    calls = []

    def launch(profile, **options):
        calls.append(options.get("channel"))
        raise Error("Profile is already in use")

    pw = SimpleNamespace(chromium=SimpleNamespace(launch_persistent_context=launch))
    with pytest.raises(ReportError, match="다른 실행 창"):
        launch_context(pw, tmp_path)
    assert calls == ["chrome"]


@pytest.mark.skipif(not os.environ.get("WING_TEST_CHROMIUM"), reason="Set WING_TEST_CHROMIUM for a local browser integration test")
def test_browser_navigation_login_and_download(tmp_path, monkeypatch):
    """Real Chromium, mocked WING responses; no requests to the real seller account."""
    from playwright.sync_api import sync_playwright

    payload = base64.b64encode("옵션ID,상품명,판매가능수량,최근7일판매량\n001,수건,20,10\n".encode("utf-8-sig")).decode()
    html = """<html><meta charset='utf-8'>
    <input id='user'><input id='pass' type='password'>
    <button id='login' onclick="document.querySelector('#signed').hidden=false">로그인</button>
    <div id='signed' hidden>내 계정</div>
    <select id='period'><option>최근 30일</option><option>최근 7일</option></select>
    <button onclick="document.querySelector('#inventory').hidden=false">로켓그로스</button>
    <button id='inventory' hidden onclick="document.querySelector('#export').hidden=false">재고 현황</button>
    <a id='export' hidden href='data:text/csv;base64,PAYLOAD' download='inventory.csv'>엑셀 다운로드</a></html>""".replace("PAYLOAD", payload)

    def respond(route):
        if route.request.url.endswith("/export"):
            route.fulfill(status=200, headers={"Content-Type": "text/csv; charset=utf-8", "Content-Disposition": 'attachment; filename="inventory.csv"'},
                          body="옵션ID,상품명,판매가능수량,최근7일판매량\n001,수건,20,10\n".encode("utf-8-sig"))
        else:
            route.fulfill(status=200, content_type="text/html; charset=utf-8", body=html)

    monkeypatch.setenv("WING_USERNAME", "test-user")
    monkeypatch.setenv("WING_PASSWORD", "test-password-not-real")
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=os.environ["WING_TEST_CHROMIUM"], headless=True)
        context = browser.new_context(accept_downloads=True)
        context.route("**/*", respond)
        page = context.new_page()
        page.goto("https://wing.coupang.com/")
        config = {"menu": ["로켓그로스", "재고현황"], "ready_selector": "#export", "export_selector": "#export",
                  "prepare": [{"action": "select", "selector": "#period", "label": "최근 7일"}],
                  "login": {"username_selector": "#user", "password_selector": "#pass", "submit_selector": "#login", "authenticated_selector": "#signed"}}
        login(page, config, automatic=True, auto_login=True)
        assert page.locator("#user").input_value() == "test-user"
        navigate_inventory(page, config)
        assert page.locator("#period").input_value() == "최근 7일"
        source = download_report(page, tmp_path, config, automatic=True)
        products, _ = parse_report(source)
        assert products[0].replenish == 40
        assert source.name.startswith("wing_")
        page.set_content("""<table><thead><tr><th>옵션ID</th><th>상품명</th><th>판매가능수량</th><th>최근7일판매량</th></tr></thead>
        <tbody><tr><td>001</td><td>수건</td><td>20</td><td>10</td></tr></tbody></table>
        <button id='next' onclick="document.querySelector('tbody').innerHTML='<tr><td>002</td><td>컵</td><td>0</td><td>3</td></tr>';this.disabled=true">다음</button>""")
        table_source = read_table(page, tmp_path, {"table_selector": "table", "next_selector": "#next"})
        table_products, _ = parse_report(table_source)
        assert [p.replenish for p in table_products] == [40, 18]
        page.locator("#next").evaluate("button => button.disabled = false")
        with pytest.raises(ReportError, match="max_pages"):
            read_table(page, tmp_path, {"table_selector": "table", "next_selector": "#next", "max_pages": 1})
        with pytest.raises(ReportError, match="명시적 확인"):
            read_table(page, tmp_path, {"table_selector": "table"})
        page.set_content("<html><title>Access Denied</title><h1>Access Denied</h1><p>You don't have permission to access this server.</p></html>")
        with pytest.raises(ReportError, match="쿠팡 인증 서버"):
            check_access(page)
        with pytest.raises(ReportError, match="Access Denied"):
            login(page, config, automatic=True, auto_login=True)
        browser.close()
