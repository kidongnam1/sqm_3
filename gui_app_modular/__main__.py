"""
SQM 재고관리 시스템 - 패키지 실행 시 진입점 (run으로 위임)
=========================================================

★ 공식 엔트리 포인트는 루트의 run.py 1곳입니다. ★

사용법 (동일한 부트스트랩: 점검, MAC Guard, 자동 백업 후 GUI):
    python run.py
    python -m gui_app_modular

둘 다 run.main()을 호출하여 동일한 경로로 실행됩니다.
"""

if __name__ == '__main__':
    import run
    run.main()
