# FA / PL Coordinate Parsing Logic

작성일: 2026-04-28

대상 샘플:

- `D:\program\SQM_inventory\SQM 4.13 입고\hapag\2200034659 FA.pdf`
- `D:\program\SQM_inventory\SQM 4.13 입고\hapag\2200034659 PL.pdf`

목표:

- FA와 PL은 1차로 API 없이 PyMuPDF 좌표 기반 파싱한다.
- PDF 복사/재저장으로 전체 위치가 약간 흔들리는 경우를 앵커 드리프트 보정으로 흡수한다.
- 좌표 파싱이 실패하거나 필수값 검증이 실패하면 2차로 AI API 파싱을 사용한다.

## 1. 기본 원칙

FA와 PL은 SQM SALAR SpA 고정 양식이므로 선사별로 양식이 달라지는 BL/DO와 다르게 하드코딩 좌표 기반 파싱이 적합하다.

좌표는 절대 픽셀이 아니라 페이지 너비/높이 대비 퍼센트로 계산한다.

```text
x_pct = word.x0 / page_width * 100
y_pct = word.y0 / page_height * 100
```

이 방식은 A4 크기, 렌더링 배율, PDF 재저장 차이에 더 안정적이다.

## 2. 처리 순서

```text
PDF 열기
→ page.get_text("words")로 단어와 좌표 추출
→ 앵커 단어 위치로 dx/dy 드리프트 계산
→ 보정된 좌표 박스에서 필드 추출
→ 숫자/날짜/LOT 정규화
→ 필수값 검증
→ 성공 시 API 호출 없이 결과 반환
→ 실패 시 AI API fallback
```

## 3. FA Parsing

구현 파일:

- `parsers/document_parser_modular/invoice_mixin.py`

진입점:

```python
DocumentParserV3().parse_invoice(pdf_path)
```

### 3.1 앵커

FA는 아래 단어를 기준으로 전체 문서 이동량을 계산한다.

```python
FA_ANCHORS = {
    "FECHA/DATE": (69.75, 21.45),
    "Ref.SQM/Our": (76.68, 31.96),
    "Origen/Origin": (56.13, 38.91),
    "Transporte/Transport": (53.24, 42.38),
    "BL-AWB-CRT": (75.92, 42.38),
}
```

각 앵커의 실제 위치와 기준 위치 차이를 모아 중앙값을 `dx`, `dy`로 사용한다.

### 3.2 주요 필드

```text
invoice_no      : 우상단 N° 영역
invoice_date    : FECHA/DATE 오른쪽
sap_no          : Ref.SQM/Our Order 오른쪽
vessel          : Transporte/Transport 오른쪽
bl_no           : BL-AWB-CRT Number 아래/오른쪽
origin          : Origen/Origin 오른쪽
destination     : Destino/Destination 오른쪽
quantity_mt     : 제품 행 수량 영역
unit_price      : 제품 행 단가 영역
total_amount    : 제품 행 금액 영역
net_weight_kg   : "Netos/Net KG" 정규식
gross_weight_kg : "Bruto/KG Gross" 정규식
package_count   : "Number of Packaging" 정규식
package_type    : "Type of Packaging" 정규식
lot_numbers     : "N° LOTES:" 이후 LOT 목록 정규식
```

중량은 좌표보다 정규식이 더 안정적이므로 현재는 전체 텍스트에서 추출한다.

### 3.3 검증 기준

FA 좌표 파싱 성공 최소 조건:

```text
invoice_no 존재
sap_no 존재
```

권장 추가 검증:

```text
quantity_mt > 0
net_weight_kg > 0
gross_weight_kg > 0
lot_numbers 1개 이상
```

샘플 검증 결과:

```text
invoice_no=17760
invoice_date=2026-02-26
sap_no=2200034659
bl_no=HLCUSCL260148627
vessel=BUENAVENTURA EXPRESS 2602W
quantity_mt=100.02
net_weight_kg=100020.0
gross_weight_kg=102625.0
package_count=200
package_type=MAXISACO MIC9000
lot_numbers=20개
```

## 4. PL Parsing

구현 파일:

- `parsers/document_parser_modular/packing_mixin.py`

진입점:

```python
DocumentParserV3().parse_packing_list(pdf_path)
```

### 4.1 앵커

PL은 아래 단어를 기준으로 전체 문서 이동량을 계산한다.

```python
PL_ANCHORS = {
    "PRODUCT": (3.96, 11.66),
    "Folio": (75.61, 6.43),
    "CONTAINER": (8.37, 24.47),
}
```

### 4.2 헤더 좌표

```text
folio       : x=82~95, y=5.5~7.5
product     : x=13~55, y=10.5~13.0
packing     : x=13~50, y=13.0~15.5
code        : x=13~48, y=15.5~18.0
vessel      : x=60~97, y=10.5~13.0
customer    : x=60~80, y=13.0~15.5
destination : x=60~80, y=15.5~18.0
```

### 4.3 LOT 행 탐지

PL 상세 행은 좌측 `LIST` 번호를 기준으로 찾는다.

```text
x=3.0~7.0%
y=26~62%
text가 숫자인 단어
```

이 숫자의 y 좌표가 각 LOT 행의 기준선이 된다.

### 4.4 행별 컬럼 좌표

각 행의 기준 y를 중심으로 `v_tol=0.70` 범위에서 컬럼을 읽는다.

```text
container_no      : x=7.0~16.5
lot_no            : x=17.0~25.0
lot_sqm           : x=26.0~32.5
mxbg_pallet       : x=33.5~37.0
plastic_jars      : x=40.5~43.0
net_weight_kg     : x=47.5~52.0
gross_weight_kg   : x=54.5~62.0
del_no            : x=63.5~69.5
al_no             : x=70.0~76.0
acc_net_weight    : x=79.0~85.0
acc_gross_weight  : x=88.5~97.0
```

### 4.5 숫자 정규화

PL 숫자는 유럽식 표기가 섞인다.

```text
5.001       → 5001.0
5.131,250   → 5131.25
100.020     → 100020.0
102.625,000 → 102625.0
```

`mxbg_pallet`, `plastic_jars`는 정수로 정규화한다.

### 4.6 검증 기준

PL 좌표 파싱 성공 최소 조건:

```text
LOT 행 1개 이상
각 LOT의 lot_no 존재
각 LOT의 net_weight_kg > 0
total_net_weight_kg > 0
```

권장 추가 검증:

```text
total_net_weight_kg == 마지막 acc_net_weight
total_gross_weight_kg == 마지막 acc_gross_weight
total_maxibag == sum(mxbg_pallet)
total_plastic_jars == sum(plastic_jars)
```

샘플 검증 결과:

```text
folio=3812291
sap_no=2200034659
vessel=BUENAVENTURA EXPRESS 2602W
product=LITHIUM CARBONATE
packing=MX 500 Kg (In Plastic Pallet)
code=MIC9000.00/500 KG
customer=SOQUIMICH LLC
destination=GWANGYANG
total_lots=20
total_net_weight_kg=100020.0
total_gross_weight_kg=102625.0
total_maxibag=200
total_plastic_jars=20
```

첫 행:

```text
container_no=HAMU 272359-6
lot_no=1126021724
lot_sqm=1024411
mxbg_pallet=10
plastic_jars=1
net_weight_kg=5001.0
gross_weight_kg=5131.25
del_no=1930985
al_no=1930994
acc_net_weight=5001.0
acc_gross_weight=5131.25
```

마지막 행:

```text
lot_no=1126021767
acc_net_weight=100020.0
acc_gross_weight=102625.0
```

## 5. Fallback Policy

FA/PL의 1차 좌표 파싱은 아래 조건 중 하나라도 발생하면 실패로 본다.

```text
PDF 텍스트 추출 실패
앵커는 없어도 되지만 필수값 추출 실패
FA: invoice_no 또는 sap_no 없음
PL: LOT 행 없음
PL: lot_no 없음 또는 net_weight_kg <= 0
PL: total_net_weight_kg <= 0
```

실패 시:

```text
FA  → AI API parse_invoice fallback
PL  → AI API parse_packing_list fallback
```

단, 운영 정책상 FA/PL은 고정 양식이므로 fallback이 발생하면 "양식 변경 또는 스캔 PDF 가능성"으로 보고 검수 화면을 띄우는 것이 좋다.

## 6. 운영 권장 구조

```text
1차 좌표 파싱
→ 필수값 검증
→ FA/PL 상호 대조
   - sap_no 일치
   - vessel 일치
   - net_weight 일치
   - gross_weight 일치
   - LOT 목록 일치 또는 포함 관계 확인
→ 성공 시 입고 후보 생성
→ 실패 시 API 파싱
→ API 결과도 검수 화면에서 사용자 승인 후 DB 반영
```

FA/PL은 새 선사 여부와 무관하게 고객사 고정 양식이므로, BL/DO처럼 선사별 템플릿을 늘리는 방식보다 현재 좌표 로직을 유지하고 검증만 강화하는 편이 안정적이다.
