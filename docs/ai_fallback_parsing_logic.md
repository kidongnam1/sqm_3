# AI Fallback Parsing Logic

작성일: 2026-04-28

대상 문서:

- FA / Invoice
- PL / Packing List
- BL / Bill of Lading
- DO / Delivery Order

목표:

- 1차 좌표 등록 파싱이 실패할 때만 Gemini API를 사용한다.
- Gemini API 결과는 좌표 파싱 결과와 동일한 내부 데이터 모델로 변환한다.
- 이후 입고 로직은 파싱 방식이 좌표인지 AI인지 몰라도 같은 방식으로 처리한다.

## 1. 핵심 원칙

AI fallback은 별도 결과 형식을 만들면 안 된다.

반드시 아래 표준 모델로 정규화한다.

```text
FA → InvoiceData
PL → PackingListData
BL → BLData
DO → DOData
```

즉, 좌표 파싱과 AI 파싱은 아래처럼 같은 출구를 가져야 한다.

```text
좌표 파싱 성공 → InvoiceData / PackingListData / BLData / DOData
좌표 파싱 실패 → Gemini JSON → 정규화 → InvoiceData / PackingListData / BLData / DOData
```

## 2. 전체 흐름

```text
parse_inbound_4docs(files, carrier_id)
  ├─ FA: try_coordinate_invoice()
  │     └─ fail → try_gemini_invoice()
  ├─ PL: try_coordinate_packing_list()
  │     └─ fail → try_gemini_packing_list()
  ├─ BL: try_coordinate_bl(carrier_id)
  │     └─ fail → try_gemini_bl(carrier_id)
  ├─ DO: try_coordinate_do(carrier_id)
  │     └─ fail → try_gemini_do(carrier_id)
  ├─ normalize_all()
  ├─ cross_check_4docs()
  ├─ confidence_score()
  └─ review_required 여부 결정
```

## 3. AI 호출 조건

Gemini API는 아래 경우에만 호출한다.

```text
PDF 텍스트 추출 실패
좌표 앵커 탐지 실패
필수 필드 누락
필수 필드 값 형식 오류
4종 문서 교차검증 실패
사용자가 수동으로 "AI 재파싱" 선택
```

좌표 파싱 결과가 완전하면 API를 호출하지 않는다.

## 4. 공통 Gemini 응답 규칙

모든 문서 프롬프트는 다음 규칙을 강제한다.

```text
JSON만 응답한다.
설명, 마크다운, 코드블록을 붙이지 않는다.
모르는 값은 null 또는 ""로 둔다.
추측해서 만들지 않는다.
숫자는 kg, MT, 날짜 단위를 명확히 변환한다.
유럽식 숫자는 정확히 해석한다.
문서에 없는 값은 다른 문서에서 가져오지 않는다.
```

숫자 해석 규칙:

```text
5.001       → 5001.0
5.131,250   → 5131.25
100.020     → 100020.0
102.625,000 → 102625.0
100,020.000 → 100020.0
100.02 MT   → 100.02
```

날짜 정규화:

```text
26.02.2026 → 2026-02-26
26 FEB 2026 → 2026-02-26
2026/02/26 → 2026-02-26
```

컨테이너 번호 정규화:

```text
HAMU 272359-6 → HAMU2723596 또는 원문/정규화값 둘 다 보관
HLCU 123456-7 → HLCU1234567
```

DB 저장용은 기존 코드 정책에 맞춰 원문 또는 정규화값을 선택한다. 비교용 키는 공백/하이픈 제거값을 사용한다.

## 5. 공통 반환 래퍼

AI fallback 결과는 내부적으로 아래 메타 정보를 함께 가진다.

```json
{
  "parse_method": "gemini",
  "doc_type": "FA|PL|BL|DO",
  "carrier_id": "HAPAG|MSC|MAERSK|HMM|CMA_CGM",
  "success": true,
  "confidence": 0.0,
  "warnings": [],
  "raw_json": {}
}
```

단, 실제 업무 로직에 넘기는 객체는 `InvoiceData`, `PackingListData`, `BLData`, `DOData`다. 위 메타는 로그와 검수 화면용이다.

## 6. FA Gemini Schema

FA는 좌표 파싱의 `InvoiceData`와 동일한 결과가 나와야 한다.

```json
{
  "sap_no": "2200034659",
  "invoice_no": "17760",
  "invoice_date": "2026-02-26",
  "bl_no": "HLCUSCL260148627",
  "customer_name": "SOQUIMICH LLC",
  "product_code": "MIC9000.00",
  "product_name": "LITHIUM CARBONATE - BATTERY GRADE - MICRONIZED",
  "quantity_mt": 100.02,
  "unit_price": 9272.00,
  "total_amount": 927385.44,
  "currency": "USD",
  "net_weight_kg": 100020.0,
  "gross_weight_kg": 102625.0,
  "package_count": 200,
  "package_type": "MAXISACO MIC9000",
  "vessel": "BUENAVENTURA EXPRESS 2602W",
  "origin": "PUERTO ANGAMOS-CHILE",
  "destination": "GWANGYANG-SOUTH KOREA",
  "incoterm": "CIF",
  "lot_numbers": ["1126021720"]
}
```

FA 필수값:

```text
sap_no
invoice_no
invoice_date
quantity_mt
net_weight_kg
gross_weight_kg
lot_numbers
```

FA 정규화:

```python
result = InvoiceData()
result.sap_no = norm_sap(data["sap_no"])
result.invoice_no = digits(data["invoice_no"])
result.salar_invoice_no = result.invoice_no
result.invoice_date = norm_date(data["invoice_date"])
result.bl_no = norm_bl(data["bl_no"])
result.customer_name = data["customer_name"] or "SOQUIMICH LLC"
result.product_code = data["product_code"] or "MIC9000.00"
result.product_name = data["product_name"]
result.quantity_mt = to_float(data["quantity_mt"])
result.net_weight_kg = to_kg(data["net_weight_kg"])
result.gross_weight_kg = to_kg(data["gross_weight_kg"])
result.package_count = to_int(data["package_count"])
result.package_type = clean_text(data["package_type"])
result.vessel = clean_text(data["vessel"])
result.origin = clean_text(data["origin"])
result.destination = clean_text(data["destination"])
result.lot_numbers = unique_lots(data["lot_numbers"])
result.success = bool(result.sap_no and result.invoice_no)
```

## 7. PL Gemini Schema

PL은 좌표 파싱의 `PackingListData`와 동일한 결과가 나와야 한다.

```json
{
  "folio": "3812291",
  "sap_no": "2200034659",
  "product": "LITHIUM CARBONATE",
  "packing": "MX 500 Kg (In Plastic Pallet)",
  "code": "MIC9000.00/500 KG",
  "vessel": "BUENAVENTURA EXPRESS 2602W",
  "customer": "SOQUIMICH LLC",
  "destination": "GWANGYANG",
  "lots": [
    {
      "list_no": 1,
      "container_no": "HAMU 272359-6",
      "lot_no": "1126021724",
      "lot_sqm": "1024411",
      "mxbg_pallet": 10,
      "plastic_jars": 1,
      "net_weight_kg": 5001.0,
      "gross_weight_kg": 5131.25,
      "del_no": "1930985",
      "al_no": "1930994",
      "acc_net_weight": 5001.0,
      "acc_gross_weight": 5131.25
    }
  ],
  "total_lots": 20,
  "total_net_weight_kg": 100020.0,
  "total_gross_weight_kg": 102625.0,
  "total_maxibag": 200,
  "total_plastic_jars": 20
}
```

PL 필수값:

```text
lots 1개 이상
lot_no
net_weight_kg
gross_weight_kg
total_net_weight_kg
total_gross_weight_kg
```

PL 정규화:

```python
result = PackingListData()
result.folio = digits(data["folio"])
result.sap_no = norm_sap(data.get("sap_no")) or sap_from_filename(pdf_path)
result.product = clean_text(data["product"])
result.packing = clean_text(data["packing"])
result.code = clean_text(data["code"])
result.vessel = clean_text(data["vessel"])
result.customer = clean_text(data["customer"])
result.destination = clean_text(data["destination"])

for item in data["lots"]:
    lot = LOTInfo(
        list_no=to_int(item["list_no"]),
        container_no=clean_container_display(item["container_no"]),
        lot_no=norm_lot(item["lot_no"]),
        lot_sqm=digits(item["lot_sqm"]),
        mxbg_pallet=to_int(item["mxbg_pallet"], default=10),
        plastic_jars=to_int(item["plastic_jars"], default=1),
        net_weight_kg=to_kg(item["net_weight_kg"]),
        gross_weight_kg=to_kg(item["gross_weight_kg"]),
        del_no=digits(item["del_no"]),
        al_no=digits(item["al_no"]),
        acc_net_weight=to_kg(item["acc_net_weight"]),
        acc_gross_weight=to_kg(item["acc_gross_weight"]),
    )
    result.lots.append(lot)
    result.rows.append(to_packing_row(lot))

result.total_lots = len(result.lots)
result.total_net_weight_kg = data_total_or_sum(data["total_net_weight_kg"], result.lots, "net")
result.total_gross_weight_kg = data_total_or_sum(data["total_gross_weight_kg"], result.lots, "gross")
result.total_maxibag = sum(l.mxbg_pallet for l in result.lots)
result.total_plastic_jars = sum(l.plastic_jars for l in result.lots)
result.containers = sorted_unique(l.container_no for l in result.lots)
result.success = len(result.lots) > 0
```

## 8. BL Gemini Schema

BL은 선사별 양식 차이가 크므로 `carrier_id`와 선사별 주의사항을 프롬프트에 넣는다.

```json
{
  "carrier_id": "HAPAG",
  "carrier_name": "Hapag-Lloyd",
  "bl_no": "HLCUSCL260148627",
  "booking_no": "",
  "scac": "HLCU",
  "sap_no": "2200034659",
  "shipper_name": "SQM SALAR SpA",
  "consignee_name": "SOQUIMICH LLC",
  "vessel": "BUENAVENTURA EXPRESS",
  "voyage": "2602W",
  "port_of_loading": "PUERTO ANGAMOS, CHILE",
  "port_of_discharge": "GWANGYANG, SOUTH KOREA",
  "place_of_receipt": "",
  "place_of_delivery": "",
  "shipped_on_board_date": "2026-02-26",
  "issue_date": "2026-02-26",
  "product_name": "LITHIUM CARBONATE - BATTERY GRADE - MICRONIZED",
  "total_containers": 5,
  "total_packages": 220,
  "net_weight_kg": 100020.0,
  "gross_weight_kg": 102625.0,
  "containers": [
    {
      "container_no": "HAMU2723596",
      "seal_no": "",
      "size_type": "40",
      "weight_kg": 20525.0,
      "measurement_cbm": 0,
      "package_count": 44
    }
  ]
}
```

BL 필수값:

```text
bl_no
vessel
voyage
port_of_loading
port_of_discharge
containers 또는 total_containers
gross_weight_kg
```

BL 정규화:

```python
result = BLData()
result.bl_no = norm_bl(data["bl_no"])
result.booking_no = norm_bl(data.get("booking_no")) or result.bl_no
result.scac = data.get("scac") or result.bl_no[:4]
result.sap_no = norm_sap(data.get("sap_no"))
result.carrier_id = carrier_id
result.carrier_name = data.get("carrier_name")
result.vessel = clean_text(data["vessel"])
result.voyage = clean_text(data["voyage"])
result.port_of_loading = clean_port(data["port_of_loading"])
result.port_of_discharge = clean_port(data["port_of_discharge"])
result.shipped_on_board_date = norm_date(data["shipped_on_board_date"])
result.issue_date = norm_date(data["issue_date"])
result.total_containers = to_int(data["total_containers"])
result.total_packages = to_int(data["total_packages"])
result.net_weight_kg = to_kg(data["net_weight_kg"])
result.gross_weight_kg = to_kg(data["gross_weight_kg"])
result.containers = normalize_container_list(data["containers"])
result.success = bool(result.bl_no)
```

## 9. DO Gemini Schema

DO는 Free Time, CON RETURN, 반납지 추출이 핵심이다.

```json
{
  "carrier_id": "HAPAG",
  "do_no": "26032314Y6OD",
  "bl_no": "HLCUSCL260148627",
  "vessel": "BUENAVENTURA EXPRESS",
  "voyage_no": "2602W",
  "port_of_loading": "PUERTO ANGAMOS, CHILE",
  "port_of_discharge": "GWANGYANG, SOUTH KOREA",
  "issue_date": "2026-03-20",
  "arrival_date": "2026-04-13",
  "gross_weight_kg": 102625.0,
  "cbm": 0,
  "containers": [
    {
      "container_no": "HAMU2723596",
      "seal_no": "",
      "free_time": "2026-04-20",
      "free_time_date": "2026-04-20",
      "return_yard": "KRKNYTM"
    }
  ],
  "free_time_info": [
    {
      "container_no": "HAMU2723596",
      "free_time_date": "2026-04-20",
      "return_location": "KRKNYTM",
      "storage_free_days": 7
    }
  ]
}
```

DO 필수값:

```text
do_no 또는 bl_no
arrival_date
containers 1개 이상
free_time_info 1개 이상 또는 대표 free_time_date
```

DO 정규화:

```python
result = DOData()
result.carrier_id = carrier_id
result.do_no = clean_text(data["do_no"])
result.bl_no = norm_bl(data["bl_no"])
result.vessel = clean_text(data["vessel"])
result.voyage_no = clean_text(data["voyage_no"])
result.port_of_loading = clean_port(data["port_of_loading"])
result.port_of_discharge = clean_port(data["port_of_discharge"])
result.issue_date = norm_date(data["issue_date"])
result.arrival_date = norm_date(data["arrival_date"])
result.gross_weight_kg = to_kg(data["gross_weight_kg"])
result.cbm = to_float(data["cbm"])

for c in data["containers"]:
    ci = ContainerInfo()
    ci.container_no = norm_container(c["container_no"])
    ci.seal_no = clean_text(c.get("seal_no"))
    ci.weight_kg = to_kg(c.get("weight_kg"))
    result.containers.append(ci)

for ft in data["free_time_info"] or derive_from_containers(data["containers"]):
    result.free_time_info.append(FreeTimeInfo(
        container_no=norm_container(ft["container_no"]),
        free_time_date=norm_date(ft["free_time_date"]),
        return_location=clean_text(ft["return_location"]),
        storage_free_days=days_between(result.arrival_date, ft["free_time_date"]),
    ))

result.success = bool(result.bl_no and result.containers)
```

## 10. Gemini Prompt Template

공통 시스템 프롬프트:

```text
당신은 SQM Inventory 입고 문서 파싱 엔진입니다.
반드시 JSON 객체 하나만 반환하세요.
문서에 없는 값은 빈 문자열 또는 null로 두고 절대 추측하지 마세요.
숫자는 실제 단위로 정규화하세요.
유럽식 숫자 표기를 정확히 해석하세요.
날짜는 YYYY-MM-DD 형식으로 반환하세요.
컨테이너 번호는 공백과 하이픈을 제거한 정규화값을 우선 반환하되,
원문 표시가 필요한 필드는 원문도 유지하세요.
```

문서별 사용자 프롬프트:

```text
문서 유형: {doc_type}
선사: {carrier_id}
목표 스키마:
{schema_json}

주의사항:
{carrier_or_doc_hint}

이 PDF에서 위 스키마에 맞는 JSON만 추출하세요.
```

선사별 힌트 예:

```text
HAPAG BL:
- BL 번호는 보통 HLCU로 시작한다.
- SWB-No. 또는 Sea Waybill No. 주변 값을 BL No로 본다.
- Booking No와 BL No를 혼동하지 않는다.

MAERSK BL:
- B/L No.가 Booking No와 같을 수 있다.
- MAEU + 숫자 형식 또는 숫자 형식이 나올 수 있다.

MSC BL:
- MEDU 또는 MSCU로 시작하는 번호가 BL No일 가능성이 높다.
- Rider Page의 컨테이너 번호를 BL No로 오인하지 않는다.

DO:
- Free Time 날짜와 Return Yard를 컨테이너별로 추출한다.
- 대표 CON RETURN은 컨테이너별 Free Time 중 가장 늦은 날짜로 계산한다.
```

## 11. 결과 검증

AI 결과는 곧바로 DB에 넣지 않는다. 반드시 정규화 후 검증한다.

문서 내부 검증:

```text
FA: quantity_mt * 1000 ~= net_weight_kg
PL: sum(lot.net_weight_kg) == total_net_weight_kg
PL: sum(lot.gross_weight_kg) == total_gross_weight_kg
PL: total_maxibag == sum(mxbg_pallet)
BL: len(containers) == total_containers 또는 total_containers가 비어 있으면 보강
DO: free_time_date >= arrival_date
```

4종 문서 교차검증:

```text
FA.sap_no == PL.sap_no
FA.bl_no == BL.bl_no == DO.bl_no
FA.vessel ~= PL.vessel ~= BL.vessel ~= DO.vessel
FA.net_weight_kg == PL.total_net_weight_kg
FA.gross_weight_kg == PL.total_gross_weight_kg == BL.gross_weight_kg
PL.lot_numbers == FA.lot_numbers 또는 PL LOT이 FA LOT에 포함
DO.containers ⊆ BL.containers
```

검증 실패 시:

```text
DB 반영 차단
검수 화면 표시
좌표 결과와 AI 결과를 나란히 표시
사용자 승인 후에만 저장
```

## 12. Confidence Score

AI 결과 신뢰도는 필드 개수만으로 판단하지 않는다.

```text
100점 시작
- 필수값 누락: 항목당 -20
- 숫자 합계 불일치: -20
- BL/DO 번호 불일치: -30
- LOT 목록 불일치: -20
- 컨테이너 목록 불일치: -20
- 날짜 역전: -20
```

정책:

```text
score >= 90  → 자동 승인 후보
70~89        → 검수 필요
70 미만      → 실패 처리, 수동 검수 필수
```

입고처럼 재고 DB를 변경하는 작업은 가능하면 `score >= 90`이어도 최종 미리보기는 보여주는 것이 좋다.

## 13. 구현 위치 제안

현재 코드 기준 권장 위치:

```text
parsers/document_parser_modular/
  ai_fallback.py              # 공통 Gemini 호출/JSON 추출/정규화
  invoice_mixin.py            # 좌표 실패 시 ai_fallback.parse_invoice()
  packing_mixin.py            # 좌표 실패 시 ai_fallback.parse_packing_list()
  bl_mixin.py                 # 좌표 실패 시 ai_fallback.parse_bl()
  do_mixin.py                 # 좌표 실패 시 ai_fallback.parse_do()
```

기존 `features/ai/gemini_parser.py`는 실제 API 호출 구현으로 유지하고, `ai_fallback.py`는 다음 책임만 가진다.

```text
프롬프트 생성
JSON 파싱
숫자/날짜/컨테이너 정규화
document_models 객체로 변환
검증 결과와 confidence 생성
```

## 14. 권장 Python 골격

```python
def parse_with_fallback(doc_type, pdf_path, carrier_id="", coordinate_fn=None):
    coord_result = None
    coord_error = ""

    try:
        coord_result = coordinate_fn(pdf_path)
        if validate_doc(doc_type, coord_result).ok:
            coord_result.parse_method = "coordinate"
            return coord_result
    except Exception as exc:
        coord_error = str(exc)

    ai_json = call_gemini(doc_type=doc_type, pdf_path=pdf_path, carrier_id=carrier_id)
    ai_result = normalize_ai_result(doc_type, ai_json, pdf_path, carrier_id)
    validation = validate_doc(doc_type, ai_result)

    ai_result.raw_response = json.dumps(ai_json, ensure_ascii=False)
    ai_result.parse_method = "gemini"

    if not validation.ok:
        ai_result.success = False
        ai_result.error_message = "; ".join(validation.errors)
        raise RuntimeError(ai_result.error_message)

    return ai_result
```

4종 통합:

```python
def parse_inbound_docs_with_ai_fallback(files, carrier_id):
    docs = ShipmentDocuments()
    docs.invoice = parse_with_fallback("FA", files.fa, carrier_id, parse_invoice_coord)
    docs.packing_list = parse_with_fallback("PL", files.pl, carrier_id, parse_pl_coord)
    docs.bl = parse_with_fallback("BL", files.bl, carrier_id, parse_bl_coord)
    docs.do = parse_with_fallback("DO", files.do, carrier_id, parse_do_coord)

    cross = cross_check_documents(docs.invoice, docs.packing_list, docs.bl, docs.do)
    docs.cross_check_result = cross

    if not cross.is_clean:
        docs.validation_errors.extend(str(item) for item in cross.items)
        docs.review_required = True

    return docs
```

## 15. 운영 결론

AI fallback의 목적은 "AI가 편하게 알아서 파싱"이 아니다.

정확한 목적은 다음 하나다.

```text
좌표 파싱이 만든 결과와 같은 구조를 AI가 대신 채우게 하는 것
```

따라서 API 응답은 항상 강한 JSON 스키마로 제한하고, 정규화/검증/교차검증을 통과한 값만 기존 입고 로직에 넘겨야 한다.
