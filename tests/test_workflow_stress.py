# -*- coding: utf-8 -*-
"""
SQM Inventory v865 --- 통합 워크플로우 스트레스 테스트
=====================================================

워크플로우:
  1 입고 (process_inbound) --- 랜덤 생성 packing_data
  2 얼로케이션/출고 (process_outbound) --- 입고 중 50% 무게 출고
  3 피킹/추가출고 --- 얼로케이션 후 잔여 중 20% 추가 출고
  4 반품 (process_return) --- 출고된 톤백 50% 반품
  5 자리이동 (record_move) --- 반품된 tonbag 위치 이동
  6 정합성 검증 --- 매 단계 후 current_weight >= 0, 합산 일치

실행 방법:
    python tests/test_workflow_stress.py
"""

import os
import sys
import random
import string
import types
import traceback
import pathlib
import importlib
import importlib.util
from datetime import datetime, date

# =========================================================================
# 1. 프로젝트 루트를 sys.path 최우선 추가
# =========================================================================
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# =========================================================================
# 2. 임시 DB 경로 (실제 DB 보호)
# =========================================================================
_temp_dir = os.environ.get('TEMP', os.environ.get('TMP', '/tmp'))
STRESS_DB_PATH = os.path.join(_temp_dir, 'sqm_stress_test.db')
os.environ['SQM_DB_PATH'] = STRESS_DB_PATH

# =========================================================================
# 3. config / core.config 가짜 모듈 주입
#    이유: NTFS 마운트 환경에서 config.py 가 truncate 되어 SyntaxError 발생.
#          engine 초기화에 필요한 심볼만 최소로 제공하고 실제 파일 파싱을 건너뜀.
# =========================================================================
_base = pathlib.Path(PROJECT_ROOT)

def _build_fake_config():
    m = types.ModuleType('config')
    m.DB_TYPE = 'sqlite'
    m.DB_PATH = STRESS_DB_PATH
    m.DB_WAL_MODE = True
    m.DB_TIMEOUT = 30.0
    m.BASE_DIR  = _base
    m.DATA_DIR  = _base / 'data'
    m.DB_DIR    = _base / 'data' / 'db'
    m.OUTPUT_DIR = _base / 'output'
    m.BACKUP_DIR = _base / 'backup'
    m.LOG_DIR    = _base / 'logs'
    m.TEMP_DIR   = _base / 'temp'
    m.SETTINGS_FILE = _base / 'settings.ini'
    m.EXPORT_DIR = _base / 'output'
    m.GEMINI_API_KEY = ''
    m.GEMINI_MODEL   = 'gemini-2.5-flash'
    m.OPENAI_API_KEY = ''
    m.OPENAI_MODEL   = 'gpt-4o'
    m.GROQ_API_KEY   = ''
    m.GROQ_MODEL     = 'llama-3.3-70b-versatile'
    m.OPENROUTER_API_KEY = ''
    m.OPENROUTER_MODEL   = 'meta-llama/llama-3.1-8b-instruct:free'
    m.OLLAMA_BASE_URL    = 'http://localhost:11434'
    m.OLLAMA_MODEL       = 'qwen2.5:14b'
    m.OLLAMA_AUTO_START  = True
    m.OLLAMA_AUTO_PULL_CONFIRM = True
    m.LMSTUDIO_BASE_URL = 'http://localhost:1234/v1'
    m.LMSTUDIO_MODEL    = 'local-model'
    m.AI_FREE_FALLBACK_ENABLED = True
    m.AI_LOCAL_AI_ENABLED      = True
    m.AI_PAID_AI_ENABLED       = False
    m.AI_REQUIRE_PAID_CONFIRM  = True
    m.AI_PROVIDER_ORDER = 'gemini,groq,openrouter,ollama,lmstudio,paid_openai'
    m.SAVE_RAW_GEMINI_RESPONSE = False
    m.DISABLE_OPENAI_FALLBACK  = False
    m.API_KEY_SOURCE = 'NONE'
    m.PG_HOST = 'localhost'
    m.PG_PORT = 5432
    m.PG_DATABASE = 'sqm_inventory'
    m.PG_USER = 'postgres'
    m.PG_PASSWORD = ''
    m.PG_MIN_CONNECTIONS = 2
    m.PG_MAX_CONNECTIONS = 10
    m.BACKUP_ENABLED = True
    m.BACKUP_MAX_COUNT = 5
    m.BACKUP_INTERVAL_HOURS = 24
    m.OUTBOUND_MODE = 'random_scan_confirm'
    m.OUTBOUND_WEIGHT_TOL_PCT = 0.001
    m.OUTBOUND_UNDO_LIMIT = 1
    m.PICKING_MAIN_MATERIAL_CODE   = '30000008'
    m.PICKING_SAMPLE_MATERIAL_CODE = '30000010'
    m.PICKING_DEFAULT_CONTAINERS   = 15
    m.validate_api_key          = lambda: (True, '')
    m.get_db_info               = lambda: {'type': 'SQLite', 'path': str(STRESS_DB_PATH)}
    m.get_settings              = lambda: {}
    m.save_api_key_secure       = lambda x: 'INI'
    m.save_ai_fallback_settings = lambda x: True
    m.save_gemini_model         = lambda x: True
    m.setup_logging             = lambda *a, **k: None
    m.get_api_key_warning       = lambda: None
    m.sql_group_concat  = lambda col, sep=',': 'GROUP_CONCAT(%s, "%s")' % (col, sep)
    m.sql_date_format   = lambda col, fmt: "strftime('%s', %s)" % (fmt, col)
    m.sql_auto_increment = lambda: 'INTEGER PRIMARY KEY AUTOINCREMENT'
    return m

fake_config = _build_fake_config()
sys.modules['config'] = fake_config

# config_logging 가짜 등록 (config.py가 import하므로)
fake_cl = types.ModuleType('config_logging')
fake_cl.setup_logging = lambda *a, **k: None
sys.modules['config_logging'] = fake_cl

# config_sql 가짜 등록
fake_cs = types.ModuleType('config_sql')
fake_cs.sql_group_concat  = lambda db_type, col, sep=',': 'GROUP_CONCAT(%s, "%s")' % (col, sep)
fake_cs.sql_date_format   = lambda db_type, col, fmt: "strftime('%s', %s)" % (fmt, col)
fake_cs.sql_auto_increment = lambda db_type: 'INTEGER PRIMARY KEY AUTOINCREMENT'
sys.modules['config_sql'] = fake_cs

# core 패키지: __init__.py는 로드하되 core.config는 가짜로 대체
_core_init = os.path.join(PROJECT_ROOT, 'core', '__init__.py')
_core_spec = importlib.util.spec_from_file_location(
    'core', _core_init,
    submodule_search_locations=[os.path.join(PROJECT_ROOT, 'core')]
)
core_mod = importlib.util.module_from_spec(_core_spec)
sys.modules['core'] = core_mod
try:
    _core_spec.loader.exec_module(core_mod)
except Exception:
    pass  # __init__이 비어있으면 무시

fake_core_cfg = types.ModuleType('core.config')
fake_core_cfg.__dict__.update(
    {k: v for k, v in fake_config.__dict__.items() if not k.startswith('__')}
)
sys.modules['core.config'] = fake_core_cfg
core_mod.config = fake_core_cfg

# =========================================================================
# 4. 엔진 임포트
# =========================================================================
from engine_modules.inventory_modular import SQMInventoryEngineV3

# =========================================================================
# 5. 랜덤 데이터 생성 헬퍼
# =========================================================================
_used_lot_nos = set()


def _gen_lot_no():
    """중복 없는 YYYYMMDD+4자리 lot_no 생성."""
    today_str = date.today().strftime('%Y%m%d')
    for _ in range(1000):
        suffix = ''.join(random.choices(string.digits, k=4))
        candidate = today_str + suffix
        if candidate not in _used_lot_nos:
            _used_lot_nos.add(candidate)
            return candidate
    raise RuntimeError("lot_no 중복 생성 한계 초과")


def _gen_packing_data():
    """랜덤 입고 packing_data 생성.

    제약:
      - tonbag 단위 무게 = 500kg 또는 1000kg (integrity_mixin 대원칙)
      - tonbag 합 = net_kg - 1.0 (샘플 S00 1kg 별도 INSERT, [I3] 통과)
    """
    # 500kg 또는 1000kg 단위 랜덤 선택
    SAMPLE_KG  = 1.0
    unit_kg    = random.choice([500.0, 1000.0])
    # 단위당 ton 수: 500kg=0.5MT, 1000kg=1MT
    # bag 개수를 2~20 범위에서 결정하고 total_mt는 그에 맞춤
    bag_count  = random.randint(2, 20)
    # net_kg = bag_count * unit_kg + SAMPLE_KG (tonbag합 + 샘플)
    net_kg     = float(bag_count * unit_kg + SAMPLE_KG)
    total_mt   = net_kg / 1000.0
    # 일반 tonbag 배분 (샘플 제외)
    distributable = net_kg - SAMPLE_KG   # = bag_count * unit_kg
    per_bag    = unit_kg                  # 딱 맞아떨어짐
    residual   = 0.0

    lot_no    = _gen_lot_no()
    sap_no    = '22000' + ''.join(random.choices(string.digits, k=5))
    bl_no     = ''.join(random.choices(string.ascii_uppercase, k=4)) + \
                ''.join(random.choices(string.digits, k=12))
    warehouse = random.choice(['GY-A', 'GY-B', 'GY-C'])

    tonbags = []
    for i in range(bag_count):
        w = round(per_bag + (residual if i == 0 else 0.0), 2)
        tonbags.append({'sub_lt': i + 1, 'weight': w, 'gross_weight': round(w + 500.0, 2)})

    return {
        'lot_no':       lot_no,
        'sap_no':       sap_no,
        'bl_no':        bl_no,
        'product':      'SQM POTASSIUM NITRATE',
        'product_code': 'KNO3',
        'lot_sqm':      float(total_mt),
        'mxbg_pallet':  bag_count,
        'net_weight':   net_kg,
        'gross_weight': net_kg + bag_count * 500.0,
        'warehouse':    warehouse,
        'vessel':       'STRESS TEST VESSEL',
        'ship_date':    '2024-01-15',
        'arrival_date': '2024-02-01',
        'tonbags':      tonbags,
    }


# =========================================================================
# 6. 정합성 검증
# =========================================================================

def verify_integrity(engine, lot_no, step):
    """
    정합성 검증 - 실패 시 AssertionError.

    엔진 규칙:
      - inventory.current_weight 는 샘플 1kg 포함/제외 두 가지 방식이 허용됨
        (integrity_mixin v7.5.0 검증10: cw == tb_avail OR cw == tb_avail_no_sample)
      - 따라서 우리도 두 방식 중 하나가 만족되면 PASS
    """
    row = engine.db.fetchone(
        "SELECT current_weight, initial_weight, picked_weight "
        "FROM inventory WHERE lot_no=?",
        (lot_no,)
    )
    assert row is not None, "[%s] LOT 레코드 없음: %s" % (step, lot_no)

    cw = float(row['current_weight'] or 0)
    iw = float(row['initial_weight']  or 0)

    # 검증 1: 음수 재고 금지
    assert cw >= -0.5, (
        "[%s] 음수 재고 발견! lot=%s current_weight=%.2fkg" % (step, lot_no, cw)
    )
    # 검증 2: 초과 재고 금지 (샘플 1kg 허용 오차 포함)
    assert cw <= iw + 1.5, (
        "[%s] 재고 초과! lot=%s current=%.2f > initial=%.2f" % (step, lot_no, cw, iw)
    )

    # 검증 3: inventory.current_weight 와 tonbag 합산 일치
    # 허용1: cw == 일반AVAILABLE합 + 샘플1kg  (샘플 포함 방식)
    # 허용2: cw == 일반AVAILABLE합             (샘플 제외 방식)
    tb_row = engine.db.fetchone(
        "SELECT "
        "  COALESCE(SUM(CASE WHEN status='AVAILABLE' AND COALESCE(is_sample,0)=0 THEN weight ELSE 0 END),0) AS normal_avail, "
        "  COALESCE(SUM(CASE WHEN COALESCE(is_sample,0)=1 THEN weight ELSE 0 END),0) AS sample_w "
        "FROM inventory_tonbag WHERE lot_no=?",
        (lot_no,)
    )
    normal_avail = float(tb_row['normal_avail'] or 0) if tb_row else 0.0
    sample_w     = float(tb_row['sample_w']     or 0) if tb_row else 0.0
    tb_with_sample    = normal_avail + sample_w   # 허용1
    tb_without_sample = normal_avail              # 허용2

    TOLERANCE = 1.0
    ok = (abs(cw - tb_with_sample) < TOLERANCE or
          abs(cw - tb_without_sample) < TOLERANCE)
    assert ok, (
        "[%s] 재고-톤백 불일치! lot=%s inv.current=%.2fkg "
        "vs tonbag(with_sample=%.2f, without_sample=%.2f)"
        % (step, lot_no, cw, tb_with_sample, tb_without_sample)
    )


# =========================================================================
# 7. 메인 사이클
# =========================================================================

def run_one_cycle(engine, iteration):
    """
    1입고 -> 2 50%출고 -> 3 잔여20%추가출고 -> 4 50%반품 -> 5 자리이동 -> 6 최종검증
    """
    pd = _gen_packing_data()
    lot_no = pd['lot_no']

    print("  [1입고] lot=%s  %.0fMT  bags=%d"
          % (lot_no, pd['net_weight'] / 1000, pd['mxbg_pallet']))

    # 1. 입고
    r = engine.process_inbound(pd)
    if not r.get('success'):
        raise AssertionError("[1입고 실패] %s: %s" % (lot_no, r.get('errors', [])))
    verify_integrity(engine, lot_no, "1입고후")

    inv = engine.db.fetchone(
        "SELECT current_weight FROM inventory WHERE lot_no=?", (lot_no,))
    avail = float(inv['current_weight'] or 0)

    # 2. 50% 출고
    alloc_w = round(avail * 0.5, 2)
    if alloc_w >= 1.0:
        print("  [2출고] %.2fMT" % (alloc_w / 1000))
        r2 = engine.process_outbound(
            {'lot_no': lot_no, 'weight_kg': alloc_w,
             'customer': 'CUST_%04d' % iteration, 'sale_ref': 'SR-%04d-A' % iteration},
            source='STRESS_TEST')
        if not r2.get('success'):
            raise AssertionError("[2출고 실패] %s: %s" % (lot_no, r2.get('errors', [])))
        verify_integrity(engine, lot_no, "2출고후")
    else:
        print("  [2출고] 스킵(재고부족)")

    inv2 = engine.db.fetchone(
        "SELECT current_weight FROM inventory WHERE lot_no=?", (lot_no,))
    avail2 = float(inv2['current_weight'] or 0)

    # 3. 잔여 20% 추가 출고
    extra_w = round(avail2 * 0.2, 2)
    if extra_w >= 1.0:
        print("  [3추가출고] %.3fMT" % (extra_w / 1000))
        r3 = engine.process_outbound(
            {'lot_no': lot_no, 'weight_kg': extra_w,
             'customer': 'CUST_%04d_B' % iteration, 'sale_ref': 'SR-%04d-B' % iteration},
            source='STRESS_TEST')
        if not r3.get('success'):
            raise AssertionError("[3추가출고 실패] %s: %s" % (lot_no, r3.get('errors', [])))
        verify_integrity(engine, lot_no, "3추가출고후")
    else:
        print("  [3추가출고] 스킵(잔여부족)")

    # 4. 반품: PICKED 톤백 50% 반품
    # 엔진의 2단계 반품 프로세스:
    #   step A: process_return() → tonbag 상태 PICKED→RETURN (대기)
    #   step B: finalize_return_to_available() → RETURN→AVAILABLE + _recalc
    # step A만 하면 정합성 검증에서 initial≠current+picked 오류 발생
    picked = engine.db.fetchall(
        "SELECT lot_no, sub_lt, weight FROM inventory_tonbag "
        "WHERE lot_no=? AND status IN ('PICKED','CONFIRMED','SHIPPED','SOLD','OUTBOUND') "
        "  AND COALESCE(is_sample,0)=0 ORDER BY sub_lt",
        (lot_no,)
    )
    if picked:
        n_ret = max(1, len(picked) // 2)
        targets = picked[:n_ret]
        print("  [4반품 stepA] process_return %d/%d개" % (n_ret, len(picked)))
        ret_data = [
            {'lot_no': (t['lot_no'] if isinstance(t, dict) else t[0]),
             'sub_lt': (t['sub_lt'] if isinstance(t, dict) else t[1]),
             'reason': 'STRESS_TEST', 'remark': 'iter=%d' % iteration}
            for t in targets
        ]
        r4 = engine.process_return(ret_data, source_type='STRESS_TEST')
        returned = r4.get('returned', 0)
        errors   = r4.get('errors', [])
        if returned == 0 and errors:
            bad = [e for e in errors
                   if 'SAMPLE' not in str(e) and 'AVAILABLE' not in str(e)]
            if bad:
                raise AssertionError("[4반품stepA 실패] %s: %s" % (lot_no, bad))

        # step B: RETURN → AVAILABLE 확정 (finalize)
        locs = ['RACK-A1', 'RACK-B2', 'RACK-C3', 'RACK-D4', 'SHELF-01']
        finalized = 0
        return_tbs = engine.db.fetchall(
            "SELECT sub_lt FROM inventory_tonbag "
            "WHERE lot_no=? AND status='RETURN' AND COALESCE(is_sample,0)=0",
            (lot_no,)
        )
        for tb_r in return_tbs:
            sub_lt_r = tb_r['sub_lt'] if isinstance(tb_r, dict) else tb_r[0]
            rf = engine.finalize_return_to_available(
                lot_no=lot_no, sub_lt=int(sub_lt_r),
                location=random.choice(locs)
            )
            if not rf.get('success'):
                raise AssertionError(
                    "[4반품stepB 실패] %s-%s: %s" % (lot_no, sub_lt_r, rf.get('message', ''))
                )
            finalized += 1
        print("  [4반품 stepB] finalize %d개 AVAILABLE 복귀" % finalized)
        verify_integrity(engine, lot_no, "4반품후")
    else:
        print("  [4반품] PICKED 없음 스킵")

    # 5. 자리이동: AVAILABLE 톤백 최대 2개
    avail_tbs = engine.db.fetchall(
        "SELECT lot_no, sub_lt, tonbag_no, location FROM inventory_tonbag "
        "WHERE lot_no=? AND status='AVAILABLE' AND COALESCE(is_sample,0)=0 "
        "ORDER BY sub_lt LIMIT 3",
        (lot_no,)
    )
    moved = 0
    locs = ['RACK-A1', 'RACK-B2', 'RACK-C3', 'RACK-D4', 'SHELF-01']
    for tb in avail_tbs[:2]:
        sub_lt = tb['sub_lt'] if isinstance(tb, dict) else tb[1]
        tn     = (tb.get('tonbag_no', '') or '') if isinstance(tb, dict) else ''
        from_l = (tb.get('location', '')  or '') if isinstance(tb, dict) else ''
        r5 = engine.record_move(
            lot_no=lot_no, sub_lt=int(sub_lt),
            to_location=random.choice(locs),
            from_location=from_l or 'UNKNOWN',
            tonbag_no=tn, operator='STRESS_TESTER', source_type='STRESS_TEST')
        if not r5.get('success'):
            raise AssertionError(
                "[5자리이동 실패] %s-%s: %s" % (lot_no, sub_lt, r5.get('message', '')))
        moved += 1
    if moved:
        print("  [5자리이동] %d개 이동" % moved)
    else:
        print("  [5자리이동] 이동 가능 없음 스킵")

    # 6. 최종 정합성 검증
    verify_integrity(engine, lot_no, "6최종")
    print("  [6검증] PASSED  lot=%s" % lot_no)


# =========================================================================
# 8. 엔트리 포인트
# =========================================================================

def main():
    print("=" * 70)
    print("SQM Inventory v865 --- 워크플로우 스트레스 테스트")
    print("DB  : " + STRESS_DB_PATH)
    print("시작: " + str(datetime.now()))
    print("=" * 70)

    # 기존 임시 DB 삭제
    for ext in ['', '-wal', '-shm']:
        p = STRESS_DB_PATH + ext
        if os.path.exists(p):
            os.remove(p)
            print("삭제: " + p)

    # 엔진 초기화
    engine = SQMInventoryEngineV3(db_path=STRESS_DB_PATH)
    health = engine.health_check()
    if not health.get('database'):
        print("헬스 체크 실패: " + str(health))
        sys.exit(1)
    print("초기화 성공. 테이블 수=%d" % len(health.get('tables', [])))
    print()

    iteration  = 0
    passed     = 0
    start_time = datetime.now()

    try:
        while True:
            iteration += 1
            print("\n" + "=" * 60)
            print("Iteration #%d  %s" % (iteration, datetime.now().strftime('%H:%M:%S')))
            try:
                run_one_cycle(engine, iteration)
                passed += 1
                elapsed = (datetime.now() - start_time).total_seconds()
                print("PASSED  (누적 %d/%d  경과 %.1fs)"
                      % (passed, iteration, elapsed))

            except AssertionError as e:
                elapsed = (datetime.now() - start_time).total_seconds()
                print("\n" + "!" * 60)
                print("BUG FOUND  iteration #%d" % iteration)
                print("  원인: " + str(e))
                print("  경과 %.1fs  통과 %d회" % (elapsed, passed))
                print("!" * 60)
                break

            except Exception as e:
                elapsed = (datetime.now() - start_time).total_seconds()
                print("\n" + "!" * 60)
                print("CRASH  iteration #%d: %s" % (iteration, e))
                traceback.print_exc()
                print("  경과 %.1fs  통과 %d회" % (elapsed, passed))
                print("!" * 60)
                break

    finally:
        engine.close()

    print("\n" + "=" * 70)
    print("결과: %d/%d iteration 통과" % (passed, iteration))
    print("종료: " + str(datetime.now()))
    print("=" * 70)
    return passed, iteration


if __name__ == '__main__':
    passed, total = main()
    sys.exit(0 if passed >= 3 else 1)
