# 파싱 안정성 및 오작동 방지 개선 계획

작성일: 2026-04-29  
대상 프로그램: SQM Inventory v8.6.5 계열  
대상 영역: 입고 PDF 파싱, Picking List 파싱, Sales Order/DN 연계, 미리보기 검수, DB 반영 전 Preflight

---

## 1. 목적

현재 프로그램은 FA, PL, BL, D/O 입고 문서와 Picking List, Sales Order를 파싱하여 재고 및 출고 워크플로우에 연결한다.

기본 파싱 기능은 동작하지만, 운영 안정성을 더 높이려면 단순히 "파싱 성공/실패"만 볼 것이 아니라 다음 항목을 체계적으로 검증해야 한다.

- 파싱 결과가 문서 간 서로 맞는지
- 좌표 기반 결과와 정규식 기반 결과가 서로 맞는지
- AI 무료/유료 결과가 서로 맞는지
- 자동 저장해도 되는 상태인지
- 사람이 반드시 검토해야 하는 상태인지
- 나중에 문제가 생겼을 때 어떤 값이 왜 반영됐는지 추적 가능한지

이 문서는 향후 개선 작업을 위한 우선순위와 구현 방향을 정리한다.

---

## 2. 현재 확인된 상태

### 2.1 입고 문서 파싱

검증된 선사 샘플:

| 선사 | 검증 상태 | 비고 |
|---|---|---|
| ONE | 정상 파싱 | BL/DO/FA/PL 정합성 확인 |
| HAPAG | 수정 후 정상 | BL 번호 뒤 페이지 번호 오파싱 보정, 컨테이너 추출 보정 |
| MAERSK | 수정 후 정상 | MAEU 접두어 통일, DO 컨테이너 5개 보강 |
| MSC | 수정 후 정상 | BL 컨테이너 수 오인 보정, DO Gross/D/O No 보강 |

현재 입고 쪽은 다음 기능을 보유한다.

- 선사별 좌표/정규식 파싱
- FA/PL/BL/D/O 문서별 파싱
- 문서 간 CrossCheck
- AI fallback
- 무료/유료 AI 동시 비교
- AI 비교 결과 검토 UI
- 미리보기 후 업로드
- 일부 hard-stop 및 All-or-Nothing 처리

### 2.2 Picking List 파싱

현재 Picking List는 다음 구조를 사용한다.

```text
PDF
→ 좌표 기반 파싱
→ 좌표 결과가 없으면 정규식 폴백
→ 본품 MT / 샘플 KG 분리
→ LOT별 검증
→ Picking Preview
→ Gate-1 검증
→ picking_table 연계
```

현재 구조는 실무 사용 가능하지만, 좌표 결과와 정규식 결과를 항상 비교하지는 않는다.

---

## 3. 개선 우선순위

| 우선순위 | 개선 항목 | 목적 |
|---:|---|---|
| 1 | 4개 선사 샘플 자동 회귀 테스트화 | 코드 수정 후 기존 선사 파싱이 깨졌는지 자동 확인 |
| 2 | Picking List 좌표/정규식 동시 비교 | Picking 결과 신뢰도 강화 |
| 3 | 파싱 품질 점수 + hard-stop 통합 | 자동 저장 가능 여부를 일관된 기준으로 판단 |
| 4 | 파싱 감사 리포트 저장 | 문제 발생 시 추적 가능하게 기록 |
| 5 | 사용자 수정 이력 저장 | 미리보기 수동 수정의 책임성과 추적성 확보 |
| 6 | 실패 원인 안내 강화 | 사용자가 원인을 쉽게 이해하고 조치 가능하게 개선 |

---

## 4. 개선 항목 상세

## 4.1 1순위: 4개 선사 샘플 자동 회귀 테스트화

### 목표

ONE, HAPAG, MAERSK, MSC 샘플 PDF 4세트를 테스트 데이터로 등록하고, 코드 수정 후 자동으로 파싱 결과를 검증한다.

### 필요한 이유

이번 검증 과정에서 선사별로 다음 문제가 발견됐다.

- HAPAG: BL 번호에 페이지 번호가 붙음
- HAPAG: BL 컨테이너가 공백 포함 형식이라 누락
- MAERSK: FA/BL은 숫자 BL, DO는 MAEU 접두어 포함 BL로 불일치
- MAERSK: DO 컨테이너 5개 중 4개만 추출
- MSC: BL 컨테이너 수가 2가 아니라 2026으로 오인
- MSC: DO Gross Weight가 0으로 추출
- MSC: DO No가 비어 있음

이런 문제는 이후 다른 코드를 수정하면서 다시 발생할 수 있으므로 자동 테스트가 필요하다.

### 구현 방향

테스트 파일 예:

```text
tests/test_inbound_carrier_samples.py
```

샘플 경로는 직접 하드코딩하지 않고 환경변수 또는 로컬 fixture 설정으로 관리한다.

예:

```text
TEST_ONE_DIR=D:\program\SQM_inventory\SQM 4.13 입고\2200034590 MIC9000 100MT (화요일 입고)
TEST_HAPAG_DIR=D:\program\SQM_inventory\SQM 4.13 입고\hapag
TEST_MAERSK_DIR=D:\program\SQM_inventory\SQM 4.13 입고\MAEU265083673 AN-MERSK
TEST_MSC_DIR=D:\program\SQM_inventory\SQM 4.13 입고\MEDUW9018104 ANㅡmsc
```

각 선사별 기대값을 정의한다.

| 선사 | SAP | BL | LOT | Container | Gross | Arrival | Free Time |
|---|---|---|---:|---:|---:|---|---|
| ONE | 2200034590 | ONEYSCLG01825300 | 20 | 5 | 102625.0 | 2026-04-11 | 2026-05-02 |
| HAPAG | 2200034659 | HLCUSCL260148627 | 20 | 5 | 102625.0 | 2026-04-11 | 2026-04-24 |
| MAERSK | 2200034449 | MAEU265083673 | 20 | 5 | 102625.0 | 2026-04-10 | 2026-05-01 |
| MSC | 2200034702 | MEDUW9018104 | 8 | 2 | 41050.0 | 2026-04-01 | 2026-04-14 |

### 검증 기준

각 샘플에서 다음을 assert 한다.

- Invoice success
- Packing List success
- BL success
- DO success
- SAP 일치
- BL No 일치
- LOT 수 일치
- 컨테이너 수 일치
- 컨테이너 목록 일치
- Gross Weight 일치
- Arrival Date 추출
- Free Time 추출

### 기대 효과

- 선사별 파싱 로직 수정 시 회귀 오류 즉시 발견
- 코드 수정 후 수동 검증 시간 감소
- 운영 안정성 상승

---

## 4.2 2순위: Picking List 좌표/정규식 동시 비교

### 목표

Picking List 파싱 시 좌표 기반 결과와 정규식 기반 결과를 항상 둘 다 생성하고, 두 결과를 비교한다.

현재는 좌표 결과가 0건일 때 정규식으로 폴백하는 성격이 강하다. 개선 후에는 좌표 결과가 성공해도 정규식 결과와 비교한다.

### 현재 방식

```text
좌표 파싱
→ LOT가 있으면 좌표 결과 사용
→ LOT가 0개면 정규식 폴백
```

### 개선 방식

```text
좌표 파싱 실행
정규식 파싱 실행
두 결과 비교
품질 점수 계산
불일치 있으면 자동 저장 금지
미리보기에서 사용자 검토
```

### 비교 항목

| 비교 항목 | 설명 | 불일치 시 조치 |
|---|---|---|
| Picking No | Customer reference | hard-stop 후보 |
| Sales Order | Sales order | warning 또는 hard-stop |
| Outbound ID | 출고 ID | warning |
| LOT 목록 | Batch number 목록 | hard-stop |
| LOT 수 | 본품 LOT 수 | hard-stop |
| 본품 총 MT | MT 합계 | hard-stop |
| 샘플 LOT 목록 | KG 샘플 목록 | warning 또는 hard-stop |
| 샘플 수 | 샘플 LOT 수 | warning 또는 hard-stop |
| Storage location | 창고/위치 | warning |
| Bag weight | 500/1000kg 등 | warning |

### 결과 구조 예

```json
{
  "coord": {
    "lot_count": 20,
    "total_mt": 100.0,
    "sample_count": 20
  },
  "regex": {
    "lot_count": 20,
    "total_mt": 100.0,
    "sample_count": 20
  },
  "conflicts": [],
  "requires_review": false,
  "quality_score": 98
}
```

### UI 개선

Picking Preview 화면에 다음 정보를 추가한다.

- 좌표 결과 LOT 수
- 정규식 결과 LOT 수
- 본품 MT 비교
- 샘플 KG 비교
- 불일치 항목 목록
- 자동 반영 가능 여부

### 기대 효과

- Picking List 오파싱 사전 차단
- 좌표 틀어짐 감지
- PDF 양식 변경 감지
- 출고 오작동 방지

---

## 4.3 3순위: 파싱 품질 점수 + hard-stop 통합

### 목표

입고, Picking List, Sales Order, DN 등 모든 파싱 결과에 공통 품질 점수를 부여한다.

점수는 0~100점으로 표현하고, 일정 기준 미만이면 자동 저장을 금지한다.

### 품질 점수 예시

| 항목 | 점수 |
|---|---:|
| 필수 문서 모두 존재 | 10 |
| SAP No 일치 | 10 |
| BL No 일치 | 15 |
| LOT 수 일치 | 15 |
| LOT 목록 일치 | 15 |
| Gross Weight 일치 | 10 |
| 컨테이너 수 일치 | 10 |
| 컨테이너 목록 일치 | 10 |
| Arrival / Free Time 존재 | 5 |

총점: 100점

### 등급 기준

| 점수 | 상태 | 조치 |
|---:|---|---|
| 95~100 | PASS | 자동 반영 가능 |
| 80~94 | REVIEW | 사용자 검토 필요 |
| 0~79 | BLOCK | 자동 저장 금지 |

### 공통 hard-stop 조건

아래 조건은 업무상 위험도가 높으므로 자동 저장을 금지한다.

```text
- BL 불일치
- Gross Weight 불일치
- LOT 수 불일치
- LOT 목록 불일치
- 컨테이너 수 불일치
- 컨테이너 목록 불일치
- 샘플 누락
- AI 무료/유료 결과 불일치
- Picking 수량 > RESERVED 수량
- Sales Order가 Picking No와 매칭되지 않음
- 같은 Sales Order 중복 업로드
```

### 구현 위치 후보

```text
features/parsers/parse_quality.py
```

공통 클래스 예:

```python
class ParseQualityResult:
    score: int
    status: str  # PASS / REVIEW / BLOCK
    hard_stops: list
    warnings: list
    details: dict
```

### 기대 효과

- 파싱 성공 여부보다 더 정확한 신뢰도 판단 가능
- 사용자에게 “왜 막혔는지” 설명 가능
- 자동 저장 기준 통일

---

## 4.4 4순위: 파싱 감사 리포트 저장

### 목표

파싱이 끝날 때마다 결과와 검증 내용을 JSON 또는 Excel로 저장한다.

문제가 생겼을 때 다음을 추적할 수 있어야 한다.

- 어떤 파일을 파싱했는지
- 어떤 값이 추출됐는지
- 어떤 문서에서 나온 값인지
- 어떤 항목이 불일치였는지
- 사용자가 어떤 값을 선택했는지
- 자동 반영됐는지, 수동 검토됐는지

### 저장 위치 예

```text
logs/parse_audit/
```

파일명 예:

```text
parse_audit_20260429_103015_ONEYSCLG01825300.json
parse_audit_20260429_103015_ONEYSCLG01825300.xlsx
```

### JSON 구조 예

```json
{
  "created_at": "2026-04-29T10:30:15",
  "workflow": "inbound",
  "carrier": "ONE",
  "files": {
    "fa": "...",
    "pl": "...",
    "bl": "...",
    "do": "..."
  },
  "parsed": {
    "sap_no": "2200034590",
    "bl_no": "ONEYSCLG01825300",
    "lot_count": 20,
    "container_count": 5,
    "gross_weight_kg": 102625.0
  },
  "quality": {
    "score": 100,
    "status": "PASS",
    "hard_stops": [],
    "warnings": []
  },
  "user_actions": []
}
```

### Excel 리포트 시트 구성

| 시트 | 내용 |
|---|---|
| Summary | 점수, 상태, 파일 목록 |
| Parsed Fields | SAP, BL, 중량, 날짜 등 |
| LOT Compare | FA/PL LOT 비교 |
| Container Compare | BL/DO/PL 컨테이너 비교 |
| Warnings | 경고 목록 |
| User Edits | 사용자 수정 이력 |

### 기대 효과

- 파싱 오류 발생 시 사후 추적 가능
- 고객/내부 문의 대응 쉬움
- 프로그램 수정 전후 결과 비교 가능

---

## 4.5 5순위: 사용자 수정 이력 저장

### 목표

미리보기 화면에서 사용자가 값을 수정하거나 무료/유료 AI 값 중 하나를 선택했을 때 이력을 저장한다.

### 저장해야 할 항목

| 항목 | 설명 |
|---|---|
| workflow | inbound / picking / sales_order |
| document_type | FA / PL / BL / DO / Picking |
| field_name | 수정한 필드 |
| row_no | 미리보기 행 번호 |
| old_value | 수정 전 값 |
| new_value | 수정 후 값 |
| source | manual / free_ai / paid_ai / coord / regex |
| user_name | 사용자명 |
| edited_at | 수정 시간 |
| reason | 선택 사유 또는 메모 |

### DB 테이블 예

```sql
CREATE TABLE IF NOT EXISTS parse_edit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workflow TEXT,
    document_type TEXT,
    field_name TEXT,
    row_no INTEGER,
    old_value TEXT,
    new_value TEXT,
    source TEXT,
    user_name TEXT,
    reason TEXT,
    edited_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

### 적용 대상

- 입고 미리보기 수정
- AI 무료/유료 비교값 선택
- Picking Preview 수정
- Sales Order 매칭 보정
- Free Time / Arrival 수동 보정

### 기대 효과

- 누가 어떤 값을 왜 바꿨는지 추적 가능
- 수동 수정으로 인한 문제를 사후 확인 가능
- 감사 리포트와 연결 가능

---

## 4.6 6순위: 실패 원인 안내 강화

### 목표

현재 error_message는 개발자 관점 메시지가 많다. 사용자에게는 업무 언어로 원인을 설명해야 한다.

### 개선 전 예

```text
429 RESOURCE_EXHAUSTED
Input should be a valid integer
BL parse failed
```

### 개선 후 예

```text
Gemini 무료 호출 한도 20회를 초과했습니다. 오늘은 로컬/Ollama 또는 OpenAI fallback을 사용하세요.

BL 번호가 문서 간 일치하지 않습니다.
FA: MAEU265083673
DO: 265083673

PL에는 20 LOT가 있으나 FA에는 19 LOT만 있습니다.
누락 LOT를 확인하세요.

BL에는 컨테이너 5개가 있으나 DO에는 4개만 있습니다.
D/O Free Time 표를 확인하세요.
```

### 구현 방향

에러 코드 매핑 파일을 만든다.

```text
features/parsers/error_explainer.py
```

예:

```python
def explain_parse_error(error: Exception | str) -> dict:
    return {
        "title": "Gemini 한도 초과",
        "message": "Gemini 무료 호출 한도에 도달했습니다.",
        "action": "Ollama 또는 OpenAI fallback을 사용하거나 내일 다시 시도하세요.",
        "severity": "warning",
    }
```

### 기대 효과

- 사용자가 문제 원인을 바로 이해
- 불필요한 디버깅 요청 감소
- 운영 중 대응 속도 향상

---

## 5. 추천 구현 순서

### Phase 1: 회귀 테스트 기반 만들기

작업:

- `tests/test_inbound_carrier_samples.py` 추가
- 4개 선사 샘플 경로 환경변수 지원
- ONE/HAPAG/MAERSK/MSC 기대값 assert

완료 기준:

- 로컬 샘플 PDF가 있을 때 4개 선사 테스트 통과
- 샘플 PDF가 없으면 skip 처리

---

### Phase 2: Picking List 비교 파서

작업:

- 좌표 결과와 정규식 결과를 항상 둘 다 생성
- 비교 결과 객체 추가
- Picking Preview에 비교 결과 표시
- 불일치 시 자동 반영 금지

완료 기준:

- 좌표/정규식 LOT 수가 다르면 REVIEW 또는 BLOCK
- 본품 MT 합계가 다르면 BLOCK
- 샘플 누락이면 REVIEW 또는 BLOCK

---

### Phase 3: 공통 품질 점수 엔진

작업:

- `features/parsers/parse_quality.py` 추가
- 입고 / Picking / SO 공통 점수 계산
- PASS / REVIEW / BLOCK 상태 반환

완료 기준:

- 입고 미리보기에서 품질 점수 표시
- Picking Preview에서 품질 점수 표시
- BLOCK 상태에서는 업로드 버튼 차단

---

### Phase 4: 감사 리포트 저장

작업:

- `logs/parse_audit/` 자동 생성
- JSON 리포트 저장
- 필요 시 Excel 리포트 추가

완료 기준:

- 파싱 1회마다 audit JSON 생성
- 파일 경로, 파싱 결과, 품질 점수, 경고/오류 포함

---

### Phase 5: 사용자 수정 이력

작업:

- `parse_edit_log` 테이블 추가
- 미리보기 수정 시 old/new 기록
- AI 비교값 선택 시 선택 출처 기록

완료 기준:

- 수동 수정 내역 조회 가능
- 감사 리포트에 수정 이력 포함 가능

---

## 6. 최종 목표 상태

최종적으로 프로그램은 다음 흐름이 되어야 한다.

```text
파일 선택
→ 다중 파서 실행
→ 결과 비교
→ 품질 점수 계산
→ hard-stop 판단
→ 미리보기 표시
→ 사용자 수정/확인
→ 감사 리포트 저장
→ Preflight
→ DB 반영
```

자동 저장은 다음 조건에서만 허용한다.

```text
품질 점수 PASS
hard-stop 없음
필수 문서 정합성 통과
사용자 검토 필요 항목 없음
Preflight 통과
```

그 외에는 반드시 사용자 검토 후 반영한다.

---

## 7. 결론

현재 파싱 로직은 실무 사용 가능한 수준까지 올라와 있다.  
다음 개선의 핵심은 파서를 더 많이 추가하는 것이 아니라, **파싱 결과를 자동으로 믿어도 되는지 판단하는 검증 체계**를 강화하는 것이다.

가장 먼저 해야 할 일은 4개 선사 샘플 자동 회귀 테스트화다.  
그 다음 Picking List 좌표/정규식 동시 비교, 공통 품질 점수, 감사 리포트 저장 순서로 진행하는 것이 효율적이다.
