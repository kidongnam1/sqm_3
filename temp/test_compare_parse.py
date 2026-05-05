# -*- coding: utf-8 -*-
"""직접 파싱 결과 vs API 파싱 결과 전 필드 비교"""
import sys, json, requests
sys.path.insert(0, r'd:\program\SQM_inventory\SQM_v866_CLEAN')

BL  = r'D:\program\SQM_inventory\SQM 4.13 입고\MAEU265083673 AN-MERSK\2200034449 BL.pdf'
FA  = r'D:\program\SQM_inventory\SQM 4.13 입고\MAEU265083673 AN-MERSK\2200034449 FA.pdf'
PL  = r'D:\program\SQM_inventory\SQM 4.13 입고\MAEU265083673 AN-MERSK\2200034449 PL.pdf'
DO  = r'D:\program\SQM_inventory\SQM 4.13 입고\MAEU265083673 AN-MERSK\MAEU265083673 DO.pdf'
API = "http://127.0.0.1:8767"

# ── 1. 직접 파싱 ─────────────────────────────────────────────
from parsers.document_parser_modular.parser import DocumentParser
p = DocumentParser()

bl_r   = p.parse_bl(BL, carrier_id='MAERSK')
pl_r   = p.parse_packing_list(PL, carrier_id='MAERSK')
inv_r  = p.parse_invoice(FA)
do_r   = p.parse_do(DO, carrier_id='MAERSK')

direct = {}

# BL 필드
if bl_r:
    direct.update({
        'bl_no':              bl_r.bl_no,
        'vessel':             bl_r.vessel,
        'voyage_no':          bl_r.voyage_no,
        'port_of_loading':    bl_r.port_of_loading,
        'port_of_discharge':  bl_r.port_of_discharge,
        'ship_date':          str(bl_r.ship_date or ''),
        'carrier_id':         bl_r.carrier_id,
        'shipper':            getattr(bl_r, 'shipper', ''),
        'consignee':          getattr(bl_r, 'consignee', ''),
    })

# PL 헤더 필드
if pl_r:
    direct.update({
        'product':            pl_r.product,
        'code':               pl_r.code,
        'vessel_pl':          pl_r.vessel,
        'folio':              pl_r.folio,
        'packing':            pl_r.packing,
        'customer':           pl_r.customer,
        'destination':        pl_r.destination,
        'sap_no':             pl_r.sap_no,
        'total_lots':         pl_r.total_lots,
        'total_mxbg':         pl_r.total_maxibag,
        'total_net_kg':       pl_r.total_net_weight_kg,
        'total_gross_kg':     pl_r.total_gross_weight_kg,
    })

# Invoice 필드
if inv_r:
    direct.update({
        'invoice_no':         inv_r.invoice_no,
        'invoice_sap_no':     inv_r.sap_no,
    })

# DO 필드
if do_r:
    direct.update({
        'arrival_date':       str(do_r.arrival_date or ''),
        'wh':                 getattr(do_r, 'warehouse_name', '') or getattr(do_r, 'warehouse', ''),
    })
    ft_infos = getattr(do_r, 'free_time_info', []) or []
    if ft_infos:
        ft = ft_infos[0]
        if isinstance(ft, dict):
            ftd = ft.get('free_time_date', '') or ft.get('free_time_until', '')
        else:
            ftd = getattr(ft, 'free_time_date', '') or getattr(ft, 'free_time_until', '')
        direct['con_return'] = str(ftd or '')
    else:
        direct['con_return'] = ''

# LOT 행 첫 번째
if pl_r and pl_r.lots:
    lot0 = pl_r.lots[0]
    direct.update({
        'lot0_lot_no':    lot0.lot_no,
        'lot0_container': lot0.container_no,
        'lot0_lot_sqm':   lot0.lot_sqm,
        'lot0_mxbg':      lot0.mxbg_pallet,
        'lot0_net_kg':    lot0.net_weight_kg,
        'lot0_gross_kg':  lot0.gross_weight_kg,
    })

# ── 2. API 파싱 ─────────────────────────────────────────────
with open(BL,'rb') as b, open(FA,'rb') as f, open(PL,'rb') as pl_f, open(DO,'rb') as d:
    files = {
        'bl':      ('BL.pdf',  b,    'application/pdf'),
        'invoice': ('FA.pdf',  f,    'application/pdf'),
        'pl':      ('PL.pdf',  pl_f, 'application/pdf'),
        'do_file': ('DO.pdf',  d,    'application/pdf'),
    }
    resp = requests.post(f"{API}/api/inbound/onestop-upload",
                         files=files,
                         data={'use_gemini':'false','dry_run':'true','template_id':'MAERSK_LC500'},
                         timeout=60)

api_data = resp.json().get('data', {})
api_rows = api_data.get('preview_rows', [])
r0 = api_rows[0] if api_rows else {}

api = {
    'bl_no':         r0.get('bl_no', ''),
    'ship_date':     r0.get('ship_date', ''),
    'arrival_date':  r0.get('arrival', ''),
    'con_return':    r0.get('con_return', ''),
    'product':       r0.get('product', ''),
    'code':          r0.get('code', ''),
    'sap_no':        r0.get('sap_no', ''),
    'invoice_no':    r0.get('invoice_no', ''),
    'lot0_lot_no':   r0.get('lot_no', ''),
    'lot0_container':r0.get('container', ''),
    'lot0_lot_sqm':  r0.get('lot_sqm', ''),
    'lot0_mxbg':     r0.get('mxbg', ''),
    'lot0_net_kg':   r0.get('net_kg', ''),
    'lot0_gross_kg': r0.get('gross_kg', ''),
    'total_rows':    len(api_rows),
}

# API에서 반환되지 않는 필드 (vessel, voyage 등)
api_extra = {
    'vessel':            api_data.get('vessel', '(API 미반환)'),
    'voyage_no':         api_data.get('voyage_no', '(API 미반환)'),
    'port_of_loading':   api_data.get('port_of_loading', '(API 미반환)'),
    'port_of_discharge': api_data.get('port_of_discharge', '(API 미반환)'),
    'carrier_id':        api_data.get('carrier_id', '(API 미반환)'),
}

# ── 3. 비교 출력 ─────────────────────────────────────────────
print("=" * 65)
print(f"{'필드':<20} {'직접파싱':>20}  {'API':>20}  결과")
print("=" * 65)

COMPARE_FIELDS = [
    ('bl_no',         'bl_no'),
    ('ship_date',     'ship_date'),
    ('arrival_date',  'arrival_date'),
    ('con_return',    'con_return'),
    ('product',       'product'),
    ('code',          'code'),
    ('sap_no',        'sap_no'),
    ('invoice_no',    'invoice_no'),
    ('lot0_lot_no',   'lot0_lot_no'),
    ('lot0_container','lot0_container'),
    ('lot0_lot_sqm',  'lot0_lot_sqm'),
    ('lot0_mxbg',     'lot0_mxbg'),
    ('lot0_net_kg',   'lot0_net_kg'),
    ('lot0_gross_kg', 'lot0_gross_kg'),
    ('total_lots',    'total_rows'),
]

mismatches = []
for dk, ak in COMPARE_FIELDS:
    dv = str(direct.get(dk, ''))
    av = str(api.get(ak, ''))
    ok = '✅' if dv == av else '❌ 불일치'
    if dv != av:
        mismatches.append((dk, dv, av))
    print(f"{dk:<20} {dv:>20}  {av:>20}  {ok}")

print()
print("── API에서 반환하지 않는 필드 (직접파싱에서만 추출) ──")
NOT_IN_API = ['vessel','voyage_no','port_of_loading','port_of_discharge','carrier_id',
              'shipper','folio','packing','customer','destination','vessel_pl',
              'total_mxbg','total_net_kg','total_gross_kg']
for f in NOT_IN_API:
    v = direct.get(f, '')
    if v:
        print(f"  {f:<20}: {v}")

print()
if mismatches:
    print(f"❌ 불일치 {len(mismatches)}건:")
    for dk, dv, av in mismatches:
        print(f"  {dk}: 직접='{dv}'  API='{av}'")
else:
    print("✅ 모든 공통 필드 일치")
