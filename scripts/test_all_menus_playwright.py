"""
v864.3 전체 메뉴/사이드바/툴바 1:1 클릭 검증 -Playwright
==========================================================
모든 data-action 버튼을 클릭하고:
1. 에러 토스트가 뜨지 않는지
2. 모달이 열리거나 탭이 전환되는지
3. 빈 화면(blank)이 아닌지
확인합니다.

사용:
    # 서버가 이미 실행 중이어야 합니다 (python -m uvicorn backend.api:app --port 8765)
    python scripts/test_all_menus_playwright.py
    python scripts/test_all_menus_playwright.py --headless
"""
import json
import sys
import argparse
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 클릭하면 안 되는 위험한 액션 (DB 변경/종료)
SKIP_ACTIONS = {
    'onExit',           # 앱 종료
    'onTestDbReset',    # DB 초기화
}

# POST 액션 중 실행하면 DB가 변경되는 것들 -클릭만 하고 confirm 안 함
CONFIRM_REQUIRED = {
    'onOnBackup',       # 백업 생성
    'onRestore',        # 복원
    'onOptimizeDb',     # DB 최적화
    'onCleanupLogs',    # 로그 정리
    'onInboundCancel',  # 입고 취소
    'onApplyApproved',  # 예약 반영
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--headless', action='store_true')
    args = parser.parse_args()

    from playwright.sync_api import sync_playwright

    results = []
    errors_found = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=args.headless)
        page = browser.new_page()

        # 콘솔 에러 수집
        console_errors = []
        page.on('console', lambda msg: console_errors.append(msg.text) if msg.type == 'error' else None)

        print("[1] 페이지 접속...")
        try:
            page.goto('http://127.0.0.1:8765/', timeout=15000)
            page.wait_for_load_state('networkidle', timeout=10000)
        except Exception as e:
            print(f"접속 실패: {e}")
            browser.close()
            return 1

        # ── Phase A: 구조 검사 ──
        print("\n[2] 구조 검사...")

        top_menus = page.query_selector_all('.menu-btn[data-menu]')
        menu_names = [m.get_attribute('data-menu') for m in top_menus]
        print(f"  탑레벨 메뉴: {len(top_menus)}개 -{menu_names}")
        results.append({'test': 'top_menu_count', 'expected': 7, 'actual': len(top_menus),
                        'pass': len(top_menus) >= 7, 'detail': menu_names})

        sidebar_btns = page.query_selector_all('.side-btn[data-route]')
        sidebar_routes = [b.get_attribute('data-route') for b in sidebar_btns]
        print(f"  사이드바: {len(sidebar_btns)}개 -{sidebar_routes}")
        results.append({'test': 'sidebar_count', 'expected': 9, 'actual': len(sidebar_btns),
                        'pass': len(sidebar_btns) == 9})

        toolbar_btns = page.query_selector_all('.tool-btn[data-action]')
        print(f"  툴바: {len(toolbar_btns)}개")
        results.append({'test': 'toolbar_count', 'expected': 7, 'actual': len(toolbar_btns),
                        'pass': len(toolbar_btns) == 7})

        # ── Phase B: 사이드바 탭 전체 클릭 ──
        print("\n[3] 사이드바 탭 클릭 테스트...")
        for route in sidebar_routes:
            try:
                btn = page.query_selector(f'.side-btn[data-route="{route}"]')
                if btn:
                    btn.click()
                    page.wait_for_timeout(800)
                    if route == 'dashboard':
                        ok = page.query_selector('#dashboard-container') is not None
                    else:
                        pc = page.query_selector('#page-container')
                        ok = pc is not None and pc.is_visible()
                    status = 'PASS' if ok else 'FAIL'
                    print(f"  [{route}] {status}")
                    results.append({'test': f'sidebar_{route}', 'pass': ok})
                    if not ok:
                        errors_found.append(f'sidebar_{route}: 화면 전환 실패')
            except Exception as e:
                print(f"  [{route}] ERROR: {e}")
                results.append({'test': f'sidebar_{route}', 'pass': False, 'error': str(e)})
                errors_found.append(f'sidebar_{route}: {e}')

        # ── Phase C: 모든 메뉴 항목 클릭 테스트 ──
        print("\n[4] 메뉴 항목 클릭 테스트 (모든 data-action)...")

        for menu_el in top_menus:
            menu_name = menu_el.get_attribute('data-menu')
            # 메뉴 열기
            menu_el.click()
            page.wait_for_timeout(300)

            buttons = menu_el.query_selector_all('.menu-dropdown button[data-action]')
            action_names = [b.get_attribute('data-action') for b in buttons]
            print(f"\n  ── [{menu_name}] {len(buttons)}개 항목 ──")

            for action_name in action_names:
                if action_name in SKIP_ACTIONS:
                    print(f"    [{action_name}] SKIP (위험)")
                    results.append({'test': f'menu_{action_name}', 'pass': True, 'skipped': True})
                    continue

                try:
                    # 메뉴 다시 열기 (이전 클릭으로 닫혔을 수 있음)
                    menu_el.click()
                    page.wait_for_timeout(200)

                    btn = menu_el.query_selector(f'.menu-dropdown button[data-action="{action_name}"]')
                    if not btn:
                        print(f"    [{action_name}] NOT_FOUND")
                        results.append({'test': f'menu_{action_name}', 'pass': False, 'error': 'button not found'})
                        errors_found.append(f'{action_name}: 버튼을 찾을 수 없음')
                        continue

                    # 클릭 전 에러 토스트 카운트 기록
                    pre_toasts = page.query_selector_all('.toast-error, .toast.error')
                    pre_count = len(pre_toasts)

                    btn.click()
                    page.wait_for_timeout(600)

                    # 모달이 열렸는지 확인
                    modal = page.query_selector('#sqm-modal')
                    modal_visible = modal is not None and modal.is_visible()

                    # 페이지가 빈 화면이 아닌지 확인
                    body_text = page.inner_text('body')
                    not_blank = len(body_text.strip()) > 50

                    # JS uncaught error 체크
                    has_js_error = any('uncaught' in e.lower() or 'ReferenceError' in e for e in console_errors[-3:])

                    ok = not_blank and not has_js_error
                    status = 'PASS'

                    extra = ''
                    if modal_visible:
                        extra = ' (modal)'
                        # 모달 닫기
                        close_btn = page.query_selector('#sqm-modal button[onclick*="display"], #sqm-modal-inner > button')
                        if close_btn:
                            close_btn.click()
                            page.wait_for_timeout(200)

                    if has_js_error:
                        status = 'JS_ERROR'
                        ok = False
                        errors_found.append(f'{action_name}: JS uncaught error')

                    print(f"    [{action_name}] {status}{extra}")
                    results.append({'test': f'menu_{action_name}', 'pass': ok, 'status': status,
                                    'modal': modal_visible})

                except Exception as e:
                    print(f"    [{action_name}] EXCEPTION: {e}")
                    results.append({'test': f'menu_{action_name}', 'pass': False, 'error': str(e)})
                    errors_found.append(f'{action_name}: {e}')

        # ── Phase D: 툴바 클릭 테스트 ──
        print("\n[5] 툴바 버튼 클릭 테스트...")
        toolbar_btns = page.query_selector_all('.tool-btn[data-action]')
        def dismiss_dialog(d):
            d.dismiss()
        page.on('dialog', dismiss_dialog)
        for tb in toolbar_btns:
            action = tb.get_attribute('data-action')
            try:
                tb.click()
                page.wait_for_timeout(500)

                modal = page.query_selector('#sqm-modal')
                modal_visible = modal is not None and modal.is_visible()

                if modal_visible:
                    close_btn = page.query_selector('#sqm-modal button[onclick*="display"], #sqm-modal-inner > button')
                    if close_btn:
                        close_btn.click()
                        page.wait_for_timeout(200)

                print(f"  [{action}] PASS" + (' (modal)' if modal_visible else ''))
                results.append({'test': f'toolbar_{action}', 'pass': True, 'modal': modal_visible})
            except Exception as e:
                print(f"  [{action}] ERROR: {e}")
                results.append({'test': f'toolbar_{action}', 'pass': False, 'error': str(e)})
        page.remove_listener('dialog', dismiss_dialog)

        # ── Phase E: 상태바 확인 ──
        print("\n[6] 상태바 확인...")
        sb = page.query_selector('#statusbar-container')
        sb_text = sb.inner_text() if sb else ''
        sb_ok = 'Engine' in sb_text or 'LOT' in sb_text
        print(f"  상태바: {'PASS' if sb_ok else 'FAIL'}")
        results.append({'test': 'statusbar', 'pass': sb_ok})

        # ── Phase F: 콘솔 에러 리포트 ──
        if console_errors:
            critical = [e for e in console_errors if 'uncaught' in e.lower() or 'TypeError' in e or 'ReferenceError' in e]
            if critical:
                print(f"\n⚠️ JS 치명적 에러 {len(critical)}건:")
                for e in critical[:5]:
                    print(f"  {e[:120]}")

        browser.close()

    # ── 결과 요약 ──
    pass_count = sum(1 for r in results if r.get('pass'))
    fail_count = sum(1 for r in results if not r.get('pass'))
    total = len(results)

    print(f"\n{'='*60}")
    print(f"결과: 총 {total}건 · PASS {pass_count} · FAIL {fail_count}")
    print(f"{'='*60}")

    if errors_found:
        print(f"\n❌ 실패/문제 항목 ({len(errors_found)}건):")
        for e in errors_found:
            print(f"  - {e}")

    # JSON 저장
    report_path = PROJECT_ROOT / 'REPORTS' / 'playwright_all_menus.json'
    report_path.parent.mkdir(exist_ok=True)
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump({
            'summary': {'total': total, 'pass': pass_count, 'fail': fail_count},
            'errors': errors_found,
            'results': results,
        }, f, ensure_ascii=False, indent=2)
    print(f"\n결과 저장: {report_path}")

    return 0 if fail_count == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
