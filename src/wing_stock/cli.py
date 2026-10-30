from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from .report import KST, ReportError, parse_report, write_report


def main(argv=None):
    parser = argparse.ArgumentParser(description="쿠팡 WING 그로스 재고 → 6주 보충계획 엑셀")
    sources = parser.add_mutually_exclusive_group()
    sources.add_argument("--input", type=Path, help="기존 WING xlsx/csv 파일로 계산 (브라우저 생략)")
    sources.add_argument("--manual-download", action="store_true", help="평소 쓰는 기본 브라우저에서 직접 다운로드 후 계산")
    parser.add_argument("--browser", choices=["auto", "chrome", "msedge", "chromium"], help="자동화 브라우저 (기본: 설치된 Chrome, Edge, Chromium 순)")
    parser.add_argument("--output", type=Path, help="출력 xlsx 경로 (기본 output/날짜별 파일)")
    parser.add_argument("--config", type=Path, help="선택자와 열 제목을 지정한 JSON 설정")
    parser.add_argument("--sheet", help="원본 xlsx의 데이터 시트 이름")
    parser.add_argument("--scope", help="기존 파일의 조회 범위·최근 7일 집계 기준 기록")
    parser.add_argument("--data-dir", type=Path, default=Path(".wing-stock"), help="로컬 세션·다운로드 저장 경로")
    parser.add_argument("--automatic", action="store_true", help="설정된 선택자와 기존 로그인 세션으로 무인 수집")
    parser.add_argument("--auto-login", action="store_true", help="설정한 로그인 선택자로 아이디/비밀번호 입력")
    args = parser.parse_args(argv)
    try:
        config = json.loads(args.config.read_text(encoding="utf-8")) if args.config else {}
        if not isinstance(config, dict):
            raise ReportError("JSON 설정은 객체여야 합니다.")
        if args.browser:
            config["browser"] = args.browser
        if args.manual_download and (args.automatic or args.auto_login):
            raise ReportError("직접 다운로드 모드에서는 자동 로그인/무인 옵션을 사용할 수 없습니다.")
        if args.input:
            source = args.input
            scope = args.scope
            if not scope:
                raise ReportError("기존 파일은 --scope로 조회 범위·최근 7일 집계 기준을 기록하세요.")
        elif args.manual_download:
            import webbrowser
            from .browser import WING_URL
            print("평소 쓰는 기본 브라우저에서 WING을 엽니다. 이 모드는 로그인·수집을 자동화하지 않습니다.")
            if not webbrowser.open(WING_URL, new=2):
                print(f"브라우저를 직접 열어 접속하세요: {WING_URL}")
            print("로켓그로스 > 재고현황에서 전체 상품과 최근 7일 판매수량이 포함된 엑셀을 저장하세요.")
            source = Path(input("다운로드한 xlsx/csv 파일을 이 창으로 끌어놓고 Enter: ").strip().strip('"')).expanduser()
            scope = args.scope or input("조회 범위·7일 집계 기준 (예: 전체 상품, WING 최근 7일): ").strip()
            if not source.is_file() or not scope:
                raise ReportError("실제 다운로드 파일과 조회 범위·집계 기준을 입력해야 합니다.")
        else:
            from .browser import collect
            source, scope = collect(config, args.data_dir, args.automatic, args.auto_login)
        products, headers = parse_report(source, config.get("columns"), args.sheet or config.get("sheet"))
        output = args.output or Path("output") / datetime.now(KST).strftime("그로스_재고계획_%Y%m%d_%H%M%S_%f.xlsx")
        if output.suffix.lower() != ".xlsx":
            raise ReportError("출력 확장자는 .xlsx여야 합니다.")
        write_report(products, output, source, headers, scope)
        print(f"완료: 상품·옵션 {len(products)}개 / 추가 확보 {sum(p.replenish for p in products):,}개")
        print(f"엑셀: {output.resolve()}")
        return 0
    except KeyboardInterrupt:
        print("중단했습니다. 원본 보고서는 변경하지 않았습니다.", file=sys.stderr)
        return 130
    except Exception as error:
        # Playwright errors may contain authenticated URLs; do not log their raw message.
        if error.__class__.__module__.startswith("playwright"):
            message = "브라우저 실행/화면 조작 실패. 브라우저 설치와 설정 선택자를 확인하세요. 인증은 직접 완료하거나 run_manual_windows.bat를 사용하세요."
        elif isinstance(error, (ReportError, OSError, json.JSONDecodeError)):
            message = str(error)
        else:
            message = f"보고서를 처리하지 못했습니다 ({type(error).__name__}). 파일 형식과 설정을 확인하세요."
        print(f"오류: {message}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
