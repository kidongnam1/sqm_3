# Web Product Master Expansion Plan

## Purpose

The current web product master exists, but it is not identical to the original Tk(GUI) product master.

Current web product master focuses on:

```text
product_name
sap_no
spec
unit
remarks
```

Original Tk(GUI) product master focuses on:

```text
code
full_name
korean_name
tonbag_support
is_default
is_active
sort_order
```

To make the web product master match the original v864-2 behavior, the web side should be expanded rather than replaced.

## Recommended Target Schema

Keep the current web fields and add the original Tk fields.

Recommended `product_master` structure:

```text
id
code
product_name
full_name
korean_name
sap_no
spec
unit
remarks
tonbag_support
is_default
is_active
sort_order
created_at
updated_at
```

This preserves current web behavior while adding the original Tk product-code behavior.

## Default Products

The original Tk(GUI) product master has 8 default products:

```text
NSH - Nickel Sulfate Hexahydrate - 황산니켈
LCA - Lithium Carbonate Anhydrous - 탄산리튬
CSH - Cobalt Sulfate Heptahydrate - 황산코발트
NCM - Nickel Cobalt Manganese - 니켈코발트망간
NCA - Nickel Cobalt Aluminum - 니켈코발트알루미늄
LFP - Lithium Iron Phosphate - 리튬인산철
LMO - Lithium Manganese Oxide - 리튬망간산화물
LCO - Lithium Cobalt Oxide - 리튬코발트산화물
```

The web API should insert these defaults either during app startup or through a dedicated endpoint such as:

```text
POST /api/product-master/sync-defaults
```

Recommended default policy:

- `code` must be unique.
- Default products should have `is_default=1`.
- Default products should not be hard-deleted.
- Default products may be editable if the original Tk behavior is preserved.

## API Changes

Current API file:

```text
backend/api/product_master.py
```

### GET /api/product-master/list

Should return all new fields:

```text
id
code
product_name
full_name
korean_name
sap_no
spec
unit
remarks
tonbag_support
is_default
is_active
sort_order
created_at
updated_at
```

Recommended ordering:

```sql
ORDER BY sort_order, code
```

Optional query behavior:

```text
active_only=true
```

### POST /api/product-master/create

Payload should support:

```text
code
product_name
full_name
korean_name
sap_no
spec
unit
remarks
tonbag_support
is_active
sort_order
```

Rules:

- `code` is required.
- `code` should be normalized to uppercase.
- `code` must be unique.
- `full_name` or `product_name` should be required.

### PUT /api/product-master/{id}

Should allow updates to:

```text
code
product_name
full_name
korean_name
sap_no
spec
unit
remarks
tonbag_support
is_active
sort_order
```

If `is_default=1`, deletion should be blocked, but editing can be allowed if matching original Tk behavior.

### DELETE /api/product-master/{id}

Recommended behavior:

- If `is_default=1`, reject deletion.
- If user-created, prefer soft delete:

```text
is_active=0
```

This is safer than hard-deleting rows that may be referenced by historical inventory data.

### POST /api/product-master/sync-from-inventory

Keep the current function that imports distinct product names from `inventory`.

Recommended migration behavior:

- If `code` is empty, leave it blank for manual cleanup or generate a safe provisional code.
- If `full_name` is empty, copy `product_name`.
- Set `is_default=0`.
- Set `is_active=1`.

## Frontend Changes

Current web product master modal is in:

```text
frontend/js/sqm-inline.js
```

The modal should show these columns:

```text
약칭
Full Name
한글명
SAP No
규격
단위
톤백지원
기본제품
활성
비고
작업
```

The input form should include:

```text
code
full_name
korean_name
sap_no
spec
unit
tonbag_support checkbox
is_active checkbox
remarks
```

Recommended buttons:

```text
추가
수정
삭제 또는 비활성화
초기화
기본 제품 동기화
재고 제품 동기화
```

Deletion behavior:

- Default product: show "기본 제품은 삭제할 수 없습니다."
- User product: call delete/soft-delete API.

## Inbound Integration

The product master is useful only if inbound workflows use it.

It should be connected to:

```text
one-stop inbound preview
Excel manual inbound
PDF inbound parse review
product auto-detection
```

When editing a product column in inbound preview, the UI should show choices like:

```text
NSH - Nickel Sulfate Hexahydrate / 황산니켈
LCA - Lithium Carbonate Anhydrous / 탄산리튬
```

Storage policy should be decided explicitly.

Recommended policy:

- Store a stable product code or standardized full name in inventory.
- Display code and names together in the UI.
- Preserve original parsed text separately if the schema supports it.

## Product Auto-Detection

The original Tk side uses helper logic in:

```text
gui_app_modular/dialogs/product_master_helper.py
```

The web side should use equivalent backend logic so all import routes behave consistently.

Example detection rules:

```text
"Nickel Sulfate" -> NSH
"Lithium Carbonate" -> LCA
"황산니켈" -> NSH
"탄산리튬" -> LCA
existing code such as NSH or LCA -> keep as-is
```

Recommended location:

```text
backend helper or API layer
```

Avoid putting all detection rules only in JavaScript, because PDF import, Excel import, and other backend routes may then produce different product codes.

## Migration Plan

1. Add missing columns to `product_master`.
2. Add default-product insertion function.
3. Expand API payload and response models.
4. Update web product master modal table and form.
5. Change delete behavior to default-safe soft deletion.
6. Keep inventory sync behavior.
7. Connect inbound preview product fields to the product master list.
8. Add backend product auto-detection helper.
9. Test create/update/delete/sync/default insertion.
10. Test inbound workflows with product master selection and auto-detection.

## Main Risk

The current web product master and original Tk product master have different schema assumptions.

Do not replace the current web schema outright. That can break existing web features using:

```text
sap_no
spec
unit
remarks
```

Use an expansion strategy:

```text
current web fields
+ original Tk fields
+ default product policy
+ inbound dropdown / auto-detection integration
```

This preserves current behavior and brings the web product master closer to v864-2 parity.
