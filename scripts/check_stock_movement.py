import sqlite3
db = sqlite3.connect(r'd:\program\SQM_inventory\SQM_v866_CLEAN\data\db\sqm_inventory.db')
rows = db.execute("SELECT * FROM stock_movement ORDER BY rowid DESC LIMIT 10").fetchall()
desc = db.execute("PRAGMA table_info(stock_movement)").fetchall()
cols = [d[1] for d in desc]
print("stock_movement columns:", cols)
print()
for r in rows:
    d = dict(zip(cols, r))
    print(d)
db.close()
