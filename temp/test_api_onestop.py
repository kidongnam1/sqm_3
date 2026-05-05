# -*- coding: utf-8 -*-
"""FastAPI /api/inbound/onestop 엔드포인트로 실제 HTTP 파싱 테스트"""
import requests
import json

API = "http://127.0.0.1:8767"

def test_onestop(label, bl_path, fa_path, pl_path, do_path, carrier_id, template_id=None):
    print(f"\n{'='*50}")
    print(f"=== {label} ===")
    print(f"{'='*50}")

    files = {}
    open_files = []
    try:
        if pl_path:
            f = open(pl_path, 'rb')
            open_files.append(f)
            files['pl'] = (pl_path.split('\\')[-1], f, 'application/pdf')
        if bl_path:
            f = open(bl_path, 'rb')
            open_files.append(f)
            files['bl'] = (bl_path.split('\\')[-1], f, 'application/pdf')
        if fa_path:
            f = open(fa_path, 'rb')
            open_files.append(f)
            files['invoice'] = (fa_path.split('\\')[-1], f, 'application/pdf')
        if do_path:
            f = open(do_path, 'rb')
            open_files.append(f)
            files['do_file'] = (do_path.split('\\')[-1], f, 'application/pdf')

        data = {'use_gemini': 'false', 'dry_run': 'true'}
        if template_id:
            data['template_id'] = template_id

        resp = requests.post(f"{API}/api/inbound/onestop-upload", files=files, data=data, timeout=60)

        if resp.status_code == 200:
            result = resp.json()
            rows = result.get('data', {}).get('preview_rows', [])
            print(f"  상태     : OK ({len(rows)}행)")
            if rows:
                r0 = rows[0]
                print(f"  LOT No   : {r0.get('lot_no')}")
                print(f"  SAP No   : {r0.get('sap_no')}")
                print(f"  BL No    : {r0.get('bl_no')}")
                print(f"  PRODUCT  : {r0.get('product')}")
                print(f"  CODE     : {r0.get('code')}")
                print(f"  Ship Date: {r0.get('ship_date')}")
                print(f"  Arrival  : {r0.get('arrival')}")
                print(f"  CON Ret  : {r0.get('con_return')}")
                print(f"  FREE TIME: {r0.get('free_time')}")
                print(f"  MXBG     : {r0.get('mxbg')}")
                print(f"  전체 LOT : {[r.get('lot_no') for r in rows[:3]]} ...")
        else:
            print(f"  ERROR {resp.status_code}: {resp.text[:300]}")
    finally:
        for f in open_files:
            f.close()


# MAERSK
test_onestop(
    "MAERSK",
    bl_path=r'D:\program\SQM_inventory\SQM 4.13 입고\MAEU265083673 AN-MERSK\2200034449 BL.pdf',
    fa_path=r'D:\program\SQM_inventory\SQM 4.13 입고\MAEU265083673 AN-MERSK\2200034449 FA.pdf',
    pl_path=r'D:\program\SQM_inventory\SQM 4.13 입고\MAEU265083673 AN-MERSK\2200034449 PL.pdf',
    do_path=r'D:\program\SQM_inventory\SQM 4.13 입고\MAEU265083673 AN-MERSK\MAEU265083673 DO.pdf',
    carrier_id='MAERSK',
    template_id='MAERSK_LC500',
)

# MSC
test_onestop(
    "MSC",
    bl_path=r'D:\program\SQM_inventory\SQM 4.13 입고\MEDUW9018104 ANㅡmsc\2200034702 BL.pdf',
    fa_path=r'D:\program\SQM_inventory\SQM 4.13 입고\MEDUW9018104 ANㅡmsc\2200034702 FA.PDF',
    pl_path=r'D:\program\SQM_inventory\SQM 4.13 입고\MEDUW9018104 ANㅡmsc\2200034702_PackingList1.pdf',
    do_path=r'D:\program\SQM_inventory\SQM 4.13 입고\MEDUW9018104 ANㅡmsc\MEDUW9018104 DO.pdf',
    carrier_id='MSC',
    template_id='MSC_LC500',
)

# HAPAG
test_onestop(
    "HAPAG",
    bl_path=r'D:\program\SQM_inventory\SQM 4.13 입고\hapag\2200034659 BL.pdf',
    fa_path=r'D:\program\SQM_inventory\SQM 4.13 입고\hapag\2200034659 FA.pdf',
    pl_path=r'D:\program\SQM_inventory\SQM 4.13 입고\hapag\2200034659 PL.pdf',
    do_path=r'D:\program\SQM_inventory\SQM 4.13 입고\hapag\HLCUSCL260148627 DO.pdf',
    carrier_id='HAPAG',
    template_id='HAPAG_LC500',
)
