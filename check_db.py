import sqlite3

db = 'data/db/sqm_inventory.db'
conn = sqlite3.connect(db)
cur = conn.cursor()

print('=== [1] inventory - LOT별 current_weight 합계 ===')
cur.execute('SELECT status, COUNT(*) as lots, ROUND(SUM(current_weight),3) as total_mt FROM inventory GROUP BY status')
for r in cur.fetchall():
    print(r)

print()
print('=== [2] inventory_tonbag - 상태별 weight 합계 ===')
cur.execute('SELECT status, COUNT(*) as bags, ROUND(SUM(weight),3) as total_mt FROM inventory_tonbag GROUP BY status')
for r in cur.fetchall():
    print(r)

print()
print('=== [3] AVAILABLE LOT 중 tonbag 없는 LOT ===')
cur.execute('''
SELECT i.lot_no, i.current_weight
FROM inventory i
WHERE i.status='AVAILABLE'
AND NOT EXISTS (SELECT 1 FROM inventory_tonbag t WHERE t.lot_no=i.lot_no)
LIMIT 10
''')
rows = cur.fetchall()
print('tonbag 없는 LOT 수:', len(rows))
for r in rows[:5]:
    print(' ', r)

print()
print('=== [4] 불일치 LOT - inventory weight vs tonbag weight 합 ===')
cur.execute('''
SELECT i.lot_no, i.current_weight as inv_wt,
       ROUND(COALESCE(SUM(t.weight),0),3) as bag_sum_wt,
       ROUND(i.current_weight - COALESCE(SUM(t.weight),0),3) as diff
FROM inventory i
LEFT JOIN inventory_tonbag t ON i.lot_no=t.lot_no
GROUP BY i.lot_no
HAVING ABS(diff) > 0.5
LIMIT 15
''')
rows = cur.fetchall()
print('불일치 LOT 수:', len(rows))
for r in rows:
    print(' ', r)

conn.close()
print()
print('Done.')
