# tests/test_parser_regression.py
# SQM v8.6.5 - Parser Regression Test (4 Carriers x 4 Doc Types)
# 실행: pytest tests/test_parser_regression.py -v
# 기준: 2026-04-29 실측값 (Ruby)

import os, pytest, sys

ROOT    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURE = os.path.join(ROOT, 'tests', 'fixtures')
sys.path.insert(0, ROOT)

def _fx(n): return os.path.join(FIXTURE, n)
def _skip_if_missing(p):
    if not os.path.exists(p):
        pytest.skip(f'fixture 없음: {os.path.basename(p)}')

@pytest.fixture(scope='session')
def parser():
    from parsers.document_parser_modular import DocumentParser
    return DocumentParser()

def _check(result, expected, label):
    assert result is not None, f'[{label}] None 반환'
    errors = []
    for field, exp_val in expected.items():
        if field == 'container_count':
            c = getattr(result, 'containers', [])
            act = len(c) if c else 0
        elif field == 'containers':
            c = getattr(result, 'containers', [])
            act = [getattr(x, 'container_no', str(x)) for x in c]
        elif field == 'lot_count':
            lots = getattr(result, 'lots', None) or getattr(result, 'lot_numbers', [])
            act = len(lots) if lots else 0
        elif field == 'lot_numbers_first':
            ln = getattr(result, 'lot_numbers', [])
            act = ln[0] if ln else ''
        else:
            act = getattr(result, field, '__MISSING__')
            if hasattr(act, 'isoformat'): act = act.isoformat()
        if act != exp_val:
            errors.append(f'  {field}:\n    expected: {exp_val!r}\n    actual  : {act!r}')
    if errors:
        pytest.fail(f'\n[{label}] 불일치 {len(errors)}건:\n' + '\n'.join(errors))


# ================================================================== ONE
class TestONE:
    def test_do(self, parser):
        path = _fx('ONE_DO.pdf'); _skip_if_missing(path)
        r = parser.parse_do(path)
        _check(r, {
            'bl_no': 'ONEYSCLG01825300', 'vessel': 'HMM EMERALD',
            'voyage': '0012W', 'port_of_loading': 'CLPAG',
            'port_of_discharge': 'KRKAN', 'arrival_date': '2026-04-11',
            'gross_weight_kg': 102625.0, 'container_count': 5,
            'mrn': '26HDM UK026I', 'msn': '5019',
            'containers': ['FDCU0445465','NYKU4915247','TCLU6404353','TGBU4681720','TGCU5305383'],
        }, 'ONE_DO')

    def test_bl(self, parser):
        path = _fx('ONE_BL.pdf'); _skip_if_missing(path)
        r = parser.parse_bl(path)
        _check(r, {
            'bl_no': 'ONEYSCLG01825300', 'vessel': 'RIO DE JANEIRO EXPRESS',
            'voyage': '2601W', 'port_of_loading': 'PUERTO ANGAMOS, CHILE',
            'port_of_discharge': 'KWANGYANG', 'gross_weight_kg': 102625.0,
            'carrier_id': 'ONE',
        }, 'ONE_BL')

    def test_fa(self, parser):
        path = _fx('ONE_FA.pdf'); _skip_if_missing(path)
        r = parser.parse_invoice(path)
        _check(r, {
            'sap_no': '2200034590', 'invoice_no': '17653',
            'bl_no': 'ONEYSCLG01825300', 'quantity_mt': 100.02,
            'unit_price': 20154.0, 'total_amount': 2015803.08,
            'currency': 'USD', 'gross_weight_kg': 102625.0,
            'net_weight_kg': 100020.0, 'package_count': 200,
            'lot_count': 20, 'lot_numbers_first': '1126012309',
        }, 'ONE_FA')

    def test_pl(self, parser):
        path = _fx('ONE_PL.pdf'); _skip_if_missing(path)
        r = parser.parse_packing_list(path)
        _check(r, {
            'folio': '3807572', 'total_lots': 20,
            'total_net_weight_kg': 100020.0, 'total_gross_weight_kg': 102625.0,
            'total_maxibag': 200, 'container_count': 5,
            'containers': ['FDCU0445465','NYKU4915247','TCLU6404353','TGBU4681720','TGCU5305383'],
        }, 'ONE_PL')


# ================================================================== HAPAG
class TestHAPAG:
    def test_do(self, parser):
        path = _fx('HAPAG_DO.pdf'); _skip_if_missing(path)
        r = parser.parse_do(path)
        _check(r, {
            'do_no': '26041712Z7H6', 'bl_no': 'HLCUSCL260148627',
            'vessel': 'BUENAVENTURA EXPRESS', 'voyage': '2602W',
            'port_of_loading': 'CLPAG', 'port_of_discharge': 'KRPUS',
            'arrival_date': '2026-04-11', 'gross_weight_kg': 102625.0,
            'container_count': 5, 'mrn': '26HLCU9401I', 'msn': '6006',
            'containers': ['HAMU2050957','HAMU2354538','HAMU2410117','HAMU2655932','HAMU2723596'],
        }, 'HAPAG_DO')

    def test_bl(self, parser):
        path = _fx('HAPAG_BL.pdf'); _skip_if_missing(path)
        r = parser.parse_bl(path)
        _check(r, {
            'bl_no': 'HLCUSCL260148627', 'vessel': 'BUENAVENTURA EXPRESS',
            'voyage': '2602W', 'port_of_loading': 'PUERTO ANGAMOS, CHILE',
            'port_of_discharge': 'BUSAN, SOUTH KOREA',
            'gross_weight_kg': 102625.0, 'carrier_id': 'HAPAG',
        }, 'HAPAG_BL')

    def test_fa(self, parser):
        path = _fx('HAPAG_FA.pdf'); _skip_if_missing(path)
        r = parser.parse_invoice(path)
        _check(r, {
            'sap_no': '2200034659', 'invoice_no': '17760',
            'bl_no': 'HLCUSCL260148627', 'quantity_mt': 100.02,
            'unit_price': 17416.0, 'total_amount': 1741948.32,
            'currency': 'USD', 'gross_weight_kg': 102625.0,
            'net_weight_kg': 100020.0, 'package_count': 200,
            'lot_count': 20, 'lot_numbers_first': '1126021720',
        }, 'HAPAG_FA')

    def test_pl(self, parser):
        path = _fx('HAPAG_PL.pdf'); _skip_if_missing(path)
        r = parser.parse_packing_list(path)
        _check(r, {
            'folio': '3812291', 'total_lots': 20,
            'total_net_weight_kg': 100020.0, 'total_gross_weight_kg': 102625.0,
            'total_maxibag': 200, 'container_count': 5,
            'containers': ['HAMU2050957','HAMU2354538','HAMU2410117','HAMU2655932','HAMU2723596'],
        }, 'HAPAG_PL')


# ================================================================== MAERSK
class TestMAERSK:
    def test_do(self, parser):
        path = _fx('MAERSK_DO.pdf'); _skip_if_missing(path)
        r = parser.parse_do(path)
        _check(r, {
            'do_no': '249457239', 'bl_no': 'MAEU265083673',
            'vessel': 'GUNVOR MAERSK', 'voyage': '614E',
            'port_of_loading': 'CLMJS', 'port_of_discharge': 'KRKAN',
            'arrival_date': '2026-04-10', 'gross_weight_kg': 102625.0,
            'container_count': 5,
            'containers': ['GAOU7530868','MRSU5835586','MRSU5916543','MRSU8417023','TCLU4946885'],
        }, 'MAERSK_DO')

    def test_bl(self, parser):
        path = _fx('MAERSK_BL.pdf'); _skip_if_missing(path)
        r = parser.parse_bl(path)
        _check(r, {
            'bl_no': 'MAEU265083673', 'vessel': 'MAERSK SKARSTIND',
            'voyage': '607W', 'port_of_loading': 'Puerto Angamos, Chile',
            'port_of_discharge': 'GWANGYANG,SOUTH KOREA',
            'gross_weight_kg': 102625.0, 'total_containers': 5, 'carrier_id': 'MAERSK',
        }, 'MAERSK_BL')

    def test_fa(self, parser):
        path = _fx('MAERSK_FA.pdf'); _skip_if_missing(path)
        r = parser.parse_invoice(path)
        _check(r, {
            'sap_no': '2200034449', 'invoice_no': '17703',
            'bl_no': 'MAEU265083673', 'quantity_mt': 100.02,
            'unit_price': 19562.0, 'total_amount': 1956591.24,
            'currency': 'USD', 'gross_weight_kg': 102625.0,
            'net_weight_kg': 100020.0, 'package_count': 200,
            'lot_count': 20, 'lot_numbers_first': '1126013019',
        }, 'MAERSK_FA')

    def test_pl(self, parser):
        path = _fx('MAERSK_PL.pdf'); _skip_if_missing(path)
        r = parser.parse_packing_list(path)
        _check(r, {
            'folio': '3809458', 'total_lots': 20,
            'total_net_weight_kg': 100020.0, 'total_gross_weight_kg': 102625.0,
            'total_maxibag': 200, 'container_count': 5,
            'containers': ['GAOU7530868','MRSU5835586','MRSU5916543','MRSU8417023','TCLU4946885'],
        }, 'MAERSK_PL')


# ================================================================== MSC
class TestMSC:
    def test_do(self, parser):
        path = _fx('MSC_DO.pdf'); _skip_if_missing(path)
        r = parser.parse_do(path)
        _check(r, {
            'do_no': '26040210N0HU', 'bl_no': 'MEDUW9018104',
            'vessel': 'MSC APOLLINE', 'voyage': 'FY612A',
            'port_of_loading': 'CLPAG', 'port_of_discharge': 'KRKAN',
            'arrival_date': '2026-04-01', 'gross_weight_kg': 41050.0,
            'container_count': 2, 'mrn': '26MSCU3084I', 'msn': '0101',
            'containers': ['MSMU5531984','UETU6117887'],
        }, 'MSC_DO')

    def test_bl(self, parser):
        path = _fx('MSC_BL.pdf'); _skip_if_missing(path)
        r = parser.parse_bl(path)
        _check(r, {
            'bl_no': 'MEDUW9018104', 'vessel': 'MANZANILLO EXPRESS',
            'voyage': '2551W', 'port_of_loading': 'Puerto Angamos, Chile',
            'port_of_discharge': 'Gwangyang, Korea',
            'gross_weight_kg': 41050.0, 'carrier_id': 'MSC',
        }, 'MSC_BL')

    def test_fa(self, parser):
        path = _fx('MSC_FA.pdf'); _skip_if_missing(path)
        r = parser.parse_invoice(path)
        _check(r, {
            'sap_no': '2200034702', 'invoice_no': '17586',
            'bl_no': 'MEDUW9018104', 'quantity_mt': 40.008,
            'unit_price': 20646.0, 'total_amount': 826005.17,
            'currency': 'USD', 'gross_weight_kg': 41050.0,
            'net_weight_kg': 40008.0, 'package_count': 80,
            'lot_count': 8, 'lot_numbers_first': '1126012313',
        }, 'MSC_FA')

    def test_pl(self, parser):
        path = _fx('MSC_PL.pdf'); _skip_if_missing(path)
        r = parser.parse_packing_list(path)
        _check(r, {
            'folio': '3806579', 'total_lots': 8,
            'total_net_weight_kg': 40008.0, 'total_gross_weight_kg': 41050.0,
            'total_maxibag': 80, 'container_count': 2,
            'containers': ['MSMU5531984','UETU6117887'],
        }, 'MSC_PL')
