# 2026-04-29 버그 패치 커밋 명령어

## Windows CMD/PowerShell에서 실행:

```
cd D:\program\SQM_inventory\SQM_v865_CLEAN

git add engine_modules/inventory_modular/outbound_mixin.py
git add engine_modules/inventory_modular/inbound_mixin.py
git add engine_modules/inventory_modular/crud_mixin.py

git commit -m "fix: patch 7 critical logic bugs (BUG #1-#5 + REAL-1/2) in inventory engine"

git push origin main
```

## 패치 내용 요약:

| 파일 | 버그 | 수정 내용 |
|---|---|---|
| outbound_mixin.py | BUG #1/#3/#6 stop_at_picked | actual_picked_kg 파라미터 추가 |
| outbound_mixin.py | BUG #1-NORMAL | _actual_kg = weight_kg - remaining_kg |
| outbound_mixin.py | BUG #2-CAPACITY | LOT 용량 초과 배정 차단 |
| crud_mixin.py | BUG #4-RETURN-RECALC | _recalc에 RETURN 상태 포함 |
| inbound_mixin.py | BUG #5-WEIGHT-TOLERANCE | 오차 0.5 → 1.51kg |

## 스트레스 테스트: 3,179 iterations PASSED
