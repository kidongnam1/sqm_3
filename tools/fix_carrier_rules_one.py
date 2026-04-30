# -*- coding: utf-8 -*-
"""
carrier_rules ONE BL 패턴 수정 스크립트 (v8.6.6 bugfix)
────────────────────────────────────────────────────────
실제 ONE Sea Waybill 번호는 ONEY 접두사 (예: ONEYSCLG01825300)
기존 DB에 ONEU 패턴이 잘못 등록되어 있어 수정.

실행: python tools/fix_carrier_rules_one.py
"""
import sqlite3
import sys
import os

# 프로젝트 루트 기준 DB 경로
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

try:
    from config import DB_PATH
except ImportError:
    DB_PATH = os.path.join(ROOT, "data", "db", "sqm_inventory.db")

print(f"DB 경로: {DB_PATH}")

try:
    con = sqlite3.connect(str(DB_PATH), timeout=15)
    con.execute("PRAGMA journal_mode=WAL")

    # ① 테이블 없으면 먼저 생성
    con.execute("""
        CREATE TABLE IF NOT EXISTS carrier_rules (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            carrier_id   TEXT NOT NULL,
            doc_type     TEXT NOT NULL DEFAULT 'BL',
            rule_name    TEXT NOT NULL,
            pattern      TEXT NOT NULL,
            description  TEXT DEFAULT '',
            sample_value TEXT DEFAULT '',
            is_active    INTEGER DEFAULT 1,
            created_at   TEXT DEFAULT (datetime('now')),
            updated_at   TEXT DEFAULT (datetime('now'))
        )
    """)
    con.commit()
    print("carrier_rules 테이블 확인/생성 완료")

    # ② 5개 선사 기본 규칙 INSERT (이미 있으면 무시)
    default_rules = [
        ('MAERSK', 'BL', 'BL_NO_MAIN',  r'MAEU\d{9}',          'Maersk BL (MAEU+숫자9자리)',         'MAEU263764814'),
        ('MSC',    'BL', 'BL_NO_MSCU',  r'MSCU[A-Z0-9]{6,10}', 'MSC BL MSCU 형식',                  'MSCU1234567'),
        ('MSC',    'BL', 'BL_NO_MEDU',  r'MEDU[A-Z0-9]{6,10}', 'MSC Sea Waybill MEDU 형식',         'MEDUFP963988'),
        ('ONE',    'BL', 'BL_NO_MAIN',  r'ONEY[A-Z0-9]{8,15}', 'ONE Sea Waybill ONEY 형식',         'ONEYSCLG01825300'),
        ('HAPAG',  'BL', 'BL_NO_MAIN',  r'HLCU[A-Z0-9]{6,15}', 'Hapag-Lloyd BL HLCU 형식',          'HLCUSCL260148627'),
    ]
    con.executemany("""
        INSERT OR IGNORE INTO carrier_rules
            (carrier_id, doc_type, rule_name, pattern, description, sample_value)
        VALUES (?,?,?,?,?,?)
    """, default_rules)
    con.commit()

    # ③ ONE BL 패턴 강제 수정 (ONEU → ONEY)
    con.execute("""
        UPDATE carrier_rules
        SET pattern      = 'ONEY[A-Z0-9]{8,15}',
            description  = 'ONE Sea Waybill ONEY 형식 (ONEYSCLG01825300)',
            sample_value = 'ONEYSCLG01825300',
            updated_at   = datetime('now')
        WHERE carrier_id = 'ONE' AND doc_type = 'BL' AND rule_name = 'BL_NO_MAIN'
    """)
    con.commit()

    # ④ 최종 확인
    rows = con.execute(
        "SELECT carrier_id, doc_type, rule_name, pattern, sample_value "
        "FROM carrier_rules ORDER BY carrier_id, doc_type"
    ).fetchall()
    print("\n[carrier_rules 전체]")
    for r in rows:
        print(f"  {r[0]:8} {r[1]:3} {r[2]:15} {r[3]:30} → {r[4]}")

    con.close()
    print("\n완료: carrier_rules 테이블 생성 + ONE BL 패턴 ONEY 등록 완료")

except sqlite3.OperationalError as e:
    print(f"\n오류: {e}")
    print("앱이 실행 중이면 종료 후 다시 실행해 주세요.")
    sys.exit(1)
