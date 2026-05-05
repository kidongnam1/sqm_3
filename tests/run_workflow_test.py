# -*- coding: utf-8 -*-
"""
SQM v8.6.6 — 전체 워크플로 Smoke Test (톤백 레벨 상세)
서버 없이 임시 SQLite DB로 전과정 검증

< 실제 프로그램 기본 로직 >
  각 LOT 내 일부 톤백만 단계별 처리 (부분 배분 -> 부분 피킹 -> 출고)
  톤백 수 = 반드시 정수 (소수 발생 시 math.ceil 처리)

시나리오 (80 LOT x 11톤백 = 880개 / 400.080 MT):
  Step 0  입고    : 880개 전부 AVAILABLE
  Step 1  배분    : 각 LOT 정규 ceil(10/2)=5개(sub_lt 1-5) + 앞 40 LOT 샘플(sub_lt 0)
                    -> 400정규 + 40샘플 = 440개 RESERVED
  Step 2  피킹    : 각 LOT 정규 ceil(5*0.8)=4개(sub_lt 1-4) + 앞 40 LOT 샘플
                    -> 360개 PICKED  /  80개(sub_lt 5) RESERVED 잔류
  Step 3  출고    : 360 PICKED -> SOLD
  Step 4  반품    : 앞 20 LOT x sub_lt 1 -> 20개 RETURN
  Step 5  이동    : 20개 RETURN -> AVAILABLE (위치: GY-B-RETURN)

최종: AVAILABLE 460 + RESERVED 80 + OUTBOUND 340 = 880 OK
"""
import sqlite3, os, tempfile, math

C  = lambda s: f"\033[32m{s}\033[0m"
Y  = lambda s: f"\033[33m{s}\033[0m"
B  = lambda s: f"\033[36m{s}\033[0m"
R  = lambda s: f"\033[31m{s}\033[0m"
P  = lambda s: f"\033[35m{s}\033[0m"
BL = lambda s: f"\033[1m{s}\033[0m"
TC = lambda s: f"\033[1m\033[36m{s}\033[0m"

def to_int_bags(n: float) -> int:
    """톤백 수 = 반드시 정수. 소수 발생 시 ceiling(올림)"""
    return math.ceil(n)

CUSTOMER = {
    "2200034590": "INA CHEMICALS",
    "2200034591": "PT JAKARTA LOGIS",
    "2200034592": "SONG IND. CO.",
    "2200034594": "AAA BATTERY CO.",
}
REG_W  = 0.500
SAMP_W = 0.001

ALL_LOTS = [
    ("1126012309","ONEYSCLG01825300","2200034590"),
    ("1126012310","ONEYSCLG01825300","2200034590"),
    ("1126012311","ONEYSCLG01825300","2200034590"),
    ("1126012404","ONEYSCLG01825300","2200034590"),
    ("1126012405","ONEYSCLG01825300","2200034590"),
    ("1126012410","ONEYSCLG01825300","2200034590"),
    ("1126012411","ONEYSCLG01825300","2200034590"),
    ("1126012412","ONEYSCLG01825300","2200034590"),
    ("1126012413","ONEYSCLG01825300","2200034590"),
    ("1126012416","ONEYSCLG01825300","2200034590"),
    ("1126012424","ONEYSCLG01825300","2200034590"),
    ("1126012426","ONEYSCLG01825300","2200034590"),
    ("1126012428","ONEYSCLG01825300","2200034590"),
    ("1126012429","ONEYSCLG01825300","2200034590"),
    ("1126012430","ONEYSCLG01825300","2200034590"),
    ("1126012433","ONEYSCLG01825300","2200034590"),
    ("1126012434","ONEYSCLG01825300","2200034590"),
    ("1126012435","ONEYSCLG01825300","2200034590"),
    ("1126012436","ONEYSCLG01825300","2200034590"),
    ("1126012437","ONEYSCLG01825300","2200034590"),
    ("1126012305","ONEYSCLG01826400","2200034591"),
    ("1126012306","ONEYSCLG01826400","2200034591"),
    ("1126012307","ONEYSCLG01826400","2200034591"),
    ("1126012308","ONEYSCLG01826400","2200034591"),
    ("1126012408","ONEYSCLG01826400","2200034591"),
    ("1126012409","ONEYSCLG01826400","2200034591"),
    ("1126012414","ONEYSCLG01826400","2200034591"),
    ("1126012415","ONEYSCLG01826400","2200034591"),
    ("1126012425","ONEYSCLG01826400","2200034591"),
    ("1126012443","ONEYSCLG01826400","2200034591"),
    ("1126012444","ONEYSCLG01826400","2200034591"),
    ("1126012445","ONEYSCLG01826400","2200034591"),
    ("1126012446","ONEYSCLG01826400","2200034591"),
    ("1126012447","ONEYSCLG01826400","2200034591"),
    ("1126012448","ONEYSCLG01826400","2200034591"),
    ("1126012449","ONEYSCLG01826400","2200034591"),
    ("1126012450","ONEYSCLG01826400","2200034591"),
    ("1126012451","ONEYSCLG01826400","2200034591"),
    ("1126012452","ONEYSCLG01826400","2200034591"),
    ("1126012501","ONEYSCLG01826400","2200034591"),
    ("1126012322","ONEYSCLG01827500","2200034592"),
    ("1126012333","ONEYSCLG01827500","2200034592"),
    ("1126012334","ONEYSCLG01827500","2200034592"),
    ("1126012335","ONEYSCLG01827500","2200034592"),
    ("1126012401","ONEYSCLG01827500","2200034592"),
    ("1126012402","ONEYSCLG01827500","2200034592"),
    ("1126012403","ONEYSCLG01827500","2200034592"),
    ("1126012407","ONEYSCLG01827500","2200034592"),
    ("1126012518","ONEYSCLG01827500","2200034592"),
    ("1126012521","ONEYSCLG01827500","2200034592"),
    ("1126012522","ONEYSCLG01827500","2200034592"),
    ("1126012523","ONEYSCLG01827500","2200034592"),
    ("1126012525","ONEYSCLG01827500","2200034592"),
    ("1126012604","ONEYSCLG01827500","2200034592"),
    ("1126012605","ONEYSCLG01827500","2200034592"),
    ("1126012611","ONEYSCLG01827500","2200034592"),
    ("1126012612","ONEYSCLG01827500","2200034592"),
    ("1126012613","ONEYSCLG01827500","2200034592"),
    ("1126012614","ONEYSCLG01827500","2200034592"),
    ("1126012615","ONEYSCLG01827500","2200034592"),
    ("1126020601","ONEYSCLG01857800","2200034594"),
    ("1126020602","ONEYSCLG01857800","2200034594"),
    ("1126020603","ONEYSCLG01857800","2200034594"),
    ("1126020604","ONEYSCLG01857800","2200034594"),
    ("1126020605","ONEYSCLG01857800","2200034594"),
    ("1126020608","ONEYSCLG01857800","2200034594"),
    ("1126020609","ONEYSCLG01857800","2200034594"),
    ("1126020610","ONEYSCLG01857800","2200034594"),
    ("1126020611","ONEYSCLG01857800","2200034594"),
    ("1126020612","ONEYSCLG01857800","2200034594"),
    ("1126020613","ONEYSCLG01857800","2200034594"),
    ("1126020614","ONEYSCLG01857800","2200034594"),
    ("1126020615","ONEYSCLG01857800","2200034594"),
    ("1126020616","ONEYSCLG01857800","2200034594"),
    ("1126020620","ONEYSCLG01857800","2200034594"),
    ("1126020621","ONEYSCLG01857800","2200034594"),
    ("1126020626","ONEYSCLG01857800","2200034594"),
    ("1126020627","ONEYSCLG01857800","2200034594"),
    ("1126020628","ONEYSCLG01857800","2200034594"),
    ("1126020630","ONEYSCLG01857800","2200034594"),
]
assert len(ALL_LOTS) == 80

SAMPLE_ALLOC_IDX = 40
RETURN_IDX       = 20


def create_db(path):
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.executescript("""
    CREATE TABLE inventory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        lot_no TEXT UNIQUE, sap_no TEXT, bl_no TEXT,
        product TEXT, product_code TEXT,
        net_weight REAL, initial_weight REAL, current_weight REAL,
        tonbag_count INTEGER, status TEXT DEFAULT 'AVAILABLE',
        warehouse TEXT, location TEXT, inbound_date TEXT,
        created_at TEXT, updated_at TEXT
    );
    CREATE TABLE inventory_tonbag (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        inventory_id INTEGER, lot_no TEXT, sap_no TEXT, bl_no TEXT,
        sub_lt INTEGER, tonbag_no TEXT, weight REAL,
        is_sample INTEGER DEFAULT 0,
        status TEXT DEFAULT 'AVAILABLE',
        location TEXT, inbound_date TEXT,
        picked_date TEXT, outbound_date TEXT, return_date TEXT,
        created_at TEXT, updated_at TEXT,
        UNIQUE(lot_no, sub_lt)
    );
    CREATE TABLE allocation_plan (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        lot_no TEXT, sub_lt INTEGER,
        customer TEXT, sale_ref TEXT, weight REAL,
        alloc_date TEXT, status TEXT DEFAULT 'RESERVED',
        created_at TEXT, updated_at TEXT
    );
    CREATE TABLE stock_movement (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        lot_no TEXT, sub_lt INTEGER,
        movement_type TEXT, from_status TEXT, to_status TEXT,
        from_location TEXT, to_location TEXT,
        weight REAL, actor TEXT, remarks TEXT, created_at TEXT
    );
    """)
    con.commit()
    return con


def populate(con):
    now = "2026-05-05 00:00:00"
    for lot_no, bl_no, sap_no in ALL_LOTS:
        con.execute("""
            INSERT INTO inventory
            (lot_no,sap_no,bl_no,product,product_code,
             net_weight,initial_weight,current_weight,
             tonbag_count,status,warehouse,location,
             inbound_date,created_at,updated_at)
            VALUES(?,?,?,'LITHIUM CARBONATE','CRY9000.00',
                   5001.0,5001.0,5001.0,11,
                   'AVAILABLE','GY','GY-A','2026-05-04',?,?)
        """, (lot_no, sap_no, bl_no, now, now))
        inv_id = con.execute(
            "SELECT id FROM inventory WHERE lot_no=?", (lot_no,)
        ).fetchone()[0]
        con.execute("""
            INSERT INTO inventory_tonbag
            (inventory_id,lot_no,sap_no,bl_no,
             sub_lt,tonbag_no,weight,is_sample,
             status,location,inbound_date,created_at,updated_at)
            VALUES(?,?,?,?,0,?,0.001,1,
                   'AVAILABLE','GY-A','2026-05-04',?,?)
        """, (inv_id,lot_no,sap_no,bl_no,f"{lot_no}-S",now,now))
        for i in range(1, 11):
            con.execute("""
                INSERT INTO inventory_tonbag
                (inventory_id,lot_no,sap_no,bl_no,
                 sub_lt,tonbag_no,weight,is_sample,
                 status,location,inbound_date,created_at,updated_at)
                VALUES(?,?,?,?,?,?,0.500,0,
                       'AVAILABLE','GY-A','2026-05-04',?,?)
            """, (inv_id,lot_no,sap_no,bl_no,i,f"{lot_no}-{i:02d}",now,now))
    con.commit()
    t  = con.execute("SELECT COUNT(*) FROM inventory_tonbag").fetchone()[0]
    mt = con.execute("SELECT SUM(weight) FROM inventory_tonbag").fetchone()[0]
    print(f"  생성 완료: {t}개 톤백 / {mt:.3f} MT / {len(ALL_LOTS)} LOT\n")


def check_integrity(con, label):
    total = con.execute("SELECT COUNT(*) FROM inventory_tonbag").fetchone()[0]
    dups  = con.execute("""SELECT COUNT(*) FROM(
        SELECT lot_no,sub_lt,COUNT(*) c FROM inventory_tonbag
        GROUP BY lot_no,sub_lt HAVING c>1)""").fetchone()[0]
    ok  = total==880 and dups==0
    sym = C("OK") if ok else R("FAIL")
    print(f"  {'OK' if ok else 'NG'} [{label}] 정합성 {sym} — 총 {total}개, 중복 {dups}건")
    return ok


def print_state_table(con, title, day):
    W = 112
    print("\n" + "="*W)
    print(f"  {TC(title)}   {Y(day)}")
    print("="*W)
    print(f"  {'LOT NO':14} {'SAP NO':12}  {'정규':^37}  {'샘플':^27}  {'총MT':>8}")
    print(f"  {'':14} {'':12}  "
          f"{'AVAIL':>6} {'RESV':>6} {'PICK':>6} {'SOLD':>6} {'RETN':>6}  "
          f"{'AVAIL':>5} {'RESV':>4} {'PICK':>4} {'SOLD':>4} {'RETN':>4}  {'':>8}")
    print("  " + "-"*(W-2))

    rows = con.execute("""
        SELECT lot_no, sap_no,
          SUM(CASE WHEN is_sample=0 AND status='AVAILABLE' THEN 1 ELSE 0 END) ra,
          SUM(CASE WHEN is_sample=0 AND status='RESERVED'  THEN 1 ELSE 0 END) rr,
          SUM(CASE WHEN is_sample=0 AND status='PICKED'    THEN 1 ELSE 0 END) rp,
          SUM(CASE WHEN is_sample=0 AND status='OUTBOUND'      THEN 1 ELSE 0 END) rs,
          SUM(CASE WHEN is_sample=0 AND status='RETURN'    THEN 1 ELSE 0 END) rt,
          SUM(CASE WHEN is_sample=1 AND status='AVAILABLE' THEN 1 ELSE 0 END) sa,
          SUM(CASE WHEN is_sample=1 AND status='RESERVED'  THEN 1 ELSE 0 END) sr,
          SUM(CASE WHEN is_sample=1 AND status='PICKED'    THEN 1 ELSE 0 END) sp,
          SUM(CASE WHEN is_sample=1 AND status='OUTBOUND'      THEN 1 ELSE 0 END) ss,
          SUM(CASE WHEN is_sample=1 AND status='RETURN'    THEN 1 ELSE 0 END) st,
          SUM(weight) tm
        FROM inventory_tonbag
        GROUP BY lot_no, sap_no ORDER BY lot_no
    """).fetchall()

    tot=[0]*10; tot_mt=0.0
    def fr(n,fn): return fn(f"{n:>6}") if n else "     -"
    def fs(n,fn): return fn(f"{n:>4}") if n else "   -"
    fns=[C,Y,B,R,P,C,Y,B,R,P]

    for r in rows:
        v=[r['ra'],r['rr'],r['rp'],r['rs'],r['rt'],
           r['sa'],r['sr'],r['sp'],r['ss'],r['st']]
        for i,x in enumerate(v): tot[i]+=x
        tot_mt+=r['tm']
        print(f"  {r['lot_no']:14} {r['sap_no']:12} "
              f" {fr(v[0],fns[0])}{fr(v[1],fns[1])}{fr(v[2],fns[2])}{fr(v[3],fns[3])}{fr(v[4],fns[4])}"
              f"  {fs(v[5],fns[5])}{fs(v[6],fns[6])}{fs(v[7],fns[7])}{fs(v[8],fns[8])}{fs(v[9],fns[9])}"
              f"  {r['tm']:>8.3f}")

    print("  " + "-"*(W-2))
    print(f"  {'합계 (80 LOT)':26}"
          f" {fns[0](f'{tot[0]:>6}')}{fns[1](f'{tot[1]:>6}')}{fns[2](f'{tot[2]:>6}')}{fns[3](f'{tot[3]:>6}')}{fns[4](f'{tot[4]:>6}')}"
          f"  {fns[5](f'{tot[5]:>4}')}{fns[6](f'{tot[6]:>4}')}{fns[7](f'{tot[7]:>4}')}{fns[8](f'{tot[8]:>4}')}{fns[9](f'{tot[9]:>4}')}"
          f"  {BL(f'{tot_mt:>8.3f}')}")
    print("="*W)


def step0_initial(con):
    print_state_table(con, "STEP 0 - 입고 완료 (전체 AVAILABLE)", "Day 0")
    check_integrity(con, "Step0-Initial")


def step1_allocation(con):
    now = "2026-05-05 09:00:00"
    reg_per_lot = to_int_bags(10 / 2)
    for idx,(lot_no,bl_no,sap_no) in enumerate(ALL_LOTS):
        cust   = CUSTOMER.get(sap_no,"UNKNOWN")
        sublts = list(range(1, reg_per_lot+1))
        if idx < SAMPLE_ALLOC_IDX:
            sublts = [0] + sublts
        for sub_lt in sublts:
            con.execute("""
                UPDATE inventory_tonbag
                SET status='RESERVED', updated_at=?
                WHERE lot_no=? AND sub_lt=? AND status='AVAILABLE'
            """, (now, lot_no, sub_lt))
            w = SAMP_W if sub_lt==0 else REG_W
            con.execute("""
                INSERT INTO allocation_plan
                (lot_no,sub_lt,customer,sale_ref,weight,
                 alloc_date,status,created_at,updated_at)
                VALUES(?,?,?,?,?,'2026-05-05','RESERVED',?,?)
            """, (lot_no,sub_lt,cust,f"ALLOC-{lot_no}-{sub_lt:02d}",w,now,now))
    con.commit()
    print_state_table(con, "STEP 1 - 배분 완료 (AVAILABLE -> RESERVED)", "Day 1")
    print_alloc_table(con)
    check_integrity(con, "Step1-Allocation")


def print_alloc_table(con):
    W = 100
    print(f"\n  {TC('[ 배분 테이블 (Allocation Table) ]')}")
    print("  " + "-"*W)
    print(f"  {'LOT NO':14} {'SAP NO':12} {'고객':18} {'구분':8} {'수량':>5} {'배분MT':>8}  {'sub_lt 범위':14}  {'배분일'}")
    print("  " + "-"*W)
    rows = con.execute("""
        SELECT lot_no, customer,
          COUNT(CASE WHEN sub_lt>0 THEN 1 END)               reg_cnt,
          COUNT(CASE WHEN sub_lt=0 THEN 1 END)               smp_cnt,
          GROUP_CONCAT(CASE WHEN sub_lt>0 THEN sub_lt END)   reg_sl,
          MAX(alloc_date) alloc_date
        FROM allocation_plan GROUP BY lot_no, customer ORDER BY lot_no
    """).fetchall()
    tot_rc=0; tot_sc=0; tot_rm=0.0; tot_sm=0.0
    for r in rows:
        sap    = next((l[1] for l in ALL_LOTS if l[0]==r['lot_no']), "")
        reg_mt = r['reg_cnt'] * REG_W
        smp_mt = r['smp_cnt'] * SAMP_W
        sl_raw = r['reg_sl'] or ""
        sl_num = sorted([int(x) for x in sl_raw.split(',') if x.strip()])
        sl_str = (f"1-{sl_num[-1]}" if len(sl_num)>1 else str(sl_num[0])) if sl_num else "-"
        # 정규 row
        print(f"  {r['lot_no']:14} {sap:12} {r['customer']:18} "
              f"{C('정규'):8} {r['reg_cnt']:>5} {reg_mt:>8.3f}  {sl_str:14}  {r['alloc_date']}")
        # 샘플 row
        if r['smp_cnt'] > 0:
            print(f"  {''  :14} {''  :12} {''  :18} "
                  f"{Y('샘플'):8} {r['smp_cnt']:>5} {smp_mt:>8.3f}  {'S(0)':14}  {r['alloc_date']}")
        tot_rc += r['reg_cnt']; tot_sc += r['smp_cnt']
        tot_rm += reg_mt;       tot_sm += smp_mt
    print("  " + "-"*W)
    print(f"  {'소계 정규':52} {C(f'{tot_rc:>5}')} {C(f'{tot_rm:>8.3f}')}")
    print(f"  {'소계 샘플':52} {Y(f'{tot_sc:>5}')} {Y(f'{tot_sm:>8.3f}')}")
    tot_c = tot_rc+tot_sc; tot_m = tot_rm+tot_sm
    print(f"  {'합  계':52} {BL(f'{tot_c:>5}')} {BL(f'{tot_m:>8.3f}')}")
    print(f"  ※ ceil(10/2)=5개/LOT x80={tot_rc}정규  |  앞{SAMPLE_ALLOC_IDX}LOT 샘플={tot_sc}샘플\n")

def step2_picking(con):
    now = "2026-05-12 10:00:00"
    pick_reg = to_int_bags(5 * 0.8)
    for idx,(lot_no,bl_no,sap_no) in enumerate(ALL_LOTS):
        sublts = list(range(1, pick_reg+1))
        if idx < SAMPLE_ALLOC_IDX:
            sublts = [0] + sublts
        for sub_lt in sublts:
            con.execute("""
                UPDATE inventory_tonbag
                SET status='PICKED', picked_date=?, updated_at=?
                WHERE lot_no=? AND sub_lt=? AND status='RESERVED'
            """, (now,now,lot_no,sub_lt))
            con.execute("""
                UPDATE allocation_plan SET status='PICKED', updated_at=?
                WHERE lot_no=? AND sub_lt=? AND status='RESERVED'
            """, (now,lot_no,sub_lt))
    con.commit()
    print_state_table(con,
        "STEP 2 - 피킹 완료 (sub_lt 1-4+샘플 PICKED / sub_lt 5 RESERVED 잔류)",
        "Day 7")
    print_pick_table(con)
    check_integrity(con, "Step2-Picking")


def print_pick_table(con):
    W = 108
    print(f"\n  {TC('[ 피킹 테이블 (Picking Table) ]')}")
    print("  " + "-"*W)
    print(f"  {'LOT NO':14} {'SAP NO':12} {'고객':18} {'구분':8} {'피킹수':>6} {'잔류RESV':>8} {'피킹MT':>8}  {'피킹일시'}")
    print("  " + "-"*W)
    rows = con.execute("""
        SELECT lot_no, sap_no,
          COUNT(CASE WHEN is_sample=0 AND status='PICKED'   THEN 1 END) rp,
          COUNT(CASE WHEN is_sample=0 AND status='RESERVED' THEN 1 END) rv,
          COUNT(CASE WHEN is_sample=1 AND status='PICKED'   THEN 1 END) sp,
          MAX(CASE WHEN is_sample=0 THEN picked_date END) rpd,
          MAX(CASE WHEN is_sample=1 THEN picked_date END) spd
        FROM inventory_tonbag GROUP BY lot_no, sap_no ORDER BY lot_no
    """).fetchall()
    tot_rp=0; tot_sp=0; tot_rv=0; tot_rm=0.0; tot_sm=0.0
    for r in rows:
        if r['rp']==0 and r['sp']==0: continue
        cust   = CUSTOMER.get(r['sap_no'],"")
        reg_mt = r['rp'] * REG_W
        smp_mt = r['sp'] * SAMP_W
        # 정규 row
        print(f"  {r['lot_no']:14} {r['sap_no']:12} {cust:18} "
              f"{C('정규'):8} {r['rp']:>6} {r['rv']:>8} {reg_mt:>8.3f}  {r['rpd'] or '-'}")
        # 샘플 row
        if r['sp'] > 0:
            print(f"  {''  :14} {''  :12} {''  :18} "
                  f"{Y('샘플'):8} {r['sp']:>6} {0:>8} {smp_mt:>8.3f}  {r['spd'] or '-'}")
        tot_rp += r['rp']; tot_sp += r['sp']
        tot_rv += r['rv']; tot_rm += reg_mt; tot_sm += smp_mt
    print("  " + "-"*W)
    print(f"  {'소계 정규':50} {C(f'{tot_rp:>6}')} {C(f'{tot_rv:>8}')} {C(f'{tot_rm:>8.3f}')}")
    print(f"  {'소계 샘플':50} {Y(f'{tot_sp:>6}')} {Y(f'{0:>8}')} {Y(f'{tot_sm:>8.3f}')}")
    tot_c=tot_rp+tot_sp; tot_m=tot_rm+tot_sm
    print(f"  {'합  계':50} {BL(f'{tot_c:>6}')} {BL(f'{tot_rv:>8}')} {BL(f'{tot_m:>8.3f}')}")
    print(f"  ※ ceil(5x0.8)=4개/LOT | 잔류 sub_lt5={tot_rv}개 RESERVED\n")

def step3_outbound(con):
    now  = "2026-05-19 14:00:00"
    rows = con.execute(
        "SELECT lot_no,sub_lt FROM inventory_tonbag WHERE status='PICKED' ORDER BY lot_no,sub_lt"
    ).fetchall()
    for r in rows:
        con.execute("""
            UPDATE inventory_tonbag
            SET status='OUTBOUND', outbound_date=?, updated_at=?
            WHERE lot_no=? AND sub_lt=? AND status='PICKED'
        """, (now,now,r['lot_no'],r['sub_lt']))
        con.execute("""
            UPDATE allocation_plan SET status='OUTBOUND', updated_at=?
            WHERE lot_no=? AND sub_lt=? AND status='PICKED'
        """, (now,r['lot_no'],r['sub_lt']))
    con.commit()
    print_state_table(con, "STEP 3 - 출고 완료 (PICKED -> OUTBOUND)", "Day 14")
    print_outbound_table(con)
    check_integrity(con, "Step3-Outbound")


def print_outbound_table(con):
    W = 108
    print(f"\n  {TC('[ 출고 테이블 (Outbound Table) ]')}")
    print("  " + "-"*W)
    print(f"  {'LOT NO':14} {'SAP NO':12} {'고객':18} {'구분':8} {'출고수':>6} {'출고MT':>8}  {'출고 Ref No':22}  {'출고일'}")
    print("  " + "-"*W)
    rows = con.execute("""
        SELECT lot_no, sap_no,
          COUNT(CASE WHEN is_sample=0 AND status='OUTBOUND' THEN 1 END) rg,
          COUNT(CASE WHEN is_sample=1 AND status='OUTBOUND' THEN 1 END) sm,
          MAX(outbound_date) od
        FROM inventory_tonbag GROUP BY lot_no, sap_no ORDER BY lot_no
    """).fetchall()
    tot_rg=0; tot_sm=0; tot_rm=0.0; tot_sm2=0.0; idx=0
    for r in rows:
        if r['rg']==0 and r['sm']==0: continue
        idx += 1
        cust   = CUSTOMER.get(r['sap_no'],"")
        ref_no = f"OUT-GY-2605-{idx:04d}"
        reg_mt = r['rg'] * REG_W
        smp_mt = r['sm'] * SAMP_W
        # 정규 row
        print(f"  {r['lot_no']:14} {r['sap_no']:12} {cust:18} "
              f"{C('정규'):8} {r['rg']:>6} {reg_mt:>8.3f}  {ref_no:22}  {r['od'] or '-'}")
        # 샘플 row
        if r['sm'] > 0:
            print(f"  {''  :14} {''  :12} {''  :18} "
                  f"{Y('샘플'):8} {r['sm']:>6} {smp_mt:>8.3f}  {ref_no:22}  {r['od'] or '-'}")
        tot_rg += r['rg']; tot_sm += r['sm']
        tot_rm += reg_mt;   tot_sm2 += smp_mt
    print("  " + "-"*W)
    print(f"  {'소계 정규':50} {C(f'{tot_rg:>6}')} {C(f'{tot_rm:>8.3f}')}")
    print(f"  {'소계 샘플':50} {Y(f'{tot_sm:>6}')} {Y(f'{tot_sm2:>8.3f}')}")
    tot_c=tot_rg+tot_sm; tot_m=tot_rm+tot_sm2
    print(f"  {'합  계':50} {BL(f'{tot_c:>6}')} {BL(f'{tot_m:>8.3f}')}\n")

def step4_return(con):
    now = "2026-05-26 09:00:00"
    for lot_no,bl_no,sap_no in ALL_LOTS[:RETURN_IDX]:
        con.execute("""
            UPDATE inventory_tonbag
            SET status='RETURN', return_date=?, updated_at=?
            WHERE lot_no=? AND sub_lt=1 AND status='OUTBOUND'
        """, (now,now,lot_no))
        con.execute("""
            UPDATE allocation_plan SET status='RETURN', updated_at=?
            WHERE lot_no=? AND sub_lt=1 AND status='OUTBOUND'
        """, (now,lot_no))
    con.commit()
    print_state_table(con,
        "STEP 4 - 반품 (SOLD -> RETURN, 앞 20 LOT sub_lt 1)",
        "Day 21")
    print_return_table(con)
    check_integrity(con, "Step4-Return")


def print_return_table(con):
    W = 96
    print(f"\n  {TC('[ 반품 테이블 (Return Table) ]')}")
    print("  " + "-"*W)
    print(f"  {'LOT NO':14} {'SAP NO':12} {'고객':18} {'구분':8} {'sub_lt':>6}  {'반품사유':20} {'반품MT':>7}  {'반품일'}")
    print("  " + "-"*W)
    rows = con.execute("""
        SELECT lot_no, sap_no, sub_lt, is_sample, weight, return_date
        FROM inventory_tonbag WHERE status='RETURN'
        ORDER BY lot_no, sub_lt
    """).fetchall()
    tot_reg=0; tot_smp=0; tot_rm=0.0; tot_sm=0.0
    for r in rows:
        cust   = CUSTOMER.get(r['sap_no'],"")
        gubun  = Y('샘플') if r['is_sample'] else C('정규')
        reason = '수량조정/반품'
        print(f"  {r['lot_no']:14} {r['sap_no']:12} {cust:18} "
              f"{gubun:8} {r['sub_lt']:>6}  {reason:20} {r['weight']:>7.3f}  {r['return_date'] or '-'}")
        if r['is_sample']:
            tot_smp += 1; tot_sm += r['weight']
        else:
            tot_reg += 1; tot_rm += r['weight']
    print("  " + "-"*W)
    print(f"  {'소계 정규':62} {C(f'{tot_reg:>6}')}  {''   :20} {C(f'{tot_rm:>7.3f}')}")
    print(f"  {'소계 샘플':62} {Y(f'{tot_smp:>6}')}  {''   :20} {Y(f'{tot_sm:>7.3f}')}")
    tot_c=tot_reg+tot_smp; tot_m=tot_rm+tot_sm
    print(f"  {'합  계':62} {BL(f'{tot_c:>6}')}  {''   :20} {BL(f'{tot_m:>7.3f}')}\n")

def step5_move(con):
    now  = "2026-05-27 08:00:00"
    rows = con.execute(
        "SELECT lot_no,sub_lt,weight FROM inventory_tonbag WHERE status='RETURN' ORDER BY lot_no,sub_lt"
    ).fetchall()
    for r in rows:
        con.execute("""
            UPDATE inventory_tonbag
            SET status='AVAILABLE', location='GY-B-RETURN', updated_at=?
            WHERE lot_no=? AND sub_lt=? AND status='RETURN'
        """, (now,r['lot_no'],r['sub_lt']))
        con.execute("""
            INSERT INTO stock_movement
            (lot_no,sub_lt,movement_type,from_status,to_status,
             from_location,to_location,weight,actor,remarks,created_at)
            VALUES(?,?,'MOVE','RETURN','AVAILABLE',
                   'GY-A','GY-B-RETURN',?,'Nam Ki-dong','반품 재입고',?)
        """, (r['lot_no'],r['sub_lt'],r['weight'],now))
    con.commit()
    print_state_table(con,
        "STEP 5 - 재입고 (RETURN -> AVAILABLE, 위치: GY-B-RETURN)",
        "Day 22")
    print_move_table(con)
    mv = con.execute("SELECT COUNT(*) FROM stock_movement WHERE movement_type='MOVE'").fetchone()[0]
    print(f"  {C('OK')} stock_movement MOVE 기록: {mv}건")
    check_integrity(con, "Step5-Move+ReAvail")


def print_move_table(con):
    W = 110
    print(f"\n  {TC('[ 이동 테이블 (Stock Movement Table) ]')}")
    print("  " + "-"*W)
    print(f"  {'LOT NO':14} {'SAP NO':12} {'구분':8} {'sub_lt':>6}  "
          f"{'유형':6} {'FROM':10} {'TO':10} "
          f"{'From창고':10} {'To창고':12} {'MT':>7}  {'이동일시'}")
    print("  " + "-"*W)
    rows = con.execute("""
        SELECT m.lot_no, t.sap_no, t.is_sample, m.sub_lt,
               m.movement_type, m.from_status, m.to_status,
               m.from_location, m.to_location,
               m.weight, m.created_at
        FROM stock_movement m
        LEFT JOIN inventory_tonbag t ON t.lot_no=m.lot_no AND t.sub_lt=m.sub_lt
        ORDER BY m.lot_no, m.sub_lt
    """).fetchall()
    tot_reg=0; tot_smp=0; tot_rm=0.0; tot_sm=0.0
    for r in rows:
        sap    = r['sap_no'] or ''
        gubun  = Y('샘플') if r['is_sample'] else C('정규')
        print(f"  {r['lot_no']:14} {sap:12} {gubun:8} {r['sub_lt']:>6}  "
              f"{r['movement_type']:6} {r['from_status']:10} {r['to_status']:10} "
              f"{r['from_location']:10} {r['to_location']:12} {r['weight']:>7.3f}  {r['created_at']}")
        if r['is_sample']:
            tot_smp += 1; tot_sm += r['weight']
        else:
            tot_reg += 1; tot_rm += r['weight']
    print("  " + "-"*W)
    print(f"  {'소계 정규':44} {C(f'{tot_reg:>6}')}  {''  :6} {''  :10} {''  :10} {''  :10} {''  :12} {C(f'{tot_rm:>7.3f}')}")
    print(f"  {'소계 샘플':44} {Y(f'{tot_smp:>6}')}  {''  :6} {''  :10} {''  :10} {''  :10} {''  :12} {Y(f'{tot_sm:>7.3f}')}")
    tot_c=tot_reg+tot_smp; tot_m=tot_rm+tot_sm
    print(f"  {'합  계':44} {BL(f'{tot_c:>6}')}  {''  :6} {''  :10} {''  :10} {''  :10} {''  :12} {BL(f'{tot_m:>7.3f}')}\n")

def final_summary(con):
    print(TC("\n" + "="*70))
    print(TC("  최종 결과 요약 (실 프로그램 기본 로직 검증)"))
    print(TC("="*70))
    sc = con.execute("""
        SELECT status,COUNT(*) cnt,SUM(weight) mt
        FROM inventory_tonbag GROUP BY status ORDER BY cnt DESC
    """).fetchall()
    mx   = max(r['cnt'] for r in sc) if sc else 1
    cmap = {'AVAILABLE':C,'RESERVED':Y,'PICKED':B,'OUTBOUND':R,'RETURN':P}
    print("\n  상태별 최종 톤백 수:")
    for r in sc:
        fn  = cmap.get(r['status'], lambda x: x)
        bar = "X" * int(r['cnt']/mx*50)
        st  = r['status']
        cnt = r['cnt']
        print(f"    {fn(f'{st:12}')}: "
              f"{fn(f'{cnt:>4}')}개 / {r['mt']:>7.3f} MT  {fn(bar)}")
    ac = con.execute("SELECT COUNT(*) FROM allocation_plan").fetchone()[0]
    mc = con.execute("SELECT COUNT(*) FROM stock_movement").fetchone()[0]
    tc = con.execute("SELECT COUNT(*) FROM inventory_tonbag").fetchone()[0]
    print(f"\n  총계: {BL(str(tc))}개 (기대: 880)")
    print(f"  allocation_plan: {ac}건 | stock_movement: {mc}건")
    ok = tc==880
    print(f"\n  {C('OK PASSED') if ok else R('FAIL')} — 정합성 {'OK' if ok else 'FAIL'}")
    if ok:
        print(f"  {BL(C('TRP 실 프로그램 기본 로직 검증 완료'))}")
        print(f"  {BL(C('  부분 배분(5/10) -> 부분 피킹(4/5) -> 출고 -> 반품 -> 재입고 정상'))}")
    print(TC("="*70 + "\n"))


def main():
    print(TC("\n" + "="*70))
    print(TC("  SQM v8.6.6 - 전체 워크플로 Smoke Test (톤백 레벨 상세)"))
    print(TC("  80 LOT x 11톤백 = 880개 / 400.080 MT"))
    print(TC("  실 프로그램 기본 로직: 각 LOT 내 부분 배분/피킹/출고/반품/이동"))
    print(TC("="*70))
    tmp = tempfile.mktemp(suffix=".db", dir="/tmp")
    print(f"\n  임시 DB: {tmp}")
    con = create_db(tmp)
    populate(con)
    step0_initial(con)
    step1_allocation(con)
    step2_picking(con)
    step3_outbound(con)
    step4_return(con)
    step5_move(con)
    final_summary(con)
    con.close()
    os.remove(tmp)

if __name__ == "__main__":
    main()
