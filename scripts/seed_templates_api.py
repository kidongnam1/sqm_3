# -*- coding: utf-8 -*-
"""
scripts/seed_templates_api.py
==============================
실행 중인 SQM FastAPI 서버에 HTTP POST로 4개 선사 x 500/1000kg 템플릿을 등록.

사용법 (앱이 실행 중인 상태에서):
    python scripts/seed_templates_api.py

앱이 꺼져 있으면 먼저 실행.bat 으로 앱을 켜세요.
"""
import urllib.request
import urllib.error
import json
import sys

BASE_URL = "http://127.0.0.1:8765"

TEMPLATES = [
    {
        "template_name": "MAERSK — 리튬카보네이트 500 kg",
        "carrier_id":    "MAERSK",
        "bag_weight_kg": 500,
        "product_hint":  "리튬카보네이트 500kg/포대",
        "bl_format":     "MAEU7",
        "gemini_hint_packing":  "Maersk 패킹리스트: 포대수량, 순중량(kg), 총중량(kg) 추출. 포대당 500kg 기준.",
        "gemini_hint_invoice":  "Maersk Invoice: 품목명, 단가, 수량, 금액, Invoice No, 날짜 추출.",
        "gemini_hint_bl":       "【Maersk BL 전용】BL No: 1페이지 우상단 B/L No. (예: MAEU1234567). 컨테이너: XXXX0000000 형식.",
        "note": "", "lot_sqm": "", "mxbg_pallet": 0, "sap_no": ""
    },
    {
        "template_name": "MAERSK — 리튬카보네이트 1,000 kg",
        "carrier_id":    "MAERSK",
        "bag_weight_kg": 1000,
        "product_hint":  "리튬카보네이트 1000kg/포대",
        "bl_format":     "MAEU7",
        "gemini_hint_packing":  "Maersk 패킹리스트: 포대수량, 순중량(kg), 총중량(kg) 추출. 포대당 1000kg 기준.",
        "gemini_hint_invoice":  "Maersk Invoice: 품목명, 단가, 수량, 금액, Invoice No, 날짜 추출.",
        "gemini_hint_bl":       "【Maersk BL 전용】BL No: 1페이지 우상단 B/L No. (예: MAEU1234567). 컨테이너: XXXX0000000 형식.",
        "note": "", "lot_sqm": "", "mxbg_pallet": 0, "sap_no": ""
    },
    {
        "template_name": "MSC — 리튬카보네이트 500 kg",
        "carrier_id":    "MSC",
        "bag_weight_kg": 500,
        "product_hint":  "리튬카보네이트 500kg/포대",
        "bl_format":     "MSCU7",
        "gemini_hint_packing":  "MSC 패킹리스트: 포대수량, 순중량(kg), 총중량(kg) 추출. 포대당 500kg 기준.",
        "gemini_hint_invoice":  "MSC Invoice: 품목명, 단가, 수량, 금액, Invoice No, 날짜 추출.",
        "gemini_hint_bl":       "【MSC BL 전용】BL No: B/L No. 라벨 옆 (MSCU 또는 MEDU로 시작). SCAC: MSCU.",
        "note": "", "lot_sqm": "", "mxbg_pallet": 0, "sap_no": ""
    },
    {
        "template_name": "MSC — 리튬카보네이트 1,000 kg",
        "carrier_id":    "MSC",
        "bag_weight_kg": 1000,
        "product_hint":  "리튬카보네이트 1000kg/포대",
        "bl_format":     "MSCU7",
        "gemini_hint_packing":  "MSC 패킹리스트: 포대수량, 순중량(kg), 총중량(kg) 추출. 포대당 1000kg 기준.",
        "gemini_hint_invoice":  "MSC Invoice: 품목명, 단가, 수량, 금액, Invoice No, 날짜 추출.",
        "gemini_hint_bl":       "【MSC BL 전용】BL No: B/L No. 라벨 옆 (MSCU 또는 MEDU로 시작). SCAC: MSCU.",
        "note": "", "lot_sqm": "", "mxbg_pallet": 0, "sap_no": ""
    },
    {
        "template_name": "ONE — 리튬카보네이트 500 kg",
        "carrier_id":    "ONE",
        "bag_weight_kg": 500,
        "product_hint":  "리튬카보네이트 500kg/포대",
        "bl_format":     "ONEU7",
        "gemini_hint_packing":  "ONE 패킹리스트: 포대수량, 순중량(kg), 총중량(kg) 추출. 포대당 500kg 기준.",
        "gemini_hint_invoice":  "ONE Invoice: 품목명, 단가, 수량, 금액, Invoice No, 날짜 추출.",
        "gemini_hint_bl":       "【ONE BL 전용】BL No: B/L No. 라벨 옆 (ONEU로 시작, 예: ONEU1234567). SCAC: ONEY. OCEAN NETWORK EXPRESS 텍스트로 선사 확인.",
        "note": "", "lot_sqm": "", "mxbg_pallet": 0, "sap_no": ""
    },
    {
        "template_name": "ONE — 리튬카보네이트 1,000 kg",
        "carrier_id":    "ONE",
        "bag_weight_kg": 1000,
        "product_hint":  "리튬카보네이트 1000kg/포대",
        "bl_format":     "ONEU7",
        "gemini_hint_packing":  "ONE 패킹리스트: 포대수량, 순중량(kg), 총중량(kg) 추출. 포대당 1000kg 기준.",
        "gemini_hint_invoice":  "ONE Invoice: 품목명, 단가, 수량, 금액, Invoice No, 날짜 추출.",
        "gemini_hint_bl":       "【ONE BL 전용】BL No: B/L No. 라벨 옆 (ONEU로 시작, 예: ONEU1234567). SCAC: ONEY. OCEAN NETWORK EXPRESS 텍스트로 선사 확인.",
        "note": "", "lot_sqm": "", "mxbg_pallet": 0, "sap_no": ""
    },
    {
        "template_name": "HAPAG — 리튬카보네이트 500 kg",
        "carrier_id":    "HAPAG",
        "bag_weight_kg": 500,
        "product_hint":  "리튬카보네이트 500kg/포대",
        "bl_format":     "HLCU7",
        "gemini_hint_packing":  "Hapag-Lloyd 패킹리스트: 포대수량, 순중량(kg), 총중량(kg) 추출. 포대당 500kg 기준.",
        "gemini_hint_invoice":  "Hapag-Lloyd Invoice: 품목명, 단가, 수량, 금액, Invoice No, 날짜 추출.",
        "gemini_hint_bl":       "【Hapag-Lloyd BL 전용】BL No: B/L No. 라벨 옆 (HLCU로 시작, 예: HLCU1234567890). SCAC: HLCU. HAPAG-LLOYD 텍스트로 선사 확인.",
        "note": "", "lot_sqm": "", "mxbg_pallet": 0, "sap_no": ""
    },
    {
        "template_name": "HAPAG — 리튬카보네이트 1,000 kg",
        "carrier_id":    "HAPAG",
        "bag_weight_kg": 1000,
        "product_hint":  "리튬카보네이트 1000kg/포대",
        "bl_format":     "HLCU7",
        "gemini_hint_packing":  "Hapag-Lloyd 패킹리스트: 포대수량, 순중량(kg), 총중량(kg) 추출. 포대당 1000kg 기준.",
        "gemini_hint_invoice":  "Hapag-Lloyd Invoice: 품목명, 단가, 수량, 금액, Invoice No, 날짜 추출.",
        "gemini_hint_bl":       "【Hapag-Lloyd BL 전용】BL No: B/L No. 라벨 옆 (HLCU로 시작, 예: HLCU1234567890). SCAC: HLCU. HAPAG-LLOYD 텍스트로 선사 확인.",
        "note": "", "lot_sqm": "", "mxbg_pallet": 0, "sap_no": ""
    },
]

def api_call(method, path, body=None):
    url = BASE_URL + path
    data = json.dumps(body).encode("utf-8") if body else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return {"ok": False, "error": e.read().decode("utf-8")}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def main():
    print("=" * 50)
    print("SQM 입고 템플릿 등록 스크립트")
    print("=" * 50)

    # 1. 서버 연결 확인
    health = api_call("GET", "/api/health")
    if not health.get("ok") and "error" not in health:
        health = api_call("GET", "/api/dashboard/stats")
    print(f"서버 상태: {'✅ 연결됨' if health else '❌ 연결 실패'}")

    # 2. 기존 템플릿 목록 확인
    existing = api_call("GET", "/api/inbound/templates")
    exist_names = set()
    if existing.get("ok"):
        for t in existing.get("templates", []):
            exist_names.add(t.get("template_name", ""))
        print(f"기존 템플릿: {len(existing.get('templates', []))}개")

    # 3. 8개 템플릿 등록
    ok_count = 0
    skip_count = 0
    for t in TEMPLATES:
        if t["template_name"] in exist_names:
            print(f"  ⏭️  이미 존재: {t['template_name']}")
            skip_count += 1
            continue
        result = api_call("POST", "/api/inbound/templates", t)
        if result.get("ok"):
            print(f"  ✅ 등록: {t['template_name']}")
            ok_count += 1
        else:
            print(f"  ❌ 실패: {t['template_name']} — {result.get('error','?')}")

    print()
    print(f"완료: 신규 {ok_count}개 등록 / 기존 {skip_count}개 건너뜀")

    # 4. 최종 확인
    final = api_call("GET", "/api/inbound/templates")
    if final.get("ok"):
        rows = final.get("templates", [])
        print(f"\n현재 DB 템플릿 총 {len(rows)}개:")
        for r in rows:
            print(f"  🚢 {r.get('carrier_id','?'):8s} | {r.get('bag_weight_kg','?')}kg | {r.get('template_name','')}")

if __name__ == "__main__":
    main()
    input("\n아무 키나 누르면 종료...")
