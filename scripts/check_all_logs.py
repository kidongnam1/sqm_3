import sqlite3
db = sqlite3.connect(r'd:\program\SQM_inventory\SQM_v866_CLEAN\data\db\sqm_inventory.db')
log_tables = ['audit_log', 'stock_movement', 'parsing_log', 'tonbag_move_log', 'return_history', 'outbound_scan']
for t in log_tables:
    try:
        cnt = db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        cols = [d[0] for d in db.execute(f"PRAGMA table_info({t})").fetchall()]
        print(f"{t}: {cnt}건  cols={cols}")
    except Exception as e:
        print(f"{t}: ERROR - {e}")
db.close()
