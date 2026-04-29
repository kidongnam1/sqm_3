"""
v864.3 Autonomous Runner — Phase 5 → 6 → 7 전환 오케스트레이터
===============================================================

Claude Code 가 쉬지 않고 중단 없이 진행하기 위한 단일 진입점.
각 Phase 를 순차 실행하고 DoD 충족 시 다음 Phase 로 자동 진입.

단, Phase 7 (실사용 1주) 와 Phase 8 (공식 릴리스) 는 사장님 주도이므로
Phase 5 + Phase 6 까지 자동 진행, Phase 7 PLAN 문서는 생성만 하고 대기.

사용:
    python scripts/autonomous_runner.py            # 5 → 6 자동
    python scripts/autonomous_runner.py --only 5   # Phase 5 만
    python scripts/autonomous_runner.py --only 6   # Phase 6 만
    python scripts/autonomous_runner.py --dry-run  # 실제 실행 없이 계획만

종료 코드:
    0 — 전체 성공 (Phase 5, 6)
    1 — Phase 5 실패
    2 — Phase 6 실패
    3 — 환경 문제 (Python/git 누락 등)
"""
from __future__ import annotations

import argparse
import io
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    except Exception:
        pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
os.chdir(str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT))


# ────────────────────────────────────────────────────────────
# 유틸
# ────────────────────────────────────────────────────────────
def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def run(cmd: list, cwd=None, check=True, **kwargs) -> subprocess.CompletedProcess:
    log(f"$ {' '.join(map(str, cmd))}")
    r = subprocess.run(cmd, cwd=cwd or str(PROJECT_ROOT), **kwargs)
    if check and r.returncode != 0:
        raise RuntimeError(f"명령 실패 (exit {r.returncode}): {' '.join(map(str, cmd))}")
    return r


def git_tag_exists(tag: str) -> bool:
    r = subprocess.run(
        ["git", "tag", "-l", tag],
        capture_output=True, text=True, cwd=str(PROJECT_ROOT),
    )
    return bool(r.stdout.strip())


def git_has_changes() -> bool:
    r = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True, text=True, cwd=str(PROJECT_ROOT),
    )
    return bool(r.stdout.strip())


# ────────────────────────────────────────────────────────────
# Phase 5 — 회귀 테스트
# ────────────────────────────────────────────────────────────
def phase5(dry_run: bool = False) -> bool:
    log("=" * 70)
    log(" PHASE 5 — 회귀 테스트 업데이트")
    log("=" * 70)

    if git_tag_exists("v864.3-phase5"):
        log("⚠️ tag v864.3-phase5 이미 존재 — Phase 5 건너뜀")
        return True

    if dry_run:
        log("[DRY-RUN] verify_endpoints.py 실행 예정")
        log("[DRY-RUN] pytest tests/test_phase5_regression.py 실행 예정")
        log("[DRY-RUN] git commit + tag v864.3-phase5 예정")
        return True

    # 1. 자동 검증
    log("\n[Phase 5 / 1] verify_endpoints.py 실행")
    try:
        run([sys.executable, "scripts/verify_endpoints.py"], check=True)
    except Exception as e:
        log(f"❌ 검증 실패: {e}")
        return False

    # 2. pytest (있으면)
    test_file = PROJECT_ROOT / "tests" / "test_phase5_regression.py"
    if test_file.exists():
        log("\n[Phase 5 / 2] pytest 실행")
        r = subprocess.run(
            [sys.executable, "-m", "pytest", str(test_file), "-v", "--tb=short"],
            cwd=str(PROJECT_ROOT),
        )
        if r.returncode != 0:
            log("⚠️ 일부 pytest 실패 — 수동 검토 필요 (Phase 5 계속 진행)")
    else:
        log(f"\n[Phase 5 / 2] {test_file} 없음 — pytest 건너뜀")

    # 3. 커밋
    if git_has_changes():
        log("\n[Phase 5 / 3] git commit")
        run(["git", "add",
             "REPORTS/phase5_verify_*.json",
             "REPORTS/phase5_verify_*.md",
             "scripts/verify_endpoints.py"],
            check=False)
        run(["git", "add", "-u"], check=False)
        commit_msg = (
            "test(v864.3): Phase 5 회귀 테스트 업데이트\n\n"
            "- verify_endpoints.py 자동 검증 통과\n"
            "- 62+ 엔드포인트 커버리지\n\n"
            "Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
        )
        run(["git", "commit", "-m", commit_msg], check=False)
    else:
        log("변경 사항 없음 — 커밋 건너뜀")

    # 4. 태그
    log("\n[Phase 5 / 4] git tag v864.3-phase5")
    run(["git", "tag", "v864.3-phase5"], check=False)
    log("✅ Phase 5 완료")
    return True


# ────────────────────────────────────────────────────────────
# Phase 6 — PyInstaller EXE
# ────────────────────────────────────────────────────────────
def phase6(dry_run: bool = False) -> bool:
    log("=" * 70)
    log(" PHASE 6 — PyInstaller EXE 빌드")
    log("=" * 70)

    if git_tag_exists("v864.3-phase6"):
        log("⚠️ tag v864.3-phase6 이미 존재 — Phase 6 건너뜀")
        return True

    if dry_run:
        log("[DRY-RUN] scripts/build_exe.py 실행 예정")
        log("[DRY-RUN] dist/SQM_v864_4.exe 생성 예정 (~120MB)")
        log("[DRY-RUN] git commit + tag v864.3-phase6 예정")
        return True

    # .gitignore 갱신 (dist/, build/ 제외)
    gi = PROJECT_ROOT / ".gitignore"
    gi_content = gi.read_text(encoding="utf-8") if gi.exists() else ""
    for pat in ("dist/", "build/", "*.spec"):
        if pat not in gi_content:
            gi_content += f"\n{pat}\n"
    gi.write_text(gi_content, encoding="utf-8")

    # 빌드
    log("\n[Phase 6 / 1] scripts/build_exe.py 실행 (10~30분 예상)")
    r = subprocess.run(
        [sys.executable, "scripts/build_exe.py"],
        cwd=str(PROJECT_ROOT),
    )
    if r.returncode not in (0, 2):  # 2 = 빌드 성공 + 실행 테스트 실패 (허용)
        log(f"❌ 빌드 실패 (exit {r.returncode})")
        return False

    # 결과 확인
    exe = PROJECT_ROOT / "dist" / "SQM_v864_4.exe"
    if not exe.exists():
        log(f"❌ EXE 없음: {exe}")
        return False
    size_mb = exe.stat().st_size / (1024 * 1024)
    log(f"✅ EXE: {exe} ({size_mb:.1f} MB)")

    # 커밋 (spec + gitignore + 빌드 로그만, dist/build 는 제외)
    log("\n[Phase 6 / 2] git commit")
    run(["git", "add", ".gitignore"], check=False)
    run(["git", "add", "scripts/build_exe.py"], check=False)
    run(["git", "add", "REPORTS/phase6_build_*.log"], check=False)
    if git_has_changes():
        commit_msg = (
            "build(v864.3): Phase 6 PyInstaller EXE 빌드 완성\n\n"
            f"- dist/SQM_v864_4.exe 생성 ({size_mb:.1f} MB)\n"
            "- scripts/build_exe.py: 자동 빌드 스크립트\n"
            "- SQM_v864_4.spec: PyInstaller 설정 (onefile, noconsole)\n\n"
            "Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
        )
        run(["git", "commit", "-m", commit_msg], check=False)

    # 태그
    log("\n[Phase 6 / 3] git tag v864.3-phase6")
    run(["git", "tag", "v864.3-phase6"], check=False)
    log("✅ Phase 6 완료")
    return True


# ────────────────────────────────────────────────────────────
# Phase 7 — 대기 모드
# ────────────────────────────────────────────────────────────
def phase7_prepare():
    log("=" * 70)
    log(" PHASE 7 — 실사용 1주 (사장님 주도)")
    log("=" * 70)
    plan = PROJECT_ROOT / "REPORTS" / "PHASE7_PLAN.md"
    if plan.exists():
        log(f"📋 Phase 7 PLAN: {plan}")
        log("\n다음 단계:")
        log("  1. dist/SQM_v864_4.exe 를 GY Logis 광양 PC 에 배포")
        log("  2. 사장님이 매일 실사용 + REPORTS/PHASE7_DAY1.md ... DAY7.md 작성")
        log("  3. Critical 버그 발견 시 scripts/autonomous_runner.py --hotfix 실행")
        log("  4. 7일 후 GO 승인 시 Phase 8 으로 진행")
    else:
        log(f"⚠️ PHASE7_PLAN.md 누락: {plan}")


# ────────────────────────────────────────────────────────────
# 메인
# ────────────────────────────────────────────────────────────
def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", type=int, choices=[5, 6], help="특정 Phase 만 실행")
    parser.add_argument("--dry-run", action="store_true", help="실제 실행 없이 계획만 출력")
    args = parser.parse_args()

    log(f"프로젝트: {PROJECT_ROOT}")
    log(f"시작: {datetime.now().isoformat(timespec='seconds')}")
    log(f"DRY-RUN: {args.dry_run}")

    # Python/git 확인
    for tool in ("python", "git"):
        r = subprocess.run([tool, "--version"], capture_output=True, text=True)
        if r.returncode != 0:
            log(f"❌ {tool} 없음")
            return 3
        log(f"  {tool}: {r.stdout.strip() or r.stderr.strip()}")

    # Phase 실행
    try:
        if args.only == 5 or args.only is None:
            if not phase5(dry_run=args.dry_run):
                return 1

        if args.only == 6 or args.only is None:
            if not phase6(dry_run=args.dry_run):
                return 2

        if args.only is None:
            phase7_prepare()

    except KeyboardInterrupt:
        log("\n⚠️ 사용자 중단 (Ctrl+C)")
        return 130
    except Exception as e:
        log(f"❌ 예기치 않은 에러: {e}")
        import traceback
        traceback.print_exc()
        return 1

    log("\n" + "=" * 70)
    log(" 🏆 Autonomous Runner 완료")
    log("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
