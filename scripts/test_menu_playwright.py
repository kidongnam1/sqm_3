"""
v864.3 메뉴 전수 테스트 — Playwright
====================================
앱이 http://127.0.0.1:8765 에서 실행 중이어야 합니다.

사용:
    python scripts/test_menu_playwright.py
    python scripts/test_menu_playwright.py --headless   (브라우저 안 띄움)
    python scripts/test_menu_playwright.py --standalone (앱 자동 시작/종료)
"""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--headless', action='store_true')
    parser.add_argument('--standalone', action='store_true', help='앱 자동 시작/종료')
    args = parser.parse_args()

    from playwright.sync_api import sync_playwright

    app_proc = None
    if args.standalone:
        print("[1] 앱 시작 중...")
        app_proc = subprocess.Popen(
            [sys.executable, str(PROJECT_ROOT / 'main_webview.py')],
            cwd=str(PROJECT_ROOT),
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        time.sleep(8)

    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=args.headless)
        page = browser.new_page()

        print("[2] 페이지 접속...")
        try:
            page.goto('http://127.0.0.1:8765/', timeout=15000)
            page.wait_for_load_state('networkidle', timeout=10000)
        except Exception as e:
            print(f"접속 실패: {e}")
            print("앱이 실행 중인지 확인하세요: python main_webview.py")
            browser.close()
            if app_proc:
                app_proc.terminate()
            return 1

        print("[3] 메뉴 구조 검사...")

        # 3-1. 탑레벨 메뉴 수 확인
        top_menus = page.query_selector_all('.menu-btn[data-menu]')
        top_menu_names = [m.get_attribute('data-menu') for m in top_menus]
        print(f"  탑레벨 메뉴: {len(top_menus)}개 — {top_menu_names}")
        results.append({
            'test': 'top_menu_count',
            'expected': 7,  # 출고/파일/보고서/도구/View/도움말/품목
            'actual': len(top_menus),
            'pass': len(top_menus) >= 7,
            'detail': top_menu_names,
        })

        # 3-2. 각 메뉴의 하부 항목 수 확인
        for menu_el in top_menus:
            menu_name = menu_el.get_attribute('data-menu')
            buttons = menu_el.query_selector_all('.menu-dropdown button[data-action]')
            action_names = [b.get_attribute('data-action') for b in buttons]
            print(f"  [{menu_name}] {len(buttons)}개 항목")
            results.append({
                'test': f'menu_{menu_name}_items',
                'count': len(buttons),
                'actions': action_names,
                'pass': len(buttons) > 0,
            })

        # 3-3. 사이드바 탭 수 확인
        sidebar_btns = page.query_selector_all('.side-btn[data-route]')
        sidebar_routes = [b.get_attribute('data-route') for b in sidebar_btns]
        print(f"  사이드바: {len(sidebar_btns)}개 — {sidebar_routes}")
        results.append({
            'test': 'sidebar_count',
            'expected': 9,
            'actual': len(sidebar_btns),
            'pass': len(sidebar_btns) == 9,
            'detail': sidebar_routes,
        })

        # 3-4. 툴바 버튼 수 확인
        toolbar_btns = page.query_selector_all('.tool-btn[data-action]')
        toolbar_actions = [b.get_attribute('data-action') for b in toolbar_btns]
        print(f"  툴바: {len(toolbar_btns)}개 — {toolbar_actions}")
        results.append({
            'test': 'toolbar_count',
            'expected': 7,
            'actual': len(toolbar_btns),
            'pass': len(toolbar_btns) == 7,
            'detail': toolbar_actions,
        })

        # 3-5. 사이드바 각 탭 클릭 테스트
        print("\n[4] 사이드바 탭 클릭 테스트...")
        for route in sidebar_routes:
            try:
                btn = page.query_selector(f'.side-btn[data-route="{route}"]')
                if btn:
                    btn.click()
                    page.wait_for_timeout(500)
                    # page-container 또는 dashboard-container가 보이는지 확인
                    if route == 'dashboard':
                        visible = page.query_selector('#dashboard-container') is not None
                    else:
                        pc = page.query_selector('#page-container')
                        visible = pc is not None and pc.is_visible()
                    print(f"  [{route}] {'PASS' if visible else 'FAIL'}")
                    results.append({
                        'test': f'sidebar_{route}_click',
                        'pass': visible,
                    })
            except Exception as e:
                print(f"  [{route}] ERROR: {e}")
                results.append({'test': f'sidebar_{route}_click', 'pass': False, 'error': str(e)})

        # 3-6. 상태바 확인
        print("\n[5] 상태바 확인...")
        sb = page.query_selector('#statusbar-container')
        sb_text = sb.inner_text() if sb else ''
        sb_ok = 'Engine' in sb_text or 'LOT' in sb_text
        print(f"  상태바: {'PASS' if sb_ok else 'FAIL'} — {sb_text[:80]}")
        results.append({'test': 'statusbar', 'pass': sb_ok, 'text': sb_text[:100]})

        browser.close()

    if app_proc:
        app_proc.terminate()
        try:
            app_proc.wait(timeout=5)
        except Exception:
            app_proc.kill()

    # 결과 저장
    pass_count = sum(1 for r in results if r.get('pass'))
    fail_count = sum(1 for r in results if not r.get('pass'))
    print(f"\n{'='*60}")
    print(f"총 {len(results)}건 · PASS {pass_count} · FAIL {fail_count}")
    print(f"{'='*60}")

    report_path = PROJECT_ROOT / 'REPORTS' / 'playwright_menu_test.json'
    report_path.parent.mkdir(exist_ok=True)
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"결과 저장: {report_path}")

    return 0 if fail_count == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
