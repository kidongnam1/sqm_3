@echo off
chcp 65001 > nul
cd /d D:\program\SQM_inventory\SQM_v866_CLEAN
echo ===== SQM v8.6.6 + PL Parser + JS Restore - Git Push =====

if exist .git\index.lock del /f .git\index.lock
echo [1] index.lock cleared

git restore --staged data/db/sqm_inventory.db 2>nul
git add .gitignore
echo [2] gitignore staged

git add CLAUDE.md
git add backend\api\__init__.py
git add backend\api\inbound.py
git add backend\api\outbound_picking.py
git add parsers\document_parser_modular\ai_fallback.py
git add parsers\document_parser_modular\bl_mixin.py
git add parsers\document_parser_modular\picking_mixin.py
git add utils\parse_alarm.py
git add tools\fix_carrier_rules_one.py
git add frontend\js\sqm-inline.js
git add frontend\js\sqm-onestop-inbound.js
git add frontend\index.html
git add scripts\menu_patch_1_structure.py
git add scripts\menu_patch_2_cleanup.py
echo [3] files staged

git commit -m "chore: add sqm_inventory.db to .gitignore" 2>nul
if errorlevel 1 echo [INFO] gitignore commit skipped

git commit -m "feat(picking): Picking List parser + JS restore + endpoint wiring

- outbound_picking.py: POST /api/outbound/picking (text+image PDF support)
- picking_mixin.py: parse_picking_list_auto() unified entry, _detect_pdf_type()
- ai_fallback.py: parse_picking_ai() Gemini Vision for scanned PDFs
- sqm-inline.js: restored ENDPOINTS+dispatchAction+bindAll+boot (5817->7588 lines)
- showPickingListPdfModal: endpoint updated + rich result UI (meta/tonbag/sample)
- JS syntax OK, null bytes 0, data-action 86/88 covered"
if errorlevel 1 echo [INFO] picking commit skipped

echo [4] commits done

git stash push -m "wip_unstaged"
echo [5] stash done

git pull --rebase origin main
if errorlevel 1 (
    echo [ERROR] rebase failed - running stash pop and aborting
    git rebase --abort 2>nul
    git stash pop
    pause
    exit /b 1
)
echo [6] rebase done

git stash pop
echo [7] stash pop done

git push origin main
if errorlevel 1 (
    echo [ERROR] push failed
    pause
    exit /b 1
)

echo.
echo ==========================================
echo   Push complete - v8.6.6 + Phase1 + Menu
echo ==========================================
pause
