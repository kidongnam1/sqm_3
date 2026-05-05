# 파일 단위 잠금 규칙 (동시 수정 충돌 방지)

## 목적
- 같은 파일을 여러 세션이 동시에 수정할 때 발생하는 충돌/덮어쓰기를 방지한다.

## 원칙
- **먼저 잠금 획득한 세션만 수정 가능**
- 늦게 들어온 세션은 `LOCKED` 메시지가 나오면 작업 중지
- 선행 세션 완료 후 잠금 해제되면 다시 진행

## 사용 명령 (Windows CMD)
- 잠금 획득
  - `scripts\file_lock.bat acquire --file frontend/js/sqm-tonbag.js --session S1`
- 잠금 상태 확인
  - `scripts\file_lock.bat status --file frontend/js/sqm-tonbag.js`
- 잠금 해제
  - `scripts\file_lock.bat release --file frontend/js/sqm-tonbag.js --session S1`
- 전체 잠금 목록
  - `scripts\file_lock.bat list`

## 자주 쓰는 파일 단축 배치
- 공통 2개 파일 잠금 시작
  - `scripts\lock_start_common.bat S1`
- 공통 2개 파일 잠금 종료
  - `scripts\lock_end_common.bat S1`

대상 파일:
- `frontend/js/sqm-tonbag.js`
- `frontend/css/v864-layout.css`

## 운영 규칙
- 세션 이름은 고유하게 사용 (예: `S1`, `S2`, `Ruby-A`)
- 편집 시작 전에 반드시 `acquire`
- 편집/검증 완료 직후 반드시 `release`
- 비정상 종료로 잠금이 남았을 때만 강제 해제:
  - `scripts\file_lock.bat release --file <파일경로> --session <내세션> --force`

## 잠금 저장 위치
- `.locks/files/*.lock.json`

