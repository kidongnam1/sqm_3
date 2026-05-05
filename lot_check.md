# LOT Status Integrity Repair

This document explains the v864-2 inbound menu item:

```text
LOT 상태 정합성 복구
```

and how it is currently reflected in v866.

## What This Menu Does

`LOT 상태 정합성 복구` is not a quantity recalculation feature.

It repairs mismatches between:

```text
inventory.status
inventory_tonbag.status
```

In other words, it checks whether the representative LOT status matches the actual statuses of the tonbags inside that LOT.

## Original v864-2 Behavior

In the original Tk(GUI), the menu asks for confirmation before running.

The message is conceptually:

```text
LOT 상태를 톤백 기준으로 일괄 보정합니다.

• LOT=SOLD 이지만 AVAILABLE 톤백 잔존 → AVAILABLE
• LOT=AVAILABLE 이지만 전체 SOLD → SOLD

계속하시겠습니까?
```

The original GUI handler is:

```text
gui_app_modular/mixins/toolbar_mixin.py
_on_fix_lot_status_integrity()
```

The actual engine function is:

```text
engine_modules/inventory_modular/outbound_mixin.py
fix_lot_status_integrity()
```

## Actual Repair Rules

The engine function checks two main cases.

### Case 1: LOT is sold/outbound, but available tonbags remain

Example:

```text
inventory.status = SOLD or OUTBOUND
inventory_tonbag.status includes AVAILABLE
```

If normal or sample AVAILABLE tonbags remain, the LOT status is corrected.

Result:

```text
SOLD/OUTBOUND -> AVAILABLE or PARTIAL
```

If some tonbags are already sold and some remain available, the corrected LOT status becomes:

```text
PARTIAL
```

### Case 2: LOT is available, but all tonbags are sold

Example:

```text
inventory.status = AVAILABLE
all inventory_tonbag.status = SOLD
```

Result:

```text
AVAILABLE -> OUTBOUND
```

## What It Does Not Do

This feature does not primarily:

- recalculate total quantity
- recalculate stock weight
- recreate missing tonbags
- repair allocation quantities
- validate sample weight

It only corrects the LOT-level representative status based on tonbag status aggregation.

## v866 Current State

v866 still contains the core engine repair logic.

Engine function:

```text
engine_modules/inventory_modular/outbound_mixin.py
fix_lot_status_integrity()
```

Tk(GUI) handler also exists:

```text
gui_app_modular/mixins/toolbar_mixin.py
_on_fix_lot_status_integrity()
```

v866 also has a web API endpoint:

```text
POST /api/action/fix-integrity
```

API implementation:

```text
backend/api/actions.py
fix_integrity()
```

The API calls:

```python
eng.fix_lot_status_integrity()
```

## Current Web Menu Wiring Problem

The v866 web menu item exists in:

```text
frontend/index.html
```

Action:

```text
onFixLotIntegrity
```

However, the current web dispatch table in:

```text
frontend/js/sqm-inline.js
```

maps it to:

```text
GET /api/action/integrity-check
```

That endpoint only performs an integrity check. It does not run the repair.

The expected repair endpoint should be:

```text
POST /api/action/fix-integrity
```

## Correct v866 Wiring

To make the web menu behave like the original v864-2 Tk(GUI) menu, the web action should be changed from:

```text
onFixLotIntegrity -> GET /api/action/integrity-check
```

to:

```text
onFixLotIntegrity -> POST /api/action/fix-integrity
```

Recommended UX:

1. Show confirmation before repair.
2. Call `POST /api/action/fix-integrity`.
3. Show repaired count and details.
4. Refresh affected inventory/outbound pages.

## Summary

Current state:

```text
Engine repair logic: exists
Tk(GUI) repair menu: exists
Web repair API: exists
Web menu wiring: incorrect / incomplete
```

Likely reason for current error or wrong behavior:

```text
The web button name says "LOT 상태 정합성 복구",
but it is wired to the check API instead of the repair API.
```

Required fix:

```text
Wire onFixLotIntegrity to POST /api/action/fix-integrity
and add confirmation/result handling.
```
