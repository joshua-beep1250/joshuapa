from __future__ import annotations

import getpass
import csv
import os
import re
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from .report import KST, ReportError

WING_URL = "https://wing.coupang.com/"


def check_access(page):
    denied = "access denied" in page.title().casefold()
    for text in ("Access Denied", "You don't have permission to access"):
        element = page.get_by_text(text, exact=text == "Access Denied")
        if element.count() and element.first.is_visible():
            denied = True
    if denied:
        raise ReportError(
            "쿠팡 인증 서버가 접속을 거부했습니다 (Access Denied). "
            "프로그램을 닫고 평소 쓰는 Chrome/Edge에서 WING 로그인이 되는지 확인하세요. "
            "일반 브라우저에서도 거부되면 화면의 Reference 번호로 WING 고객센터에 문의하세요. "
            "일반 브라우저에서만 된다면 run_manual_windows.bat로 엑셀을 직접 받아 계산할 수 있습니다. "
            "반복 로그인이나 차단 우회는 시도하지 않습니다."
        )


def launch_context(pw, root, browser="auto"):
    from playwright.sync_api import Error as BrowserError

    if browser not in {"auto", "chrome", "msedge", "chromium"}:
        raise ReportError("browser는 auto, chrome, msedge, chromium 중 하나여야 합니다.")
    candidates = ["chrome", "msedge", "chromium"] if browser == "auto" else [browser]
    for candidate in candidates:
        profile = root / ("browser-profile" if candidate == "chromium" else f"browser-profile-{candidate}")
        profile.mkdir(exist_ok=True)
        profile.chmod(0o700)
        options = {"headless": False, "accept_downloads": True, "locale": "ko-KR",
                   "timezone_id": "Asia/Seoul", "viewport": {"width": 1440, "height": 1000}}
        if candidate != "chromium":
            options["channel"] = candidate
        try:
            context = pw.chromium.launch_persistent_context(str(profile), **options)
            print(f"사용 브라우저: {candidate} (전용 프로필)")
            return context
        except BrowserError as error:
            missing = any(term in str(error).casefold() for term in ("not found", "doesn't exist", "does not exist"))
            # Only try another installed browser when the executable is missing.
            # A login denial must never trigger retries with other browsers.
            if browser != "auto" or not missing or candidate == candidates[-1]:
                raise ReportError("브라우저를 시작하지 못했습니다. Chrome/Edge 설치와 다른 실행 창을 확인하세요. "
                                  "또는 setup_windows.bat로 Chromium을 설치하세요.") from None


def require_wing_url(url):
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "wing.coupang.com" or parsed.username or parsed.password:
        raise ReportError("시작/재고 URL은 https://wing.coupang.com/ 내부 주소여야 합니다.")
    return url


def locator(page, spec):
    """Accept CSS, or explicit role/name; never execute configuration as code."""
    if isinstance(spec, str) and spec:
        return page.locator(spec)
    if isinstance(spec, dict) and spec.get("role") and spec.get("name"):
        return page.get_by_role(spec["role"], name=spec["name"], exact=True)
    raise ReportError("선택자는 CSS 문자열 또는 {role, name} 객체로 지정하세요.")


def login(page, config, automatic, auto_login):
    from playwright.sync_api import TimeoutError as BrowserTimeout

    check_access(page)
    auth = config.get("login", {})
    marker = auth.get("authenticated_selector")
    if marker:
        try:
            locator(page, marker).wait_for(state="visible", timeout=4000)
            return
        except BrowserTimeout:
            pass
    if auto_login:
        required = ("username_selector", "password_selector", "submit_selector", "authenticated_selector")
        if not all(auth.get(key) for key in required):
            raise ReportError("자동 로그인에는 config의 login 선택자 4개를 실제 화면에 맞게 지정해야 합니다.")
        username = os.environ.get("WING_USERNAME")
        password = os.environ.get("WING_PASSWORD")
        if automatic and (not username or not password):
            raise ReportError("무인 자동 로그인은 WING_USERNAME, WING_PASSWORD 환경변수가 필요합니다.")
        username = username or input("WING 아이디 (저장하지 않음): ").strip()
        password = password or getpass.getpass("WING 비밀번호 (화면 표시/저장 안 함): ")
        locator(page, auth["username_selector"]).fill(username)
        locator(page, auth["password_selector"]).fill(password)
        locator(page, auth["submit_selector"]).click()
        del password
        try:
            locator(page, marker).wait_for(state="visible", timeout=15000)
            return
        except BrowserTimeout:
            check_access(page)
            if automatic:
                raise ReportError("로그인 완료를 확인하지 못했습니다. 인증/캡차가 있다면 일반 모드로 직접 완료하세요.") from None
    if automatic:
        raise ReportError("유효한 로그인 세션을 확인하지 못했습니다. 먼저 일반 모드로 로그인하세요.")
    input("브라우저에서 WING 로그인과 추가 인증을 완료한 뒤 여기서 Enter를 누르세요: ")
    check_access(page)
    if marker:
        locator(page, marker).wait_for(state="visible", timeout=15000)


def navigate_inventory(page, config):
    url = config.get("inventory_url")
    if url:
        page.goto(require_wing_url(url), wait_until="domcontentloaded")
    else:
        for name in config.get("menu", ["로켓그로스", "재고현황"]):
            # Match whitespace variations, without guessing undocumented WING URLs.
            pattern = re.compile(r"^\s*" + r"\s*".join(map(re.escape, name.replace(" ", ""))) + r"\s*$")
            page.get_by_text(pattern).click(timeout=15000)
    # Optional read-only filters, such as switching the sales period to 최근 7일.
    for action in config.get("prepare", []):
        target = locator(page, action["selector"])
        operation = action["action"]
        if operation == "click":
            target.click()
        elif operation == "select":
            target.select_option(label=action["label"])
        elif operation == "fill":
            target.fill(action["value"])
        elif operation == "wait":
            target.wait_for(state="visible", timeout=30000)
        else:
            raise ReportError("prepare 작업은 click, select, fill, wait만 지원합니다.")
    if config.get("ready_selector"):
        locator(page, config["ready_selector"]).wait_for(state="visible", timeout=30000)


def download_report(page, root: Path, config, automatic):
    export_selector = config.get("export_selector")
    if automatic and not export_selector:
        raise ReportError("무인 모드에서는 실제 전체 상품 엑셀 버튼의 export_selector를 설정하세요.")
    if export_selector:
        try:
            with page.expect_download(timeout=120000) as pending:
                locator(page, export_selector).click()
            download = pending.value
        except Exception:
            if automatic:
                raise
            print("자동 다운로드를 완료하지 못했습니다. 수동 다운로드로 전환합니다.")
            download = _manual_download(page)
    else:
        download = _manual_download(page)
    failure = download.failure()
    if failure:
        raise ReportError("WING 보고서 다운로드가 실패했습니다. 브라우저에서 오류를 확인하세요.")
    extension = Path(download.suggested_filename).suffix.lower()
    if extension not in {".xlsx", ".csv"}:
        raise ReportError("다운로드 파일이 xlsx/csv가 아닙니다. 엑셀 보고서를 선택해 주세요.")
    directory = root / "downloads"
    directory.mkdir(parents=True, exist_ok=True)
    filename = datetime.now(KST).strftime("wing_%Y%m%d_%H%M%S_%f") + extension
    destination = directory / filename
    download.save_as(destination)
    destination.chmod(0o600)
    return destination


def _manual_download(page):
    print("브라우저에서 최근 7일 판매수량이 포함된 전체 상품 재고 엑셀을 다운로드하세요.")
    print("내보내기 옵션이 있다면 현재 페이지만이 아닌 전체 상품을 선택하세요. (대기: 5분)")
    with page.expect_download(timeout=300000) as pending:
        input("다운로드를 클릭한 뒤 여기서 Enter를 누르세요: ")
    return pending.value


def read_table(page, root: Path, config):
    """Read an explicitly configured HTML table, including all configured pages."""
    table_spec = config.get("table_selector")
    if not table_spec:
        raise ReportError("화면 수집에는 실제 table_selector가 필요합니다.")
    next_spec = config.get("next_selector")
    if not next_spec and config.get("single_page") is not True:
        raise ReportError("화면 수집에는 next_selector 또는 single_page: true의 명시적 확인이 필요합니다.")
    collected, seen = [], set()
    headings = None
    max_pages = config.get("max_pages", 500)
    if not isinstance(max_pages, int) or max_pages < 1:
        raise ReportError("max_pages는 1 이상의 정수여야 합니다.")
    for _ in range(max_pages):
        table = locator(page, table_spec)
        table.wait_for(state="visible", timeout=30000)
        header_rows = table.locator("thead tr")
        if header_rows.count() != 1:
            raise ReportError("화면 수집은 단일 헤더 행의 HTML 표를 지원합니다. 엑셀 다운로드 모드를 사용하세요.")
        current_headers = header_rows.locator("th,td").all_inner_texts()
        if headings is not None and current_headers != headings:
            raise ReportError("페이지를 넘긴 후 표 열 구성이 달라졌습니다.")
        headings = current_headers
        body = table.locator("tbody tr")
        rows = [body.nth(index).locator("td").all_inner_texts() for index in range(body.count())]
        if not rows or any(len(row) != len(headings) for row in rows):
            raise ReportError("상품 행이 없거나 표 구조가 다릅니다. 필터·로딩 상태를 확인하세요.")
        fingerprint = tuple(tuple(row) for row in rows)
        if fingerprint in seen:
            raise ReportError("동일한 페이지가 반복되었습니다. 중복/일부 데이터로 계산하지 않습니다.")
        seen.add(fingerprint)
        collected.extend(rows)
        if not next_spec:
            break
        next_button = locator(page, next_spec)
        if next_button.count() != 1:
            raise ReportError("다음 페이지 버튼을 확인하지 못했습니다. 전체 페이지 수집을 보장할 수 없습니다.")
        if not next_button.is_enabled() or next_button.get_attribute("aria-disabled") == "true":
            break
        if len(seen) >= max_pages:
            raise ReportError("max_pages에 도달했습니다. 일부 데이터로는 계산하지 않습니다.")
        previous = table.inner_text()
        next_button.click()
        deadline = time.monotonic() + 30
        while locator(page, table_spec).inner_text() == previous:
            if time.monotonic() >= deadline:
                raise ReportError("다음 페이지 데이터가 갱신되지 않았습니다.")
            page.wait_for_timeout(200)
        if config.get("ready_selector"):
            locator(page, config["ready_selector"]).wait_for(state="visible", timeout=30000)
    directory = root / "downloads"
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / datetime.now(KST).strftime("wing_table_%Y%m%d_%H%M%S_%f.csv")
    with destination.open("x", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(headings)
        writer.writerows(collected)
    destination.chmod(0o600)
    return destination


def collect(config: dict, root: Path, automatic=False, auto_login=False):
    from playwright.sync_api import sync_playwright

    if automatic and (not config.get("scope") or not config.get("ready_selector")):
        raise ReportError("무인 모드는 config의 scope(필터·7일 집계 기준), ready_selector가 필요합니다.")
    root.mkdir(parents=True, exist_ok=True)
    root.chmod(0o700)
    with sync_playwright() as pw:
        # Persist only a dedicated local profile, never the user's normal browser profile.
        context = launch_context(pw, root, config.get("browser", "auto"))
        try:
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(WING_URL, wait_until="domcontentloaded")
            check_access(page)
            login(page, config, automatic, auto_login)
            try:
                navigate_inventory(page, config)
            except Exception:
                check_access(page)
                if automatic:
                    raise
                print("자동 메뉴 이동을 확인하지 못했습니다.")
                input("브라우저에서 로켓그로스 > 재고현황으로 이동한 뒤 Enter: ")
            check_access(page)
            if urlparse(page.url).hostname != "wing.coupang.com":
                raise ReportError("WING 내부 재고 페이지가 아닙니다. 로그인 상태를 확인하세요.")
            if automatic:
                scope = config["scope"]
            else:
                print("전체 상품·옵션, 판매가능 재고, 최근 7일 '판매수량'이 맞는지 확인하세요.")
                scope = input("조회 범위/집계 기준을 기록하세요 (예: 전체 상품, WING 최근 7일): ").strip()
                if not scope:
                    raise ReportError("조회 범위와 최근 7일 집계 기준 확인이 필요합니다.")
            mode = config.get("collection", "download")
            if mode not in {"download", "table"}:
                raise ReportError("collection은 download 또는 table이어야 합니다.")
            source = read_table(page, root, config) if mode == "table" else download_report(page, root, config, automatic)
            return source, scope
        finally:
            context.close()
