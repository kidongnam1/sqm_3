import sqlite3
db = sqlite3.connect(r'd:\program\SQM_inventory\SQM_v866_CLEAN\data\db\sqm_inventory.db')
tables = [t[0] for t in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()]
print("Tables:", tables)
if 'audit_log' in tables:
    cnt = db.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
    print(f"audit_log rows: {cnt}")
    if cnt > 0:
        rows = db.execute("SELECT * FROM audit_log ORDER BY rowid DESC LIMIT 5").fetchall()
        cols = [d[0] for d in db.execute("SELECT * FROM audit_log LIMIT 0").description or []]
        print("Columns:", cols)
        for r in rows:
            print(" ", dict(zip(cols, r)) if cols else r)
else:
    print("audit_log table does NOT exist!")
db.close()
