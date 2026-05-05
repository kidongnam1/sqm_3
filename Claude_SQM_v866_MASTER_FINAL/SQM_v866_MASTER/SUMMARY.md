# SQM v866 작업 현재 상태
마지막 업데이트: 초기화 (2026-05-01)

## 현재 버전
v8.6.5 (Phase 5 완료 — 44 passed)

## 완료된 Phase
Phase 0: 환경 검증
Phase 1~5: UI + 백엔드 + 파서 + 테스트 완료

## 진행 중
Phase 6: EXE 빌드 + 기능 완성

## 미완성 항목 (이번 작업 대상)
- carriers.py: GET에서 쓰기 버그
- config_logging.py: CP949 UnicodeEncodeError
- sqm-inline.js: _zFloatTop IIFE 스코프 오류
- scan_api.py: 신규 생성 필요
- integrity_api.py: 신규 생성 필요
- inventory.js: 실데이터 연결 미완성
- dashboard.js: KPI 실데이터 + 30초 갱신
- scan.js: 4버튼 API 연결

## 핵심 결정사항
- sqm-inline.js 수정: Python 스크립트만 허용 (Edit 툴 금지)
- SOLD 전환: scan_api.py에서만
- 포트: 8765
- DB: data/db/sqm_inventory.db

## Agent 상태
A(프론트JS): 대기
B(백엔드API): 대기
C(버그수정): 대기
D(검증ZIP): 대기
