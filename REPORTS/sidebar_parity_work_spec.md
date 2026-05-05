# Sidebar Parity Work Specification

## Goal

Bring the current web UI sidebar tabs in `SQM_v866_CLEAN` closer to the original Tkinter GUI behavior from:

```text
D:\program\SQM_inventory\Claude_SQM_v864_20260329_FULL
```

Current working folder:

```text
D:\program\SQM_inventory\SQM_v866_CLEAN
```

Target sidebar tabs:

```text
Inventory
Allocation
Picked
Outbound
Return
Move
Dashboard
Log
Scan
```

The sidebar tab count is already 9 in both versions. The gap is inside each tab: buttons, filters, detail panels, context menus, export actions, and state-change workflows.

## Recommended Team Size

Use a 5-person sub-agent team.

- 1 lead/spec owner
- 3 frontend feature owners split by tab group
- 1 backend/API and verification owner

This is preferable to a single implementer because the risk is not only coding effort. The larger risk is missing parity details across 9 tabs.

## Common Rules

- Use original Tkinter code as the behavior reference.
- Active web UI sources are mainly:

```text
frontend/index.html
frontend/js/sqm-inline.js
```

- Original tab behavior references are:

```text
gui_app_modular/tabs/inventory_tab.py
gui_app_modular/tabs/allocation_tab.py
gui_app_modular/tabs/picked_tab.py
gui_app_modular/tabs/sold_tab.py
gui_app_modular/tabs/cargo_overview_tab.py
gui_app_modular/tabs/move_tab.py
gui_app_modular/tabs/dashboard_tab.py
gui_app_modular/tabs/log_tab.py
gui_app_modular/tabs/scan_tab.py
```

- Reuse existing APIs before adding new ones.
- If an API is missing, first look for an existing engine method and expose it minimally.
- Do not add buttons that silently do nothing.
- Destructive operations must show confirmation.
- State-changing actions must refresh the active tab after success.
- State-changing inventory/outbound actions should trigger or expose follow-up integrity checks where appropriate.

## Team 1: Lead / Specification Owner

### Owned Files

```text
REPORTS/sidebar_parity_checklist.md
REPORTS/sidebar_parity_gap_table.md
```

### Tasks

- Extract all original tab-level functions from the original Tkinter source.
- Build a per-tab comparison table with:
  - visible buttons
  - filters/search inputs
  - detail panels
  - right-click/context menu items
  - Excel/PDF exports
  - state transition actions
  - existing API or required API
  - current web implementation status
  - priority
- Track each feature as `missing`, `partial`, or `done`.
- Assign each missing item to an implementation owner.

### Done Criteria

- All 9 sidebar tabs have a parity checklist.
- Each missing item has owner, priority, and expected behavior.

## Team 2: Inventory + Allocation Owner

### Owned Files

```text
frontend/js/sqm-inline.js
backend/api/inventory_api.py
backend/api/allocation_api.py
backend/api/queries.py
```

### Inventory Scope

Implement or verify:

- refresh
- LOT detail view
- tonbag detail view
- copy LOT
- copy full row
- quick outbound entry
- return/re-inbound entry
- LOT history lookup
- stronger totals footer
- filters/search
- web context menu if needed

### Allocation Scope

Implement or verify:

- show all allocations
- Excel export
- refresh
- cancel selected allocation
- bulk cancel by SALE REF
- LOT overview
- full reset
- `RESERVED -> AVAILABLE`
- `PICKED -> RESERVED`
- `OUTBOUND -> PICKED`
- select all
- detail-panel selected cancel
- detail-panel cancel all

### Done Criteria

- Inventory and Allocation expose the original high-risk operations in the web UI.
- Dangerous actions require confirmation.
- API errors are visible to the user.

## Team 3: Picked + Outbound Owner

### Owned Files

```text
frontend/js/sqm-inline.js
backend/api/outbound_api.py
backend/api/queries.py
backend/api/actions.py
```

### Picked Scope

Implement or verify:

- refresh
- revert picked cargo decision
- show all picked
- Excel export
- select all
- LOT tonbag detail
- back to LOT list from detail view

### Outbound Scope

Implement or verify:

- refresh
- cancel outbound
- finalize return to available
- show all sold/outbound
- Excel export
- LOT tonbag detail
- back to LOT list from detail view

### Done Criteria

- Picked and Outbound support original cancellation/revert/export behavior.
- On success, the tab reloads.
- Partial DB updates are avoided.

## Team 4: Return + Move + Log + Scan Owner

### Owned Files

```text
frontend/js/sqm-inline.js
backend/api/scan_api.py
backend/api/actions.py
backend/api/queries.py
backend/api/inventory_api.py
```

### Return Scope

Implement or verify:

- Return Inbound Excel
- Return re-inbound
- Return Statistics
- refresh
- return table with reason/date/weight

### Move Scope

Implement or verify:

- Tonbag UID lookup
- current location display
- destination location input
- execute move
- clear
- continuous scan checkbox
- Location Upload Excel
- Move Approval
- refresh
- status filter
- LOT search
- move history table

### Log Scope

Implement or verify:

- clear
- export
- refresh
- limit selection

### Scan Scope

Implement or verify:

- tonbag number input
- lookup
- clear
- quick-action buttons
- two original check options
- scan history table
- keep current PDF Inbound panel if it does not conflict

### Done Criteria

- Return, Move, Log, and Scan expose original tab actions or a documented replacement.
- Move and Scan support Enter-key workflows.
- Log export downloads or creates CSV/Excel.

## Team 5: Backend/API + Verification Owner

### Owned Files

```text
backend/api/*.py
scripts/test_menu_playwright.py
scripts/test_all_menus_playwright.py
scripts/verify_endpoints.py
REPORTS/sidebar_parity_test_result.md
```

### Tasks

- Classify frontend-required actions as:
  - existing API
  - existing engine method needing an API wrapper
  - missing behavior
- Add minimal wrappers only where needed.
- Update or add click tests for sidebar pages and their primary actions.
- Run syntax checks:
  - Python compile
  - JavaScript syntax check
- Smoke test:
  - 9 sidebar tabs load
  - primary buttons are clickable
  - destructive buttons show confirmation
  - no unregistered action
  - no 404/501 for completed features

### Done Criteria

- Every added button has a real action, a disabled state, or a clear planned-state message.
- Test results are documented in:

```text
REPORTS/sidebar_parity_test_result.md
```

## Priority

### Priority 1

```text
Inventory
Allocation
Picked
Outbound
```

These directly affect stock state and quantity integrity.

### Priority 2

```text
Return
Move
Scan
```

These affect operational workflows and physical stock handling.

### Priority 3

```text
Dashboard
Log
```

These are important for visibility and audit but less likely to corrupt inventory state.

## Suggested Execution Order

1. Lead creates the parity checklist and gap table.
2. Implementation owners add missing UI/actions by tab group.
3. Backend owner exposes missing API wrappers.
4. Each owner performs tab-level smoke tests.
5. Verification owner runs full sidebar/menu click tests.
6. Lead signs off against the checklist.

## Expected Output Files

```text
REPORTS/sidebar_parity_checklist.md
REPORTS/sidebar_parity_gap_table.md
REPORTS/sidebar_parity_test_result.md
```

## Likely Modified Files

```text
frontend/js/sqm-inline.js
frontend/index.html
backend/api/inventory_api.py
backend/api/allocation_api.py
backend/api/outbound_api.py
backend/api/scan_api.py
backend/api/actions.py
backend/api/queries.py
scripts/test_all_menus_playwright.py
```
