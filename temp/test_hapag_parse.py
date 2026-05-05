# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, r'd:\program\SQM_inventory\SQM_v866_CLEAN')

BL  = r'D:\program\SQM_inventory\SQM 4.13 입고\hapag\2200034659 BL.pdf'
FA  = r'D:\program\SQM_inventory\SQM 4.13 입고\hapag\2200034659 FA.pdf'
PL  = r'D:\program\SQM_inventory\SQM 4.13 입고\hapag\2200034659 PL.pdf'
DO  = r'D:\program\SQM_inventory\SQM 4.13 입고\hapag\HLCUSCL260148627 DO.pdf'

from parsers.document_parser_modular.parser import DocumentParser
p = DocumentParser()

print('=== BL 파싱 ===')
bl = p.parse_bl(BL, carrier_id='HAPAG')
if bl:
    print(f'  BL No     : {bl.bl_no}')
    print(f'  Vessel    : {bl.vessel}')
    print(f'  Ship Date : {bl.ship_date}')
    print(f'  Carrier   : {bl.carrier_id}')
else:
    print('  FAIL')

print()
print('=== PL 파싱 ===')
pl = p.parse_packing_list(PL, carrier_id='HAPAG')
if pl:
    print(f'  Product   : {pl.product}')
    print(f'  Code      : {pl.code}')
    print(f'  LOT 수    : {len(pl.lots)}')
    print(f'  LOT 목록  : {[r.lot_no for r in pl.lots[:3]]}')
else:
    print('  FAIL')

print()
print('=== Invoice(FA) 파싱 ===')
inv = p.parse_invoice(FA)
if inv:
    print(f'  Invoice No: {inv.invoice_no}')
    print(f'  SAP No    : {inv.sap_no}')
else:
    print('  FAIL')

print()
print('=== D/O 파싱 ===')
do = p.parse_do(DO, carrier_id='HAPAG')
if do:
    print(f'  Arrival   : {do.arrival_date}')
    ft_infos = getattr(do, 'free_time_info', []) or []
    if ft_infos:
        ft = ft_infos[0]
        if isinstance(ft, dict):
            ftd = ft.get('free_time_date', '') or ft.get('free_time_until', '')
        else:
            ftd = getattr(ft, 'free_time_date', '') or getattr(ft, 'free_time_until', '')
        print(f'  CON Return: {ftd}')
    else:
        print(f'  CON Return: (없음)')
    wh = getattr(do, 'warehouse_name', '') or getattr(do, 'warehouse', '')
    print(f'  Warehouse : {wh}')
    print(f'  Success   : {do.success}')
else:
    print('  FAIL')
