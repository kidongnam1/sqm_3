# -*- coding: utf-8 -*-
"""MSC 직접 파싱 결과 vs API 전 필드 비교"""
import sys, requests
sys.path.insert(0, r'd:\program\SQM_inventory\SQM_v866_CLEAN')

BASE = r'D:\program\SQM_inventory\SQM 4.13 입고\MEDUW9018104 ANㅡmsc'
BL  = f'{BASE}\\2200034702 BL.pdf'
FA  = f'{BASE}\\2200034702 FA.PDF'
PL  = f'{BASE}\\2200034702_PackingList1.pdf'
DO  = f'{BASE}\\MEDUW9018104 DO.pdf'
API = "http://127.0.0.1:8769"

from parsers.document_parser_modular.parser import DocumentParser
p = DocumentParser()
bl_r  = p.parse_bl(BL, carrier_id='MSC')
pl_r  = p.parse_packing_list(PL, carrier_id='MSC')
inv_r = p.parse_invoice(FA)
do_r  = p.parse_do(DO, carrier_id='MSC')

ft_infos = getattr(do_r, 'free_time_info', []) or []
ft0 = ft_infos[0] if ft_infos else None
con_return_direct = str(getattr(ft0,'free_time_date','') or '') if ft0 else ''

DIRECT = {
    'BL / bl_no':            getattr(bl_r,'bl_no','') or '',
    'BL / vessel':           getattr(bl_r,'vessel','') or '',
    'BL / voyage':           getattr(bl_r,'voyage','') or '',
    'BL / port_of_loading':  getattr(bl_r,'port_of_loading','') or '',
    'BL / port_of_discharge':getattr(bl_r,'port_of_discharge','') or '',
    'BL / ship_date':        str(getattr(bl_r,'ship_date','') or ''),
    'BL / shipper':          getattr(bl_r,'shipper_name','') or '',
    'BL / consignee':        getattr(bl_r,'consignee_name','') or '',
    'BL / gross_weight_kg':  str(getattr(bl_r,'gross_weight_kg','') or ''),
    'BL / carrier_id':       getattr(bl_r,'carrier_id','') or '',
    'INV / sap_no':          str(getattr(inv_r,'sap_no','') or ''),
    'INV / invoice_no':      str(getattr(inv_r,'invoice_no','') or ''),
    'INV / product_name':    getattr(inv_r,'product_name','') or '',
    'INV / product_code':    getattr(inv_r,'product_code','') or '',
    'INV / quantity_mt':     str(getattr(inv_r,'quantity_mt','') or ''),
    'INV / currency':        getattr(inv_r,'currency','') or '',
    'INV / net_weight_kg':   str(getattr(inv_r,'net_weight_kg','') or ''),
    'INV / gross_weight_kg': str(getattr(inv_r,'gross_weight_kg','') or ''),
    'INV / incoterm':        getattr(inv_r,'incoterm','') or '',
    'DO / do_no':            str(getattr(do_r,'do_no','') or ''),
    'DO / bl_no':            getattr(do_r,'bl_no','') or '',
    'DO / arrival_date':     str(getattr(do_r,'arrival_date','') or ''),
    'DO / con_return':       con_return_direct,
    'PL / product':          getattr(pl_r,'product','') or '',
    'PL / code':             getattr(pl_r,'code','') or '',
    'PL / vessel':           getattr(pl_r,'vessel','') or '',
    'PL / total_lots':       str(getattr(pl_r,'total_lots','') or ''),
}

with open(BL,'rb') as b, open(FA,'rb') as f, open(PL,'rb') as pl_f, open(DO,'rb') as d:
    resp = requests.post(f"{API}/api/inbound/onestop-upload",
        files={'bl':('BL.pdf',b,'application/pdf'),'invoice':('FA.pdf',f,'application/pdf'),
               'pl':('PL.pdf',pl_f,'application/pdf'),'do_file':('DO.pdf',d,'application/pdf')},
        data={'use_gemini':'false','dry_run':'true','template_id':'MSC_LC500'}, timeout=60)

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
    'INV / currency':        id_.get('currency',''),
    'INV / net_weight_kg':   str(id_.get('net_weight_kg','') or ''),
    'INV / gross_weight_kg': str(id_.get('gross_weight_kg','') or ''),
    'INV / incoterm':        id_.get('incoterm',''),
    'DO / do_no':            dd.get('do_no',''),
    'DO / bl_no':            dd.get('bl_no',''),
    'DO / arrival_date':     dd.get('arrival_date',''),
    'DO / con_return':       dd.get('con_return',''),
    'PL / product':          pd_.get('product',''),
    'PL / code':             pd_.get('code',''),
    'PL / vessel':           pd_.get('vessel',''),
    'PL / total_lots':       str(pd_.get('total_lots','') or ''),
}

print(f"{'필드':<30} {'직접파싱':>30}  {'API':>30}  결과")
print("-" * 100)
mismatches = []
for key in DIRECT:
    dv = str(DIRECT.get(key, ''))
    av = str(API_MAP.get(key, ''))
    ok = 'OK' if dv == av else '*** 불일치 ***'
    if dv != av: mismatches.append((key, dv, av))
    print(f"{key:<30} {dv[:30]:>30}  {av[:30]:>30}  {ok}")

print()
print("=" * 80)
if mismatches:
    print(f"불일치 {len(mismatches)}건:")
    for k, dv, av in mismatches:
        print(f"  [{k}]  직접={dv!r}  API={av!r}")
else:
    print("모든 필드 일치")
