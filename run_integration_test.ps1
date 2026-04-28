# SQM v865 - AI fallback integration test
# Run: .\run_integration_test.ps1

$UPLOADS = "$env:USERPROFILE\AppData\Roaming\Claude\local-agent-mode-sessions\07665fd4-da1f-402c-bb3e-8c67be3d094b\7b352852-70c9-442b-94f9-960aba799136\local_d82e5c24-99cb-441b-bd41-737a0dff248d\uploads"

$env:TEST_FA_ONE = "$UPLOADS\2200034590 FA-2b8b8cd3.PDF"
$env:TEST_BL_ONE = "$UPLOADS\2200034590 BL-abdbde9d.pdf"
$env:TEST_DO_ONE = "$UPLOADS\ONEYSCLG01825300 DO-db84cfc0.pdf"

Write-Host "[vars set]" -ForegroundColor Cyan
Write-Host "  FA: $env:TEST_FA_ONE"
Write-Host "  BL: $env:TEST_BL_ONE"
Write-Host "  DO: $env:TEST_DO_ONE"
Write-Host ""

# verify files exist
foreach ($v in @($env:TEST_FA_ONE, $env:TEST_BL_ONE, $env:TEST_DO_ONE)) {
    if (Test-Path $v) { Write-Host "  [OK] $v" -ForegroundColor Green }
    else              { Write-Host "  [MISSING] $v" -ForegroundColor Red }
}
Write-Host ""

pytest tests/test_ai_fallback_parity.py -m integration -v --timeout=90
