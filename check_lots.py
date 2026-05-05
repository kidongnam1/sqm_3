import sqlite3

path = r"D:\program\SQM_inventory\SQM_v866_CLEAN\data\db\sqm_inventory.db"
conn = sqlite3.connect(path)
cur = conn.cursor()

# inventory 컬럼 확인
cur.execute("PRAGMA table_info(inventory)")
cols = cur.fetchall()
print("=== inventory 컬럼 목록 ===")
for c in cols:
    print(f"  {c[1]:<25} {c[2]}")

# AVAILABLE 상태 행 수
cur.execute("SELECT COUNT(*) FROM inventory WHERE status='AVAILABLE'")
print(f"\nAVAILABLE 행수: {cur.fetchone()[0]}개")

# 실제 데이터 샘플 (컬럼명 자동 감지)
col_names = [c[1] for c in cols]
# lot_no, status, 수량관련, 제품관련 컬럼 찾기
qty_col = next((c for c in col_names if 'qty' in c.lower() or 'weight' in c.lower() or 'mt' in c.lower()), col_names[2])
prod_col = next((c for c in col_names if 'product' in c.lower() or 'code' in c.lower()), col_names[3])

print(f"\n사용할 컬럼: lot_no / status / {qty_col} / {prod_col}")

cur.execute(f"""
    SELECT lot_no, status, {qty_col}, {prod_col}
    FROM inventory
    WHERE status='AVAILABLE'
    ORDER BY lot_no
    LIMIT 30
""")
rows = cur.fetchall()
print(f"\nAVAILABLE LOT 목록 ({len(rows)}개):")
print(f"  {'LOT NO':<20} {'STATUS':<12} {qty_col:<12} {prod_col}")
print("  " + "-"*65)
for r in rows:
    print(f"  {str(r[0]):<20} {str(r[1]):<12} {str(r[2]):<12} {str(r[3] or '-')}")

conn.close()
