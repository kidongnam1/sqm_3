# SQM v866 MASTER-P3: Phase 3 (Frontend JS)
**읽은 후 MASTER_P4.md 로 진행**
**progress.txt 에 각 TASK 완료 기록 필수**

---
## 절대 원칙 (항상 적용)
- sqm-inline.js Edit 툴 직접 수정 금지 (Python 스크립트만)
- 모든 JS fetch: api-client.js 통해서만
- 빈 화면 절대 금지
- node --check 검증 필수
- 에러 시 RETRY 3회 + Ruby 즉시 수정 후 다음 TASK 진행 (중단 금지)
- error_report.md는 기록용으로만 사용 (작성해도 STOP하지 말 것)

---
## 체크포인트 규칙
완료 시: progress.txt 에 "DONE: [TASK명]" 추가

---
# PHASE 3 — 프론트엔드 JS 완성 (Agent A)

**현황:** frontend/js/pages/ 9개 파일 존재 (50~112줄). 기능 연결 미완성 부분 보완.

## P3-TASK-01: api-client.js 표준화 확인

**파일:** `frontend/js/api-client.js`
**예상: 15분**

```javascript
// 아래 함수들이 반드시 있어야 함
// 없으면 추가, 있으면 패턴 확인

async function apiGet(endpoint, params = {}) {
    const url = new URL(`http://localhost:8765${endpoint}`);
    Object.entries(params).forEach(([k, v]) => url.searchParams.append(k, v));
    try {
        const res = await fetch(url.toString());
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        if (!data.success) throw new Error(data.message || '서버 오류');
        return data;
    } catch (e) {
        showToast(e.message, 'error');
        throw e;
    }
}

async function apiPost(endpoint, body = {}) {
    try {
        const res = await fetch(`http://localhost:8765${endpoint}`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(body)
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        if (!data.success) throw new Error(data.message || '서버 오류');
        return data;
    } catch (e) {
        showToast(e.message, 'error');
        throw e;
    }
}
```

**검증:**
```bash
node --check frontend/js/api-client.js
grep -n "apiGet\|apiPost\|apiPut" frontend/js/api-client.js | head -10
```
**완료 후:** progress.txt 기록

## P3-TASK-02: inventory.js 실데이터 연결

**파일:** `frontend/js/pages/inventory.js` (현재 94줄)
**API:** `/api/inventory` (inventory_api.py)
**예상: 30분**

```javascript
// 반드시 포함할 함수들

async function loadInventory(filters = {}) {
    try {
        const data = await apiGet('/api/inventory', filters);
        renderInventoryTable(data.data);
        updateStatusBar(data.data.length);
    } catch (e) { /* apiGet이 Toast 처리 */ }
}

function renderInventoryTable(rows) {
    // 19개 컬럼 순서 고정
    // No|LOT NO|SAP NO|BL NO|PRODUCT|STATUS|Balance(Kg)|NET(Kg)|
    // CONTAINER|MXBG|INVOICE NO|SHIP DATE|ARRIVAL|CON RETURN|
    // FREE TIME|WH|CUSTOMS|Inbound(Kg)|Outbound(Kg)

    // 행 색상 (CSS 클래스로)
    // AVAILABLE → row-available
    // RESERVED  → row-reserved
    // PICKED    → row-picked
    // OUTBOUND  → row-outbound
}

// 더블클릭 → LOT 상세 모달
function onRowDoubleClick(lotNo) { /* ... */ }

// 우클릭 → 즉시 출고 컨텍스트 메뉴
function onRowRightClick(e, lotNo) { /* ... */ }

// 탭 진입 시 자동 로드
document.addEventListener('DOMContentLoaded', () => loadInventory());
```

**검증:**
```bash
node --check frontend/js/pages/inventory.js
grep -n "async function\|apiGet\|apiPost" frontend/js/pages/inventory.js
```
**완료 후:** progress.txt 기록

## P3-TASK-03: dashboard.js KPI 실데이터 연결

**파일:** `frontend/js/pages/dashboard.js` (현재 112줄)
**API:** `/api/dashboard/stats`, `/api/integrity/check`
**예상: 25분**

```javascript
// 반드시 포함할 함수들

async function loadDashboard() {
    try {
        const [stats, integrity] = await Promise.all([
            apiGet('/api/dashboard/stats'),
            apiGet('/api/integrity/check')
        ]);
        renderKpiCards(stats.data);
        renderIntegrityLight(integrity.data);
        renderProductTable(stats.data.by_product);
    } catch (e) {}
}

function renderKpiCards(data) {
    // KPI 카드 5개: AVAILABLE / RESERVED / PICKED / OUTBOUND / RETURN
    // 각: 상태명 + 톤백수 + 총 중량Kg
    // 색상: CSS 변수 (design-tokens.css) 사용
}

function renderIntegrityLight(data) {
    // data.error > 0 → 🔴
    // data.warning > 0 → 🟡
    // else → 🟢
}

// 30초 자동 갱신
setInterval(loadDashboard, 30000);
loadDashboard();  // 최초 로드
```

**검증:**
```bash
node --check frontend/js/pages/dashboard.js
grep -n "setInterval\|loadDashboard" frontend/js/pages/dashboard.js
```
**완료 후:** progress.txt 기록

## P3-TASK-04: scan.js 4버튼 연결

**파일:** `frontend/js/pages/scan.js` (현재 69줄)
**API:** `/api/scan/*`
**예상: 25분**

```javascript
// 핵심 구현

const uidInput = document.getElementById('uid-input');

// 엔터키 → 자동 조회
uidInput?.addEventListener('keydown', async (e) => {
    if (e.key === 'Enter') await lookupUid(uidInput.value.trim());
});

async function lookupUid(uid) {
    const data = await apiPost('/api/scan/lookup', {uid});
    showScanResult(data.data);
    updateActionButtons(data.data.status);
}

function updateActionButtons(status) {
    // 조건부 활성화
    document.getElementById('btn-confirm').disabled = (status !== 'PICKED');
    document.getElementById('btn-return').disabled  = (status !== 'OUTBOUND');
    document.getElementById('btn-restock').disabled = (status !== 'RETURN');
    document.getElementById('btn-move').disabled    = false;  // 항상 활성
}

// 4개 버튼 핸들러
async function confirmOutbound() {
    // PICKED → OUTBOUND → SOLD (SOLD는 이 경로만)
    await apiPost('/api/scan/confirm_outbound', {uid: uidInput.value});
}
```

**검증:**
```bash
node --check frontend/js/pages/scan.js
```
**완료 후:** progress.txt 기록

## P3-TASK-05: menubar.js 미연결 메뉴 완성

**파일:** `frontend/js/handlers/menubar.js`
**참조:** `docs/handoff/feature_matrix.json` (85개 기능)
**예상: 30분**

```bash
# 현재 연결된 메뉴 수 확인
grep -c "async function\|apiGet\|apiPost" frontend/js/handlers/menubar.js

# feature_matrix.json 에서 미연결 항목 찾기
python -c "
import json
with open('docs/handoff/feature_matrix.json') as f:
    fm = json.load(f)
missing = [f for f in fm if not f.get('js_handler')]
print(f'미연결 기능: {len(missing)}개')
for m in missing[:10]:
    print(' -', m.get('name', '?'))
"
```

각 미연결 메뉴에 대해:
- apiGet/apiPost 연결 함수 추가
- 연결 불가능한 기능은 showToast('준비 중', 'info') 처리

**검증:**
```bash
node --check frontend/js/handlers/menubar.js
```
**완료 후:** progress.txt 기록

---

### SYNC-2: Phase 2+3 완료

```
MASTER Agent 확인:
[ ] scan_api.py, integrity_api.py py_compile 통과
[ ] backend/__init__.py 신규 라우터 등록
[ ] 모든 JS 파일 node --check 통과
[ ] dashboard.js setInterval(30000) 포함
→ python scripts/telegram_notify.py sync2 [API수]
→ python scripts/telegram_notify.py sync3 [JS파일수]
→ Agent D 검증 시작
```

---


---
## P3 완료 후 다음 단계
progress.txt 에 "DONE: PHASE3" 기록
python scripts/telegram_notify.py sync3 5
→ MASTER_P4.md 로 진행
