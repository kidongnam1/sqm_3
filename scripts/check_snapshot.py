import sqlite3
db = sqlite3.connect(r'd:\program\SQM_inventory\SQM_v866_CLEAN\data\db\sqm_inventory.db')
tables = [t[0] for t in db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
for t in ['inventory_snapshot', 'inventory', 'stock_movement']:
    if t in tables:
        cnt = db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(f"{t}: {cnt}건")
    else:
        print(f"{t}: 테이블 없음")
db.close()
