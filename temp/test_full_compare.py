# -*- coding: utf-8 -*-
"""직접 파싱 결과 vs API data 전체 필드 비교"""
import sys, requests
sys.path.insert(0, r'd:\program\SQM_inventory\SQM_v866_CLEAN')

BL  = r'D:\program\SQM_inventory\SQM 4.13 입고\MAEU265083673 AN-MERSK\2200034449 BL.pdf'
FA  = r'D:\program\SQM_inventory\SQM 4.13 입고\MAEU265083673 AN-MERSK\2200034449 FA.pdf'
PL  = r'D:\program\SQM_inventory\SQM 4.13 입고\MAEU265083673 AN-MERSK\2200034449 PL.pdf'
DO  = r'D:\program\SQM_inventory\SQM 4.13 입고\MAEU265083673 AN-MERSK\MAEU265083673 DO.pdf'
API = "http://127.0.0.1:8769"

# ── 1. 직접 파싱 ────────────────────────────────────────────────
from parsers.document_parser_modular.parser import DocumentParser
p = DocumentParser()
bl_r  = p.parse_bl(BL, carrier_id='MAERSK')
pl_r  = p.parse_packing_list(PL, carrier_id='MAERSK')
inv_r = p.parse_invoice(FA)
do_r  = p.parse_do(DO, carrier_id='MAERSK')

ft_infos = getattr(do_r, 'free_time_info', []) or []
ft0 = ft_infos[0] if ft_infos else None
con_return_direct = str(getattr(ft0,'free_time_date','') or '') if ft0 else ''

DIRECT = {
    # BL
    'BL / bl_no':            bl_r.bl_no,
    'BL / vessel':           bl_r.vessel,
    'BL / voyage':           bl_r.voyage,
    'BL / port_of_loading':  bl_r.port_of_loading,
    'BL / port_of_discharge':bl_r.port_of_discharge,
    'BL / ship_date':        str(bl_r.ship_date or ''),
    'BL / shipper':          getattr(bl_r,'shipper_name','') or '',
    'BL / consignee':        getattr(bl_r,'consignee_name','') or '',
    'BL / gross_weight_kg':  str(bl_r.gross_weight_kg or ''),
    'BL / carrier_id':       bl_r.carrier_id,
    # Invoice
    'INV / sap_no':          inv_r.sap_no,
    'INV / invoice_no':      inv_r.invoice_no,
    'INV / product_name':    inv_r.product_name,
    'INV / product_code':    inv_r.product_code,
    'INV / quantity_mt':     str(inv_r.quantity_mt or ''),
    'INV / unit_price':      str(inv_r.unit_price or ''),
    'INV / total_amount':    str(inv_r.total_amount or ''),
    'INV / currency':        inv_r.currency,
    'INV / net_weight_kg':   str(inv_r.net_weight_kg or ''),
    'INV / gross_weight_kg': str(inv_r.gross_weight_kg or ''),
    'INV / package_count':   str(inv_r.package_count or ''),
    'INV / package_type':    getattr(inv_r,'package_type','') or '',
    'INV / incoterm':        getattr(inv_r,'incoterm','') or '',
    'INV / origin':          getattr(inv_r,'origin','') or '',
    'INV / destination':     getattr(inv_r,'destination','') or '',
    'INV / customer_name':   getattr(inv_r,'customer_name','') or '',
    # DO
    'DO / do_no':            str(getattr(do_r,'do_no','') or ''),
    'DO / bl_no':            getattr(do_r,'bl_no','') or '',
    'DO / vessel':           getattr(do_r,'vessel','') or '',
    'DO / voyage':           getattr(do_r,'voyage','') or '',
    'DO / arrival_date':     str(do_r.arrival_date or ''),
    'DO / issue_date':       str(getattr(do_r,'issue_date','') or ''),
    'DO / con_return':       con_return_direct,
    'DO / mrn':              getattr(do_r,'mrn','') or '',
    'DO / cbm':              str(getattr(do_r,'cbm','') or ''),
    # PL 헤더
    'PL / product':          pl_r.product,
    'PL / code':             pl_r.code,
    'PL / folio':            pl_r.folio,
    'PL / packing':          pl_r.packing,
    'PL / vessel':           pl_r.vessel,
    'PL / customer':         pl_r.customer,
    'PL / destination':      pl_r.destination,
    'PL / sap_no':           pl_r.sap_no,
    'PL / total_lots':       str(pl_r.total_lots),
    'PL / total_maxibag':    str(pl_r.total_maxibag),
    'PL / total_net_kg':     str(pl_r.total_net_weight_kg),
    'PL / total_gross_kg':   str(pl_r.total_gross_weight_kg),
}

# ── 2. API 파싱 ────────────────────────────────────────────────
with open(BL,'rb') as b, open(FA,'rb') as f, open(PL,'rb') as pl_f, open(DO,'rb') as d:
    resp = requests.post(f"{API}/api/inbound/onestop-upload",
        files={'bl':('BL.pdf',b,'application/pdf'),'invoice':('FA.pdf',f,'application/pdf'),
               'pl':('PL.pdf',pl_f,'application/pdf'),'do_file':('DO.pdf',d,'application/pdf')},
        data={'use_gemini':'false','dry_run':'true','template_id':'MAERSK_LC500'}, timeout=60)

data = resp.json().get('data', {})
r0   = (data.get('preview_rows') or [{}])[0]
bd   = data.get('bl_detail', {})
id_  = data.get('invoice_detail', {})
dd   = data.get('do_detail', {})
pd_  = data.get('pl_detail', {})

API_MAP = {
    'BL / bl_no':            data.get('bl_no',''),
    'BL / vessel':           bd.get('vessel',''),
    'BL / voyage':           bd.get('voyage',''),
    'BL / port_of_loading':  bd.get('port_of_loading',''),
    'BL / port_of_discharge':bd.get('port_of_discharge',''),
    'BL / ship_date':        r0.get('ship_date',''),
    'BL / shipper':          bd.get('shipper',''),
    'BL / consignee':        bd.get('consignee',''),
    'BL / gross_weight_kg':  str(bd.get('gross_weight_kg','') or ''),
    'BL / carrier_id':       bd.get('carrier_id',''),
    'INV / sap_no':          r0.get('sap_no',''),
    'INV / invoice_no':      r0.get('invoice_no',''),
    'INV / product_name':    id_.get('product_name',''),
    'INV / product_code':    id_.get('product_code',''),
    'INV / quantity_mt':     str(id_.get('quantity_mt','') or ''),
    'INV / unit_price':      str(id_.get('unit_price','') or ''),
    'INV / total_amount':    str(id_.get('total_amount','') or ''),
    'INV / currency':        id_.get('currency',''),
    'INV / net_weight_kg':   str(id_.get('net_weight_kg','') or ''),
    'INV / gross_weight_kg': str(id_.get('gross_weight_kg','') or ''),
    'INV / package_count':   str(id_.get('package_count','') or ''),
    'INV / package_type':    id_.get('package_type',''),
    'INV / incoterm':        id_.get('incoterm',''),
    'INV / origin':          id_.get('origin',''),
    'INV / destination':     id_.get('destination',''),
    'INV / customer_name':   id_.get('customer_name',''),
    'DO / do_no':            dd.get('do_no',''),
    'DO / bl_no':            dd.get('bl_no',''),
    'DO / vessel':           dd.get('vessel',''),
    'DO / voyage':           dd.get('voyage',''),
    'DO / arrival_date':     dd.get('arrival_date',''),
    'DO / issue_date':       dd.get('issue_date',''),
    'DO / con_return':       dd.get('con_return',''),
    'DO / mrn':              dd.get('mrn',''),
    'DO / cbm':              str(dd.get('cbm','') or ''),
    'PL / product':          pd_.get('product',''),
    'PL / code':             pd_.get('code',''),
    'PL / folio':            pd_.get('folio',''),
    'PL / packing':          pd_.get('packing',''),
    'PL / vessel':           pd_.get('vessel',''),
    'PL / customer':         pd_.get('customer',''),
    'PL / destination':      pd_.get('destination',''),
    'PL / sap_no':           pd_.get('sap_no',''),
    'PL / total_lots':       str(pd_.get('total_lots','') or ''),
    'PL / total_maxibag':    str(pd_.get('total_maxibag','') or ''),
    'PL / total_net_kg':     str(pd_.get('total_net_kg','') or ''),
    'PL / total_gross_kg':   str(pd_.get('total_gross_kg','') or ''),
}

# ── 3. 비교 출력 ────────────────────────────────────────────────
print(f"{'필드':<30} {'직접파싱':>30}  {'API':>30}  결과")
print("-" * 100)
mismatches = []
for key in DIRECT:
    dv = str(DIRECT.get(key, ''))
    av = str(API_MAP.get(key, ''))
    ok = 'OK' if dv == av else '*** 불일치 ***'
    if dv != av:
        mismatches.append((key, dv, av))
    print(f"{key:<30} {dv[:30]:>30}  {av[:30]:>30}  {ok}")

print()
print("=" * 100)
if mismatches:
    print(f"불일치 {len(mismatches)}건:")
    for k, dv, av in mismatches:
        print(f"  [{k}]")
        print(f"    직접: {dv}")
        print(f"    API : {av}")
else:
    print("모든 필드 일치")
