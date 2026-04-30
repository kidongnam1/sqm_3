# SQM v865 Release Notes

Release date: 2026-04-30

## Highlights

- DO 문서의 입항일과 컨테이너 반납일을 기준으로 프리타임을 자동 계산하도록 보강했습니다.
- Gemini 비교 팝업이 미리보기 창 뒤에 가려지지 않도록 표시 순서와 크기, z-index를 조정했습니다.
- 입고 메뉴에서 인바운드 템플릿 관리 메뉴를 바로 찾을 수 있도록 노출명과 액션 연결을 정리했습니다.
- 상단 메뉴와 하위 메뉴가 마우스 이동 중 쉽게 사라지지 않도록 클릭 고정 방식으로 보강했습니다.
- 대량 이동 승인 화면과 API 흐름을 추가해 PENDING 이동 요청을 승인/반려할 수 있게 했습니다.

## Inbound / DO Free Time

- `YYYYMMDD`, `YYYY-MM-DD`, `YYYY/MM/DD`, `YYYY.MM.DD`, `DD/MM/YYYY`, `DD-MMM-YYYY` 등 여러 날짜 형식을 공통 정규화합니다.
- DO 파싱 결과의 `arrival_date`와 `free_time_date` 또는 `con_return`을 사용해 `free_time` 일수를 계산합니다.
- 반납일이 입항일보다 앞서는 경우 음수 대신 `0`으로 처리합니다.
- Web API, GUI 업로드, OCR fallback 경로 모두 동일한 날짜 계산 유틸을 사용하도록 정리했습니다.

## OCR / Parser Reliability

- DO OCR에서 8자리 날짜(`20260424`)도 감지하도록 확장했습니다.
- OCR 의존성 확인이 실제 모듈 import 기준으로 동작하도록 수정했습니다.
- 컨테이너 번호 보정 시 앞 4자리 영문 영역을 숫자로 바꾸지 않도록 개선했습니다.
- Gemini fallback 결과의 반납일도 날짜 정규화 후 저장되도록 보강했습니다.

## UI Improvements

- Gemini 비교 팝업을 파싱 결과 창 이후에 띄워 가려짐 문제를 줄였습니다.
- 비교 팝업 위치를 화면 상단에 가깝게 조정하고 최대 높이와 폭을 키웠습니다.
- `입고 → 인바운드 템플릿 관리` 메뉴를 직접 노출했습니다.
- 기존 `조회/관리 → 파싱 템플릿 관리`는 `입고 파싱 템플릿 관리`로 이름을 명확히 바꿨습니다.
- 상위 메뉴와 하위 메뉴를 클릭하면 열린 상태가 유지되고, 바깥 클릭 또는 `Esc`에서 닫히도록 변경했습니다.

## Transfer Workflow

- 대량 이동 요청 제출, PENDING 조회, 승인, 반려 API를 추가했습니다.
- 웹 화면에서 대량 이동 승인 모달을 통해 요청 목록 확인 및 승인/반려가 가능합니다.

## Tests

- 날짜 정규화 및 프리타임 계산 유닛 테스트를 추가했습니다.
- ONE, HAPAG, MAERSK, MSC DO fixture 회귀 테스트에 반납일과 프리타임 계산 검증을 추가했습니다.

## Verification

- `python -m pytest tests\test_date_utils_free_time.py tests\test_parser_regression.py -q`
- `node --check frontend\js\sqm-onestop-inbound.js`
- `node --check frontend\js\sqm-inline.js`
- `node --check frontend\js\handlers\menubar.js`

## Excluded From Release Commit

- Runtime DB file changes are not included.
- Pytest cache changes are not included.
- Local backup, debug, and temporary helper files are not included.
