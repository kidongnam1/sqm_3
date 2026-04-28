# carrier_profiles — SQM v8.7.0 YAML 플러그인

## 목적

`features/ai/bl_carrier_registry.py` 의 Python 하드코딩 `CARRIER_TEMPLATES`
dict 를 **교체하지 않고** 옵셔널 YAML 레이어로 확장한다.

- 신규 선사를 추가하려면 `profiles/<carrier>.yml` 파일 1개만 작성한다.
- 기존 Python 템플릿(MSC/MAERSK/HMM/CMA_CGM/ONE)의 동작은 **100% 보존**된다.
- `pyyaml` 미설치 환경에서도 앱은 정상 부팅한다 (로더는 빈 dict 반환).

## v8.7.0 정책 (중요)

- **자동 선사 감지는 제거되었다** (Chunk A).
  - `bl_mixin._detect_carrier_from_words` 는 explicit 미지정 시 `""` 반환
  - `multi_template_registry.guess_carrier` 는 항상 `None` 반환
- 따라서 본 플러그인은 "키워드로 선사를 자동 매칭"하는 용도가 **아니다**.
  사용자가 UI 콤보박스에서 선택한 선사의 **파싱 힌트 저장소** 역할이다.

## YAML 스키마

```yaml
id: ZIM                              # 필수. CARRIER_OPTIONS 키와 일치해야 함
name: ZIM Integrated Shipping        # 표시용 이름

detect:                              # 보조 정보 (자동감지 X, 참고 데이터)
  keywords: [ZIM, ZIM INTEGRATED]    # 키워드 리스트
  pattern: 'ZIM\s+INTEGRATED'        # 선택 — Python 정규식 문자열
  file_prefixes: [ZIMU, ZIM]         # DO 파일명 접두사

bl:                                  # BL(선하증권) 파싱 규칙
  number_regex: '^ZIMU\w{7,10}$'     # BL No 추출/검증용 정규식
  format_hint: ZIMU1234567           # Gemini 프롬프트 예시
  page_scope: page0                  # page0 | page0_to_2 | all
  sap_page_hint: all                 # 선택
  bl_equals_booking_no: false        # Maersk 같은 특수 플래그

do:                                  # DO(화물인도지시서) 파싱 규칙
  number_regex: '^\d{9}$'

hints:                               # Gemini 프롬프트 힌트 (문서 종류별)
  bl:      "이 서류는 ZIM 선사의 Bill of Lading입니다"
  invoice: "이 서류는 ZIM 선사의 Invoice/FA입니다"
  packing: "이 서류는 ZIM 선사의 Packing List입니다"

containers:                          # 컨테이너 prefix 리스트
  - ZIMU
  - ZCSU
```

## 신규 선사 추가 절차

1. `profiles/<id>.yml` 파일을 작성 (위 스키마 참조).
2. `engine_modules/constants.py` 의 `CARRIER_OPTIONS` 리스트에도 해당 id 추가
   (UI 콤보박스 계약 때문에 이 1줄은 여전히 수정 필요).
3. 앱 재시작. 로그에 아래 2줄이 출력되면 성공:
   ```
   [CarrierProfile] 로드: ZIM (ZIM Integrated Shipping) ← zim.yml
   [CarrierRegistry] YAML 플러그인 병합 완료: N개 선사
   ```

## 기존 Python 템플릿과의 공존 규칙

| 상황 | 결과 |
|---|---|
| YAML 에만 있는 선사 | 신규 `CarrierTemplate` 로 `CARRIER_TEMPLATES` 에 추가 |
| Python 에만 있는 선사 | 기존 그대로 (변경 없음) |
| 양쪽에 모두 있는 선사 | **Python 우선** — Python 의 빈 필드만 YAML 값으로 보강 |
| YAML 이 파싱 실패 | 해당 파일만 skip, 나머지 정상 로드 |
| `pyyaml` 미설치 | 전체 YAML 레이어 no-op (앱 정상 부팅) |

즉, **"migrate to YAML" 은 선택적 리팩터이지 강제 교체가 아니다**.
검증된 MSC/MAERSK 는 Python 유지, 신규 선사만 YAML 로 시도하는 것을 권장한다.

## pyyaml 설치

```bash
pip install pyyaml
```

`pyyaml` 이 없어도 앱은 정상 동작한다 (YAML 레이어만 비활성). 설치를 강제하지 않는다.

## 파일 구조

```
features/ai/carrier_profiles/
  __init__.py                       # load_all_profiles / get_profile / merge_with_registry re-export
  carrier_profile_loader.py         # 로더 본체 (약 220줄)
  README.md                         # 이 문서
  profiles/
    msc.yml                         # 기존 Python 템플릿 역변환 (참고용)
    maersk.yml                      # 기존 Python 템플릿 역변환 (참고용)
    hmm.yml                         # 기존 Python 템플릿 역변환 (참고용)
    zim.yml                         # 신규 선사 예제 (Python 템플릿 없음)
```

## 공개 API

```python
from features.ai.carrier_profiles import (
    load_all_profiles,   # () -> Dict[str, dict]         — 전체 프로파일
    get_profile,         # (cid: str) -> Optional[dict]  — 단일 조회
    merge_with_registry, # (registry: dict) -> dict      — 병합
)
```

## 관련 문서

- `docs/track_b/track_b_report.md` — 본 POC 의 설계 배경 및 감사 보고서
